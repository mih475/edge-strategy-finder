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


def _pick_close_frame(raw: "pd.DataFrame") -> "pd.DataFrame":
    """Return a 2-column frame of closing prices for SPY and ^VIX, robust to the
    several shapes yfinance has shipped across versions:
      - MultiIndex columns (field, ticker) with group_by='column' (the default)
      - MultiIndex columns (ticker, field) with group_by='ticker'
      - flat columns for a single ticker
    """
    cols = raw.columns
    if isinstance(cols, pd.MultiIndex):
        lvl0 = set(cols.get_level_values(0))
        if "Close" in lvl0:                 # (field, ticker)
            close = raw["Close"]
        else:                               # (ticker, field)
            close = raw.xs("Close", axis=1, level=1)
    else:
        close = raw  # flat; assume already close-like
    return close


def load_vix_spy() -> pd.DataFrame:
    """Real daily VIX (implied) + SPY (underlying) close history via yfinance.
    Returns columns: ['spy_close', 'vix']. Runs on an open network only.

    Hardened against yfinance's shifting column layouts: we locate the SPY and
    VIX columns by name-matching rather than assuming an exact label, then assert
    the result is non-empty so a silent download failure surfaces clearly instead
    of producing an empty frame downstream.
    """
    try:
        import yfinance as yf
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "yfinance not installed. Run: pip install yfinance\n"
            "(Inside the Claude sandbox the data hosts are blocked - use "
            "synthetic_vix_spy() there, and run this on your own machine.)"
        ) from e

    # Pulling full history is load-bearing: recent yfinance defaults to a SHORT
    # window (~1 month) when no period/start is given, which silently starves the
    # study. We try an explicit start date first (most reliable across versions),
    # then fall back to period="max".
    raw = yf.download(["^VIX", "SPY"], start="2004-01-01", auto_adjust=True,
                      progress=False)
    if raw is None or len(raw) < 300:
        raw = yf.download(["^VIX", "SPY"], period="max", auto_adjust=True,
                          progress=False)
    if raw is None or len(raw) == 0:
        raise RuntimeError(
            "yfinance returned no rows for ^VIX/SPY. This is usually a transient "
            "rate-limit or network issue - wait a minute and retry, or upgrade: "
            "pip install -U yfinance."
        )

    close = _pick_close_frame(raw)
    # locate columns by name, case-insensitive, so label quirks don't matter
    spy_col = vix_col = None
    for c in close.columns:
        name = str(c).upper()
        if "SPY" in name and spy_col is None:
            spy_col = c
        if "VIX" in name and vix_col is None:
            vix_col = c
    if spy_col is None or vix_col is None:
        raise RuntimeError(
            f"Could not find SPY and VIX columns in yfinance output; got "
            f"{list(close.columns)}. Upgrade yfinance or load via --source csv."
        )

    out = pd.DataFrame({
        "spy_close": pd.to_numeric(close[spy_col], errors="coerce"),
        "vix": pd.to_numeric(close[vix_col], errors="coerce"),
    }).dropna()
    out.index = pd.to_datetime(out.index)
    out.index.name = "datetime"
    if len(out) < 300:
        raise RuntimeError(
            f"Only {len(out)} clean rows of VIX+SPY - too few to test. The "
            "download likely came back partial; retry or upgrade yfinance."
        )
    print(f"[data] loaded {len(out)} daily rows, "
          f"{out.index[0].date()} -> {out.index[-1].date()}")
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


# ---------------------------------------------------------------------------
# End-of-day options chains (for the real-fills VRP study).
# ---------------------------------------------------------------------------
def load_eod_options(path: str) -> pd.DataFrame:
    """Load end-of-day option chains from OptionsDX-style CSV(s) into a tidy
    long frame. `path` may be a single .csv/.txt file or a directory of them
    (one per month/year is the usual OptionsDX layout); all are concatenated.

    OptionsDX columns arrive bracketed and space-padded, e.g. '[P_BID]', with a
    row per (quote_date, expiry, strike). We normalize names and keep only the
    put-side fields the VRP study needs. Returns columns:
        quote_date, underlying, expire_date, dte, strike,
        p_bid, p_ask, p_delta, p_iv
    """
    import glob
    import os

    files = []
    if os.path.isdir(path):
        for ext in ("*.csv", "*.txt"):
            files.extend(sorted(glob.glob(os.path.join(path, "**", ext),
                                          recursive=True)))
    else:
        files = [path]
    if not files:
        raise RuntimeError(f"No .csv/.txt option files found under {path!r}")

    def norm(c: str) -> str:
        return c.strip().strip("[]").strip().lower()

    aliases = {
        "quote_date": ["quote_date", "date"],
        "underlying": ["underlying_last", "underlying", "stock_price"],
        "expire_date": ["expire_date", "expiration", "exp_date"],
        "dte": ["dte"],
        "strike": ["strike"],
        "p_bid": ["p_bid", "put_bid", "bid_p"],
        "p_ask": ["p_ask", "put_ask", "ask_p"],
        "p_delta": ["p_delta", "put_delta"],
        "p_iv": ["p_iv", "put_iv", "p_volatility"],
    }

    frames = []
    for fp in files:
        # Read only the 9 columns we need (of ~33), by name, to keep memory sane
        # across multi-GB datasets. We read the header first to map normalized
        # names back to each file's exact (bracketed, space-padded) spelling.
        header = pd.read_csv(fp, nrows=0, skipinitialspace=True)
        norm_to_orig = {norm(c): c for c in header.columns}
        colmap = {}          # want -> original column spelling
        for want, al in aliases.items():
            for a in al:
                if a in norm_to_orig:
                    colmap[want] = norm_to_orig[a]
                    break
        missing = {"quote_date", "underlying", "expire_date", "strike",
                   "p_bid", "p_ask"} - set(colmap)
        if missing:
            raise RuntimeError(
                f"{os.path.basename(fp)}: missing required option columns "
                f"{missing}. Got {list(norm_to_orig)[:12]}..."
            )
        usecols = list(colmap.values())
        raw = pd.read_csv(fp, usecols=usecols, low_memory=False,
                          skipinitialspace=True)
        sub = raw.rename(columns={v: k for k, v in colmap.items()})
        # Normalize IV to PERCENTAGE POINTS per file: OptionsDX changed its IV
        # convention across years (decimal 0.22 vs percent 22.0), so decide this
        # file-by-file, where the convention is internally consistent.
        if "p_iv" in sub.columns:
            iv = pd.to_numeric(sub["p_iv"], errors="coerce")
            if iv.notna().any() and float(iv.median()) < 3.0:
                sub["p_iv"] = iv * 100.0
            else:
                sub["p_iv"] = iv
        frames.append(sub)

    df = pd.concat(frames, ignore_index=True)
    df["quote_date"] = pd.to_datetime(df["quote_date"], errors="coerce")
    df["expire_date"] = pd.to_datetime(df["expire_date"], errors="coerce")
    for c in ["underlying", "strike", "p_bid", "p_ask", "p_delta", "p_iv", "dte"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "dte" not in df.columns:
        df["dte"] = (df["expire_date"] - df["quote_date"]).dt.days
    df = df.dropna(subset=["quote_date", "expire_date", "strike",
                           "underlying", "p_bid", "p_ask"])
    df = df.sort_values(["quote_date", "expire_date", "strike"]).reset_index(drop=True)
    print(f"[data] loaded {len(df):,} option rows across "
          f"{df['quote_date'].nunique()} quote dates, "
          f"{df['quote_date'].min().date()} -> {df['quote_date'].max().date()}")
    return df


# ---------------------------------------------------------------------------
# Multi-asset daily closes (for the trend-following sleeve).
# ---------------------------------------------------------------------------
# Liquid ETF proxies spanning asset classes, each mapping to a micro future you
# could actually trade. Trend following needs DIVERSIFIED, weakly-correlated
# markets - that is where its robustness comes from, unlike the 3 correlated
# equity indices in the ES research.
TREND_UNIVERSE = {
    "SPY": "US large-cap equity   (-> MES)",
    "IWM": "US small-cap equity   (-> M2K)",
    "EFA": "developed intl equity (-> no micro; research proxy)",
    "TLT": "long US Treasuries    (-> micro 10y/ZN)",
    "GLD": "gold                  (-> MGC)",
    "DBC": "broad commodities     (-> no micro; research proxy)",
    "UUP": "US dollar index       (-> M6E inverse)",
}


def load_daily_closes(tickers: list[str] | None = None) -> pd.DataFrame:
    """Wide frame of daily adjusted closes (index=date, columns=tickers) via
    yfinance. Open-network only; inside the sandbox use synthetic_multi_asset()."""
    tickers = tickers or list(TREND_UNIVERSE)
    try:
        import yfinance as yf
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pip install yfinance (run on your own machine).") from e
    raw = yf.download(tickers, start="2004-01-01", auto_adjust=True, progress=False)
    if raw is None or len(raw) == 0:
        raise RuntimeError("yfinance returned no rows; retry or upgrade yfinance.")
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) and "Close" in raw.columns.get_level_values(0) else raw
    close = close.dropna(how="all").sort_index()
    close.index = pd.to_datetime(close.index)
    close.index.name = "date"
    keep = [t for t in tickers if t in close.columns]
    close = close[keep]
    print(f"[data] loaded {close.shape[1]} assets x {len(close)} days, "
          f"{close.index[0].date()} -> {close.index[-1].date()}")
    return close


def synthetic_multi_asset(years: int = 18, seed: int = 7) -> pd.DataFrame:
    """Labeled stand-in: several weakly-correlated assets, some with persistent
    trends (so time-series momentum has something real to capture), some noisier.
    NOT an edge - plumbing only. Swap in load_daily_closes() for a real answer."""
    rng = np.random.default_rng(seed)
    n = years * 252
    idx = pd.bdate_range("2007-01-03", periods=n)
    names = ["AEQ", "BEQ", "CBOND", "DGOLD", "ECMD", "FFX"]
    cols = {}
    for k, name in enumerate(names):
        # regime-switching drift => trends that TSMOM can ride
        drift = np.zeros(n)
        t = 0
        while t < n:
            seg = rng.integers(40, 160)
            mu = rng.normal(0, 0.0006)
            drift[t:t + seg] = mu
            t += seg
        vol = (0.008 + 0.004 * rng.random())
        shocks = rng.normal(0, vol, n)
        # mild cross-correlation via a shared factor for the two equities
        px = 100 * np.exp(np.cumsum(drift + shocks))
        cols[name] = px
    df = pd.DataFrame(cols, index=idx)
    df.index.name = "date"
    df.attrs["synthetic"] = True
    return df
