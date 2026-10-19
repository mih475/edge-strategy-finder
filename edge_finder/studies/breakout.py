"""Study 7 - the chart-pattern BREAKOUT engine (the mechanic under most patterns).

Nearly every classical chart pattern (rectangle, triangle, flag, pennant, and the
reversals once the neckline goes) resolves to the SAME tradeable event: price
breaks a horizontal resistance (or support), you enter in the breakout direction,
put a protective stop on the far side of the range, and target the "measured move"
= the range height projected from the breakout (per the Fidelity/Kirkpatrick deck:
"a pattern is not complete until an actual breakout occurs").

So before hand-coding 20 fiddly detectors, we test the engine they all feed. Two
questions, in order of rigor:

  (A) INFORMATION TEST (Lo-Mamaysky-Wang style): after a mechanical N-day-high
      breakout, is the forward-return distribution DIFFERENT from the unconditional
      base rate? If not, the "pattern" carries no information - it's pareidolia,
      exactly what the Fidelity "Limits of Patterns" slide warns about. This needs
      only closes and no trade assumptions, so it's the cleanest read.

  (B) TRADEABLE TEST: the full breakout trade - entry on the breakout close,
      protective stop at the opposite side of the range (1R = that risk), target at
      +1x range height, time-stop after `max_hold` bars - run through the harness
      gates and protected split.

Causality: resistance/support use ONLY the prior N closes (shift(1)), so a signal
at day t uses nothing from day t. Data: daily SPY closes (vix_spy.csv). Close-only,
so stops/targets are evaluated on closes (no intrabar fills); noted as a limit.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from ..config import DEFAULT, Config
from ..strategy import Strategy


def _load_spy(csv: str) -> pd.Series:
    df = pd.read_csv(csv, parse_dates=["datetime"]).set_index("datetime").sort_index()
    col = "spy_close" if "spy_close" in df.columns else df.columns[0]
    return df[col].astype(float)


# ---------------------------------------------------------------------------
# (A) Information test: does a breakout change the forward-return distribution?
# ---------------------------------------------------------------------------
def information_test(close: pd.Series, N: int = 20, horizons=(1, 5, 10, 20),
                     seed: int = 7) -> None:
    resistance = close.shift(1).rolling(N).max()
    brk = (close > resistance)                       # causal N-day-high breakout
    rng = np.random.default_rng(seed)
    print(f"  INFORMATION TEST - {int(brk.sum())} N={N} breakouts vs all days")
    print(f"    horizon   mean fwd ret: AFTER breakout | ALL days   | diff      p(boot)")
    for k in horizons:
        fwd = close.shift(-k) / close - 1.0
        after = fwd[brk].dropna()
        alld = fwd.dropna()
        if len(after) < 20:
            continue
        diff = after.mean() - alld.mean()
        # bootstrap: random samples of same size from all days; P(|rand diff| >= observed)
        n = len(after)
        base = alld.to_numpy()
        draws = rng.integers(0, base.size, size=(5000, n))
        rand_means = base[draws].mean(axis=1)
        p = float((np.abs(rand_means - alld.mean()) >= abs(diff)).mean())
        print(f"    {k:>3}d     {after.mean()*100:+7.3f}%        | {alld.mean()*100:+7.3f}%   "
              f"| {diff*100:+6.3f}%  {p:.3f}")
    print("    (p = chance a random set of days shows a gap this big; >0.05 = no real signal)")


# ---------------------------------------------------------------------------
# (B) Tradeable breakout strategy
# ---------------------------------------------------------------------------
class Breakout(Strategy):
    def __init__(self, N: int = 20, max_hold: int = 40, target_mult: float = 1.0,
                 max_width: float | None = None, allow_short: bool = False,
                 cost_bps: float = 1.0, cfg: Config = DEFAULT):
        self.N = N
        self.max_hold = max_hold
        self.target_mult = target_mult
        self.max_width = max_width         # if set, require range width <= this (consolidation)
        self.allow_short = allow_short
        self.cost_bps = cost_bps
        tag = f", consol<= {max_width:.0%}" if max_width else ""
        mode = "long/short" if allow_short else "long-only"
        self.name = (f"Breakout N={N}, target {target_mult:g}x, stop=range, "
                     f"{max_hold}d hold ({mode}{tag}, {cost_bps:g}bp/side)")

    COLUMNS = ["entry_time", "exit_time", "direction", "gross_R", "cost_R",
               "hold", "rr", "exit_reason"]

    def generate(self, data) -> pd.DataFrame:
        c = (data if isinstance(data, pd.Series) else data[data.columns[0]]).astype(float)
        idx = c.index
        res = c.shift(1).rolling(self.N).max()
        sup = c.shift(1).rolling(self.N).min()
        px = c.to_numpy(); R = res.to_numpy(); S = sup.to_numpy()
        n = len(c)
        rows = []
        i = self.N + 1
        while i < n - 1:
            if not (np.isfinite(R[i]) and np.isfinite(S[i])):
                i += 1; continue
            width = (R[i] - S[i]) / px[i] if px[i] > 0 else np.inf
            up = px[i] > R[i]
            dn = self.allow_short and (px[i] < S[i])
            if self.max_width is not None and width > self.max_width:
                i += 1; continue
            if not (up or dn):
                i += 1; continue
            direction = 1 if up else -1
            entry = px[i]
            height = (R[i] - S[i]) * self.target_mult
            if direction == 1:
                stop = S[i]; target = entry + height
            else:
                stop = R[i]; target = entry - height
            risk = abs(entry - stop)
            if risk <= 0:
                i += 1; continue
            # walk forward on closes
            exit_i, reason = None, "time"
            for j in range(i + 1, min(i + 1 + self.max_hold, n)):
                if direction == 1:
                    if px[j] <= stop: exit_i, reason = j, "stop"; break
                    if px[j] >= target: exit_i, reason = j, "target"; break
                else:
                    if px[j] >= stop: exit_i, reason = j, "stop"; break
                    if px[j] <= target: exit_i, reason = j, "target"; break
            if exit_i is None:
                exit_i = min(i + self.max_hold, n - 1)
            exitpx = px[exit_i]
            gross_ret = direction * (exitpx - entry)
            gross_R = gross_ret / risk
            cost_R = (2 * self.cost_bps / 1e4 * entry) / risk
            rows.append({
                "entry_time": idx[i], "exit_time": idx[exit_i], "direction": direction,
                "gross_R": gross_R, "cost_R": cost_R, "hold": exit_i - i,
                "rr": height / risk, "exit_reason": reason,
            })
            i = exit_i + 1     # one position at a time
        return pd.DataFrame(rows, columns=self.COLUMNS)


def trade_diagnostics(trades) -> None:
    if not trades:
        print("  (no trades)"); return
    import collections
    reasons = collections.Counter(t.meta["exit_reason"] for t in trades)
    holds = np.mean([t.meta["hold"] for t in trades])
    rr = np.mean([t.meta["rr"] for t in trades])
    print(f"  {len(trades)} trades, avg hold {holds:.0f}d, avg reward:risk {rr:.2f}, "
          f"exits: {dict(reasons)}")


def main(argv=None):
    from ..runner import evaluate, print_report
    from .. import data as D

    p = argparse.ArgumentParser(description="Chart-pattern breakout engine on SPY")
    p.add_argument("--csv", default="data/vix_spy.csv")
    p.add_argument("--N", type=int, default=20)
    p.add_argument("--max-hold", type=int, default=40)
    p.add_argument("--target-mult", type=float, default=1.0)
    p.add_argument("--consol", type=float, default=None,
                   help="require range width <= this fraction (e.g. 0.12) = consolidation breakout")
    p.add_argument("--short", action="store_true")
    p.add_argument("--cost-bps", type=float, default=1.0)
    args = p.parse_args(argv)

    close = _load_spy(args.csv)
    print(f"Loaded {len(close)} daily closes, {close.index[0].date()} -> {close.index[-1].date()}\n")

    # (A) information test first - cheapest, most decisive
    information_test(close, N=args.N)
    print()

    # (B) tradeable
    cfg = DEFAULT
    strat = Breakout(N=args.N, max_hold=args.max_hold, target_mult=args.target_mult,
                     max_width=args.consol, allow_short=args.short, cost_bps=args.cost_bps, cfg=cfg)
    full = strat.to_trades(close)
    rep = evaluate(full, strat.name + " | FULL SAMPLE", cfg)
    print_report(rep)
    print()
    trade_diagnostics(full)
    print()
    print("  PROTECTED SPLIT (develop 1993-2014 -> validate 2015-19 -> holdout 2020-26)")
    for stage in ("develop", "validate", "holdout"):
        sub = D.slice_split(close.to_frame("spy_close"), stage, cfg.split)
        if len(sub) < args.N + 40:
            print(f"    [{stage:<8}] insufficient"); continue
        st = evaluate(strat.to_trades(sub["spy_close"]), f"{stage}", cfg)
        md = st.metrics.as_dict(); nf = sum(1 for g in st.gates if not g.passed)
        flag = "SURVIVOR" if st.survivor else "rejected"
        print(f"    [{stage:<8}] n={md['n']:>4}  exp {md['expectancy_R']:+.3f}R"
              f"  PF {md['profit_factor']:.2f}  win {md['win_rate']:.1%}"
              f"  gates failed {nf}/{len(st.gates)}  -> {flag}")
    print("=" * 64)


if __name__ == "__main__":
    main()
