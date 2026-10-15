"""Study 4 - combine the two validated sleeves into one book.

The whole project points here. Two edges that each pass their own tests but fail
in OPPOSITE regimes:
  - VRP put-spread (short vol): income in calm/bull markets, bleeds in bears.
  - Time-series momentum (long vol): profits in bears/crises, chops in calm.

If their monthly returns are weakly or negatively correlated, a blend has a higher
Sharpe and a shallower drawdown than either alone - the only real free lunch in
investing. This study measures that directly: it builds each sleeve's monthly
return stream, aligns them on their common period, reports the correlation, and
constructs a risk-parity blend (each sleeve scaled to the same volatility, then
averaged), with the combined Sharpe, drawdown, by-year, and the regime-offset
table that shows one sleeve carrying the other.

Honest scope: the VRP stream here is 2016-2023 (OptionsDX free EOD); the trend
stream is longer but the blend is measured only on the overlap. This is a
portfolio-construction look, not a new edge - no new gates, because the sleeves
were already gated individually.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DEFAULT
from .vrp_options import VRPPutSpread
from .trend import TimeSeriesMomentum


def _monthly_R(trades) -> pd.Series:
    """Mean R per calendar month across a sleeve's trades (its monthly P&L in R)."""
    if not trades:
        return pd.Series(dtype=float)
    df = pd.DataFrame([{"m": pd.Timestamp(t.exit_time).to_period("M"), "R": t.pnl_R}
                       for t in trades])
    s = df.groupby("m")["R"].mean()
    s.index = s.index.to_timestamp()
    return s.sort_index()


def _stats(x: pd.Series, ann: int = 12) -> dict:
    if len(x) < 2 or x.std() == 0:
        return {"ann": float(x.sum()), "vol": 0.0, "sharpe": 0.0, "maxdd": 0.0,
                "pos": float((x > 0).mean()) if len(x) else 0.0}
    curve = x.cumsum()
    dd = float((curve - curve.cummax()).min())
    return {
        "ann": float(x.mean() * ann),
        "vol": float(x.std() * np.sqrt(ann)),
        "sharpe": float(x.mean() / x.std() * np.sqrt(ann)),
        "maxdd": dd,
        "pos": float((x > 0).mean()),
    }


def _line(name, s):
    st = _stats(s)
    print(f"  {name:<26} ann {st['ann']:+.2f} R  vol {st['vol']:.2f}  "
          f"Sharpe {st['sharpe']:+.2f}  maxDD {st['maxdd']:.1f} R  pos {st['pos']:.0%}")
    return st


def main(argv=None):
    import argparse
    from .. import data as D

    p = argparse.ArgumentParser(description="Combine VRP + trend into one book")
    p.add_argument("--options-path", required=True,
                   help="dir of OptionsDX SPY EOD files (for the VRP sleeve)")
    p.add_argument("--trend-source", choices=["yahoo", "csv"], default="yahoo")
    p.add_argument("--trend-csv", default=None)
    p.add_argument("--vrp-trend-sma", type=int, default=200,
                   help="200 = filtered VRP (standalone-safe); 0 = UNFILTERED VRP "
                        "(let the trend sleeve cover bears instead of the filter)")
    args = p.parse_args(argv)

    cfg = DEFAULT

    # ---- sleeve 1: VRP put-spread ----
    sma = args.vrp_trend_sma if args.vrp_trend_sma and args.vrp_trend_sma > 0 else None
    tag = f"+{sma}DMA filter" if sma else "UNFILTERED (trend covers bears)"
    print(f"Building VRP sleeve (0.30/0.15 put spread, weekly, {tag})...")
    opt = D.load_eod_options(args.options_path)
    vrp = VRPPutSpread(target_dte=30, short_delta=0.30, long_delta=0.15,
                       entry_every_days=7, richness_threshold=None,
                       trend_filter_sma=sma, cfg=cfg)
    vrp_m = _monthly_R(vrp.to_trades(opt))

    # ---- sleeve 2: time-series momentum ----
    print("Building trend sleeve (12m TSMOM, diversified, 10% vol target)...")
    px = D.load_daily_closes() if args.trend_source == "yahoo" else \
        pd.read_csv(args.trend_csv, parse_dates=[0], index_col=0)
    tsmom = TimeSeriesMomentum(cfg=cfg)
    trend_tr = tsmom.to_trades(px)
    trend_m = (pd.DataFrame([{"m": pd.Timestamp(t.exit_time).to_period("M"), "R": t.pnl_R}
                             for t in trend_tr])
               .groupby("m")["R"].mean())
    trend_m.index = trend_m.index.to_timestamp()
    trend_m = trend_m.sort_index()

    # ---- align on the common period ----
    both = pd.concat({"VRP": vrp_m, "TREND": trend_m}, axis=1, sort=True).dropna()
    if len(both) < 12:
        raise SystemExit(f"Only {len(both)} overlapping months; need more overlap.")
    lo, hi = both.index[0].date(), both.index[-1].date()
    corr = float(both["VRP"].corr(both["TREND"]))

    print("\n" + "=" * 64)
    print(f" TWO-SLEEVE BOOK  |  common period {lo} -> {hi}  ({len(both)} months)")
    print("=" * 64)
    print(f"  Correlation(VRP, TREND) monthly returns: {corr:+.2f}"
          + ("   (negatively correlated - ideal)" if corr < 0 else
             "   (low correlation - good)" if corr < 0.3 else
             "   (higher than hoped)"))
    print()

    # standardize each sleeve to the SAME volatility (risk parity), then blend 50/50
    def unit_vol(s):
        return s / s.std() if s.std() > 0 else s
    vrp_rp = unit_vol(both["VRP"])
    trend_rp = unit_vol(both["TREND"])
    blend = 0.5 * vrp_rp + 0.5 * trend_rp

    print("  STANDALONE (risk-normalized to compare fairly):")
    s_v = _line("VRP sleeve", vrp_rp)
    s_t = _line("Trend sleeve", trend_rp)
    print()
    print("  COMBINED (risk-parity 50/50):")
    s_b = _line("Two-sleeve book", blend)

    lift = s_b["sharpe"] - max(s_v["sharpe"], s_t["sharpe"])
    dd_better = s_b["maxdd"] - max(s_v["maxdd"], s_t["maxdd"])  # less negative = better
    print()
    print(f"  Sharpe lift over the better single sleeve: {lift:+.2f}")
    print(f"  Combined max drawdown vs the better single sleeve: "
          f"{s_b['maxdd']:.1f} vs {max(s_v['maxdd'], s_t['maxdd']):.1f} R")

    # regime-offset table: years where the sleeves pulled in opposite directions
    print("\n  REGIME OFFSET (standardized R by year; watch for one carrying the other)")
    yv = vrp_rp.groupby(vrp_rp.index.year).sum()
    yt = trend_rp.groupby(trend_rp.index.year).sum()
    yb = blend.groupby(blend.index.year).sum()
    print(f"    {'year':<6}{'VRP':>8}{'TREND':>8}{'BOOK':>8}")
    for y in sorted(set(yv.index) | set(yt.index)):
        v, t, b = yv.get(y, 0.0), yt.get(y, 0.0), yb.get(y, 0.0)
        flag = "  <- offset" if (v < 0 < t) or (t < 0 < v) else ""
        print(f"    {y:<6}{v:>8.1f}{t:>8.1f}{b:>8.1f}{flag}")
    print("=" * 64)
    print("\nNote: risk-normalized units compare SHAPE, not dollar returns. The point"
          "\nis the Sharpe lift and drawdown reduction from combining, plus how often"
          "\none sleeve is green while the other is red (the offset).")


if __name__ == "__main__":
    main()
