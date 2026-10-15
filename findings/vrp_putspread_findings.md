# Findings — VRP as a defined-risk SPY put spread (EOD)

Status: **REJECTED as built** (fails protected holdout). Edge is real but
regime-dependent. Recorded 2026-10-12.

Study: `edge_finder/studies/vrp_options.py`
Data: OptionsDX free EOD SPY option chains, 2016-01-04 → 2023-12-29
(7,302,478 rows, 2,009 quote dates).

## Specification (frozen before results)

- Sell a put spread on SPY: short ~0.30-delta put, long ~0.15-delta put
  (strictly lower strike), chosen from the expiry nearest 30 DTE.
- Fills conservative: sell short at BID, buy long at ASK. Credit = short_bid −
  long_ask. Width = short_strike − long_strike.
- Hold to expiry; settle on the underlying at the expiry's close. Payoff capped
  at the defined-risk max loss (width − credit).
- 1R = max loss = width − credit (natural unit for a defined-risk trade).
- Entry cadence: weekly (positions overlap; see caveat).
- Costs: commission + slippage per leg, open and expiry, charged in R.
- Two variants: unconditional, and conditioned "sell only when short-put IV ≥
  1.10 × trailing-21d realized vol".
- Protected split: develop 2016–19, validate 2020–21 (COVID), holdout 2022–23
  (the 2022 bear — never seen during development).

## Results

### Full sample (in-sample, unconditional)
411 trades, +0.0363 R/trade, PF 1.35, win 84.9%, maxDD −7.7 R, bootstrap 98.3%.
Passes all 7 gates. **But full-sample is in-sample and not the test.**

### Protected split

| Stage | Unconditional | Conditioned (IV≥1.1×RV) |
|---|---|---|
| develop 2016–19 | +0.056 R, PF 1.71 — SURVIVOR | +0.054 R, PF 1.72 — SURVIVOR |
| validate 2020–21 | +0.071 R, PF 1.93 | +0.062 R, PF 1.79 |
| **holdout 2022–23** | **−0.052 R, PF 0.73 — REJECTED** | **−0.072 R, PF 0.66 — REJECTED** |

Positive in development AND validation (including the COVID crash), then
**negative out-of-sample in the 2022–23 holdout.** Both variants.

## What we learned

1. **The VRP is real.** Positive and gate-passing across develop + validate, on
   real fills, after costs, through the COVID spike. This is not nothing.

2. **The defined-risk cap works exactly as designed.** Every worst-case loss
   across 8 years — including Feb-2020 entries settling into the March crash —
   capped at −1.00 R. No −8 R convex blowups like the naked variance proxy.
   Trading the VRP as a spread is the correct structure for small capital.

3. **It is a fair-weather edge.** A short put spread is implicitly long the
   market. It profits when stocks are flat, rising, or crash-and-recover (COVID:
   hit in March 2020, then the vol collapse + V-recovery made 2020–21 strongly
   positive). It **bleeds in a sustained grinding bear** — 2022 fell ~25% in slow
   downmoves with no snap-back, a steady drip of −1 R losses the premium can't
   cover. This is structural, not bad luck.

4. **IV-richness conditioning did not help** — it slightly *reduced* expectancy
   and failed bootstrap. For defined-risk put spreads the IV filter is the wrong
   conditioner.

5. **Same lesson as the ES research:** an edge that works in some regimes decays
   on a later holdout. The protected split caught it; the in-sample full run did
   not.

## Decision

Do NOT trade this as built. The holdout failure is disqualifying for a "stable"
income strategy.

## Next hypothesis (frozen 2026-10-12, BEFORE seeing its results)

Add a **trend/regime filter**: take no new put-spread entries when SPY closes
below its 200-day simple moving average (causal). Rationale: stop being
implicitly long the market while the market is in a confirmed downtrend — directly
targets the 2022 failure mechanism, with an economic reason, not a curve fit.

**Methodological honesty:** 2022–23 has now been observed, so it is no longer
pristine. Running the trend-filtered version on 2016–2023 is a DEVELOPMENT look
only. True validation requires data the current holdout did not inform —
**download OptionsDX SPY EOD for 2024–2025 and test there** before trusting it.

## Bigger-picture direction

The most robust outcome is a **two-sleeve book**: this short-vol income edge for
calm/bull regimes, plus a diversified trend-following sleeve that *profits* in
bears like 2022. Size them together via the correlation study. Neither alone is
all-weather; the combination can be.

---

## Update 2026-10-12 — trend filter tested; holdout now burned

Ran the frozen 200-day trend filter (skip entries when SPY < 200DMA).

| Variant (holdout 2022-23) | Expectancy | PF | vs no filter |
|---|---|---|---|
| unconditional, no filter | -0.052 R | 0.73 | — |
| **unconditional + 200DMA** | **+0.003 R** | 1.02 | bleed neutralized → breakeven |
| conditioned + 200DMA | -0.019 R | 0.88 | still negative |

Findings:
- The trend filter **works as theorized**: it removes the 2022 bear bleed, taking
  the holdout from a clear loss to roughly breakeven. Mechanism (don't be long
  into a downtrend) confirmed.
- **Cost:** it also discards the most lucrative post-crash selling (high IV while
  price is still below the 200DMA, e.g. spring 2020), so the full-sample edge
  falls (+0.036 → +0.020 R) and fails bootstrap. Lower return for bear safety.
- Net: this is a **modest fair-weather income sleeve with bear protection**, not
  a positive all-weather edge. Holdout is breakeven at best.

### Methodological stop (important)
Four variants have now been evaluated against the 2022-23 holdout (plain,
conditioned, trend, conditioned+trend). That is multiple testing against the same
held-out data — the holdout is now **burned** and can no longer certify anything.
No more variant-hunting on 2016-2023.

### FROZEN SPEC (chosen on principle, before seeing new data)
**Unconditional VRP put-spread (0.30/0.15 delta, ~30 DTE, weekly) + 200DMA trend
filter.** Rationale for the choices, not fitted to the burned holdout:
- trend filter: included — addresses the one structural failure with a real
  economic mechanism.
- IV conditioning: excluded — did not reliably help and adds a parameter
  (parsimony).

### The only valid next test
Download OptionsDX SPY EOD for **2024 and 2025** (same free source) and run this
frozen spec there. That is untouched data. If it is positive out-of-sample on
2024-25, the income sleeve is real. If not, retire it.
