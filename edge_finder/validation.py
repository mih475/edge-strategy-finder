"""Robustness gates and the trade-sequence Monte Carlo.

These are the tests that separate a real edge from a lucky backtest. Each
returns a structured result so the runner can print a pass/fail scorecard.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from . import metrics as M
from .config import Gates
from .strategy import Trade


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str


def bootstrap_prob_positive(trades: list[Trade], paths: int, seed: int) -> float:
    """P(mean net R > 0) by resampling trades with replacement. Low value means
    the positive mean could easily be noise."""
    pnl = np.array([t.pnl_R for t in trades])
    if pnl.size == 0:
        return 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, pnl.size, size=(paths, pnl.size))
    means = pnl[idx].mean(axis=1)
    return float((means > 0).mean())


def year_concentration(trades: list[Trade]) -> tuple[float, dict[int, float]]:
    """Share of total POSITIVE-year profit coming from the single best year.
    This is the gate that catches 2022-type regime dependence."""
    by_year: dict[int, float] = defaultdict(float)
    for t in trades:
        by_year[t.year] += t.pnl_R
    positive = {y: p for y, p in by_year.items() if p > 0}
    total_pos = sum(positive.values())
    if total_pos <= 0:
        return 1.0, dict(by_year)
    top = max(positive.values())
    return top / total_pos, dict(by_year)


def tail_drop_positive(trades: list[Trade]) -> tuple[bool, float]:
    """Is expectancy still positive after removing the single best trade?"""
    pnl = np.array([t.pnl_R for t in trades])
    if pnl.size <= 1:
        return False, 0.0
    without_best = np.sort(pnl)[:-1]
    return bool(without_best.mean() > 0), float(without_best.mean())


def cost_stress(trades: list[Trade], multiple: float) -> tuple[bool, float]:
    """Re-charge costs at `multiple`x and check expectancy stays positive."""
    stressed = np.array([t.gross_R - multiple * t.cost_R for t in trades])
    if stressed.size == 0:
        return False, 0.0
    return bool(stressed.mean() > 0), float(stressed.mean())


def run_gates(trades: list[Trade], gates: Gates, paths: int, seed: int) -> list[GateResult]:
    m = M.compute(trades)
    results: list[GateResult] = []

    results.append(GateResult(
        "sample size", m.n >= gates.min_trades,
        f"{m.n} trades (need >= {gates.min_trades})"))

    results.append(GateResult(
        "expectancy > 0", m.expectancy_R > gates.min_expectancy_R,
        f"{m.expectancy_R:+.4f} R/trade after cost"))

    results.append(GateResult(
        "profit factor", m.profit_factor >= gates.min_profit_factor,
        f"PF {m.profit_factor:.3f} (need >= {gates.min_profit_factor})"))

    conc, by_year = year_concentration(trades)
    results.append(GateResult(
        "year concentration", conc <= gates.max_year_concentration,
        f"best year = {conc:.0%} of positive-year profit (limit {gates.max_year_concentration:.0%})"))

    bp = bootstrap_prob_positive(trades, paths, seed)
    results.append(GateResult(
        "bootstrap", bp >= gates.bootstrap_min_win,
        f"P(mean>0) = {bp:.2%} (need >= {gates.bootstrap_min_win:.0%})"))

    ok, exp = tail_drop_positive(trades)
    results.append(GateResult(
        "tail robustness", ok == gates.tail_drop_still_positive or ok,
        f"expectancy w/o best trade = {exp:+.4f} R"))

    ok2, exp2 = cost_stress(trades, gates.cost_multiple_stress)
    results.append(GateResult(
        f"{gates.cost_multiple_stress:g}x cost stress", ok2,
        f"expectancy at {gates.cost_multiple_stress:g}x cost = {exp2:+.4f} R"))

    return results


@dataclass
class MonteCarlo:
    median_total_R: float
    p05_total_R: float
    p95_total_R: float
    median_maxdd_R: float
    worst_maxdd_R: float          # 5th-percentile (deepest) drawdown
    prob_negative: float          # share of resamples ending below zero


def trade_sequence_mc(trades: list[Trade], paths: int, seed: int) -> MonteCarlo:
    """Resample the trade set WITH REPLACEMENT many times (each path draws N
    trades from the observed N), then build each path's equity curve. This is the
    honest distribution a single backtest line hides: how good or bad the same
    edge could look from a different draw of the same process, and how deep the
    drawdown can get. (Note: permuting order alone leaves the total unchanged —
    a sum is order-independent — so resampling with replacement is what gives a
    real outcome distribution.)"""
    pnl = np.array([t.pnl_R for t in trades])
    if pnl.size == 0:
        return MonteCarlo(0, 0, 0, 0, 0, 1.0)
    rng = np.random.default_rng(seed)
    n = pnl.size
    idx = rng.integers(0, n, size=(paths, n))
    sampled = pnl[idx]                       # (paths, n)
    curves = np.cumsum(sampled, axis=1)
    totals = curves[:, -1]
    peaks = np.maximum.accumulate(curves, axis=1)
    maxdds = (curves - peaks).min(axis=1)
    return MonteCarlo(
        median_total_R=float(np.median(totals)),
        p05_total_R=float(np.percentile(totals, 5)),
        p95_total_R=float(np.percentile(totals, 95)),
        median_maxdd_R=float(np.median(maxdds)),
        worst_maxdd_R=float(np.percentile(maxdds, 5)),
        prob_negative=float((totals < 0).mean()),
    )
