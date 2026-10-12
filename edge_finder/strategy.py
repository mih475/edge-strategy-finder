"""The Trade record and the Strategy base class.

A Strategy's only job is to turn market data into a list of Trade records, each
carrying a net P&L already expressed in R (risk units) so every strategy is
comparable on the same scale. Costs are applied by the study/runner, not hidden
inside the signal, so the harness can stress them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class Trade:
    """One closed position.

    pnl_R is the realized result in risk units (1R = the amount risked on the
    trade). gross_R is before costs; cost_R is the friction charged. Keep both
    so the harness can re-stress costs without re-running the signal.
    """
    entry_time: datetime
    exit_time: datetime
    direction: int                 # +1 long / short-vol, -1 short / long-vol
    gross_R: float
    cost_R: float
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def pnl_R(self) -> float:
        return self.gross_R - self.cost_R

    @property
    def year(self) -> int:
        return self.exit_time.year


class Strategy:
    """Subclass and implement generate(). Return a DataFrame of trades with at
    least: entry_time, exit_time, direction, gross_R, cost_R. The base class
    turns that into Trade objects and nothing else, so studies stay declarative.
    """

    name: str = "unnamed"

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError

    def to_trades(self, data: pd.DataFrame) -> list[Trade]:
        df = self.generate(data)
        required = {"entry_time", "exit_time", "direction", "gross_R", "cost_R"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"{self.name}: generate() missing columns {missing}")
        meta_cols = [c for c in df.columns if c not in required]
        out: list[Trade] = []
        for _, row in df.iterrows():
            out.append(
                Trade(
                    entry_time=pd.Timestamp(row["entry_time"]).to_pydatetime(),
                    exit_time=pd.Timestamp(row["exit_time"]).to_pydatetime(),
                    direction=int(row["direction"]),
                    gross_R=float(row["gross_R"]),
                    cost_R=float(row["cost_R"]),
                    meta={c: row[c] for c in meta_cols},
                )
            )
        return out
