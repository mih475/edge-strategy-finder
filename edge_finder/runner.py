"""The runner: take a strategy's trades, score them, run the gates and the Monte
Carlo, and print a scorecard. One function so every study reports identically.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import metrics as M
from . import validation as V
from .config import Config, DEFAULT
from .strategy import Trade


@dataclass
class Report:
    label: str
    metrics: M.Metrics
    gates: list[V.GateResult]
    mc: V.MonteCarlo
    survivor: bool


def evaluate(trades: list[Trade], label: str, cfg: Config = DEFAULT) -> Report:
    m = M.compute(trades)
    gates = V.run_gates(trades, cfg.gates, cfg.mc_paths, cfg.rng_seed)
    mc = V.trade_sequence_mc(trades, cfg.mc_paths, cfg.rng_seed)
    survivor = all(g.passed for g in gates)
    return Report(label, m, gates, mc, survivor)


def print_report(rep: Report) -> None:
    line = "=" * 64
    print(line)
    print(f" {rep.label}")
    print(line)
    md = rep.metrics.as_dict()
    print(f"  trades {md['n']:>6}   expectancy {md['expectancy_R']:+.4f} R"
          f"   PF {md['profit_factor']:.3f}")
    print(f"  win%   {md['win_rate']:>6.1%}   total {md['total_R']:+.1f} R"
          f"   maxDD {md['max_drawdown_R']:.1f} R")
    print("  " + "-" * 60)
    print("  ROBUSTNESS GATES")
    for g in rep.gates:
        mark = "PASS" if g.passed else "FAIL"
        print(f"    [{mark}] {g.name:<20} {g.detail}")
    print("  " + "-" * 60)
    mc = rep.mc
    print("  OUTCOME MONTE CARLO (resample trade set with replacement)")
    print(f"    total R   median {mc.median_total_R:+.1f}"
          f"   [p05 {mc.p05_total_R:+.1f}, p95 {mc.p95_total_R:+.1f}]")
    print(f"    max DD    median {mc.median_maxdd_R:.1f}"
          f"   worst-5% {mc.worst_maxdd_R:.1f} R")
    print(f"    P(ends negative) {mc.prob_negative:.1%}")
    print("  " + "-" * 60)
    verdict = "SURVIVOR - promote to next data stage" if rep.survivor \
        else "REJECTED - did not pass all gates"
    print(f"  VERDICT: {verdict}")
    print(line)
