"""Study 4 - the "ChatGPT confluence" SPY day-trade strategy (Reddit r/Daytrading).

Provenance: a widely-shared Reddit post in which a trader spent ~6 hours having
ChatGPT formalize his discretionary SPY options day-trade into a scored formula.
The original (FMD = average of five sub-scores -> buy calls if >= 0.50, else
puts; ~20-25% trailing stops; 70-85% claimed win rate) is NOT testable as
written, because every sub-score ("RSI rating 1-10", "VWAP rating 1-10") is a
subjective number the trader assigns by eye, and one sub-step (the options-greek
average) is dimensionally incoherent. So this module does the only honest thing:
it rebuilds the IDEA - a pre-open confluence vote that picks call vs put - with
every input replaced by a hard, causal, reproducible rule, then runs it through
the SAME gates and protected split as every other study in this repo.

What is being tested (rung 1 of the data ladder): does the confluence VOTE have
any directional predictive value on the SPY UNDERLYING? The real strategy buys
short-dated options, which only ADD cost (bid/ask, theta decay, IV crush). If the
signal cannot beat ~1 bp of ETF friction on the underlying, the options version -
paying 100x that in friction - is hopeless and no options data need be bought.
A positive result here would merely EARN the right to test it on real option
chains (rung 2), exactly as the README's data ladder prescribes.

Mechanics (frozen before looking at results):
  Decision is made each day using data through that day's CLOSE (causal). The
  position is held one trading day (close_t -> close_{t+1}); this stands in for
  "decide pre-open, hold the day". Five votes, each in {-1, 0, +1}, +1 = bullish
  (calls):
    1. Trend     : close>SMA20 and SMA20>SMA50 -> +1 ; mirror -> -1 ; else 0
    2. RSI(14)   : >55 -> +1 ; <45 -> -1 ; else 0
    3. MACD      : MACD(12,26) line vs signal(9): hist>0 -> +1 ; <0 -> -1
    4. Momentum  : sign of trailing 3-day return (his "previous-day" input)
    5. VIX regime: VIX < its 20-day SMA -> +1 (calm/risk-on) ; above -> -1
  score = sum(votes) in [-5, +5]. score>0 -> long (calls), <0 -> short (puts),
  ==0 -> stand aside (no trade). This is his FMD >=0.50 call/put rule, made
  mechanical.

R unit: 1R = trailing 20-day daily return stdev of SPY. pnl_R for a day reduces
to  direction * (next_day_return / trailing_daily_vol) - cost  - i.e. the
forward move in units of the instrument's own risk, the same convention the
trend study uses, so results are comparable on one scale.

Cost: `cost_bps` PER SIDE on the underlying (default 1.0 bp, realistic retail SPY
ETF), charged round-trip in R. This is the floor; the options version's true
friction is far larger and is NOT modeled here - another reason a marginal
underlying result should be read as a rejection, not a maybe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DEFAULT, Config, DataSplit
from ..strategy import Strategy


# ---------------------------------------------------------------------------
# Causal indicator helpers (each uses only past-and-current data).
# ---------------------------------------------------------------------------
def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder smoothing via EWM(alpha=1/n)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    # when avg_loss == 0 (all gains) RSI -> 100
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    return rsi


def _macd_hist(close: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=sig, adjust=False).mean()
    return macd - signal


class RedditConfluence(Strategy):
    """The mechanical confluence-vote day-trade on SPY."""

    def __init__(
        self,
        rsi_hi: float = 55.0,
        rsi_lo: float = 45.0,
        mom_days: int = 3,
        vol_lookback: int = 20,
        min_abs_score: int = 1,     # trade only when |score| >= this
        cost_bps: float = 1.0,
        cfg: Config = DEFAULT,
    ):
        self.rsi_hi = rsi_hi
        self.rsi_lo = rsi_lo
        self.mom_days = mom_days
        self.vlb = vol_lookback
        self.min_abs_score = min_abs_score
        self.cost_bps = cost_bps
        self.name = (f"Reddit confluence SPY day-trade "
                     f"(|score|>={min_abs_score}, {cost_bps:g}bp/side)")

    COLUMNS = ["entry_time", "exit_time", "direction", "gross_R", "cost_R",
               "score", "fwd_ret", "vol"]

    def _votes(self, px: pd.DataFrame) -> pd.DataFrame:
        c = px["spy_close"].astype(float)
        sma20 = c.rolling(20).mean()
        sma50 = c.rolling(50).mean()
        rsi = _rsi(c, 14)
        hist = _macd_hist(c)
        mom = c.pct_change(self.mom_days)

        s_trend = pd.Series(0, index=c.index, dtype=float)
        s_trend = s_trend.mask((c > sma20) & (sma20 > sma50), 1.0)
        s_trend = s_trend.mask((c < sma20) & (sma20 < sma50), -1.0)

        s_rsi = pd.Series(0.0, index=c.index)
        s_rsi = s_rsi.mask(rsi > self.rsi_hi, 1.0)
        s_rsi = s_rsi.mask(rsi < self.rsi_lo, -1.0)

        s_macd = pd.Series(0.0, index=c.index)
        s_macd = s_macd.mask(hist > 0, 1.0)
        s_macd = s_macd.mask(hist < 0, -1.0)

        s_mom = np.sign(mom).fillna(0.0)

        votes = pd.DataFrame({
            "trend": s_trend, "rsi": s_rsi, "macd": s_macd, "mom": s_mom,
        }, index=c.index)

        if "vix" in px.columns:
            vix = px["vix"].astype(float)
            vix_sma = vix.rolling(20).mean()
            s_vix = pd.Series(0.0, index=c.index)
            s_vix = s_vix.mask(vix < vix_sma, 1.0)
            s_vix = s_vix.mask(vix > vix_sma, -1.0)
            votes["vix"] = s_vix
        # if no VIX column, the VIX vote is simply absent (score over 4 votes)

        return votes

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        px = data.sort_index().copy()
        if "spy_close" not in px.columns:
            # tolerate a generic 'close' column
            if "close" in px.columns:
                px = px.rename(columns={"close": "spy_close"})
            else:
                raise ValueError("reddit_spy needs a 'spy_close' (or 'close') column")

        c = px["spy_close"].astype(float)
        ret = c.pct_change()                       # ret at t = close_t/close_{t-1}-1
        fwd = ret.shift(-1)                         # next-day return, the outcome
        vol = ret.rolling(self.vlb).std()          # trailing daily vol through t (causal)

        votes = self._votes(px)
        score = votes.sum(axis=1)

        df = pd.DataFrame({"score": score, "fwd": fwd, "vol": vol}, index=c.index)
        # valid decision rows: indicators warmed up, vol finite, a next day exists
        df = df.dropna(subset=["fwd", "vol"])
        df = df[df["vol"] > 0]
        # require all indicators present (warm-up): score defined only once SMA50 etc. exist
        df = df[votes.reindex(df.index).notna().all(axis=1)]

        rows = []
        idx = df.index
        for i in range(len(idx) - 0):
            t = idx[i]
            sc = df["score"].iloc[i]
            if abs(sc) < self.min_abs_score:
                continue
            direction = 1 if sc > 0 else -1
            v = float(df["vol"].iloc[i])
            f = float(df["fwd"].iloc[i])
            gross_R = direction * f / v
            # round-trip cost in R: (bps/1e4) per side * 2, scaled by 1/vol
            cost_R = (self.cost_bps / 1e4) * 2.0 / v
            # exit is the NEXT index date (the day whose return 'fwd' measures)
            exit_t = idx[i + 1] if i + 1 < len(idx) else t
            rows.append({
                "entry_time": t, "exit_time": exit_t, "direction": direction,
                "gross_R": gross_R, "cost_R": cost_R,
                "score": float(sc), "fwd_ret": f, "vol": v,
            })
        return pd.DataFrame(rows, columns=self.COLUMNS)


# ---------------------------------------------------------------------------
# Diagnostics specific to this study.
# ---------------------------------------------------------------------------
def score_bucket_table(strat: RedditConfluence, px: pd.DataFrame) -> None:
    """The single most revealing test: does a HIGHER confluence score actually
    mean a higher next-day return? Group every decision day by its raw score and
    show the mean next-day SPY return (in bp) and hit rate. A real signal is
    monotone in score; noise is flat. Uses the UNFILTERED vote (all days)."""
    px = px.sort_index().copy()
    if "spy_close" not in px.columns and "close" in px.columns:
        px = px.rename(columns={"close": "spy_close"})
    c = px["spy_close"].astype(float)
    fwd = c.pct_change().shift(-1)
    votes = strat._votes(px)
    score = votes.sum(axis=1)
    tab = pd.DataFrame({"score": score, "fwd": fwd}).dropna()
    tab = tab[votes.reindex(tab.index).notna().all(axis=1)]
    print("  SCORE -> NEXT-DAY SPY RETURN  (the 'does the score mean anything' test)")
    print("    score     n   mean_fwd(bp)   up_rate   long/short")
    for s in range(-5, 6):
        sub = tab[np.isclose(tab["score"], s)]
        if len(sub) == 0:
            continue
        mean_bp = sub["fwd"].mean() * 1e4
        up = (sub["fwd"] > 0).mean()
        side = "long" if s > 0 else ("short" if s < 0 else "flat")
        print(f"    {s:+d}   {len(sub):>5}   {mean_bp:+8.2f}     {up:5.1%}    {side}")
    # overall base rate for reference
    base = (tab["fwd"] > 0).mean()
    print(f"    [base rate: SPY up next day = {base:.1%} of all {len(tab)} days]")


def by_year(trades) -> None:
    if not trades:
        print("  (no trades)"); return
    df = pd.DataFrame([{"y": t.exit_time.year, "R": t.pnl_R} for t in trades])
    yr = df.groupby("y")["R"].agg(["size", "sum", "mean"])
    print("  by year:  " + "  ".join(
        f"{y}:{row['sum']:+.0f}R(n={int(row['size'])})" for y, row in yr.iterrows()))


# ---------------------------------------------------------------------------
# Data loading + CLI (mirrors the other studies).
# ---------------------------------------------------------------------------
def _load(source: str, csv: str | None):
    from .. import data as D
    if source == "yahoo":
        return D.load_vix_spy()
    if source == "csv":
        if not csv:
            raise SystemExit("--csv required with --source csv "
                             "(columns: datetime/date, spy_close, vix)")
        df = pd.read_csv(csv)
        dtc = ("datetime" if "datetime" in df.columns
               else "date" if "date" in df.columns else df.columns[0])
        df[dtc] = pd.to_datetime(df[dtc])
        df = df.set_index(dtc).sort_index()
        df.index.name = "datetime"
        # normalize common column spellings
        ren = {}
        for cand in ("spy_close", "SPY", "spy", "Close", "close", "Adj Close", "adj_close"):
            if cand in df.columns and "spy_close" not in df.columns and cand != "spy_close":
                ren[cand] = "spy_close"; break
        for cand in ("vix", "VIX", "^VIX", "vix_close"):
            if cand in df.columns and "vix" not in df.columns and cand != "vix":
                ren[cand] = "vix"; break
        df = df.rename(columns=ren)
        return df
    return D.synthetic_vix_spy()


def main(argv=None):
    import argparse
    from ..runner import evaluate, print_report
    from .. import data as D

    p = argparse.ArgumentParser(
        description="Reddit 'ChatGPT confluence' SPY day-trade, made mechanical")
    p.add_argument("--source", choices=["synthetic", "yahoo", "csv"], default="synthetic")
    p.add_argument("--csv", default=None)
    p.add_argument("--min-score", type=int, default=1,
                   help="trade only when |confluence score| >= this (default 1)")
    p.add_argument("--cost-bps", type=float, default=1.0,
                   help="per-side cost on the UNDERLYING in bps (default 1.0)")
    args = p.parse_args(argv)

    px = _load(args.source, args.csv)
    if px.attrs.get("synthetic"):
        print("\n*** SYNTHETIC DATA - plumbing demo only, NOT a real edge. ***")
        print("*** Its SPY path has NO directional signal by construction, so a")
        print("*** flat/negative result here is expected and correct. Use")
        print("*** --source csv (your SPY+VIX history) for a real answer. ***\n")

    cfg = DEFAULT
    strat = RedditConfluence(min_abs_score=args.min_score, cost_bps=args.cost_bps, cfg=cfg)

    full = strat.to_trades(px)
    rep = evaluate(full, strat.name + " | FULL SAMPLE (in-sample)", cfg)
    print_report(rep)
    print()
    score_bucket_table(strat, px)
    print()
    by_year(full)
    print()

    # Protected split: default DataSplit keeps COVID-2020 and the 2022 bear in
    # holdout, so survival means surviving regimes the rule never saw while judged.
    print("  PROTECTED SPLIT (develop 1993-2014 -> validate 2015-19 -> holdout 2020-26)")
    print("  (iterate ONLY on develop; validate/holdout are opened, never tuned to)")
    for stage in ("develop", "validate", "holdout"):
        sub = D.slice_split(px, stage, cfg.split)
        if sub.empty or len(sub) < 80:
            print(f"    [{stage:<8}] insufficient data in window")
            continue
        st = evaluate(strat.to_trades(sub), f"{strat.name} | {stage.upper()}", cfg)
        md = st.metrics.as_dict()
        nf = sum(1 for g in st.gates if not g.passed)
        flag = "SURVIVOR" if st.survivor else "rejected"
        print(f"    [{stage:<8}] n={md['n']:>5}  exp {md['expectancy_R']:+.4f}R"
              f"  PF {md['profit_factor']:.2f}  win {md['win_rate']:.1%}"
              f"  maxDD {md['max_drawdown_R']:.1f}R  gates failed {nf}/{len(st.gates)}"
              f"  -> {flag}")
    print("=" * 64)


if __name__ == "__main__":
    main()
