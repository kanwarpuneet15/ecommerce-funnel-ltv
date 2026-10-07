"""
Build the warehouse end to end:  raw -> seeds -> staging -> intermediate -> marts -> tests.

Usage:
    python src/run_pipeline.py            # build everything and run tests
    python src/run_pipeline.py --no-tests

The model order below IS the dependency graph (each step only reads from earlier ones):

    raw.*  ─┐
    seeds.* ┼─> stg.* ─> int.* ─> core.* (star schema) ─> mart.* (aggregates) ─> dashboard/exports
            └───────────────────────────────────────────────────────────────────> tests
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

DAG = [
    "sql/raw/load_raw.sql",
    "sql/raw/load_seeds.sql",
    "sql/staging/stg_events.sql",
    "sql/staging/stg_sessions.sql",
    "sql/staging/stg_users.sql",
    "sql/staging/stg_orders.sql",
    "sql/staging/stg_order_items.sql",
    "sql/staging/stg_products_and_spend.sql",
    "sql/intermediate/int_models.sql",
    "sql/marts/core_models.sql",
    "sql/marts/analytics_marts.sql",
]


def build() -> None:
    for f in DAG:
        t = time.time()
        db.run_file(ROOT / f)
        print(f"  built {f:<45} {time.time() - t:5.1f}s")


def run_tests() -> bool:
    """Every file in sql/tests returns the rows that VIOLATE an expectation. 0 rows = pass."""
    ok = True
    for f in sorted((ROOT / "sql" / "tests").glob("*.sql")):
        for i, stmt in enumerate(s for s in f.read_text(encoding="utf-8").split(";") if s.strip() and not
                                 all(l.strip().startswith("--") or not l.strip() for l in s.splitlines())):
            name = next((l.strip("- ").strip() for l in stmt.splitlines() if l.strip().startswith("-- test:")), f"{f.stem}#{i}")
            n = len(db.query(stmt))
            status = "PASS" if n == 0 else f"FAIL ({n} violating rows)"
            ok &= n == 0
            print(f"  [{status}] {name.replace('test:', '').strip()}")
    return ok


if __name__ == "__main__":
    print("Building warehouse ...")
    build()
    if "--no-tests" not in sys.argv:
        print("Running data tests ...")
        passed = run_tests()
        print("ALL TESTS PASSED" if passed else "SOME TESTS FAILED")
        sys.exit(0 if passed else 1)
