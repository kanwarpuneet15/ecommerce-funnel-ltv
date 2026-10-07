"""
Export the analysis-ready tables the BI dashboard reads (small CSVs, committed to git so the
dashboard works without rebuilding the warehouse).

Usage: python src/export_dashboard_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "exports"

EXPORTS = {
    "dim_date": "SELECT * FROM core.dim_date",
    "dim_customers": """SELECT user_id, signup_ts, gender, age_band, city, state, city_tier, acquisition_channel,
                               acquisition_device, is_customer, first_order_ts, cohort_month, valid_orders,
                               is_repeat_customer, net_revenue_to_date, gross_margin_to_date,
                               first_order_payment_type, acquired_in_sale, first_order_category,
                               first_order_had_return, ever_rto
                        FROM core.dim_customers""",
    "fct_orders": """SELECT order_id, user_id, order_date, order_month, status, payment_type, is_discounted,
                            is_sale_order, is_valid_order, is_cancelled, is_rto, is_in_flight, has_return,
                            units, gmv, discount_amount, gross_revenue, returned_revenue, net_revenue, cogs,
                            gross_margin, gross_revenue_placed, customer_order_number, is_first_order,
                            order_session_channel, order_session_device, acquisition_channel
                     FROM core.fct_orders""",
    "funnel_daily": "SELECT * FROM mart.mart_funnel_daily",
    "channel_monthly": "SELECT * FROM mart.mart_channel_monthly",
    "cohort_retention": "SELECT * FROM mart.mart_cohort_retention",
    "customer_ltv": """SELECT user_id, cohort_month, date_trunc('quarter', cohort_month)::DATE AS cohort_quarter,
                              acquisition_channel, first_order_payment_type, acquired_in_sale,
                              CASE WHEN margin_to_date < 500 THEN '< ₹500' WHEN margin_to_date < 1000 THEN '₹500–1k'
                                   WHEN margin_to_date < 2000 THEN '₹1k–2k' WHEN margin_to_date < 4000 THEN '₹2k–4k'
                                   ELSE '₹4k+' END AS ltv_band,
                              CASE WHEN margin_to_date < 500 THEN 1 WHEN margin_to_date < 1000 THEN 2
                                   WHEN margin_to_date < 2000 THEN 3 WHEN margin_to_date < 4000 THEN 4 ELSE 5 END AS ltv_band_order,
                              net_revenue_first_order, margin_first_order, margin_90d, margin_180d, margin_365d,
                              net_revenue_365d, orders_365d, margin_to_date, orders_to_date,
                              eligible_90d, eligible_180d, eligible_365d
                       FROM mart.mart_customer_ltv""",
    "clv_predictions": "SELECT * FROM mart.mart_customer_clv_predictions",
    "kpi_monthly": "SELECT * FROM mart.mart_kpi_monthly",
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sql in EXPORTS.items():
        path = (OUT / f"{name}.csv").as_posix()
        # DuckDB writes the file itself: exact types, ISO dates, true/false booleans
        db.execute(f"COPY ({sql}) TO '{path}' (HEADER, DELIMITER ',')")
        n = sum(1 for _ in open(OUT / f"{name}.csv", encoding="utf-8")) - 1
        print(f"{name:<18} {n:>7,} rows  {(OUT / f'{name}.csv').stat().st_size / 1e6:5.2f} MB")
