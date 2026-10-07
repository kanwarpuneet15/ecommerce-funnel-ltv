"""
Probabilistic customer-lifetime models, implemented from the original papers with scipy
(so every formula is visible and testable; no black-box library).

BG/NBD  — Fader, Hardie & Lee (2005), "Counting Your Customers the Easy Way".
           Models how many REPEAT purchases a customer makes, allowing for silent churn:
           while "alive", purchases follow Poisson(lambda), lambda ~ Gamma(r, alpha);
           after each purchase the customer drops out with prob p, p ~ Beta(a, b).
Gamma-Gamma — Fader, Hardie & Lee (2005), "RFM and CLV: Using Iso-value Curves".
           Models the average value per transaction; assumes value is independent of frequency.

Inputs per customer (time unit = weeks):
    x   = number of repeat purchases in the calibration period (frequency)
    t_x = time from first purchase to last purchase (recency)
    T   = time from first purchase to end of calibration (age)
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import betaln, gammaln, hyp2f1


def _fit(negll, x0, args):
    """Maximum likelihood on log-parameters. Bounded (exp(-8)..exp(8)) and NaN-safe, so
    degenerate segments cannot send parameters to infinity. Multiple starts, best kept."""
    def safe(lp, *a):
        v = negll(lp, *a)
        return v if np.isfinite(v) else 1e12
    best = None
    for start in (x0, np.zeros_like(x0), np.asarray(x0) + 1.0):
        res = minimize(safe, x0=start, args=args, method="L-BFGS-B", bounds=[(-8, 8)] * len(x0))
        if best is None or res.fun < best.fun:
            best = res
    if not np.isfinite(best.fun) or best.fun >= 1e12:
        raise RuntimeError("fit failed")
    return best


# --------------------------------------------------------------------------- BG/NBD
def bgnbd_negll(log_params, x, t_x, T):
    r, alpha, a, b = np.exp(log_params)
    A1 = gammaln(r + x) - gammaln(r) + r * np.log(alpha)
    A2 = betaln(a, b + x) - betaln(a, b) - (r + x) * np.log(alpha + T)
    # second term only exists for customers with at least one repeat purchase
    with np.errstate(divide="ignore", invalid="ignore"):
        A3 = np.where(x > 0,
                      betaln(a + 1, b + np.maximum(x, 1) - 1) - betaln(a, b) - (r + x) * np.log(alpha + t_x),
                      -np.inf)
    ll = A1 + np.logaddexp(A2, A3)
    return -ll.sum()


def fit_bgnbd(x, t_x, T):
    x, t_x, T = map(np.asarray, (x, t_x, T))
    res = _fit(bgnbd_negll, np.log([0.5, 10.0, 1.0, 1.0]), (x, t_x, T))
    r, alpha, a, b = np.exp(res.x)
    return {"r": r, "alpha": alpha, "a": a, "b": b, "negll": res.fun}


def bgnbd_p_alive(params, x, t_x, T):
    r, alpha, a, b = (params[k] for k in ("r", "alpha", "a", "b"))
    x, t_x, T = map(np.asarray, (x, t_x, T))
    term = np.where(x > 0, a / (b + x - 1) * ((alpha + T) / (alpha + t_x)) ** (r + x), 0.0)
    return 1.0 / (1.0 + term)


def bgnbd_expected_purchases(params, t, x, t_x, T):
    """E[number of repeat purchases in (T, T+t] | x, t_x, T]."""
    r, alpha, a, b = (params[k] for k in ("r", "alpha", "a", "b"))
    x, t_x, T = map(np.asarray, (x, t_x, T))
    hyp = hyp2f1(r + x, b + x, a + b + x - 1, t / (alpha + T + t))
    num = (a + b + x - 1) / (a - 1) * (1 - ((alpha + T) / (alpha + T + t)) ** (r + x) * hyp)
    den = 1 + np.where(x > 0, a / (b + x - 1) * ((alpha + T) / (alpha + t_x)) ** (r + x), 0.0)
    return num / den


# --------------------------------------------------------------------------- Gamma-Gamma
def gg_negll(log_params, x, m):
    p, q, v = np.exp(log_params)
    ll = (gammaln(p * x + q) - gammaln(p * x) - gammaln(q) + q * np.log(v)
          + (p * x - 1) * np.log(m) + p * x * np.log(x) - (p * x + q) * np.log(v + m * x))
    return -ll.sum()


def fit_gamma_gamma(x, m):
    """x = number of transactions used for the mean (>=1), m = mean value per transaction (>0)."""
    x, m = np.asarray(x, float), np.asarray(m, float)
    res = _fit(gg_negll, np.log([2.0, 3.0, float(np.mean(m))]), (x, m))
    p, q, v = np.exp(res.x)
    return {"p": p, "q": q, "v": v, "negll": res.fun}


def gg_expected_value(params, x, m, population_mean=None):
    """E[value per transaction | x, m]; customers with x=0 get the population mean."""
    p, q, v = params["p"], params["q"], params["v"]
    x, m = np.asarray(x, float), np.asarray(m, float)
    pop = p * v / (q - 1) if population_mean is None else population_mean
    cond = (v + m * x) * p / (p * x + q - 1)
    return np.where(x > 0, cond, pop)


# --------------------------------------------------------------------------- MBG/NBD
# Batislam, Denizel & Filiztekin (2007). Same as BG/NBD except a customer can also drop out
# right after the FIRST purchase. Plain BG/NBD assumes every one-time buyer is still "alive",
# which over-predicts repeat purchasing in businesses with many one-and-done customers.
def mbgnbd_negll(log_params, x, t_x, T):
    r, alpha, a, b = np.exp(log_params)
    A1 = gammaln(r + x) - gammaln(r) + r * np.log(alpha)
    A2 = betaln(a, b + x + 1) - betaln(a, b)
    A3 = -(r + x) * np.log(alpha + T)
    A4 = np.log(a) - np.log(b + x) + (r + x) * (np.log(alpha + T) - np.log(alpha + t_x))
    return -(A1 + A2 + A3 + np.logaddexp(0, A4)).sum()


def fit_mbgnbd(x, t_x, T):
    x, t_x, T = map(np.asarray, (x, t_x, T))
    res = _fit(mbgnbd_negll, np.log([0.5, 10.0, 1.0, 1.0]), (x, t_x, T))
    r, alpha, a, b = np.exp(res.x)
    return {"r": r, "alpha": alpha, "a": a, "b": b, "negll": res.fun}


def mbgnbd_p_alive(params, x, t_x, T):
    r, alpha, a, b = (params[k] for k in ("r", "alpha", "a", "b"))
    x, t_x, T = map(np.asarray, (x, t_x, T))
    return 1.0 / (1.0 + a / (b + x) * ((alpha + T) / (alpha + t_x)) ** (r + x))


def mbgnbd_expected_purchases(params, t, x, t_x, T):
    r, alpha, a, b = (params[k] for k in ("r", "alpha", "a", "b"))
    x, t_x, T = map(np.asarray, (x, t_x, T))
    hyp = hyp2f1(r + x, b + x + 1, a + b + x, t / (alpha + T + t))
    num = (a + b + x) / (a - 1) * (1 - hyp * ((alpha + T) / (alpha + T + t)) ** (r + x))
    den = 1 + a / (b + x) * ((alpha + T) / (alpha + t_x)) ** (r + x)
    return num / den
