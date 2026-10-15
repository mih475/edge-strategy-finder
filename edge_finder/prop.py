"""Prop-firm rule simulator (TakeProfitTrader model).

A prop account doesn't ask "is the edge positive?" It asks "can this edge reach the
profit target BEFORE a normal losing streak hits the trailing drawdown?" That is a
much tighter question, and it is where most funded accounts die. This simulator
answers it with Monte Carlo: feed it a strategy's per-trade P&L (in points) and a
contract size, and it reports P(pass the eval), P(blow the drawdown), and the
expected result net of the account fee.

TakeProfitTrader rules modeled (verify against your dashboard — terms change):
  Account   Target    Trailing DD   Max contracts
  $25K      $1,500    $1,500        3
  $50K      $3,000    $2,000        6
  $75K      $4,500    $2,500        9
  $100K     $6,000    $3,000        12
  $150K     $9,000    $4,500        15
  - Trailing drawdown trails the (end-of-day) balance up and LOCKS at the starting
    balance once you're up by the drawdown amount; after that you simply can't go
    below start. (PRO funded phase trails intraday — harsher; model with intraday=True.)
  - Consistency: best single day must be < 50% of total net profit.
  - Minimum 3 trading days.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ES_POINT = 50.0    # $ per point, E-mini S&P
MES_POINT = 5.0    # $ per point, Micro E-mini S&P

TPT = {
    25000:  dict(target=1500, dd=1500, max_contracts=3),
    50000:  dict(target=3000, dd=2000, max_contracts=6),
    75000:  dict(target=4500, dd=2500, max_contracts=9),
    100000: dict(target=6000, dd=3000, max_contracts=12),
    150000: dict(target=9000, dd=4500, max_contracts=15),
}


@dataclass
class PropResult:
    account: int
    contracts: int
    point_value: float
    p_pass: float
    p_blow: float
    p_timeout: float
    p_consistency_fail: float
    median_days_to_pass: float
    expected_dd_hit: float


def simulate_eval(trade_pts: np.ndarray, account: int, contracts: int,
                  point_value: float, intraday_risk_pts: np.ndarray | None = None,
                  max_trades: int = 400, paths: int = 20000, seed: int = 7) -> PropResult:
    """Monte Carlo the evaluation: draw trades (with replacement) until the target
    is reached (pass), the trailing floor is breached (blow), or max_trades (timeout).

    trade_pts: historical per-trade P&L in points.
    intraday_risk_pts: per-trade worst adverse excursion in points (defaults to the
        loss size, i.e. assume losers hit their stop intraday) — used for the
        intraday breach check, which is how a real account blows mid-trade.
    """
    rng = np.random.default_rng(seed)
    pnl = trade_pts.astype(float) * point_value * contracts
    if intraday_risk_pts is None:
        # assume each trade's worst intraday point was min(0, its result): losers
        # reach at least their realized loss intraday.
        intraday = np.minimum(pnl, 0.0)
    else:
        intraday = -np.abs(intraday_risk_pts.astype(float)) * point_value * contracts
    target = TPT[account]["target"]
    dd = TPT[account]["dd"]
    n = len(pnl)

    passes = blows = timeouts = consist_fail = 0
    days_to_pass = []
    for _ in range(paths):
        bal = 0.0
        peak = 0.0
        floor = -dd
        best_day = -1e18
        total = 0.0
        outcome = "timeout"
        idx = rng.integers(0, n, size=max_trades)
        for k in range(max_trades):
            i = idx[k]
            # intraday adverse excursion first (can blow mid-trade)
            if bal + intraday[i] <= floor:
                outcome = "blow"; break
            bal += pnl[i]
            total = bal
            best_day = max(best_day, pnl[i])
            if bal > peak:
                peak = bal
                floor = min(peak - dd, 0.0)   # trails up, locks at start (0)
            if bal <= floor:
                outcome = "blow"; break
            if bal >= target and (k + 1) >= 3:
                # consistency: best day < 50% of total
                if best_day < 0.5 * bal:
                    outcome = "pass"; days_to_pass.append(k + 1)
                else:
                    outcome = "consist"  # hit target but fails consistency; keep going a bit
                    # in practice you'd trade more small days; treat as not-yet-pass
                    continue
                break
        if outcome == "pass": passes += 1
        elif outcome == "blow": blows += 1
        elif outcome == "consist": consist_fail += 1
        else: timeouts += 1

    return PropResult(
        account=account, contracts=contracts, point_value=point_value,
        p_pass=passes / paths, p_blow=blows / paths,
        p_timeout=timeouts / paths, p_consistency_fail=consist_fail / paths,
        median_days_to_pass=float(np.median(days_to_pass)) if days_to_pass else float("nan"),
        expected_dd_hit=float(np.mean(np.minimum(pnl, 0.0))),
    )


def sweep(trade_pts, account, point_value, label, risk_pts=None, max_c=None):
    cfg = TPT[account]
    max_c = max_c or cfg["max_contracts"]
    print(f"\n{label}  |  TPT ${account:,}  (target ${cfg['target']}, "
          f"trailing DD ${cfg['dd']}, max {cfg['max_contracts']} contracts)")
    print(f"  {'contracts':>9}{'P(pass)':>9}{'P(blow)':>9}{'P(timeout)':>11}"
          f"{'med days':>9}")
    for c in range(1, max_c + 1):
        r = simulate_eval(trade_pts, account, c, point_value, risk_pts)
        print(f"  {c:>9}{r.p_pass:>9.1%}{r.p_blow:>9.1%}{r.p_timeout:>11.1%}"
              f"{r.median_days_to_pass:>9.0f}")
