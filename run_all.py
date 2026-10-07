"""
Reproduce the whole project from scratch (about 5 minutes):

    python run_all.py

1. generate the synthetic raw data         (src/generate_data.py)
2. build the warehouse + run 29 data tests (src/run_pipeline.py)
3. run the business-question SQL           (src/run_analysis.py -> outputs/analysis/)
4. execute the notebooks                   (notebooks/src/*.py -> notebooks/*.ipynb)
5. export dashboard data + Power BI files  (dashboard/exports/, dashboard/powerbi/)
6. run the Python test suite               (tests/)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    [PY, "src/generate_data.py"],
    [PY, "src/run_pipeline.py"],
    [PY, "src/run_analysis.py"],
    *[[PY, "src/nbrun.py", f"notebooks/src/{n}.py", f"notebooks/{n}.ipynb"]
      for n in ["01_data_profiling", "02_funnel_analysis", "03_cohort_retention", "04_ltv_analysis"]],
    [PY, "src/export_dashboard_data.py"],
    [PY, "dashboard/build_pbip.py", *sys.argv[1:]],
    [PY, "-m", "unittest", "discover", "-s", "tests", "-v"],
]

if __name__ == "__main__":
    for cmd in STEPS:
        print(f"\n=== {' '.join(Path(c).name if i < 2 else c for i, c in enumerate(cmd))}", flush=True)
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            sys.exit(f"Step failed: {' '.join(cmd)}")
    print("\nDone. Open dashboard/powerbi/Threadline.pbip in Power BI Desktop.")
