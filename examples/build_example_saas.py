"""Builds the "Example: Tiered SaaS" client: a current state, a plan that adds
outbound funded by a loan, and the comparison between them.

    PYTHONPATH=. python examples/build_example_saas.py

All numbers are invented. The point is the structure: four price tiers with
upgrades between them, an organic channel that grows year by year, a product
widget that brings referrals, a sales and marketing share of fixed costs for
fully loaded CAC, and a plan state that is the current state plus outbound
rows, a hire and a loan."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.events import State, Offer, MarketingEvent, FixedExpense, Upgrade, FinancingEvent, clone_state, simulate
from store.client import create_client, load_client_meta
from store.states import Comparison, save_state, save_comparison

CLIENT = "example-saas"
T = 1460  # four years
MIX = {"Starter": 40, "Team": 40, "Business": 17, "Enterprise": 3}  # share of new sales per tier


def tier(name, price, renewal, churn):
    """Monthly subscription: 30-day contract that renews at (1 - churn)."""
    return Offer(name=name, billing="contract", price=price, realization_rate=0.97, cost_to_fulfill=0.18,
                 contract_length=30, churn_rate=churn, renewal_price=renewal, renewal_cost_to_fulfill=0.18,
                 renewal_rate_of_renewals=1 - churn)


def organic(title, start, end, visits_per_day, validated=False):
    return MarketingEvent(title=title, offer="Team", offer_mix=dict(MIX), channel="SEO", driver="volume",
                          start_day=start, end_day=end, spend_per_day=80.0, views_per_day=visits_per_day, ctr=1.0,
                          lead_to_view=0.01, sale_to_lead=0.09, sales_cycle_days=14, validated=validated,
                          validation_note="Analytics, last 8 months" if validated else "")


current = State(
    title="Tiered SaaS - Current State",
    description="A bootstrapped B2B SaaS at about $60K MRR with four monthly tiers, all new customers from search, "
                "content and a referral widget. Numbers are invented for the example.",
    time_span=T, projection_period=T, discount_rate=0.12, tax_rate=0.25, perpetual_growth_rate=0.02,
    ebitda_multiple=12.0, ebitda_projection_period=1825, shares=1_000_000, starting_cash=180_000,
    transaction_fee=0.035,
    existing_by_offer={"Starter": 210, "Team": 150, "Business": 45, "Enterprise": 8},
    offers=[tier("Starter", 49, 49, 0.06), tier("Team", 149, 159, 0.03), tier("Business", 399, 429, 0.02),
            tier("Enterprise", 1200, 1300, 0.012)],
    events=[
        organic("Search and content (year 1)", 0, 364, 600, validated=True),
        organic("Search and content (year 2)", 365, 729, 750),
        organic("Search and content (year 3)", 730, 1094, 920),
        organic("Search and content (year 4)", 1095, 1459, 1100),
        MarketingEvent(title="Referral widget in customer apps", offer="Team", offer_mix=dict(MIX), channel="Viral",
                       driver="viral", start_day=0, end_day=T - 1, invites_per_customer=0.3, invite_conversion=0.07,
                       sales_cycle_days=14, validation_note="Share of signups with a referral source, assumed"),
    ],
    expenses=[
        FixedExpense("Core team", "Product, engineering, support, admin: 7 people.", 0, T - 1, 38_000 / 30,
                     employee=True),
        FixedExpense("Growth share of the team", "About 1.5 people's time on content, search and the referral program.", 0, T - 1,
                     9_000 / 30, employee=True, sales_marketing=True),
        FixedExpense("Hiring as the base grows", "One support or success hire per ~300 more customers.", 0, T - 1,
                     0.0, per_100_customers_per_day=1_500 / 30, employee=True),
        FixedExpense("Tools, office, G&A", "", 0, T - 1, 4_500 / 30),
    ],
    upgrades=[
        Upgrade("Starter", "Team", 0.015, 0, T - 1, "Single users adding teammates."),
        Upgrade("Team", "Business", 0.012, 0, T - 1, "Teams needing the advanced features."),
        Upgrade("Business", "Enterprise", 0.004, 0, T - 1, "SSO, invoicing, SLA."),
    ],
)
current.existing_customers = float(sum(current.existing_by_offer.values()))
current.existing_customers_offer = "Team"

plan = clone_state(current, "Tiered SaaS - Outbound Plan")
plan.source = ""
plan.description = ("The current state plus a volume-based outbound channel from day 90, one person to run it, and a "
                    "$250K loan on day 60 to fund the first year. Everything in the outbound rows is a hypothesis "
                    "until the first 90 days of sending are measured.")
plan.events += [
    MarketingEvent(title="Outbound: companies 20-200 staff", offer="Team",
                   offer_mix={"Team": 55, "Business": 40, "Enterprise": 5}, channel="Multichannel Outbound",
                   driver="outbound", start_day=90, end_day=T - 1, contacts_per_day=300, cost_per_contact=0.35,
                   people_cost_per_month=7_000, tools_cost_per_month=900, reply_rate=0.04, positive_reply_rate=0.30,
                   meeting_rate=0.60, close_rate=0.22, time_to_market=10, sales_cycle_days=30,
                   validation_note="Reply and meeting rates from comparable campaigns, not yet measured here"),
    MarketingEvent(title="Outbound: enterprise, SDR-led", offer="Enterprise", channel="Cold Email",
                   driver="outbound", start_day=120, end_day=T - 1, contacts_per_day=40, cost_per_contact=1.20,
                   people_cost_per_month=5_500, tools_cost_per_month=400, reply_rate=0.05, positive_reply_rate=0.35,
                   meeting_rate=0.65, close_rate=0.15, time_to_market=14, sales_cycle_days=75,
                   validation_note="Assumed"),
]
plan.financing = [
    FinancingEvent("Working capital loan", "loan", 60, 250_000, interest_rate=0.07, maturity_days=1095, grace_days=180,
                   terms="7% fixed, 6 months grace, repaid over 3 years"),
]
plan.expenses.append(FixedExpense("Head of Growth", "Runs outbound, content and the funnel.", 60, T - 1, 9_000 / 30,
                                  employee=True, sales_marketing=True))

if __name__ == "__main__":
    if load_client_meta(CLIENT) is None:
        create_client(CLIENT, "Example: Tiered SaaS", "B2B SaaS",
                      "Invented numbers. A current state, a plan that adds outbound funded by a loan, and the comparison.")
    for s in (current, plan):
        r = simulate(s)
        print(f"{s.title}: MRR month 1 {r.cash_collected_total[:30].sum():,.0f}, "
              f"month 12 {r.cash_collected_total[330:360].sum():,.0f}, total DCF {r.cum_dcf[-1]:,.0f}")
        save_state(CLIENT, s)
    c = Comparison(title="Tiered SaaS - Current vs Outbound Plan", state_ids=[current.id, plan.id],
                   description="What the outbound plan adds over four years, if the hypothesis rows hold.",
                   compare_day=1095, intervention_label="a volume-based outbound channel",
                   target_label="B2B SaaS companies")
    save_comparison(CLIENT, c)
    print("saved client", CLIENT, "comparison", c.id)
