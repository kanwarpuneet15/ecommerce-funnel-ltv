# CV & Interview Positioning

**Honesty rule:** this is a portfolio project on **synthetic data**. Never write "increased revenue by X%" or "saved ₹Y". Nothing was deployed at a real company. Describe what *you built and found*, and the size of the *modelled* opportunity, labelled as such. Every number below was measured in this project; the source is in brackets.

## Measured facts you can safely quote
| Fact | Source |
|---|---|
| ~4M raw events, 1.14M sessions, 33.5k orders, 20.3k customers, 33 months | generator / DQ report |
| 14 data-quality issues detected and resolved; 29 automated SQL tests + 12 Python tests | `docs/data_quality_report.md`, `sql/tests`, `tests/` |
| 13 business-question SQL queries (window functions, cohorts, diff-in-diff, percentiles) | `sql/analysis/` |
| Paid Social: 29% of customers, 16.6% 12-month repeat vs 31.2% (Paid Search); LTV:CAC 1.05× vs 1.64× | `07_channel_quality_ltv_cac.sql` |
| Marginal CAC of the 2025 Meta scale-up ₹1,250 vs ₹1,069 12-month margin LTV | `08_paid_social_scale_up.sql` |
| Checkout redesign effect +9.6 pp (95% CI 6.6–12.7) via diff-in-diff; true planted effect +8 pp | `05_...diff_in_diff.sql`, generator doc |
| Predictive LTV: holdout error cut from +48% (BG/NBD) to +13% (segmented MBG/NBD) | notebook 04 |
| Modelled opportunity: +4 pp mobile checkout ≈ ₹13L net revenue / yr (scenario) | notebook 02 |
| SQL-vs-pandas reconciliation caught a day-boundary bug in LTV windows | `tests/test_sql_vs_python.py` |

## Resume bullets: pick ONE version (3–4 bullets)

**Version A: Growth / Marketing Analyst emphasis**
- Built an end-to-end funnel, cohort and LTV analysis for a D2C e-commerce business (synthetic, 4M events / 20k customers) in SQL and Python, answering whether high-volume acquisition channels bring high-value customers.
- Showed that the largest acquisition channel (Paid Social, 29% of customers) had half the 12-month repeat rate of Paid Search (17% vs 31%) and an LTV:CAC of 1.05×, and that its marginal CAC after a spend increase (₹1,250) exceeded 12-month customer margin (₹1,069).
- Measured a mobile checkout redesign at +9.6 pp completion using difference-in-differences, and sized a further checkout improvement at ~₹13L annual net revenue as an explicitly assumed scenario.
- Delivered a 5-page Power BI dashboard (39 documented DAX measures) and a prioritised impact × effort × confidence recommendation matrix.

**Version B: Business / Strategy Analyst emphasis**
- Framed a budget-allocation question for a D2C apparel business and answered it with funnel, cohort, unit-economics and LTV analysis (SQL, Python, Power BI) on a 33-month synthetic dataset.
- Found that Paid Social growth was masking unprofitable acquisition (LTV:CAC 1.05× vs 1.64× for Paid Search) and that blended retention hid a channel-mix shift. Recommended re-basing Meta bids on value and testing spend holdouts.
- Quantified opportunities as labelled scenarios (e.g. ₹13L/yr from mobile checkout) and documented limitations, data gaps and causal caveats for stakeholders.

**Version C: Analytics engineering / data-quality emphasis**
- Designed a layered SQL warehouse (raw → staging → star schema → marts) in DuckDB with 29 automated data tests, resolving 14 real-world defects including UTC/IST mixing, bot traffic, duplicate events, messy UTM attribution and identity stitching.
- Implemented fixed-horizon LTV with right-censoring controls and a predictive CLV model (MBG/NBD + Gamma-Gamma) validated on a 12-month holdout, cutting forecast error from +48% to +13%.
- Reconciled every headline metric between SQL and an independent pandas implementation, catching and fixing a day-boundary bug in LTV windows.

## GitHub repository description (≤ 350 chars)
> End-to-end e-commerce growth analytics: funnel, cohort retention, LTV & CAC on a documented synthetic D2C dataset. SQL (DuckDB) warehouse with 29 data tests, diff-in-diff experiment readout, predictive CLV (MBG/NBD + Gamma-Gamma) validated on holdout, Power BI dashboard, and prioritised recommendations.

## LinkedIn project post
> **Do the channels that bring the most customers also bring the best ones?**
>
> I built an end-to-end growth analytics project for a fictional Indian D2C apparel brand to answer that question. I simulated ~4M web events and 33k orders with realistic data problems, then worked through it like a growth analyst would:
>
> 🔧 Cleaned 14 data issues (UTC vs IST, bots, duplicate events, messy UTMs, internal test orders) in a tested SQL warehouse
> 📉 Funnel: mobile checkout was the costliest leak; a diff-in-diff read of a redesign showed +9.6 pp
> 🔁 Cohorts: Paid Social customers repeat half as often, and blended retention hid that mix shift
> 💰 LTV vs CAC: the largest channel barely broke even (1.05×), and the marginal customer from a spend increase cost more than they earned
> 🔮 Predictive LTV validated on a holdout year
>
> Because the data is synthetic, I could check that my methods recover the true effects. They did (+9.6 pp measured vs +8 pp true).
>
> Repo + dashboard: [link] · #DataAnalytics #GrowthAnalytics #SQL #PowerBI

## 30-second explanation
> "I built a growth analytics project for a D2C apparel brand to answer one question: do our biggest acquisition channels bring our most valuable customers? I cleaned about 4 million web events into a tested SQL model, then did funnel, cohort and LTV analysis. The answer was no. Paid Social brought 29% of customers, but they repeat half as often and barely pay back their acquisition cost, and the extra customers from a recent spend increase cost more than they earned in a year. I recommended re-basing that budget on value and fixing mobile checkout, which I'd measured as the biggest funnel leak."

## 2-minute explanation (structure: context → data → method → findings → recommendation → limits)
1. **Context (15s):** "A D2C apparel brand was about to set next year's budget on the assumption that the channel driving the most orders deserves the most money. I wanted to test that."
2. **Data (20s):** "No public dataset has funnel events, repeat orders, product cost and ad spend together, so I built a documented simulator calibrated to industry benchmarks and planted realistic data problems. The data is labelled synthetic everywhere, and I knew the ground truth, so I could validate my methods."
3. **Engineering (20s):** "I built a layered DuckDB warehouse with 29 data tests. I fixed things like UTC/IST mismatches, bots and messy UTM tags, and used visitor-to-user stitching to get first-touch attribution."
4. **Analysis (35s):** "Funnel: mobile checkout completion was 16 points below desktop, and a diff-in-diff showed the recent redesign added about 10 points. Cohorts: Paid Social customers repeat half as often, and blended retention hid that mix shift. LTV: I used fixed-horizon margin LTV with right-censoring control rather than ARPU × lifespan. Paid Social's LTV:CAC was 1.05× against 1.64× for search, and the marginal CAC of the recent spend increase was higher than a year of customer margin."
5. **Recommendation (20s):** "Re-base Meta on value-based bidding with a holdout test before cutting spend, keep investing in mobile checkout with A/B tests, and run a day-30-to-90 second-purchase journey."
6. **Limits (10s):** "It's synthetic data with first-touch attribution and no fulfilment costs. Real incrementality tests and cost data are the next things I'd need."
