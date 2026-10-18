# Phase 0 — Frozen Spec, Instrument Map, and 1x Sizing

Status: **Both decisions RESOLVED — long/flat (§2), $5,000 start (§4).** Spec is
locked; no parameter changes without a full re-validation. One data run remains
to finalize the dollar sizing: the deployment-accurate curve on real data (§6).

This is the "lock the edge" deliverable from `TRADING_PLAN.md`. It pins down
*exactly* what you will trade, *in what*, and *at what size* — so that from
Phase 1 onward there are no decisions left to get wrong, only a checklist to
follow.

---

## 1. The frozen edge (verbatim from `studies/trend.py`)

Time-series momentum across a diversified, weakly-correlated basket. These are
the parameters that **survived the protected 2021–25 holdout (incl. the 2022
bear)** — the only thing in the whole project that did. They are now frozen.

| Parameter | Value | Code |
|---|---|---|
| Universe | 7 markets (see §2) | `data.TREND_UNIVERSE` |
| Trend signal | sign of trailing **252-day** total return | `lookback_days=252` |
| Vol-estimate window | trailing **63 days** of daily returns | `vol_lookback_days=63` |
| Per-position vol target | **10% annualized** (= 2.887%/mo = 1R) | `target_ann_vol=0.10` |
| Per-position leverage cap | **3.0x** | `max_leverage=3.0` |
| Rebalance | **month-end**, hold one month, re-evaluate | monthly loop |
| Costs modeled | **2 bps** × turnover per rebalance | `cost_bps=2.0` |

**The four rules, in one sentence each (this is the Phase 0 gate — you must be
able to state these from memory):**

1. **Entry:** at month-end, for each market, if its price today is higher than
   it was 252 trading days ago, hold it long next month; otherwise (see §2)
   hold nothing or go short.
2. **Exit / sizing:** size each position so its own expected risk equals a 10%
   annual-vol budget — scale exposure by `10%-target ÷ that market's recent
   realized vol`, capped at 3x — and the whole book is the equal-risk average
   across all markets.
3. **Rebalance:** act only at month-end. No intra-month adjustments, ever.
4. **Schedule:** once a month, same day, mechanical. The computer generates the
   target positions; you place them.

---

## 2. DECISION A — RESOLVED: long/flat (cash account, no shorting)

We ran both variants on the full 2004→2026 history. The per-trade gate results
(the correctly-measured numbers) across the protected split:

| Stage | long/short exp | gates | long/flat exp | gates |
|---|---|---|---|---|
| develop (2007–16) | +0.062R | 1 fail → rejected | **+0.124R** | **0 fail → SURVIVOR** |
| validate (2017–20) | −0.056R | 6 fail → rejected | +0.000R | 6 fail → rejected (flat) |
| holdout (2021–25) | +0.090R | 0 fail → SURVIVOR | **+0.205R** | **0 fail → SURVIVOR** |
| full-sample maxDD | −31.3R | | **−18.4R** | |

**Long/flat is better on develop AND holdout, passes all 7 gates on both, and
draws down far less.** On this long-biased, bull-dominated ETF universe the
short leg was a *net drag* — shorting equities/intl in their occasional
downtrends got whipsawed by sharp reversals. Holding cash instead of shorting
both earns more and is the only thing you can do in a plain cash account.
Decision A therefore resolves cleanly to **long/flat**, and happily the
simpler-to-run variant is also the better one. Operationally: `--long-flat`.

**Two honest caveats that do NOT change the decision but DO constrain
expectations:**

1. **Both variants were flat/negative in the validate window (2017–2020).**
   Long/flat was breakeven there (long/short lost). That is trend following's
   well-known multi-year drought regime (chop, no sustained trends). It is *in*
   the record and it *will* happen again. Plan for 1–3 year stretches where this
   book makes nothing. Quitting during one is how the 29-in-30 fail.

2. **The long/flat PORTFOLIO aggregate is optimistic** (full-sample Sharpe read
   0.97, the by-year R line looks strong). That is a *measurement artifact*: the
   current code drops cash/flat months from the equal-risk average, so it only
   averages the months you were actually in the market. Your real *deployed*
   return is lower, because in flat months you hold cash earning ~nothing.
   **Therefore we do NOT size off 0.97 Sharpe.** Sizing stays anchored to the
   conservative plan framework (§4): ~11–15% native return, ~12% vol, plan-for
   −30% drawdown. (A deployment-accurate portfolio curve — counting cash months
   — is the one remaining thing worth computing to tighten §4; it's optional and
   does not block Phase 0.)

---

## 3. Instrument map — the honest version

Only **3 of the 7** markets have a clean, liquid micro-future equivalent. The
rest do not, and pretending otherwise would break the diversification that is
the entire edge.

| Market | ETF (what was backtested) | Clean micro future? | How you actually trade it |
|---|---|---|---|
| US large-cap equity | **SPY** | **Yes → MES** (Micro E-mini S&P) | ETF now; MES at Rung 2 |
| US small-cap equity | **IWM** | **Yes → M2K** (Micro Russell 2000) | ETF now; M2K at Rung 2 |
| Gold | **GLD** | **Yes → MGC** (Micro Gold) | ETF now; MGC at Rung 2 |
| Developed intl equity | **EFA** | **No** liquid micro | ETF only |
| Long US Treasuries | **TLT** | **No** (ZN/ZB are full-size; micro-yield futures are inverse & not a price proxy) | ETF only |
| Broad commodities | **DBC** | **No** (it's a basket; MCL is only crude) | ETF only |
| US dollar index | **UUP** | **No** (DX is full-size; micro-FX are single pairs) | ETF only |

**Conclusion:** the instrument *is the 7-ETF basket*, exactly as validated.
Trade all seven as **ETF shares** in a normal brokerage account. Micros
(MES/M2K/MGC) are an optional capital-efficiency swap for three of the sleeves
*later*, once you want leverage — not a replacement for the book. There is no
way to run this exact book as "all micros," and that's fine.

---

## 4. 1x position sizing — rule first, dollars second

### The sizing rule (deterministic — no judgment)
Per rebalance, for each market `i` you are holding:

```
sleeve_dollar_vol  = V            # the same risk budget for every sleeve (equal risk)
position_notional_i = V / sigma_i # sigma_i = that market's recent annualized vol
shares_i = position_notional_i / price_i
```

`sigma_i` comes from the **trailing 63-day** realized vol the code already
computes — you refresh it every month. Low-vol markets (UUP, TLT) get *more*
dollars; high-vol markets (IWM) get *less*. That is what "equal risk" means.

### Choosing V so the book runs at its native ~12% vol
For N=7 markets at an average pairwise correlation ≈ 0.15:

```
portfolio_vol = V_frac * sqrt( N * (1 + (N-1)*rho) )
              = V_frac * sqrt( 7 * 1.9 ) = V_frac * 3.65
set 12% = V_frac * 3.65  ->  V_frac ≈ 3.3% of capital per sleeve
```

Representative exposures at 1x (annual vols are *illustrative* — the rule uses
live trailing vol, not these):

| Market | repr. σ | sleeve exposure (% of capital, when trend is ON) |
|---|---|---|
| SPY | 16% | 21% |
| IWM | 21% | 16% |
| EFA | 16% | 21% |
| TLT | 14% | 23% |
| GLD | 15% | 22% |
| DBC | 18% | 18% |
| UUP | 8% | 41% |
| **Gross when all 7 are ON** | | **≈ 160%** |

### The cash-account reality (important)
When every market is calm and trending, the vol-target *wants ~1.6x gross*. A
cash account caps you at **100% gross** — so in that all-on regime you scale
every sleeve down by ~0.62 and realized vol lands nearer ~7–8%, not 12%. That
is **conservative and fine** for Phases 0–2. Running the book at its true native
12% profile (and above) requires margin or futures — which is exactly what the
**leverage ladder** unlocks later. So "Rung 1 = 1.0x" in practice means: *no
extra portfolio multiplier, gross capped at 100%*.

### Dollar survivability check (the thing that actually matters)
At 1x, your whole account moves with the book. Plan emotionally for the
**plan-for** column, not the model column — fat tails make reality worse.

| Capital | ~1x annual vol (±) | model worst DD (~-13%) | **plan-for DD (-30%)** | ~1x expected yr (+11%) |
|---|---|---|---|---|
| $5,000 | $600 | -$650 | **-$1,500** | +$550 |
| $10,000 | $1,200 | -$1,300 | **-$3,000** | +$1,100 |
| $25,000 | $3,000 | -$3,250 | **-$7,500** | +$2,750 |
| $50,000 | $6,000 | -$6,500 | **-$15,000** | +$5,500 |

**DECISION B — RESOLVED: $5,000 start.** Plan-for drawdown ≈ **−$1,500**;
expected ~1x year ≈ +$550. This is deliberately small: Phases 0–2 buy *proof you
can execute*, not income. Size up only with salary contributions, never on a win
streak.

**The one thing that bites at $5k — fractional shares are mandatory.** Several
sleeves are high-priced ETFs (SPY and GLD trade in the hundreds of dollars per
share). At $5k a sleeve's target exposure is only a few hundred dollars, so
whole-share rounding would wreck the risk balance (you might hold 0 shares of
one market and an oversized slug of another). Use a broker that supports
**fractional-share** trading (Fidelity and Schwab both do) so you can hit each
sleeve's target weight precisely. Without fractional shares, $5k is too small to
run this book faithfully.

**The dollar figures above are provisional** — they use the plan's generic ~12%
vol. Once you run the deployment-accurate curve (§6) we replace them with the
book's *true* cash-capped vol and drawdown, which is likely lower (cash months +
the 100% gross cap both de-risk a $5k cash account).

---

## 5. Why this is sized to survive, not to impress

The expected return at 1x is ~$550/yr on $5k — trivial. **That is the point of
Phase 0–2.** You are not here to make money yet; you are buying proof that you
can hold a -30% drawdown and still place exactly what the rule says. The money
comes later, from salary contributions compounding on a book you've *earned*
the right to lever. If the dollar drawdown above makes you want to override the
rule, the number is too big — drop a line.

---

## 6. Re-confirm on real data (run on your PC)

The container here has no market-data network, so run these in the repo folder
`C:\Users\ishra\Claude\TradingStrategyFinder\edge-strategy-finder` with
`yfinance` installed (`pip install yfinance`):

```bash
# 1) Re-confirm the FROZEN long/short edge still holds across the protected split
python -m edge_finder.studies.trend --source yahoo

# 2) The variant you'll trade (long/flat). This now ALSO prints the
#    DEPLOYMENT-ACCURATE curve: real 1/N book, cash months counted, with both a
#    NATIVE line and a CASH-CAP line (gross capped at 100% = your $5k reality).
python -m edge_finder.studies.trend --source yahoo --long-flat
```

Decision A is already settled (long/flat won). What's left is to read the
**CASH-CAP** line from command #2 — its `vol` and `maxDD` are the real numbers
for a $5k cash account. Paste that block back and we finalize the §4 dollar
sizing (replace the provisional ±$600 / −$1,500 with the true figures).

---

## 7. Phase 0 exit gate (do not advance until all are true)

- [ ] You can state the entry, exit/sizing, rebalance, and schedule rules from
      memory (§1).
- [x] Decision A resolved: **long/flat**, on fresh full-history evidence —
      survives develop + holdout all-gates, beats long/short, cash-account native
      (§2).
- [x] Decision B resolved: **$5,000** start, fractional-share broker required
      (§4). Dollar sizing finalized once the §6 CASH-CAP curve is read.
- [ ] The 7 instruments and their tickers are written down (§3).
- [ ] The monthly signal is automatable (you're an engineer — a script that
      emails you the 7 target positions is Phase 1's first task).

When all five are checked, Phase 0 is done and you move to Phase 1 (paper).
