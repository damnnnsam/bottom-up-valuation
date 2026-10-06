# Bottom-up valuation

Value a business from the metrics its marketing produces every day: CPM, click-through rate, contact to lead rate, meeting rate, close rate, price, churn, time to collect. The model simulates the business day by day from those inputs, discounts the cash flows, and puts a number on the whole thing. Change one input, and you see what it is worth.

It runs as a small Streamlit app.

```
pip install -r requirements.txt
streamlit run main.py
```

Two example clients are included. Pick one in the sidebar.

**Live mode** is for building a model with someone, for example on a sales call: every input sits in the left sidebar in plain units (%, per month, days), and the value, cash, CAC and charts on the right update as you type, with the change against the saved version. Open any state and click Live. "Save as new state" turns the current numbers into a second state and a comparison.

## Why bottom-up

A business is a set of offers, and a set of channels that bring customers to those offers, and a set of costs for running it. Everything else follows. A top-down model starts from revenue and a growth rate and works down to a margin. This model starts from a channel row that says "300 contacts per day at $0.35 each, 4% contact to lead, 30% of leads interested, 60% of those take a meeting, 22% close, 30-day sales cycle" and works up to cash, profit and value.

Two reasons to do it this way:

1. The inputs are the numbers you can actually measure and change. An ad platform tells you CPM and CTR today. Your sending tool tells you the contact to lead rate today. A growth rate is a result, not a lever.
2. Timing is money. Spend goes out on day 1, the lead arrives after the time to market, the sale closes after the sales cycle, the cash arrives after the time to collect, the refund window closes later still. Two businesses with the same unit economics and different timing need different amounts of cash. A monthly or quarterly model cannot see that; a daily one can.

Every marketing row is marked **validated** (the rates come from measured data) or **hypothesis**. A state that is 0 of 7 validated is a plan. A state that is 7 of 7 is a business.

## The primitives

A **state** is one version of the business. You compare states: current vs plan, CPM 100 vs CPM 50, with outbound vs without.

| Primitive | What it holds |
|---|---|
| **Offer** | Price, realization rate, cost to sell, cost to fulfil, time to collect, refund period and rate, contract length, churn, renewal price and costs, renewal rate of renewals. Or a payment schedule (day, amount) for anything that doesn't fit a contract. |
| **Marketing event** | One channel for one day window. Paid: spend per day with CPM and CTR, or cost per click. Outbound: contacts per day, cost per contact, people and tools, contact to lead, positive reply, meeting and close rates. Organic: visits per day. Viral: invites per customer and invite conversion. Each row has time to market, sales cycle, an optional offer mix across tiers, and the validated flag. |
| **Fixed expense** | Amount per day for a day window, plus an amount per 100 active customers. Flags for employee and for sales & marketing (counts toward fully loaded CAC). |
| **Financing event** | Equity (amount, pre-money valuation or shares issued; dilutes), grant, or loan (interest, grace, maturity, compounding). Changes cash, debt and share count. Does not change the discounted cash flow, except through loan interest. |
| **Upgrade** | A monthly share of active customers on one offer moves to another. Expansion revenue between tiers. |

Day windows include both ends. Splitting a row at a day ("ends day 180, copy starts day 181") is how you model an intervention: same business, one input changes on one day.

## What comes out

Per state, at any chosen day:

- Unit economics: fully loaded CAC (sales & marketing cost, lagged by the time to sale, over the trailing 12 months of new customers), CAC ratio, CAC payback in months, LTV over a chosen horizon discounted and net of delivery, LTV : CAC, cash payback in days.
- Cash: cash needed, lowest cash balance and when, time to profitability, time to self-fund.
- Valuation: total discounted cash flow after tax, terminal value, enterprise and equity value, share price. An EBITDA multiple version for comparison.
- Every daily series the engine produces (customers, funnel, revenue, each cost line, margin, profit, cash, financing, discounted cash flow) as daily, monthly or cumulative charts.
- A monthly, quarterly or yearly statement, and a daily CSV.

Per comparison: the metrics side by side with the change, and any series as values, absolute difference and percent difference against the first state, marked at the compare day. Plus a share link that shows the comparison read-only.

## Example: what CPM does to value

Same offer, same funnel, same costs. Three states with CPM at $120, $100 and $50. At $120 the discounted cash flow goes negative and stays there: stop. At $100 it hovers around zero: nothing is happening. At $50 the business is worth something: run it. Build it in five minutes: one state, clone it twice, change one number in each, create a comparison.

## Layout

```
main.py              Streamlit entry point
states_app.py        pages: client home, state report, editor, comparison, share view
engine/events.py     the model: data classes and the daily simulation
engine/state_metrics.py   KPIs and valuation from a simulation result
ui/graphs.py         series registry and chart views
ui/corporate.py      one design: styles, tables, chart template
store/               JSON files under data/clients/<client>/ (or a GitHub repo via st.secrets on Streamlit Cloud)
examples/            script that builds the Tiered SaaS example
data/clients/example-*   the two example clients
```

Your own clients under `data/clients/` are git-ignored; only `example-*` folders are tracked.

## Credits

The row-and-day-window structure (offers, marketing events with start and end days, fixed expenses, financing events, state comparisons with difference charts) follows the comparison tool Nick Kozmin of Salesprocess.io shows in his videos. The engine, the metrics and the app are an independent implementation. The Higher EdTech example reproduces the numbers from one of those videos.

MIT license.
