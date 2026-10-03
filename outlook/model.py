"""
PS 26086 sub-seasonal outlook: per gram panchayat, issued daily 1 May - 30 Sep, probabilities for weeks 1-4.

Events (CHIRPS GP-mean rain r[d]; week k of an issue on day i covers days i+7(k-1) .. i+7k-1):
  dry_k      all 7 days < 2.5 mm (IMD dry day)                       break / dry week
  wet_k      weekly total >= 1.5 x the GP's climatological weekly total (training seasons only)
  heavy_k    any day >= 30 mm                                         heavy downpour
  break3w    a run of >= 7 consecutive dry days (< 2.5 mm) inside days i .. i+20
  onset_k    the agronomic onset falls in week k (rows before that season's onset only)
  false3w    a 'false start' (sowing rains followed by a dry spell) occurs in days i .. i+20 (rows before onset only)
Agronomic onset (Marteau et al. 2009 style): first day d with r[d] >= 1 and r[d] + r[d+1] >= 20 mm that is NOT followed
by 7 consecutive days totalling < 5 mm within days d+2 .. d+21; a wet start that is followed by such a spell is a false start.

Features (all known at issue time): the event's climatological probability for this GP and calendar window (training
seasons only), recent rain (7 / 30 days), dry days in the last 14, season-to-date anomaly, wet starts so far and days
since the last one, MJO (OMI PC1, PC2, amplitude; day before issue), ENSO (weekly Nino 3.4, >= 4 days old), IOD
(previous month's DMI), calendar day, GP location and climatological mean.

Model: HistGradientBoostingClassifier per event x week. Validation: 9 season-blocked folds over 1981-2023 (each season
predicted by models that never saw it), Brier skill vs the same-fold climatology, 90 % CI by season bootstrap.

  python -m outlook.model            -> outlook/results/{cv_metrics.json, oof_*.npz}, outlook/models/*.joblib
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

REPO = Path(__file__).resolve().parents[1]
DATA, RES, MOD = REPO / "outlook" / "data", REPO / "outlook" / "results", REPO / "outlook" / "models"
NI = 153                      # issue days: 1 May (0) .. 30 Sep (152)
DRY, HEAVY = 2.5, 30.0
N_FOLDS = 9


def runs_dry(r):
    """r [..., D] -> for each day, length of the dry run (< DRY) ending at that day."""
    out = np.zeros(r.shape, np.int16)
    run = np.zeros(r.shape[:-1], np.int16)
    for d in range(r.shape[-1]):
        run = np.where(r[..., d] < DRY, run + 1, 0)
        out[..., d] = run
    return out


def onset_and_false(r):
    """r [Y, D, G] -> onset day index [Y, G] (NaN if none by 30 Sep) and false-start indicator [Y, D, G]."""
    Y, D, G = r.shape
    wet_start = (r[:, :-1] >= 1.0) & (r[:, :-1] + r[:, 1:] >= 20.0)                   # [Y, D-1, G]
    c = np.concatenate([np.zeros((Y, 1, G)), np.cumsum(r, 1)], 1)                      # prefix sums
    sum7 = c[:, 7:] - c[:, :-7]                                                         # 7-day total starting at day s
    dry7 = sum7 < 5.0                                                                   # [Y, D-6, G]
    onset = np.full((Y, G), np.nan, np.float32)
    false = np.zeros((Y, D, G), bool)
    for d in range(D - 1):
        lo, hi = d + 2, min(d + 21 - 6, dry7.shape[1] - 1)                              # dry spell starting d+2 .. d+15
        if lo > hi or d > 152:
            continue
        spell = dry7[:, lo:hi + 1].any(1)
        ws = wet_start[:, d]
        newly = ws & ~spell & np.isnan(onset)
        false[:, d] = ws & spell & np.isnan(onset)
        onset[newly] = d
    return onset, false


def build_events(r, onset, false):
    Y, D, G = r.shape
    ev = {}
    c = np.concatenate([np.zeros((Y, 1, G)), np.cumsum(r, 1)], 1)
    for k in range(1, 5):
        s = np.arange(NI) + 7 * (k - 1)
        ev[f"dry_{k}"] = np.stack([(r[:, a:a + 7] < DRY).all(1) for a in s], 1).astype(np.float32)
        ev[f"heavy_{k}"] = np.stack([(r[:, a:a + 7] >= HEAVY).any(1) for a in s], 1).astype(np.float32)
        ev[f"tot_{k}"] = np.stack([c[:, a + 7] - c[:, a] for a in s], 1).astype(np.float32)
    # a >= 7-day dry run lying entirely inside days i .. i+20 (runs are counted from day i: no credit for dry days
    # before the issue date, which the features already know)
    def run_in_window(i):
        run = np.zeros((Y, G), np.int16)
        hit = np.zeros((Y, G), bool)
        for d in range(i, i + 21):
            run = np.where(r[:, d] < DRY, run + 1, 0)
            hit |= run >= 7
        return hit
    ev["break3w"] = np.stack([run_in_window(i) for i in range(NI)], 1).astype(np.float32)
    before = np.arange(NI)[None, :, None] <= np.nan_to_num(onset, nan=1e9)[:, None, :]   # rows before onset
    for k in range(1, 5):
        lo = np.arange(NI)[None, :, None] + 7 * (k - 1)
        o = onset[:, None, :]
        e = ((o >= lo) & (o < lo + 7)).astype(np.float32)
        ev[f"onset_{k}"] = np.where(before, e, np.nan)
    fs = np.stack([false[:, i:i + 21].any(1) for i in range(NI)], 1).astype(np.float32)
    ev["false3w"] = np.where(before, fs, np.nan)
    return ev


def clim_prob(E, train_mask, half=15):
    """E [Y, NI, G] (NaN = not applicable) -> climatological probability [NI, G] from the training seasons, +-half days."""
    X = np.where(train_mask[:, None, None], E, np.nan)
    num = np.nansum(X, 0)
    den = np.sum(np.isfinite(X), 0).astype(np.float32)
    k = np.ones(2 * half + 1, np.float32)
    conv = lambda a: np.stack([np.convolve(a[:, g], k, mode="same") for g in range(a.shape[1])], 1)
    p = conv(num) / np.maximum(conv(den), 1)
    return np.clip(p, 0.002, 0.998)


def features(r, idx, onset_obs, clim_p, clim_mean, lat, lon, i_list):
    """Feature tensor [Y, len(i_list), G, F] using only information available at each issue day."""
    Y, D, G = r.shape
    c = np.concatenate([np.zeros((Y, 1, G)), np.cumsum(r, 1)], 1)
    dry = (r < DRY).astype(np.float32)
    cd = np.concatenate([np.zeros((Y, 1, G)), np.cumsum(dry, 1)], 1)
    ws_cum, last_ws = onset_obs
    F = []
    for j, i in enumerate(i_list):
        r7 = c[:, i] - c[:, max(i - 7, 0)]
        r30 = c[:, i] - c[:, max(i - 30, 0)]
        d14 = cd[:, i] - cd[:, max(i - 14, 0)]
        std = c[:, i]
        std_clim = clim_mean[None, :] * i
        f = [np.log(clim_p[i] / (1 - clim_p[i]))[None].repeat(Y, 0), np.log1p(r7), np.log1p(r30), d14,
             np.log1p(std) - np.log1p(std_clim), ws_cum[:, i], np.minimum(i - last_ws[:, i], 60),
             idx["omi_pc1"][:, i, None].repeat(G, 1), idx["omi_pc2"][:, i, None].repeat(G, 1),
             np.hypot(idx["omi_pc1"][:, i], idx["omi_pc2"][:, i])[:, None].repeat(G, 1),
             idx["nino34"][:, i, None].repeat(G, 1), idx["dmi"][:, i, None].repeat(G, 1),
             np.full((Y, G), np.sin(2 * np.pi * (i + 121) / 365)), np.full((Y, G), np.cos(2 * np.pi * (i + 121) / 365)),
             lat[None].repeat(Y, 0), lon[None].repeat(Y, 0), clim_mean[None].repeat(Y, 0)]
        F.append(np.stack(f, -1))
    return np.stack(F, 1).astype(np.float32)          # [Y, I, G, F]


FEATURE_NAMES = ["clim_logit", "rain7", "rain30", "dry_days14", "season_anom", "wet_starts", "days_since_wet_start",
                 "mjo_pc1", "mjo_pc2", "mjo_amp", "nino34", "dmi", "doy_sin", "doy_cos", "lat", "lon", "clim_mean"]


def observed_wet_starts(r):
    Y, D, G = r.shape
    ws = np.zeros((Y, D, G), bool)
    ws[:, 1:] = (r[:, :-1] >= 1.0) & (r[:, :-1] + r[:, 1:] >= 20.0)    # a 2-day wet start completed by day d-1... (known at d+1)
    known = np.zeros((Y, D, G), np.float32)
    known[:, 2:] = ws[:, :-2]                                           # known at issue day i if it ended before i
    cum = np.cumsum(known, 1)
    last = np.full((Y, D, G), -60.0, np.float32)
    for d in range(1, D):
        last[:, d] = np.where(known[:, d] > 0, d, last[:, d - 1])
    return cum, last


def main():
    RES.mkdir(parents=True, exist_ok=True)
    MOD.mkdir(parents=True, exist_ok=True)
    z = np.load(DATA / "gp_daily.npz")
    r = z["rain"].astype(np.float32)
    years = z["years"]
    lat, lon = z["lat"].astype(np.float32), z["lon"].astype(np.float32)
    idx = dict(np.load(DATA / "indices.npz"))
    Y, D, G = r.shape
    onset, false = onset_and_false(r)
    ev = build_events(r, onset, false)
    print(f"{Y} seasons x {G} GPs | onset found {np.isfinite(onset).mean():.0%} of GP-seasons, median "
          f"{np.nanmedian(onset):.0f} days after 1 May | base rates: "
          + ", ".join(f"{k} {np.nanmean(v):.3f}" for k, v in ev.items() if not k.startswith("tot")), flush=True)
    obs_ws = observed_wet_starts(r)
    fold = np.arange(Y) % N_FOLDS
    targets = [f"{e}_{k}" for e in ("dry", "wet", "heavy", "onset") for k in range(1, 5)] + ["break3w", "false3w"]
    I_all = list(range(NI))
    I_train = list(range(0, NI, 2))
    metrics, rng = {}, np.random.default_rng(0)
    for tname in targets:
        t0 = time.time()
        oof = np.full((Y, NI, G), np.nan, np.float32)
        oofc = np.full((Y, NI, G), np.nan, np.float32)
        for f in range(N_FOLDS):
            tr = fold != f
            if tname.startswith("wet"):
                k = int(tname[-1])
                T = ev[f"tot_{k}"]
                thr = 1.5 * clim_prob_mean(T, tr)
                E = (T >= thr[None]).astype(np.float32)
            else:
                E = ev[tname]
            cp = clim_prob(E, tr)
            cm = np.nanmean(r[tr][:, 31:153], (0, 1))
            Xtr = features(r[tr], {k: v[tr] for k, v in idx.items() if k != "years"}, (obs_ws[0][tr], obs_ws[1][tr]), cp, cm, lat, lon, I_train)
            ytr = E[tr][:, I_train]
            gsel = np.arange(G) % 2 == 0
            Xf, yf = Xtr[:, :, gsel].reshape(-1, Xtr.shape[-1]), ytr[:, :, gsel].reshape(-1)
            ok = np.isfinite(yf)
            mdl = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=400,
                                                 l2_regularization=1.0, random_state=0).fit(Xf[ok], yf[ok])
            te = ~tr
            Xte = features(r[te], {k: v[te] for k, v in idx.items() if k != "years"}, (obs_ws[0][te], obs_ws[1][te]), cp, cm, lat, lon, I_all)
            p = mdl.predict_proba(Xte.reshape(-1, Xte.shape[-1]))[:, 1].reshape(te.sum(), NI, G)
            oof[te] = p
            oofc[te] = cp[None].repeat(te.sum(), 0)
            if tname.startswith("wet"):
                ev.setdefault(f"wet_target_{tname[-1]}", np.full((Y, NI, G), np.nan, np.float32))[te] = E[te]
        Etrue = ev[f"wet_target_{tname[-1]}"] if tname.startswith("wet") else ev[tname]
        m = np.isfinite(Etrue) & np.isfinite(oof)
        y, p, c = Etrue[m], oof[m], oofc[m]
        yr = np.broadcast_to(np.arange(Y)[:, None, None], Etrue.shape)[m]
        bs, bsc = np.mean((p - y) ** 2), np.mean((c - y) ** 2)
        groups = [np.where(yr == a)[0] for a in range(Y)]
        groups = [g_ for g_ in groups if len(g_)]
        boots = []
        for _ in range(300):
            sel = np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))])
            boots.append(1 - np.mean((p[sel] - y[sel]) ** 2) / np.mean((c[sel] - y[sel]) ** 2))
        bins = np.clip((p * 10).astype(int), 0, 9)
        rel = [[float(p[bins == b].mean()), float(y[bins == b].mean()), int((bins == b).sum())] for b in range(10) if (bins == b).any()]
        metrics[tname] = {"bss": round(float(1 - bs / bsc), 4), "ci90": [round(float(np.percentile(boots, 5)), 4), round(float(np.percentile(boots, 95)), 4)],
                          "base_rate": round(float(y.mean()), 4), "brier": round(float(bs), 5), "brier_clim": round(float(bsc), 5),
                          "n": int(m.sum()), "reliability": rel}
        np.savez_compressed(RES / f"oof_{tname}.npz", p=oof.astype(np.float16), clim=oofc.astype(np.float16), y=Etrue.astype(np.float16))
        print(f"{tname:9s} BSS {metrics[tname]['bss']:+.3f} [{metrics[tname]['ci90'][0]:+.3f}, {metrics[tname]['ci90'][1]:+.3f}] "
              f"base {metrics[tname]['base_rate']:.3f} | {time.time() - t0:.0f}s", flush=True)
        json.dump(metrics, open(RES / "cv_metrics.json", "w"), indent=1)
    np.savez_compressed(RES / "onset.npz", onset=onset, years=years)
    print("DONE", flush=True)


def clim_prob_mean(T, train_mask, half=15):
    X = np.where(train_mask[:, None, None], T, np.nan)
    num, den = np.nansum(X, 0), np.sum(np.isfinite(X), 0).astype(np.float32)
    k = np.ones(2 * half + 1, np.float32)
    conv = lambda a: np.stack([np.convolve(a[:, g], k, mode="same") for g in range(a.shape[1])], 1)
    return conv(num) / np.maximum(conv(den), 1)


if __name__ == "__main__":
    main()
