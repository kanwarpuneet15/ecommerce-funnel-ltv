"""
Run every business-question query in sql/analysis/ and save its result to
outputs/analysis/<name>.csv (these CSVs are what the README and insights cite).

Usage: python src/run_analysis.py [--print]
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "analysis"


def run_sql_file(path: Path) -> pd.DataFrame:
    return db.query(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for f in sorted((ROOT / "sql" / "analysis").glob("*.sql")):
        df = run_sql_file(f)
        df.to_csv(OUT / f"{f.stem}.csv", index=False)
        print(f"{f.stem}: {len(df)} rows")
        if "--print" in sys.argv:
            print(df.to_string(index=False), "\n")
