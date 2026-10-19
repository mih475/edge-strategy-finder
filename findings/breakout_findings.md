# Finding: the chart-pattern BREAKOUT engine carries no edge on SPY

Date: 2026-10-19. Data: daily SPY closes (`data/vix_spy.csv`), 2004-2026, 5,734
days. Spec: `studies/breakout.py`. Causal N=20 resistance (prior-20-day-high) / support
breakout; tradeable version adds a protective stop at the opposite side of the
range (1R = that risk), a +1x measured-move target, and a 40-day time stop.

## Context

User chose to test the **breakout engine** first — the common mechanic under
triangles, rectangles, flags, pennants and (post-neckline) the reversals. The
Fidelity/Kirkpatrick deck: "a pattern is not complete until an actual breakout
occurs." So this is the shared, highest-leverage thing to test.

## Three tests, one answer: no information

**1. Information test (Lo-Mamaysky-Wang style) — the decisive, drift-controlled read.**
Forward return AFTER a 20-day-high breakout vs the unconditional base rate:

| horizon | after breakout | all days | diff | p(bootstrap) |
|---|---|---|---|---|
| 1d | +0.015% | +0.048% | −0.033% | 0.32 |
| 5d | +0.114% | +0.233% | −0.118% | 0.07 |
| 10d | +0.347% | +0.462% | −0.115% | 0.20 |
| 20d | +0.717% | +0.919% | −0.202% | 0.10 |

Breakouts are followed by **below-average** returns, none statistically significant.
The signal carries no positive information. Restricting to **consolidation** (tight-
range, bottom-tercile width) breakouts — the "clean" triangle/rectangle setups —
makes it *worse*: +0.44% vs +0.92% at 20d. The tidier the pattern, the less it predicts.

**2. Tradeable version — looks like a winner, isn't.** Full sample: +0.226R/trade,
PF 1.78, 69% win, tagged SURVIVOR. But the **protected split rejects all three
stages** (develop +0.09R fails bootstrap; validate/validate too few trades), and
the full-sample pass is a sample-size artifact. The 69% win rate comes from the
measured-move target + a long-only bias across a 22-year **bull market** — drift,
not signal.

**3. Null control — the proof.** Random entry days with the *identical* trade
structure (range stop, +1x target, 40d time-stop, long-only) average **+0.139R**;
the real breakout's +0.226R sits at the **58th percentile** of the random
distribution (5–95%: −0.94 to +1.06). The breakout entry is statistically
indistinguishable from throwing a dart and applying the same exits. The structure
+ drift make the money; the pattern adds nothing.

## Interpretation

The breakout mechanic — the engine beneath most classical chart patterns — has
**no predictive edge on daily SPY**. Its backtest "profit" is long-only drift
dressed up by a win-rate-flattering target/stop structure, exactly the
pattern-illusion the Fidelity deck's own "Limits" slide warns about ("see patterns
where there aren't any", "look backwards rather than forward"). Three independent
tests (conditional distribution, protected split, random-entry null) agree.

**Important nuance — the principle isn't dead, the application is.** Time-series
momentum / breakout DOES work as the SLOW, DIVERSIFIED version that already
survived this project's holdout: monthly trend across ~7 uncorrelated markets
(`studies/trend.py`). What fails is the retail chart-pattern application: a fast
(20-day) breakout on a SINGLE equity index. The edge lives in diversification and
horizon, not in the shape on one chart.

## Decision

**REJECT** the breakout engine as a standalone SPY edge, and with it the
continuation patterns (triangles, rectangles, flags) that reduce to it — they
inherit a mechanic shown here to carry no information. The reversal patterns
(head-and-shoulders, double top/bottom) remain untested and are a separate
geometry (pivot structure, not a channel break); test those next if desired, via
automated pivot detection. Caveat: close-only daily data (no intrabar fills); the
information and null tests, which drive the verdict, don't depend on fills.
