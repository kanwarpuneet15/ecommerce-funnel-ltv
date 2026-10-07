"""
Minimal notebook builder: executes a percent-format Python script ("# %%" cells,
"# %% [markdown]" for text) and writes a Jupyter .ipynb WITH outputs (text,
DataFrame tables and matplotlib charts), so notebooks render on GitHub.

Usage: python src/nbrun.py notebooks/src/01_data_profiling.py notebooks/01_data_profiling.ipynb
(With Jupyter installed you can equally open and re-run the .ipynb directly.)
"""
from __future__ import annotations

import ast
import base64
import contextlib
import io
import json
import os
import sys
import traceback
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 200)


def split_cells(src: str):
    cells, cur, kind = [], [], "code"
    for line in src.splitlines():
        if line.startswith("# %%"):
            if any(l.strip() for l in cur):
                cells.append((kind, "\n".join(cur).strip("\n")))
            cur, kind = [], ("markdown" if "[markdown]" in line else "code")
            continue
        cur.append(line)
    if any(l.strip() for l in cur):
        cells.append((kind, "\n".join(cur).strip("\n")))
    return cells


def md_text(block: str) -> str:
    return "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in block.splitlines())


def run(script: Path, out: Path):
    root = script.resolve().parents[2]
    os.chdir(root)
    sys.path.insert(0, str(root / "src"))
    ns: dict = {"__name__": "__main__"}
    nb_cells, count, failed = [], 0, False
    for kind, block in split_cells(script.read_text(encoding="utf-8")):
        if kind == "markdown":
            nb_cells.append({"cell_type": "markdown", "metadata": {}, "source": md_text(block).splitlines(True)})
            continue
        count += 1
        outputs, buf = [], io.StringIO()
        try:
            tree = ast.parse(block)
            last = tree.body[-1] if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            body = tree.body[:-1] if last else tree.body
            with contextlib.redirect_stdout(buf):
                exec(compile(ast.Module(body, []), "<cell>", "exec"), ns)
                val = eval(compile(ast.Expression(last.value), "<cell>", "eval"), ns) if last else None
        except Exception:
            failed = True
            val = None
            outputs.append({"output_type": "error", "ename": "Error", "evalue": "",
                            "traceback": traceback.format_exc().splitlines()})
        if buf.getvalue():
            outputs.insert(0, {"output_type": "stream", "name": "stdout", "text": buf.getvalue().splitlines(True)})
        for num in plt.get_fignums():
            fig = plt.figure(num)
            b = io.BytesIO()
            fig.savefig(b, format="png", dpi=110, bbox_inches="tight")
            outputs.append({"output_type": "display_data", "metadata": {},
                            "data": {"image/png": base64.b64encode(b.getvalue()).decode(), "text/plain": ["<Figure>"]}})
        plt.close("all")
        if val is not None:
            data = {"text/plain": repr(val).splitlines(True)}
            if isinstance(val, (pd.DataFrame, pd.Series)):
                frame = val.to_frame() if isinstance(val, pd.Series) else val
                data["text/html"] = frame.to_html(max_rows=40).splitlines(True)
            outputs.append({"output_type": "execute_result", "execution_count": count, "metadata": {}, "data": data})
        nb_cells.append({"cell_type": "code", "execution_count": count, "metadata": {},
                         "source": block.splitlines(True), "outputs": outputs})
        if failed:
            err = next(o for o in outputs if o["output_type"] == "error")
            print(f"Cell {count} failed:\n" + "\n".join(err["traceback"]), file=sys.stderr)
            break
    nb = {"cells": nb_cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                          "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print(f"wrote {out} ({count} code cells){' WITH ERRORS' if failed else ''}")
    return not failed


if __name__ == "__main__":
    ok = run(Path(sys.argv[1]), Path(sys.argv[2]))
    sys.exit(0 if ok else 1)
