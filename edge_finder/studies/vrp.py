"""Study 1 — the Volatility Risk Premium (VRP).

Economic idea: index implied volatility (VIX) sits, on average, ABOVE the
volatility that subsequently realizes. Someone who sells that implied vol and
delivers the realized vol collects the difference. This is not a price forecast;
it is being paid to carry variance risk — which is exactly why it persists where
price-pattern edges decay. The question this study answers is only: after
realistic cost, is the premium actually harvestable, and does conditioning on
"rich" implied vol improve it?

Instrument model: a short 21-trading-day variance swap, approximated in
VOLATILITY POINTS. Each trade sells implied vol at today's VIX and pays the
realized vol over the next 21 trading days:

        gross (vol points) = VIX_t  -  realized_vol(t+1 .. t+21)

(A true varswap settles on variance, adding a small convexity term in favor of
the buyer; working in vol points is the standard intuitive approximation and is
deliberately conservative for a seller.) We sample NON-OVERLAPPING 21-day blocks
so every observation is independent — no overlap-inflated significance.

R unit: 1R = `r_unit_volpts` vol points of adverse move (default 10 — roughly
what a short-vol position loses if vol spikes hard against it). This only sets
the scale for reading expectancy and drawdown; the pass/fail gates are
scale-invariant.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DEFAULT, Config
from ..strategy import Strategy


def annualized_vol(log_returns: np.ndarray, trading_days: int = 252) -> float:
    if log_returns.size < 2:
        return np.nan
    return float(np.std(log_returns, ddof=1) * np.sqrt(trading_days) * 100.0)


class VarianceRiskPremium(Strategy):
    """Sell short-horizon index variance, optionally only when implied vol is
    rich versus recent realized vol.

    Parameters
    ----------
    horizon_days : holding period of each varswap (trading days).
    richness_threshold : if set, only sell when VIX_t >= threshold * trailing
        realized vol (causal, uses only past data). None = sell every block.
    r_unit_volpts : vol points per 1R (interpretability only).
    payoff_mode : "variance" (default) settles like a real variance swap, which
        is CONVEX in the realized move and therefore charges crisis losses
        honestly; "volpoints" is the naive linear (VIX - realized) approximation
        kept only for comparison — it understates tail losses and should never be
        the basis for a go/no-go decision.
    """

    def __init__(
        self,
        horizon_days: int = 21,
        richness_threshold: float | None = None,
        r_unit_volpts: float = 10.0,
        payoff_mode: str = "variance",
        cfg: Config = DEFAULT,
    ):
        if payoff_mode not in ("variance", "volpoints"):
            raise ValueError("payoff_mode must be 'variance' or 'volpoints'")
        self.h = horizon_days
        self.threshold = richness_threshold
        self.r_unit = r_unit_volpts
        self.payoff_mode = payoff_mode
        self.cfg = cfg
        self.name = (
            f"VRP short-vol {horizon_days}d [{payoff_mode}]"
            + (f" | sell when VIX>={richness_threshold:g}x realized"
               if richness_threshold else " | unconditional")
        )

    def _gross_volpts(self, implied: float, realized: float) -> float:
        """Short-vol gross result in vol-point-equivalent units.

        variance mode: a variance swap pays on variance (vol squared). For a
        short position with vega notional scaled to 1 vol point, the settlement is
            (K^2 - RV^2) / (2K)
        where K = implied, RV = realized (both in vol points). Near the money this
        reduces to (K - RV) — matching the linear model — but when RV spikes far
        above K it blows up quadratically, which is the real risk of short vol.
        E.g. K=20, RV=80: linear = -60, variance = (400-6400)/40 = -150.
        """
        if self.payoff_mode == "volpoints":
            return implied - realized
        return (implied ** 2 - realized ** 2) / (2.0 * implied)

    COLUMNS = ["entry_time", "exit_time", "direction", "gross_R", "cost_R",
               "implied_vol", "realized_vol", "vrp_volpts"]

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        if not {"spy_close", "vix"}.issubset(data.columns):
            raise ValueError("VRP study needs columns ['spy_close','vix']")
        if len(data) < 2 * self.h + 2:
            raise ValueError(
                f"VRP study got only {len(data)} rows; needs at least "
                f"{2 * self.h + 2} for a {self.h}-day horizon. Check the data load."
            )
        df = data.sort_index()
        close = df["spy_close"].to_numpy(dtype=float)
        vix = df["vix"].to_numpy(dtype=float)
        idx = df.index
        logret = np.diff(np.log(close), prepend=np.log(close[0]))  # logret[i] for day i

        h = self.h
        cost_R = self.cfg.cost.vol_point_cost / self.r_unit
        rows = []
        # non-overlapping blocks; need h past days (trailing RV) and h future days
        t = h
        while t + h < len(idx):
            implied = vix[t]
            fwd = logret[t + 1 : t + 1 + h]          # realized over next h days
            realized_fwd = annualized_vol(fwd, self.cfg.trading_days)
            if np.isnan(realized_fwd):
                t += h
                continue

            take = True
            if self.threshold is not None:
                trailing = annualized_vol(logret[t - h + 1 : t + 1], self.cfg.trading_days)
                take = (not np.isnan(trailing)) and (implied >= self.threshold * trailing)

            if take:
                gross_volpts = self._gross_volpts(implied, realized_fwd)
                rows.append({
                    "entry_time": idx[t],
                    "exit_time": idx[t + h],
                    "direction": 1,                          # short vol
                    "gross_R": gross_volpts / self.r_unit,
                    "cost_R": cost_R,
                    "implied_vol": implied,
                    "realized_vol": realized_fwd,
                    "vrp_volpts": gross_volpts,
                })
            t += h

        # Always return a frame with the expected columns, even if empty, so an
        # empty result reports as "0 trades" rather than a cryptic column error.
        return pd.DataFrame(rows, columns=self.COLUMNS)


# ---------------------------------------------------------------------------
# CLI: run the study end to end and print scorecards.
# ---------------------------------------------------------------------------
def _load(source: str, csv: str | None):
    from .. import data as D
    if source == "yahoo":
        return D.load_vix_spy()
    if source == "csv":
        if not csv:
            raise SystemExit("--csv PATH required with --source csv")
        raw = D.load_ohlcv_csv(csv)
        # expect spy_close + vix columns in the csv
        return raw
    return D.synthetic_vix_spy()


def worst_episode_audit(trades, n: int = 10) -> None:
    """Print the n worst single trades so crises are visible, not averaged away.
    This is the sanity check against a too-clean backtest: if 2008/2018/2020 do
    not show up here as deep losers, the model is not charging the tail."""
    if not trades:
        print("  (no trades)")
        return
    ordered = sorted(trades, key=lambda t: t.pnl_R)[:n]
    print("  WORST EPISODES (deepest single-trade losses)")
    print(f"    {'entry':<12}{'exit':<12}{'VIX in':>8}{'realized':>10}{'R':>9}")
    for t in ordered:
        print(f"    {str(t.entry_time.date()):<12}{str(t.exit_time.date()):<12}"
              f"{t.meta.get('implied_vol', float('nan')):>8.1f}"
              f"{t.meta.get('realized_vol', float('nan')):>10.1f}"
              f"{t.pnl_R:>9.2f}")


def main(argv=None):
    import argparse
    from ..runner import evaluate, print_report
    from .. import data as D

    p = argparse.ArgumentParser(description="Volatility Risk Premium study")
    p.add_argument("--source", choices=["synthetic", "yahoo", "csv"], default="synthetic")
    p.add_argument("--csv", default=None, help="CSV with datetime, spy_close, vix")
    p.add_argument("--horizon", type=int, default=21)
    p.add_argument("--threshold", type=float, default=1.10,
                   help="conditioned: sell only when VIX >= threshold x trailing realized vol")
    p.add_argument("--mode", choices=["variance", "volpoints"], default="variance",
                   help="payoff model; 'variance' (default) is the honest convex "
                        "settlement, 'volpoints' the naive linear comparison")
    args = p.parse_args(argv)

    df = _load(args.source, args.csv)
    if df.attrs.get("synthetic"):
        print("\n*** SYNTHETIC DATA - plumbing demo only, NOT a real edge. ***")
        print("*** Re-run with --source yahoo or --source csv for real results. ***\n")

    cfg = DEFAULT
    print(f"\n### PAYOFF MODE: {args.mode}"
          + ("  (CONVEX variance-swap settlement — charges the tail honestly)"
             if args.mode == "variance"
             else "  (LINEAR approximation — understates the tail, comparison only)"))

    for thresh in (None, args.threshold):
        strat = VarianceRiskPremium(horizon_days=args.horizon,
                                    richness_threshold=thresh,
                                    payoff_mode=args.mode, cfg=cfg)

        # ---- full-sample reference ----
        full_trades = strat.to_trades(df)
        rep = evaluate(full_trades, strat.name + " | FULL SAMPLE (in-sample)", cfg)
        print_report(rep)
        worst_episode_audit(full_trades, n=10)
        print()

        # ---- protected develop / validate / holdout ----
        print("  PROTECTED SPLIT (develop -> validate -> holdout; "
              "holdout contains COVID-2020 + 2022, never seen in development)")
        for stage in ("develop", "validate", "holdout"):
            sub = D.slice_split(df, stage, cfg.split)
            if len(sub) < 2 * args.horizon + 2:
                print(f"    [{stage}] too few rows ({len(sub)}) to evaluate")
                continue
            st = evaluate(strat.to_trades(sub),
                          f"{strat.name} | {stage.upper()}", cfg)
            md = st.metrics.as_dict()
            flag = "SURVIVOR" if st.survivor else "rejected"
            n_fail = sum(1 for g in st.gates if not g.passed)
            print(f"    [{stage:<8}] n={md['n']:>3}  exp {md['expectancy_R']:+.3f}R"
                  f"  PF {md['profit_factor']:.2f}  winDD {md['max_drawdown_R']:.1f}R"
                  f"  gates failed: {n_fail}/{len(st.gates)}  -> {flag}")
        print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
