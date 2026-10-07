"""
States, comparisons and the share view.

Navigation lives in the URL so titles in tables are plain links:
    ?client=<c>                         client home
    ?client=<c>&state=<id>              state report
    ?client=<c>&state=<id>&edit=1       state editor
    ?client=<c>&comparison=<id>         comparison
    ...&share=1                         read-only view for prospects
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.corporate import (
    inject_css, esc, money, money_short, num, rate, pct, days, signed, red, table, card, page_title, subtitle,
    chart, PALETTE, NAVY, RED, GOLD, INK, RULE,
)
from ui import graphs as G
from engine.events import (
    State, Offer, MarketingEvent, FixedExpense, Upgrade, FinancingEvent, simulate, clone_state, split_row,
    build_schedule, state_to_dict, state_from_dict, offer_economics, existing_book, event_mix,
)
from engine.state_metrics import compute_state_kpis, compute_state_valuation, channel_targets, customer_economics
from store.client import list_clients, load_client_meta, create_client, delete_client
from store.states import (
    Comparison, list_states, load_state, save_state, delete_state,
    list_comparisons, load_comparison, save_comparison, delete_comparison, seed_example,
)

inject_css()

CHANNELS = ["Paid Advertising", "Outbound Prospecting", "Organic", "Viral", "Referral", "Partnerships", "Other"]
DRIVERS = ["spend", "outbound", "volume", "viral", "team"]


# ── Computation (cached on the state's content) ──────────────────────

@st.cache_data(show_spinner=False, max_entries=128)
def _run(state_json: str, at_day: int | None):
    s = state_from_dict(json.loads(state_json))
    r = simulate(s)
    return r, compute_state_kpis(s, r, at_day), compute_state_valuation(s, r)


def run(s: State, at_day: int | None = None):
    return _run(json.dumps(state_to_dict(s), sort_keys=True, default=str), at_day)


def short_names(titles: list) -> list:
    """Drop the shared "Client - " prefix so labels say what differs."""
    if len(titles) < 2:
        return list(titles)
    parts = [t.split(" - ") for t in titles]
    k = 0
    while all(len(p) > k + 1 for p in parts) and len({p[k] for p in parts}) == 1:
        k += 1
    return [" - ".join(p[k:]) for p in parts]


# ── Navigation ────────────────────────────────────────────────────────

def qp(name: str, default=None):
    return st.query_params.get(name, default)


def href(**params) -> str:
    return "?" + "&".join(f"{k}={v}" for k, v in params.items() if v not in (None, ""))


def link(text: str, **params) -> str:
    return f'<a class="c-red" href="{href(**params)}" target="_self" style="text-decoration:none">{esc(text)}</a>'


def go_to(**params) -> None:
    st.query_params.clear()
    for k, v in params.items():
        if v not in (None, ""):
            st.query_params[k] = str(v)
    st.rerun()


# ── Read-only blocks ──────────────────────────────────────────────────

def sim_parameters_html(s: State, client: str, share: bool) -> str:
    title = esc(s.title) if share else link(s.title, client=client, state=s.id)
    rows = [
        ["Title", f'<span class="c-red">{title}</span>' if share else title],
        ["Description", esc(s.description)],
        ["Time Span", num(float(s.time_span))],
        ["Projection Period", num(float(s.projection_period))],
        ["Discount Rate", rate(s.discount_rate)],
        ["Tax Rate", rate(s.tax_rate)],
        ["Loss Carryforward", "Yes" if s.loss_carryforward else "No"],
        ["Perpetual Growth Rate", rate(s.perpetual_growth_rate)],
        ["EBITDA Multiple", num(s.ebitda_multiple)],
        ["EBITDA Projection Period", num(float(s.ebitda_projection_period))],
        ["Shares", f"{int(s.shares):,}"],
        ["LTV Horizon", f"{num(s.ltv_years)} years"],
        ["CAC Spend Lag", "Auto (time to sale)" if s.cac_lag_days < 0 else days(s.cac_lag_days)],
        ["Created", esc(s.created)],
    ]
    if not share:
        rows.append(["Edit", link("Edit", client=client, state=s.id, edit=1)])
    return table([], rows, kv=True)


def starting_state_html(s: State) -> str:
    book = existing_book(s)
    ex = "<br>".join(f"{num(n)} on {esc(o)}" for o, n in book.items()) if book else "0"
    if len(book) > 1:
        ex = f"{num(sum(book.values()))} total<br>" + ex
    return table([], [
        ["Starting Cash", money(s.starting_cash)],
        ["Assets", money(s.assets)],
        ["Liabilities", money(s.liabilities)],
        ["Debt", money(s.debt)],
        ["Interest Rate", rate(s.interest_rate)],
        ["Upfront Investment", money(s.upfront_investment)],
        ["Existing Customers", ex],
        ["Total Addressable Market", num(s.total_addressable_market) if s.total_addressable_market else "No cap"],
        ["Transaction Fee", rate(s.transaction_fee)],
    ], kv=True)


def offers_html(s: State, compact: bool = False) -> str:
    active = s.active_offer_names()
    book = existing_book(s)
    rows = []
    for o in s.offers:
        e = offer_economics(o)
        status = "Active" if o.name in active else "Inactive"
        if compact:
            rows.append([red(o.name), o.billing.title(), money(o.price), money(e["expected_value"]), money(e["ltv"]),
                         rate(o.churn_rate) if o.billing == "contract" else f"{len(o.payments)} payments", status])
            continue
        if o.billing == "schedule":
            c = ["–"] * 2 + [f"{len(o.payments)} payments"] + ["–"] * 9
            rows.append([red(o.name), "Schedule", num(round(book.get(o.name, 0))), money(o.price), money(e["expected_value"]), money(e["ltv"]),
                         rate(o.realization_rate), rate(o.cost_to_sell), rate(o.cost_to_fulfill)] + c[2:] + [status])
        else:
            rows.append([red(o.name), "Contract", num(round(book.get(o.name, 0))), money(o.price), money(e["expected_value"]), money(e["ltv"]),
                         rate(o.realization_rate), rate(o.cost_to_sell), rate(o.cost_to_fulfill), o.time_to_collect,
                         o.contract_length, o.refund_period, rate(o.refund_rate), rate(o.churn_rate),
                         money(o.renewal_price), o.renewal_time_to_collect, rate(o.renewal_cost_to_sell),
                         rate(o.renewal_cost_to_fulfill), rate(o.renewal_rate_of_renewals), status])
    if compact:
        return table(["Offer", "Billing", "Price", "Expected Value", "LTV", "Churn", "Status"], rows, num_cols={2, 3, 4})
    return table(["Offer", "Billing", "Existing Customers", "Price", "Expected Value", "LTV", "Realization Rate",
                  "Cost To Sell", "Cost To Fulfil", "Time To Collect", "Contract Length", "Refund Period", "Refund Rate",
                  "Churn Rate", "Renewal Price", "Renewal Time To Collect", "Renewal Cost To Sell",
                  "Renewal Cost To Fulfil", "Renewal Rate Of Renewals", "Status"], rows, num_cols=set(range(2, 19)))


def payment_chart(s: State, key: str, height: int = 300) -> None:
    fig = go.Figure()
    active = s.active_offer_names()
    for i, o in enumerate(s.offers):
        pts = offer_economics(o)["points"]
        if not pts:
            continue
        status = "Active" if o.name in active else "Inactive"
        fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts],
                                 mode="lines+markers" if len(pts) <= 24 else "lines",
                                 name=o.name if status == "Active" else f"{o.name} (inactive)",
                                 line=dict(color=PALETTE[(i + 1) % len(PALETTE)], width=2,
                                           dash="solid" if status == "Active" else "dot")))
    chart(fig, "Payment Schedule (expected cash per sale, by period)", height, money_axis=True, key=key)


def _d(v, ok: bool, f=num):
    return f(v) if ok else "–"


# ── Channel types: each section shows only its own inputs, in natural units ──
# kinds: pct (stored as fraction, shown in %), money, money_m / num_m (stored per day, shown per month), num, int
EV_HEAD = [("Title", "title", "text"), ("Offer", "offer", "offer"), ("Offer Mix", "offer_mix", "mix"),
           ("Channel", "channel", "channel"), ("Start Day", "start_day", "int"), ("End Day", "end_day", "int")]
EV_TAIL = [("Time To Market (Days)", "time_to_market", "int"), ("Sales Cycle (Days)", "sales_cycle_days", "int"),
           ("Cost To Sell", "cost_to_sell_override", "override"), ("Validated", "validated", "bool"),
           ("Validation Data", "validation_note", "note")]
FIN_KINDS = ["equity", "grant", "loan"]
TYPE_CHANNELS = {
    "spend": ["Paid Advertising", "Paid Search", "Paid Social"],
    "outbound": ["Multichannel Outbound", "Outbound Prospecting", "Cold Email", "Cold Calling", "LinkedIn Outreach"],
    "volume": ["SEO", "Content", "Reviews", "Community", "Organic"],
    "viral": ["Viral", "Referral"],
    "team": ["Outbound Prospecting"],
}
CHANNEL_TYPES = [
    ("spend", "Paid Ads", "Paid Advertising",
     "Display and social: give CPM and CTR, cost per click follows (CPM / 1,000 / CTR). Search: give cost per click "
     "instead and leave CPM at 0. Clicks become leads (signups, trials, demo requests), leads become customers.",
     [("Spend Per Month", "spend_per_day", "money_m"), ("Cost Per Click (optional)", "cost_per_click", "money"),
      ("CPM", "cpm", "money"), ("CTR", "ctr", "pct"),
      ("Click To Lead", "lead_to_view", "pct"), ("Lead To Customer", "sale_to_lead", "pct")]),
    ("outbound", "Outbound", "Outbound Prospecting",
     "Volume is contacts per day, not people, so one GTM engineer can scale sending. Put the people running this "
     "channel in People Cost here, not in fixed expenses. Mailboxes × sends per mailbox caps the volume (0 = no cap). "
     "Contacts → leads (replies) → interested → meetings held → customers.",
     [("Contacts Per Day", "contacts_per_day", "num"), ("Cost Per Contact", "cost_per_contact", "money"),
      ("People Cost Per Month", "people_cost_per_month", "money"), ("Tools Cost Per Month", "tools_cost_per_month", "money"),
      ("Mailboxes", "mailboxes", "num"), ("Sends Per Mailbox Per Day", "sends_per_mailbox_per_day", "num"),
      ("Contact To Lead Rate", "contact_to_lead_rate", "pct"), ("Positive Reply Rate", "positive_reply_rate", "pct"),
      ("Meeting Rate", "meeting_rate", "pct"), ("Close Rate", "close_rate", "pct")]),
    ("volume", "Organic, Content and SEO", "SEO",
     "Visitors per month from search, content, reviews or community. Content cost is what the channel costs to run "
     "(writers, tools); it counts toward CAC.",
     [("Visits Per Month", "views_per_day", "num_m"), ("Content Cost Per Month", "spend_per_day", "money_m"),
      ("Visit To Lead", "lead_to_view", "pct"), ("Lead To Customer", "sale_to_lead", "pct")]),
    ("viral", "Viral and Referral", "Viral",
     "New customers = active customers × invites per customer per contract period × invite conversion.",
     [("Invites Per Customer Per Period", "invites_per_customer", "num"), ("Invite Conversion", "invite_conversion", "pct"),
      ("Cost To Market Per Sale (% of price)", "viral_cost_to_market", "pct")]),
    ("team", "SDR Team (headcount-based)", "Outbound Prospecting",
     "Outbound where contacts scale with headcount. Use Outbound for volume-based sending.",
     [("Headcount", "headcount", "num"), ("Salary Per Month", "salary_per_month", "money"),
      ("Contacts Per Head Per Month", "contacts_per_head_per_month", "num"), ("Contact Rate", "ctr", "pct"),
      ("Contact To Lead", "lead_to_view", "pct"), ("Lead To Customer", "sale_to_lead", "pct")]),
]


def _ev_display(e, attr, kind):
    v = getattr(e, attr)
    if attr == "cost_per_click" and not v:  # derived from CPM and CTR unless set directly
        if e.cpm > 0 and e.ctr > 0:
            return f'{money(e.cpm / (1000.0 * e.ctr))} <span class="c-muted" style="font-size:11px">from CPM</span>'
        return "–"
    if attr == "cpm" and e.cost_per_click > 0:  # the other way round: CPC given, CPM is derived
        return f'{money(e.cost_per_click * e.ctr * 1000.0)} <span class="c-muted" style="font-size:11px">from CPC</span>' if e.ctr > 0 else "–"
    if kind == "offer":
        return esc(mix_to_text(e.offer_mix)) if e.offer_mix else red(e.offer)
    if kind in ("text", "channel", "note"):
        return esc(v)
    if kind == "bool":
        return "Validated" if v else '<span class="c-hyp">Hypothesis</span>'
    if kind == "int":
        return f"{int(v):,}"
    if kind == "pct":
        return rate(v)
    if kind == "override":
        return "Offer's" if v < 0 else rate(v)
    if kind == "money":
        return money(v)
    if kind == "money_m":
        return money(v * 30.0, 0)
    if kind == "num_m":
        return num(round(v * 30.0))
    return num(v)


def events_html(s: State, r=None) -> str:
    parts = []
    for key, label, _, _, cols in CHANNEL_TYPES:
        evs = [e for e in s.events if e.driver == key]
        if not evs:
            continue
        spec_ = [c for c in EV_HEAD if c[2] != "mix"] + cols + EV_TAIL
        rows = [[_ev_display(e, a, kd) for _, a, kd in spec_] for e in evs]
        heads = [lbl for lbl, _, _ in spec_]
        num_cols = {i for i, (_, _, kd) in enumerate(spec_) if kd not in ("text", "offer", "channel", "bool", "note")}
        parts.append(f'<div class="c-evtype">{esc(label)}</div>' + table(heads, rows, num_cols=num_cols))
    return "".join(parts) or "<p>No marketing events.</p>"


def validation_summary(s: State) -> str:
    n = len(s.events)
    v = sum(1 for e in s.events if e.validated)
    if n == 0:
        return ""
    if v == n:
        return f"All {n} marketing rows validated."
    return f"{v} of {n} marketing rows validated, {n - v} hypothesis."


def financing_html(s: State) -> str:
    rows = []
    for f in s.financing:
        if f.kind == "loan":
            detail = (f"{rate(f.interest_rate)} interest, repaid over {f.maturity_days:,} days"
                      + (f", {f.grace_days:,} days grace" if f.grace_days else "")
                      + (", compounding" if f.compounding else ""))
        elif f.kind == "equity":
            detail = (f"{money(f.valuation, 0)} pre-money" if f.valuation else "") + \
                     (f", {num(f.shares_issued)} shares issued" if f.shares_issued else "")
            detail = detail.strip(", ") or "–"
        else:
            detail = esc(f.purpose) or "–"
        rows.append([red(f.title), f.kind.title(), f"{int(f.day):,}", money(f.amount, 0), detail, esc(f.terms)])
    return table(["Title", "Type", "Day", "Amount", "Details", "Terms"], rows, num_cols={2, 3})


def funnel_html(r) -> str:
    rows = []
    for f in r.funnels:
        rows.append([esc(f.title), esc(f.channel), money(f.spend_per_day), num(f.impressions), num(f.views),
                     num(f.leads), num(f.sales), money(f.cost_per_lead), money(f.cac), money(f.expected_value),
                     money(f.ltv), (f"{f.ev_to_cac:,.2f}" if np.isfinite(f.ev_to_cac) else "–"),
                     (f"{f.ltv_to_cac:,.2f}" if np.isfinite(f.ltv_to_cac) else "–"), f.days_active,
                     money(f.total_spend, 0), num(round(f.total_sales, 1)), f.cash_conversion_cycle])
    return table(["Title", "Channel", "Cost Per Day", "Reached Per Day", "Engaged Per Day",
                  "Leads / Meetings Per Day", "Sales Per Day", "Cost Per Lead", "CAC", "Expected Value", "LTV", "EV : CAC",
                  "LTV : CAC", "Days Active", "Total Spend", "Total Sales", "Cash Conversion Cycle (Days)"],
                 rows, num_cols=set(range(2, 17)))


def expenses_html(s: State) -> str:
    rows = [[red(x.title), esc(x.description), x.start_day, x.end_day, money(x.amount_per_day),
             money(x.per_100_customers_per_day), "Employee" if x.employee else "Not Employee",
             "Yes" if x.sales_marketing else "–"] for x in s.expenses]
    return table(["Title", "Description", "Start Time", "End Time", "Amount (per day)",
                  "Per 100 Customers (per day)", "Employee", "Sales & Marketing"], rows, num_cols={2, 3, 4, 5})


def upgrades_html(s: State) -> str:
    rows = [[esc(u.from_offer), esc(u.to_offer), rate(u.monthly_rate), u.start_day, u.end_day, esc(u.description)]
            for u in s.upgrades]
    return table(["From Offer", "To Offer", "Monthly Rate", "Start Day", "End Day", "Description"], rows,
                 num_cols={2, 3, 4})


def offers_at_day_html(s: State, r, at: int) -> str:
    """Active customers and cash per offer at a day."""
    book = existing_book(s)
    a0 = max(0, at - 29)
    tot_active = float(r.active_customers[at]) or 1.0
    rows = []
    for o in s.offers:
        act = float(r.active_by_offer.get(o.name, np.zeros(1))[at]) if r.active_by_offer else 0.0
        cash30 = float(r.revenue_by_offer.get(o.name, np.zeros(at + 1))[a0:at + 1].sum())
        sold = float(r.sales_by_offer.get(o.name, np.zeros(at + 1))[:at + 1].sum()) if r.sales_by_offer else 0.0
        upin = float(r.upgrades_in.get(o.name, np.zeros(at + 1))[:at + 1].sum()) if r.upgrades_in else 0.0
        upout = float(r.upgrades_out.get(o.name, np.zeros(at + 1))[:at + 1].sum()) if r.upgrades_out else 0.0
        if not (act or cash30 or sold or book.get(o.name)):
            continue
        rows.append([red(o.name), num(round(book.get(o.name, 0.0))), num(round(sold)), num(round(upin)),
                     num(round(upout)), num(round(act)), pct(act / tot_active * 100.0),
                     money(cash30, 0), money(cash30 / act if act > 0 else 0.0)])
    return table(["Offer", "Existing (day 0)", "New Sales", "Upgrades In", "Upgrades Out", "Active", "Share Of Active",
                  "Cash Last 30 Days", "Cash Per Active"], rows, num_cols=set(range(1, 9)))


def kpi_tables(k, v, s: State) -> tuple:
    a, b = k.cac_window
    ratio = lambda x: f"{x:,.2f}" if np.isfinite(x) else "–"
    unit = table([], [
        ["CAC (fully loaded, 12 months)", f"<b>{money(k.cac_blended)}</b>"],
        ["Sales & marketing cost", money(k.sm_cost, 0)],
        ["New customers", num(round(k.sm_new_customers))],
        ["Window", f"days {a:,}–{b:,}, spend lagged {k.cac_lag} days"],
        ["CAC ratio ($ S&M per $1 new ARR)", ratio(k.cac_ratio)],
        ["New ARR / expansion ARR", f"{money(k.new_arr, 0)} / {money(k.expansion_arr, 0)}"],
        [f"LTV ({num(s.ltv_years)} years, discounted)", f"<b>{money(k.ltv)}</b>"],
        ["LTV : CAC", f"<b>{ratio(k.ltv_cac_ratio)}</b>"],
        ["CAC payback", (f"{k.payback_months:,.1f} months" if np.isfinite(k.payback_months) else "–")],
        ["Payback (cash, net of delivery)", days(k.payback_period_days)],
        ["Expected value per sale", money(k.expected_value)],
        ["LTV (20 years, undiscounted)", money(k.ltv_20y)],
        ["Cash conversion cycle", days(k.cash_conversion_cycle)],
        ["K value (viral)", num(k.k_value, 3)],
    ], kv=True)
    run_rate = table([], [
        ["Revenue booked", money(k.monthly_revenue)],
        ["Cash collected", money(k.monthly_cash_collected)],
        ["Free cash flow", money(k.monthly_fcf)],
        ["New customers", num(round(k.monthly_new_customers, 2))],
        ["Gross margin", pct(k.gross_margin)],
        ["EBITDA margin", pct(k.ebitda_margin)],
        ["Net margin", pct(k.net_margin)],
        ["Profit per customer per month", money(k.profit_per_customer_per_month)],
    ], kv=True)
    cash = table([], [
        ["Cash needed", money(k.cash_needed)],
        ["Cash consumption", money(k.cash_consumption)],
        ["Lowest cash balance", f"{money(k.min_cash)} (day {k.min_cash_day:,})"],
        ["Time to profitability", days(k.time_to_profitability_days)],
        ["Time to self-fund", days(k.time_to_self_fund_days)],
        ["Total customers", num(round(k.total_customers, 1))],
        ["Active customers", num(round(k.active_customers, 1))],
    ], kv=True)
    val = table([], [
        [f"Total discounted cash flow after tax (day {min(s.projection_period, s.time_span):,})",
         f"<b>{money(v.dcf_cumulative)}</b>"],
        ["Per share", money(v.dcf_per_share, 4)],
        ["PV of free cash flow", money(v.pv_fcf)],
        ["Terminal value", money(v.terminal_value)],
        ["PV of terminal value", money(v.pv_terminal_value)],
        ["Enterprise value (DCF)", money(v.enterprise_value_dcf)],
        ["Equity value (DCF)", money(v.equity_value_dcf)],
        ["Share price (DCF)", money(v.share_price_dcf, 4)],
        ["Trailing 12-month EBITDA", money(v.trailing_ebitda)],
        [f"Enterprise value (EBITDA × {num(s.ebitda_multiple)})", money(v.enterprise_value_ebitda)],
        ["Equity value (EBITDA)", money(v.equity_value_ebitda)],
        ["Share price (EBITDA)", money(v.share_price_ebitda, 4)],
        ["Cash at valuation", money(v.cash_at_valuation)],
        ["Net debt", money(v.net_debt)],
    ], kv=True)
    return unit, run_rate, cash, val


def statement_html(r, period: int, n_periods: int, label: str) -> str:
    T = len(r.days)
    n = min(n_periods, int(np.ceil(T / period)))
    edges = [(i * period, min((i + 1) * period, T)) for i in range(n)]
    S = lambda arr: [float(arr[a:b].sum()) for a, b in edges]
    E = lambda arr: [float(arr[b - 1]) for a, b in edges]
    lines = [
        ("Cash collected, new sales", S(r.cash_collected_new), ""),
        ("Cash collected, renewals", S(r.cash_collected_renewal), ""),
        ("Total cash collected", S(r.cash_collected_total), "c-total"),
        ("Fulfilment", [-x for x in S(r.cost_fulfillment)], ""),
        ("Transaction fees", [-x for x in S(r.cost_transaction_fees)], ""),
        ("Gross profit", S(r.gross_profit), "c-total"),
        ("Marketing", [-x for x in S(r.cost_marketing)], ""),
        ("Sales", [-x for x in S(r.cost_sales)], ""),
        ("Fixed expenses", [-x for x in S(r.cost_fixed)], ""),
        ("Refunds", [-x for x in S(r.cost_refunds)], ""),
        ("EBITDA", S(r.ebitda), "c-total"),
        ("Interest", [-x for x in S(r.cost_interest)], ""),
        ("Tax", [-x for x in S(r.tax)], ""),
        ("Free cash flow", S(r.free_cash_flow), "c-total"),
        ("Discounted cash flow", S(r.dcf), ""),
        ("Cumulative discounted cash flow", E(r.cum_dcf), ""),
        ("Cash balance (end)", E(r.cash_balance), "c-total"),
    ]
    counts = [
        ("Leads", S(r.leads)), ("New customers", S(r.new_customers_total)),
        ("Active customers (end)", E(r.active_customers)), ("Renewals", S(np.diff(np.concatenate([[0], r.renewed_customers])))),
    ]
    rows, cls = [], []
    for name, vals, c in lines:
        rows.append([esc(name)] + [f"{v:,.0f}" if abs(v) >= 0.5 else "0" for v in vals])
        cls.append(c)
    rows.append(["Customers"] + [""] * n)
    cls.append("c-section")
    for name, vals in counts:
        rows.append([esc(name)] + [f"{v:,.1f}" for v in vals])
        cls.append("")
    return table([""] + [f"{label} {i + 1}" for i in range(n)], rows, num_cols=set(range(1, n + 1)), row_classes=cls)


def dcf_chart(named, compare_day, key):
    fig = go.Figure()
    for i, (name, r) in enumerate(named):
        fig.add_trace(go.Scatter(x=r.days, y=r.cum_dcf, mode="lines", name=name,
                                 line=dict(color=PALETTE[i % len(PALETTE)], width=3)))
    if compare_day is not None:
        fig.add_vline(x=compare_day, line=dict(color="#adb5bd", dash="dash"))
    chart(fig, "Total Discounted Cash Flow After Tax", 420, money_axis=True, key=key)


def cash_chart(named, key):
    fig = go.Figure()
    for i, (name, r) in enumerate(named):
        fig.add_trace(go.Scatter(x=r.days, y=r.cash_balance, mode="lines", name=name,
                                 line=dict(color=PALETTE[i % len(PALETTE)], width=2)))
    fig.add_hline(y=0, line=dict(color="#cbd5e1", width=1))
    chart(fig, "Cash Balance", 340, money_axis=True, key=key)


# ── State report ──────────────────────────────────────────────────────

def kpi_tiles(s: State, r, k, v) -> str:
    at = int(k.at_day)
    ratio = lambda x: f"{x:,.1f}" if np.isfinite(x) else "–"
    tiles = [
        ("Cash collected, last 30 days", money(k.monthly_cash_collected, 0)),
        ("Active customers", num(round(k.active_customers))),
        ("New customers, last 30 days", num(round(k.monthly_new_customers))),
        ("CAC (fully loaded)", money(k.cac_blended, 0)),
        ("LTV : CAC", ratio(k.ltv_cac_ratio)),
        ("CAC payback", f"{k.payback_months:,.1f} mo" if np.isfinite(k.payback_months) else "–"),
        ("Cash balance", money(float(r.cash_balance[at]), 0)),
        ("Total DCF after tax", money(v.dcf_cumulative, 0)),
    ]
    return '<div class="c-tiles">' + "".join(
        f'<div class="c-tile"><div class="lbl">{esc(l)}</div><div class="val">{x}</div></div>' for l, x in tiles
    ) + "</div>"


def monthly_cash_chart(r, key: str) -> None:
    m = len(r.days) // 30
    fig = go.Figure()
    mo = lambda arr: [float(arr[i * 30:(i + 1) * 30].sum()) for i in range(m)]
    fig.add_trace(go.Bar(x=list(range(1, m + 1)), y=mo(r.cash_collected_total), name="Cash collected", marker_color="#1e293b"))
    fig.add_trace(go.Bar(x=list(range(1, m + 1)), y=[-x for x in mo(r.cost_total)], name="Costs", marker_color="#cbd5e1"))
    fig.add_trace(go.Scatter(x=list(range(1, m + 1)), y=mo(r.free_cash_flow), name="Free cash flow",
                             line=dict(color="#2563eb", width=2)))
    fig.update_layout(barmode="relative", bargap=0.35)
    chart(fig, "Cash Collected and Costs per Month", 340, money_axis=True, key=key, xtitle="Month")


def render_inputs(client: str, s: State, r, share: bool, key: str) -> None:
    l, rgt = st.columns(2, gap="medium")
    card("Sim Parameters", sim_parameters_html(s, client, share), l)
    card("Starting State", starting_state_html(s), rgt)
    card("Offer Segments", offers_html(s))
    payment_chart(s, key=f"pc_{key}")
    card("Marketing Events", events_html(s))
    card("Funnel Per Event", funnel_html(r))
    card("Fixed Expenses", expenses_html(s))
    if s.upgrades:
        card("Upgrades", upgrades_html(s))
    if s.financing:
        card("Financing Events", financing_html(s))


def render_statement(s: State, r, share: bool, key: str) -> None:
    per = st.radio("Period", ["Monthly", "Quarterly", "Yearly"], horizontal=True, key=f"per_{key}",
                   label_visibility="collapsed")
    p, n, lab = {"Monthly": (30, 36, "M"), "Quarterly": (91, 40, "Q"), "Yearly": (365, 20, "Y")}[per]
    card(f"{per} Statement (first {n} periods)", statement_html(r, p, n, lab))
    if not share:
        df = pd.DataFrame({f: getattr(r, f) for f in (
            "days", "spend", "impressions", "views", "leads", "new_customers_total", "active_customers",
            "cash_collected_new", "cash_collected_renewal", "cost_marketing", "cost_sales", "cost_fulfillment",
            "cost_fixed", "cost_transaction_fees", "cost_refunds", "cost_interest", "ebitda", "tax",
            "free_cash_flow", "dcf", "cum_dcf", "cash_balance", "financing_in", "loan_repayment",
            "debt_outstanding", "shares_outstanding")})
        st.download_button("Download daily CSV", df.to_csv(index=False).encode(), file_name=f"{s.id}_daily.csv")


SECTIONS = ["Overview", "Graphs", "Inputs", "Statement"]


def section_nav(key: str, default: str = "Overview") -> str:
    sec = st.segmented_control("Section", SECTIONS, default=default, key=f"sec_{key}", label_visibility="collapsed")
    return sec or default


def render_state(client: str, s: State, share: bool) -> None:
    page_title(s.title, s.description)
    T = int(s.time_span)
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 3])
    at = c1.number_input("Metrics at day", 0, T - 1, T - 1, step=30, key=f"at_{s.id}")
    r, k, v = run(s, int(at))
    if not share:
        if c2.button("Live", key=f"lv_{s.id}", type="primary", help="All inputs on the left, results update as you type"):
            go_to(client=client, state=s.id, live=1)
        if c4.button("Tables", key=f"e_{s.id}"):
            go_to(client=client, state=s.id, edit=1)
        if c3.button("Share link", key=f"sh_{s.id}"):
            st.session_state[f"show_share_{s.id}"] = True
        if st.session_state.get(f"show_share_{s.id}"):
            st.code(share_url(client, state=s.id), language=None)
    st.markdown(kpi_tiles(s, r, k, v), unsafe_allow_html=True)
    vs = validation_summary(s)
    if vs:
        st.markdown(f'<div class="c-muted" style="margin:-10px 0 14px">{esc(vs)}</div>', unsafe_allow_html=True)

    sec = section_nav(s.id)
    if sec == "Overview":
        subtitle(f"Key Metrics at Day {k.at_day:,}")
        unit, rr, cash, val = kpi_tables(k, v, s)
        a, b, c = st.columns(3, gap="medium")
        card("Unit Economics", unit, a)
        card("Last 30 Days", rr, b)
        card("Cash and Customers", cash, c)
        a, b = st.columns([1, 1], gap="medium")
        card("Valuation", val, a)
        ch = [[esc(ch), money(cv) if np.isfinite(cv) else "–"] for ch, cv in k.cac_by_channel.items()]
        with b:
            card("Channel CAC (direct channel costs only)", table(["Channel", "CAC"], ch, num_cols={1}))
            if len(s.offers) > 1:
                card("Customers by Offer", offers_at_day_html(s, r, int(k.at_day)))
        a, b = st.columns(2, gap="medium")
        with a:
            dcf_chart([(s.title, r)], None, key=f"dcf_{s.id}")
            monthly_cash_chart(r, key=f"mo_{s.id}")
        with b:
            cash_chart([(s.title, r)], key=f"cash_{s.id}")
            G.by_channel_chart(r, f"ovch_{s.id}", "Monthly")
        card(f"Targets (payback in {num(s.target_payback_months)} months, LTV : CAC {num(s.target_ltv_cac)})",
             targets_html(s))
        card("Marketing Events", events_html(s))
    elif sec == "Graphs":
        view, mode = G.picker(s.id)
        G.render_view([(s.title, r)], view, mode, f"g_{s.id}", offers=[o.name for o in s.offers])
    elif sec == "Inputs":
        render_inputs(client, s, r, share, s.id)
    else:
        render_statement(s, r, share, s.id)


def share_url(client: str, **kw) -> str:
    q = href(client=client, share=1, **kw)
    try:
        return st.context.url.split("?")[0] + q
    except Exception:
        return q


# ── State editor ──────────────────────────────────────────────────────

def _ver(sid):
    return st.session_state.get(f"ver_{sid}", 0)


def _set_draft(sid, s: State, bump=True):
    st.session_state[f"draft_{sid}"] = state_to_dict(s)
    if bump:
        st.session_state[f"ver_{sid}"] = _ver(sid) + 1
        st.rerun()


def mix_to_text(mix: dict) -> str:
    if not mix:
        return ""
    tot = sum(float(v) for v in mix.values()) or 1.0
    return "; ".join(f"{k} {float(v) / tot * 100:g}" for k, v in mix.items())


def text_to_mix(text, offer_names: list) -> dict:
    """'Starter 40; Team 40; Pro 15' -> {offer: share}. Unknown offer names are dropped."""
    import re
    out = {}
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return out
    for part in str(text).split(";"):
        m = re.match(r"\s*(.+?)\s*[:=]?\s*([0-9]*\.?[0-9]+)\s*%?\s*$", part)
        if m and m.group(1) in offer_names and float(m.group(2)) > 0:
            out[m.group(1)] = out.get(m.group(1), 0.0) + float(m.group(2))
    return out


def _f(x, d=0.0):
    try:
        return d if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)
    except Exception:
        return d


def _i(x, d=0):
    return int(round(_f(x, d)))


def render_editor(client: str, sid: str) -> None:
    saved = load_state(client, sid)
    if saved is None:
        st.error("State not found.")
        return
    if f"draft_{sid}" not in st.session_state:
        st.session_state[f"draft_{sid}"] = state_to_dict(saved)
    base = state_from_dict(st.session_state[f"draft_{sid}"])
    k = f"{sid}_{_ver(sid)}"

    page_title("Edit State", "")
    st.markdown(f'<div class="c-statetitle">{link(base.title, client=client, state=sid)}</div>', unsafe_allow_html=True)

    left, right = st.columns([3, 1.25], gap="large")
    with left:
        st.markdown("#### Sim Parameters")
        a, b = st.columns(2)
        title = a.text_input("Title", base.title, key=f"t_{k}")
        desc = b.text_input("Description", base.description, key=f"d_{k}")
        c = st.columns(5)
        time_span = c[0].number_input("Time Span", 30, 20000, int(base.time_span), step=100, key=f"ts_{k}")
        proj = c[1].number_input("Projection Period", 1, 20000, int(base.projection_period), step=100, key=f"pp_{k}")
        disc = c[2].number_input("Discount Rate", 0.0, 1.0, float(base.discount_rate), 0.01, "%.4f", key=f"dr_{k}")
        tax = c[3].number_input("Tax Rate", 0.0, 1.0, float(base.tax_rate), 0.01, "%.4f", key=f"tr_{k}")
        shares = c[4].number_input("Shares", 1, 10 ** 10, int(base.shares), 1000, key=f"sh_{k}")
        c = st.columns(5)
        growth = c[0].number_input("Perpetual Growth Rate", 0.0, 0.5, float(base.perpetual_growth_rate), 0.005, "%.4f", key=f"g_{k}")
        mult = c[1].number_input("EBITDA Multiple", 0.0, 100.0, float(base.ebitda_multiple), 0.5, key=f"m_{k}")
        eproj = c[2].number_input("EBITDA Projection Period", 1, 20000, int(base.ebitda_projection_period), 100, key=f"ep_{k}")
        carry = c[3].checkbox("Loss Carryforward", base.loss_carryforward, key=f"lc_{k}")
        c = st.columns(5)
        ltv_years = c[0].number_input("LTV Horizon (Years)", 0.5, 20.0, float(base.ltv_years), 0.5, key=f"ly_{k}",
                                      help="LTV counts this many years of a customer, discounted at the discount rate, "
                                           "net of delivery costs, refunds and the transaction fee.")
        cac_lag = c[1].number_input("CAC Spend Lag (Days)", -1, 365, int(base.cac_lag_days), 1, key=f"cl_{k}",
                                    help="Spend is matched to customers won this many days later. "
                                         "-1 = automatic (sales-weighted time to market + sales cycle).")

        st.markdown("#### Starting State")
        c = st.columns(5)
        cash0 = c[0].number_input("Starting Cash", value=float(base.starting_cash), step=1000.0, key=f"sc_{k}")
        assets = c[1].number_input("Assets", value=float(base.assets), step=1000.0, key=f"as_{k}")
        liab = c[2].number_input("Liabilities", value=float(base.liabilities), step=1000.0, key=f"li_{k}")
        debt = c[3].number_input("Debt", value=float(base.debt), step=1000.0, key=f"db_{k}")
        irate = c[4].number_input("Interest Rate", 0.0, 1.0, float(base.interest_rate), 0.005, "%.4f", key=f"ir_{k}")
        c = st.columns(5)
        upfront = c[0].number_input("Upfront Investment", value=float(base.upfront_investment), step=1000.0, key=f"up_{k}")
        book0 = existing_book(base)
        ex_total0 = float(sum(book0.values()))
        ex_total = c[1].number_input("Existing Customers", 0.0, value=ex_total0, step=1.0, key=f"ec_{k}",
                                     help="Total across offers. Changing it scales every offer in proportion; "
                                          "or set each offer in the Offer Segments table.")
        ex_note = c[2].empty()
        tam = c[3].number_input("Total Addressable Market", 0.0, value=float(base.total_addressable_market), step=1000.0,
                                key=f"tam_{k}", help="0 = no cap")
        tfee = c[4].number_input("Transaction Fee", 0.0, 1.0, float(base.transaction_fee), 0.001, "%.4f", key=f"tf_{k}")

        st.markdown("#### Offer Segments")
        st.caption("Contract offers use price, collection, refunds, contract length, churn and renewals. "
                   "Schedule offers use a list of payments after the sale (edit them below the table). "
                   "Rates are fractions: 0.15 = 15%.")
        of_cols = ["Offer", "Billing", "Existing Customers", "Price", "Realization Rate", "Cost To Sell", "Cost To Fulfil", "Time To Collect",
                   "Contract Length", "Refund Period", "Refund Rate", "Churn Rate", "Renewal Price",
                   "Renewal Time To Collect", "Renewal Cost To Sell", "Renewal Cost To Fulfil", "Renewal Rate Of Renewals"]
        of_df = pd.DataFrame([[o.name, o.billing, book0.get(o.name, 0.0), o.price, o.realization_rate, o.cost_to_sell, o.cost_to_fulfill,
                               o.time_to_collect, o.contract_length, o.refund_period, o.refund_rate, o.churn_rate,
                               o.renewal_price, o.renewal_time_to_collect, o.renewal_cost_to_sell,
                               o.renewal_cost_to_fulfill, o.renewal_rate_of_renewals] for o in base.offers],
                             columns=of_cols)
        rate_cfg = lambda: st.column_config.NumberColumn(format="%.4f", min_value=0.0, max_value=1.0)
        int_cfg = lambda: st.column_config.NumberColumn(format="%d", min_value=0, step=1)
        of_ed = st.data_editor(of_df, num_rows="dynamic", hide_index=True, key=f"of_{k}", column_config={
            "Billing": st.column_config.SelectboxColumn(options=["contract", "schedule"], required=True),
            "Existing Customers": st.column_config.NumberColumn(format="%.1f", min_value=0.0,
                                                                help="Customers on this offer on day 0"),
            "Price": st.column_config.NumberColumn(format="%.2f"),
            "Renewal Price": st.column_config.NumberColumn(format="%.2f"),
            **{c_: rate_cfg() for c_ in ("Realization Rate", "Cost To Sell", "Cost To Fulfil", "Refund Rate",
                                         "Churn Rate", "Renewal Cost To Sell", "Renewal Cost To Fulfil",
                                         "Renewal Rate Of Renewals")},
            **{c_: int_cfg() for c_ in ("Time To Collect", "Contract Length", "Refund Period", "Renewal Time To Collect")},
        })
        offers, renames, book = [], {}, {}
        prev = {o.name: o for o in base.offers}
        for i, row in of_ed.iterrows():
            name = str(row["Offer"]).strip() if pd.notna(row["Offer"]) else ""
            if not name:
                continue
            if i < len(base.offers) and len(of_ed) == len(base.offers) and base.offers[i].name != name:
                renames[base.offers[i].name] = name
            old = prev.get(name) or (base.offers[i] if i < len(base.offers) else None)
            if _f(row["Existing Customers"]) > 0:
                book[name] = _f(row["Existing Customers"])
            offers.append(Offer(
                name=name, billing=str(row["Billing"] or "contract"), price=_f(row["Price"]),
                realization_rate=_f(row["Realization Rate"], 1.0), cost_to_sell=_f(row["Cost To Sell"]),
                cost_to_fulfill=_f(row["Cost To Fulfil"]), time_to_collect=_i(row["Time To Collect"]),
                contract_length=_i(row["Contract Length"], 365), refund_period=_i(row["Refund Period"]),
                refund_rate=_f(row["Refund Rate"]), churn_rate=_f(row["Churn Rate"], 1.0),
                renewal_price=_f(row["Renewal Price"]), renewal_time_to_collect=_i(row["Renewal Time To Collect"]),
                renewal_cost_to_sell=_f(row["Renewal Cost To Sell"]),
                renewal_cost_to_fulfill=_f(row["Renewal Cost To Fulfil"]),
                renewal_rate_of_renewals=_f(row["Renewal Rate Of Renewals"]),
                payments=list(old.payments) if old else [], generator=dict(old.generator) if old else {},
            ))
        tab_total = float(sum(book.values()))
        if abs(ex_total - ex_total0) > 1e-9:  # the total was changed: scale the per-offer split
            if tab_total > 0:
                book = {n_: v_ * ex_total / tab_total for n_, v_ in book.items()}
            elif offers and ex_total > 0:
                book = {offers[0].name: ex_total}
            split_txt = ", ".join(f"{n_} {v_:,.0f}" for n_, v_ in book.items())
            ex_note.caption(f"Scaled across offers: {split_txt}. Save to keep it.")
        else:
            ex_note.caption("Per offer: set in the Offer Segments table below." if tab_total == ex_total0 else
                            f"Table total is now {tab_total:,.0f}.")
        for j, o in enumerate(offers):
            if o.billing != "schedule":
                continue
            with st.expander(f"Payment schedule: {o.name}", expanded=not o.payments):
                gen = o.generator or {"kind": "custom"}
                kinds = ["subscription", "one_time", "installments", "custom"]
                kind = st.selectbox("Schedule type", kinds, kinds.index(gen.get("kind", "custom"))
                                    if gen.get("kind") in kinds else 3, key=f"sk_{k}_{j}")
                g = {"kind": kind}
                if kind == "subscription":
                    c = st.columns(4)
                    g["price"] = c[0].number_input("Price per payment", value=float(gen.get("price", o.price or 100.0)), key=f"sp_{k}_{j}")
                    g["every_days"] = c[1].number_input("Every (days)", 1, 3650, int(gen.get("every_days", 30)), key=f"se_{k}_{j}")
                    g["churn"] = c[2].number_input("Churn per period", 0.0, 1.0, float(gen.get("churn", 0.05)), 0.005, "%.5f", key=f"sc_{k}_{j}")
                    g["periods"] = c[3].number_input("Payments", 1, 600, int(gen.get("periods", 13)), key=f"sn_{k}_{j}")
                    o.payments = build_schedule(g)
                elif kind == "one_time":
                    c = st.columns(2)
                    g["price"] = c[0].number_input("Price", value=float(gen.get("price", o.price or 1000.0)), key=f"sp_{k}_{j}")
                    g["day"] = c[1].number_input("Paid on day after sale", 0, 3650, int(gen.get("day", 0)), key=f"sd_{k}_{j}")
                    o.payments = build_schedule(g)
                elif kind == "installments":
                    c = st.columns(3)
                    g["price"] = c[0].number_input("Total price", value=float(gen.get("price", o.price or 1000.0)), key=f"sp_{k}_{j}")
                    g["n"] = c[1].number_input("Installments", 1, 120, int(gen.get("n", 3)), key=f"si_{k}_{j}")
                    g["every_days"] = c[2].number_input("Every (days)", 1, 3650, int(gen.get("every_days", 30)), key=f"se_{k}_{j}")
                    o.payments = build_schedule(g)
                else:
                    pdf = pd.DataFrame(o.payments or [[0, o.price]], columns=["Day", "Amount"])
                    ed = st.data_editor(pdf, num_rows="dynamic", hide_index=True, key=f"pay_{k}_{j}")
                    o.payments = [[_i(x["Day"]), _f(x["Amount"])] for _, x in ed.iterrows() if pd.notna(x["Day"])]
                o.generator = g
                st.caption(f"Expected value: {offer_economics(o)['expected_value']:,.2f} over {len(o.payments)} payments")
        offer_names = [o.name for o in offers] or [""]

        st.markdown("#### Marketing Events")
        st.caption("One section per channel type, each with its own inputs. Every row runs between its start and end "
                   "day (both included); sales land after time to market plus sales cycle. Offer Mix (optional) splits "
                   "a row's sales across offers, e.g. Starter 40; Team 40; Pro 20. Cost To Sell empty = the offer's rate.")
        events = []
        shown_types = [t for t in CHANNEL_TYPES if t[0] != "team" or any(e.driver == "team" for e in base.events)]
        tcols = st.columns(len(shown_types))
        show = {}
        for tc, (key, label, *_rest) in zip(tcols, shown_types):
            n_rows = sum(1 for e in base.events if e.driver == key)
            show[key] = tc.checkbox(label, value=n_rows > 0, key=f"show_{key}_{k}")
        for key, label, default_channel, helptext, cols in CHANNEL_TYPES:
            evs = [e for e in base.events if e.driver == key]
            if key == "team" and not evs:
                continue
            if not show.get(key):
                for e in evs:  # hidden, not removed: rows stay in the model
                    e2 = copy.deepcopy(e)
                    e2.offer = renames.get(e2.offer, e2.offer)
                    e2.offer_mix = {renames.get(a_, a_): b_ for a_, b_ in (e2.offer_mix or {}).items()}
                    events.append(e2)
                if evs:
                    st.caption(f"{label}: {len(evs)} row{'s' if len(evs) != 1 else ''} hidden, still active in the model.")
                continue
            st.markdown(f"##### {label}")
            st.caption(helptext)
            spec_ = EV_HEAD + cols + EV_TAIL
            def _lab(lbl, kd):
                return lbl + (" (%)" if kd in ("pct", "override") else " ($)" if kd in ("money", "money_m") else "")
            # pandas needs the column types up front, otherwise an empty table gets no checkbox / text columns
            _dtype = {"text": "object", "offer": "object", "mix": "object", "channel": "object", "note": "object",
                      "bool": "bool"}
            def _to_ui(e, a_, kd):
                v = getattr(e, a_)
                if kd == "offer":
                    return renames.get(v, v)
                if kd == "mix":
                    return mix_to_text({renames.get(x, x): y for x, y in (v or {}).items()})
                if kd == "pct":
                    return v * 100.0
                if kd == "override":
                    return None if v < 0 else v * 100.0
                if kd in ("money_m", "num_m"):
                    return v * 30.0
                return v
            df = pd.DataFrame([[_to_ui(e, a_, kd) for _, a_, kd in spec_] for e in evs],
                              columns=[_lab(l_, kd) for l_, _, kd in spec_])
            if df.empty:
                df = df.astype({_lab(l_, kd): _dtype.get(kd, "float") for l_, _, kd in spec_})
            else:
                df = df.astype({_lab(l_, kd): "bool" for l_, _, kd in spec_ if kd == "bool"})
            cfg = {}
            for l_, a_, kd in spec_:
                L_ = _lab(l_, kd)
                if kd == "text":
                    cfg[L_] = st.column_config.TextColumn()
                elif kd == "offer":
                    cfg[L_] = st.column_config.SelectboxColumn(options=offer_names, required=True)
                elif kd == "mix":
                    cfg[L_] = st.column_config.TextColumn(help="Optional, e.g. Starter 40; Team 40; Pro 20. Empty = all to Offer.")
                elif kd == "bool":
                    cfg[L_] = st.column_config.CheckboxColumn(default=False,
                                                              help="Ticked = the rates come from measured data. "
                                                                   "Unticked = hypothesis.")
                elif kd == "note":
                    cfg[L_] = st.column_config.TextColumn(help="Where the numbers come from: test, period, sample size.")
                elif kd == "channel":
                    opts = list(TYPE_CHANNELS.get(key, [default_channel]))
                    opts += [e.channel for e in evs if e.channel and e.channel not in opts]  # keep existing labels
                    cfg[L_] = st.column_config.SelectboxColumn(options=opts, default=default_channel)
                elif kd == "int":
                    cfg[L_] = int_cfg()
                elif kd in ("pct", "override"):
                    cfg[L_] = st.column_config.NumberColumn(format="%.2f%%", min_value=0.0, max_value=100.0,
                                                            help="Empty = use the offer's cost to sell" if kd == "override" else None)
                elif kd in ("money", "money_m"):
                    cfg[L_] = st.column_config.NumberColumn(format="$%.2f", min_value=0.0)
                else:
                    cfg[L_] = st.column_config.NumberColumn(min_value=0.0)
            ed = st.data_editor(df, num_rows="dynamic", hide_index=True, key=f"ev_{key}_{k}", column_config=cfg)
            for _, x in ed.iterrows():
                t_ = x[_lab("Title", "text")]
                if t_ is None or (isinstance(t_, float) and np.isnan(t_)) or not str(t_).strip():
                    continue
                e = MarketingEvent(title=str(t_), offer="", driver=key, channel=default_channel)
                if key == "team":
                    e.ctr = 1.0
                for l_, a_, kd in spec_:
                    v = x[_lab(l_, kd)]
                    missing = v is None or (isinstance(v, float) and np.isnan(v))
                    if kd == "title":
                        continue
                    if kd == "offer":
                        e.offer = "" if missing else str(v)
                    elif kd == "mix":
                        e.offer_mix = text_to_mix(v, offer_names)
                    elif kd == "channel":
                        e.channel = default_channel if missing else str(v)
                    elif kd == "text":
                        continue
                    elif kd == "bool":
                        e.validated = bool(v) if not missing else False
                    elif kd == "note":
                        e.validation_note = "" if missing else str(v)
                    elif kd == "int":
                        setattr(e, a_, _i(v, (int(time_span) - 1) if a_ == "end_day" else 0))
                    elif kd == "pct":
                        setattr(e, a_, _f(v) / 100.0)
                    elif kd == "override":
                        e.cost_to_sell_override = -1.0 if missing else _f(v) / 100.0
                    elif kd in ("money_m", "num_m"):
                        setattr(e, a_, _f(v) / 30.0)
                    else:
                        setattr(e, a_, _f(v))
                events.append(e)

        st.markdown("#### Fixed Expenses")
        st.caption("Amounts are per day. A monthly cost divided by 30 gives the daily amount. Tick Sales & Marketing "
                   "for growth, marketing and sales costs so they count toward CAC.")
        fx_df = pd.DataFrame([[x.title, x.description, x.start_day, x.end_day, x.amount_per_day,
                               x.per_100_customers_per_day, x.employee, x.sales_marketing] for x in base.expenses],
                             columns=["Title", "Description", "Start Day", "End Day", "Amount Per Day",
                                      "Per 100 Customers Per Day", "Employee", "Sales & Marketing"])
        fx_ed = st.data_editor(fx_df, num_rows="dynamic", hide_index=True, key=f"fx_{k}", column_config={
            "Start Day": int_cfg(), "End Day": int_cfg(),
            "Amount Per Day": st.column_config.NumberColumn(format="%.2f"),
            "Per 100 Customers Per Day": st.column_config.NumberColumn(format="%.2f"),
            "Employee": st.column_config.CheckboxColumn(default=False),
            "Sales & Marketing": st.column_config.CheckboxColumn(
                default=False, help="Counts toward fully loaded CAC: growth, marketing and sales people and tools. "
                                    "Profit does not change."),
        })
        expenses = [FixedExpense(str(x["Title"]), str(x["Description"]) if pd.notna(x["Description"]) else "",
                                 _i(x["Start Day"]), _i(x["End Day"]), _f(x["Amount Per Day"]),
                                 _f(x["Per 100 Customers Per Day"]), bool(x["Employee"]) if pd.notna(x["Employee"]) else False,
                                 bool(x["Sales & Marketing"]) if pd.notna(x["Sales & Marketing"]) else False)
                    for _, x in fx_ed.iterrows() if pd.notna(x["Title"]) and str(x["Title"]).strip()]

        st.markdown("#### Upgrades")
        st.caption("Each month, this share of active customers on the first offer moves to the second offer. "
                   "They start the new offer at its renewal price, with no sales cost. 0.02 = 2% per month.")
        up_df = pd.DataFrame([[renames.get(u.from_offer, u.from_offer), renames.get(u.to_offer, u.to_offer),
                               u.monthly_rate, u.start_day, u.end_day, u.description] for u in base.upgrades],
                             columns=["From Offer", "To Offer", "Monthly Rate", "Start Day", "End Day", "Description"])
        up_ed = st.data_editor(up_df, num_rows="dynamic", hide_index=True, key=f"upg_{k}", column_config={
            "From Offer": st.column_config.SelectboxColumn(options=offer_names, required=True),
            "To Offer": st.column_config.SelectboxColumn(options=offer_names, required=True),
            "Monthly Rate": rate_cfg(), "Start Day": int_cfg(), "End Day": int_cfg(),
        })
        upgrades = [Upgrade(str(x["From Offer"]), str(x["To Offer"]), _f(x["Monthly Rate"]), _i(x["Start Day"]),
                            _i(x["End Day"], int(time_span) - 1),
                            str(x["Description"]) if pd.notna(x["Description"]) else "")
                    for _, x in up_ed.iterrows() if pd.notna(x["From Offer"]) and pd.notna(x["To Offer"])]

        st.markdown("#### Financing Events")
        st.caption("Cash that arrives on one day. Equity issues shares: give the pre-money valuation (shares follow) or "
                   "the shares issued. A loan accrues interest on the balance and is repaid in equal daily amounts "
                   "from the grace period to maturity. Grants are free money. Financing changes cash, debt and "
                   "shares, not the discounted cash flow (except loan interest).")
        fn_cols = ["Title", "Type", "Day", "Amount", "Interest Rate", "Maturity (Days)", "Grace (Days)", "Compounding",
                   "Pre-Money Valuation", "Shares Issued", "Purpose", "Terms"]
        fn_df = pd.DataFrame([[f.title, f.kind, f.day, f.amount, f.interest_rate, f.maturity_days, f.grace_days,
                               f.compounding, f.valuation, f.shares_issued, f.purpose, f.terms] for f in base.financing],
                             columns=fn_cols)
        if fn_df.empty:
            fn_df = fn_df.astype({"Title": "object", "Type": "object", "Day": "float", "Amount": "float",
                                  "Interest Rate": "float", "Maturity (Days)": "float", "Grace (Days)": "float",
                                  "Compounding": "bool", "Pre-Money Valuation": "float", "Shares Issued": "float",
                                  "Purpose": "object", "Terms": "object"})
        fn_ed = st.data_editor(fn_df, num_rows="dynamic", hide_index=True, key=f"fin_{k}", column_config={
            "Type": st.column_config.SelectboxColumn(options=FIN_KINDS, required=True, default="equity"),
            "Day": int_cfg(), "Maturity (Days)": int_cfg(), "Grace (Days)": int_cfg(),
            "Amount": st.column_config.NumberColumn(format="dollar", min_value=0.0),
            "Interest Rate": st.column_config.NumberColumn(format="%.4f", min_value=0.0, max_value=1.0,
                                                           help="Loans only. Annual, as a fraction: 0.06 = 6%."),
            "Compounding": st.column_config.CheckboxColumn(default=False, help="Loans only."),
            "Pre-Money Valuation": st.column_config.NumberColumn(format="dollar", min_value=0.0, help="Equity only."),
            "Shares Issued": st.column_config.NumberColumn(format="%.0f", min_value=0.0,
                                                           help="Equity only. 0 = derived from the valuation."),
            "Purpose": st.column_config.TextColumn(help="Grants only."),
        })
        financing = []
        for _, x in fn_ed.iterrows():
            if not (pd.notna(x["Title"]) and str(x["Title"]).strip()):
                continue
            financing.append(FinancingEvent(
                title=str(x["Title"]), kind=str(x["Type"]) if pd.notna(x["Type"]) else "equity", day=_i(x["Day"]),
                amount=_f(x["Amount"]), terms=str(x["Terms"]) if pd.notna(x["Terms"]) else "",
                interest_rate=_f(x["Interest Rate"]), maturity_days=_i(x["Maturity (Days)"], 1095),
                grace_days=_i(x["Grace (Days)"]),
                compounding=bool(x["Compounding"]) if pd.notna(x["Compounding"]) else False,
                valuation=_f(x["Pre-Money Valuation"]), shares_issued=_f(x["Shares Issued"]),
                purpose=str(x["Purpose"]) if pd.notna(x["Purpose"]) else ""))

    cur = state_from_dict(state_to_dict(base))
    cur.title, cur.description = title, desc
    cur.time_span, cur.projection_period, cur.discount_rate, cur.tax_rate = int(time_span), int(proj), disc, tax
    cur.shares, cur.perpetual_growth_rate, cur.ebitda_multiple = int(shares), growth, mult
    cur.ltv_years, cur.cac_lag_days = float(ltv_years), int(cac_lag)
    cur.ebitda_projection_period, cur.loss_carryforward = int(eproj), bool(carry)
    cur.starting_cash, cur.assets, cur.liabilities, cur.debt, cur.interest_rate = cash0, assets, liab, debt, irate
    cur.upfront_investment = upfront
    cur.existing_by_offer = book
    cur.existing_customers = float(sum(book.values()))
    cur.existing_customers_offer = max(book, key=book.get) if book else ""
    cur.total_addressable_market, cur.transaction_fee = tam, tfee
    cur.offers, cur.events, cur.expenses, cur.upgrades, cur.financing = offers, events, expenses, upgrades, financing

    with right:
        r, kp, v = run(cur)
        st.markdown("#### Result")
        st.markdown(table([], [
            ["Total DCF after tax", money(v.dcf_cumulative)],
            ["Equity value (DCF)", money(v.equity_value_dcf)],
            ["Share price (DCF)", money(v.share_price_dcf, 4)],
            ["CAC", money(kp.cac_blended)],
            ["LTV : CAC", f"{kp.ltv_cac_ratio:,.2f}" if np.isfinite(kp.ltv_cac_ratio) else "–"],
            ["Cash needed", money(kp.cash_needed)],
            ["Time to profitability", days(kp.time_to_profitability_days)],
        ], kv=True), unsafe_allow_html=True)
        fig = go.Figure(go.Scatter(x=r.days, y=r.cum_dcf, mode="lines", line=dict(color=NAVY, width=2), name=cur.title))
        chart(fig, "Total DCF After Tax", 260, money_axis=True, key=f"lcum_{k}")

        st.markdown("#### Intervention")
        st.caption("Split a row: it ends the day before the chosen day and a copy starts on that day. "
                   "Edit the copy to describe the change.")
        rows = [f"Event: {e.title} ({e.start_day}-{e.end_day})" for e in cur.events] + \
               [f"Expense: {x.title} ({x.start_day}-{x.end_day})" for x in cur.expenses]
        if rows:
            pick = st.selectbox("Row", range(len(rows)), format_func=lambda i: rows[i], key=f"sp_r_{k}")
            at = st.number_input("Change starts on day", 1, int(cur.time_span), 181, key=f"sp_d_{k}")
            if st.button("Split row", key=f"sp_go_{k}"):
                nxt = state_from_dict(state_to_dict(cur))
                try:
                    if pick < len(nxt.events):
                        nxt.events = split_row(nxt.events, pick, int(at))
                    else:
                        nxt.expenses = split_row(nxt.expenses, pick - len(nxt.events), int(at))
                    _set_draft(sid, nxt)
                except ValueError as err:
                    st.error(str(err))

        st.markdown("#### Save")
        b1, b2 = st.columns(2)
        if b1.button("Save", type="primary", key=f"save_{k}"):
            save_state(client, cur)
            _set_draft(sid, cur, bump=False)
            st.success("Saved.")
        if b2.button("Discard", key=f"disc_{k}"):
            st.session_state.pop(f"draft_{sid}", None)
            st.session_state[f"ver_{sid}"] = _ver(sid) + 1
            st.rerun()
        if st.button("View report", key=f"view_{k}"):
            go_to(client=client, state=sid)
        if st.button("Live view", key=f"live_{k}"):
            go_to(client=client, state=sid, live=1)

        st.markdown("#### Clone as Intervention State")
        nt = st.text_input("New state title", cur.title.replace("Before", "After"), key=f"cl_t_{k}")
        mk = st.checkbox("Create a comparison of the two", True, key=f"cl_c_{k}")
        if st.button("Clone", key=f"cl_go_{k}"):
            save_state(client, cur)
            c_ = clone_state(cur, nt)
            save_state(client, c_)
            if mk:
                save_comparison(client, Comparison(title=f"{cur.title} vs {nt}", state_ids=[cur.id, c_.id]))
            go_to(client=client, state=c_.id, edit=1)

        with st.expander("Delete state"):
            if st.button("Delete this state", key=f"del_{k}"):
                delete_state(client, sid)
                st.session_state.pop(f"draft_{sid}", None)
                go_to(client=client)


# ── Comparison ────────────────────────────────────────────────────────

LOWER_IS_BETTER = {"CAC (fully loaded, 12 months)", "CAC ratio", "CAC payback (months)", "Cash needed",
                   "Time to profitability (days)", "Time to self-fund (days)"}
NEUTRAL = {"Total marketing spend", "Total tax"}  # more is neither good nor bad by itself

METRIC_ROWS = [
    ("Total DCF after tax", lambda s, r, k, v: v.dcf_cumulative, money),
    ("Enterprise value (DCF)", lambda s, r, k, v: v.enterprise_value_dcf, money),
    ("Equity value (DCF)", lambda s, r, k, v: v.equity_value_dcf, money),
    ("Share price (DCF)", lambda s, r, k, v: v.share_price_dcf, lambda x: money(x, 4)),
    ("Enterprise value (EBITDA)", lambda s, r, k, v: v.enterprise_value_ebitda, money),
    ("CAC (fully loaded, 12 months)", lambda s, r, k, v: k.cac_blended, money),
    ("CAC ratio", lambda s, r, k, v: k.cac_ratio, lambda x: f"{x:,.2f}" if np.isfinite(x) else "–"),
    ("CAC payback (months)", lambda s, r, k, v: k.payback_months, lambda x: f"{x:,.1f}" if np.isfinite(x) else "–"),
    ("Expected value per sale", lambda s, r, k, v: k.expected_value, money),
    ("LTV (horizon, discounted)", lambda s, r, k, v: k.ltv, money),
    ("LTV : CAC", lambda s, r, k, v: k.ltv_cac_ratio, lambda x: f"{x:,.2f}" if np.isfinite(x) else "–"),
    ("Cash needed", lambda s, r, k, v: k.cash_needed, money),
    ("Lowest cash balance", lambda s, r, k, v: k.min_cash, money),
    ("Time to profitability (days)", lambda s, r, k, v: k.time_to_profitability_days, lambda x: days(x)),
    ("Time to self-fund (days)", lambda s, r, k, v: k.time_to_self_fund_days, lambda x: days(x)),
    ("Total customers", lambda s, r, k, v: k.total_customers, lambda x: num(round(x, 1))),
    ("Active customers (end)", lambda s, r, k, v: k.active_customers, lambda x: num(round(x, 1))),
    ("Total cash collected", lambda s, r, k, v: float(r.cash_collected_total.sum()), money),
    ("Total marketing spend", lambda s, r, k, v: float(r.cost_marketing.sum()), money),
    ("Total tax", lambda s, r, k, v: float(r.tax.sum()), money),
]


def render_comparison(client: str, comp: Comparison, share: bool) -> None:
    states = [s for s in (load_state(client, i) for i in comp.state_ids) if s]
    if not states:
        st.warning("This comparison has no states.")
        return
    outs = [run(s) for s in states]
    short = short_names([s.title for s in states])
    named = [(nm, o[0]) for nm, o in zip(short, outs)]
    page_title(comp.title, comp.description)
    day = int(comp.compare_day)

    if not share:
        with st.expander("Comparison settings"):
            c = st.columns(3)
            maxd = max(len(o[0].days) for o in outs) - 1
            nd = c[0].number_input("Compare at day", 0, maxd, min(day, maxd), 10, key=f"cd_{comp.id}")
            lab = c[1].text_input("Intervention (for the message)", comp.intervention_label, key=f"il_{comp.id}")
            tgt = c[2].text_input("Target segment", comp.target_label, key=f"tl_{comp.id}")
            ttl = st.text_input("Title", comp.title, key=f"ct_{comp.id}")
            dsc = st.text_area("Description", comp.description, key=f"cds_{comp.id}")
            opts = {s.id: s.title for s in list_states(client)}
            ch = st.multiselect("States (the first is the baseline)", list(opts),
                                [i for i in comp.state_ids if i in opts], format_func=lambda i: opts[i], key=f"cs_{comp.id}")
            b = st.columns([1, 1, 4])
            if b[0].button("Save", type="primary", key=f"svc_{comp.id}"):
                comp.compare_day, comp.intervention_label, comp.target_label = int(nd), lab, tgt
                comp.title, comp.description, comp.state_ids = ttl, dsc, ch
                save_comparison(client, comp)
                st.rerun()
            if b[1].button("Delete", key=f"dlc_{comp.id}"):
                delete_comparison(client, comp.id)
                go_to(client=client)
            day = int(nd)

    msg = ""
    if len(named) >= 2:
        base_name, base = named[0]
        heads = []
        for name, r in named[1:]:
            d = min(day, len(r.days) - 1, len(base.days) - 1)
            diff = float(r.cum_dcf[d] - base.cum_dcf[d])
            b0 = float(base.cum_dcf[d])
            cls = "pos" if diff > 0 else ("neg" if diff < 0 else "")
            pill = (f'<span class="c-pill {cls}">{"+" if diff > 0 else ""}{diff / abs(b0) * 100:,.1f}%</span>'
                    if abs(b0) > 1 else "")
            heads.append(f'<div class="c-head"><div class="lbl"><b>{esc(name)}</b> vs {esc(base_name)}</div>'
                         f'<div class="val {cls}">{"+" if diff > 0 else ""}{money_short(diff)}{pill}</div>'
                         f'<div class="sub">Total discounted cash flow after tax at day {d:,}</div></div>')
        st.markdown('<div class="c-heads">' + "".join(heads) + "</div>", unsafe_allow_html=True)
        if not share:
            r1 = named[1][1]
            d = min(day, len(r1.days) - 1, len(base.days) - 1)
            diff = float(r1.cum_dcf[d] - base.cum_dcf[d])
            using = f" using {comp.intervention_label}" if comp.intervention_label else ""
            msg = (f"We specialize in helping {comp.target_label or '[target segment]'}. Here's a model showing a "
                   f"{money_short(diff)} discounted future cash flow benefit after {d:,} days{using}. "
                   f"Here's a link to the model: {share_url(client, comparison=comp.id)}")

    # One page, in this order: the states side by side, key metrics, then every graph.
    subtitle("States")
    cols = st.columns(len(states), gap="medium")
    for col, s, nm, (r, k, v) in zip(cols, states, short, outs):
        with col:
            st.markdown(f'<div class="c-statetitle">{esc(s.title) if share else link(s.title, client=client, state=s.id)}</div>',
                        unsafe_allow_html=True)
            vs = validation_summary(s)
            if vs:
                st.markdown(f'<div class="c-muted" style="margin:-8px 0 10px">{esc(vs)}</div>', unsafe_allow_html=True)
            card("Sim Parameters", sim_parameters_html(s, client, share))
            card("Starting State", starting_state_html(s))
            card("Offer Segments", offers_html(s, compact=True))
            payment_chart(s, key=f"cpc_{comp.id}_{s.id}", height=280)
            card("Marketing Events", events_html(s))
            card("Fixed Expenses", expenses_html(s))
            if s.upgrades:
                card("Upgrades", upgrades_html(s))
            if s.financing:
                card("Financing Events", financing_html(s))

    subtitle("Key Metrics")
    heads = ["Metric"] + short + (
        ["Change"] if len(states) == 2 else [f"\u0394 {nm}" for nm in short[1:]])
    rows = []
    for label, fn, fmt in METRIC_ROWS:
        vals = [fn(s, r, k, v) for s, (r, k, v) in zip(states, outs)]
        deltas = []
        for x in vals[1:]:
            ok = np.isfinite(x) and np.isfinite(vals[0]) and "days" not in label
            deltas.append(signed(x - vals[0], fmt if fmt in (money,) else (lambda z: num(round(z, 2 if abs(z) < 100 else 0))),
                                 lower_is_better=None if label in NEUTRAL else label in LOWER_IS_BETTER) if ok else "\u2013")
        rows.append([esc(label)] + [fmt(x) for x in vals] + deltas)
    card("", table(heads, rows, num_cols=set(range(1, len(heads)))))
    a, b = st.columns(2, gap="medium")
    with a:
        card(f"Targets: {short[0]} (payback in {num(states[0].target_payback_months)} months, "
             f"LTV : CAC {num(states[0].target_ltv_cac)})", targets_html(states[0]))
    with b:
        if len(states) > 1:
            card(f"Targets: {short[1]} (payback in {num(states[1].target_payback_months)} months, "
                 f"LTV : CAC {num(states[1].target_ltv_cac)})", targets_html(states[1]))

    subtitle("Graphs")
    c1, c2 = st.columns([3, 1.2])
    c1.markdown('<div class="c-muted" style="margin-top:6px">Every series, each as values for all states, then the '
                'absolute and percent difference against the first state. Click a name to jump to it.</div>',
                unsafe_allow_html=True)
    mode = c2.segmented_control("Show as", G.MODES, default="Daily", key=f"cgm_{comp.id}",
                                label_visibility="collapsed") or "Daily"
    left, right = st.columns([1, 4.2], gap="medium")
    with left:
        st.markdown(G.shortcuts_html(named, sticky=True), unsafe_allow_html=True)
    with right:
        G.render_all(named, mode, f"cg_{comp.id}", compare_day=day)
    if msg:
        with st.expander("Message template"):
            st.text_area("Message", msg, height=100, key=f"msg_{comp.id}", label_visibility="collapsed")


# ── Client home ───────────────────────────────────────────────────────

def render_home(client: str) -> None:
    meta = load_client_meta(client)
    notes = meta.notes if meta and getattr(meta, "notes", "") else ""
    if st.session_state.get("_scope"):
        notes = ""  # internal research notes stay with the admin view
    page_title(meta.name if meta else client, notes)
    comps, states = list_comparisons(client), list_states(client)

    rows = [[link(c.title, client=client, comparison=c.id), len(c.state_ids), f"{c.compare_day:,}", esc(c.created)]
            for c in comps]
    card("Comparisons", table(["Title", "States", "Compare Day", "Created"], rows, num_cols={1, 2})
         if rows else '<div class="c-muted">No comparisons yet.</div>')

    rows = []
    for s in states:
        r, k, v = run(s)
        rows.append([link(s.title, client=client, state=s.id), len(s.offers), len(s.events), len(s.expenses),
                     money(v.dcf_cumulative), money(k.cac_blended),
                     f"{k.ltv_cac_ratio:,.2f}" if np.isfinite(k.ltv_cac_ratio) else "–", money(k.cash_needed),
                     days(k.time_to_profitability_days), link("Live", client=client, state=s.id, live=1)])
    card("States", table(["Title", "Offers", "Events", "Expenses", "Total DCF After Tax", "CAC", "LTV : CAC",
                          "Cash Needed", "Time To Profitability", ""], rows, num_cols={1, 2, 3, 4, 5, 6, 7})
         if rows else '<div class="c-muted">No states yet.</div>')



# ── Sidebar ───────────────────────────────────────────────────────────

def sidebar(client: str | None) -> str | None:
    scope = st.session_state.get("_scope")
    if scope:
        return _guest_sidebar(scope)
    clients = list_clients()
    slugs = [c for c, _ in clients]
    names = {c: m.name for c, m in clients}
    with st.sidebar.expander("New client", expanded=not slugs):
        cn = st.text_input("Name", key="new_cl_n")
        ci = st.text_input("Industry", key="new_cl_i")
        if st.button("Create client", key="new_cl_go") and cn.strip():
            slug = re.sub(r"[^a-z0-9]+", "-", cn.strip().lower()).strip("-") or "client"
            create_client(slug, cn.strip(), ci.strip())
            go_to(client=slug)
    if not slugs:
        st.sidebar.info("No clients yet. Create one above.")
        return None
    idx = slugs.index(client) if client in slugs else 0
    pick = st.sidebar.selectbox("Client", slugs, idx, format_func=lambda s: names.get(s, s), key="mdl_client")
    if pick != client:
        go_to(client=pick)
    if st.sidebar.button("Client home", key="nav_home"):
        go_to(client=pick)
    comps, states = list_comparisons(pick), list_states(pick)
    if comps:
        st.sidebar.caption("Comparisons")
        for c in comps:
            if st.sidebar.button(c.title, key=f"nc_{c.id}"):
                go_to(client=pick, comparison=c.id)
    if states:
        st.sidebar.caption("States")
        for s in states:
            if st.sidebar.button(s.title, key=f"ns_{s.id}"):
                go_to(client=pick, state=s.id)
    st.sidebar.write("")
    with st.sidebar.expander("New state"):
        t = st.text_input("Title", "New State", key="new_s_t")
        src = st.selectbox("Start from", ["Blank"] + [s.id for s in states],
                           format_func=lambda i: i if i == "Blank" else next(x.title for x in states if x.id == i),
                           key="new_s_src")
        if st.button("Create", key="new_s_go"):
            if src == "Blank":
                s = State(title=t, offers=[Offer("Main Offer", price=5000.0, realization_rate=1.0, contract_length=365,
                                                 churn_rate=0.5, renewal_price=5000.0, renewal_rate_of_renewals=0.5)],
                          events=[MarketingEvent("Outbound Prospecting", "Main Offer", "Outbound Prospecting", "team",
                                                 0, 730, ctr=0.3, lead_to_view=0.2, sale_to_lead=0.15,
                                                 sales_cycle_days=14, headcount=1, salary_per_month=4000,
                                                 contacts_per_head_per_month=1500)],
                          expenses=[FixedExpense("Operations", "", 0, 2999, 250.0)])
            else:
                s = clone_state(next(x for x in states if x.id == src), t)
            save_state(pick, s)
            go_to(client=pick, state=s.id, live=1)
    with st.sidebar.expander("New comparison"):
        t = st.text_input("Title", "New Comparison", key="new_c_t")
        opts = {s.id: s.title for s in states}
        ch = st.multiselect("States (the first is the baseline)", list(opts), format_func=lambda i: opts[i], key="new_c_s")
        if st.button("Create", key="new_c_go") and ch:
            c = Comparison(title=t, state_ids=ch)
            save_comparison(pick, c)
            go_to(client=pick, comparison=c.id)
    with st.sidebar.expander("Examples"):
        if st.button("Load the Higher EdTech example", key="seed"):
            c = seed_example(pick)
            go_to(client=pick, comparison=c.id)
    with st.sidebar.expander("Delete client"):
        if st.button(f"Delete {names.get(pick, pick)}", key="del_client"):
            delete_client(pick)
            go_to()
    return pick


def targets_html(s: State) -> str:
    """Raw targets table: per channel, now vs the most it may cost; plus what one customer is worth."""
    ce = customer_economics(s)
    rows = []
    def cell(now, mx, fmt=money):
        if not (np.isfinite(now) and np.isfinite(mx)):
            return fmt(now) if np.isfinite(now) else "–", fmt(mx) if np.isfinite(mx) else "–"
        cls = "c-pos" if now <= mx else "c-neg"
        return f'<span class="{cls}">{fmt(now)}</span>', fmt(mx)
    ts = channel_targets(s)
    goal = s.goal_new_customers_per_month > 0
    funnel = []
    for t in ts:
        cpl_now, cpl_max = cell(t["cpl"], t["max_cpl"])
        cac_now, cac_max = cell(t["cac"], t["max_cac"])
        row = [esc(t["title"]), num(round(t["customers_month"], 2)), num(round(t["leads_month"], 1)),
               rate(t["lead_to_customer"]), cpl_now, cpl_max, cac_now, cac_max]
        if goal:
            g = f"{num(round(t['goal_leads_month']))}" if "goal_leads_month" in t else "–"
            c = money(t["goal_cost_month"], 0) if np.isfinite(t.get("goal_cost_month", float("inf"))) else "–"
            row += [g, c]
        rows.append(row)
        for lbl, nw, mx in t["units"]:
            n_, m_ = cell(nw, mx)
            funnel.append([esc(t["title"]), esc(lbl), n_, m_])
        if "contacts_per_customer" in t and np.isfinite(t["contacts_per_customer"]):
            funnel.append([esc(t["title"]), "Contacts per customer", num(round(t["contacts_per_customer"])), "–"])
    heads = ["Channel", "Customers / mo", "Leads / mo", "Lead → customer", "Cost per lead", "Max cost per lead",
             "CAC", "Max CAC"]
    if goal:
        heads += [f"Leads / mo for {num(s.goal_new_customers_per_month)} customers", "Cost / mo at today's cost per lead"]
    tbl = table(heads, rows, num_cols=set(range(1, len(heads)))) if rows else '<div class="c-muted">No channels yet.</div>'
    if ts:
        rule = ts[0]["rule"]
        tbl += (f'<div class="c-muted" style="font-size:12.5px;margin:6px 0 14px">Max CAC is set by the '
                f'{"payback target" if rule == "payback" else "LTV : CAC target"}, whichever allows less. '
                f'Max cost per lead = (max CAC minus cost to sell) x lead to customer. Green = under the max, red = over.</div>')
    if funnel:
        tbl += table(["Channel", "Down the funnel", "Now", "Max"], funnel, num_cols={2, 3})
    if not ce:
        return tbl
    life = ce["lifetime_months"]
    kv = table([], [
        ["Price per month", money(ce["price_month"])],
        ["Gross profit per customer per month", money(ce["gross_profit_month"])],
        ["Average lifetime", f"{life:,.1f} months" if np.isfinite(life) else "No churn"],
        [f"LTV ({num(s.ltv_years)} years, discounted)", money(ce["ltv"])],
        ["Net cash per customer after 3 / 6 / 12 months",
         f"{money(ce['net_3m'])} / {money(ce['net_6m'])} / {money(ce['net_12m'])}"],
        ["Fixed costs per month", money(ce["fixed_month"])],
        ["Customers needed to cover fixed costs", num(round(ce["break_even_customers"], 1))
         if np.isfinite(ce["break_even_customers"]) else "–"],
    ], kv=True)
    return tbl + f'<div style="margin-top:14px;max-width:560px">{kv}</div>'


# ── Live mode: every input in the sidebar, results update as you type ──

LIVE_NEW_ROWS = {
    "spend": ("Paid ads", dict(channel="Paid Advertising", spend_per_day=100.0, cpm=25.0, ctr=0.01, lead_to_view=0.03,
                               sale_to_lead=0.10, sales_cycle_days=14)),
    "outbound": ("Outbound", dict(channel="Multichannel Outbound", contacts_per_day=200.0, cost_per_contact=0.30,
                                  tools_cost_per_month=500.0, contact_to_lead_rate=0.02, positive_reply_rate=0.30,
                                  meeting_rate=0.60, close_rate=0.20, sales_cycle_days=30)),
    "volume": ("Organic / SEO", dict(channel="SEO", views_per_day=100.0, lead_to_view=0.01, sale_to_lead=0.10,
                                     sales_cycle_days=14)),
    "viral": ("Viral / referral", dict(channel="Viral", invites_per_customer=0.5, invite_conversion=0.10,
                                       sales_cycle_days=14)),
}


def _lv(box, label, value, kind, key, help=None):
    """Number input in natural units. Returns the value in model units."""
    value = 0.0 if value is None else value
    if kind == "pct":
        return box.number_input(f"{label} (%)", value=float(value) * 100.0, step=0.1, format="%.2f", key=key,
                                help=help) / 100.0
    if kind in ("money_m", "num_m"):
        v = float(value) * 30.0
        lab = f"{label} ($)" if kind == "money_m" else label
        return box.number_input(lab, value=v, step=100.0 if v >= 100 else 10.0, format="%.0f", key=key,
                                help=help) / 30.0
    if kind == "int":
        return int(box.number_input(label, value=int(value), step=1, key=key, help=help))
    if kind == "money":
        v = float(value)
        return box.number_input(f"{label} ($)", value=v, step=100.0 if v >= 1000 else (1.0 if v >= 10 else 0.05),
                                format="%.0f" if v >= 1000 else "%.2f", key=key, help=help)
    v = float(value)
    return box.number_input(label, value=v, step=1.0 if v >= 10 else 0.1,
                            format="%.0f" if v >= 100 and v == round(v) else "%.2f", key=key, help=help)


def _canon(x):
    """State dict with floats rounded, so unit conversions in the inputs don't count as edits."""
    if isinstance(x, dict):
        return {k_: _canon(v_) for k_, v_ in x.items() if k_ not in ("created",)}
    if isinstance(x, list):
        return [_canon(v_) for v_ in x]
    if isinstance(x, float):
        return float(f"{x:.9g}")
    return x


def _pairs(box, items):
    """Lay inputs out two per row. items: list of (label, value, kind, key, setter)."""
    for j in range(0, len(items), 2):
        cols = box.columns(2)
        for c, (lab, val, kind, key, setter) in zip(cols, items[j:j + 2]):
            setter(_lv(c, lab, val, kind, key))


def render_live(client: str, sid: str) -> None:
    saved = load_state(client, sid)
    if saved is None:
        st.error("State not found.")
        return
    draft = st.session_state.get(f"draft_{sid}")
    cur = state_from_dict(draft) if draft else state_from_dict(state_to_dict(saved))
    k = f"lv_{sid}_{_ver(sid)}"
    sb = st.sidebar
    st.markdown('<style>section[data-testid="stSidebar"]{width:440px !important;min-width:440px !important}'
                '[data-testid="stSidebar"] [data-testid="stNumberInput"] label p{font-size:12px !important}'
                '[data-testid="stSidebar"] .stNumberInput{margin-bottom:-6px}</style>', unsafe_allow_html=True)

    sb.markdown(f'<div class="c-statetitle" style="margin-top:-8px">{esc(cur.title)}</div>', unsafe_allow_html=True)
    nav = sb.columns(3)
    if nav[0].button("Report", key=f"{k}_rep"):
        go_to(client=client, state=sid)
    if nav[1].button("Tables", key=f"{k}_tab", help="The full editor with every field as a table"):
        go_to(client=client, state=sid, edit=1)
    if nav[2].button("Client", key=f"{k}_home"):
        go_to(client=client)

    # Offers
    with sb.expander("1 · Offer", expanded=True):
        st.caption('Ask: What do you sell and at what price? Monthly or annual? Of 10 new customers, how many are gone after the first period, and how many leave per period after that? What does delivering it cost, as a share of the price? Sales commission? How fast do you get paid?')
        for j, o in enumerate(cur.offers):
            st.markdown(f"**{esc(o.name)}**")
            if o.billing == "schedule":
                st.caption(f"Payment schedule with {len(o.payments)} payments: edit it in Tables.")
                continue
            def _so(attr, o=o):
                return lambda v: setattr(o, attr, v)
            old_ful, old_sell_ren = o.cost_to_fulfill, o.renewal_cost_to_fulfill
            _pairs(st, [("Price", o.price, "money", f"{k}_op_{j}", _so("price")),
                        ("Contract length (days)", o.contract_length, "int", f"{k}_ol_{j}", _so("contract_length")),
                        ("Churn at first renewal", o.churn_rate, "pct", f"{k}_oc_{j}", _so("churn_rate")),
                        ("Renewal rate after that", o.renewal_rate_of_renewals, "pct", f"{k}_orr_{j}",
                         _so("renewal_rate_of_renewals")),
                        ("Renewal price", o.renewal_price, "money", f"{k}_orp_{j}", _so("renewal_price")),
                        ("Cost to fulfil", o.cost_to_fulfill, "pct", f"{k}_of_{j}", _so("cost_to_fulfill")),
                        ("Cost to sell", o.cost_to_sell, "pct", f"{k}_os_{j}", _so("cost_to_sell")),
                        ("Time to collect (days)", o.time_to_collect, "int", f"{k}_ot_{j}", _so("time_to_collect"))])
            if abs(old_sell_ren - old_ful) < 1e-12:  # same delivery cost on renewals: keep them together
                o.renewal_cost_to_fulfill = o.cost_to_fulfill

    # Starting state
    with sb.expander("2 · Today", expanded=False):
        st.caption('Ask: How many paying customers today, on which offer? Cash in the bank? Any debt? Payment provider fee?')
        book = existing_book(cur)
        def _set(attr):
            return lambda v: setattr(cur, attr, v)
        _pairs(st, [("Starting cash", cur.starting_cash, "money", f"{k}_cash", _set("starting_cash")),
                    ("Debt", cur.debt, "money", f"{k}_debt", _set("debt")),
                    ("Interest rate", cur.interest_rate, "pct", f"{k}_ir", _set("interest_rate")),
                    ("Payment fee", cur.transaction_fee, "pct", f"{k}_fee", _set("transaction_fee")),
                    ("Upfront investment", cur.upfront_investment, "money", f"{k}_up", _set("upfront_investment")),
                    ("Market size (0 = no cap)", cur.total_addressable_market, "num", f"{k}_tam",
                     _set("total_addressable_market"))])
        st.caption("Customers on day 0")
        newbook = {}
        items = []
        for o in cur.offers:
            items.append((o.name, book.get(o.name, 0.0), "num", f"{k}_ex_{o.name}",
                          (lambda name: (lambda v: newbook.__setitem__(name, v)))(o.name)))
        _pairs(st, items)
        cur.existing_by_offer = {n_: v_ for n_, v_ in newbook.items() if v_ > 0}
        cur.existing_customers = float(sum(cur.existing_by_offer.values()))
        cur.existing_customers_offer = max(cur.existing_by_offer, key=cur.existing_by_offer.get) if cur.existing_by_offer else ""

    # Fixed costs
    with sb.expander("3 · Fixed costs", expanded=False):
        st.caption('Ask: What does the business cost per month before marketing: team, rent, tools? Mark growth and sales people as sales & marketing. Does it grow with customers (support, account managers)?')
        remove = None
        for i, x in enumerate(cur.expenses):
            box = st.container(border=True)
            h = box.columns([5, 1])
            h[0].markdown(f"**{esc(x.title)}**", unsafe_allow_html=True)
            if h[1].button("✕", key=f"{k}_xrm_{i}"):
                remove = i
            def _sx(attr, x=x):
                return lambda v: setattr(x, attr, v)
            items = [("Per month", x.amount_per_day, "money_m", f"{k}_xa_{i}", _sx("amount_per_day")),
                     ("Per 100 customers per month", x.per_100_customers_per_day, "money_m", f"{k}_xp_{i}",
                      _sx("per_100_customers_per_day")),
                     ("Start day", x.start_day, "int", f"{k}_xs_{i}", _sx("start_day")),
                     ("End day", x.end_day, "int", f"{k}_xe_{i}", _sx("end_day"))]
            _pairs(box, items)
            x.sales_marketing = box.checkbox("Sales & marketing (counts toward CAC)", x.sales_marketing, key=f"{k}_xsm_{i}")
        if remove is not None:
            cur.expenses.pop(remove)
            _set_draft(sid, cur)
        a = st.columns([4, 2])
        nt = a[0].text_input("New cost", "", key=f"{k}_xnew", placeholder="e.g. Head of Sales",
                             label_visibility="collapsed")
        if a[1].button("Add", key=f"{k}_xadd") and nt.strip():
            cur.expenses.append(FixedExpense(nt.strip(), "", 0, int(cur.time_span) - 1, 5000 / 30, employee=True))
            _set_draft(sid, cur)

    # Marketing channels
    offer_names = [o.name for o in cur.offers]
    with sb.expander("4 · Channels", expanded=True):
        st.caption('Ask per channel: When does it start? Paid: budget per month, CPM (or cost per click), click-through rate, % of clicks that become a lead, % of leads that buy. Outbound: contacts per month, cost, % of contacts that become a lead, % of leads that buy. Days from first touch to closed deal. Measured or a guess? Tick Validated only if measured.')
        remove = None
        for i, e in enumerate(cur.events):
            spec = next((t for t in CHANNEL_TYPES if t[0] == e.driver), None)
            box = st.container(border=True)
            h = box.columns([5, 1])
            h[0].markdown(f"**{esc(e.title)}**  \n<span class='c-muted' style='font-size:12px'>{esc(e.channel)}"
                          f"{'' if e.validated else ' · hypothesis'}</span>", unsafe_allow_html=True)
            if h[1].button("✕", key=f"{k}_rm_{i}", help="Remove this channel"):
                remove = i
            def _se(attr, e=e):
                return lambda v: setattr(e, attr, v)
            items = [("Start day", e.start_day, "int", f"{k}_es_{i}", _se("start_day")),
                     ("End day", e.end_day, "int", f"{k}_ee_{i}", _se("end_day"))]
            for lab, attr, kind in (spec[4] if spec else []):
                items.append((lab, getattr(e, attr), kind, f"{k}_e_{attr}_{i}", _se(attr)))
            items += [("Time to market (days)", e.time_to_market, "int", f"{k}_ettm_{i}", _se("time_to_market")),
                      ("Sales cycle (days)", e.sales_cycle_days, "int", f"{k}_esc_{i}", _se("sales_cycle_days"))]
            _pairs(box, items)
            e.validated = box.checkbox("Validated (measured, not assumed)", e.validated, key=f"{k}_ev_{i}")
        if remove is not None:
            cur.events.pop(remove)
            _set_draft(sid, cur)
        st.caption("Add a channel")
        a = st.columns([3, 3, 2])
        kind = a[0].selectbox("Type", list(LIVE_NEW_ROWS), format_func=lambda x: LIVE_NEW_ROWS[x][0],
                              key=f"{k}_addk", label_visibility="collapsed")
        off = a[1].selectbox("Offer", offer_names or [""], key=f"{k}_addo", label_visibility="collapsed")
        if a[2].button("Add", key=f"{k}_add"):
            lab, defaults = LIVE_NEW_ROWS[kind]
            e = MarketingEvent(title=f"{lab} {sum(1 for x in cur.events if x.driver == kind) + 1}", offer=off,
                               driver=kind, start_day=0, end_day=int(cur.time_span) - 1, ctr=1.0)
            for a_, v_ in defaults.items():
                setattr(e, a_, v_)
            if kind == "spend":
                e.ctr = defaults["ctr"]
            cur.events.append(e)
            _set_draft(sid, cur)

    # Targets
    with sb.expander("5 · Targets", expanded=False):
        st.caption("Ask: How fast must a new customer pay back what it cost to win them? How many new customers a month do you want? These set the max cost per customer, lead, click and contact on the right.")
        _pairs(st, [("Payback target (months)", cur.target_payback_months, "num", f"{k}_tpm",
                     lambda v: setattr(cur, "target_payback_months", v)),
                    ("LTV : CAC target", cur.target_ltv_cac, "num", f"{k}_tlc", lambda v: setattr(cur, "target_ltv_cac", v)),
                    ("New customers wanted per month", cur.goal_new_customers_per_month, "num", f"{k}_tg",
                     lambda v: setattr(cur, "goal_new_customers_per_month", v))])

    # Upgrades
    if cur.upgrades:
        with sb.expander("Optional · Upgrades between offers", expanded=False):
            items = []
            for i, u in enumerate(cur.upgrades):
                items.append((f"{u.from_offer} → {u.to_offer} per month", u.monthly_rate, "pct", f"{k}_u_{i}",
                              (lambda u: (lambda v: setattr(u, "monthly_rate", v)))(u)))
            _pairs(st, items)

    # Financing
    with sb.expander("Optional · Financing", expanded=False):
        remove = None
        for i, f in enumerate(cur.financing):
            box = st.container(border=True)
            h = box.columns([5, 1])
            h[0].markdown(f"**{esc(f.title)}** <span class='c-muted' style='font-size:12px'>{f.kind}</span>",
                          unsafe_allow_html=True)
            if h[1].button("✕", key=f"{k}_frm_{i}"):
                remove = i
            def _sf(attr, f=f):
                return lambda v: setattr(f, attr, v)
            items = [("Amount", f.amount, "money", f"{k}_fa_{i}", _sf("amount")),
                     ("Day", f.day, "int", f"{k}_fd_{i}", _sf("day"))]
            if f.kind == "loan":
                items += [("Interest rate", f.interest_rate, "pct", f"{k}_fi_{i}", _sf("interest_rate")),
                          ("Repaid by day (after loan)", f.maturity_days, "int", f"{k}_fm_{i}", _sf("maturity_days")),
                          ("Grace (days)", f.grace_days, "int", f"{k}_fg_{i}", _sf("grace_days"))]
            elif f.kind == "equity":
                items += [("Pre-money valuation", f.valuation, "money", f"{k}_fv_{i}", _sf("valuation"))]
            _pairs(box, items)
        if remove is not None:
            cur.financing.pop(remove)
            _set_draft(sid, cur)
        a = st.columns([3, 2])
        fk = a[0].selectbox("Type", FIN_KINDS, key=f"{k}_fnew", label_visibility="collapsed")
        if a[1].button("Add", key=f"{k}_fadd"):
            cur.financing.append(FinancingEvent(f"{fk.title()} {len(cur.financing) + 1}", fk, 30, 250_000.0,
                                                interest_rate=0.07 if fk == "loan" else 0.0,
                                                valuation=5_000_000.0 if fk == "equity" else 0.0))
            _set_draft(sid, cur)

    # Valuation
    with sb.expander("Optional · Valuation settings", expanded=False):
        def _set(attr):
            return lambda v: setattr(cur, attr, v)
        _pairs(st, [("Days simulated", cur.time_span, "int", f"{k}_ts", _set("time_span")),
                    ("Valued up to day", cur.projection_period, "int", f"{k}_pp", _set("projection_period")),
                    ("Discount rate", cur.discount_rate, "pct", f"{k}_dr", _set("discount_rate")),
                    ("Tax rate", cur.tax_rate, "pct", f"{k}_tr", _set("tax_rate")),
                    ("Perpetual growth", cur.perpetual_growth_rate, "pct", f"{k}_g", _set("perpetual_growth_rate")),
                    ("EBITDA multiple", cur.ebitda_multiple, "num", f"{k}_m", _set("ebitda_multiple")),
                    ("Shares", cur.shares, "int", f"{k}_sh", _set("shares")),
                    ("LTV horizon (years)", cur.ltv_years, "num", f"{k}_ly", _set("ltv_years"))])
        cur.time_span = max(int(cur.time_span), 30)
        cur.projection_period = min(max(int(cur.projection_period), 1), cur.time_span)

    st.session_state[f"draft_{sid}"] = state_to_dict(cur)

    # ── Results ──
    page_title(cur.title, cur.description)
    r, kp, v = run(cur)
    r0, k0, v0 = run(saved)
    changed = _canon(state_to_dict(cur)) != _canon(state_to_dict(saved))

    b = st.columns([1, 1.3, 1, 4])
    if b[0].button("Save", type="primary", key=f"{k}_save", disabled=not changed):
        save_state(client, cur)
        st.toast("Saved")
        st.rerun()
    with b[1].popover("Save as new state"):
        nt = st.text_input("Title", cur.title + " (variant)", key=f"{k}_nt")
        mk = st.checkbox("Compare it with the saved state", True, key=f"{k}_mk")
        if st.button("Create", key=f"{k}_create", type="primary"):
            c_ = clone_state(cur, nt)
            c_.source = ""
            save_state(client, c_)
            if mk:
                save_comparison(client, Comparison(title=f"{saved.title} vs {nt}", state_ids=[saved.id, c_.id]))
            st.session_state.pop(f"draft_{sid}", None)
            go_to(client=client, state=c_.id, live=1)
    if b[2].button("Reset", key=f"{k}_reset", disabled=not changed, help="Back to the saved numbers"):
        st.session_state.pop(f"draft_{sid}", None)
        st.session_state[f"ver_{sid}"] = _ver(sid) + 1
        st.rerun()

    def head(label, now, before, fmt=money_short, lower_is_better=False):
        d = now - before if (np.isfinite(now) and np.isfinite(before)) else 0.0
        cls = "" if (not changed or abs(d) < 1e-9) else ("pos" if (d < 0 if lower_is_better else d > 0) else "neg")
        sub = (f'{"+" if d > 0 else ""}{fmt(d)} vs saved' if changed and abs(d) >= 1e-9 else "Same as saved")
        return (f'<div class="c-head"><div class="lbl">{esc(label)}</div><div class="val">{fmt(now)}</div>'
                f'<div class="sub"><span class="c-{"pos" if cls == "pos" else "neg" if cls == "neg" else "muted"}">'
                f'{esc(sub)}</span></div></div>')
    ratio = lambda x: f"{x:,.1f}" if np.isfinite(x) else "–"
    st.markdown('<div class="c-heads">'
                + head("Total discounted cash flow after tax", v.dcf_cumulative, v0.dcf_cumulative)
                + head("Equity value (DCF)", v.equity_value_dcf, v0.equity_value_dcf)
                + head("Lowest cash balance", kp.min_cash, k0.min_cash)
                + head("CAC (fully loaded)", kp.cac_blended, k0.cac_blended, money, lower_is_better=True)
                + head("LTV : CAC", kp.ltv_cac_ratio, k0.ltv_cac_ratio, ratio)
                + "</div>", unsafe_allow_html=True)
    vs = validation_summary(cur)
    if vs:
        st.markdown(f'<div class="c-muted" style="margin:-6px 0 12px">{esc(vs)}</div>', unsafe_allow_html=True)

    card(f"Targets (payback in {num(cur.target_payback_months)} months, LTV : CAC {num(cur.target_ltv_cac)})",
         targets_html(cur))
    named = [("Saved", r0), ("Now", r)] if changed else [(cur.title, r)]
    a, c = st.columns(2, gap="medium")
    with a:
        G.values_chart(named, "cum_dcf", "Daily", f"{k}_g1")
        G.values_chart(named, "active_customers", "Daily", f"{k}_g3")
    with c:
        G.values_chart(named, "cash_balance", "Daily", f"{k}_g2")
        monthly_cash_chart(r, key=f"{k}_g4")
    card("Funnel Per Channel", funnel_html(r))
    unit, rr, cash, val = kpi_tables(kp, v, cur)
    a, c, d = st.columns(3, gap="medium")
    card("Unit Economics", unit, a)
    card("Last 30 Days", rr, c)
    card("Cash and Customers", cash, d)


def _guest_sidebar(slug: str) -> str:
    """A client's own login: their client only, no client switcher, Live first."""
    meta = load_client_meta(slug)
    if st.query_params.get("client") != slug:
        go_to(client=slug)
    st.sidebar.markdown(f"**{esc(meta.name if meta else slug)}**")
    if st.sidebar.button("Overview", key="g_home"):
        go_to(client=slug)
    comps, states = list_comparisons(slug), list_states(slug)
    if comps:
        st.sidebar.caption("Comparisons")
        for c in comps:
            if st.sidebar.button(c.title, key=f"gc_{c.id}"):
                go_to(client=slug, comparison=c.id)
    if states:
        st.sidebar.caption("States")
        for s_ in states:
            if st.sidebar.button(s_.title, key=f"gs_{s_.id}"):
                go_to(client=slug, state=s_.id, live=1)
    st.sidebar.write("")
    with st.sidebar.expander("New state"):
        t = st.text_input("Title", "New State", key="g_new_t")
        src = st.selectbox("Start from", [s_.id for s_ in states] or ["blank"],
                           format_func=lambda i: next((x.title for x in states if x.id == i), "Blank"), key="g_new_src")
        if st.button("Create", key="g_new_go"):
            base = next((x for x in states if x.id == src), None)
            s_ = clone_state(base, t) if base else State(title=t)
            save_state(slug, s_)
            go_to(client=slug, state=s_.id, live=1)
    with st.sidebar.expander("New comparison"):
        t = st.text_input("Title", "New Comparison", key="g_new_ct")
        opts = {s_.id: s_.title for s_ in states}
        ch = st.multiselect("States (the first is the baseline)", list(opts), format_func=lambda i: opts[i], key="g_new_cs")
        if st.button("Create", key="g_new_cgo") and ch:
            c = Comparison(title=t, state_ids=ch)
            save_comparison(slug, c)
            go_to(client=slug, comparison=c.id)
    st.sidebar.write("")
    st.sidebar.caption("Your changes are saved to this model. Every state's Live page shows the inputs on the left; "
                       "the value, cash and targets on the right update as you type.")
    return slug


# ── Main ──────────────────────────────────────────────────────────────

share = qp("share") == "1"
client = qp("client")
if share:
    st.markdown('<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],'
                '[data-testid="collapsedControl"],[data-testid="stHeader"]{display:none}</style>',
                unsafe_allow_html=True)
elif qp("live") == "1" and qp("state"):
    pass  # the live page fills the sidebar with inputs
else:
    client = sidebar(client)

if client and st.session_state.get("_scope") and client != st.session_state["_scope"]:
    go_to(client=st.session_state["_scope"])
if client:
    if qp("comparison"):
        comp = load_comparison(client, qp("comparison"))
        if comp:
            render_comparison(client, comp, share)
        else:
            st.error("Comparison not found.")
    elif qp("state"):
        if qp("live") == "1" and not share:
            render_live(client, qp("state"))
        elif qp("edit") == "1" and not share:
            render_editor(client, qp("state"))
        else:
            s = load_state(client, qp("state"))
            if s:
                render_state(client, s, share)
            else:
                st.error("State not found.")
    elif not share:
        render_home(client)
