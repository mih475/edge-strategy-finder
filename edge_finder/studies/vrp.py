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
    """

    def __init__(
        self,
        horizon_days: int = 21,
        richness_threshold: float | None = None,
        r_unit_volpts: float = 10.0,
        cfg: Config = DEFAULT,
    ):
        self.h = horizon_days
        self.threshold = richness_threshold
        self.r_unit = r_unit_volpts
        self.cfg = cfg
        self.name = (
            f"VRP short-vol {horizon_days}d"
            + (f" | sell when VIX>={richness_threshold:g}x realized"
               if richness_threshold else " | unconditional")
        )

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        if not {"spy_close", "vix"}.issubset(data.columns):
            raise ValueError("VRP study needs columns ['spy_close','vix']")
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
                gross_volpts = implied - realized_fwd       # short vol
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

        return pd.DataFrame(rows)


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


def main(argv=None):
    import argparse
    from ..runner import evaluate, print_report

    p = argparse.ArgumentParser(description="Volatility Risk Premium study")
    p.add_argument("--source", choices=["synthetic", "yahoo", "csv"], default="synthetic")
    p.add_argument("--csv", default=None, help="CSV with datetime, spy_close, vix")
    p.add_argument("--horizon", type=int, default=21)
    p.add_argument("--threshold", type=float, default=1.10,
                   help="conditioned: sell only when VIX >= threshold x trailing realized vol")
    args = p.parse_args(argv)

    df = _load(args.source, args.csv)
    if df.attrs.get("synthetic"):
        print("\n*** SYNTHETIC DATA — plumbing demo only, NOT a real edge. ***")
        print("*** Re-run with --source yahoo (pip install yfinance) or --source csv for real results. ***\n")

    cfg = DEFAULT
    for thresh in (None, args.threshold):
        strat = VarianceRiskPremium(horizon_days=args.horizon,
                                    richness_threshold=thresh, cfg=cfg)
        trades = strat.to_trades(df)
        rep = evaluate(trades, strat.name, cfg)
        print_report(rep)


if __name__ == "__main__":
    main()
