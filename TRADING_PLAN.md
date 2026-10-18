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
- Realistic expectation, now MEASURED (deployment-accurate run, 2007–2026):
  **native ~3.8%/yr at ~3.8% vol, Sharpe ~1.0, worst drawdown ~-7%**, with long
  flat stretches (2017–2020 made ~nothing). Excellent risk-*adjusted* quality,
  but low absolute return — because the vol is low. See "Return target" for what
  leverage can and cannot do with that.

(Optional second sleeve later: the VRP put-spread, but only after it's validated on
fresh 2024–25 option data. Start with one sleeve.)

## Return target — CORRECTED with the measured native profile

The earlier version of this section assumed native vol was ~12% and concluded
15% needed only ~1.6x leverage. **That was wrong.** The deployment-accurate run
measured the book's true native profile:

> **CAGR ~3.8% · vol ~3.8% · Sharpe ~0.98 · worst drawdown ~-7% · avg gross 52%**

The edge quality is *excellent* (Sharpe ~1.0). The absolute return is small
because the vol is small — the book sits ~48% in cash and is deeply diversified.
Return = Sharpe × vol, so **15% is not a 1.6x nudge; it needs ~4x leverage.**
Corrected tradeoff (drawdown scales roughly linearly with leverage, worse in the
tails):

| Leverage | ~vol | ~return | model worst DD | plan-for DD | How you'd run it |
|---|---|---|---|---|---|
| **1.0x native** | 3.8% | **~3.8%** | -7% | -12% | **$5k cash account — now** |
| 1.9x | ~7% | ~7% | -14% | -22% | cash account, fully deployed — the ceiling |
| 2.6x | ~10% | ~10% | -19% | -30% | margin account (~2.6:1) |
| **4.0x** | ~15% | **~15%** | -29% | **-45%+** | futures or heavy margin |

**Two hard truths:**

1. A **$5k cash account physically tops out near ~1.9x / ~7%** — it cannot reach
   15%. That needs futures or margin *and* the stomach for ~-45% drawdowns.
2. The 0.98 Sharpe is a clean backtest. **Live** — after real spreads, taxes,
   execution gaps, and the well-documented compression of trend Sharpes over the
   last decade — expect **~0.5–0.7**. At Sharpe 0.6, hitting 15% needs ~25% vol
   (~6.5x leverage), which is a wipe-out risk. So in practice **15% is not a safe
   target for this edge.**

**Revised stance:** run **native (~3.8%)** at $5k through Phases 1–2 to build the
discipline track record. Treat leverage as a slowly-earned rung requiring a
bigger margin/futures account *and* proven behavior — and even then aim for
~7–10%, not 15%. The real wealth engine is **salary contributions compounding**;
this book's job is diversification and risk-adjusted return, not the headline
number. The "Honest expectations" section below warned of exactly this.

**The leverage ladder (earn each rung with live discipline, never skip):**
1. **Rung 1 — 1.0x native (~4%):** all of Phase 1 (paper) and Phase 2 (live at
   $5k). Prove you execute to the rule and hold a drawdown without deviating.
2. **Rung 2 — up to ~1.9x (~7%):** a cash account fully deployed, only after Rung
   1 survived a live losing stretch with zero rule-breaks.
3. **Rung 3 — ~2.6x+ (margin/futures, ~10%):** only in a larger account, only
   after Rung 2 did the same. 15%/4x is explicitly NOT a planned rung.

Dollar reality at $5k: native ≈ **+$190/yr**; at the ~1.9x ceiling ≈ +$350/yr.
Modest by design. Salary-funded and salary-backstopped.

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
