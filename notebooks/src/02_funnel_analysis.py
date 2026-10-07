# %% [markdown]
# # 02 · Funnel analysis
#
# **Business question:** where do we lose buyers between landing and purchase, which
# channels and devices convert, and which fix is worth the most?
#
# **Definitions**
# - Unit of analysis: a **session** (non-bot). Stages use "reached this stage *or any later
#   stage*", so Buy-Now purchases that skip the cart are counted correctly (DQ-12).
# - Stages: Session → Product view → Add to cart → Checkout → Purchase.
# - Window: the last 12 complete months (Oct 2025 – Sep 2026), unless stated.
# - Funnel conversion is measured from tracked events. 4.4% of orders are untracked (DQ-11),
#   so absolute conversion is slightly understated. Comparisons between segments are unaffected
#   as long as tracking loss is similar across them; desktop loses more, which makes desktop
#   look slightly *worse* than it is.

# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter, PercentFormatter
from scipy import stats

from db import query as q
from run_analysis import run_sql_file
from pathlib import Path
import viz

viz.setup()
A = Path("sql/analysis")


def wilson(k, n, z=1.96):
    """95% Wilson confidence interval for a proportion (better than normal approx near 0)."""
    p = k / n
    d = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / d
    return c - h, c + h

# %% [markdown]
# ## 1. The overall funnel

# %%
f = run_sql_file(A / "04_funnel_stages.sql")
overall = f[f.device_type == "all devices"].reset_index(drop=True)
overall

# %%
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.barh(overall.stage[::-1], overall.sessions[::-1], color=viz.BLUE, height=0.6)
for i, r in overall[::-1].reset_index(drop=True).iterrows():
    lab = f"{r.sessions:,.0f}" + ("" if pd.isna(r.step_conversion) else f"   ({r.step_conversion:.0%} of previous)")
    ax.text(r.sessions + 4000, i, lab, va="center", color=viz.INK_2, fontsize=9)
ax.set_xlim(0, overall.sessions.max() * 1.45)
ax.grid(axis="y", visible=False)
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x / 1000:.0f}k"))
ax.set_title("Session funnel, Oct 2025 – Sep 2026: the biggest leak is product view → cart")

# %% [markdown]
# **Reading the funnel**
# - **3.1%** of sessions end in a purchase.
# - The largest *volume* loss is **product view → add to cart**: only about 18% of product viewers add
#   anything, and about 230k sessions leave at this step.
# - The *late* stages lose far fewer sessions, but each of them is worth much more, because
#   **a session that reaches checkout is ~10× more likely to convert** than one that only views a product.
#
# So "largest drop-off" and "highest-value opportunity" are different questions. Section 5 sizes them.

# %% [markdown]
# ## 2. Device: mobile is 81% of sessions but converts at ~58% of the desktop rate (2.8% vs 4.8%)

# %%
dev = f[f.device_type != "all devices"].pivot(index="stage", columns="device_type", values="step_conversion")
dev = dev[["mobile", "desktop", "tablet"]].dropna()
dev["mobile_vs_desktop_pp"] = (dev.mobile - dev.desktop) * 100
dev.round(3)

# %%
stg = q("""
select device_type,
       sum(product_view_sessions) pv, sum(cart_sessions) cart,
       sum(checkout_sessions) co, sum(purchase_sessions) buy, sum(sessions) s
from mart.mart_funnel_daily
where session_date between '2025-10-01' and '2026-09-30' and device_type in ('mobile','desktop')
group by 1
""").set_index("device_type")
rows = []
for d in ["mobile", "desktop"]:
    r = stg.loc[d]
    for name, k, n in [("Product view → Cart", r.cart, r.pv), ("Cart → Checkout", r.co, r.cart),
                       ("Checkout → Purchase", r.buy, r.co), ("Session → Purchase", r.buy, r.s)]:
        lo, hi = wilson(k, n)
        rows.append({"device": d, "step": name, "rate": k / n, "ci_low": lo, "ci_high": hi, "n": int(n)})
ci = pd.DataFrame(rows)
ci.round(4)

# %%
fig, ax = plt.subplots(figsize=(9, 3.4))
steps = ["Product view → Cart", "Cart → Checkout", "Checkout → Purchase"]
x = np.arange(len(steps))
for j, d in enumerate(["desktop", "mobile"]):
    sub = ci.set_index(["device", "step"]).loc[d].loc[steps]
    ax.bar(x + (j - 0.5) * 0.36, sub.rate, width=0.34, color=viz.DEVICE_COLORS[d], label=d)
    ax.errorbar(x + (j - 0.5) * 0.36, sub.rate, yerr=[sub.rate - sub.ci_low, sub.ci_high - sub.rate],
                fmt="none", ecolor=viz.INK, capsize=3, lw=1)
    for xi, v in zip(x, sub.rate):
        ax.text(xi + (j - 0.5) * 0.36, v + 0.02, f"{v:.0%}", ha="center", fontsize=9, color=viz.INK_2)
ax.set_xticks(x, steps); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_ylim(0, 0.85)
ax.legend(); ax.grid(axis="x", visible=False)
ax.set_title("Step conversion by device (95% CI): mobile's widest gap is at checkout")

# %% [markdown]
# The confidence intervals are tiny relative to the gaps (large samples), so these differences are not noise.
# The **largest device gap is at the final step**: about 16 points fewer mobile checkouts complete. That points
# to payment/checkout friction on mobile (address entry, OTP, payment app hand-off) rather than to weaker
# product interest.

# %% [markdown]
# ## 3. Channel × device conversion

# %%
cd = run_sql_file(A / "02_conversion_by_channel_device.sql")
cd

# %%
chan = cd[cd.channel != "ALL CHANNELS"].copy()
ct = q("""
select channel, sum(purchased::int) as buyers, count(*) - sum(purchased::int) as non_buyers
from core.fct_sessions where session_date between '2025-10-01' and '2026-09-30' group by 1
""")
chi2, p, dof, _ = stats.chi2_contingency(ct[["buyers", "non_buyers"]].to_numpy())
print(f"Chi-square test of independence (channel x purchased): chi2={chi2:,.0f}, dof={dof}, p={p:.1e}")

fig, ax = plt.subplots(figsize=(9, 3.8))
chan = chan.sort_values("conversion_all")
ax.barh(chan.channel, chan.conversion_all, color=[viz.highlight(c) for c in chan.channel], height=0.6)
for i, (v, s) in enumerate(zip(chan.conversion_all, chan.sessions)):
    ax.text(v + 0.001, i, f"{v:.1%}  ·  {s / 1000:.0f}k sessions", va="center", fontsize=9, color=viz.INK_2)
ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0)); ax.set_xlim(0, chan.conversion_all.max() * 1.5)
ax.grid(axis="y", visible=False)
ax.set_title("Session conversion by channel: Paid Social is the largest channel and the weakest converter")

# %% [markdown]
# - **Paid Social is the largest traffic source (36% of sessions) but converts at 1.3%**, less than half the
#   site average. Its traffic is 90% mobile, but device mix doesn't explain the gap: Paid Social converts
#   worse than other channels *on every device*. Even on desktop it trails Paid Search.
# - **Email and Direct convert best.** Both are mostly existing customers and people returning with intent,
#   so they are better read as *demand-capture* channels than as acquisition channels.
# - The chi-square test rejects "conversion is the same across channels" (p ≈ 0). With samples this large,
#   significance is almost guaranteed; the **size** of the gaps is what matters.
#
# ⚠️ Session conversion is a last-click view. It says nothing about whether a channel's *customers*
# come back. That is the cohort and LTV question (notebooks 03–04).

# %% [markdown]
# ## 4. Did the mobile checkout redesign (Aug 2025) work? Difference-in-differences

# %%
trend = q("""
select date_trunc('month', session_date) as month, device_type,
       sum(purchase_sessions)::double / sum(checkout_sessions) as checkout_completion
from mart.mart_funnel_daily
where device_type in ('mobile','desktop') and session_date <= '2026-09-30'
group by all order by 1
""")
fig, ax = plt.subplots(figsize=(9, 3.6))
for d in ["desktop", "mobile"]:
    t = trend[trend.device_type == d]
    ax.plot(t.month, t.checkout_completion, color=viz.DEVICE_COLORS[d], label=d, marker="o", ms=3)
ax.axvline(pd.Timestamp("2025-08-01"), color=viz.INK_2, ls="--", lw=1)
ax.text(pd.Timestamp("2025-08-10"), 0.36, "mobile checkout\nredesign ships", fontsize=9, color=viz.INK_2)
ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0)); ax.set_ylim(0.3, 0.8); ax.legend(loc="upper left")
ax.set_title("Checkout → purchase completion by month: mobile steps up after Aug 2025, desktop doesn't")

# %%
did = run_sql_file(A / "05_checkout_redesign_diff_in_diff.sql")
did.T.rename(columns={0: "value"})

# %%
pre = trend[(trend.month >= "2024-02-01") & (trend.month < "2025-08-01")].pivot(index="month", columns="device_type", values="checkout_completion")
gap = (pre.mobile - pre.desktop)
slope = stats.linregress(np.arange(len(gap)), gap.to_numpy())
print(f"Pre-period trend in the mobile-desktop gap: {slope.slope * 100:+.2f} pp/month (p={slope.pvalue:.2f})")

# %% [markdown]
# **Result:** mobile checkout completion rose **+7.3 pp** while desktop (untouched) moved −2.3 pp over the
# same months. The difference-in-differences estimate is **+9.6 pp (95% CI 6.6 – 12.7)**.
#
# - Desktop is the control because it got the same seasons, sales and marketing but **not** the redesign.
# - **Parallel-trends check:** before the launch the mobile–desktop gap had no significant trend (p shown
#   above), which supports the comparison.
# - **Caveats:** this is observational, not a randomised A/B test. Anything else that changed mobile-only
#   in Aug 2025 (a payment-app update, say) would be credited to the redesign. The CI also uses a simple
#   binomial SE and ignores day-to-day clustering, so it is probably too narrow.
#
# *(Method-validation note: the generator planted a +8 pp effect, which falls inside the CI. The method
#  recovers the truth, and slightly over-estimates it because desktop happened to dip.)*

# %% [markdown]
# ## 5. Where is the money? Sizing the opportunities (scenarios, not forecasts)
#
# For each step: **revenue at stake** = sessions lost at the step × the probability that a session which
# *passed* the step went on to buy × net revenue per order. This is an upper bound, because people who drop
# out are less motivated than people who continue. The next table therefore sizes **realistic, explicitly
# assumed improvements** instead.

# %%
rev = q("""
select sum(net_revenue) / count(*) filter (where is_valid_order) as net_rev_per_valid_order,
       sum(gross_margin) / count(*) filter (where is_valid_order) as margin_per_valid_order,
       avg(is_valid_order::int) as valid_share
from core.fct_orders where order_date between '2025-10-01' and '2026-09-30'
""").iloc[0]
print(rev.round(3).to_string())

m = stg.loc["mobile"]
d_ = stg.loc["desktop"]
o = overall.set_index("stage")
p_after = {  # P(purchase | reached stage), all devices
    "2. Product view": o.loc["5. Purchase", "sessions"] / o.loc["2. Product view", "sessions"],
    "3. Add to cart": o.loc["5. Purchase", "sessions"] / o.loc["3. Add to cart", "sessions"],
    "4. Checkout": o.loc["5. Purchase", "sessions"] / o.loc["4. Checkout", "sessions"],
    "5. Purchase": 1.0,
}
at_stake = pd.DataFrame({
    "step": ["Session → Product view", "Product view → Cart", "Cart → Checkout", "Checkout → Purchase"],
    "sessions_lost": o.sessions_lost_at_step.iloc[1:].to_numpy(),
    "p_purchase_if_passed": list(p_after.values()),
})
at_stake["upper_bound_net_revenue"] = (at_stake.sessions_lost * at_stake.p_purchase_if_passed
                                       * rev.valid_share * rev.net_rev_per_valid_order)
at_stake.round(3)

# %%
scen = []
# A. Mobile checkout: close a further 25% of the remaining gap to desktop
gap_co = d_.buy / d_.co - m.buy / m.co
add_orders_A = m.co * 0.25 * gap_co
scen.append(("A. Mobile checkout completion closes 25% of remaining gap to desktop",
             f"+{0.25 * gap_co * 100:.1f} pp on {m.buy / m.co:.0%}", add_orders_A))
# B. Mobile product view -> cart +1pp absolute
p_buy_given_cart_m = m.buy / m.cart
add_orders_B = m.pv * 0.01 * p_buy_given_cart_m
scen.append(("B. Mobile product view → cart improves by 1 pp", f"{m.cart / m.pv:.1%} → {m.cart / m.pv + .01:.1%}", add_orders_B))
# C. Paid Social traffic converts 10% better (relative) — e.g. better landing pages
ps = chan.set_index("channel").loc["Paid Social"]
add_orders_C = ps.sessions * ps.conversion_all * 0.10
scen.append(("C. Paid Social session conversion +10% relative (landing-page fit)", f"{ps.conversion_all:.2%} → {ps.conversion_all * 1.1:.2%}", add_orders_C))
S = pd.DataFrame(scen, columns=["scenario", "assumed change", "extra_purchase_sessions_per_year"])
S["extra_valid_orders"] = S.extra_purchase_sessions_per_year * rev.valid_share
S["extra_net_revenue_inr"] = S.extra_valid_orders * rev.net_rev_per_valid_order
S["extra_gross_margin_inr"] = S.extra_valid_orders * rev.margin_per_valid_order
S["pct_of_annual_net_revenue"] = S.extra_net_revenue_inr / q(
    "select sum(net_revenue) from core.fct_orders where order_date between '2025-10-01' and '2026-09-30'").iloc[0, 0]
S.round(3)

# %% [markdown]
# **Assumptions (explicit):** volumes are the last 12 months of tracked sessions (real volume is about 4%
# higher because of tracking loss); incremental purchasers behave like average purchasers (same AOV, same
# cancel/RTO rate). This is simple scenario arithmetic, not a forecast. Changes in one stage also shift the
# mix of later stages.
#
# **Takeaways**
# - Closing a quarter of the *remaining* mobile checkout gap (+4 pp) is worth about **₹13L net revenue / ₹7L
#   margin a year (~5% of revenue)**. A **1 pp lift in mobile product-view → cart** (+6% relative) is worth about
#   **₹10L**. The top of the funnel has more *volume*; the bottom has more *value per session*. Both are worth testing.
# - Making Paid Social traffic convert 10% better is worth only about ₹4L, because it touches one channel's
#   sessions, while site-wide mobile fixes touch 81% of traffic.
# - Prioritisation (impact × effort × confidence) is in `docs/insights_and_recommendations.md`.

# %% [markdown]
# ## 6. Segments: visitor type and sale periods

# %%
seg = q("""
select visitor_type,
       count(*) as sessions,
       avg(purchased::int) as conversion,
       avg(reached_cart::int) as cart_rate,
       sum(purchased::int)::double / nullif(sum(reached_cart::int), 0) as cart_to_purchase
from core.fct_sessions where session_date between '2025-10-01' and '2026-09-30'
group by 1 order by 2 desc
""")
seg.round(4)

# %%
sale = q("""
select is_sale_day, count(*) / count(distinct session_date) as sessions_per_day,
       avg(purchased::int) as conversion, avg(reached_cart::int) as cart_rate
from core.fct_sessions where session_date between '2024-01-01' and '2026-09-30'
group by 1
""")
sale.round(4)

# %% [markdown]
# - **New visitors convert at 1.6%**, returning prospects at 3.7% (more than 2×), and existing customers at 27%.
#   Most first visits are research. Capturing the visitor (newsletter, wishlist, retargeting) matters as
#   much as converting them on the first visit.
# - **Sale days bring ~1.5× the daily traffic, but conversion per session is no higher** (2.7% vs 2.8%).
#   Sales buy volume, not efficiency. The cohort analysis checks whether sale-acquired customers are worth as much later.
