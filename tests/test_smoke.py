"""End-to-end smoke test: builds synthetic data, runs the VRP study through the
full harness, and asserts the pipeline produces a coherent report. Run:

    python -m pytest tests/ -q      (or)      python tests/test_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge_finder import data as D
from edge_finder.runner import evaluate
from edge_finder.studies.vrp import VarianceRiskPremium


def test_pipeline_runs():
    df = D.synthetic_vix_spy(years=16, seed=7)
    strat = VarianceRiskPremium(richness_threshold=None)
    trades = strat.to_trades(df)
    assert len(trades) > 50, "expected a reasonable number of non-overlapping trades"
    rep = evaluate(trades, strat.name)
    # coherence, not correctness-of-edge (data is synthetic)
    assert rep.metrics.n == len(trades)
    assert rep.mc.p05_total_R <= rep.mc.median_total_R <= rep.mc.p95_total_R
    assert len(rep.gates) == 7
    print(f"OK: {len(trades)} trades, expectancy {rep.metrics.expectancy_R:+.4f} R, "
          f"survivor={rep.survivor}")


if __name__ == "__main__":
    test_pipeline_runs()
    print("smoke test passed")
