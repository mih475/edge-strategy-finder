# Finding: long/flat beats long/short on the diversified ETF trend book

Date: 2026-10-15. Data: yfinance adjusted closes, 7-ETF universe
(SPY, IWM, EFA, TLT, GLD, DBC, UUP), 2004-01-02 → 2026-10-15 (5,733 days).
Spec: 252-day trend signal, 63-day vol estimate, 10% per-position vol target,
3x cap, monthly rebalance, 2 bps × turnover cost. `studies/trend.py`.

## Result (protected split, per-trade expectancy in R, after cost)

| Stage | long/short | gates | long/flat | gates |
|---|---|---|---|---|
| develop 2007–16  | +0.062R (PF 1.17) | 1/7 fail → rejected | +0.124R (PF 1.37) | 0/7 → SURVIVOR |
| validate 2017–20 | −0.056R (PF 0.89) | 6/7 fail → rejected | +0.000R (PF 1.00) | 6/7 fail → rejected |
| holdout 2021–25  | +0.090R (PF 1.25) | 0/7 → SURVIVOR | +0.205R (PF 1.69) | 0/7 → SURVIVOR |

Full-sample: long/short exp +0.089R, PF 1.25, maxDD −31.3R, MC worst-5% −35R.
Long/flat exp +0.173R, PF 1.54, maxDD −18.4R, MC worst-5% −20.5R.

## Interpretation

- **The short leg was a net drag** on this universe/era. It is equity-heavy and
  long-biased, and the sample is dominated by bull markets (2009–21, 2023–26).
  Shorting equities/intl in their brief downtrends repeatedly got run over by
  sharp V-reversals. Holding cash instead both earns more and halves drawdown.
- **Long/flat passes all 7 gates on BOTH develop and holdout** — the strongest
  evidence any variant in this project has produced.
- **Validate (2017–2020) was flat for both** (long/flat breakeven, long/short
  negative). This is trend following's documented multi-year drought regime, not
  a bug. It must be expected to recur.

## Caveats before trusting the magnitude

1. **Portfolio aggregate is optimistic for long/flat.** `generate()` drops
   flat months (no row when trail ≤ 0), so `portfolio_summary` averages only
   active months → overstates deployed return (reported Sharpe 0.97). The
   per-trade gate stats above are correctly measured; the compounded portfolio
   curve is not. Do NOT size off 0.97 Sharpe. A deployment-accurate equity curve
   (cash months as 0) is still to be computed.
2. Costs modeled at 2 bps × turnover; real retail ETF costs (spread + commission
   + the occasional gap) may run higher. 2x-cost stress still passed (+0.1706R).

## Decision

Trade the **long/flat** variant in a cash brokerage account for Phases 0–2.
It is the better-performing AND the operationally-feasible choice (no shorting,
no margin call). Full long/short remains a possible Rung-2+ futures experiment,
but current evidence says the short leg does not help on this book.

## Deployment-accurate curve (the number that actually matters), 2026-10-15

`deployment_curve()` builds the real 1/N book in capital terms, **counting cash
months as zero**, 2007–2026:

- avg gross exposure **~52%** of capital
- **NATIVE:** CAGR **+3.8%**, vol **3.8%**, Sharpe **0.98**, maxDD **-7.3%**, +months 61%
- **CASH-CAP** (gross ≤ 100%): CAGR +3.8%, vol 3.8%, Sharpe 0.99, maxDD -7.3%
  (≈ identical to native — avg gross is only 52%, so the cap rarely binds)

**Implication.** The flattering 0.97 Sharpe from `portfolio_summary` was a
cash-month-exclusion artifact; the *honest* profile is ~3.8% return at ~3.8%
vol. The edge is high-*quality* (Sharpe ~1.0) but low-*return* because it is
low-vol (deeply diversified, ~48% in cash). Return = Sharpe × vol.

Consequence for the plan: **15% needs ~4x leverage, not 1.6x** (the old plan
assumed 12% native vol). A $5k cash account tops out near ~1.9x / ~7%. And a
realistic *live* Sharpe (~0.5–0.7 after frictions/taxes) makes 15% effectively
unreachable at safe leverage. `TRADING_PLAN.md` → "Return target" updated to
reflect this. Native ~3.8% is the Phase 1–2 operating point; wealth comes from
salary contributions, not leverage.
