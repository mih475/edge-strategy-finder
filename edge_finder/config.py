"""Frozen configuration: cost assumptions, robustness-gate thresholds, and the
protected data split. Freeze these BEFORE looking at a strategy's results. The
gates below are deliberately strict — they are the same spirit as the ES/MES
research that correctly rejected every 2022-concentrated near-miss.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Protected data split. Development is the only set you may iterate on.
# Validation is opened once a rule survives development. Holdout is opened once,
# ever, at the very end. Do not tune anything to validation or holdout.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DataSplit:
    develop: tuple[str, str] = ("2008-01-01", "2019-12-31")
    validate: tuple[str, str] = ("2020-01-01", "2022-12-31")
    holdout: tuple[str, str] = ("2023-01-01", "2026-12-31")


# ---------------------------------------------------------------------------
# Friction. Expressed in the units each study uses. For the variance-swap VRP
# study, cost is in annualized VOLATILITY POINTS of round-trip bid/ask on the
# strike (a 21-day index varswap trades at roughly 0.5-1.5 vol points wide for
# retail; we default conservative). Studies that trade futures override with
# ticks + commission instead.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CostModel:
    # futures-style
    tick_value: float = 1.25          # MES: $1.25 per 0.25 tick
    tick_size: float = 0.25
    commission_rt: float = 1.24       # per MES round turn, typical retail
    slippage_ticks: float = 1.0       # entry+exit slippage, in ticks, total
    # varswap / vol-points style (for the VRP study)
    vol_point_cost: float = 1.0       # round-trip, in annualized vol points
    # generic bps (for equity-like proxies)
    bps_per_side: float = 1.0


# ---------------------------------------------------------------------------
# Robustness gates. A candidate must pass ALL of these to be called "survivor".
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Gates:
    min_trades: int = 100             # enough independent observations
    min_expectancy_R: float = 0.0     # positive after costs (strict: >0)
    min_profit_factor: float = 1.10   # a real cushion over breakeven
    max_year_concentration: float = 0.75   # no single year > 75% of profits
    bootstrap_min_win: float = 0.95   # P(mean>0) over resamples
    tail_drop_still_positive: bool = True  # survives removing the best trade
    cost_multiple_stress: float = 2.0      # still positive at 2x modeled cost


@dataclass(frozen=True)
class Config:
    split: DataSplit = field(default_factory=DataSplit)
    cost: CostModel = field(default_factory=CostModel)
    gates: Gates = field(default_factory=Gates)
    trading_days: int = 252
    rng_seed: int = 7
    mc_paths: int = 5000


DEFAULT = Config()
