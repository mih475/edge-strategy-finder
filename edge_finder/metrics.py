"""Performance metrics, all computed from a list of Trade records in R units."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .strategy import Trade


@dataclass
class Metrics:
    n: int
    expectancy_R: float          # mean net R per trade — the headline edge
    total_R: float
    win_rate: float
    profit_factor: float         # gross wins / gross losses (net of cost)
    sharpe_per_trade: float      # mean/std of per-trade R (not annualized)
    max_drawdown_R: float        # worst peak-to-trough on the cumulative R curve
    best_trade_R: float
    worst_trade_R: float

    def as_dict(self) -> dict[str, float]:
        return {
            "n": self.n,
            "expectancy_R": round(self.expectancy_R, 4),
            "total_R": round(self.total_R, 2),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "sharpe_per_trade": round(self.sharpe_per_trade, 4),
            "max_drawdown_R": round(self.max_drawdown_R, 2),
            "best_trade_R": round(self.best_trade_R, 4),
            "worst_trade_R": round(self.worst_trade_R, 4),
        }


def _pnl_array(trades: list[Trade]) -> np.ndarray:
    return np.array([t.pnl_R for t in trades], dtype=float)


def max_drawdown_R(pnl: np.ndarray) -> float:
    if pnl.size == 0:
        return 0.0
    curve = np.cumsum(pnl)
    peak = np.maximum.accumulate(curve)
    return float((curve - peak).min())


def compute(trades: list[Trade]) -> Metrics:
    pnl = _pnl_array(trades)
    n = pnl.size
    if n == 0:
        return Metrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    pf = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")
    std = pnl.std(ddof=1) if n > 1 else 0.0
    return Metrics(
        n=n,
        expectancy_R=float(pnl.mean()),
        total_R=float(pnl.sum()),
        win_rate=float((pnl > 0).mean()),
        profit_factor=pf,
        sharpe_per_trade=float(pnl.mean() / std) if std > 0 else 0.0,
        max_drawdown_R=max_drawdown_R(pnl),
        best_trade_R=float(pnl.max()),
        worst_trade_R=float(pnl.min()),
    )
