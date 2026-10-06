"""Graph views over a StateResult: every daily series the engine produces, shown as
daily, monthly or cumulative values, and for comparisons as values, absolute
difference and percent difference against the first state."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from ui.corporate import chart, PALETTE, RED, RULE, money, esc

# key: (label, attribute or callable, kind, money?)  kind: flow = per day (summed per period), stock = level
SERIES = {
    # customers
    "new_customers_total": ("New customers", "new_customers_total", "flow", False),
    "active_customers": ("Active customers", "active_customers", "stock", False),
    "cumulative_customers": ("Total customers (cumulative)", "cumulative_customers", "stock", False),
    "churned_customers": ("Churned customers (cumulative)", "churned_customers", "stock", False),
    "renewed_customers": ("Renewed customers (cumulative)", "renewed_customers", "stock", False),
    "new_customers_inbound": ("New customers: inbound", "new_customers_inbound", "flow", False),
    "new_customers_outbound": ("New customers: outbound", "new_customers_outbound", "flow", False),
    "new_customers_organic": ("New customers: organic", "new_customers_organic", "flow", False),
    "new_customers_viral": ("New customers: viral", "new_customers_viral", "flow", False),
    # funnel
    "impressions": ("Reached (impressions, contacts, visits)", "impressions", "flow", False),
    "views": ("Engaged (clicks, leads)", "views", "flow", False),
    "leads": ("Leads and meetings", "leads", "flow", False),
    "leads_inbound": ("Leads: inbound", "leads_inbound", "flow", False),
    "leads_outbound": ("Leads: outbound", "leads_outbound", "flow", False),
    "leads_organic": ("Leads: organic", "leads_organic", "flow", False),
    # revenue
    "cash_collected_total": ("Cash collected", "cash_collected_total", "flow", True),
    "cash_collected_new": ("Cash collected: new customers", "cash_collected_new", "flow", True),
    "cash_collected_renewal": ("Cash collected: renewals", "cash_collected_renewal", "flow", True),
    "revenue_total": ("Revenue booked", "revenue_total", "flow", True),
    # costs
    "cost_total": ("Total costs", "cost_total", "flow", True),
    "cost_marketing": ("Marketing spend", "cost_marketing", "flow", True),
    "cost_sales": ("Cost to sell", "cost_sales", "flow", True),
    "cost_fulfillment": ("Cost to fulfil", "cost_fulfillment", "flow", True),
    "cost_cogs": ("Cost of goods sold (fulfil + payment fees)", "cost_cogs", "flow", True),
    "cost_fixed": ("Fixed expenses", "cost_fixed", "flow", True),
    "cost_fixed_sm": ("Fixed expenses: sales and marketing", "cost_fixed_sm", "flow", True),
    "cost_transaction_fees": ("Payment fees", "cost_transaction_fees", "flow", True),
    "cost_refunds": ("Refunds", "cost_refunds", "flow", True),
    "cost_interest": ("Interest", "cost_interest", "flow", True),
    "variable_cash_flow": ("Variable cash flow (cash collected minus variable costs)",
                           lambda r: r.cash_collected_total - r.cost_marketing - r.cost_sales - r.cost_fulfillment
                           - r.cost_transaction_fees - r.cost_refunds, "flow", True),
    # profit
    "gross_profit": ("Gross profit", "gross_profit", "flow", True),
    "ebitda": ("EBITDA", "ebitda", "flow", True),
    "cash_flow_before_tax": ("Cash flow before tax", "cash_flow_before_tax", "flow", True),
    "tax": ("Tax", "tax", "flow", True),
    "net_income": ("Cash flow after tax", "net_income", "flow", True),
    "free_cash_flow": ("Free cash flow", "free_cash_flow", "flow", True),
    # cash and financing
    "cash_balance": ("Cash balance", "cash_balance", "stock", True),
    "cash_balance_operating": ("Cash balance without financing", "cash_balance_operating", "stock", True),
    "cumulative_fcf": ("Cumulative free cash flow", "cumulative_fcf", "stock", True),
    "financing_in": ("Financing received", "financing_in", "flow", True),
    "loan_repayment": ("Loan repayments", "loan_repayment", "flow", True),
    "debt_outstanding": ("Debt outstanding", "debt_outstanding", "stock", True),
    "shares_outstanding": ("Shares outstanding", "shares_outstanding", "stock", False),
    # valuation
    "dcf": ("Discounted cash flow after tax", "dcf", "flow", True),
    "cum_dcf": ("Total discounted cash flow after tax", "cum_dcf", "stock", True),
}

VIEWS = [
    ("Overview", ["cum_dcf", "cash_balance", "active_customers", "cash_collected_total"]),
    ("Customers", ["new_customers_total", "active_customers", "cumulative_customers", "churned_customers"]),
    ("Channels", ["new_customers_inbound", "new_customers_outbound", "new_customers_organic",
                  "new_customers_viral"]),
    ("Funnel", ["impressions", "views", "leads", "new_customers_total"]),
    ("Revenue", ["cash_collected_total", "cash_collected_new", "cash_collected_renewal", "revenue_total"]),
    ("Costs", ["cost_total", "cost_marketing", "cost_sales", "cost_fulfillment", "cost_fixed",
               "cost_transaction_fees", "cost_refunds", "cost_interest"]),
    ("Margin", ["variable_cash_flow", "gross_profit", "cost_cogs", "cost_fixed_sm"]),
    ("Profit", ["ebitda", "cash_flow_before_tax", "tax", "net_income"]),
    ("Cash", ["cash_balance", "cash_balance_operating", "cumulative_fcf", "free_cash_flow"]),
    ("Financing", ["financing_in", "loan_repayment", "debt_outstanding", "shares_outstanding"]),
    ("Valuation", ["dcf", "cum_dcf"]),
]
MODES = ["Daily", "Monthly", "Cumulative"]


def series(r, key: str) -> np.ndarray:
    label, src, kind, _ = SERIES[key]
    arr = src(r) if callable(src) else getattr(r, src, None)
    if arr is None:
        arr = np.zeros(len(r.days))
    return np.asarray(arr, dtype=float)


def shaped(arr: np.ndarray, kind: str, mode: str) -> tuple:
    """(x, y) for a mode. Flows: Monthly sums per 30 days, Cumulative running total.
    Stocks: Monthly takes the level at the end of each 30 days; Cumulative is the level itself."""
    T = len(arr)
    if mode == "Monthly":
        m = T // 30
        if m == 0:
            return np.arange(T), arr
        x = np.arange(1, m + 1)
        if kind == "flow":
            y = arr[:m * 30].reshape(m, 30).sum(axis=1)
        else:
            y = arr[29:m * 30:30]
        return x, y
    if mode == "Cumulative" and kind == "flow":
        return np.arange(T), np.cumsum(arr)
    return np.arange(T), arr


def _title(key: str, mode: str) -> str:
    label, _, kind, _ = SERIES[key]
    if mode == "Monthly":
        return f"{label} per month" if kind == "flow" else f"{label} (end of month)"
    if mode == "Cumulative" and kind == "flow":
        return f"{label} (cumulative)"
    return f"{label} per day" if kind == "flow" else label


def values_chart(named: list, key: str, mode: str, ckey: str, compare_day=None, height: int = 320) -> None:
    label, _, kind, is_money = SERIES[key]
    fig = go.Figure()
    for i, (name, r) in enumerate(named):
        x, y = shaped(series(r, key), kind, mode)
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name,
                                 line=dict(color=PALETTE[i % len(PALETTE)], width=2.5 if len(named) > 1 else 2)))
    if compare_day is not None:
        fig.add_vline(x=(compare_day // 30) if mode == "Monthly" else compare_day, line=dict(color="#adb5bd", dash="dash"))
    if is_money and kind == "stock":
        fig.add_hline(y=0, line=dict(color="#cbd5e1", width=1))
    chart(fig, _title(key, mode), height, money_axis=is_money, key=ckey,
          xtitle="Month" if mode == "Monthly" else "Days", zero=True)


def difference_charts(named: list, key: str, mode: str, ckey: str, compare_day=None) -> None:
    """Absolute and percent difference of every state against the first one."""
    label, _, kind, is_money = SERIES[key]
    base_name, base = named[0]
    bx, by = shaped(series(base, key), kind, mode)
    fa, fp = go.Figure(), go.Figure()
    for i, (name, r) in enumerate(named[1:], start=1):
        x, y = shaped(series(r, key), kind, mode)
        n = min(len(y), len(by))
        dd = y[:n] - by[:n]
        floor = max(0.02 * float(np.max(np.abs(by[:n]))) if n else 0.0, 1e-9)
        with np.errstate(divide="ignore", invalid="ignore"):
            pc = np.where(np.abs(by[:n]) > floor, dd / np.abs(by[:n]) * 100.0, np.nan)
        colr = PALETTE[i % len(PALETTE)]
        fa.add_trace(go.Scatter(x=x[:n], y=dd, mode="lines", name=f"{name} minus {base_name}",
                                line=dict(color=colr, width=2.5), fill="tozeroy", fillcolor="rgba(11,37,69,0.08)"))
        fp.add_trace(go.Scatter(x=x[:n], y=pc, mode="lines", name=f"{name} vs {base_name}",
                                line=dict(color=colr, width=2.5)))
        if compare_day is not None:
            d = (compare_day // 30) - 1 if mode == "Monthly" else compare_day
            if 0 <= d < n:
                txt = money(dd[d]) if is_money else f"{dd[d]:,.1f}"
                fa.add_annotation(x=x[d], y=dd[d], text=f"{'Month' if mode == 'Monthly' else 'Day'} {x[d]:,}: {txt}",
                                  showarrow=True, arrowcolor="#adb5bd", ax=90, ay=60, bgcolor="#fff",
                                  bordercolor=RULE, borderpad=6)
    if compare_day is not None:
        xv = (compare_day // 30) if mode == "Monthly" else compare_day
        for f in (fa, fp):
            f.add_vline(x=xv, line=dict(color="#adb5bd", dash="dash"))
    xt = "Month" if mode == "Monthly" else "Days"
    chart(fa, f"{_title(key, mode)}: absolute difference", 320, money_axis=is_money, key=ckey + "_a", xtitle=xt)
    fp.update_yaxes(ticksuffix="%")
    chart(fp, f"{_title(key, mode)}: percent difference", 300, key=ckey + "_p", xtitle=xt)


def by_offer_chart(r, offers: list, ckey: str, mode: str, what: str = "active") -> None:
    fig = go.Figure()
    src = r.active_by_offer if what == "active" else r.revenue_by_offer
    kind = "stock" if what == "active" else "flow"
    for i, name in enumerate(offers):
        arr = src.get(name)
        if arr is None or not np.any(arr):
            continue
        x, y = shaped(np.asarray(arr, dtype=float), kind, mode)
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name, stackgroup="one",
                                 line=dict(color=PALETTE[i % len(PALETTE)], width=1.5)))
    ttl = "Active customers by offer" if what == "active" else "Cash collected by offer"
    if mode == "Monthly":
        ttl += " (end of month)" if what == "active" else " per month"
    chart(fig, ttl, 340, money_axis=(what != "active"), key=ckey, xtitle="Month" if mode == "Monthly" else "Days")


def by_channel_chart(r, ckey: str, mode: str) -> None:
    fig = go.Figure()
    for i, (lbl, key) in enumerate([("Inbound", "new_customers_inbound"), ("Outbound", "new_customers_outbound"),
                                    ("Organic", "new_customers_organic"), ("Viral", "new_customers_viral"),
                                    ("Other", "new_customers_other")]):
        arr = getattr(r, key, None)
        if arr is None or not np.any(arr):
            continue
        x, y = shaped(np.asarray(arr, dtype=float), "flow", mode)
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=lbl, stackgroup="one",
                                 line=dict(color=PALETTE[i % len(PALETTE)], width=1.5)))
    ttl = {"Daily": "New customers per day by channel", "Monthly": "New customers per month by channel",
           "Cumulative": "Total new customers by channel"}[mode]
    chart(fig, ttl, 340, key=ckey, xtitle="Month" if mode == "Monthly" else "Days")


def picker(ckey: str, default_view: str = "Overview", views=None) -> tuple:
    """View and mode selectors. Returns (view name, mode)."""
    names = [v for v, _ in (views or VIEWS)]
    c1, c2 = st.columns([3.3, 1.5])
    view = c1.segmented_control("Graphs", names, default=default_view if default_view in names else names[0],
                                key=f"gv_{ckey}", label_visibility="collapsed")
    mode = c2.segmented_control("Show as", MODES, default="Daily", key=f"gm_{ckey}", label_visibility="collapsed")
    return view or names[0], mode or "Daily"


def render_view(named: list, view: str, mode: str, ckey: str, compare_day=None, offers: list | None = None) -> None:
    """One state: a grid of charts for the view. Several states: the same charts with one line per state."""
    keys = dict(VIEWS)[view]
    r0 = named[0][1]
    multi = len(named) > 1
    cols = st.columns(2, gap="medium")
    i = 0
    if view == "Channels" and not multi:
        with cols[0]:
            by_channel_chart(r0, f"{ckey}_bych", mode)
        i = 1
    if view == "Customers" and not multi and offers and len(offers) > 1:
        with cols[i % 2]:
            by_offer_chart(r0, offers, f"{ckey}_byo", mode, "active")
        i += 1
    if view == "Revenue" and not multi and offers and len(offers) > 1:
        with cols[i % 2]:
            by_offer_chart(r0, offers, f"{ckey}_byr", mode, "cash")
        i += 1
    for key in keys:
        if key not in SERIES:
            continue
        if not multi and key in ("financing_in", "loan_repayment", "debt_outstanding") and \
                not np.any(series(r0, key)):
            continue
        with cols[i % 2]:
            values_chart(named, key, mode, f"{ckey}_{key}", compare_day)
        i += 1


def _slug(key: str) -> str:
    return "g-" + key.replace("_", "-")


def shortcuts_html(named: list) -> str:
    """Anchor links to every graph on the page, grouped like the views."""
    parts = []
    seen = set()
    for view, keys in VIEWS:
        if view == "Overview":
            continue
        items = []
        for k in keys:
            if k in seen or k not in SERIES or not _has_data(named, k):
                continue
            seen.add(k)
            items.append(f'<a href="#{_slug(k)}">{SERIES[k][0]}</a>')
        if items:
            parts.append(f'<div class="c-sc-group"><div class="c-sc-title">{view}</div>' + "".join(items) + "</div>")
    rest = [k for k in SERIES if k not in seen and _has_data(named, k)]
    if rest:
        parts.append('<div class="c-sc-group"><div class="c-sc-title">Other</div>'
                     + "".join(f'<a href="#{_slug(k)}">{SERIES[k][0]}</a>' for k in rest) + "</div>")
    return '<div class="c-shortcuts">' + "".join(parts) + "</div>"


def _has_data(named: list, key: str) -> bool:
    return any(np.any(series(r, key)) for _, r in named)


def render_all(named: list, mode: str, ckey: str, compare_day=None) -> None:
    """Every series on one page: values, then absolute and percent difference against the first state."""
    import streamlit as st
    multi = len(named) > 1
    seen = set()
    order = [k for _, keys in VIEWS for k in keys if k in SERIES] + list(SERIES)
    for key in order:
        if key in seen or not _has_data(named, key):
            continue
        seen.add(key)
        st.markdown(f'<div class="c-anchor" id="{_slug(key)}"></div>', unsafe_allow_html=True)
        values_chart(named, key, mode, f"{ckey}_{key}_v", compare_day, height=360)
        if multi:
            a, b = st.columns(2, gap="medium")
            with a:
                _difference_chart(named, key, mode, f"{ckey}_{key}", compare_day, "abs")
            with b:
                _difference_chart(named, key, mode, f"{ckey}_{key}", compare_day, "pct")


def _difference_chart(named, key, mode, ckey, compare_day, which) -> None:
    label, _, kind, is_money = SERIES[key]
    base_name, base = named[0]
    bx, by = shaped(series(base, key), kind, mode)
    fig = go.Figure()
    for i, (name, r) in enumerate(named[1:], start=1):
        x, y = shaped(series(r, key), kind, mode)
        n = min(len(y), len(by))
        dd = y[:n] - by[:n]
        colr = PALETTE[i % len(PALETTE)]
        if which == "abs":
            fig.add_trace(go.Scatter(x=x[:n], y=dd, mode="lines", name=f"{name} minus {base_name}",
                                     line=dict(color=colr, width=2), fill="tozeroy", fillcolor="rgba(37,99,235,0.08)"))
            if compare_day is not None:
                d = (compare_day // 30) - 1 if mode == "Monthly" else compare_day
                if 0 <= d < n:
                    txt = money(dd[d]) if is_money else f"{dd[d]:,.1f}"
                    fig.add_annotation(x=x[d], y=dd[d], text=f"{'Month' if mode == 'Monthly' else 'Day'} {x[d]:,}: {txt}",
                                       showarrow=True, arrowcolor="#adb5bd", ax=80, ay=50, bgcolor="#fff",
                                       bordercolor=RULE, borderpad=6)
        else:
            floor = max(0.02 * float(np.max(np.abs(by[:n]))) if n else 0.0, 1e-9)
            with np.errstate(divide="ignore", invalid="ignore"):
                pc = np.where(np.abs(by[:n]) > floor, dd / np.abs(by[:n]) * 100.0, np.nan)
            fig.add_trace(go.Scatter(x=x[:n], y=pc, mode="lines", name=f"{name} vs {base_name}",
                                     line=dict(color=colr, width=2)))
    if compare_day is not None:
        fig.add_vline(x=(compare_day // 30) if mode == "Monthly" else compare_day, line=dict(color="#adb5bd", dash="dash"))
    xt = "Month" if mode == "Monthly" else "Days"
    if which == "abs":
        chart(fig, "Absolute difference", 300, money_axis=is_money, key=ckey + "_a", xtitle=xt)
    else:
        fig.update_yaxes(ticksuffix="%")
        chart(fig, "Percent difference", 300, key=ckey + "_p", xtitle=xt)
