"""edge_finder — a disciplined edge-discovery harness.

The whole point of this package is to make it HARD to fool yourself. Every
strategy is scored the same way, through the same friction model, the same
walk-forward split, the same robustness gates, and the same Monte Carlo on the
trade sequence. A single lucky backtest path cannot pass; only an edge that
survives cost, out-of-sample data, tail removal, and regime concentration does.

Design borrowed from the author's ES/MES research conventions:
  - friction modeled from the first run, never bolted on later
  - development / validation / holdout are separate and protected
  - results are judged on the distribution of outcomes, not one path
"""

__version__ = "0.1.0"
