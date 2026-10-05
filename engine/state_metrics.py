"""Key metrics and valuation for a State: unit economics, cash timing and the DCF figures."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.events import State, StateResult, offer_economics, offer_ltv, event_mix


@dataclass
class StateKPIs:
    at_day: int
    # unit economics
    cac_blended: float  # fully loaded: S&M cost (lagged) / new customers, rolling 12 months
    cac_by_channel: dict  # direct channel costs only (paid-CAC style)
    ltv: float  # ltv_years horizon, discounted, net of delivery, refunds and payment fees
    expected_value: float
    ltv_cac_ratio: float
    payback_period_days: float  # cash payback, net of delivery costs
    payback_collection_days: float  # original definition: CAC / daily collection of the first payment
    # margins, trailing 30 days
    gross_margin: float
    ebitda_margin: float
    net_margin: float
    # trailing 30 days
    monthly_revenue: float
    monthly_cash_collected: float
    monthly_fcf: float
    monthly_new_customers: float
    # customers
    total_customers: float
    active_customers: float
    profit_per_customer_per_month: float
    k_value: float
    # cash and timing
    cash_needed: float
    cash_consumption: float
    min_cash: float
    min_cash_day: int
    time_to_profitability_days: int  # -1 = never within the time span
    time_to_self_fund_days: int  # -1 = never
    cash_conversion_cycle: float
    payback_months: float = float("inf")  # standard: CAC / (new MRR per customer x gross margin)
    cac_ratio: float = float("inf")  # S&M per $1 of new + expansion ARR
    sm_cost: float = 0.0  # S&M cost in the CAC window
    sm_new_customers: float = 0.0
    cac_window: tuple = (0, 0)  # (first day, last day) of new customers counted
    cac_lag: int = 0
    new_arr: float = 0.0
    expansion_arr: float = 0.0
    ltv_20y: float = 0.0  # reference: 20 years, undiscounted, delivery costs only
    cac_direct_cumulative: float = 0.0  # reference: direct channel costs since day 0 / all new customers


@dataclass
class StateValuation:
    dcf_cumulative: float  # total discounted cash flow after tax over the projection period
    dcf_per_share: float
    pv_fcf: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value_dcf: float
    equity_value_dcf: float
    share_price_dcf: float
    trailing_ebitda: float
    enterprise_value_ebitda: float
    equity_value_ebitda: float
    share_price_ebitda: float
    cash_at_valuation: float
    net_debt: float
    shares_at_valuation: float = 0.0
    debt_at_valuation: float = 0.0


def compute_state_kpis(state: State, r: StateResult, at_day: int | None = None) -> StateKPIs:
    T = len(r.days)
    end = T if at_day is None else max(1, min(int(at_day) + 1, T))
    s30 = max(0, end - 30)

    new_total = float(r.new_customers_total[:end].sum())
    acq_direct = float(r.cost_marketing[:end].sum() + r.cost_sales[:end].sum())
    cac_direct_cum = acq_direct / max(new_total, 1.0)

    # Fully loaded CAC, rolling 12 months, spend lagged by the sales-weighted time to sale
    if state.cac_lag_days is not None and state.cac_lag_days >= 0:
        lag = int(state.cac_lag_days)
    else:
        tot_s = sum(float(sv.sum()) for sv in r.event_sales)
        lag = int(round(sum((ev.time_to_market + ev.sales_cycle_days) * float(sv.sum())
                            for ev, sv in zip(state.events, r.event_sales)) / tot_s)) if tot_s > 0 else 0
    w = min(365, end)
    n0 = end - w
    new_win = float(r.new_customers_total[n0:end].sum())
    s0, s1 = max(0, n0 - lag), max(0, end - lag)
    fixed_sm = r.cost_fixed_sm if r.cost_fixed_sm is not None else np.zeros(T)
    sell_new = r.cost_sales_new if r.cost_sales_new is not None else r.cost_sales
    sm = float(r.cost_marketing[s0:s1].sum() + sell_new[s0:s1].sum() + fixed_sm[s0:s1].sum())
    cac = sm / new_win if new_win > 0 else float("inf")

    by_channel: dict = {}
    for ev, sales, cost in zip(state.events, r.event_sales, r.event_cost):
        c = by_channel.setdefault(ev.channel, [0.0, 0.0])
        c[0] += float(cost[:end].sum())
        c[1] += float(sales[:end].sum())
    cac_by_channel = {k: (v[0] / v[1] if v[1] > 0 else float("nan")) for k, v in by_channel.items()}

    # Sales-weighted offer economics
    econ = {o.name: offer_economics(o) for o in state.offers}
    ltvh = {o.name: offer_ltv(o, state.ltv_years, state.discount_rate, state.transaction_fee) for o in state.offers}
    weights: dict = {}
    for ev, sales in zip(state.events, r.event_sales):
        for oname, share in event_mix(ev).items():
            weights[oname] = weights.get(oname, 0.0) + share * float(sales[:end].sum())
    wsum = sum(weights.values())
    if wsum > 0:
        ltv = sum(ltvh[o] * w_ for o, w_ in weights.items() if o in ltvh) / wsum
        ltv20 = sum(econ[o]["ltv"] * w_ for o, w_ in weights.items() if o in econ) / wsum
        ev_ = sum(econ[o]["expected_value"] * w_ for o, w_ in weights.items() if o in econ) / wsum
    elif state.offers:
        n_ = state.offers[0].name
        ltv, ltv20, ev_ = ltvh[n_], econ[n_]["ltv"], econ[n_]["expected_value"]
    else:
        ltv = ltv20 = ev_ = 0.0

    # New and expansion ARR in the window; standard payback
    def monthly(o, renewal=False):
        if o.billing != "contract":
            pays = sorted(o.payments or [])
            return (pays[0][1] * o.realization_rate) if pays else 0.0
        p_ = o.renewal_price if renewal else o.price
        return p_ * o.realization_rate * 30.0 / max(int(o.contract_length), 1)
    sbo = r.sales_by_offer or {}
    new_mrr = sum(float(sbo[o.name][n0:end].sum()) * monthly(o) for o in state.offers if o.name in sbo)
    exp_mrr = 0.0
    for o in state.offers:
        if r.upgrades_in and o.name in r.upgrades_in:
            exp_mrr += float(r.upgrades_in[o.name][n0:end].sum()) * monthly(o, True)
        if r.upgrades_out and o.name in r.upgrades_out:
            exp_mrr -= float(r.upgrades_out[o.name][n0:end].sum()) * monthly(o, True)
    new_arr, exp_arr = new_mrr * 12.0, exp_mrr * 12.0
    cac_ratio = sm / (new_arr + exp_arr) if (new_arr + exp_arr) > 0 else float("inf")
    cash_w = float(r.cash_collected_total[n0:end].sum())
    gm_w = float(r.gross_profit[n0:end].sum()) / cash_w if cash_w > 0 else 0.0
    mrr_per_new = new_mrr / new_win if new_win > 0 else 0.0
    payback_m = cac / (mrr_per_new * gm_w) if (mrr_per_new * gm_w) > 0 and np.isfinite(cac) else float("inf")

    # Payback: days after a sale until that customer's cash, net of delivery, covers the CAC
    payback = float("inf")
    main = max(weights, key=weights.get) if wsum > 0 else (state.offers[0].name if state.offers else None)
    o = state.offer_by_name(main) if main else None
    if o is not None and np.isfinite(cac):
        from engine.events import offer_kernel
        k = offer_kernel(o, max(T, 3650))
        net = (k["cash_new"] + k["cash_ren"]) * (1 - state.transaction_fee) - k["refund_cost"] - k["ful_new"] \
            - k["ful_ren"] - k["sell_ren"]
        hit = np.nonzero(np.cumsum(net) >= cac)[0]
        if len(hit):
            payback = float(hit[0])
    payback_coll = float("inf")
    if o is not None and np.isfinite(cac):
        first = (o.price * o.realization_rate) if o.billing == "contract" else (
            sorted(o.payments)[0][1] * o.realization_rate if o.payments else 0.0)
        rate_ = first / max(int(o.time_to_collect), 1) if o.billing == "contract" else first / 30.0
        payback_coll = cac / rate_ if rate_ > 0 else float("inf")

    rev30 = float(r.cash_collected_total[s30:end].sum())
    gp30 = float(r.gross_profit[s30:end].sum())
    eb30 = float(r.ebitda[s30:end].sum())
    ni30 = float(r.net_income[s30:end].sum())
    pct = lambda a: (a / rev30 * 100.0) if rev30 > 0 else 0.0

    active_end = float(r.active_customers[end - 1])
    ppcm = ((rev30 - float(r.cost_total[s30:end].sum())) / active_end) if active_end > 0 else 0.0

    k_value = sum(ev.invites_per_customer * ev.invite_conversion for ev in state.events if ev.driver == "viral")

    cash = r.cash_balance
    min_idx = int(np.argmin(cash))
    cum_after_upfront = r.cumulative_fcf - state.upfront_investment
    neg = np.nonzero(cum_after_upfront < 0)[0]
    if len(neg) == 0:
        ttp = 0
    elif neg[-1] < T - 1:
        ttp = int(neg[-1] + 1)
    else:
        ttp = -1
    if cash[0] >= 0:
        ttsf = 0
    else:
        up = np.nonzero((cash[1:] >= 0) & (cash[:-1] < 0))[0]
        ttsf = int(up[0] + 1) if len(up) else -1

    spend_w = [(f.cash_conversion_cycle, max(f.total_spend, 1e-9)) for f in r.funnels if f.driver != "viral"]
    ccc = (sum(c * w for c, w in spend_w) / sum(w for _, w in spend_w)) if spend_w else 0.0

    return StateKPIs(
        at_day=end - 1, cac_blended=cac, cac_by_channel=cac_by_channel, ltv=ltv, expected_value=ev_,
        ltv_cac_ratio=(ltv / cac) if (cac > 0 and np.isfinite(cac)) else float("inf"),
        payback_period_days=payback, payback_collection_days=payback_coll,
        payback_months=payback_m, cac_ratio=cac_ratio, sm_cost=sm, sm_new_customers=new_win,
        cac_window=(n0, end - 1), cac_lag=lag, new_arr=new_arr, expansion_arr=exp_arr, ltv_20y=ltv20,
        cac_direct_cumulative=cac_direct_cum,
        gross_margin=pct(gp30), ebitda_margin=pct(eb30), net_margin=pct(ni30),
        monthly_revenue=float(r.revenue_total[s30:end].sum()), monthly_cash_collected=rev30,
        monthly_fcf=float(r.free_cash_flow[s30:end].sum()),
        monthly_new_customers=float(r.new_customers_total[s30:end].sum()),
        total_customers=float(r.cumulative_customers[end - 1]), active_customers=active_end,
        profit_per_customer_per_month=ppcm, k_value=k_value,
        cash_needed=max(-float(cash.min()), state.upfront_investment, 0.0),
        cash_consumption=abs(min(float(cash.min()), 0.0)),
        min_cash=float(cash[min_idx]), min_cash_day=min_idx,
        time_to_profitability_days=ttp, time_to_self_fund_days=ttsf, cash_conversion_cycle=ccc,
    )


def compute_state_valuation(state: State, r: StateResult) -> StateValuation:
    T = len(r.days)
    proj = min(max(int(state.projection_period), 1), T)
    pv_fcf = float(r.dcf[:proj].sum())
    window = min(365, proj)
    annual_fcf = float(r.free_cash_flow[proj - window:proj].mean()) * 365.0
    g, d = state.perpetual_growth_rate, state.discount_rate
    tv = annual_fcf * (1 + g) / (d - g) if d > g else 0.0
    pv_tv = tv / ((1 + d) ** (proj / 365.0))
    ev_dcf = pv_fcf + pv_tv
    debt_s = r.debt_outstanding if r.debt_outstanding is not None else np.full(T, float(state.debt))
    shares_s = r.shares_outstanding if r.shares_outstanding is not None else np.full(T, float(state.shares))
    cash_val = float(r.cash_balance[proj - 1])
    debt_val = float(debt_s[proj - 1])
    eq_dcf = ev_dcf - debt_val + max(cash_val, 0.0)

    ep = min(max(int(state.ebitda_projection_period), 1), T)
    trailing = float(r.ebitda[max(ep - 365, 0):ep].sum())
    ev_eb = trailing * state.ebitda_multiple
    cash_eb = float(r.cash_balance[ep - 1])
    eq_eb = ev_eb - float(debt_s[ep - 1]) + max(cash_eb, 0.0)
    sh = max(float(shares_s[proj - 1]), 1.0)
    sh_eb = max(float(shares_s[ep - 1]), 1.0)
    return StateValuation(
        dcf_cumulative=float(r.cum_dcf[proj - 1]), dcf_per_share=float(r.cum_dcf[proj - 1]) / sh,
        pv_fcf=pv_fcf, terminal_value=tv, pv_terminal_value=pv_tv, enterprise_value_dcf=ev_dcf,
        equity_value_dcf=eq_dcf, share_price_dcf=eq_dcf / sh, trailing_ebitda=trailing,
        enterprise_value_ebitda=ev_eb, equity_value_ebitda=eq_eb, share_price_ebitda=eq_eb / sh_eb,
        cash_at_valuation=cash_val, net_debt=debt_val - cash_val, shares_at_valuation=sh,
        debt_at_valuation=debt_val,
    )
