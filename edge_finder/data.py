"""Data loading.

Three realities:
  1. On YOUR machine the network is open, so load_vix_spy() can pull real daily
     VIX + SPY history via yfinance (pip install yfinance).
  2. If you have Databento daily/underlying data, point load_ohlcv_csv() at it.
  3. Inside the Claude sandbox the market-data hosts are firewalled, so
     synthetic_vix_spy() builds a *clearly labeled* stand-in series that lets the
     whole pipeline run end to end. Its numbers are NOT an edge — they exist only
     to prove the plumbing. Swap in real data for a real answer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DataSplit


def load_ohlcv_csv(path: str, tz: str | None = "America/New_York") -> pd.DataFrame:
    """Generic OHLCV loader. Expects a 'datetime' (or 'date') column plus
    open/high/low/close and optionally volume."""
    df = pd.read_csv(path)
    dtcol = "datetime" if "datetime" in df.columns else "date"
    df[dtcol] = pd.to_datetime(df[dtcol], utc=True)
    df = df.sort_values(dtcol).drop_duplicates(dtcol).set_index(dtcol)
    if tz:
        df.index = df.index.tz_convert(tz)
    df.index.name = "datetime"
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=[c for c in ["close"] if c in df.columns])


def load_vix_spy() -> pd.DataFrame:
    """Real daily VIX (implied) + SPY (underlying) close history via yfinance.
    Returns columns: ['spy_close', 'vix']. Runs on an open network only."""
    try:
        import yfinance as yf
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "yfinance not installed. Run: pip install yfinance\n"
            "(Inside the Claude sandbox the data hosts are blocked — use "
            "synthetic_vix_spy() there, and run this on your own machine.)"
        ) from e
    raw = yf.download(["^VIX", "SPY"], auto_adjust=True, progress=False)
    close = raw["Close"].rename(columns={"^VIX": "vix", "SPY": "spy_close"})
    out = close[["spy_close", "vix"]].dropna()
    out.index = pd.to_datetime(out.index)
    out.index.name = "datetime"
    return out


def synthetic_vix_spy(years: int = 16, seed: int = 7) -> pd.DataFrame:
    """A labeled stand-in for VIX + SPY daily data so the pipeline runs where the
    real feed is unavailable. Builds SPY as GBM with stochastic volatility, and
    VIX as realized vol plus a positive premium and noise — so a volatility risk
    premium EXISTS by construction. This demonstrates the machinery; it is not
    evidence about real markets. The '.attrs' flag marks it synthetic.
    """
    rng = np.random.default_rng(seed)
    n = years * 252
    idx = pd.bdate_range("2009-01-02", periods=n)

    # stochastic (mean-reverting) instantaneous vol, annualized
    vol = np.empty(n)
    vol[0] = 0.16
    for t in range(1, n):
        shock = rng.normal(0, 0.015)
        vol[t] = abs(0.95 * vol[t - 1] + 0.05 * 0.16 + shock)
    vol = np.clip(vol, 0.07, 0.80)

    daily_sigma = vol / np.sqrt(252)
    drift = 0.07 / 252
    rets = rng.normal(drift, 1.0, n) * daily_sigma
    spy = 90.0 * np.exp(np.cumsum(rets))

    # VIX = forward-ish implied vol = local vol scaled up by a premium + noise,
    # floored, in vol points. The premium is what makes selling vol pay.
    premium = 1.0 + rng.normal(0.04, 0.02, n).clip(-0.02, None)  # ~ +4% mult
    vix = np.clip(vol * 100.0 * premium + rng.normal(0, 1.2, n), 8.0, 90.0)

    out = pd.DataFrame({"spy_close": spy, "vix": vix}, index=idx)
    out.index.name = "datetime"
    out.attrs["synthetic"] = True
    return out


def slice_split(df: pd.DataFrame, which: str, split: DataSplit) -> pd.DataFrame:
    """Return the develop / validate / holdout slice by name."""
    lo, hi = getattr(split, which)
    idx = df.index
    naive = idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
    mask = (naive >= pd.Timestamp(lo)) & (naive <= pd.Timestamp(hi))
    return df.loc[mask]
