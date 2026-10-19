# Finding: the Reddit "ChatGPT confluence" SPY day-trade has no directional edge

Date: 2026-10-18. Data: `data/vix_spy.csv` (yfinance via `load_vix_spy`),
5,734 daily rows, 2004-01-02 → 2026-10-16. Spec: `studies/reddit_spy.py` —
mechanical 5-vote confluence (trend / RSI / MACD / 3-day momentum / VIX-regime),
trade when |score| ≥ 1, 1 bp/side underlying cost, 1R = trailing 20-day daily
vol, hold close→close (a pre-open-decision proxy).

## Context

Origin is a widely-shared r/Daytrading post: a trader had ChatGPT formalize his
discretionary SPY options day-trade into a scored formula (FMD = average of five
sub-scores → calls if ≥ 0.50 else puts; 20–25% trailing stops; **claimed 70–85%
win rate**). As written it is untestable — every sub-score is a subjective 1–10
the trader assigns by eye, and the options-greek step is dimensionally
incoherent. So we rebuilt the *idea* (a pre-open confluence vote → call/put) with
every input replaced by a hard, causal rule, and ran it through the same gates
and protected split as every other study here. This tests **rung 1 of the data
ladder**: does the vote predict direction on the SPY *underlying* at all? If it
can't beat 1 bp of ETF friction, the real options version (bid/ask + theta +
IV crush) is hopeless and no option data need be touched.

## Result (protected split, per-trade expectancy in R, after cost)

| Stage | n | expectancy | PF | win% | gates | verdict |
|---|---|---|---|---|---|---|
| develop 1993–2014  | 2,659 | −0.0371R | 0.91 | 49.9% | 5/7 fail | rejected |
| validate 2015–2019 | 1,215 | −0.0123R | 0.97 | 49.3% | 5/7 fail | rejected |
| holdout 2020–2026  | 1,624 | −0.0204R | 0.95 | 50.9% | 5/7 fail | rejected |

Full sample: expectancy **−0.0289R**, PF **0.932**, win **50.0%**, total
**−159.9R**, maxDD −185R. Outcome Monte Carlo: **P(ends negative) = 96.9%**,
median total −161R. It fails on **develop, validate AND holdout** — this is not
an edge that decayed out-of-sample, it is the absence of an edge in every regime.

## Why it fails (the informative part)

**Long vs short leg (full sample):**

| Leg | n | expectancy | win% | total | gross-right % |
|---|---|---|---|---|---|
| LONG (calls)  | 3,554 | +0.0104R | 53.5% | +37R  | 54.8% |
| SHORT (puts)  | 1,983 | −0.0994R | 43.8% | −197R | 44.5% |

- **The score carries ~zero directional information.** Long bets are right 54.8%
  of the time — essentially identical to SPY's *unconditional* 55.0% up-day rate.
  The long leg only "works" by riding SPY's structural drift, not because the
  signal picked anything. It is buy-and-hold with extra steps and worse timing.
- **The short leg is actively harmful** — right only 44.5% of the time, *worse
  than a coin flip.* It shorts a structurally rising instrument, and the
  score→next-day table shows the strongest *bearish* vote days (score −5, −4)
  were followed by the **highest** positive returns (+14 bp, +12 bp): classic
  short-term mean-reversion + drift. Selling puts into those days is backwards.
- **The score is not monotone.** Mean next-day return by score bucket is just the
  ambient +drift plus noise (all buckets positive, range +0.9 to +15.8 bp, no
  ordering). A real signal is monotone in score; this is flat.

This is the *same lesson* `trend_longflat_findings.md` reached: on a long-biased
equity, the short leg is a net drag. Long/flat beat long/short there; here, the
"flat" is just buy-and-hold, which returned **+939% / +10.8% CAGR** over the
window while the strategy lost money.

## The claimed 70–85% win rate

Not supported in any regime. Realized next-day directional win rate is **≈50%**
(50.0% full sample). The original's high win rate, if it was ever real, came from
the 20–25% trailing stop booking many small wins while letting correlated losers
run — a profile that inflates *win rate* while destroying *expectancy*, and that
the R-based gates and the Monte Carlo see straight through.

## Caveats

1. **This is the underlying, at 1 bp/side.** The actual strategy buys short-dated
   options. Theta decay, bid/ask, and IV crush make a no-skill direction a
   guaranteed bleed — the options version is strictly worse than these numbers,
   not better. No option P&L was modeled because a negative underlying signal
   makes it unnecessary.
2. Close→close daily proxy, not true intraday/0DTE execution. Given the signal
   has no edge even at this favorable, low-friction resolution, finer execution
   modeling cannot rescue it.
3. Daily trades are autocorrelated; the gates treat them as independent. The
   result is so decisively negative that this does not change the conclusion.

## Decision

**REJECT. Do not trade it, in any form.** It reinforces the project's thesis:
durable edge comes from risk premia and diversification (the trend sleeve that
survived), not from pre-open technical confluence on a single index. Pre-open
"confluence scoring" of standard indicators is, on this evidence, a dressed-up
coin flip that pays the drift on the long side and gives it back (plus costs) on
the short side.
