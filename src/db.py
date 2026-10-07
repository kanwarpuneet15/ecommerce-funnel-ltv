"""
Thin DuckDB helper used by the pipeline, notebooks and tests.

Uses the `duckdb` Python package when installed (normal setup: `pip install -r requirements.txt`).
Falls back to the DuckDB command-line binary if the package is unavailable, so the
project still runs in locked-down environments.
"""
from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse.duckdb"

try:
    import duckdb  # type: ignore
    _HAS_PY = True
except ImportError:  # pragma: no cover
    _HAS_PY = False
    _CLI = shutil.which("duckdb")
    if _CLI is None:
        raise ImportError("Install the duckdb package (pip install duckdb) or the DuckDB CLI.")


def _cli(sql: str, csv: bool) -> str:
    args = [_CLI, str(DB_PATH)] + (["-csv"] if csv else [])
    res = subprocess.run(args, input=sql, capture_output=True, text=True, cwd=ROOT)
    if res.returncode != 0 or "Error:" in res.stderr:
        raise RuntimeError(f"DuckDB error:\n{res.stderr}\n--- SQL ---\n{sql[:2000]}")
    return res.stdout


def execute(sql: str) -> None:
    """Run one or more statements (DDL / DML)."""
    if _HAS_PY:
        with duckdb.connect(str(DB_PATH)) as con:
            con.execute(f"SET file_search_path='{ROOT.as_posix()}'")
            con.execute(sql)
    else:
        _cli(f"SET file_search_path='{ROOT.as_posix()}';\n{sql}", csv=False)


def query(sql: str) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame."""
    if _HAS_PY:
        with duckdb.connect(str(DB_PATH), read_only=False) as con:
            con.execute(f"SET file_search_path='{ROOT.as_posix()}'")
            return con.execute(sql).df()
    out = _cli(f"SET file_search_path='{ROOT.as_posix()}';\n{sql}", csv=True)
    if not out.strip():
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(out))
    for c in df.columns:
        lc = c.lower()
        if (df[c].dtype == object or pd.api.types.is_string_dtype(df[c])) and (lc.endswith(("_at", "_ts", "_date", "_month", "_day", "_week")) or lc in ("date", "month", "week", "day")):
            try:
                df[c] = pd.to_datetime(df[c])
            except (ValueError, TypeError):
                pass
    return df


def run_file(path: str | Path) -> None:
    execute(Path(path).read_text(encoding="utf-8"))
