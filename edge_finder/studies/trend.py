"""Study 3 - Time-Series Momentum (trend following) across diversified markets.

The economic idea: markets trend. Prices that have risen over the past ~12 months
tend to keep rising, and vice versa - a persistent anomaly documented across
decades and asset classes (Moskowitz-Ooi-Pedersen; AQR). You get paid partly as a
risk premium (you provide liquidity to hedgers and ride slow information
diffusion) and partly from behavioral under-reaction. Crucially, trend following
is long volatility in character: it tends to make its best money in sustained
dislocations - which is exactly the 2022-style grinding bear that KILLED the VRP
put-spread sleeve. That complementarity is the whole point of pairing them.

What makes it robust is DIVERSIFICATION across weakly-correlated markets, not a
clever signal on one. The ES research only ever traded 3 correlated equity indices
+ one bond; this trades equities, intl, bonds, gold, commodities and the dollar.

Mechanics (frozen):
  - Universe: a basket of markets (ETF proxies that map to micro futures).
  - Signal at each month-end: sign of the trailing `lookback_days` total return
    (classic 12-month TSMOM), using only past data.
  - Vol targeting: size each position so each market risks the same - scale by
    target_vol / trailing realized vol (leverage capped). This equalizes risk so
    no single market dominates, and is how real trend books are run.
  - Hold one month, then re-evaluate.
  - Unit: 1R = the per-position monthly vol target. pnl_R for an (asset, month)
    reduces to  signal * (next-month return / trailing monthly vol)  - i.e. the
    market's forward move in units of its own risk, signed by the trend. Pooling
    all (asset, month) pairs gives a large, comparable sample for the gates.
  - A portfolio line (equal-risk average across markets each month) reports the
    DIVERSIFIED result - higher Sharpe, shallower drawdown than any one market.

Costs: a few bps of turnover per rebalance, charged in R.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DEFAULT, Config, DataSplit
from ..strategy import Strategy


class TimeSeriesMomentum(Strategy):
    def __init__(
        self,
        lookback_days: int = 252,
        vol_lookback_days: int = 63,
        target_ann_vol: float = 0.10,
        max_leverage: float = 3.0,
        cost_bps: float = 2.0,
        cfg: Config = DEFAULT,
    ):
        self.lb = lookback_days
        self.vlb = vol_lookback_days
        self.target_ann = target_ann_vol
        self.max_lev = max_leverage
        self.cost_bps = cost_bps
        self.cfg = cfg
        self.name = f"TSMOM {lookback_days//21}m-trend, {int(target_ann_vol*100)}% vol-target"

    COLUMNS = ["entry_time", "exit_time", "direction", "gross_R", "cost_R",
               "asset", "signal", "fwd_ret", "pos_ret"]

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        # data: wide daily closes, index=date, columns=assets
        px = data.sort_index().astype(float)
        me = px.resample("ME").last()                 # month-end closes
        target_m = self.target_ann / np.sqrt(12.0)    # monthly vol target => 1R
        daily_ret = px.pct_change()

        rows = []
        prev_sig = {c: 0 for c in px.columns}
        months = me.index
        for i in range(len(months) - 1):
            t, t1 = months[i], months[i + 1]
            for c in px.columns:
                hist = px[c].loc[:t].dropna()
                if len(hist) < self.lb + 5:
                    continue
                # trailing total return over lookback (causal)
                trail = hist.iloc[-1] / hist.iloc[-self.lb] - 1.0
                signal = 1 if trail > 0 else -1
                # trailing realized monthly vol
                dr = daily_ret[c].loc[:t].dropna().iloc[-self.vlb:]
                if len(dr) < self.vlb // 2:
                    continue
                rv_m = float(dr.std() * np.sqrt(21.0))
                if not np.isfinite(rv_m) or rv_m <= 0:
                    continue
                size = min(target_m / rv_m, self.max_lev)
                p0, p1 = me[c].get(t), me[c].get(t1)
                if p0 is None or p1 is None or not np.isfinite(p0) or not np.isfinite(p1) or p0 <= 0:
                    continue
                fwd = p1 / p0 - 1.0
                pos_ret = size * signal * fwd
                gross_R = pos_ret / target_m
                # turnover cost: charge when signal changes (full flip) or always a touch
                turn = 2.0 if signal != prev_sig[c] else 0.3
                cost_R = (self.cost_bps / 1e4) * size * turn / target_m
                prev_sig[c] = signal
                rows.append({
                    "entry_time": t, "exit_time": t1, "direction": signal,
                    "gross_R": gross_R, "cost_R": cost_R, "asset": c,
                    "signal": signal, "fwd_ret": fwd, "pos_ret": pos_ret,
                })
        return pd.DataFrame(rows, columns=self.COLUMNS)


def portfolio_summary(trades, target_ann_vol=0.10):
    """Build the equal-risk diversified portfolio: average position pnl across
    markets each month. Reports the benefit of diversification."""
    if not trades:
        print("  (no trades)")
        return
    df = pd.DataFrame([{"month": t.exit_time, "R": t.pnl_R} for t in trades])
    port = df.groupby("month")["R"].mean().sort_index()   # mean R across assets
    curve = port.cumsum()
    peak = curve.cummax()
    maxdd = float((curve - peak).min())
    ann = port.mean() * 12
    vol = port.std() * np.sqrt(12)
    sharpe = float(ann / vol) if vol > 0 else 0.0
    pos = (port > 0).mean()
    print("  DIVERSIFIED PORTFOLIO (equal-risk average across markets, monthly)")
    print(f"    months {len(port)}   mean {port.mean():+.3f} R/mo   "
          f"ann {ann:+.2f} R   Sharpe {sharpe:.2f}")
    print(f"    positive months {pos:.0%}   max drawdown {maxdd:.1f} R")
    # yearly
    yr = port.groupby(port.index.year).sum()
    cells = "  ".join(f"{y}:{v:+.1f}" for y, v in yr.items())
    print(f"    by year (R): {cells}")


def worst_best_years(trades):
    df = pd.DataFrame([{"y": t.exit_time.year, "R": t.pnl_R} for t in trades])
    byyear = df.groupby("y")["R"].mean()
    print("  trend edge by year (mean R/trade across all markets):")
    print("    " + "  ".join(f"{y}:{v:+.3f}" for y, v in byyear.items()))


def _load(source, csv):
    from .. import data as D
    if source == "yahoo":
        return D.load_daily_closes()
    if source == "csv":
        if not csv:
            raise SystemExit("--csv required with --source csv (wide daily closes)")
        df = pd.read_csv(csv)
        dtc = "date" if "date" in df.columns else df.columns[0]
        df[dtc] = pd.to_datetime(df[dtc])
        return df.set_index(dtc).sort_index()
    return D.synthetic_multi_asset()


def main(argv=None):
    import argparse
    from ..runner import evaluate, print_report
    from .. import data as D

    p = argparse.ArgumentParser(description="Time-series momentum (trend) sleeve")
    p.add_argument("--source", choices=["synthetic", "yahoo", "csv"], default="synthetic")
    p.add_argument("--csv", default=None)
    p.add_argument("--lookback", type=int, default=252)
    p.add_argument("--target-vol", type=float, default=0.10)
    args = p.parse_args(argv)

    px = _load(args.source, args.csv)
    if px.attrs.get("synthetic"):
        print("\n*** SYNTHETIC DATA - plumbing demo only, NOT a real edge. ***")
        print("*** Run with --source yahoo (pip install yfinance) for real markets. ***\n")

    cfg = DEFAULT
    # Trend data (ETF universe) begins ~2007. Hold out 2021-2025, which INCLUDES
    # the 2022 bear - the regime where trend following should earn its keep and
    # the VRP sleeve failed. That contrast is the thesis.
    tsplit = DataSplit(develop=("2007-01-01", "2016-12-31"),
                       validate=("2017-01-01", "2020-12-31"),
                       holdout=("2021-01-01", "2025-12-31"))

    strat = TimeSeriesMomentum(lookback_days=args.lookback,
                               target_ann_vol=args.target_vol, cfg=cfg)
    full = strat.to_trades(px)
    rep = evaluate(full, strat.name + " | FULL SAMPLE (in-sample)", cfg)
    print_report(rep)
    worst_best_years(full)
    print()
    portfolio_summary(full, args.target_vol)
    print()
    print("  PROTECTED SPLIT (develop 2007-16 -> validate 2017-20 -> holdout 2021-25, incl. 2022 bear)")
    for stage in ("develop", "validate", "holdout"):
        sub = D.slice_split(px, stage, tsplit)
        if sub.empty or len(sub) < args.lookback + 30:
            print(f"    [{stage}] insufficient data in window")
            continue
        st = evaluate(strat.to_trades(sub), f"{strat.name} | {stage.upper()}", cfg)
        md = st.metrics.as_dict()
        nf = sum(1 for g in st.gates if not g.passed)
        flag = "SURVIVOR" if st.survivor else "rejected"
        print(f"    [{stage:<8}] n={md['n']:>4}  exp {md['expectancy_R']:+.3f}R"
              f"  PF {md['profit_factor']:.2f}  maxDD {md['max_drawdown_R']:.1f}R"
              f"  gates failed: {nf}/{len(st.gates)}  -> {flag}")
    print("=" * 64)


if __name__ == "__main__":
    main()
