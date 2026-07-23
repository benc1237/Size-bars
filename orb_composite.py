"""ORB MFE/MAE composite study -- 6B futures (proxy for spot GBPUSD).
Reads TP/SL/time-exit off the excursion distribution; no parameter search.
Data: cached QuantPad parquets from the Propv1 backtest project (UTC)."""
import numpy as np, pandas as pd, matplotlib.pyplot as plt

DATA = r"C:\Users\benc1\OneDrive\claude\Propv1\data"
rng = np.random.default_rng(0)
df5 = pd.read_parquet(f"{DATA}/6BFUT_5m_back_1689973800000_1784581800000.parquet")
d1 = pd.read_parquet(f"{DATA}/6BFUT_1d_back_1689973800000_1784581800000.parquet")
df5.index, d1.index = df5.index.tz_localize(None), d1.index.tz_localize(None)
H, L, C = df5.h.to_numpy(), df5.l.to_numpy(), df5.c.to_numpy()
day = df5.index.normalize()
dsec = day.to_numpy()

# ---- Step 1: session table (one row per day) ------------------------------
tr = np.maximum(d1.h - d1.l, np.maximum((d1.h - d1.c.shift()).abs(), (d1.l - d1.c.shift()).abs()))
asia = df5[df5.index.hour < 7]
sess = asia.groupby(asia.index.normalize()).agg(asia_hi=("h", "max"), asia_lo=("l", "min"))
sess["asia_width"] = sess.asia_hi - sess.asia_lo
sess["atr14"] = tr.rolling(14).mean().shift(1).reindex(sess.index)  # prior-day only
sess["asia_pctile"] = (sess.asia_width / sess.atr14).rolling(60).rank(pct=True)
S = sess.reindex(day)
brk = (df5.index.hour >= 8) & ((C > S.asia_hi.to_numpy()) | (C < S.asia_lo.to_numpy()))
t0 = pd.Series(df5.index[brk], index=day[brk]).groupby(level=0).first()
evs = sess.loc[t0.index].assign(t0=t0).dropna(subset=["atr14"])
evs["pos"] = df5.index.get_indexer(pd.DatetimeIndex(evs.t0))
evs["side"] = np.where(C[evs.pos] > evs.asia_hi, 1, -1)
evs["entry"] = C[evs.pos]  # entry at close of breakout bar (completed bar)
ok = sess.dropna(subset=["atr14"]).query("asia_width > 0")
print(f"sessions={len(ok)} events={len(evs)} no-trade rate={1 - len(evs)/len(ok):.1%} "
      f"long={int((evs.side > 0).sum())} short={int((evs.side < 0).sum())}")

# ---- Step 2: excursion matrices (48 x 5m bars after t0, same session only) --
def excur(pos, side, entry, norm):
    idx = np.minimum(pos[:, None] + np.arange(1, 49), len(C) - 1)
    live = dsec[idx] == dsec[pos][:, None]          # mask bars past session end
    h, l = np.where(live, H[idx], np.nan), np.where(live, L[idx], np.nan)
    fav, adv = np.where(side[:, None] > 0, h, l), np.where(side[:, None] > 0, l, h)
    mfe = np.maximum(np.fmax.accumulate(side[:, None] * (fav - entry[:, None]), 1), 0)
    mae = np.maximum(np.fmax.accumulate(-side[:, None] * (adv - entry[:, None]), 1), 0)
    return mfe / norm[:, None], mae / norm[:, None]

pos, side, entry = evs.pos.to_numpy(), evs.side.to_numpy(), evs.entry.to_numpy()
MFE, MAE = excur(pos, side, entry, evs.atr14.to_numpy())          # ATR units
MFEw, MAEw = excur(pos, side, entry, evs.asia_width.to_numpy())   # asia-width units

# ---- Step 3: read the distribution ----------------------------------------
P = [25, 50, 70, 80, 90]
tm, ta = MFE[:, -1], MAE[:, -1]
tab = pd.DataFrame({"MFE_atr": np.nanpercentile(tm, P), "MAE_atr": np.nanpercentile(ta, P),
                    "MFE_aw": np.nanpercentile(MFEw[:, -1], P),
                    "MAE_aw": np.nanpercentile(MAEw[:, -1], P)}, index=P).round(3)
TP = np.nanpercentile(tm, 70)
win = tm >= TP                                     # heat taken by eventual winners
SL85, SL90 = np.nanpercentile(ta[win], [85, 90])
med = np.nanmedian(MFE, 0)
flat = int(np.argmax(med >= 0.95 * med[-1])) + 1   # first bar within 5% of terminal median
t0m = (pd.DatetimeIndex(evs.t0).hour * 60 + pd.DatetimeIndex(evs.t0).minute).to_numpy()
texit = {}
for T in (12, 16, 21):                             # 3 discrete candidates, no sweep
    n = np.clip((T * 60 - t0m) // 5 - 1, 1, 48)
    texit[f"{T:02d}:00"] = np.nanmedian(np.where(T * 60 - t0m < 10, 0, MFE[np.arange(len(evs)), n - 1]))
print(tab, f"\nTP(p70 MFE)={TP:.3f} ATR | SL winners' MAE p85={SL85:.3f} p90={SL90:.3f} ATR")
print(f"median-MFE flattens at bar {flat} ({flat*5}m) | median MFE captured by exit: {({k: round(v,3) for k,v in texit.items()})}")
print(f"R:R(TP/SL90)={TP/SL90:.2f} breakeven WR={1/(1+TP/SL90):.1%}")

# ---- Step 4: null test (shuffled entry times/sides on same days, 500x) -----
eligp = np.flatnonzero(df5.index.hour >= 8)
edays = dsec[eligp]
lo, hi = np.searchsorted(edays, evs.index.to_numpy()), np.searchsorted(edays, evs.index.to_numpy(), side="right")
obs = np.nanmedian(tm) / np.nanmedian(ta)
null = []
for _ in range(500):
    rp = eligp[lo + (rng.random(len(evs)) * (hi - lo)).astype(int)]
    f, a = excur(rp, rng.choice(np.array([-1, 1]), len(evs)), C[rp], evs.atr14.to_numpy())
    null.append(np.nanmedian(f[:, -1]) / np.nanmedian(a[:, -1]))
pval = (1 + np.sum(np.array(null) >= obs)) / (len(null) + 1)
print(f"observed med MFE/MAE ratio={obs:.3f} | null mean={np.mean(null):.3f} p5-p95=[{np.percentile(null,5):.3f},{np.percentile(null,95):.3f}] p={pval:.4f}")

# ---- Step 5: one conditioning cut -- asia_pctile quintiles -----------------
q = pd.qcut(evs.asia_pctile, 5, labels=False)
g = pd.DataFrame({"MFE": tm, "MAE": ta, "q": q.to_numpy()}).dropna().groupby("q")
qt = g[["MFE", "MAE"]].quantile([.25, .5, .7, .8, .9]).unstack().round(3)
qt["ratio_med"] = (g.MFE.median() / g.MAE.median()).round(2)
qt["n"] = g.size()
print(qt.to_string())

# ---- Plots (palette: dataviz reference, light mode) ------------------------
SURF, INK, SEC, MUT, GRID, BLU, ORG = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#2a78d6", "#eb6834"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": SEC, "xtick.color": MUT, "ytick.color": MUT, "text.color": INK, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "Segoe UI", "axes.axisbelow": True})
mins = np.arange(1, 49) * 5
fig, ax = plt.subplots(figsize=(9, 5))
for M, c, lab in [(MFE, BLU, "MFE"), (MAE, ORG, "MAE")]:
    ax.fill_between(mins, np.nanpercentile(M, 25, 0), np.nanpercentile(M, 75, 0), color=c, alpha=0.14, lw=0)
    ax.plot(mins, np.nanmedian(M, 0), color=c, lw=2, label=lab)
    ax.annotate(lab, (mins[-1], np.nanmedian(M, 0)[-1]), xytext=(6, 0), textcoords="offset points",
                color=c, va="center", fontweight="bold")
ax.axvline(flat * 5, color=MUT, lw=1, ls=":")
ax.annotate(f"median MFE within 5% of terminal: bar {flat}", (flat * 5, ax.get_ylim()[1] * 0.95), color=MUT, fontsize=9)
ax.set(xlabel="minutes since entry", ylabel="excursion (ATR units)")
ax.set_title("ORB composite: median MFE / MAE with IQR band (6B, ATR units)", color=INK)
ax.legend(frameon=False, loc="center left")
fig.savefig("mfe_mae_curves.png", dpi=150, bbox_inches="tight")
x = np.arange(len(qt))
fig2, ax2 = plt.subplots(figsize=(8, 5))
ax2.bar(x - 0.17, qt[("MFE", 0.7)], 0.3, color=BLU, label="MFE p70 (TP read)", edgecolor=SURF, linewidth=2)
ax2.bar(x + 0.17, qt[("MAE", 0.9)], 0.3, color=ORG, label="MAE p90 (SL read)", edgecolor=SURF, linewidth=2)
for xi, r in zip(x, qt["ratio_med"]):
    ax2.annotate(f"ratio {r}", (xi, max(qt[("MFE", 0.7)][xi], qt[("MAE", 0.9)][xi]) + 0.02), ha="center", color=SEC, fontsize=9)
ax2.set_xticks(x, [f"Q{i+1}" for i in x])
ax2.set(xlabel="asia_pctile quintile (Q1 = compressed, Q5 = expanded)", ylabel="terminal excursion (ATR units)")
ax2.set_title("TP/SL percentile reads by Asia-range quintile", color=INK)
ax2.legend(frameon=False)
fig2.savefig("quintile_bars.png", dpi=150, bbox_inches="tight")
