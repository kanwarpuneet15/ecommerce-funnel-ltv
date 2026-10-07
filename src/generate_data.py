"""
Synthetic data generator for "Threadline", a FICTIONAL Indian D2C apparel brand.

Why synthetic?  No public dataset combines web-funnel events, device, order
history, product cost AND marketing spend at customer level. Rather than pretend,
this generator simulates a realistic business from documented assumptions
(src/config.py, docs/generator_assumptions.md), calibrated to public benchmarks.

Output: raw, deliberately *imperfect* source tables in data/raw/ that mimic what
an analyst would actually receive (UTC event logs with UTM strings, an OLTP order
table in local time, ad-platform spend exports, etc.).

Run:  python src/generate_data.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import config as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
rng = np.random.default_rng(C.SEED)
T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


def choice(options, probs, size):
    probs = np.asarray(probs, dtype=float)
    return np.asarray(options, dtype=object)[rng.choice(len(options), size=size, p=probs / probs.sum())]


END_TS = pd.Timestamp(C.END_DATE) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
REDESIGN_TS = pd.Timestamp(C.CHECKOUT_REDESIGN_DATE)

# ============================================================================
# 1. Calendar
# ============================================================================
days = pd.date_range(C.START_DATE, C.END_DATE, freq="D")
n_days = len(days)
month_idx = ((days.year - days[0].year) * 12 + days.month - days[0].month).to_numpy()
MONTH_SEASON = {1: 1.0, 2: 0.88, 3: 0.92, 4: 0.95, 5: 0.95, 6: 0.97,
                7: 1.0, 8: 0.95, 9: 1.0, 10: 1.12, 11: 1.10, 12: 1.08}
season = np.array([MONTH_SEASON[m] for m in days.month])
weekday = np.where(days.dayofweek >= 5, 1.08, 0.97)
sale_mult = np.ones(n_days)
sale_name = np.array([None] * n_days, dtype=object)
sale_lo = np.zeros(n_days)
sale_hi = np.zeros(n_days)
for s, e, name, mult, lo, hi in C.SALE_WINDOWS:
    m = (days >= s) & (days <= e)
    sale_mult[m], sale_name[m], sale_lo[m], sale_hi[m] = mult, name, lo, hi
day_pos = {d: i for i, d in enumerate(days)}

HOUR_W = np.array([2, 1, 1, 0.5, 0.5, 0.7, 1.2, 2, 3, 3.5, 4, 4.2,
                   4.5, 4.5, 4.2, 4.2, 4.5, 5, 5.5, 6.5, 7.5, 8, 7, 4.5])
HOUR_W = HOUR_W / HOUR_W.sum()


def random_time_in_day(n):
    hrs = rng.choice(24, size=n, p=HOUR_W)
    return pd.to_timedelta(hrs * 3600 + rng.integers(0, 3600, n), unit="s")


# ============================================================================
# 2. Paid media: spend -> CPC -> clicks -> new visitors
# ============================================================================
ramp = np.ones(n_days)
r0, r1 = pd.Timestamp(C.PAID_SOCIAL_RAMP_START), pd.Timestamp(C.PAID_SOCIAL_RAMP_END)
in_ramp = (days >= r0) & (days < r1)
ramp[in_ramp] = 1 + (C.PAID_SOCIAL_RAMP_MULT - 1) * ((days[in_ramp] - r0).days / (r1 - r0).days)
ramp[days >= r1] = C.PAID_SOCIAL_RAMP_MULT

spend, clicks, paid_new = {}, {}, {}
for ch in ["Paid Search", "Paid Social"]:
    base = C.PAID_DAILY_SPEND_INR[ch] * C.SCALE
    growth = (1.01 ** month_idx) if ch == "Paid Search" else ramp
    sale_spend = 1 + 0.7 * (sale_mult - 1)
    sp = base * growth * season * sale_spend * rng.lognormal(0, 0.08, n_days)
    cpc = (C.PAID_BASE_CPC_INR[ch] * (sp / base) ** C.CPC_SCALE_ELASTICITY[ch]
           * np.where(sale_mult > 1, 1.12, 1.0) * rng.lognormal(0, 0.06, n_days))
    spend[ch], clicks[ch] = sp, sp / cpc
    paid_new[ch] = rng.poisson(clicks[ch] * C.PAID_NEW_VISITOR_SHARE)

# ============================================================================
# 3. New visitors (one row per first-time visitor)
# ============================================================================
counts = {}
for ch in C.CHANNELS:
    if ch in paid_new:
        counts[ch] = paid_new[ch]
    else:
        mu = (C.UNPAID_DAILY_NEW_VISITORS[ch] * C.SCALE * (1 + C.UNPAID_MONTHLY_GROWTH[ch]) ** month_idx
              * season * weekday * sale_mult)
        counts[ch] = rng.poisson(mu)

v_day, v_ch = [], []
for ch in C.CHANNELS:
    v_day.append(np.repeat(np.arange(n_days), counts[ch]))
    v_ch.append(np.full(counts[ch].sum(), ch, dtype=object))
v_day = np.concatenate(v_day)
v_ch = np.concatenate(v_ch)
NV = len(v_day)
V = pd.DataFrame({"acq_channel": v_ch})
V["arrival_ts"] = days[v_day] + random_time_in_day(NV)
V["device"] = "mobile"
for ch, (pm, pd_, pt) in C.DEVICE_MIX.items():
    m = V.acq_channel.to_numpy() == ch
    V.loc[m, "device"] = choice(["mobile", "desktop", "tablet"], [pm, pd_, pt], m.sum())
sig = 0.55
V["intent"] = rng.lognormal(-sig ** 2 / 2, sig, NV)            # heterogeneity, mean 1
V["tier"] = choice(["metro", "tier2", "tier3"], [0.45, 0.35, 0.20], NV)
V = V.sort_values("arrival_ts").reset_index(drop=True)
V["visitor_id"] = [f"v_{x:016x}" for x in rng.integers(0, 2 ** 63, NV, dtype=np.int64)]
log(f"visitors: {NV:,}")

# ============================================================================
# 4. Session funnel helper
# ============================================================================
CH_MULT = {k: np.array(v) for k, v in C.CHANNEL_FUNNEL_MULT.items()}


def ch_mult(channels, j):
    return np.array([CH_MULT[c][j] for c in channels])


def purchase_prob(device, ts):
    base = np.array([C.P_PURCHASE_BY_DEVICE[d] for d in device])
    lift = (device == "mobile") & (ts >= REDESIGN_TS)
    return base + lift * C.MOBILE_CHECKOUT_LIFT_AFTER_REDESIGN


def in_sale(ts):
    ts = pd.Series(ts)
    idx = np.clip(((ts.dt.normalize() - days[0]).dt.days).to_numpy(), 0, n_days - 1)
    return sale_mult[idx] > 1, idx


# ============================================================================
# 5. Prospect sessions (before first purchase)
# ============================================================================
extra = np.minimum(rng.poisson(0.42 * V.intent.to_numpy() ** 0.7), 8)
n_s = 1 + extra
S = pd.DataFrame({"v": np.repeat(np.arange(NV), n_s)})
S["k"] = S.groupby("v").cumcount()
gaps = np.where(S.k.to_numpy() == 0, 0, rng.exponential(4.0, len(S)) * 86400 + rng.integers(600, 7200, len(S)))
S["session_ts"] = V.arrival_ts.to_numpy()[S.v] + pd.to_timedelta(
    pd.Series(gaps).groupby(S.v).cumsum().to_numpy(), unit="s")
S["channel"] = V.acq_channel.to_numpy()[S.v]
ret = S.k.to_numpy() > 0
rm = C.RETURN_SESSION_CHANNEL_MIX
S.loc[ret, "channel"] = choice(list(rm), list(rm.values()), ret.sum())
S["device"] = V.device.to_numpy()[S.v]
intent = V.intent.to_numpy()[S.v]
ch = S.channel.to_numpy()
sale, _ = in_sale(S.session_ts)
p_pv = np.clip(C.P_PRODUCT_VIEW * ch_mult(ch, 0), 0, 0.95)
p_atc = np.clip(C.P_ADD_TO_CART * ch_mult(ch, 1) * np.where(ret, C.RETURNING_VISITOR_MULT, 1)
                * np.where(sale, 1.15, 1) * intent ** 0.8, 0, 0.9)
p_co = np.clip(C.P_BEGIN_CHECKOUT * ch_mult(ch, 2) * intent ** 0.3, 0, 0.9)
p_buy = np.clip(purchase_prob(S.device.to_numpy(), S.session_ts) * intent ** 0.2, 0, 0.95)
u = rng.random((4, len(S)))
S["r_pv"] = u[0] < p_pv
S["r_atc"] = S.r_pv & (u[1] < p_atc)
S["r_co"] = S.r_atc & (u[2] < p_co)
S["r_buy"] = S.r_co & (u[3] < p_buy)
S = S[S.session_ts <= END_TS]
first_buy = S[S.r_buy].groupby("v").k.min()
S["fb"] = S.v.map(first_buy).fillna(99).astype(int)
S = S[S.k <= S.fb].drop(columns="fb").reset_index(drop=True)
S["kind"] = "prospect"
log(f"prospect sessions: {len(S):,}; first purchases: {S.r_buy.sum():,}")

# ============================================================================
# 6. Products
# ============================================================================
ITEMS = {
    "Tops": ["T-Shirt", "Shirt", "Kurta", "Blouse", "Polo", "Crop Top"],
    "Bottoms": ["Jeans", "Chinos", "Trousers", "Skirt", "Joggers", "Palazzo"],
    "Dresses": ["Maxi Dress", "Midi Dress", "Shirt Dress", "Wrap Dress", "Co-ord Set"],
    "Outerwear": ["Denim Jacket", "Bomber Jacket", "Puffer Jacket", "Blazer", "Hoodie"],
    "Shoes": ["Sneakers", "Loafers", "Sandals", "Running Shoes", "Flats"],
    "Activewear": ["Track Pants", "Sports Bra", "Training Tee", "Leggings", "Shorts"],
    "Basics": ["Socks 3-Pack", "Briefs 3-Pack", "Vest 2-Pack", "Camisole", "Boxers 2-Pack"],
    "Accessories": ["Cap", "Belt", "Tote Bag", "Scarf", "Sunglasses", "Wallet"],
}
ADJ = ["Classic", "Relaxed", "Slim", "Oversized", "Everyday", "Linen", "Cotton", "Ribbed",
       "Printed", "Washed", "Essential", "Stretch", "Utility", "Textured", "Lightweight"]
cats = list(C.CATEGORY_SPEC)
prod_rows = []
pid = 1001
for cat in cats:
    lo, hi, cost_r, _, _ = C.CATEGORY_SPEC[cat]
    n = C.N_PRODUCTS // len(cats)
    for i in range(n):
        price = int(np.round(rng.uniform(lo, hi) / 100) * 100 - 1)
        dept = choice(["Women", "Men", "Unisex"], [0.55, 0.35, 0.10], 1)[0]
        prod_rows.append({
            "product_id": pid, "product_name": f"{rng.choice(ADJ)} {rng.choice(ITEMS[cat])}",
            "category": cat, "department": dept, "list_price": price,
            "unit_cost": round(price * cost_r * rng.uniform(0.9, 1.1), 2),
            "popularity": 1 / (i + 1) ** 0.8,
        })
        pid += 1
P = pd.DataFrame(prod_rows)
cat_products = {c: (g.product_id.to_numpy(), (g.popularity / g.popularity.sum()).to_numpy())
                for c, g in P.groupby("category")}
price_of = P.set_index("product_id").list_price
cost_of = P.set_index("product_id").unit_cost
CAT_ITEM_RET = {c: v[3] for c, v in C.CATEGORY_SPEC.items()}
FIRST_MIX = np.array([C.CATEGORY_SPEC[c][4] for c in cats])
ADDON_MIX = FIRST_MIX * np.array([1, 0.8, 0.6, 0.5, 0.6, 1, 2.2, 2.0])


# ============================================================================
# 7. Order generator (vectorised for a batch of orders)
# ============================================================================
def make_orders(o: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """o: columns cust, order_ts, order_no, acq_channel, sess_channel, device, tier, fav_cat"""
    n = len(o)
    sale, didx = in_sale(o.order_ts)
    month = o.order_ts.dt.month.to_numpy()
    n_items = np.minimum(1 + rng.poisson(0.55, n), 6)
    it = pd.DataFrame({"o": np.repeat(np.arange(n), n_items)})
    it["pos"] = it.groupby("o").cumcount()
    first = it.pos.to_numpy() == 0
    mix_first = np.tile(FIRST_MIX, (n, 1))
    winter = np.isin(month, [11, 12, 1])
    summer = np.isin(month, [5, 6, 7, 8])
    mix_first[:, 3] *= np.where(winter, 2.5, np.where(summer, 0.4, 1.0))
    mix_first /= mix_first.sum(1, keepdims=True)
    # first item category
    cum = mix_first.cumsum(1)
    r = rng.random(n)
    cat_first = np.array(cats, dtype=object)[(r[:, None] > cum).sum(1)]
    fav = o.fav_cat.to_numpy()
    use_fav = (o.order_no.to_numpy() > 1) & (rng.random(n) < 0.4)
    cat_first = np.where(use_fav, fav, cat_first)
    cat = np.where(first, cat_first[it.o], choice(cats, ADDON_MIX, len(it)))
    it["category"] = cat
    prods = np.empty(len(it), dtype=np.int64)
    for c in cats:
        m = it.category.to_numpy() == c
        ids, w = cat_products[c]
        prods[m] = rng.choice(ids, size=m.sum(), p=w)
    it["product_id"] = prods
    it["quantity"] = np.where(it.category == "Basics", rng.choice([1, 2, 3], len(it), p=[.6, .3, .1]),
                              rng.choice([1, 2], len(it), p=[.95, .05]))
    it["unit_price"] = price_of.reindex(it.product_id).to_numpy().astype(float)
    # discounts
    oi = it.o.to_numpy()
    disc = np.zeros(n)
    code = np.array([None] * n, dtype=object)
    sname = sale_name[didx]
    disc_sale = np.round(rng.uniform(sale_lo[didx], sale_hi[didx]) / 0.05) * 0.05
    welcome = (o.order_no.to_numpy() == 1) & (o.acq_channel.to_numpy() == "Paid Social") & (rng.random(n) < 0.45)
    aff = (o.sess_channel.to_numpy() == "Affiliate") & (rng.random(n) < 0.8)
    aff_pct = rng.choice([0.10, 0.12, 0.15], n)
    disc = np.where(aff, aff_pct, disc)
    code = np.where(aff, np.char.add("AFF", (aff_pct * 100).astype(int).astype(str)).astype(object), code)
    disc = np.where(welcome, C.WELCOME_DISCOUNT, disc)
    code = np.where(welcome, "WELCOME10", code)
    disc = np.where(sale, disc_sale, disc)
    code = np.where(sale, np.where(np.char.find(sname.astype(str), "Diwali") >= 0, "DIWALI", "EOSS"), code)
    it["discount_amount"] = np.round(it.unit_price * it.quantity * disc[oi], 2)
    # 0.3% free-gift lines (legit zero price)
    gift = rng.random(len(it)) < 0.003
    it.loc[gift, "discount_amount"] = it.loc[gift, "unit_price"] * it.loc[gift, "quantity"]

    # payment
    tier = o.tier.to_numpy()
    p_cod = (C.COD_SHARE_BASE + np.select([tier == "tier3", tier == "tier2"], [0.15, 0.06], -0.06)
             + 0.10 * (o.acq_channel.to_numpy() == "Paid Social") - 0.10 * (o.device.to_numpy() == "desktop")
             - 0.08 * (o.order_no.to_numpy() > 1))
    cod = rng.random(n) < np.clip(p_cod, 0.05, 0.9)
    pay = np.where(cod, "COD", choice(["UPI", "CARD", "WALLET"], [.6, .25, .15], n))
    kind = np.where(cod, "COD", "PREPAID")
    cancel_p = np.where(cod, C.CANCEL_RATE["COD"], C.CANCEL_RATE["PREPAID"])
    rto_p = np.where(cod, C.RTO_RATE["COD"], C.RTO_RATE["PREPAID"]) * np.where(tier == "tier3", 1.3, 1)
    u1 = rng.random(n)
    status = np.where(u1 < cancel_p, "cancelled", np.where(u1 < cancel_p + rto_p, "rto", "delivered"))
    ts = o.order_ts
    shipped = ts + pd.to_timedelta(rng.uniform(0.5, 2.5, n), unit="D")
    delivered = shipped + pd.to_timedelta(rng.uniform(1.5, 6, n), unit="D")
    rto_at = shipped + pd.to_timedelta(rng.uniform(6, 12, n), unit="D")
    cancelled = ts + pd.to_timedelta(rng.uniform(0.05, 1, n), unit="D")
    out = pd.DataFrame({"cust": o.cust.to_numpy(), "order_ts": ts.to_numpy(), "order_no": o.order_no.to_numpy(),
                        "payment_method": pay, "status": status, "discount_code": code,
                        "sess_channel": o.sess_channel.to_numpy()})
    out["shipped_at"] = np.where(status == "cancelled", pd.NaT, shipped)
    out["delivered_at"] = np.where(status == "delivered", delivered, pd.NaT)
    out["rto_at"] = np.where(status == "rto", rto_at, pd.NaT)
    out["cancelled_at"] = np.where(status == "cancelled", cancelled, pd.NaT)
    for c in ["shipped_at", "delivered_at", "rto_at", "cancelled_at"]:
        out[c] = pd.to_datetime(out[c])
    # item returns (only delivered orders)
    ret_p = (np.array([CAT_ITEM_RET[c] for c in it.category])
             * np.where(o.acq_channel.to_numpy()[oi] == "Paid Social", C.PAID_SOCIAL_RETURN_MULT, 1)
             * np.where(sale[oi], 1.1, 1))
    deliv_ts = out.delivered_at.to_numpy()[oi]
    is_ret = (status[oi] == "delivered") & (rng.random(len(it)) < ret_p)
    ret_ts = pd.to_datetime(deliv_ts) + pd.to_timedelta(rng.uniform(4, 20, len(it)), unit="D")
    it["returned_at"] = np.where(is_ret, ret_ts, pd.NaT)
    it["returned_at"] = pd.to_datetime(it.returned_at)
    out["any_return"] = pd.Series(is_ret).groupby(oi).any().reindex(range(n), fill_value=False).to_numpy()
    out["first_cat"] = cat_first
    return out, it


# ============================================================================
# 8. Customers: first order + repeat purchasing in vectorised rounds
# ============================================================================
fb = S[S.r_buy].copy()
cust = pd.DataFrame({"v": fb.v.to_numpy(), "first_sess_idx": fb.index.to_numpy()})
NC = len(cust)
cust["acq_channel"] = V.acq_channel.to_numpy()[cust.v]
cust["device"] = V.device.to_numpy()[cust.v]
cust["tier"] = V.tier.to_numpy()[cust.v]
cust["intent"] = V.intent.to_numpy()[cust.v]
first_ts = fb.session_ts.to_numpy() + pd.to_timedelta(rng.uniform(4, 25, NC), unit="m")
cust["p_base"] = np.array([C.BASE_DROPOUT_BY_CHANNEL[c] for c in cust.acq_channel]) + rng.normal(0, 0.07, NC)
cust["mu"] = C.MEAN_INTERPURCHASE_DAYS * rng.lognormal(0, 0.5, NC) / cust.intent ** 0.3
cust["acq_sale"] = in_sale(pd.Series(first_ts))[0]

all_orders, all_items, extra_sessions = [], [], []
o1 = pd.DataFrame({"cust": np.arange(NC), "order_ts": pd.Series(first_ts), "order_no": 1,
                   "acq_channel": cust.acq_channel, "sess_channel": fb.channel.to_numpy(),
                   "device": cust.device, "tier": cust.tier, "fav_cat": None})
ords, its = make_orders(o1)
ords["session_ref"] = cust.first_sess_idx.to_numpy()
all_orders.append(ords)
all_items.append(its.assign(batch=0))
cust["fav_cat"] = ords.first_cat.to_numpy()
M = C.DROPOUT_MODIFIERS
cust["p_drop"] = np.clip(cust.p_base + M["first_order_rto"] * (ords.status.to_numpy() == "rto")
                         + M["first_order_any_return"] * ords.any_return.to_numpy()
                         + M["acquired_in_sale"] * cust.acq_sale
                         + M["first_order_basics"] * (cust.fav_cat == "Basics")
                         + M["first_order_outerwear"] * (cust.fav_cat == "Outerwear"), 0.05, 0.97)
P_CO_CUST = min(C.P_BEGIN_CHECKOUT * 1.5, 0.9)

active = np.ones(NC, dtype=bool)
last_ts = pd.Series(first_ts)
order_no = np.ones(NC, dtype=int)
k = 1
while active.any():
    idx = np.where(active)[0]
    drop = rng.random(len(idx)) < cust.p_drop.to_numpy()[idx] * M["per_order_loyalty_decay"] ** (order_no[idx] - 1)
    gap = rng.gamma(C.INTERPURCHASE_GAMMA_SHAPE, cust.mu.to_numpy()[idx] / C.INTERPURCHASE_GAMMA_SHAPE)
    nxt = last_ts.to_numpy()[idx] + pd.to_timedelta(gap, unit="D")
    # dropped customers: occasional browsing after they stop buying
    d_idx = idx[drop]
    nb = rng.poisson(0.6, len(d_idx))
    if nb.sum():
        ci = np.repeat(d_idx, nb)
        bts = last_ts.to_numpy()[ci] + pd.to_timedelta(rng.uniform(5, 200, len(ci)), unit="D")
        extra_sessions.append(pd.DataFrame({"cust": ci, "session_ts": bts, "kind": "browse"}))
    keep = ~drop & (nxt <= END_TS.to_datetime64())
    stop = ~drop & ~keep
    active[idx[drop | stop]] = False
    idx, nxt = idx[keep], nxt[keep]
    if len(idx) == 0:
        break
    # browsing sessions between orders
    nb = rng.poisson(0.8, len(idx))
    ci = np.repeat(idx, nb)
    lo = last_ts.to_numpy()[ci]
    span = (np.repeat(nxt, nb) - lo) / np.timedelta64(1, "s")
    extra_sessions.append(pd.DataFrame({"cust": ci, "session_ts": lo + pd.to_timedelta(rng.random(len(ci)) * span, unit="s"),
                                        "kind": "browse"}))
    # purchase attempts: failures before success (checkout friction applies to repeat buyers too)
    dev = cust.device.to_numpy()[idx]
    p_succ = P_CO_CUST * np.clip(purchase_prob(dev, pd.Series(nxt)) * C.CUSTOMER_INTENT_MULT, 0, 0.95)
    fails = rng.geometric(p_succ) - 1
    lost = fails > 3
    fails = np.minimum(fails, 4)
    ci = np.repeat(idx, fails)
    back = np.concatenate([np.arange(f, 0, -1) for f in fails]) if fails.sum() else np.array([])
    fts = np.repeat(nxt, fails) - pd.to_timedelta(back * rng.uniform(0.3, 2.5, len(ci)), unit="D")
    extra_sessions.append(pd.DataFrame({"cust": ci, "session_ts": fts, "kind": "attempt_fail"}))
    win = idx[~lost]
    wts = nxt[~lost]
    order_no[win] += 1
    last_ts.iloc[idx] = nxt
    if len(win):
        sch = choice(list(rm), list(rm.values()), len(win))
        o = pd.DataFrame({"cust": win, "order_ts": pd.Series(wts) - pd.Timedelta(0), "order_no": order_no[win],
                          "acq_channel": cust.acq_channel.to_numpy()[win], "sess_channel": sch,
                          "device": cust.device.to_numpy()[win], "tier": cust.tier.to_numpy()[win],
                          "fav_cat": cust.fav_cat.to_numpy()[win]})
        ords, its = make_orders(o)
        ords["session_ref"] = -1
        all_orders.append(ords)
        all_items.append(its.assign(batch=k))
    k += 1

orders = []
items = []
offset = 0
for ords, its in zip(all_orders, all_items):
    its = its.copy()
    its["o"] = its.o + offset
    offset += len(ords)
    orders.append(ords)
    items.append(its)
O = pd.concat(orders, ignore_index=True)
I = pd.concat(items, ignore_index=True)
log(f"customers: {NC:,}; orders: {len(O):,}; items: {len(I):,}; rounds: {k}")

# ============================================================================
# 9. Customer sessions (repeat purchases, failed attempts, browsing)
# ============================================================================
rep = O[O.order_no > 1]
cs = [pd.DataFrame({"cust": rep.cust.to_numpy(),
                    "session_ts": rep.order_ts.to_numpy() - pd.to_timedelta(rng.uniform(3, 25, len(rep)), unit="m"),
                    "kind": "attempt_win", "order_row": rep.index.to_numpy(), "channel": rep.sess_channel.to_numpy()})]
cs += extra_sessions
CS = pd.concat(cs, ignore_index=True)
CS = CS[CS.session_ts <= END_TS]
CS["v"] = cust.v.to_numpy()[CS.cust]
CS["device"] = cust.device.to_numpy()[CS.cust]
nochan = CS.channel.isna()
CS.loc[nochan, "channel"] = choice(list(rm), list(rm.values()), nochan.sum())
n = len(CS)
u = rng.random((4, n))
kind = CS.kind.to_numpy()
CS["r_pv"] = np.where(kind == "browse", u[0] < C.P_PRODUCT_VIEW * 1.1, True)
CS["r_atc"] = np.where(kind == "browse", CS.r_pv & (u[1] < C.P_ADD_TO_CART * 1.2), True)
CS["r_co"] = np.where(kind == "browse", CS.r_atc & (u[2] < C.P_BEGIN_CHECKOUT * 0.6),
                      np.where(kind == "attempt_fail", u[2] < 0.55, True))
CS["r_buy"] = kind == "attempt_win"
CS["order_row"] = CS.order_row.fillna(-1).astype(int)
log(f"customer sessions: {n:,}")

# link first orders to their prospect session
S["order_row"] = -1
first_rows = O.index[O.order_no == 1].to_numpy()
S.loc[O.loc[first_rows, "session_ref"].to_numpy(), "order_row"] = first_rows
S["kind"] = "prospect"
ALL = pd.concat([S[["v", "session_ts", "channel", "device", "r_pv", "r_atc", "r_co", "r_buy", "order_row", "kind"]],
                 CS[["v", "session_ts", "channel", "device", "r_pv", "r_atc", "r_co", "r_buy", "order_row", "kind"]]],
                ignore_index=True).sort_values("session_ts", kind="stable").reset_index(drop=True)
ALL["session_id"] = [f"s_{x:016x}" for x in rng.integers(0, 2 ** 63, len(ALL), dtype=np.int64)]
log(f"all sessions: {len(ALL):,}")

# ============================================================================
# 10. Users (registered accounts) and IDs
# ============================================================================
# order ids by time
O = O.sort_values("order_ts", kind="stable")
O["order_id"] = np.arange(300001, 300001 + len(O))
row_to_oid = pd.Series(O.order_id.to_numpy(), index=O.index)
I["order_id"] = row_to_oid.reindex(I.o).to_numpy()

# registration: customers (pre-registered at an earlier session 30% of the time, else at checkout)
cust_v = cust.v.to_numpy()
reg = pd.DataFrame({"v": cust_v, "created_at": pd.Series(first_ts) - pd.to_timedelta(rng.uniform(1, 4, NC), unit="m")})
earlier = ALL[ALL.v.isin(cust_v) & (ALL.kind == "prospect") & ALL.r_pv & (ALL.order_row < 0)]
earlier = earlier.groupby("v").session_ts.min()
pre = reg.v.map(earlier)
use_pre = pre.notna() & (rng.random(NC) < 0.30)
reg.loc[use_pre, "created_at"] = pre[use_pre] + pd.Timedelta(minutes=2)
# non-buying registrants
nb_sess = ALL[(ALL.kind == "prospect") & ALL.r_pv & ~ALL.v.isin(cust_v)]
nb_first = nb_sess.groupby("v").session_ts.min()
pick = nb_first.index[rng.random(len(nb_first)) < 0.06]
reg = pd.concat([reg, pd.DataFrame({"v": pick, "created_at": nb_first[pick].to_numpy() + pd.Timedelta(minutes=3)})],
                ignore_index=True).sort_values("created_at").reset_index(drop=True)
reg["user_id"] = np.arange(50001, 50001 + len(reg))
v_to_user = reg.set_index("v").user_id
O["user_id"] = v_to_user.reindex(cust_v[O.cust]).to_numpy()

CITIES = {
    "metro": [("Mumbai", "Maharashtra"), ("Delhi", "Delhi"), ("Bengaluru", "Karnataka"), ("Hyderabad", "Telangana"),
              ("Chennai", "Tamil Nadu"), ("Kolkata", "West Bengal"), ("Pune", "Maharashtra"), ("Ahmedabad", "Gujarat")],
    "tier2": [("Jaipur", "Rajasthan"), ("Lucknow", "Uttar Pradesh"), ("Indore", "Madhya Pradesh"), ("Chandigarh", "Chandigarh"),
              ("Kochi", "Kerala"), ("Nagpur", "Maharashtra"), ("Coimbatore", "Tamil Nadu"), ("Bhubaneswar", "Odisha"),
              ("Surat", "Gujarat"), ("Vadodara", "Gujarat")],
    "tier3": [("Ajmer", "Rajasthan"), ("Gorakhpur", "Uttar Pradesh"), ("Siliguri", "West Bengal"), ("Jhansi", "Uttar Pradesh"),
              ("Bhagalpur", "Bihar"), ("Hubli", "Karnataka"), ("Udaipur", "Rajasthan"), ("Patiala", "Punjab"),
              ("Rohtak", "Haryana"), ("Bilaspur", "Chhattisgarh")],
}
NU = len(reg)
tiers = V.tier.to_numpy()[reg.v]
city = np.empty(NU, dtype=object)
state = np.empty(NU, dtype=object)
for t, lst in CITIES.items():
    m = tiers == t
    j = rng.integers(0, len(lst), m.sum())
    city[m] = [lst[x][0] for x in j]
    state[m] = [lst[x][1] for x in j]
U = pd.DataFrame({
    "user_id": reg.user_id, "created_at": reg.created_at.dt.round("s"),
    "email_domain": choice(["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "rediffmail.com", "hotmail.com"],
                           [.78, .07, .05, .04, .03, .03], NU),
    "gender": choice(["F", "M"], [0.62, 0.38], NU),
    "birth_year": (2025 - np.clip(18 + rng.gamma(3.2, 3.6, NU), 18, 65)).astype(int),
    "city": city, "state": state,
})

# ============================================================================
# 11. Events (raw web/app tracking log, UTC)
# ============================================================================
NS = len(ALL)
n_page = 1 + rng.poisson(0.8, NS)
n_pv = np.where(ALL.r_pv, 1 + rng.poisson(1.2, NS), 0)
buy_now = ALL.r_buy.to_numpy() & (rng.random(NS) < C.BUY_NOW_SHARE)
n_atc = np.where(ALL.r_atc & ~buy_now, 1 + (rng.random(NS) < 0.2), 0)
n_co = ALL.r_co.to_numpy().astype(int)
n_buy = ALL.r_buy.to_numpy().astype(int)
blocks = [("page_view", n_page), ("product_view", n_pv), ("add_to_cart", n_atc),
          ("begin_checkout", n_co), ("purchase", n_buy)]
ev_parts = []
for order_k, (name, cnt) in enumerate(blocks):
    s_idx = np.repeat(np.arange(NS), cnt)
    ev_parts.append(pd.DataFrame({"s": s_idx, "event_name": name, "ord": order_k}))
E = pd.concat(ev_parts, ignore_index=True).sort_values(["s", "ord"], kind="stable").reset_index(drop=True)
gap_s = np.where(E.groupby("s").cumcount().to_numpy() == 0, 0, rng.exponential(45, len(E)) + 3)
offs = pd.Series(gap_s).groupby(E.s.to_numpy()).cumsum().to_numpy()
sess_ts = ALL.session_ts.to_numpy()
ev_ts = sess_ts[E.s] + pd.to_timedelta(offs, unit="s")
# purchase event ts must equal order ts (order system); use order ts minus 1-5 s
o_ts = O.set_index(O.index).order_ts
is_p = E.event_name.to_numpy() == "purchase"
orow = ALL.order_row.to_numpy()[E.s]
ev_ts = pd.Series(ev_ts)
ev_ts[is_p] = o_ts.reindex(orow[is_p]).to_numpy() - pd.to_timedelta(rng.integers(1, 5, is_p.sum()), unit="s")
E["ts_ist"] = ev_ts.to_numpy()
E["order_id"] = np.where(is_p, row_to_oid.reindex(orow).to_numpy(), np.nan)

# product ids on product_view / add_to_cart; purchase sessions: atc product = first item of the order
pop = P.popularity / P.popularity.sum()
needs_p = E.event_name.isin(["product_view", "add_to_cart"]).to_numpy()
E["product_id"] = np.where(needs_p, rng.choice(P.product_id.to_numpy(), len(E), p=pop.to_numpy()), np.nan)

# session-level attributes
browser = np.empty(NS, dtype=object)
dev = ALL.device.to_numpy()
for d, (opts, pr) in {"mobile": (["Chrome", "Safari", "Samsung Internet", "Firefox"], [.70, .18, .10, .02]),
                      "desktop": (["Chrome", "Edge", "Safari", "Firefox"], [.72, .12, .10, .06]),
                      "tablet": (["Safari", "Chrome"], [.55, .45])}.items():
    m = dev == d
    browser[m] = choice(opts, pr, m.sum())
chs = ALL.channel.to_numpy()
utm_s = np.array([None] * NS, dtype=object)
utm_m = np.array([None] * NS, dtype=object)
utm_c = np.array([None] * NS, dtype=object)
refd = np.array([None] * NS, dtype=object)
retarget = ALL.kind.to_numpy() != "prospect"


def put(mask, arr, opts, pr):
    arr[mask] = choice(opts, pr, mask.sum())


m = chs == "Organic Search"; put(m, refd, ["google.com", "bing.com", "duckduckgo.com"], [.9, .07, .03])
m = chs == "Paid Search"
put(m, utm_s, ["google", "bing"], [.96, .04]); put(m, utm_m, ["cpc", "CPC", "ppc"], [.9, .06, .04])
put(m, utm_c, ["brand_search", "generic_search", "shopping"], [.3, .4, .3])
m = chs == "Paid Social"
put(m, utm_s, ["facebook", "instagram", "fb", "ig", "Instagram", "Facebook"], [.3, .45, .08, .07, .06, .04])
put(m, utm_m, ["paid_social", "paid", "cpc", None], [.7, .15, .1, .05])
put(m, utm_c, ["prospecting_broad", "prospecting_lookalike", "retargeting_cart", "retargeting_view"], [.4, .35, .15, .1])
put(m & (rng.random(NS) < 0.4), refd, ["l.instagram.com", "m.facebook.com"], [.6, .4])
m = chs == "Email"
put(m, utm_s, ["newsletter", "klaviyo"], [.6, .4]); put(m, utm_m, ["email", "Email", "e-mail"], [.85, .1, .05])
put(m, utm_c, ["weekly_drop", "abandoned_cart", "winback", "sale_announcement"], [.45, .25, .1, .2])
m = chs == "Affiliate"
put(m, utm_s, ["cashback_site", "coupon_site", "deals_blog"], [.5, .35, .15]); put(m, utm_m, ["affiliate"], [1])
m = chs == "Referral"; put(m, refd, ["stylemag.in", "pinterest.com", "reddit.com", "quora.com"], [.35, .35, .15, .15])
m = chs == "Organic Social"
put(m, refd, ["instagram.com", "l.instagram.com", "facebook.com", "m.facebook.com", "youtube.com"], [.3, .3, .1, .15, .15])

sid = ALL.session_id.to_numpy()
vid = V.visitor_id.to_numpy()[ALL.v.to_numpy()]
E["session_id"] = sid[E.s]
E["visitor_id"] = vid[E.s]
E["device_type"] = dev[E.s]
E["browser"] = browser[E.s]
E["utm_source"] = utm_s[E.s]
E["utm_medium"] = utm_m[E.s]
E["utm_campaign"] = utm_c[E.s]
E["referrer_domain"] = refd[E.s]
# user_id appears on events once the visitor is logged in (after registration)
reg_ts = reg.set_index("v").created_at
e_reg = reg_ts.reindex(ALL.v.to_numpy()[E.s]).to_numpy()
logged = pd.notna(e_reg) & (E.ts_ist.to_numpy() >= e_reg)
E["user_id"] = np.where(logged, v_to_user.reindex(ALL.v.to_numpy()[E.s]).to_numpy(), np.nan)
cat_slug = P.set_index("product_id").category.str.lower()
paths = np.select(
    [E.event_name == "page_view", E.event_name == "product_view", E.event_name == "add_to_cart",
     E.event_name == "begin_checkout", E.event_name == "purchase"],
    ["/", "/product/", "/cart", "/checkout", "/order-confirmation"], "/").astype(object)
pv_m = E.event_name.to_numpy() == "product_view"
paths[pv_m] = "/product/" + E.loc[pv_m, "product_id"].astype(int).astype(str)
pg = E.event_name.to_numpy() == "page_view"
paths[pg] = choice(["/", "/category/tops", "/category/dresses", "/category/bottoms", "/sale", "/new-in", "/search"],
                   [.35, .15, .1, .1, .1, .1, .1], pg.sum())
E["page_path"] = paths

# tracking loss: whole sessions never reach the collector (ad blockers / consent)
loss_p = np.array([C.TRACKING_LOSS_BY_DEVICE[d] for d in dev])
lost_sess = rng.random(NS) < loss_p
E = E[~lost_sess[E.s]]
log(f"events before DQ noise: {len(E):,} (sessions lost to tracking: {lost_sess.sum():,})")

# ---- bots
n_bot_sess = int(C.BOT_SESSION_SHARE * NS)
bot_vis = [f"v_{x:016x}" for x in rng.integers(0, 2 ** 63, 150, dtype=np.int64)]
bs_v = rng.choice(bot_vis, n_bot_sess)
bs_ts = days[rng.integers(0, n_days, n_bot_sess)] + random_time_in_day(n_bot_sess)
bs_n = rng.integers(25, 120, n_bot_sess)
bE = pd.DataFrame({"b": np.repeat(np.arange(n_bot_sess), bs_n)})
bE["event_name"] = choice(["page_view", "product_view"], [.4, .6], len(bE))
boff = pd.Series(rng.uniform(0.2, 2.0, len(bE))).groupby(bE.b).cumsum().to_numpy()
bE["ts_ist"] = bs_ts[bE.b] + pd.to_timedelta(boff, unit="s")
bE["session_id"] = np.array([f"s_{x:016x}" for x in rng.integers(0, 2 ** 63, n_bot_sess, dtype=np.int64)])[bE.b]
bE["visitor_id"] = bs_v[bE.b]
bE["device_type"] = "desktop"
bE["browser"] = choice(["Chrome", "HeadlessChrome"], [.6, .4], n_bot_sess)[bE.b]
bE["product_id"] = np.where(bE.event_name == "product_view", rng.choice(P.product_id.to_numpy(), len(bE)), np.nan)
bE["page_path"] = np.where(bE.event_name == "product_view", "/product/" + bE.product_id.fillna(0).astype(int).astype(str), "/")
E = pd.concat([E.drop(columns=["s", "ord"]), bE.drop(columns="b")], ignore_index=True)

E["event_id"] = [f"e_{x:016x}" for x in rng.integers(0, 2 ** 63, len(E), dtype=np.int64)]
# UTC conversion (tracking pipeline logs in UTC; orders DB stores IST)
E["event_ts_utc"] = (pd.to_datetime(E.ts_ist) - pd.Timedelta(hours=5, minutes=30))
# ---- duplicates and clock skew
d1 = E.sample(frac=C.DUP_EVENT_SAME_ID_SHARE, random_state=1)
d2 = E.sample(frac=C.DUP_EVENT_NEW_ID_SHARE, random_state=2).copy()
d2["event_id"] = [f"e_{x:016x}" for x in rng.integers(0, 2 ** 63, len(d2), dtype=np.int64)]
E = pd.concat([E, d1, d2], ignore_index=True)
skew = rng.choice(len(E), C.FUTURE_TS_EVENTS, replace=False)
E.loc[skew, "event_ts_utc"] = E.loc[skew, "event_ts_utc"] + pd.Timedelta(days=400)
E = E.sample(frac=1, random_state=3).reset_index(drop=True)   # logs arrive unordered
E["event_ts_utc"] = E.event_ts_utc.dt.strftime("%Y-%m-%dT%H:%M:%S.%f").str[:-3] + "Z"
E["user_id"] = E.user_id.astype("Int64")
E["product_id"] = E.product_id.astype("Int64")
E["order_id"] = E.order_id.astype("Int64")
EV_COLS = ["event_id", "event_ts_utc", "event_name", "session_id", "visitor_id", "user_id", "device_type",
           "browser", "utm_source", "utm_medium", "utm_campaign", "referrer_domain", "page_path",
           "product_id", "order_id"]
E = E[EV_COLS]
log(f"events final: {len(E):,}")

# ============================================================================
# 12. Finalise orders / items (+ internal test accounts and planted issues)
# ============================================================================
I["order_item_id"] = np.arange(9000001, 9000001 + len(I))
I["net"] = I.unit_price * I.quantity - I.discount_amount
sub = I.groupby("order_id").net.sum()
O["items_subtotal"] = O.order_id.map(sub)
O["shipping_fee"] = np.where(O.items_subtotal < C.FREE_SHIPPING_THRESHOLD_INR, C.SHIPPING_FEE_INR, 0)
O["order_total"] = (O.items_subtotal + O.shipping_fee).round(2)
mm = rng.random(len(O)) < C.ORDER_TOTAL_MISMATCH_SHARE
O.loc[mm, "order_total"] = (O.loc[mm, "order_total"] * rng.choice([0.9, 1.18], mm.sum())).round(2)

# internal QA/test accounts placing real orders in production
NT = C.N_INTERNAL_TEST_USERS
t_uid = np.arange(990001, 990001 + NT)
t_created = days[rng.integers(0, 60, NT)] + random_time_in_day(NT)
TU = pd.DataFrame({"user_id": t_uid, "created_at": t_created, "email_domain": "threadline.in",
                   "gender": choice(["F", "M"], [.5, .5], NT), "birth_year": rng.integers(1985, 2001, NT),
                   "city": "Bengaluru", "state": "Karnataka"})
U = pd.concat([U, TU], ignore_index=True)
nto = rng.integers(2, 9, NT)
TO = pd.DataFrame({"user_id": np.repeat(t_uid, nto)})
TO["order_ts"] = days[rng.integers(0, n_days, len(TO))] + random_time_in_day(len(TO))
TO["order_id"] = np.arange(800001, 800001 + len(TO))
TO["payment_method"] = "UPI"
TO["status"] = choice(["delivered", "cancelled"], [.5, .5], len(TO))
TO["discount_code"] = "QA100"
TO["shipped_at"] = pd.NaT
TO["delivered_at"] = np.where(TO.status == "delivered", TO.order_ts + pd.Timedelta(days=1), pd.NaT)
TO["delivered_at"] = pd.to_datetime(TO.delivered_at)
TO["rto_at"] = pd.NaT
TO["cancelled_at"] = np.where(TO.status == "cancelled", TO.order_ts + pd.Timedelta(hours=1), pd.NaT)
TO["cancelled_at"] = pd.to_datetime(TO.cancelled_at)
TI = pd.DataFrame({"order_id": TO.order_id, "product_id": rng.choice(P.product_id.to_numpy(), len(TO)),
                   "quantity": 1, "unit_price": 1.0, "discount_amount": 0.0, "returned_at": pd.NaT})
TO["items_subtotal"], TO["shipping_fee"], TO["order_total"] = 1.0, 0, 1.0
I = pd.concat([I, TI.assign(order_item_id=np.arange(9900001, 9900001 + len(TI)))], ignore_index=True)

ORD_COLS = ["order_id", "user_id", "order_ts", "status", "payment_method", "discount_code",
            "shipping_fee", "order_total", "shipped_at", "delivered_at", "rto_at", "cancelled_at"]
OUT_O = pd.concat([O[ORD_COLS], TO[ORD_COLS]], ignore_index=True)
# orders still in flight at snapshot time
inflight_ship = OUT_O.shipped_at > END_TS
inflight_del = OUT_O.delivered_at > END_TS
OUT_O.loc[inflight_del & ~inflight_ship, "status"] = "shipped"
OUT_O.loc[inflight_ship, "status"] = "processing"
for c in ["shipped_at", "delivered_at", "rto_at", "cancelled_at"]:
    OUT_O.loc[OUT_O[c] > END_TS, c] = pd.NaT
OUT_O.loc[(OUT_O.rto_at.isna()) & (OUT_O.status == "rto"), "status"] = "shipped"
I.loc[I.returned_at > END_TS, "returned_at"] = pd.NaT
# messy status casing from a legacy admin tool
mess = rng.random(len(OUT_O)) < 0.01
OUT_O.loc[mess, "status"] = OUT_O.loc[mess, "status"].str.upper()
OUT_O = OUT_O.rename(columns={"order_ts": "created_at"})
for c in ["created_at", "shipped_at", "delivered_at", "rto_at", "cancelled_at"]:
    OUT_O[c] = pd.to_datetime(OUT_O[c]).dt.round("s")
OUT_O["user_id"] = OUT_O.user_id.astype("Int64")
# duplicate rows from a re-run ETL load
OUT_O = pd.concat([OUT_O, OUT_O.sample(C.DUP_ORDER_ROWS, random_state=4)], ignore_index=True)
OUT_O = OUT_O.sort_values("created_at", kind="stable").reset_index(drop=True)

ITEM_COLS = ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount_amount", "returned_at"]
OUT_I = I[ITEM_COLS].copy()
OUT_I["returned_at"] = pd.to_datetime(OUT_I.returned_at).dt.round("s")

# ============================================================================
# 13. Marketing spend exports
# ============================================================================
rows = []
for i, d in enumerate(days):
    for ct, sh in [("brand", .2), ("generic", .45), ("shopping", .35)]:
        sp = spend["Paid Search"][i] * sh * rng.uniform(.9, 1.1)
        ck = clicks["Paid Search"][i] * sh * rng.uniform(.92, 1.08)
        rows.append((d, "google_ads", ct, sp, ck / rng.uniform(.04, .06), ck, "INR"))
    for ct, sh in [("prospecting", .75), ("retargeting", .25)]:
        sp = spend["Paid Social"][i] * sh * rng.uniform(.9, 1.1)
        ck = clicks["Paid Social"][i] * sh * rng.uniform(.92, 1.08)
        rows.append((d, "meta_ads", ct, sp, ck / rng.uniform(.009, .014), ck, "INR"))
MS = pd.DataFrame(rows, columns=["date", "platform", "campaign_type", "spend", "impressions", "clicks", "currency"])
usd = (MS.platform == "meta_ads") & (MS.date >= "2025-02-10") & (MS.date <= "2025-02-16")
MS.loc[usd, "spend"] = MS.loc[usd, "spend"] / C.USD_INR_RATE_FEB_2025
MS.loc[usd, "currency"] = "USD"
# affiliate commissions: monthly, on delivered last-click affiliate revenue
aff = O[(O.sess_channel == "Affiliate") & (O.status == "delivered")].copy()
aff["month_end"] = aff.order_ts.dt.to_period("M").dt.to_timestamp("M")
am = aff.groupby("month_end").items_subtotal.sum() * C.AFFILIATE_COMMISSION
MS = pd.concat([MS, pd.DataFrame({"date": am.index, "platform": "affiliate_network", "campaign_type": "commission",
                                  "spend": am.values, "impressions": np.nan, "clicks": np.nan, "currency": "INR"})])
months = pd.date_range(C.START_DATE, C.END_DATE, freq="MS")
MS = pd.concat([MS, pd.DataFrame({"date": months, "platform": "email_platform", "campaign_type": "subscription",
                                  "spend": float(C.EMAIL_PLATFORM_MONTHLY_INR), "impressions": np.nan,
                                  "clicks": np.nan, "currency": "INR"})])
MS = MS[MS.date <= pd.Timestamp(C.END_DATE)]
MS["spend"] = MS.spend.round(2)
MS["impressions"] = MS.impressions.round().astype("Int64")
MS["clicks"] = MS.clicks.round().astype("Int64")
MS["date"] = pd.to_datetime(MS.date).dt.date
MS = MS.sort_values(["date", "platform", "campaign_type"]).reset_index(drop=True)

# ============================================================================
# 14. Write
# ============================================================================
RAW.mkdir(parents=True, exist_ok=True)
P[["product_id", "product_name", "category", "department", "list_price", "unit_cost"]].to_csv(RAW / "products.csv", index=False)
U.to_csv(RAW / "users.csv", index=False)
OUT_O.to_csv(RAW / "orders.csv", index=False)
OUT_I.to_csv(RAW / "order_items.csv", index=False)
MS.to_csv(RAW / "marketing_spend.csv", index=False)
E.to_csv(RAW / "events.csv.gz", index=False, compression={"method": "gzip", "compresslevel": 3})
log("written: " + ", ".join(f"{p.name} ({p.stat().st_size / 1e6:.1f} MB)" for p in sorted(RAW.iterdir())))
