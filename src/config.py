"""
Central configuration for the synthetic data generator.

EVERY behavioural assumption baked into the synthetic dataset lives in this file,
so that (a) the data is fully transparent and reproducible, and (b) the analysis
can be validated against a known "ground truth" (see docs/generator_assumptions.md).

The company, "Threadline", is FICTIONAL: a mid-sized Indian D2C apparel brand.
Monetary values are in INR.
"""
from datetime import date

SEED = 20261007
START_DATE = date(2024, 1, 1)
END_DATE = date(2026, 9, 30)          # data snapshot / "today" for the analysis
SCALE = 0.8                            # multiplies visitor volume and spend

# ---------------------------------------------------------------------------
# Business calendar: sale events drive traffic, spend and discounts
# ---------------------------------------------------------------------------
SALE_WINDOWS = [
    # (start, end, name, traffic_multiplier, discount_low, discount_high)
    ("2024-01-03", "2024-01-14", "EOSS Winter 2024", 1.8, 0.30, 0.50),
    ("2024-07-01", "2024-07-14", "EOSS Summer 2024", 1.8, 0.30, 0.50),
    ("2024-10-22", "2024-11-01", "Diwali Sale 2024", 2.4, 0.25, 0.45),
    ("2025-01-02", "2025-01-14", "EOSS Winter 2025", 1.8, 0.30, 0.50),
    ("2025-07-01", "2025-07-14", "EOSS Summer 2025", 1.8, 0.30, 0.50),
    ("2025-10-10", "2025-10-21", "Diwali Sale 2025", 2.4, 0.25, 0.45),
    ("2026-01-02", "2026-01-14", "EOSS Winter 2026", 1.8, 0.30, 0.50),
    ("2026-07-01", "2026-07-14", "EOSS Summer 2026", 1.8, 0.30, 0.50),
]

# Business events the analysis should be able to detect
PAID_SOCIAL_RAMP_START = "2025-03-01"   # management doubles Meta spend to chase volume
PAID_SOCIAL_RAMP_END = "2025-06-01"
PAID_SOCIAL_RAMP_MULT = 2.2
CHECKOUT_REDESIGN_DATE = "2025-08-01"   # mobile checkout redesign ships

# ---------------------------------------------------------------------------
# Acquisition: daily NEW visitors per channel (before seasonality / growth)
# ---------------------------------------------------------------------------
CHANNELS = ["Organic Search", "Paid Search", "Paid Social", "Email",
            "Affiliate", "Referral", "Organic Social", "Direct"]

UNPAID_DAILY_NEW_VISITORS = {          # base level at START_DATE
    "Organic Search": 150, "Direct": 60, "Affiliate": 45, "Referral": 20,
    "Organic Social": 30, "Email": 8,  # email "new visitors" = newsletter signups
}
UNPAID_MONTHLY_GROWTH = {"Organic Search": 0.015, "Direct": 0.012, "Affiliate": 0.005,
                         "Referral": 0.0, "Organic Social": 0.01, "Email": 0.0}

PAID_DAILY_SPEND_INR = {"Paid Search": 3870, "Paid Social": 4400}   # base, pre-ramp
PAID_BASE_CPC_INR = {"Paid Search": 21.5, "Paid Social": 11.0}
CPC_SCALE_ELASTICITY = {"Paid Search": 0.15, "Paid Social": 0.35}   # diminishing returns
PAID_NEW_VISITOR_SHARE = 0.80          # share of paid clicks that are first-time visitors
EMAIL_PLATFORM_MONTHLY_INR = 25000
AFFILIATE_COMMISSION = 0.10            # % of affiliate last-click order revenue
USD_INR_RATE_FEB_2025 = 87.0           # used to plant/resolve a currency issue

DEVICE_MIX = {   # P(mobile, desktop, tablet) by acquisition channel
    "Organic Search": (0.72, 0.23, 0.05), "Paid Search": (0.68, 0.27, 0.05),
    "Paid Social": (0.91, 0.06, 0.03), "Email": (0.70, 0.25, 0.05),
    "Affiliate": (0.80, 0.16, 0.04), "Referral": (0.65, 0.30, 0.05),
    "Organic Social": (0.90, 0.07, 0.03), "Direct": (0.66, 0.29, 0.05),
}

# ---------------------------------------------------------------------------
# Session funnel (per session) — calibrated to public benchmarks:
#   ~2.5% session conversion overall, mobile ~1.8% vs desktop ~3.9%,
#   ~70% cart abandonment (Baymard), mobile abandonment > desktop.
# ---------------------------------------------------------------------------
P_PRODUCT_VIEW = 0.58
P_ADD_TO_CART = 0.12           # given product view
P_BEGIN_CHECKOUT = 0.46        # given add to cart
P_PURCHASE_BY_DEVICE = {"mobile": 0.40, "desktop": 0.64, "tablet": 0.52}  # given checkout
MOBILE_CHECKOUT_LIFT_AFTER_REDESIGN = 0.08   # absolute lift in mobile checkout->purchase

CHANNEL_FUNNEL_MULT = {        # multiplies product view / add-to-cart / checkout probs
    "Organic Search": (1.00, 1.05, 1.00), "Paid Search": (1.12, 1.25, 1.05),
    "Paid Social": (0.80, 0.62, 0.92), "Email": (1.20, 1.45, 1.08),
    "Affiliate": (1.05, 1.20, 1.05), "Referral": (1.00, 0.95, 1.00),
    "Organic Social": (0.90, 0.75, 0.95), "Direct": (1.10, 1.30, 1.05),
}
RETURNING_VISITOR_MULT = 1.25  # on add-to-cart for 2nd+ prospect sessions
CUSTOMER_INTENT_MULT = 1.35    # on checkout->purchase for repeat purchase attempts
BUY_NOW_SHARE = 0.05           # purchases that skip add_to_cart (Buy Now button)

RETURN_SESSION_CHANNEL_MIX = {  # channel of 2nd+ sessions (prospects and customers)
    "Direct": 0.32, "Organic Search": 0.18, "Paid Social": 0.16, "Paid Search": 0.12,
    "Email": 0.14, "Affiliate": 0.05, "Organic Social": 0.03,
}

# ---------------------------------------------------------------------------
# Repeat purchasing (post first order). NOT the BG/NBD model on purpose:
# gamma inter-purchase times + covariate-driven dropout, so a BG/NBD fit is a
# realistic, slightly misspecified model rather than the true generator.
# ---------------------------------------------------------------------------
BASE_DROPOUT_BY_CHANNEL = {     # P(customer never buys again) after an order
    "Organic Search": 0.58, "Paid Search": 0.60, "Paid Social": 0.75, "Email": 0.50,
    "Affiliate": 0.67, "Referral": 0.62, "Organic Social": 0.68, "Direct": 0.52,
}
DROPOUT_MODIFIERS = {
    "first_order_rto": 0.25,          # undelivered COD first order -> likely gone
    "first_order_any_return": 0.08,
    "acquired_in_sale": 0.10,
    "first_order_basics": -0.08,       # replenishable category
    "first_order_outerwear": 0.05,
    "per_order_loyalty_decay": 0.85,   # dropout prob multiplied by this per extra order
}
MEAN_INTERPURCHASE_DAYS = 110
INTERPURCHASE_GAMMA_SHAPE = 1.5

# ---------------------------------------------------------------------------
# Orders, payments, fulfilment (Indian e-commerce realities: COD and RTO)
# ---------------------------------------------------------------------------
CATEGORY_SPEC = {   # price range INR, cost ratio, item return rate, first-order mix
    "Tops":        (599, 1499, 0.42, 0.14, 0.24),
    "Bottoms":     (899, 2299, 0.44, 0.20, 0.15),
    "Dresses":     (1199, 2999, 0.40, 0.25, 0.12),
    "Outerwear":   (1999, 4999, 0.46, 0.15, 0.06),
    "Shoes":       (1499, 3999, 0.50, 0.18, 0.09),
    "Activewear":  (799, 1999, 0.43, 0.12, 0.10),
    "Basics":      (299, 799, 0.38, 0.04, 0.13),
    "Accessories": (299, 999, 0.35, 0.06, 0.11),
}
N_PRODUCTS = 480
SHIPPING_FEE_INR = 49
FREE_SHIPPING_THRESHOLD_INR = 799
WELCOME_DISCOUNT = 0.10
AFFILIATE_COUPON = (0.10, 0.15)
COD_SHARE_BASE = 0.35
RTO_RATE = {"COD": 0.20, "PREPAID": 0.02}
CANCEL_RATE = {"COD": 0.06, "PREPAID": 0.03}
PAID_SOCIAL_RETURN_MULT = 1.25

# ---------------------------------------------------------------------------
# Planted data-quality issues (detected and handled in Phase 3 — see DQ report)
# ---------------------------------------------------------------------------
TRACKING_LOSS_BY_DEVICE = {"mobile": 0.03, "desktop": 0.08, "tablet": 0.04}
BOT_SESSION_SHARE = 0.003
DUP_EVENT_SAME_ID_SHARE = 0.004
DUP_EVENT_NEW_ID_SHARE = 0.001
FUTURE_TS_EVENTS = 60
DUP_ORDER_ROWS = 90
ORDER_TOTAL_MISMATCH_SHARE = 0.002
N_INTERNAL_TEST_USERS = 35
