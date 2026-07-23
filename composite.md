# ORB MFE/MAE Composite Study — 6B (GBP futures)

**Data:** 6B futures 5m + daily bars, 2023-07-24 → 2026-07-20 (UTC), cached QuantPad parquets from Propv1.
**Instrument caveat:** 6B is a *proxy* for spot GBPUSD. ATR-normalised excursions should transfer approximately, but confirm on spot before use.
**Event:** first 5m **close** beyond the Asia range (00:00–07:00 UTC hi/lo) at/after 08:00 UTC; entry at that bar's close; 240-minute (48-bar) excursion window, capped at session end. All bars completed; ATR(14) is prior-day.

## Session / event counts

| valid sessions | events | no-trade rate | long / short |
|---|---|---|---|
| 754 | 748 | **0.8%** | 378 / 370 |

⚠️ The trigger fires on 99.2% of sessions — the Asia range is narrow relative to the London/NY day, so "breakout" is near-universal and carries almost no selection information by itself.

## Terminal excursion percentiles (48 bars)

| pct | MFE (ATR) | MAE (ATR) | MFE (asia-width) | MAE (asia-width) |
|---|---|---|---|---|
| 25 | 0.083 | 0.091 | 0.24 | 0.27 |
| 50 | 0.170 | **0.181** | 0.53 | 0.56 |
| 70 | 0.280 | 0.291 | 0.85 | 0.93 |
| 80 | 0.363 | 0.389 | 1.12 | 1.15 |
| 90 | 0.493 | 0.521 | 1.66 | 1.77 |

**MAE ≥ MFE at every percentile, in both normalisations.** The typical breakout entry experiences slightly *more* adverse than favourable excursion — consistent with paying a breakout premium and getting mean-reversion drag.

- TP read (MFE p70): **0.280 ATR**
- SL read (MAE p85/p90 of sessions whose MFE reached the TP — the winners' heat): **0.228 / 0.262 ATR**
- Implied R:R (TP / SL-p90) = **1.07** → breakeven win rate **48.4%**
- Time exit: median MFE never flattens inside the window (first bar within 5% of terminal = bar 42 of 48, ≈210 min — that's √t diffusion still growing, not a plateau). Median MFE captured by exit candidate: 12:00 = 0.135, 16:00 = 0.166, 21:00 = 0.170 ATR.

## Null test (mandatory) — **FAILED**

500 rebuilds with random ≥08:00 entry times and random sides on the same event days, same machinery:

| observed median MFE/MAE ratio | null mean | null p5–p95 | empirical p |
|---|---|---|---|
| 0.938 | 1.009 | [0.876, 1.161] | **0.81** |

The real composite does **not** beat the shuffled null — 81% of random-entry composites produced a *better* MFE/MAE ratio than the actual ORB entries. The outward drift in the composite is mechanical range-edge diffusion, not breakout edge. **Per the study design: stop here.**

## Conditioning — asia_pctile quintiles (rolling 60-session rank of asia_width/ATR14)

| quintile | n | MFE p50 | MFE p70 | MAE p50 | MAE p90 | med MFE/MAE ratio |
|---|---|---|---|---|---|---|
| Q1 (compressed) | 141 | 0.144 | 0.237 | 0.149 | 0.397 | 0.96 |
| Q2 | 130 | 0.167 | 0.247 | 0.182 | 0.527 | 0.92 |
| Q3 | 131 | 0.179 | 0.315 | 0.152 | 0.441 | 1.18 |
| Q4 | 140 | 0.179 | 0.314 | 0.209 | 0.605 | 0.86 |
| Q5 (expanded) | 128 | 0.190 | 0.330 | 0.217 | 0.577 | 0.88 |

**Answer:** No — compression does *not* produce larger MFE/MAE ratios than expansion; the ratio is non-monotonic (Q3 highest at 1.18, Q1 = 0.96 vs Q5 = 0.88), so there is no router evidence in this cut.

## Verdict (3 lines)

1. **No TP/SL/time-exit is recommended from this study**: the composite fails the shuffled-entry null (p = 0.81), so the numbers that would have been read off (TP 0.28 ATR, SL 0.26 ATR, R:R 1.07, breakeven WR 48.4%) describe diffusion, not edge.
2. The 5m-close Asia-range breakout at 08:00+ UTC on 6B, as specified, has **no excursion advantage over random entry timing** — and MAE > MFE at every percentile means it is marginally worse than random.
3. Before any backtest of this trigger: the entry definition itself needs work (it fires 99.2% of days); do not tune TP/SL around it.

## Trial log (feeds Deflated Sharpe)

Variants examined in this study: 2 normalisations (ATR14, asia_width) × 1 TP read (p70) × 2 SL reads (winners' MAE p85, p90) × 3 time-exit candidates (12/16/21 UTC) = **12 variant combinations**, plus 1 conditioning cut (asia_pctile quintiles). Null test: 500 shuffles, seed 0, single test statistic (median MFE/MAE ratio). No parameter search was performed.

## Plots

- `mfe_mae_curves.png` — median MFE/MAE vs minutes-since-entry with IQR bands (ATR units). MAE tracks above MFE throughout.
- `quintile_bars.png` — MFE p70 vs MAE p90 by asia_pctile quintile with median-ratio labels.

*Reproduce: `python orb_composite.py` (reads the Propv1 cache; seed fixed).*
