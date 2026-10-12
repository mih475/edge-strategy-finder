# edge-strategy-finder

A disciplined edge-discovery harness for options and futures research. The goal
is not to find a strategy that *looks* good on one backtest — it's to make that
nearly impossible, so that whatever survives is worth real money.

It grew out of the lessons in a prior ES/MES research project (`test-project`):
seven rounds of price-direction strategies, all rejected after honest testing.
The recurring killers were **friction**, **single-regime (2022) concentration**,
and **decay on later holdouts**. This repo bakes the defenses against all three
into a reusable machine, and then goes hunting in a different pond: **risk
premia** (being paid to carry a risk) instead of price prediction.

## Why this pond

Price patterns decay because once found they get arbitraged away. A risk premium
persists *because* it's compensation for bearing a risk other people don't want.
It also tends to live at longer horizons, where friction is a rounding error
instead of the whole P&L — which is the exact wall the intraday ES research kept
hitting. The first study harvests the best-documented one: the **volatility risk
premium**.

## What's inside

```
edge_finder/
  config.py        frozen cost model, robustness-gate thresholds, protected split
  strategy.py      Trade record + Strategy base class (signals -> trades in R)
  metrics.py       expectancy(R), profit factor, Sharpe, max drawdown, ...
  validation.py    gates (sample, PF, concentration, bootstrap, tail, cost-stress)
                   + outcome Monte Carlo (resample-with-replacement)
  runner.py        evaluate() + a single printed scorecard every study shares
  data.py          loaders: yfinance (real), generic/Databento CSV, synthetic demo
  studies/
    vrp.py         STUDY 1 — volatility risk premium (variance-swap-style)
tests/
  test_smoke.py    end-to-end run on synthetic data
```

### The robustness gates (all must pass to be a "survivor")

| Gate | What it catches |
|---|---|
| sample size (≥100 trades) | luck masquerading as edge |
| expectancy > 0 after cost | the edge is real, not gross-only |
| profit factor ≥ 1.10 | a genuine cushion over breakeven |
| year concentration ≤ 75% | the 2022-type single-regime mirage |
| bootstrap P(mean>0) ≥ 95% | the positive mean isn't noise |
| tail robustness | survives removing the single best trade |
| 2× cost stress | survives if friction is double your estimate |

Plus an **outcome Monte Carlo** that resamples the trade set with replacement, so
you see the *distribution* of total return and drawdown — not the one lucky line
a single backtest shows you.

## Run it

```bash
pip install -r requirements.txt

# 1) See the plumbing work on labeled SYNTHETIC data (no network needed):
python -m edge_finder.studies.vrp --source synthetic

# 2) Real result on your own machine (open network):
pip install yfinance
python -m edge_finder.studies.vrp --source yahoo --threshold 1.10

# 3) From your own CSV (datetime, spy_close, vix):
python -m edge_finder.studies.vrp --source csv --csv data/vix_spy.csv
```

The study prints two scorecards: the **unconditional** premium (sell vol every
period) and the **conditioned** one (sell only when VIX is rich versus trailing
realized vol). Compare them — the conditioning is the edge refinement.

> **Synthetic data is plumbing only.** `synthetic_vix_spy()` builds a series with
> a premium baked in by construction so the code runs end to end. Its numbers are
> not evidence about markets. Use `--source yahoo` or your own data for a real
> answer.

## The data ladder

1. **Free (start here):** daily VIX + SPY via yfinance. Proves whether the VRP
   *signal* has predictive value before you spend a cent.
2. **Real option fills (next):** the vol-point varswap model approximates a short
   straddle/varswap. To backtest actual sold options (defined-risk spreads, real
   bid/ask, assignment) you need an options chain — your Databento account can
   serve this, same as the CVD data in `test-project`.

## Roadmap (next studies, each a file in `studies/`)

- `portfolio.py` — combine the *existing* edges from `test-project` (ORB, CPI,
  ISM…) and compute their correlation matrix. Several weak, uncorrelated edges
  can be robust as a book even when none passes the solo gate — the one thing a
  single-survivor search can't see.
- `carry.py` — VIX-futures term structure (contango/backwardation) and futures
  roll yield. Friction-light, risk-premium based.
- `trend.py` — time-series momentum across diversified micro futures (MES, MNQ,
  MGC, M2K, micro crude, micro bonds). Durable, and diversified across asset
  classes rather than three correlated equity indices.
- `event_surprise.py` — signed actual-vs-consensus macro surprise (the Round-8
  idea from `test-project`), not price-only continuation.

## Discipline rules (carried over from test-project)

- Freeze `config.py` before looking at a strategy's results.
- Iterate only on the **develop** split. Open **validate** once a rule survives.
  Open **holdout** once, ever, at the end. Never tune to validate/holdout.
- One base specification per idea. No threshold sweeps in the first pass.
- Model friction from the first run, never bolt it on later.

---

*Research tooling for your own analysis. Not financial advice. Markets cluster
losses in ways a fixed-edge model understates — treat every number here as a
hypothesis to be falsified, not a promise.*
