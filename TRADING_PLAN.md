# The 1-in-30 Plan: a modest real edge, executed with discipline

The research is clear: ~1–3% of active traders are consistently profitable, and the
survivors win on **risk and behavior**, not entries. This plan is built to make you
one of them — not by out-disciplining everyone, but by choosing an edge that
*removes* the situations where discipline fails.

## The core idea

Your weakness (by your own account, six years of it) is execution and psychology:
overtrading, deviating under pressure, chasing. The fix isn't more willpower. It's
to **trade a mechanical, low-frequency edge** so there are almost no decisions left
to get wrong:

- **Mechanical** -> no discretionary judgment to bias -> kills the disposition
  effect and hindsight.
- **Low-frequency (monthly)** -> almost no chances to overtrade or revenge-trade,
  the two biggest killers. Fits a full-time job.
- **Automatable signals** (you're an engineer) -> the computer generates the
  orders; emotion never touches the entry.
- **Tiny fixed risk** -> no losing streak can end you; removes the fear that drives
  bad decisions.

You engineer the discipline into the *system*, so being the 1-in-30 is about
following a checklist, not conquering your nature.

## The edge to use

The **diversified trend-following sleeve** we built and validated (`studies/trend.py`):
time-series momentum across ~7 uncorrelated markets (equity, intl, bonds, gold,
commodities, dollar), vol-targeted, monthly rebalance.

Why this one:
- It **survived its protected holdout** (2021–25, incl. the 2022 bear) cleanly —
  the only thing in the whole project that did.
- It is **positive in crises** (2008, 2022) — the regime where everything else bled.
- It is **monthly and mechanical** — the ideal shape for someone whose edge must be
  execution discipline, not screen-time skill.
- Realistic expectation: **~0.5–0.6 Sharpe, roughly 10–15%/yr at ~12–15% vol, with
  15–25% drawdowns and long flat stretches** (2017–2020 was flat industry-wide).
  Not 30%. Real, modest, survivable.

(Optional second sleeve later: the VRP put-spread, but only after it's validated on
fresh 2024–25 option data. Start with one sleeve.)

## The phased path (go/no-go gates — do not skip)

### Phase 0 — Lock the edge (2–4 weeks)
- Freeze the trend spec (lookback, vol target, universe). No more tinkering.
- Re-run `studies/trend.py` and confirm develop/validate/holdout still hold.
- Pick instruments: **micro futures** (MES, MNQ, M2K, MGC, MCL, micro bonds/FX) so
  the book is tradeable on small capital. Map each universe member to its micro.
- Size with the **Edge & Ruin Lab**: choose risk-per-position so the historical
  ~20% drawdown is survivable at your account size. Write the sizing down.
- **Gate:** you can state, in one sentence each, the entry rule, exit rule, sizing
  rule, and rebalance schedule — from memory.

### Phase 1 — Paper / forward test (3–6 months)
- Run it live in a sim account. Automate the monthly signal (a script that emails
  you the target positions).
- **Judge execution, NOT P&L.** A quarter is far too short to judge a 0.5-Sharpe
  edge — it's ~90% noise. You are testing *yourself*.
- Log every rebalance: did I place exactly what the rule said? Any deviation? Why?
- **Gate to proceed:** ≥95% of rebalances executed to the rule, zero unplanned
  trades, slippage ≈ modeled.

### Phase 2 — Micro live, minimum size (3–6 months)
- Trade **1 micro contract per signal** with money you can fully afford to lose.
- The point is to feel a real drawdown with real money and **prove you don't
  deviate.** This is the actual test the previous six years failed.
- **Gate to scale:** you held the rules through at least one losing stretch without
  overriding, panic-closing, or adding unplanned risk.

### Phase 3 — Scale with contributions (ongoing, years)
- As your **salary funds the account**, add contracts / markets, sized by risk
  parity + fixed-fractional risk. The contributions do the heavy lifting early; the
  edge compounds on top.
- Re-check risk-of-ruin at every size increase. Never size up after a win streak on
  emotion; size by the math only.

## The non-negotiable rules (the discipline core)

1. **Fixed fractional risk.** Each position sized so the book's expected worst
   drawdown stays within your pre-set tolerance. Never "feel" the size.
2. **Never override a signal.** Mechanical in, mechanical out. A rule-break that
   wins is still a failure and must be logged as one.
3. **Trade only on the schedule.** Monthly rebalance. No intra-month "adjustments."
4. **No additions to losers, no revenge trades, ever.**
5. **One book.** No side bets, no "just this once" discretionary trade. Those are a
   different (losing) game.
6. **Journal every action**, and review monthly: execution fidelity first, P&L
   second.

## What to track

Per rebalance and monthly: positions vs. rule (fidelity %), each position's R,
monthly return, rolling 12-month return, current drawdown vs. historical max,
realized vs. modeled slippage. **Execution fidelity is the headline metric for the
first year — not money.**

## Honest expectations (read this when you're discouraged)

- Year 1 is about proving you can *execute*, not about profit.
- The edge is modest; most of your wealth will come from **salary contributions +
  time**, with the edge improving risk-adjusted returns and adding diversification.
- There will be flat years and 20% drawdowns. They are normal and were in the
  backtest. Quitting during them is how the other 29-in-30 fail.
- This competes with "door #3" (your software skills) for your time. Both are valid.
  The honest math still says your career is the higher-return asset on small capital
  — so treat this as the disciplined side-sleeve it is, not the main engine.

## The one-line version

Pick the one edge that survived (trend), automate it so emotion can't touch it,
risk tiny amounts, never override, fund it from your salary, and judge yourself on
whether you followed the rules — for years. That is the entire game, and it is
boring on purpose. Boring is what 1-in-30 looks like.
