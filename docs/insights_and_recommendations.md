# Insights & Recommendations

**Audience:** VP Growth, Performance Marketing, CRM, Product/CRO, Finance.
**Period:** data Jan 2024 – Sep 2026. "Last 12 months" = Oct 2025 – Sep 2026.
**Value measure:** product gross margin (net revenue after discounts and returns, minus the cost of goods kept), unless stated.

> **Read this first.** The data is **synthetic** (fictional brand "Threadline"; see `docs/generator_assumptions.md`).
> The numbers show what the method finds; they are not facts about a real company. Every figure below can be traced
> to a query in `sql/analysis/` or a notebook cell, and every scenario lists its assumptions.

## The one-line answer to the central question

> **Do the channels that bring the most customers also bring the most valuable ones? No.** Paid Social is our
> largest acquisition channel (29% of all customers ever acquired) and our least valuable. Its customers repeat
> half as often, and the money spent on them in the past year roughly breaks even on 12-month product margin
> and loses money once fulfilment costs are counted.

---

## Five major insights

### 1. Paid Social buys volume, not value
- **Observation:** Paid Social is the largest channel by sessions and new customers, and the weakest on every quality measure.
- **Evidence:** 36% of sessions but 1.3% session conversion (site average 3.1%). 12-month repeat rate **16.6% vs 31.2%** for Paid Search. 12-month margin LTV **₹1,069 vs ₹1,473**. LTV:CAC **1.05× vs 1.64×** (`07_channel_quality_ltv_cac.sql`). Paid Social customers are 8% of the top value decile and about 29% of the bottom half.
- **Why it matters:** CAC is about the same for both channels (₹1,021 vs ₹899), but a Paid Search customer returns about 55% more margin per rupee of CAC. Optimising Meta campaigns for "purchases" or "lowest CPA" rewards exactly the one-and-done buyers that drag LTV down.
- **Implication:** Paid Social is barely profitable on product margin (1.05×). Under illustrative fulfilment-cost assumptions it falls to **0.88×**, i.e. loss-making within 12 months.
- **Action:** Judge Paid Social on 90-day margin LTV per rupee, not CPA. Feed Meta a value-based signal (repeat customers and high-margin first orders as the optimisation event). Cap bids at the **maximum affordable CAC** (₹356 at 3× LTV:CAC on 12-month margin, or state an explicit longer payback target).

### 2. The 2025 Meta spend increase hit diminishing returns: the marginal customer costs more than they are worth
- **Observation:** Meta spend rose about 2.2× (Mar–Jun 2025). CPC rose 33% as audiences saturated.
- **Evidence:** Average CAC rose from ₹951 to ₹1,094, but the **marginal CAC of the extra 1,333 customers per year was ₹1,250**, above the ~₹1,070 12-month margin a Paid Social customer generates. The extra customers were not *worse* (90-day margin LTV ₹1,027 vs ₹972 before), just **more expensive** (`08_paid_social_scale_up.sql`).
- **Why it matters:** Average CAC hides this. Average CAC still looks "OK", while the last ₹16.7 lakh/year of spend buys customers at a loss.
- **Implication:** Scenario (assumptions: lost customers are the marginal ones; LTV as measured): cutting back to pre-ramp spend saves **₹16.7L/yr** and gives up about **₹14.2L** of 12-month margin, **net +₹2.4L/yr** on product margin, or about **+₹4.7L/yr** on contribution under the illustrative fulfilment costs. The prize isn't huge; the real point is to **stop buying unprofitable growth and redeploy the budget**.
- **Action:** Run a **spend holdout test** (e.g. reduce Meta in some states for 6–8 weeks) to measure true incremental customers before cutting, then move the freed budget to channels with headroom and higher LTV:CAC (Paid Search non-brand, affiliate partners, email capture).

### 3. Mobile checkout is the highest-value funnel fix, and the 2025 redesign proves it can be moved
- **Observation:** 81% of sessions are mobile, which converts at 2.8% vs 4.8% on desktop. The single largest device gap is the last step: **checkout → purchase is 53% on mobile vs 69% on desktop** (`04_funnel_stages.sql`).
- **Evidence:** The Aug-2025 mobile checkout redesign raised mobile completion by **+9.6 pp (95% CI 6.6–12.7)** relative to desktop (difference-in-differences, parallel pre-trends confirmed, p = 0.31 for a pre-period trend in the gap) (`05_checkout_redesign_diff_in_diff.sql`).
- **Why it matters:** A session that reaches checkout is ~10× more likely to convert than one that only views a product. Each recovered checkout is worth a full order.
- **Implication (scenario):** Closing a further 25% of the remaining mobile gap (+4 pp) ≈ **+727 orders, ₹13.3L net revenue, ₹7.2L margin per year (~5% of revenue)**. This assumes extra buyers behave like average buyers. It is arithmetic, not a forecast.
- **Action:** Continue mobile checkout work with **A/B tests**, not before/after launches: UPI intent / one-tap payment, address autofill, guest checkout, and fewer OTP steps.

### 4. Blended retention looks stable, but it is a mix of two forces
- **Observation:** 90-day repeat rate by cohort quarter looks flat at ~15–17%.
- **Evidence:** Paid Social's share of new customers rose from ~25% to ~32% after the ramp. Holding the 2024 channel mix fixed, recent cohorts would repeat **0.4–0.6 pp more** than they actually do (`13_cohort_mix_shift.sql`).
- **Why it matters:** Leadership reading a blended metric would conclude "retention is flat". In reality acquisition mix is pulling it down while within-channel retention holds up. More Paid Social will keep eroding blended retention even if CRM and product improve.
- **Action:** Report retention **by acquisition channel** and **mix-adjusted**, with Marketing owning mix and CRM/Product owning within-channel retention.

### 5. Discount-led acquisition creates low-value customers; first-order quality predicts lifetime value
- **Observation:** How a customer is acquired predicts their value more than who they are.
- **Evidence:** Customers acquired during sales are worth **₹649 vs ₹1,521** of 12-month margin (thin discounted first order, then 20% vs 29% repeat). Customers who **return an item from their first order** repeat 22% vs 29%. City tier barely matters (notebook 03 §5). Basics as a first purchase has the highest repeat rate (+6 pp vs average) but low ticket. Outerwear/Shoes first orders produce the highest LTV through order size (`12_first_category_retention.sql`).
- **Why it matters:** Sales and welcome discounts are judged on the weekend's revenue, not on the cohort they create.
- **Action:** Evaluate each sale on **cohort 90-day margin**, not GMV. Test a **welcome offer without a discount** (e.g. free returns/exchanges on the first order, or a size-fit guarantee) against the current 10% code. Add fit guidance on first purchases to reduce first-order returns.

### Supporting insights
- **Second purchase timing:** 27.5% of customers buy again within a year, median 76 days after the first order. 57% of first-year repeaters have bought by day 90. → Start the second-purchase journey around **day 30–40** and push hardest before day 90 (`11_time_to_second_purchase.sql`).
- **Value concentration:** the top 10% of customers generate ~37% of margin and the top 20% ~55%. The predictive model's VIP + High tiers (20% of customers) hold ~73% of expected next-year margin → protect them with service and early access rather than discounts (notebook 04 §5).
- **COD / RTO:** 22% of COD orders in the last 12 months were never delivered, vs 2% for prepaid (27% of COD orders in Tier-3 cities across the full period). That is ₹26L of gross order value shipped and returned, with forward and reverse logistics paid on each (`10_cod_rto_economics.sql`).

---

## Three high-confidence recommendations

| # | Recommendation | Owner | Why we're confident |
|---|---|---|---|
| R1 | **Re-base Paid Social on value, not volume.** Cap the CAC target at what 12-month margin supports, switch optimisation to value-based events, and claw back the post-ramp marginal spend after a holdout test confirms incrementality. | Performance Marketing + Finance | Consistent across four independent views: session conversion, repeat rate, fixed-horizon LTV, and the predictive model all rank Paid Social last. LTV:CAC ≈ 1×. |
| R2 | **Keep investing in mobile checkout, using A/B tests.** | Product / CRO | The DiD estimate is large with a CI clear of zero; the mechanism is visible in the funnel (largest device gap at the last step); it touches 81% of sessions. |
| R3 | **Launch a day-30 → day-90 second-purchase programme and report retention by channel (mix-adjusted).** | CRM + Analytics | The repeat-timing distribution is stable across channels and cohorts. 68% of a customer's first-year revenue comes from the first order, so converting one-time buyers into repeaters is the main lever on LTV (a repeater adds ~₹1,640 of margin in year one). |

## Opportunity matrix (impact × effort × confidence)

| Opportunity | Impact (annual, scenario) | Effort | Confidence | Priority |
|---|---|---|---|---|
| Mobile checkout improvements (A/B tested) | High: ~₹13L revenue / ₹7L margin for +4 pp | Medium (eng work) | **High** (DiD +9.6 pp precedent) | **1 — do now** |
| Re-base Paid Social to value; cut marginal spend after holdout | Medium: +₹2–5L margin net of saved spend, plus budget redeployed | Low (bidding/budget changes) | **High** on direction, Medium on size | **1 — do now** |
| Second-purchase CRM journey (day 30–90) | Low–Medium: each +1 pp in 12-month repeat rate ≈ +93 repeaters × ₹1,640 ≈ ₹1.5L margin/yr. Compounds, and is cheap | Low | Medium (causal effect needs a holdout) | **2 — next** |
| Mobile product page → cart (+1 pp) | Medium: ~₹10L revenue / ₹5.6L margin | Medium (merchandising, PDP) | Medium | **2 — next** |
| Sale strategy: judge on cohort margin; non-discount welcome offer | Medium (protects LTV; hard to size) | Low | Medium | **3 — test** |
| COD → prepaid nudges in Tier-2/3 (UPI incentive / COD fee) | Low–Medium: fewer RTOs, logistics savings | Low | Medium | **3 — test** |
| Improve Paid Social landing-page conversion (+10% rel.) | Low: ~₹3.8L revenue | Medium | Medium | 4 — later |

## Two areas where more data is needed

1. **Incrementality and true CAC.** All attribution here is first-touch (acquisition) or last-click (orders). Neither tells us how many customers would have bought anyway. Geo holdouts / conversion-lift tests and campaign-level spend are needed before large budget moves. Unpaid channels' costs (SEO, content, influencers) are missing, so their CAC is unknown, not zero.
2. **Fulfilment and cost-to-serve.** Shipping, packaging, payment-gateway and RTO logistics costs aren't in the data. LTV here is *product* margin, and the contribution view in notebook 04 uses labelled assumptions. Real 3PL and gateway invoices would turn the sensitivity into fact, which matters most for COD-heavy, return-heavy segments.

## Two risks / limitations

1. **Synthetic data, and some circularity.** The generator encodes assumptions (documented). The analysis recovers them (e.g. DiD +9.6 pp vs a planted +8 pp), which validates the *methods*, not real-world behaviour. On real data, the same pipeline would need re-validation and the conclusions could differ.
2. **Observational causality and model error.** The checkout effect is a quasi-experiment, not an A/B test. Segment differences (sale-acquired, COD) are associations. The predictive LTV model over-predicts next-year orders by about 13% overall (well calibrated for Paid Social/Paid Search, up to +40% for small mixed groups), so use it for **ranking**, not absolute forecasts.
