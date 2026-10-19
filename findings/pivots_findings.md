# Finding: reversal patterns (double top/bottom, H&S) — rare, and no tradeable edge on SPY

Date: 2026-10-19. Data: daily SPY closes (`data/vix_spy.csv`), 2004-2026. Spec:
`studies/pivots.py`. Fractal pivots (window w=5, confirmed at i+w — causal),
then double top/bottom (High-Low-High / mirror, tops within 5%, trough ≥3% deep)
and head-and-shoulders (5 pivots, head ≥3% above shoulders, shoulders within 5%).
Entry = first neckline break within 30 bars of confirmation; stop beyond the
pattern extreme (1R); target = measured move; 60-bar time stop.

## Counts first (this is itself a finding)

| Pattern | triggers in 22 years | tradeable n |
|---|---|---|
| Double bottom | 147 | 75 |
| Double top | 76 | 51 |
| Inverse H&S | 13 | 13 |
| **Head-and-shoulders top** | **3** | **3** |

Head-and-shoulders — the most famous pattern of all — fires **3 times in 22 years**
on SPY; inverse H&S 13 times. You cannot build a book, or even run a valid test,
on 3 signals. On a single instrument these are **too rare to trade**, full stop.
(The Lo et al. study needed hundreds of stocks to get statistical power — that's
the only way to accumulate enough occurrences.)

## The two with enough samples — tested three ways

**Double bottom (bullish).** Looks like a winner: +0.189R/trade, PF 1.59, 64% win,
"SURVIVOR" on the full sample. But:
- *Information test:* edge over drift is +0.08%/+0.10%/−0.17% at 5/10/20 days —
  noise around the base rate.
- *Null control (decisive):* random entries with the **same stop/target structure**
  average **+0.264R**, and the real double-bottom sits at the **24th percentile** —
  i.e. the pattern does *worse* than the median random entry. The +0.19R is drift +
  trade structure; the pattern shape **subtracts** value. No edge.

**Double top (bearish).** This is the one genuinely interesting result:
- *Information test:* forward returns after a double top are **−0.26% / −0.88% /
  −2.03%** at 5/10/20d — clearly **below** the base rate (−1.1% below drift at 20d).
  So a double top **does carry real bearish information.** It's the only pattern in
  the whole project that showed conditional information beyond drift.
- But it is **not monetizable on SPY**: the tradeable short loses (−0.413R, PF 0.42,
  29% win), because shorting fights the index's structural up-drift, and the null
  shows the trade structure is *worse* than random shorts (12th percentile). Real
  bearish info, no tradeable edge on a long-drifting index.

**Inverse H&S / H&S top:** 13 and 3 occurrences — too few to conclude; both lose in
the tiny samples, but that's not statistically meaningful.

## Interpretation

- **Reversal patterns are too rare on one instrument to be a standalone strategy.**
  H&S at 3 hits/22yr is the headline.
- **Where there are enough samples, the shape adds no tradeable value.** Double
  bottom is drift+structure (and below random); double top carries genuine bearish
  information but can't be monetized by shorting a rising index.
- The **double-top bearish-information** result is the single most interesting
  signal found: it's real and conditional. The honest way to pursue it, if at all,
  would be across many instruments and/or as a **risk-off / exit** signal (reduce
  long exposure) rather than an outright short on SPY — not as a standalone trade.

## Decision

**REJECT** reversal patterns as a tradeable SPY edge: H&S/inverse-H&S too rare to
test; double bottom adds nothing beyond drift (below random); double top has real
bearish information but no tradeable edge on a long-biased index. Caveat: close-only
daily data (no intrabar fills) and modest samples — but the null control and the
rarity counts, which drive the verdict, don't depend on fills.

Combined with `breakout_findings.md`, this closes the chart-pattern program:
continuation patterns reduce to a breakout engine with no information; reversal
patterns are too rare and/or add nothing beyond drift. Consistent with the whole
project — durable edge is in risk premia and diversification (the trend sleeve),
not in shapes on a single chart.
