"""
Unit tests for the BG/NBD and Gamma-Gamma implementations.
Strategy: simulate customers from the model with KNOWN parameters, fit, and check the
fit recovers them and that predictions match simulated future behaviour.

Run: python -m unittest discover tests      (or: pytest tests)
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clv_models import (bgnbd_expected_purchases, bgnbd_p_alive, fit_bgnbd,  # noqa: E402
                        fit_gamma_gamma, gg_expected_value, fit_mbgnbd,
                        mbgnbd_expected_purchases, mbgnbd_p_alive)


def simulate_bgnbd(n, r, alpha, a, b, T_cal, T_hold, rng, modified=False):
    lam = rng.gamma(r, 1 / alpha, n)
    p = rng.beta(a, b, n)
    x = np.zeros(n, int)
    t_x = np.zeros(n)
    future = np.zeros(n, int)
    for i in range(n):
        t = 0.0
        alive = (rng.random() > p[i]) if modified else True   # MBG: can drop right after the first purchase
        while alive:
            t += rng.exponential(1 / lam[i])
            if t > T_cal + T_hold:
                break
            if t <= T_cal:
                x[i] += 1
                t_x[i] = t
            else:
                future[i] += 1
            alive = rng.random() > p[i]          # drop out after a purchase
    return x, t_x, np.full(n, float(T_cal)), future


class TestBGNBD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(7)
        cls.true = dict(r=0.6, alpha=12.0, a=0.9, b=2.5)
        cls.x, cls.t_x, cls.T, cls.future = simulate_bgnbd(6000, **cls.true, T_cal=52, T_hold=52, rng=rng)
        cls.fit = fit_bgnbd(cls.x, cls.t_x, cls.T)

    def test_recovers_parameters(self):
        for k in ("r", "alpha"):
            self.assertAlmostEqual(self.fit[k] / self.true[k], 1.0, delta=0.25, msg=k)

    def test_predicts_holdout_total(self):
        pred = bgnbd_expected_purchases(self.fit, 52, self.x, self.t_x, self.T).sum()
        self.assertAlmostEqual(pred / self.future.sum(), 1.0, delta=0.08)

    def test_p_alive_bounds_and_ordering(self):
        pa = bgnbd_p_alive(self.fit, self.x, self.t_x, self.T)
        self.assertTrue(np.all((pa >= 0) & (pa <= 1)))
        self.assertTrue(np.all(pa[self.x == 0] == 1.0))   # no repeat yet -> cannot have dropped out (model property)
        # a frequent buyer who bought recently is more likely alive than one who stopped long ago
        recent = bgnbd_p_alive(self.fit, np.array([5]), np.array([50.0]), np.array([52.0]))
        stale = bgnbd_p_alive(self.fit, np.array([5]), np.array([5.0]), np.array([52.0]))
        self.assertGreater(recent[0], stale[0])


class TestMBGNBD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(11)
        cls.true = dict(r=0.8, alpha=10.0, a=1.5, b=1.5)
        cls.x, cls.t_x, cls.T, cls.future = simulate_bgnbd(6000, **cls.true, T_cal=52, T_hold=52, rng=rng,
                                                           modified=True)
        cls.fit = fit_mbgnbd(cls.x, cls.t_x, cls.T)

    def test_predicts_holdout_total(self):
        pred = mbgnbd_expected_purchases(self.fit, 52, self.x, self.t_x, self.T).sum()
        self.assertAlmostEqual(pred / self.future.sum(), 1.0, delta=0.08)

    def test_one_time_buyers_can_be_dead(self):
        pa = mbgnbd_p_alive(self.fit, self.x, self.t_x, self.T)
        self.assertTrue(np.all((pa > 0) & (pa < 1)))
        self.assertLess(pa[self.x == 0].mean(), 0.9)


class TestGammaGamma(unittest.TestCase):
    def test_recovers_population_mean(self):
        rng = np.random.default_rng(3)
        p, q, v = 4.0, 3.5, 900.0
        n = 5000
        nu = rng.gamma(q, 1 / v, n)                     # customer-level rate
        x = rng.integers(1, 6, n)
        m = np.array([rng.gamma(p, 1 / nu_i, k).mean() for nu_i, k in zip(nu, x)])
        fit = fit_gamma_gamma(x, m)
        true_mean = p * v / (q - 1)
        est_mean = fit["p"] * fit["v"] / (fit["q"] - 1)
        self.assertAlmostEqual(est_mean / true_mean, 1.0, delta=0.08)
        cond = gg_expected_value(fit, x, m)
        self.assertTrue(np.all(cond > 0))


if __name__ == "__main__":
    unittest.main()
