"""Study 5 - short-term mean reversion on SPY (the one real hint from the Reddit
confluence buckets: strong "bearish" days were followed by bounces).

Unlike the confluence vote (which had no directional edge), this tests a SPECIFIC,
documented anomaly: after a sharp short-term drop WITHIN an ongoing uptrend, a
liquid index tends to snap back over the next few days. It is a behavioral
liquidity-provision effect (panic sellers pay up to get out; you get paid to take
the other side), and it is the basis of the well-known Connors RSI(2) system.

Two things make it a fair test rather than curve-fitting:
  * LONG-ONLY with a regime filter. The repo already showed the short leg is a
    drag on long-biased equities, so we never short. We only buy dips while the
    index is above its 200-day average (i.e. "buy the dip in a bull market").
  * ONE frozen base spec, run through the same gates + protected split as
    everything else. No threshold sweep.

Base spec (frozen):
  entry  : at close when RSI(2) < `rsi_entry` (default 10) AND close > SMA200
  exit   : at close when close > SMA5 (short-term mean reclaimed),
           or after `max_hold` days (default 6) as a backstop
  one position at a time (no pyramiding); 1R = trailing 20-day daily vol at
  entry, so results are comparable to the other studies; long-only (direction +1)
  cost   : `cost_bps` per side on the underlying, round-trip, charged in R.

Optional VIX-spike variant (--mode vixfade): same long-only/above-200d structure
but the trigger is a VIX spike (VIX > `vix_spike_mult` x its 20-day average)
instead of RSI(2). Tests whether fading fear pays on the index.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DEFAULT, Config
from ..strategy import Strategy
from .reddit_spy import _rsi


class ShortTermMeanReversion(Strategy):
    def __init__(
        self,
        mode: str = "rsi2",            # "rsi2" | "vixfade"
        rsi_entry: float = 10.0,
        rsi_period: int = 2,
        trend_sma: int = 200,
        exit_sma: int = 5,
        max_hold: int = 6,
        vix_spike_mult: float = 1.20,
        vol_lookback: int = 20,
        cost_bps: float = 1.0,
        cfg: Config = DEFAULT,
    ):
        if mode not in ("rsi2", "vixfade"):
            raise ValueError("mode must be 'rsi2' or 'vixfade'")
        self.mode = mode
        self.rsi_entry = rsi_entry
        self.rsi_period = rsi_period
        self.trend_sma = trend_sma
        self.exit_sma = exit_sma
        self.max_hold = max_hold
        self.vix_spike_mult = vix_spike_mult
        self.vlb = vol_lookback
        self.cost_bps = cost_bps
        trig = (f"RSI({rsi_period})<{rsi_entry:g}" if mode == "rsi2"
                else f"VIX>{vix_spike_mult:g}x20dMA")
        self.name = (f"SPY mean-reversion long-only [{trig} & >SMA{trend_sma}, "
                     f"exit>SMA{exit_sma}/{max_hold}d, {cost_bps:g}bp/side]")

    COLUMNS = ["entry_time", "exit_time", "direction", "gross_R", "cost_R",
               "hold_days", "entry_px", "exit_px", "trigger"]

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        px = data.sort_index().copy()
        if "spy_close" not in px.columns and "close" in px.columns:
            px = px.rename(columns={"close": "spy_close"})
        c = px["spy_close"].astype(float)

        sma_trend = c.rolling(self.trend_sma).mean()
        sma_exit = c.rolling(self.exit_sma).mean()
        rsi = _rsi(c, self.rsi_period)
        ret = c.pct_change()
        vol = ret.rolling(self.vlb).std()

        if self.mode == "vixfade":
            if "vix" not in px.columns:
                raise ValueError("vixfade mode needs a 'vix' column")
            vix = px["vix"].astype(float)
            vix_ma = vix.rolling(20).mean()
            trigger = (vix > self.vix_spike_mult * vix_ma)
            trig_label = "vix_spike"
        else:
            trigger = (rsi < self.rsi_entry)
            trig_label = "rsi2_low"

        idx = c.index
        n = len(idx)
        rows = []
        i = 0
        # warm-up: need the longest lookback available
        warm = max(self.trend_sma, self.vlb, 20) + 2
        while i < n - 1:
            t = idx[i]
            if i < warm or not np.isfinite(vol.iloc[i]) or vol.iloc[i] <= 0:
                i += 1
                continue
            long_ok = np.isfinite(sma_trend.iloc[i]) and c.iloc[i] > sma_trend.iloc[i]
            fire = bool(trigger.iloc[i]) and long_ok
            if not fire:
                i += 1
                continue
            # ENTER at close of day i
            entry_px = float(c.iloc[i])
            v = float(vol.iloc[i])
            # walk forward to exit
            j = i + 1
            exit_idx = None
            while j < n:
                held = j - i
                reclaimed = np.isfinite(sma_exit.iloc[j]) and c.iloc[j] > sma_exit.iloc[j]
                if reclaimed or held >= self.max_hold:
                    exit_idx = j
                    break
                j += 1
            if exit_idx is None:
                break  # ran off the end while in a position
            exit_px = float(c.iloc[exit_idx])
            gross_R = (exit_px / entry_px - 1.0) / v
            cost_R = (self.cost_bps / 1e4) * 2.0 / v
            rows.append({
                "entry_time": t, "exit_time": idx[exit_idx], "direction": 1,
                "gross_R": gross_R, "cost_R": cost_R,
                "hold_days": exit_idx - i, "entry_px": entry_px,
                "exit_px": exit_px, "trigger": trig_label,
            })
            i = exit_idx + 1   # one position at a time: resume after exit
        return pd.DataFrame(rows, columns=self.COLUMNS)


def hold_stats(trades) -> None:
    if not trades:
        print("  (no trades)"); return
    hd = np.array([t.meta["hold_days"] for t in trades])
    wins = np.array([t.pnl_R for t in trades]) > 0
    print(f"  avg hold {hd.mean():.1f} days (max {hd.max()})   win% {wins.mean():.1%}")


def by_year(trades) -> None:
    if not trades:
        print("  (no trades)"); return
    df = pd.DataFrame([{"y": t.exit_time.year, "R": t.pnl_R} for t in trades])
    yr = df.groupby("y")["R"].agg(["size", "sum"])
    print("  by year:  " + "  ".join(
        f"{y}:{row['sum']:+.1f}R(n={int(row['size'])})" for y, row in yr.iterrows()))


def _load(source, csv):
    from .reddit_spy import _load as rl
    return rl(source, csv)


def main(argv=None):
    import argparse
    from ..runner import evaluate, print_report
    from .. import data as D

    p = argparse.ArgumentParser(description="Short-term mean reversion on SPY")
    p.add_argument("--source", choices=["synthetic", "yahoo", "csv"], default="synthetic")
    p.add_argument("--csv", default=None)
    p.add_argument("--mode", choices=["rsi2", "vixfade"], default="rsi2")
    p.add_argument("--rsi-entry", type=float, default=10.0)
    p.add_argument("--max-hold", type=int, default=6)
    p.add_argument("--cost-bps", type=float, default=1.0)
    args = p.parse_args(argv)

    px = _load(args.source, args.csv)
    if px.attrs.get("synthetic"):
        print("\n*** SYNTHETIC DATA - plumbing only, NOT a real edge. ***\n")

    cfg = DEFAULT
    strat = ShortTermMeanReversion(mode=args.mode, rsi_entry=args.rsi_entry,
                                   max_hold=args.max_hold, cost_bps=args.cost_bps, cfg=cfg)
    full = strat.to_trades(px)
    rep = evaluate(full, strat.name + " | FULL SAMPLE (in-sample)", cfg)
    print_report(rep)
    print()
    hold_stats(full)
    by_year(full)
    print()
    print("  PROTECTED SPLIT (develop 1993-2014 -> validate 2015-19 -> holdout 2020-26)")
    for stage in ("develop", "validate", "holdout"):
        sub = D.slice_split(px, stage, cfg.split)
        if sub.empty or len(sub) < 250:
            print(f"    [{stage:<8}] insufficient data in window")
            continue
        st = evaluate(strat.to_trades(sub), f"{strat.name} | {stage.upper()}", cfg)
        md = st.metrics.as_dict()
        nf = sum(1 for g in st.gates if not g.passed)
        flag = "SURVIVOR" if st.survivor else "rejected"
        print(f"    [{stage:<8}] n={md['n']:>4}  exp {md['expectancy_R']:+.4f}R"
              f"  PF {md['profit_factor']:.2f}  win {md['win_rate']:.1%}"
              f"  maxDD {md['max_drawdown_R']:.1f}R  gates failed {nf}/{len(st.gates)}"
              f"  -> {flag}")
    print("=" * 64)


if __name__ == "__main__":
    main()
