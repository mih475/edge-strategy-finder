# Finding: short-term mean reversion is REAL but does not pass the protected split (a LEAD, not a survivor)

Date: 2026-10-18. Data: `data/vix_spy.csv` (yfinance), 2004-01-02 → 2026-10-16.
Spec: `studies/meanrev.py`. Long-only, buy-the-dip in an uptrend:
entry at close when RSI(2) < 10 AND close > SMA200; exit at close when close >
SMA5 or after 6 days; one position at a time; 1R = trailing 20-day daily vol at
entry; 1 bp/side cost. (Canonical Connors RSI(2) values — not tuned to this data.)
A VIX-spike-fade variant (VIX > 1.2x its 20d MA, same long-only/>SMA200 frame)
was run as a cross-check.

Motivation: the one real hint from `reddit_confluence_findings.md` — the strongest
*bearish* confluence days were followed by the biggest bounces. That is short-term
mean reversion, a documented liquidity-provision effect. This study tests it cleanly.

## Result

RSI(2), full sample: n=182, expectancy **+0.552R**, PF **1.88**, win **74.2%**,
maxDD −21.5R, MC P(negative) 0.3% — **passes all 7 gates on the full sample.**
VIX-fade full sample: n=113, +0.468R, PF 1.68, win 73.5% — also all 7 (full).

**But the protected split tells the real story (RSI(2)):**

| Stage | n | expectancy | PF | win% | gates | verdict |
|---|---|---|---|---|---|---|
| develop 2004–14  | 79 | +0.393R | 1.53 | 70.9% | 1 fail (bootstrap 90.6%) | rejected (near-miss) |
| validate 2015–19 | 30 | +0.023R | 1.02 | 70.0% | 5 fail | **rejected (edge absent)** |
| holdout 2020–26  | 57 | +1.003R | 4.08 | 80.7% | 0 fail | survivor |

The effect was strong 2004–14, **gone 2015–19**, strong again 2020–26. Validate is
a clean fail: PF ~1.0, bootstrap P(mean>0)=56% (coin flip), and **tail-drop goes
negative (−0.087R)** — remove the single best trade and the window is a net loss.
The positive full-sample number leans on a few large wins. VIX-fade is similar:
full-sample survivor, rejected on all three splits (1–2 gates each).

## Interpretation

1. **Real effect, not noise.** Unlike the confluence vote (zero directional
   skill), buy-the-dip-in-an-uptrend shows a genuine, documented edge on develop
   AND holdout. This is the first signal derived from the Reddit idea that is not
   a coin flip.
2. **Does NOT pass the discipline.** By the project rule (survive the protected
   split; never tune to validate/holdout), the 2015–19 collapse disqualifies it as
   a validated edge. The full-sample "SURVIVOR" is an in-sample mirage — exactly
   what the split exists to expose. Do NOT trade it on the strength of the
   full-sample card.
3. **The 74% win rate is a trap**, and is almost certainly the source of the
   Reddit post's "70–85%" claim. Mean reversion structurally wins often and loses
   big occasionally (2018: −18.7R in one year; the negative validate tail). Win
   rate flatters; expectancy + tail are the truth the gates measure.
4. **Risk character is SHORT volatility** — selling insurance. Same family as the
   rejected VRP put-spread sleeve, and the *opposite* of the trend sleeve
   (long-vol, wins in crises). It would NOT diversify the trend book; it would
   concentrate the same crash exposure. Two short-vol sleeves that both bleed in
   2008/2020/2022 are not a portfolio.

## Correlation check (2026-10-19): redundant short-vol, does not diversify trend

Monthly-return correlations, 2004-2026 (272 months), mean-rev vs the other
sleeves (VRP from the variance-swap study; trend proxied SPY-only long/flat here,
since the full ETF book wasn't loaded):

| | MeanRev | VRP | TrendSPY | SPY |
|---|---|---|---|---|
| MeanRev | 1.00 | 0.19 | 0.28 | 0.19 |

Headline correlations look low (~0.2) — superficially "diversifying." **They are
misleading.** Mean-rev is flat ~49% of months (active only 51%), which mechanically
damps correlation, and the low average hides WHERE the losses fall. In sharp
down-SPY months (SPY < −3%, n=39): mean-rev averages **−0.996R and is positive
only 15% of the time** — it gets crushed in exactly the selloffs a book needs
protection from. VRP is the same side (−0.41R, short-vol). The diversified trend
book is the sleeve that is *positive* in those crises (long-vol).

**Conclusion:** mean-rev is the same risk family as VRP — short-vol, crash-
exposed — so it competes for the one short-vol slot rather than adding an
independent edge, and its losses cluster in the crises trend is meant to hedge.
Combined with failing the protected split, it is retired. (Caveat: trend here is
a SPY-only proxy; the crisis-clustering point comes from mean-rev's own behavior
and does not depend on the proxy.)

## Decision

**LEAD, not a survivor. Not tradeable as-is.** The next honest step, IF pursued,
is study on the **develop window only** (no tuning to validate/holdout), and —
only if it earns its keep — evaluation for correlation against the trend sleeve
via `combine.py`, where its value (if any) is as a weakly-correlated add-on, not a
standalone. Explicitly do NOT sweep RSI/exit thresholds to force validate to pass;
that is the overfitting failure this repo was built to prevent.
