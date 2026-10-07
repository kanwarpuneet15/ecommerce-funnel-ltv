"""
Independent re-computation of headline metrics in pandas, straight from the RAW files,
compared with the SQL warehouse. If the two implementations agree, it is very unlikely
that both contain the same bug.

Requires the warehouse to be built first:  python src/run_pipeline.py
Run: python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402

RAW = ROOT / "data" / "raw"
SNAP = pd.Timestamp("2026-09-30 23:59:59")


class TestSqlVsPython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        users = pd.read_csv(RAW / "users.csv")
        orders = pd.read_csv(RAW / "orders.csv", parse_dates=["created_at"]).drop_duplicates("order_id")
        items = pd.read_csv(RAW / "order_items.csv", parse_dates=["returned_at"])
        internal = set(users.loc[users.email_domain.str.lower() == "threadline.in", "user_id"])
        orders = orders[~orders.user_id.isin(internal)].copy()
        orders["status"] = orders.status.str.lower()
        orders["valid"] = ~orders.status.isin(["cancelled", "rto"])
        items["gross"] = items.unit_price * items.quantity - items.discount_amount
        items["net"] = np.where(items.returned_at.notna(), 0, items.gross)
        per_order = items.groupby("order_id").net.sum()
        orders["net"] = np.where(orders.valid, orders.order_id.map(per_order), 0)
        cls.orders, cls.items = orders, items

    def test_order_count(self):
        sql = db.query("select count(*) n from core.fct_orders").n.iloc[0]
        self.assertEqual(sql, len(self.orders))

    def test_net_revenue_total(self):
        sql = db.query("select sum(net_revenue) v from core.fct_orders").v.iloc[0]
        self.assertAlmostEqual(float(sql), float(self.orders.net.sum()), delta=1.0)

    def test_customer_count(self):
        sql = db.query("select count(*) n from core.dim_customers where is_customer").n.iloc[0]
        self.assertEqual(sql, self.orders.loc[self.orders.valid, "user_id"].nunique())

    def test_cohort_sizes(self):
        v = self.orders[self.orders.valid]
        first = v.groupby("user_id").created_at.min().dt.to_period("M").value_counts().sort_index()
        sql = db.query("""select strftime(cohort_month, '%Y-%m') m, count(*) n from core.dim_customers
                          where is_customer group by 1 order by 1""").set_index("m").n
        py = pd.Series(first.values, index=first.index.astype(str))
        pd.testing.assert_series_equal(sql.sort_index(), py.sort_index(), check_names=False, check_dtype=False)

    def test_repeat_rate_365d(self):
        v = self.orders[self.orders.valid].sort_values("created_at")
        first = v.groupby("user_id").created_at.min()
        elig = first[first + pd.Timedelta(days=395) <= SNAP]
        v = v[v.user_id.isin(elig.index)]
        v = v.assign(day_n=(v.created_at - v.user_id.map(first)).dt.days)
        py = (v[v.day_n < 365].groupby("user_id").size() >= 2).mean()
        sql = db.query("select avg((orders_365d >= 2)::int) r from mart.mart_customer_ltv where eligible_365d").r.iloc[0]
        self.assertAlmostEqual(float(sql), float(py), places=6)

    def test_session_conversion_from_raw_events(self):
        ev = pd.read_csv(RAW / "events.csv.gz", usecols=["event_id", "event_ts_utc", "event_name", "session_id", "browser"])
        ev = ev.drop_duplicates("event_id")
        ev["ts"] = pd.to_datetime(ev.event_ts_utc.str.rstrip("Z")) + pd.Timedelta(minutes=330)
        ev = ev[ev.ts <= SNAP]
        s = ev.groupby("session_id").agg(n=("event_id", "size"), t0=("ts", "min"), t1=("ts", "max"),
                                         buy=("event_name", lambda x: (x == "purchase").any()),
                                         br=("browser", "first"))
        dur = (s.t1 - s.t0).dt.total_seconds().clip(lower=1)
        bot = (s.br == "HeadlessChrome") | ((s.n >= 25) & (s.n / dur * 60 > 20))
        py = s.loc[~bot, "buy"].mean()
        sql = db.query("select avg(purchased::int) c from core.fct_sessions").c.iloc[0]
        # content-duplicates (new event_id) are not removed here, so allow a tiny tolerance
        self.assertAlmostEqual(float(sql), float(py), delta=0.0005)


if __name__ == "__main__":
    unittest.main()
