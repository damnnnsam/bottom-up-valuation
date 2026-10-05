"""
The state model: a business as offers, marketing events, fixed expenses and
financing events, simulated day by day.

  Sim parameters   time span, projection period, discount rate, tax rate,
                   perpetual growth, EBITDA multiple, shares, LTV horizon
  Starting state   cash, assets, liabilities, debt and interest, upfront
                   investment, existing customers per offer, total addressable
                   market, payment fee
  Offers           price, realization, cost to sell and fulfil, time to
                   collect, refunds, contract length, churn, renewals with
                   their own price and costs, renewal rate of renewals.
                   An offer can instead be a payment schedule (day / amount
                   after the sale).
  Marketing events one row per channel and day window. Drivers:
                     spend     spend per day with CPM and CTR, or cost per click
                     outbound  contacts per day, cost per contact, people and
                               tools, reply / positive / meeting / close rates
                     volume    visits per day given directly (SEO, content)
                     viral     active customers x invites x invite conversion
                     team      headcount x contacts per head per month
                   Sales land after time to market + sales cycle. Each row is
                   marked validated (measured) or hypothesis.
  Fixed expenses   amount per day between two days, plus an amount per day
                   for every 100 active customers; employee and sales &
                   marketing flags (the latter counts toward CAC).
  Financing events equity (dilution), grants, loans with interest, grace and
                   maturity. They change cash, debt and shares, not the DCF.
  Offer tiers      existing customers split across offers; a channel row can
                   sell several offers by share (offer mix); upgrades move a
                   monthly share of active customers between offers.

Day windows include both ends (0-180, then 181-700). Rates are fractions
(0.09 = 9%). The row-and-day-window structure follows the comparison tool
Nick Kozmin (Salesprocess.io) shows in his videos; the engine is original.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone

import numpy as np


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Data model ─────────────────────────────────────────────────────────

@dataclass
class Offer:
    name: str
    billing: str = "contract"  # "contract" or "schedule"
    price: float = 5000.0
    realization_rate: float = 1.0
    cost_to_sell: float = 0.0  # fraction of price, paid on the day of sale
    cost_to_fulfill: float = 0.0  # contract: fraction of price spread over the contract; schedule: of each payment
    time_to_collect: int = 0  # days the first payment is spread over (0 = paid on the day of sale)
    contract_length: int = 365
    refund_period: int = 0
    refund_rate: float = 0.0
    churn_rate: float = 1.0  # share that does not renew at the end of the first contract
    renewal_price: float = 0.0
    renewal_time_to_collect: int = 0
    renewal_cost_to_sell: float = 0.0
    renewal_cost_to_fulfill: float = 0.0
    renewal_rate_of_renewals: float = 0.0
    # schedule billing
    payments: list = field(default_factory=list)  # [[day after sale, amount], ...]
    generator: dict = field(default_factory=dict)


@dataclass
class MarketingEvent:
    title: str
    offer: str
    channel: str = "Paid Advertising"
    driver: str = "spend"  # spend | outbound | volume | viral | team (original SDR model)
    start_day: int = 0
    end_day: int = 365
    spend_per_day: float = 0.0
    cost_per_click: float = 0.0  # spend driver: if set, clicks = spend / CPC (search); otherwise CPM and CTR
    cpm: float = 0.0
    ctr: float = 1.0
    lead_to_view: float = 0.0
    sale_to_lead: float = 0.0
    time_to_market: int = 0
    sales_cycle_days: int = 0
    # team driver
    headcount: float = 0.0
    salary_per_month: float = 0.0
    contacts_per_head_per_month: float = 0.0
    # outbound driver: volume-based, so one GTM engineer can scale sending without adding heads
    contacts_per_day: float = 0.0
    cost_per_contact: float = 0.0  # data, enrichment, verification, sending
    people_cost_per_month: float = 0.0  # SDRs / GTM engineer running this channel (counts toward CAC)
    tools_cost_per_month: float = 0.0
    mailboxes: float = 0.0  # optional sending limit: mailboxes x sends per mailbox per day (0 = no limit)
    sends_per_mailbox_per_day: float = 0.0
    reply_rate: float = 0.0  # contacts -> replies
    positive_reply_rate: float = 0.0  # replies -> interested
    meeting_rate: float = 0.0  # interested -> meeting held
    close_rate: float = 0.0  # meeting -> customer
    # volume driver
    views_per_day: float = 0.0
    # viral driver
    invites_per_customer: float = 0.0
    invite_conversion: float = 0.0
    viral_cost_to_market: float = 0.0  # fraction of offer price per viral sale
    # override of the offer's cost to sell (fraction of price); -1 = use the offer's
    cost_to_sell_override: float = -1.0
    offer_mix: dict = field(default_factory=dict)  # {offer: share}; empty = 100% to `offer`
    validated: bool = False  # False = hypothesis; True = the rates come from measured data
    validation_note: str = ""  # where the numbers come from (test, period, sample size)


@dataclass
class FixedExpense:
    title: str
    description: str = ""
    start_day: int = 0
    end_day: int = 730
    amount_per_day: float = 0.0
    per_100_customers_per_day: float = 0.0
    employee: bool = False
    sales_marketing: bool = False  # counts toward fully loaded CAC (profit is unchanged)


@dataclass
class FinancingEvent:
    """Cash that arrives on one day: equity, grant or loan.

    Equity issues shares (dilution). A grant is free money. A loan accrues
    interest on the outstanding balance and is repaid in equal daily amounts
    between `day + grace_days` and `day + maturity_days`. With `compounding`
    the interest is added to the balance instead of being paid as it accrues.
    Financing never changes the DCF except through loan interest; it changes
    cash, debt and shares."""
    title: str
    kind: str = "equity"  # equity | grant | loan
    day: int = 0
    amount: float = 0.0
    terms: str = ""
    # loan only
    interest_rate: float = 0.0  # annual, on the outstanding balance
    maturity_days: int = 1095  # fully repaid this many days after the loan day
    grace_days: int = 0  # repayment starts this many days after the loan day
    compounding: bool = False  # True = interest is capitalised and paid with the principal
    # equity only
    valuation: float = 0.0  # pre-money valuation; with shares_issued = 0 the shares follow from it
    shares_issued: float = 0.0
    purpose: str = ""  # grant only


@dataclass
class Upgrade:
    """A monthly share of active customers on one offer moves to another.

    The moved customers stop their old offer and start the new one as if on a
    renewal (renewal price and costs, no sales cost)."""
    from_offer: str
    to_offer: str
    monthly_rate: float = 0.0  # 0.02 = 2% of active customers on from_offer per month
    start_day: int = 0
    end_day: int = 3000
    description: str = ""


@dataclass
class State:
    title: str
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created: str = field(default_factory=_now)
    # sim parameters
    time_span: int = 3000
    projection_period: int = 3000
    discount_rate: float = 0.09
    tax_rate: float = 0.22
    loss_carryforward: bool = False
    perpetual_growth_rate: float = 0.02
    ebitda_multiple: float = 14.0
    ebitda_projection_period: int = 1825
    shares: int = 1_000_000
    ltv_years: float = 5.0  # LTV horizon; LTV is discounted at discount_rate and net of the transaction fee
    cac_lag_days: int = -1  # spend lag for CAC; -1 = sales-weighted time to market + sales cycle
    # starting state
    starting_cash: float = 0.0
    assets: float = 0.0
    liabilities: float = 0.0
    debt: float = 0.0
    interest_rate: float = 0.0
    upfront_investment: float = 0.0
    existing_customers: float = 0.0
    existing_customers_offer: str = ""
    existing_by_offer: dict = field(default_factory=dict)  # {offer: count}; overrides the two fields above
    total_addressable_market: float = 0.0  # 0 = no cap
    transaction_fee: float = 0.0  # fraction of cash collected
    # rows
    offers: list = field(default_factory=list)
    events: list = field(default_factory=list)
    expenses: list = field(default_factory=list)
    upgrades: list = field(default_factory=list)
    financing: list = field(default_factory=list)
    source: str = ""  # e.g. "model:baseline" when converted from an old model

    def offer_by_name(self, name: str):
        for o in self.offers:
            if o.name == name:
                return o
        return None

    def active_offer_names(self) -> set:
        names = set()
        for e in self.events:
            names.update(event_mix(e))
        names.update(existing_book(self))
        for u in self.upgrades:
            if u.monthly_rate > 0:
                names.update((u.from_offer, u.to_offer))
        return names


def existing_book(state) -> dict:
    """Existing customers per offer."""
    if state.existing_by_offer:
        return {k: float(v) for k, v in state.existing_by_offer.items() if float(v or 0) > 0}
    if state.existing_customers > 0:
        names = [o.name for o in state.offers]
        off = state.existing_customers_offer if state.existing_customers_offer in names else (names[0] if names else "")
        return {off: float(state.existing_customers)} if off else {}
    return {}


def existing_total(state) -> float:
    return float(sum(existing_book(state).values()))


def event_mix(ev) -> dict:
    """Share of an event's sales going to each offer (sums to 1)."""
    mix = {k: float(v) for k, v in (ev.offer_mix or {}).items() if float(v or 0) > 0}
    tot = sum(mix.values())
    if tot <= 0:
        return {ev.offer: 1.0}
    return {k: v / tot for k, v in mix.items()}


def _pick(cls, d: dict):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


def state_to_dict(s: State) -> dict:
    return asdict(s)


def state_from_dict(d: dict) -> State:
    d = dict(d)
    offers = []
    for od in d.pop("offers", []):
        o = _pick(Offer, od)
        if "billing" not in od and od.get("payments"):  # saved by the first version
            o.billing = "schedule"
            o.price = float(od.get("generator", {}).get("price", od["payments"][0][1]))
        offers.append(o)
    events = []
    for ed in d.pop("events", []):
        e = _pick(MarketingEvent, ed)
        events.append(e)
    expenses = [_pick(FixedExpense, x) for x in d.pop("expenses", [])]
    upgrades = [_pick(Upgrade, u) for u in d.pop("upgrades", [])]
    financing = [_pick(FinancingEvent, x) for x in d.pop("financing", [])]
    s = _pick(State, d)
    s.offers, s.events, s.expenses, s.upgrades, s.financing = offers, events, expenses, upgrades, financing
    return s


# ── Payment schedule generators (schedule billing) ─────────────────────

def schedule_subscription(price, every_days, churn_per_period, periods):
    every_days = max(int(every_days), 1)
    keep = 1.0 - churn_per_period
    return [[k * every_days, round(price * keep ** k, 4)] for k in range(int(periods))]


def build_schedule(gen: dict) -> list:
    kind = gen.get("kind", "subscription")
    if kind == "subscription":
        return schedule_subscription(gen.get("price", 100.0), gen.get("every_days", 30),
                                     gen.get("churn", 0.05), gen.get("periods", 13))
    if kind == "one_time":
        return [[int(gen.get("day", 0)), float(gen.get("price", 1000.0))]]
    if kind == "installments":
        n = max(int(gen.get("n", 3)), 1)
        return [[k * int(gen.get("every_days", 30)), round(gen.get("price", 1000.0) / n, 4)] for k in range(n)]
    return []


# ── Per-sale cohort curves ─────────────────────────────────────────────

KERNEL_FIELDS = ("rev_new", "rev_ren", "cash_new", "cash_ren", "sell_new", "sell_ren",
                 "ful_new", "ful_ren", "refund_cost", "refunded", "churned", "renewed", "active")


def _spread(arr: np.ndarray, start: int, length: int, total: float) -> None:
    n = len(arr)
    if start >= n or total == 0:
        return
    if length <= 0:
        arr[start] += total
        return
    arr[start:min(start + length, n)] += total / length


def offer_kernel(o: Offer, n: int, existing: bool = False) -> dict:
    """What one sale (or one existing customer) of this offer does, day by day after the sale."""
    k = {f: np.zeros(n) for f in KERNEL_FIELDS}
    rr = o.realization_rate

    if o.billing == "schedule":
        pays = sorted((int(d), float(a)) for d, a in (o.payments or []))
        if not pays:
            return k
        first = pays[0][1] if pays[0][1] else 1.0
        k["sell_new"][0] = o.price * o.cost_to_sell
        for i, (d, a) in enumerate(pays):
            if d < n:
                k["cash_new"][d] += a * rr
                k["rev_new"][d] += a * rr
                k["ful_new"][d] += a * rr * o.cost_to_fulfill
            gap = (d - pays[i - 1][0]) if i else 30
            nxt = pays[i + 1][0] if i + 1 < len(pays) else d + max(gap, 1)
            k["active"][d:min(nxt, n)] += a / first
        if o.refund_rate > 0 and o.refund_period < n:
            k["refunded"][o.refund_period] += o.refund_rate
            k["refund_cost"][o.refund_period] += o.refund_rate * pays[0][1] * rr
        return k

    P, L = o.price, max(int(o.contract_length), 1)
    p_ren = o.renewal_price
    if existing:
        # Existing customers start on a renewal: renewal price and costs, no sales cost.
        _spread(k["rev_ren"], 0, o.renewal_time_to_collect, p_ren * rr)
        _spread(k["cash_ren"], 0, o.renewal_time_to_collect, p_ren * rr)
        _spread(k["ful_ren"], 0, L, p_ren * o.renewal_cost_to_fulfill)
        k["active"][:] += 1.0
        if L < n:
            k["churned"][L] += o.churn_rate
            k["active"][L:] -= o.churn_rate
        renewing = 1.0 - o.churn_rate
    else:
        k["rev_new"][0] = P * rr
        _spread(k["cash_new"], 0, o.time_to_collect, P * rr)
        k["sell_new"][0] = P * o.cost_to_sell
        _spread(k["ful_new"], 0, L, P * o.cost_to_fulfill)
        k["active"][:] += 1.0
        rp = int(o.refund_period)
        if o.refund_rate > 0 and rp < n:
            k["refunded"][rp] += o.refund_rate
            k["refund_cost"][rp] += o.refund_rate * P * rr
            k["active"][rp:] -= o.refund_rate
        if L < n:
            ch = (1.0 - o.refund_rate) * o.churn_rate
            k["churned"][L] += ch
            k["active"][L:] -= ch
        renewing = (1.0 - o.churn_rate) * (1.0 - o.refund_rate)

    r = L
    while r < n and renewing > 1e-9:
        k["renewed"][r] += renewing
        _spread(k["rev_ren"], r, o.renewal_time_to_collect, renewing * p_ren * rr)
        _spread(k["cash_ren"], r, o.renewal_time_to_collect, renewing * p_ren * rr)
        _spread(k["sell_ren"], r, o.renewal_time_to_collect, renewing * p_ren * o.renewal_cost_to_sell)
        _spread(k["ful_ren"], r, L, renewing * p_ren * o.renewal_cost_to_fulfill)
        if r + L < n:
            lost = renewing * (1.0 - o.renewal_rate_of_renewals)
            k["churned"][r + L] += lost
            k["active"][r + L:] -= lost
        renewing *= o.renewal_rate_of_renewals
        r += L
    return k


def offer_economics(o: Offer, horizon: int = 7300) -> dict:
    """Per-sale numbers for one offer over a long horizon (20 years by default)."""
    k = offer_kernel(o, horizon)
    cash = k["cash_new"] + k["cash_ren"]
    expected_value = float(cash.sum() - k["refund_cost"].sum())
    ltv = float(expected_value - k["ful_new"].sum() - k["ful_ren"].sum() - k["sell_ren"].sum())
    if o.billing == "schedule":
        points = [[int(d), float(a) * o.realization_rate] for d, a in sorted(o.payments or [])]
    else:
        nz = np.nonzero(cash > 1e-9)[0]
        last = int(nz.max()) if len(nz) else 0
        points = [[b, float(cash[b:b + 30].sum())] for b in range(0, last + 1, 30) if cash[b:b + 30].sum() > 1e-6]
        points = points[:120]
    return {"expected_value": expected_value, "ltv": ltv, "points": points,
            "expected_renewals": float(k["renewed"].sum())}


def offer_ltv(o: Offer, years: float = 5.0, discount_rate: float = 0.0, transaction_fee: float = 0.0) -> float:
    """Contribution per sale over `years`, discounted, net of delivery, refunds, renewal selling and payment fees."""
    H = max(int(round(years * 365)), 1)
    k = offer_kernel(o, H)
    net = (k["cash_new"] + k["cash_ren"]) * (1.0 - transaction_fee) - k["ful_new"] - k["ful_ren"] \
        - k["refund_cost"] - k["sell_ren"]
    d = (1.0 + discount_rate) ** (-np.arange(H) / 365.0)
    return float((net * d).sum())


# ── Results ────────────────────────────────────────────────────────────

CHANNEL_GROUPS = {
    "Paid Advertising": "inbound", "Inbound": "inbound", "Paid": "inbound",
    "Paid Search": "inbound", "Paid Social": "inbound",
    "Outbound Prospecting": "outbound", "Outbound": "outbound",
    "Cold Email": "outbound", "Cold Calling": "outbound", "LinkedIn Outreach": "outbound",
    "Multichannel Outbound": "outbound",
    "Organic": "organic", "Content": "organic", "SEO": "organic", "Reviews": "organic", "Community": "organic",
    "Viral": "viral", "Referral": "viral",
}


@dataclass
class EventFunnel:
    title: str
    channel: str
    driver: str
    spend_per_day: float
    impressions: float
    views: float
    leads: float
    sales: float
    cost_per_lead: float
    cac: float  # marketing + sales cost per sale, over the whole run
    expected_value: float
    ltv: float
    ev_to_cac: float
    ltv_to_cac: float
    days_active: int
    total_spend: float
    total_sales: float
    cash_conversion_cycle: int


@dataclass
class StateResult:
    days: np.ndarray
    spend: np.ndarray
    impressions: np.ndarray
    views: np.ndarray
    leads: np.ndarray
    leads_inbound: np.ndarray
    leads_outbound: np.ndarray
    leads_organic: np.ndarray
    new_customers_inbound: np.ndarray
    new_customers_outbound: np.ndarray
    new_customers_organic: np.ndarray
    new_customers_viral: np.ndarray
    new_customers_other: np.ndarray
    new_customers_total: np.ndarray
    cumulative_customers: np.ndarray
    active_customers: np.ndarray
    churned_customers: np.ndarray
    renewed_customers: np.ndarray
    refunded_customers: np.ndarray
    revenue_new: np.ndarray
    revenue_renewal: np.ndarray
    revenue_total: np.ndarray
    cash_collected_new: np.ndarray
    cash_collected_renewal: np.ndarray
    cash_collected_total: np.ndarray
    revenue_by_offer: dict
    cost_marketing: np.ndarray
    cost_sales: np.ndarray
    cost_fulfillment: np.ndarray
    cost_fixed: np.ndarray
    cost_fixed_employee: np.ndarray
    cost_transaction_fees: np.ndarray
    cost_interest: np.ndarray
    cost_refunds: np.ndarray
    cost_total: np.ndarray
    gross_profit: np.ndarray
    ebitda: np.ndarray
    ebit: np.ndarray
    tax: np.ndarray
    net_income: np.ndarray
    free_cash_flow: np.ndarray
    cumulative_fcf: np.ndarray
    cash_balance: np.ndarray
    discount_factor: np.ndarray
    dcf: np.ndarray
    cum_dcf: np.ndarray
    funnels: list
    event_sales: list
    event_cost: list
    active_by_offer: dict = field(default_factory=dict)
    cost_fixed_sm: np.ndarray = None  # fixed expenses flagged sales & marketing
    cost_sales_new: np.ndarray = None  # cost to sell on new sales only (renewal selling cost excluded)
    sales_by_offer: dict = field(default_factory=dict)
    upgrades_in: dict = field(default_factory=dict)
    upgrades_out: dict = field(default_factory=dict)
    # financing
    financing_in: np.ndarray = None  # cash received per day (equity, grants, loans)
    loan_repayment: np.ndarray = None  # principal (and capitalised interest) repaid per day
    loan_interest: np.ndarray = None  # interest on financing loans per day (inside cost_interest)
    debt_outstanding: np.ndarray = None  # starting debt + financing loans outstanding
    shares_outstanding: np.ndarray = None
    cash_balance_operating: np.ndarray = None  # cash balance without financing (as before)
    cost_cogs: np.ndarray = None  # cost to fulfil + transaction fees (cost of goods sold)
    cash_flow_before_tax: np.ndarray = None


def simulate_financing(state: State, T: int) -> dict:
    """Daily financing cash flows, debt and share count from the financing events."""
    fin_in = np.zeros(T)
    repay = np.zeros(T)
    interest = np.zeros(T)
    loan_bal = np.zeros(T)
    shares = np.full(T, float(max(int(state.shares), 1)))
    for f in state.financing or []:
        d0 = int(f.day)
        amt = float(f.amount or 0.0)
        if amt <= 0 or d0 < 0 or d0 >= T:
            continue
        fin_in[d0] += amt
        if f.kind == "equity":
            n = float(f.shares_issued or 0.0)
            if n <= 0 and float(f.valuation or 0) > 0:
                n = amt / (float(f.valuation) / shares[d0])  # price per share = pre-money / shares before
            if n > 0:
                shares[d0:] += n
        elif f.kind == "loan":
            # Interest is a cost on the day it accrues (it reaches cash through net income).
            # Repayment is the principal, in equal daily amounts after the grace period.
            # With compounding the accrued interest is added to the balance, so later
            # interest is charged on it too; the balance shown includes it.
            r = float(f.interest_rate or 0.0) / 365.0
            m = max(int(f.maturity_days), 1)
            g = min(max(int(f.grace_days), 0), m - 1)
            principal = amt
            bal = amt
            p = amt / (m - g)
            for d in range(d0, min(d0 + m - 1, T - 1) + 1):  # m days: t = 0 .. m-1, m-g repayments
                i = bal * r
                interest[d] += i
                if f.compounding:
                    bal += i
                t = d - d0
                if t >= g:
                    repay[d] += p
                    principal -= p
                    bal -= p
                loan_bal[d] += max(principal, 0.0)
    debt = loan_bal + float(state.debt or 0.0)
    return {"financing_in": fin_in, "loan_repayment": repay, "loan_interest": interest,
            "debt_outstanding": debt, "shares_outstanding": shares}


def _window(start, end, T):
    s, e = max(int(start), 0), min(int(end), T - 1)
    return (s, e) if e >= s else None


def _event_rates(ev: MarketingEvent) -> tuple:
    """Per active day: cost, reached (impressions / contacts / visits), engaged, leads, sales."""
    if ev.driver == "outbound":
        c = ev.contacts_per_day
        if ev.mailboxes > 0 and ev.sends_per_mailbox_per_day > 0:
            c = min(c, ev.mailboxes * ev.sends_per_mailbox_per_day)
        cost = c * ev.cost_per_contact + (ev.people_cost_per_month + ev.tools_cost_per_month) / 30.0
        replies = c * ev.reply_rate
        meetings = replies * ev.positive_reply_rate * ev.meeting_rate
        return cost, c, replies, meetings, meetings * ev.close_rate
    if ev.driver == "team":
        cost = ev.headcount * ev.salary_per_month / 30.0
        imp = ev.headcount * ev.contacts_per_head_per_month / 30.0
        vw = imp * ev.ctr
    elif ev.driver == "volume":
        cost = ev.spend_per_day
        imp = vw = ev.views_per_day
    elif ev.driver == "viral":
        return 0.0, 0.0, 0.0, 0.0, 0.0
    else:
        cost = ev.spend_per_day
        if ev.cost_per_click > 0:
            vw = ev.spend_per_day / ev.cost_per_click
            imp = vw / ev.ctr if ev.ctr > 0 else vw
        else:
            imp = (ev.spend_per_day / ev.cpm * 1000.0) if ev.cpm > 0 else 0.0
            vw = imp * ev.ctr
    ld = vw * ev.lead_to_view
    return cost, imp, vw, ld, ld * ev.sale_to_lead


def simulate(state: State) -> StateResult:
    T = max(int(state.time_span), 2)
    days = np.arange(T)
    offers = {o.name: o for o in state.offers}
    kernels = {name: offer_kernel(o, T) for name, o in offers.items()}

    n_ev = len(state.events)
    spend = np.zeros(T)
    impressions = np.zeros(T)
    views = np.zeros(T)
    leads = np.zeros(T)
    leads_by_group = {g: np.zeros(T) for g in ("inbound", "outbound", "organic")}
    base_sales = np.zeros((n_ev, T))
    ev_spend = np.zeros((n_ev, T))

    for i, ev in enumerate(state.events):
        w = _window(ev.start_day, ev.end_day, T)
        if w is None or ev.driver == "viral":
            continue
        s, e = w
        cost, imp, vw, ld, sl = _event_rates(ev)
        ev_spend[i, s:e + 1] += cost
        spend[s:e + 1] += cost
        impressions[s:e + 1] += imp
        views[s:e + 1] += vw
        leads[s:e + 1] += ld
        g = CHANNEL_GROUPS.get(ev.channel)
        if g in leads_by_group:
            leads_by_group[g][s:e + 1] += ld
        delay = int(ev.time_to_market) + int(ev.sales_cycle_days)
        if s + delay < T:
            base_sales[i, s + delay:min(e + delay, T - 1) + 1] += sl

    # Day loop: viral sales depend on active customers; the market cap on both
    sales = np.zeros((n_ev, T))
    active = np.zeros(T)
    sales_by_offer = {name: np.zeros(T) for name in offers}
    active_by_offer = {name: np.zeros(T) for name in offers}
    book = {k: v for k, v in existing_book(state).items() if k in offers}
    ex_total = existing_total(state)
    ups = [u for u in state.upgrades if u.monthly_rate > 0 and u.from_offer in offers
           and u.to_offer in offers and u.from_offer != u.to_offer]
    ex_kernels = {}
    for name in set(book) | {u.from_offer for u in ups} | {u.to_offer for u in ups}:
        ex_kernels[name] = offer_kernel(offers[name], T, existing=True)
    for name, n in book.items():
        active += n * ex_kernels[name]["active"]
        active_by_offer[name] += n * ex_kernels[name]["active"]
    mixes = [event_mix(ev) for ev in state.events]
    up_in = {name: np.zeros(T) for name in offers}
    up_out = {name: np.zeros(T) for name in offers}

    viral_idx = [i for i, ev in enumerate(state.events) if ev.driver == "viral"]
    tam = float(state.total_addressable_market or 0)
    for d in range(T):
        today = base_sales[:, d].copy()
        for i in viral_idx:
            ev = state.events[i]
            delay = int(ev.time_to_market) + int(ev.sales_cycle_days)
            src = d - delay
            if src >= 0 and ev.start_day <= src <= ev.end_day:
                L = 0.0
                for oname, share in mixes[i].items():
                    o = offers.get(oname)
                    L += share * (max(int(o.contract_length), 1) if (o and o.billing == "contract") else 365)
                L = max(L, 1.0)
                base_active = active[src] if src > 0 else ex_total
                today[i] = base_active * (ev.invites_per_customer / L) * ev.invite_conversion
        total = today.sum()
        if tam > 0 and total > 0 and d > 0:
            headroom = tam - active[d - 1]
            if headroom <= 0:
                today[:] = 0.0
            elif total > headroom:
                today *= headroom / total
        sales[:, d] = today
        for i, ev in enumerate(state.events):
            if today[i] <= 0:
                continue
            for oname, share in mixes[i].items():
                if oname in kernels:
                    n = today[i] * share
                    sales_by_offer[oname][d] += n
                    active[d:] += n * kernels[oname]["active"][:T - d]
                    active_by_offer[oname][d:] += n * kernels[oname]["active"][:T - d]
        for u in ups:
            if u.start_day <= d <= u.end_day:
                n = max(active_by_offer[u.from_offer][d], 0.0) * u.monthly_rate / 30.0
                if n > 0:
                    ka, kb = ex_kernels[u.from_offer]["active"][:T - d], ex_kernels[u.to_offer]["active"][:T - d]
                    active_by_offer[u.from_offer][d:] -= n * ka
                    active_by_offer[u.to_offer][d:] += n * kb
                    active[d:] += n * (kb - ka)
                    up_out[u.from_offer][d] += n
                    up_in[u.to_offer][d] += n
        if tam > 0:
            active[d] = min(active[d], tam)
    active = np.maximum(active, 0.0)

    # Everything else is linear in sales: convolve each offer's per-sale curves
    agg = {f: np.zeros(T) for f in KERNEL_FIELDS}
    revenue_by_offer = {}
    for name, sb in sales_by_offer.items():
        kern = kernels[name]
        if sb.any():
            for f in KERNEL_FIELDS:
                if f != "active":
                    agg[f] += np.convolve(sb, kern[f])[:T]
            revenue_by_offer[name] = np.convolve(sb, kern["cash_new"] + kern["cash_ren"])[:T]
        else:
            revenue_by_offer[name] = np.zeros(T)
    for name, n in book.items():
        ek = ex_kernels[name]
        for f in KERNEL_FIELDS:
            if f != "active":
                agg[f] += n * ek[f]
        revenue_by_offer[name] = revenue_by_offer[name] + n * (ek["cash_new"] + ek["cash_ren"])
    for name in offers:
        if not (up_in[name].any() or up_out[name].any()):
            continue
        ek = ex_kernels[name]
        flow = up_in[name] - up_out[name]
        for f in KERNEL_FIELDS:
            if f != "active":
                agg[f] += np.convolve(flow, ek[f])[:T]
        revenue_by_offer[name] = revenue_by_offer[name] + np.convolve(flow, ek["cash_new"] + ek["cash_ren"])[:T]

    # Per event: sales-cost overrides and viral cost to market
    cost_marketing = spend.copy()
    sell_adjust = np.zeros(T)
    event_cost = []
    for i, ev in enumerate(state.events):
        price = sum(sh * offers[n].price for n, sh in mixes[i].items() if n in offers)
        offer_sell = sum(sh * offers[n].cost_to_sell * offers[n].price for n, sh in mixes[i].items() if n in offers)
        ev_sell = (ev.cost_to_sell_override * price) if ev.cost_to_sell_override >= 0 else offer_sell
        if ev.cost_to_sell_override >= 0:
            sell_adjust += sales[i] * (ev_sell - offer_sell)
        mk = ev_spend[i].copy()
        if ev.driver == "viral" and ev.viral_cost_to_market > 0:
            v = sales[i] * price * ev.viral_cost_to_market
            cost_marketing += v
            mk += v
        event_cost.append(mk + sales[i] * ev_sell)

    cost_fixed = np.zeros(T)
    cost_fixed_emp = np.zeros(T)
    cost_fixed_sm = np.zeros(T)
    for x in state.expenses:
        w = _window(x.start_day, x.end_day, T)
        if w is None:
            continue
        s, e = w
        row = x.amount_per_day + active[s:e + 1] / 100.0 * x.per_100_customers_per_day
        cost_fixed[s:e + 1] += row
        if x.employee:
            cost_fixed_emp[s:e + 1] += row
        if x.sales_marketing:
            cost_fixed_sm[s:e + 1] += row

    cash_new, cash_ren = agg["cash_new"], agg["cash_ren"]
    cash_total = cash_new + cash_ren
    cost_txn = cash_total * state.transaction_fee
    cost_sales = agg["sell_new"] + agg["sell_ren"] + sell_adjust
    cost_ful = agg["ful_new"] + agg["ful_ren"]
    cost_ref = agg["refund_cost"]
    fin = simulate_financing(state, T)
    cost_interest = np.full(T, state.debt * state.interest_rate / 365.0) + fin["loan_interest"]
    cost_total = cost_marketing + cost_sales + cost_ful + cost_fixed + cost_txn + cost_interest + cost_ref

    gross_profit = cash_total - (cost_ful + cost_txn)
    ebitda = gross_profit - (cost_marketing + cost_sales + cost_fixed + cost_ref)
    ebit = ebitda  # no depreciation or amortisation modelled
    if state.loss_carryforward:
        tax = np.zeros(T)
        carry = 0.0
        for d in range(T):
            x = ebit[d]
            if x <= 0:
                carry -= x
            else:
                used = min(carry, x)
                carry -= used
                tax[d] = (x - used) * state.tax_rate
    else:
        tax = np.where(ebit > 0, ebit * state.tax_rate, 0.0)
    net_income = ebit - tax - cost_interest
    fcf = net_income.copy()
    cumulative_fcf = np.cumsum(fcf)
    cash_operating = state.starting_cash - state.upfront_investment + cumulative_fcf
    cash_balance = cash_operating + np.cumsum(fin["financing_in"] - fin["loan_repayment"])

    disc = (1.0 + state.discount_rate) ** (-days / 365.0)
    dcf = fcf * disc
    cum_dcf = np.cumsum(dcf)

    by_group = {g: np.zeros(T) for g in ("inbound", "outbound", "organic", "viral", "other")}
    for i, ev in enumerate(state.events):
        g = "viral" if ev.driver == "viral" else CHANNEL_GROUPS.get(ev.channel, "other")
        by_group[g] += sales[i]
    new_total = sales.sum(axis=0) if n_ev else np.zeros(T)

    econ_cache = {name: dict(offer_economics(o), ltv=offer_ltv(o, state.ltv_years, state.discount_rate,
                                                                 state.transaction_fee))
                  for name, o in offers.items()}
    funnels = []
    for i, ev in enumerate(state.events):
        econ = {"expected_value": sum(sh * econ_cache[n]["expected_value"] for n, sh in mixes[i].items() if n in econ_cache),
                "ltv": sum(sh * econ_cache[n]["ltv"] for n, sh in mixes[i].items() if n in econ_cache)}
        ttc = sum(sh * int(offers[n].time_to_collect) for n, sh in mixes[i].items() if n in offers)
        w = _window(ev.start_day, ev.end_day, T)
        n_days = 0 if w is None else w[1] - w[0] + 1
        cost, imp, vw, ld, sl = _event_rates(ev)
        if ev.driver == "viral":
            sl = float(sales[i].sum()) / max(n_days, 1)
        tot_sales = float(sales[i].sum())
        tot_cost = float(event_cost[i].sum())
        cac = tot_cost / tot_sales if tot_sales > 0 else float("inf")
        funnels.append(EventFunnel(
            title=ev.title, channel=ev.channel, driver=ev.driver, spend_per_day=cost,
            impressions=imp, views=vw, leads=ld, sales=sl,
            cost_per_lead=(cost / ld) if ld > 0 else float("inf"),
            cac=cac, expected_value=econ["expected_value"], ltv=econ["ltv"],
            ev_to_cac=(econ["expected_value"] / cac) if np.isfinite(cac) and cac > 0 else float("inf"),
            ltv_to_cac=(econ["ltv"] / cac) if np.isfinite(cac) and cac > 0 else float("inf"),
            days_active=n_days, total_spend=float(ev_spend[i].sum()), total_sales=tot_sales,
            cash_conversion_cycle=int(ev.time_to_market) + int(ev.sales_cycle_days) + int(round(ttc)),
        ))

    return StateResult(
        days=days, spend=spend, impressions=impressions, views=views, leads=leads,
        leads_inbound=leads_by_group["inbound"], leads_outbound=leads_by_group["outbound"],
        leads_organic=leads_by_group["organic"],
        new_customers_inbound=by_group["inbound"], new_customers_outbound=by_group["outbound"],
        new_customers_organic=by_group["organic"], new_customers_viral=by_group["viral"],
        new_customers_other=by_group["other"], new_customers_total=new_total,
        cumulative_customers=np.cumsum(new_total) + ex_total,
        active_customers=active, churned_customers=np.cumsum(agg["churned"]),
        renewed_customers=np.cumsum(agg["renewed"]), refunded_customers=np.cumsum(agg["refunded"]),
        revenue_new=agg["rev_new"], revenue_renewal=agg["rev_ren"], revenue_total=agg["rev_new"] + agg["rev_ren"],
        cash_collected_new=cash_new, cash_collected_renewal=cash_ren, cash_collected_total=cash_total,
        revenue_by_offer=revenue_by_offer,
        cost_marketing=cost_marketing, cost_sales=cost_sales, cost_fulfillment=cost_ful,
        cost_fixed=cost_fixed, cost_fixed_employee=cost_fixed_emp, cost_transaction_fees=cost_txn,
        cost_interest=cost_interest, cost_refunds=cost_ref, cost_total=cost_total,
        gross_profit=gross_profit, ebitda=ebitda, ebit=ebit, tax=tax, net_income=net_income,
        free_cash_flow=fcf, cumulative_fcf=cumulative_fcf, cash_balance=cash_balance,
        discount_factor=disc, dcf=dcf, cum_dcf=cum_dcf,
        funnels=funnels, event_sales=list(sales), event_cost=event_cost,
        active_by_offer={k: np.maximum(v, 0.0) for k, v in active_by_offer.items()},
        sales_by_offer=sales_by_offer, upgrades_in=up_in, upgrades_out=up_out,
        cost_fixed_sm=cost_fixed_sm, cost_sales_new=agg["sell_new"] + sell_adjust,
        financing_in=fin["financing_in"], loan_repayment=fin["loan_repayment"], loan_interest=fin["loan_interest"],
        debt_outstanding=fin["debt_outstanding"], shares_outstanding=fin["shares_outstanding"],
        cash_balance_operating=cash_operating, cost_cogs=cost_ful + cost_txn, cash_flow_before_tax=ebit - cost_interest,
    )


# ── Intervention helpers ───────────────────────────────────────────────

def clone_state(s: State, title: str) -> State:
    c = state_from_dict(state_to_dict(s))
    c.id = uuid.uuid4().hex[:10]
    c.title = title
    c.created = _now()
    c.source = f"clone:{s.id}"
    return c


def split_row(rows: list, index: int, at_day: int, suffix: str = " (After Intervention)") -> list:
    """End row `index` on at_day - 1 and insert a copy that starts on at_day."""
    rows = list(rows)
    old = rows[index]
    if not (old.start_day < at_day <= old.end_day):
        raise ValueError(f"Day {at_day} is outside {old.start_day}-{old.end_day}")
    new = copy.deepcopy(old)
    old.end_day = at_day - 1
    new.start_day = at_day
    if hasattr(new, "title") and suffix and not new.title.endswith(suffix):
        new.title += suffix
    rows.insert(index + 1, new)
    return rows


# ── Example: Higher EdTech ─────────────────────────────────────────────

def example_higher_edtech() -> tuple:
    """Before/after states of an EdTech company (an example from one of Kozmin's videos).

    $100/month offer. 9.604% monthly churn gives an expected value of $761.01
    over 13 payments; 5.492% gives $947.13 (the two numbers on screen).
    """
    gb = {"kind": "subscription", "price": 100.0, "every_days": 30, "churn": 0.09604, "periods": 13}
    ga = {"kind": "subscription", "price": 100.0, "every_days": 30, "churn": 0.05492, "periods": 13}
    offer = Offer("Mid-Market Offer", billing="schedule", price=100.0, payments=build_schedule(gb), generator=gb)
    before = State(
        title="Higher EdTech - State 1 (Before Intervention)",
        description="EdTech, $100/month offer, paid traffic. QA by 3-4 engineers.",
        offers=[offer],
        events=[MarketingEvent("Paid Funnel", "Mid-Market Offer", "Paid Advertising", "spend", 0, 700,
                               spend_per_day=2000.0, cpm=25.0, ctr=0.02, lead_to_view=0.1, sale_to_lead=0.07,
                               sales_cycle_days=14)],
        expenses=[FixedExpense("Customer Support Agents", "", 0, 730, 98.6),
                  FixedExpense("QA Engineers", "3-4 QA Engineers", 0, 730, 158.0),
                  FixedExpense("Developers", "10-15 developers", 0, 730, 841.0, employee=True)],
    )
    after = clone_state(before, "Higher EdTech - State 2 (After Intervention)")
    after.source = ""
    after.description = ("Same business with QA AI: fewer bugs lower churn and CPM from day 181; "
                         "QA team shrinks from day 91.")
    after.offers.append(Offer("Mid-Market Offer (After Intervention)", billing="schedule", price=100.0,
                              payments=build_schedule(ga), generator=ga))
    after.events = split_row(after.events, 0, 181)
    after.events[1].offer = "Mid-Market Offer (After Intervention)"
    after.events[1].cpm = 20.0
    after.expenses = split_row(after.expenses, 1, 91)
    after.expenses[2].description = "1-2 QA Engineers"
    after.expenses[2].amount_per_day = 55.0
    return before, after
