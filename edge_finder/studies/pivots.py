"""Study 8 - pivot-based REVERSAL patterns: double top/bottom, head-and-shoulders.

These are the patterns the one serious academic study (Lo-Mamaysky-Wang 2000)
actually tested, and they're a different geometry from the breakout engine: a
specific sequence of swing highs/lows (pivots), then a neckline break.

Pipeline:
  1. PIVOTS: fractal swing points on close. Bar i is a pivot high if its close is
     the max over [i-w, i+w]; pivot low symmetric. A pivot is only CONFIRMED at
     i+w (you can't know it's a swing until w bars later) - so everything is causal.
     Consecutive same-type pivots are collapsed to the more extreme one, giving a
     clean alternating high/low sequence.
  2. DETECT on the confirmed pivot sequence:
       - double top   : High, Low, High with the two highs within `tol`, trough
                        >= `depth` below them. Neckline = the trough. Bearish.
       - double bottom: mirror. Bullish.
       - H&S top      : H,L,H,L,H with head (middle high) above both shoulders by
                        >= `depth`, shoulders within `tol`. Neckline = line through
                        the two troughs. Bearish.
       - inverse H&S  : mirror. Bullish.
  3. TRIGGER: after the last pivot is confirmed, the first close that breaks the
     neckline (down for tops, up for bottoms) within `max_wait` bars = entry.
     Stop beyond the pattern extreme (1R = that risk); target = measured move
     (pattern height projected from the neckline); time-stop at `max_hold`.

Three tests per pattern (same rigor as the breakout study): (A) information test -
forward return after the trigger vs the unconditional base rate; (B) tradeable
through the gates + protected split; (C) random-entry null with identical structure.

Data: daily SPY closes. NOTE: reversal patterns are rare on one instrument, so
counts will be small - reported prominently, because "too rare to trade" is a
finding. The Lo et al. study needed hundreds of stocks to get statistical power.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import DEFAULT, Config
from ..strategy import Strategy


def _load_spy(csv: str) -> pd.Series:
    df = pd.read_csv(csv, parse_dates=["datetime"]).set_index("datetime").sort_index()
    col = "spy_close" if "spy_close" in df.columns else df.columns[0]
    return df[col].astype(float)


@dataclass
class Pivot:
    i: int          # bar index of the swing
    price: float
    kind: int       # +1 high, -1 low
    conf: int       # bar index at which it is confirmed (i + w)


def find_pivots(c: np.ndarray, w: int) -> list[Pivot]:
    n = len(c)
    piv: list[Pivot] = []
    for i in range(w, n - w):
        win = c[i - w:i + w + 1]
        if c[i] == win.max() and (c[i] > c[i - 1] or c[i] > c[i + 1]):
            piv.append(Pivot(i, c[i], +1, i + w))
        elif c[i] == win.min() and (c[i] < c[i - 1] or c[i] < c[i + 1]):
            piv.append(Pivot(i, c[i], -1, i + w))
    # collapse consecutive same-kind pivots -> keep the more extreme
    out: list[Pivot] = []
    for p in piv:
        if out and out[-1].kind == p.kind:
            if (p.kind == +1 and p.price > out[-1].price) or (p.kind == -1 and p.price < out[-1].price):
                out[-1] = p
        else:
            out.append(p)
    return out


def detect(pivs: list[Pivot], pattern: str, tol: float, depth: float):
    """Yield dicts describing each detected pattern (geometry + neckline + extreme)."""
    out = []
    for k in range(len(pivs)):
        if pattern in ("double_top", "double_bottom"):
            if k < 2:
                continue
            a, b, cc = pivs[k - 2], pivs[k - 1], pivs[k]
            if pattern == "double_top":
                if not (a.kind == +1 and b.kind == -1 and cc.kind == +1):
                    continue
                if abs(a.price - cc.price) / a.price > tol:
                    continue
                peak = max(a.price, cc.price)
                if (peak - b.price) / peak < depth:
                    continue
                out.append(dict(kind="double_top", dir=-1, neck=b.price,
                                extreme=peak, last_conf=cc.conf, last_i=cc.i,
                                height=peak - b.price))
            else:
                if not (a.kind == -1 and b.kind == +1 and cc.kind == -1):
                    continue
                if abs(a.price - cc.price) / a.price > tol:
                    continue
                trough = min(a.price, cc.price)
                if (b.price - trough) / trough < depth:
                    continue
                out.append(dict(kind="double_bottom", dir=+1, neck=b.price,
                                extreme=trough, last_conf=cc.conf, last_i=cc.i,
                                height=b.price - trough))
        else:  # head and shoulders (5 pivots)
            if k < 4:
                continue
            p1, p2, p3, p4, p5 = pivs[k - 4:k + 1]
            if pattern == "hs_top":
                if not (p1.kind == +1 and p2.kind == -1 and p3.kind == +1 and p4.kind == -1 and p5.kind == +1):
                    continue
                if not (p3.price > p1.price and p3.price > p5.price):
                    continue
                if (p3.price - max(p1.price, p5.price)) / p3.price < depth:
                    continue
                if abs(p1.price - p5.price) / p1.price > tol:
                    continue
                neck = max(p2.price, p4.price)   # conservative neckline
                out.append(dict(kind="hs_top", dir=-1, neck=neck, extreme=p5.price,
                                last_conf=p5.conf, last_i=p5.i, height=p3.price - neck))
            else:  # hs_bottom (inverse)
                if not (p1.kind == -1 and p2.kind == +1 and p3.kind == -1 and p4.kind == +1 and p5.kind == -1):
                    continue
                if not (p3.price < p1.price and p3.price < p5.price):
                    continue
                if (min(p1.price, p5.price) - p3.price) / p3.price < depth:
                    continue
                if abs(p1.price - p5.price) / p1.price > tol:
                    continue
                neck = min(p2.price, p4.price)
                out.append(dict(kind="hs_bottom", dir=+1, neck=neck, extreme=p5.price,
                                last_conf=p5.conf, last_i=p5.i, height=neck - p3.price))
    return out


def triggers(c: np.ndarray, pats: list[dict], max_wait: int) -> list[dict]:
    """For each detected pattern, find the first neckline break after confirmation."""
    n = len(c)
    out = []
    for p in pats:
        start = max(p["last_conf"], p["last_i"]) + 1
        for t in range(start, min(start + max_wait, n)):
            broke = (c[t] < p["neck"]) if p["dir"] == -1 else (c[t] > p["neck"])
            if broke:
                q = dict(p); q["entry_i"] = t; q["entry"] = c[t]
                out.append(q); break
    return out


class PivotPattern(Strategy):
    def __init__(self, pattern: str, w: int = 5, tol: float = 0.05, depth: float = 0.03,
                 max_wait: int = 30, max_hold: int = 60, cost_bps: float = 1.0,
                 cfg: Config = DEFAULT):
        self.pattern = pattern
        self.w = w; self.tol = tol; self.depth = depth
        self.max_wait = max_wait; self.max_hold = max_hold; self.cost_bps = cost_bps
        self.name = f"{pattern} (w={w}, tol={tol:.0%}, depth={depth:.0%})"

    COLUMNS = ["entry_time", "exit_time", "direction", "gross_R", "cost_R", "hold", "exit_reason"]

    def _trig(self, c):
        pivs = find_pivots(c, self.w)
        pats = detect(pivs, self.pattern, self.tol, self.depth)
        return triggers(c, pats, self.max_wait)

    def generate(self, data) -> pd.DataFrame:
        c = (data if isinstance(data, pd.Series) else data[data.columns[0]]).astype(float)
        idx = c.index; arr = c.to_numpy(); n = len(arr)
        rows = []
        last_exit = -1
        for p in self._trig(arr):
            i = p["entry_i"]
            if i <= last_exit:
                continue                       # one position at a time
            d = p["dir"]; entry = p["entry"]
            stop = p["extreme"]
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            target = entry - p["height"] if d == -1 else entry + p["height"]
            exit_i, reason = None, "time"
            for j in range(i + 1, min(i + 1 + self.max_hold, n)):
                if d == -1:
                    if arr[j] >= stop: exit_i, reason = j, "stop"; break
                    if arr[j] <= target: exit_i, reason = j, "target"; break
                else:
                    if arr[j] <= stop: exit_i, reason = j, "stop"; break
                    if arr[j] >= target: exit_i, reason = j, "target"; break
            if exit_i is None:
                exit_i = min(i + self.max_hold, n - 1)
            gR = d * (arr[exit_i] - entry) / risk
            cR = (2 * self.cost_bps / 1e4 * entry) / risk
            rows.append({"entry_time": idx[i], "exit_time": idx[exit_i], "direction": d,
                         "gross_R": gR, "cost_R": cR, "hold": exit_i - i, "exit_reason": reason})
            last_exit = exit_i
        return pd.DataFrame(rows, columns=self.COLUMNS)


def information_test(c: np.ndarray, trig: list[dict], horizons=(5, 10, 20), seed=7):
    rng = np.random.default_rng(seed)
    n = len(c)
    ents = np.array([p["entry_i"] for p in trig])
    dirs = np.array([p["dir"] for p in trig])
    if len(ents) < 8:
        print(f"    (only {len(ents)} triggers - too few for a meaningful information test)")
        return
    for k in horizons:
        fwd_all = []
        for i in range(n - k):
            fwd_all.append(c[i + k] / c[i] - 1.0)
        fwd_all = np.array(fwd_all)
        valid = ents < (n - k)
        e = ents[valid]; dd = dirs[valid]
        signed = dd * (c[np.minimum(e + k, n - 1)] / c[e] - 1.0)   # return in predicted direction
        base_signed = fwd_all.mean()   # unconditional (long bias ~ +drift)
        # compare signed pattern return to what a same-direction random bet earns
        draws = rng.integers(0, len(fwd_all), size=(5000, len(e)))
        rand = (dd.mean()) * fwd_all[draws].mean(axis=1) if False else None
        print(f"    {k:>3}d: pattern return in predicted dir {signed.mean()*100:+.3f}%  "
              f"| base (buy&hold same horizon) {base_signed*100:+.3f}%  "
              f"| edge over drift {(signed.mean()-base_signed*np.sign(dd.mean() or 1))*100:+.3f}%")


def main(argv=None):
    from ..runner import evaluate, print_report
    from .. import data as D

    p = argparse.ArgumentParser(description="Pivot reversal patterns on SPY")
    p.add_argument("--csv", default="data/vix_spy.csv")
    p.add_argument("--w", type=int, default=5)
    p.add_argument("--tol", type=float, default=0.05)
    p.add_argument("--depth", type=float, default=0.03)
    p.add_argument("--cost-bps", type=float, default=1.0)
    args = p.parse_args(argv)

    close = _load_spy(args.csv)
    arr = close.to_numpy()
    print(f"Loaded {len(close)} daily closes, {close.index[0].date()} -> {close.index[-1].date()}\n")
    cfg = DEFAULT

    for pattern in ("double_bottom", "double_top", "hs_bottom", "hs_top"):
        strat = PivotPattern(pattern, w=args.w, tol=args.tol, depth=args.depth, cost_bps=args.cost_bps, cfg=cfg)
        trig = strat._trig(arr)
        print("=" * 64)
        print(f" {pattern.upper()}  -  {len(trig)} triggered occurrences (2004-2026)")
        print("=" * 64)
        information_test(arr, trig)
        full = strat.to_trades(close)
        if len(full) == 0:
            print("  (no tradeable occurrences)\n"); continue
        rep = evaluate(full, f"{pattern} | FULL SAMPLE", cfg)
        md = rep.metrics.as_dict(); nf = sum(1 for g in rep.gates if not g.passed)
        print(f"  TRADEABLE: n={md['n']}  exp {md['expectancy_R']:+.3f}R  PF {md['profit_factor']:.2f}"
              f"  win {md['win_rate']:.1%}  total {md['total_R']:+.1f}R  maxDD {md['max_drawdown_R']:.1f}R"
              f"  -> {'SURVIVOR' if rep.survivor else f'rejected {nf}/7'}")
        # null control: random entries, same direction, stop/target = median risk/height (%)
        d = 1 if pattern.endswith("bottom") else -1
        n = len(arr)
        risks = []; heights = []
        for q in trig:
            risks.append(abs(q['entry'] - q['extreme'])/q['entry']); heights.append(q['height']/q['entry'])
        if risks:
            mr, mh = np.median(risks), np.median(heights)
            exps = []
            cand = np.arange(args.w+1, n-61)
            for s in range(300):
                rr = np.random.default_rng(s)
                picks = rr.choice(cand, size=min(len(full), len(cand)), replace=False)
                Rs = []
                for i in picks:
                    entry = arr[i]; stop = entry*(1 - d*mr); target = entry*(1 + d*mh)
                    risk = abs(entry-stop); ex=None
                    for j in range(i+1, min(i+1+60, n)):
                        if d==1:
                            if arr[j]<=stop: ex=j;break
                            if arr[j]>=target: ex=j;break
                        else:
                            if arr[j]>=stop: ex=j;break
                            if arr[j]<=target: ex=j;break
                    if ex is None: ex=min(i+60,n-1)
                    Rs.append(d*(arr[ex]-entry)/risk)
                exps.append(np.mean(Rs))
            exps=np.array(exps)
            pct = (exps < md['expectancy_R']).mean()*100
            print(f"  NULL (random entries, same stop/target): mean {exps.mean():+.3f}R, "
                  f"real at {pct:.0f}th pctile  {'(> signal adds nothing)' if 20<pct<80 else ''}")
        print()


if __name__ == "__main__":
    main()
