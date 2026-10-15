"""Study 2 - the Volatility Risk Premium, traded as a REAL defined-risk put
spread on end-of-day SPY option chains.

Why this exists: Study 1 (vrp.py) confirmed the VRP survives an honest convex
payoff, but it was a variance-swap PROXY built from VIX minus realized vol - no
bid/ask, no real strikes, uncapped tail. This study trades the premium the way
you actually would with $1,000: sell a put spread (defined risk), hold to expiry,
settle on the real underlying, pay the real bid/ask. The max loss is capped at
(width - credit), so the -8R convex blowups from Study 1 cannot happen - that is
the whole point of trading it as a spread.

Mechanics (frozen before looking at results):
  - Entry: on each scheduled date, pick the expiry closest to `target_dte`.
  - Short leg: the put nearest `short_delta` (e.g. 0.30).  Long leg: the put
    nearest `long_delta` (e.g. 0.15), strictly below the short strike.
  - Fills are conservative: SELL the short at its BID, BUY the long at its ASK.
    Credit = short_bid - long_ask.  Width = short_strike - long_strike.
  - Hold to expiry.  Settle on the underlying at the expiry's quote:
        short intrinsic = max(short_strike - S_exp, 0)
        long  intrinsic = max(long_strike  - S_exp, 0)
        payoff = credit - (short_intrinsic - long_intrinsic)   [capped by width]
  - 1R = max loss = width - credit.  So pnl_R = payoff / max_loss, a natural,
    honest risk unit for a defined-risk trade.
  - Conditioning: optionally only enter when the short put's implied vol is rich
    vs trailing realized vol of the underlying (the same VRP-richness idea that
    protected the weak regime in Study 1), computed causally.

Costs: commission per contract (both legs, both open and expiry) plus a slippage
nudge, all charged in R.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DEFAULT, Config
from ..strategy import Strategy


# --------------------------------------------------------------------------- #
# Black-Scholes helpers (only used to build the synthetic demo chain).
# --------------------------------------------------------------------------- #
def _norm_cdf(x):
    from math import erf, sqrt
    if np.isscalar(x):
        return 0.5 * (1.0 + erf(x / sqrt(2.0)))
    return 0.5 * (1.0 + np.vectorize(erf)(x / np.sqrt(2.0)))


def bs_put(S, K, T, sigma, r=0.03):
    S, K, T, sigma = map(np.asarray, (S, K, T, sigma))
    T = np.clip(T, 1e-6, None)
    sigma = np.clip(sigma, 1e-6, None)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    price = K * np.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
    delta = _norm_cdf(d1) - 1.0  # put delta in [-1, 0]
    return price, delta


# --------------------------------------------------------------------------- #
# The strategy.
# --------------------------------------------------------------------------- #
class VRPPutSpread(Strategy):
    def __init__(
        self,
        target_dte: int = 30,
        short_delta: float = 0.30,
        long_delta: float = 0.15,
        entry_every_days: int = 30,
        richness_threshold: float | None = None,
        trend_filter_sma: int | None = None,
        cfg: Config = DEFAULT,
    ):
        self.target_dte = target_dte
        self.short_delta = short_delta
        self.long_delta = long_delta
        self.entry_every = entry_every_days
        self.threshold = richness_threshold
        # Frozen 2026-10-12: skip new entries while SPY closes below its
        # `trend_filter_sma`-day simple moving average (causal). Rationale: a short
        # put spread is implicitly long the market, so stand aside in a confirmed
        # downtrend. Targets the 2022-bear failure. None = filter off.
        self.trend_sma = trend_filter_sma
        self.cfg = cfg
        self.name = (
            f"VRP put-spread {short_delta:.2f}/{long_delta:.2f}d ~{target_dte}DTE"
            + (f" | sell when IV>={richness_threshold:g}x realized"
               if richness_threshold else " | unconditional")
            + (f" | trend>{trend_filter_sma}DMA" if trend_filter_sma else "")
        )

    COLUMNS = ["entry_time", "exit_time", "direction", "gross_R", "cost_R",
               "short_strike", "long_strike", "credit", "width",
               "underlying_entry", "underlying_exit", "short_iv"]

    def _underlying_series(self, chain: pd.DataFrame) -> pd.Series:
        return (chain.groupby("quote_date")["underlying"].first().sort_index())

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        req = {"quote_date", "underlying", "expire_date", "strike",
               "p_bid", "p_ask"}
        if not req.issubset(data.columns):
            raise ValueError(f"VRP put-spread needs columns {req}")
        chain = data.copy()
        has_delta = "p_delta" in chain.columns and chain["p_delta"].notna().any()
        has_iv = "p_iv" in chain.columns and chain["p_iv"].notna().any()

        u = self._underlying_series(chain)
        under_dates = list(u.index)
        logret = np.diff(np.log(u.to_numpy()), prepend=np.log(u.to_numpy()[0]))
        # trailing 21d realized vol by quote_date, for conditioning (causal)
        rv = pd.Series(logret, index=u.index).rolling(21).std() * np.sqrt(252) * 100.0
        # causal trend filter: SPY vs its N-day SMA
        sma = u.rolling(self.trend_sma).mean() if self.trend_sma else None

        # expiry -> settlement underlying (first quote on/after the expiry date)
        settle = {}
        for exp in chain["expire_date"].unique():
            on = u[u.index >= exp]
            if len(on):
                settle[exp] = float(on.iloc[0])

        rows = []
        last_entry = None
        td = self.target_dte
        for qd in under_dates:
            if last_entry is not None and (qd - last_entry).days < self.entry_every:
                continue
            # trend filter: stand aside when SPY is below its SMA (or SMA unknown)
            if sma is not None:
                s = sma.get(qd, np.nan)
                if np.isnan(s) or u.get(qd, np.nan) < s:
                    continue
            day = chain[chain["quote_date"] == qd]
            if day.empty:
                continue
            # choose expiry nearest target_dte (>= 7 days out)
            exps = day["expire_date"].drop_duplicates()
            dte = (exps - qd).dt.days
            exps = exps[dte >= 7]
            if exps.empty:
                continue
            exp = exps.iloc[(( (exps - qd).dt.days - td ).abs()).argmin()]
            legday = day[day["expire_date"] == exp]
            puts = legday[(legday["p_bid"] > 0) & (legday["p_ask"] > 0)].copy()
            if len(puts) < 4:
                continue
            S0 = float(puts["underlying"].iloc[0])

            # pick short/long strikes by delta if available, else by % OTM
            if has_delta:
                puts["absd"] = puts["p_delta"].abs()
                short = puts.iloc[(puts["absd"] - self.short_delta).abs().argmin()]
                cand = puts[puts["strike"] < short["strike"]]
                if cand.empty:
                    continue
                longp = cand.iloc[(cand["absd"] - self.long_delta).abs().argmin()]
            else:
                # fallback: short ~5% OTM, long ~10% OTM
                short = puts.iloc[(puts["strike"] - S0 * 0.95).abs().argmin()]
                cand = puts[puts["strike"] < short["strike"]]
                if cand.empty:
                    continue
                longp = cand.iloc[(cand["strike"] - S0 * 0.90).abs().argmin()]

            width = float(short["strike"] - longp["strike"])
            if width <= 0:
                continue
            credit = float(short["p_bid"] - longp["p_ask"])  # conservative fills
            if credit <= 0:
                continue
            max_loss = width - credit
            if max_loss <= 0:
                continue

            short_iv = float(short["p_iv"]) if has_iv and not pd.isna(short["p_iv"]) else np.nan
            # conditioning on IV richness vs trailing realized (causal)
            if self.threshold is not None:
                trail = rv.get(qd, np.nan)
                iv_for_test = short_iv if not np.isnan(short_iv) else np.nan
                if np.isnan(iv_for_test) or np.isnan(trail) or \
                        iv_for_test < self.threshold * trail:
                    continue

            S_exp = settle.get(exp)
            if S_exp is None:
                continue
            short_intr = max(short["strike"] - S_exp, 0.0)
            long_intr = max(longp["strike"] - S_exp, 0.0)
            payoff = credit - (short_intr - long_intr)
            payoff = max(payoff, -max_loss)  # defined risk cap

            # costs: 2 legs x (open + expiry) contracts, commission + slippage, in R
            contracts = 2
            comm = self.cfg.cost.commission_rt * contracts
            slip = self.cfg.cost.tick_size * self.cfg.cost.slippage_ticks * contracts
            cost_dollars = comm + slip
            # per 1-contract spread, $ per R = max_loss*100 (100 multiplier)
            cost_R = cost_dollars / (max_loss * 100.0)

            rows.append({
                "entry_time": qd,
                "exit_time": exp,
                "direction": 1,
                "gross_R": payoff / max_loss,
                "cost_R": cost_R,
                "short_strike": float(short["strike"]),
                "long_strike": float(longp["strike"]),
                "credit": credit,
                "width": width,
                "underlying_entry": S0,
                "underlying_exit": S_exp,
                "short_iv": short_iv,
            })
            last_entry = qd

        return pd.DataFrame(rows, columns=self.COLUMNS)


# --------------------------------------------------------------------------- #
# Synthetic EOD option chain, so the pipeline runs where real data is absent.
# NOT an edge - a labeled stand-in. A vol premium is baked in by construction.
# --------------------------------------------------------------------------- #
def synthetic_eod_options(years: int = 12, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = years * 252
    idx = pd.bdate_range("2012-01-03", periods=n)
    # stochastic vol underlying
    vol = np.empty(n); vol[0] = 0.16
    for t in range(1, n):
        vol[t] = abs(0.94 * vol[t - 1] + 0.06 * 0.16 + rng.normal(0, 0.02))
    vol = np.clip(vol, 0.07, 0.9)
    rets = rng.normal(0.07 / 252, 1.0, n) * (vol / np.sqrt(252))
    S = 130.0 * np.exp(np.cumsum(rets))
    under = pd.Series(S, index=idx)

    # monthly expiries: 3rd Friday each month
    exps = pd.date_range(idx[0], idx[-1] + pd.Timedelta(days=40), freq="WOM-3FRI")

    rows = []
    # build chains only on ~weekly quote dates to keep the demo light
    quote_days = idx[::5]
    for qd in quote_days:
        S0 = float(under.loc[qd])
        local_vol = float(vol[idx.get_loc(qd)])
        implied = local_vol * (1.0 + 0.06)  # +6% premium -> VRP exists by design
        fut = [e for e in exps if 7 <= (e - qd).days <= 70]
        for exp in fut:
            T = (exp - qd).days / 365.0
            strikes = np.round(S0 * np.linspace(0.80, 1.05, 26) / 1.0, 0)
            iv = implied + 0.15 * (1 - strikes / S0)  # mild put skew
            price, delta = bs_put(S0, strikes, T, iv)
            spread = np.maximum(0.02, price * 0.03)  # 3% bid/ask, floor 2c
            for K, pr, dl, sp, v in zip(strikes, price, delta, spread, iv):
                rows.append({
                    "quote_date": qd, "underlying": S0, "expire_date": exp,
                    "dte": (exp - qd).days, "strike": float(K),
                    "p_bid": max(pr - sp / 2, 0.01), "p_ask": pr + sp / 2,
                    "p_delta": float(dl), "p_iv": float(v) * 100.0,
                })
    df = pd.DataFrame(rows)
    df.attrs["synthetic"] = True
    return df


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    import argparse
    from ..runner import evaluate, print_report
    from .. import data as D
    from .vrp import worst_episode_audit

    p = argparse.ArgumentParser(description="VRP traded as a defined-risk put spread (EOD)")
    p.add_argument("--source", choices=["synthetic", "optionsdx"], default="synthetic")
    p.add_argument("--path", default=None, help="file or dir of OptionsDX EOD CSVs")
    p.add_argument("--target-dte", type=int, default=30)
    p.add_argument("--entry-every", type=int, default=7,
                   help="days between entries; 7 = weekly (more observations)")
    p.add_argument("--short-delta", type=float, default=0.30)
    p.add_argument("--long-delta", type=float, default=0.15)
    p.add_argument("--threshold", type=float, default=1.10)
    p.add_argument("--trend-sma", type=int, default=None,
                   help="skip entries when SPY < this-day SMA (e.g. 200). "
                        "Frozen regime filter; off by default.")
    args = p.parse_args(argv)

    if args.source == "optionsdx":
        if not args.path:
            raise SystemExit("--path to OptionsDX CSV(s) required with --source optionsdx")
        df = D.load_eod_options(args.path)
    else:
        df = synthetic_eod_options()
        print("\n*** SYNTHETIC OPTIONS - plumbing demo only, NOT a real edge. ***")
        print("*** Download free SPY EOD chains (OptionsDX) and use --source optionsdx. ***\n")

    cfg = DEFAULT
    # Options data begins 2016, so the VIX-era split in config.py doesn't fit.
    # Use an options-specific protected split: develop pre-COVID, validate the
    # COVID/recovery, hold out the 2022 bear + 2023 (never seen in development).
    from ..config import DataSplit
    opt_split = DataSplit(develop=("2016-01-01", "2019-12-31"),
                          validate=("2020-01-01", "2021-12-31"),
                          holdout=("2022-01-01", "2023-12-31"))
    if args.entry_every <= 10:
        print("  (weekly entries into ~30-DTE spreads overlap, so successive "
              "trades are not fully independent; treat n as larger than the\n"
              "   effective independent sample, and weigh the holdout accordingly.)")
    for thresh in (None, args.threshold):
        strat = VRPPutSpread(target_dte=args.target_dte,
                             short_delta=args.short_delta,
                             long_delta=args.long_delta,
                             entry_every_days=args.entry_every,
                             richness_threshold=thresh,
                             trend_filter_sma=args.trend_sma, cfg=cfg)
        full = strat.to_trades(df)
        rep = evaluate(full, strat.name + " | FULL SAMPLE (in-sample)", cfg)
        print_report(rep)
        worst_episode_audit_spread(full, n=10)
        print()
        print("  PROTECTED SPLIT (develop 2016-19 -> validate 2020-21 -> holdout 2022-23)")
        for stage in ("develop", "validate", "holdout"):
            sub = D.slice_split(df.set_index("quote_date"), stage, opt_split)
            sub = sub.reset_index()
            if sub.empty:
                print(f"    [{stage}] no data in window")
                continue
            st = evaluate(strat.to_trades(sub), f"{strat.name} | {stage.upper()}", cfg)
            md = st.metrics.as_dict()
            nf = sum(1 for g in st.gates if not g.passed)
            flag = "SURVIVOR" if st.survivor else "rejected"
            print(f"    [{stage:<8}] n={md['n']:>3}  exp {md['expectancy_R']:+.3f}R"
                  f"  PF {md['profit_factor']:.2f}  maxDD {md['max_drawdown_R']:.1f}R"
                  f"  gates failed: {nf}/{len(st.gates)}  -> {flag}")
        print("=" * 64 + "\n")


def worst_episode_audit_spread(trades, n: int = 10) -> None:
    if not trades:
        print("  (no trades)")
        return
    ordered = sorted(trades, key=lambda t: t.pnl_R)[:n]
    print("  WORST EPISODES (deepest single-spread losses; capped at -1R by design)")
    print(f"    {'entry':<12}{'expiry':<12}{'S in':>8}{'S out':>8}"
          f"{'credit':>8}{'width':>7}{'R':>8}")
    for t in ordered:
        m = t.meta
        print(f"    {str(t.entry_time.date()):<12}{str(t.exit_time.date()):<12}"
              f"{m.get('underlying_entry', float('nan')):>8.1f}"
              f"{m.get('underlying_exit', float('nan')):>8.1f}"
              f"{m.get('credit', float('nan')):>8.2f}"
              f"{m.get('width', float('nan')):>7.1f}{t.pnl_R:>8.2f}")


if __name__ == "__main__":
    main()
