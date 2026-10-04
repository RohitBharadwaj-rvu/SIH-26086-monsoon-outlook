"""
GEFS hybrid v2 (specification fixed before results): calibrated ensemble, event-matched member features, lean stacker.

  1. Calibration: GEFS daily rain at each panchayat is quantile-mapped to observed CHIRPS panchayat rain, separately for
     forecast weeks 1-4. The mapping is fitted on reforecast seasons that exclude the evaluated season's half
     (2000-09 <-> 2010-19), and on all of 2000-2019 for the operational test and the final model.
  2. Event-matched member features: each event's own definition is applied to every member's 28-day trajectory:
     dry / wet (>= 1.5 x the panchayat normal) / heavy week k, >= 7-day dry run in 21 days, agronomic onset in week k
     (wet start from 25 May not followed by a 7-day spell < 5 mm), false start within 21 days. Feature = member fraction.
  3. Lean stacker: logistic regression with the outlook's logit as a fixed offset (it learns corrections only) on the
     target's own features (2-5 inputs + run age), strong L2. Validated leave-one-season-out over 2000-2019; final
     stackers applied unchanged to operational GEFS 2021-2023 as an independent test.
  4. Blend: equal-weight mean of the GFS and GEFS-v2 hybrid probabilities where both exist (no fitting), scored on
     2015-2019 and 2021-2023.

  python -m outlook.stack_gefs2 ckpts/gefs  -> outlook/results/stack_gefs2{,_blend}.npz / _metrics.json, outlook/models/stack_gefs2_*.joblib
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
from scipy.optimize import minimize

from outlook.model import DATA, DRY, HEAVY, MOD, NI, ONSET_START, RES
from outlook.stack_gefs import ALL, OPS_YEARS, TARGETS, YEARS, gefs_gp, logit

C = 0.005
HALF_A, HALF_B = list(range(2000, 2010)), list(range(2010, 2020))
QS = np.linspace(0, 1, 401)
FEATS = {"dry": lambda k: [f"tot{k}", f"fdry{k}"], "wet": lambda k: [f"tot{k}", f"fwet{k}"],
         "heavy": lambda k: [f"tot{k}", f"fheavy{k}"], "onset": lambda k: [f"fon{k}", f"tot{k}"]}
FEATS_T = {"break3w": ["fbreak", "tot1", "tot2", "tot3"], "false3w": ["ffalse", "fon123", "tot1"]}


def target_feats(t):
    if t in FEATS_T:
        return FEATS_T[t] + ["age"]
    e, k = t.rsplit("_", 1)
    return FEATS[e](k) + ["age"]


def runs_for_year(runs, y):
    """-> E [NI, G, M, 28] raw member rain from the issue day (NaN where no run within 6 days), age [NI]."""
    if y not in runs:
        return None, None
    inits, R = runs[y]
    G, M = R.shape[2], R.shape[1]
    E = np.full((NI, G, M, 28), np.nan, np.float32); age = np.full(NI, np.nan, np.float32)
    for i in range(NI):
        t = date(y, 5, 1) + timedelta(days=i)
        c = [n for n, d in enumerate(inits) if 0 <= (t - d).days <= 6]
        if c:
            n = c[-1]; a = (t - inits[n]).days
            E[i] = R[n][..., a:a + 28].transpose(1, 0, 2); age[i] = a
    return E, age


def fit_qm(Es, obs, years, rng):
    """quantile maps per forecast week from member values vs observed rain on the same target days."""
    qm = []
    for w in range(4):
        g, o = [], []
        for y in years:
            E = Es.get(y)
            if E is None:
                continue
            a = obs[y]                                                                   # [D, G]
            ii, gg = np.where(np.isfinite(E[:, :, 0, 0]))
            s = rng.choice(len(ii), min(4000, len(ii)), replace=False)
            i, g_ = ii[s], gg[s]
            d = rng.integers(7 * w, 7 * w + 7, len(s))
            g.append(E[i, g_, :, d].ravel()); o.append(np.repeat(a[i + d, g_], E.shape[2]))
        g, o = np.concatenate(g), np.concatenate(o)
        qm.append((np.quantile(g, QS), np.quantile(o, QS)))
    return qm


def apply_qm(E, qm):
    X = np.empty_like(E)
    for w in range(4):
        gq, oq = qm[w]
        X[..., 7 * w:7 * w + 7] = np.interp(E[..., 7 * w:7 * w + 7], gq, oq)
    return X


def member_feats(X, age, normal, y):
    """X [NI, G, M, 28] calibrated rain; normal [NI, G, 4] weekly normal -> dict name -> [NI, G]."""
    f = {}
    for k in range(1, 5):
        w = X[..., 7 * (k - 1):7 * k]; S = w.sum(-1)
        f[f"tot{k}"] = np.log1p(S.mean(-1))
        f[f"fdry{k}"] = (w < DRY).all(-1).mean(-1)
        f[f"fheavy{k}"] = (w >= HEAVY).any(-1).mean(-1)
        f[f"fwet{k}"] = (S >= 1.5 * normal[..., k - 1][..., None]).mean(-1)
    run = np.zeros(X.shape[:-1], np.int16); hit = np.zeros(X.shape[:-1], bool)
    for d in range(21):
        run = np.where(X[..., d] < DRY, run + 1, 0); hit |= run >= 7
    f["fbreak"] = hit.mean(-1)
    # agronomic onset / false start on each member (wet start from 25 May; dry-spell check truncated at day 28)
    ws = (X[..., :-1] >= 1.0) & (X[..., :-1] + X[..., 1:] >= 20.0)                       # [NI, G, M, 27]
    c = np.concatenate([np.zeros(X.shape[:-1] + (1,), np.float32), np.cumsum(X, -1)], -1)
    dry7 = (c[..., 7:] - c[..., :-7]) < 5.0                                               # spell starting at s: [.., 22]
    calday = np.arange(NI)[:, None] + np.arange(27)[None, :]                              # issue day + d
    ok_cal = (calday >= ONSET_START)[:, None, None, :]
    onset_d = np.full(X.shape[:-1], 99, np.int16); false_any = np.zeros(X.shape[:-1], bool)
    for d in range(27):
        lo, hi = d + 2, min(d + 15, dry7.shape[-1] - 1)
        spell = dry7[..., lo:hi + 1].any(-1) if lo <= hi else np.zeros(X.shape[:-1], bool)
        start = ws[..., d] & ok_cal[..., d] & (onset_d == 99)
        if d <= 20:
            false_any |= start & spell
        onset_d = np.where(start & ~spell, d, onset_d)
    for k in range(1, 5):
        f[f"fon{k}"] = ((onset_d >= 7 * (k - 1)) & (onset_d < 7 * k)).mean(-1)
    f["fon123"] = (onset_d < 21).mean(-1)
    f["ffalse"] = false_any.mean(-1)
    f["age"] = np.broadcast_to(age[:, None], f["tot1"].shape)
    out = {k: v.astype(np.float32) for k, v in f.items()}
    for v in out.values():
        v[np.isnan(age)] = np.nan                                                         # no run within 6 days
    return out


def weekly_normal(r, yrs_all, exclude):
    """GP normal weekly totals by issue day and lead week from CHIRPS seasons not in `exclude` -> [NI, G, 4]."""
    keep = [a for a, y in enumerate(yrs_all) if y not in exclude]
    c = np.concatenate([np.zeros((len(keep), 1, r.shape[2])), np.cumsum(r[keep], 1)], 1)
    out = np.zeros((NI, r.shape[2], 4), np.float32)
    for k in range(4):
        s = np.arange(NI) + 7 * k
        out[..., k] = (c[:, s + 7] - c[:, s]).mean(0)
    return out


def fit_offset(Z, off, y):
    """logistic with fixed offset: p = sigmoid(off + b0 + Z b), L2 1/(2C) on b."""
    def f(w):
        z = off + w[0] + Z @ w[1:]
        p = 1 / (1 + np.exp(-z))
        loss = np.sum(np.logaddexp(0, z) - y * z) + 0.5 / C * np.sum(w[1:] ** 2)
        g = np.concatenate([[np.sum(p - y)], Z.T @ (p - y) + w[1:] / C])
        return loss, g
    return minimize(f, np.zeros(Z.shape[1] + 1), jac=True, method="L-BFGS-B").x


def predict_offset(w, Z, off):
    return 1 / (1 + np.exp(-(off + w[0] + Z @ w[1:])))


def main(gefs_dir: Path):
    t0 = time.time()
    gd = np.load(DATA / "gp_daily.npz")
    r = gd["rain"].astype(np.float32); yrs_all = [int(y) for y in gd["years"]]
    glat, glon = gd["lat"].astype(np.float64), gd["lon"].astype(np.float64)
    G = len(glat)
    runs = gefs_gp(gefs_dir, glat, glon)
    Es, ages = {}, {}
    for y in ALL:
        Es[y], ages[y] = runs_for_year(runs, y)
    obs = {y: r[yrs_all.index(y)] for y in ALL}
    rng = np.random.default_rng(0)
    qms = {"A": fit_qm(Es, obs, HALF_B, rng), "B": fit_qm(Es, obs, HALF_A, rng), "all": fit_qm(Es, obs, YEARS, rng)}
    normals = {"A": weekly_normal(r, yrs_all, HALF_A), "B": weekly_normal(r, yrs_all, HALF_B),
               "all": weekly_normal(r, yrs_all, OPS_YEARS)}
    print("quantile maps (obs mm at GEFS 50/90/99th pct, week 1):",
          [round(float(np.interp(np.quantile(qms['all'][0][0], q), qms['all'][0][0], qms['all'][0][1])), 1) for q in (0.5, 0.9, 0.99)],
          f"| {time.time() - t0:.0f}s", flush=True)
    # features: validation version (calibration never saw the evaluated half) and final/ops version
    Fv, Ff = {}, {}
    for y in ALL:
        if Es[y] is None:
            continue
        if y in YEARS:
            h = "A" if y in HALF_A else "B"
            Fv[y] = member_feats(apply_qm(Es[y], qms[h]), ages[y], normals[h], y)
        Ff[y] = member_feats(apply_qm(Es[y], qms["all"]), ages[y], normals["all"], y)
    del Es
    print(f"member features for {len(Ff)} seasons | {time.time() - t0:.0f}s", flush=True)
    yi = [yrs_all.index(y) for y in ALL]
    gsel = np.arange(G) % 2 == 0
    metrics, stacked = {}, {}
    for ev in TARGETS:
        z = np.load(RES / f"oof_{ev}.npz")
        p, c, yv = (z[k].astype(np.float32)[yi] for k in ("p", "clim", "y"))
        names = target_feats(ev)
        Xv = np.full(p.shape + (len(names),), np.nan, np.float32); Xf = Xv.copy()
        for a, y in enumerate(ALL):
            if y in Fv:
                Xv[a] = np.stack([Fv[y][n] for n in names], -1)
            if y in Ff:
                Xf[a] = np.stack([Ff[y][n] for n in names], -1)
        off = logit(p)
        isref = np.array([y in YEARS for y in ALL]); isops = np.array([y in OPS_YEARS for y in ALL])
        okv = np.isfinite(Xv[..., 0]) & np.isfinite(yv) & np.isfinite(p) & isref[:, None, None]
        okf = np.isfinite(Xf[..., 0]) & np.isfinite(yv) & np.isfinite(p)
        ps = p.copy()
        for k, y in enumerate(YEARS):
            a = ALL.index(y)
            tr = okv & gsel[None, None, :]; tr[a] = False
            te = np.zeros_like(okv); te[a] = okv[a]
            if not te.any():
                continue
            mu, sd = Xv[tr].mean(0), Xv[tr].std(0) + 1e-6
            w = fit_offset((Xv[tr] - mu) / sd, off[tr], yv[tr])
            ps[te] = predict_offset(w, (Xv[te] - mu) / sd, off[te])
        m = okv
        used = [y for a, y in enumerate(ALL) if m[a].any()]
        bs = lambda q, mm: float(np.mean((q[mm] - yv[mm]) ** 2))
        yr_of = np.broadcast_to(np.arange(len(ALL))[:, None, None], m.shape)[m]
        groups = [g_ for g_ in (np.where(yr_of == a)[0] for a in range(len(ALL))) if len(g_)]
        sv, cv, yy = ps[m], c[m], yv[m]
        boots = [1 - np.mean((sv[s_] - yy[s_]) ** 2) / np.mean((cv[s_] - yy[s_]) ** 2)
                 for s_ in (np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))]) for _ in range(400))]
        metrics[ev] = {"bss_outlook": round(1 - bs(p, m) / bs(c, m), 4), "bss_stacked": round(1 - bs(ps, m) / bs(c, m), 4),
                       "ci90_stacked": [round(float(np.percentile(boots, 5)), 4), round(float(np.percentile(boots, 95)), 4)],
                       "n": int(m.sum()), "seasons": f"{len(used)} seasons {used[0]}-{used[-1]} (leave-one-season-out)",
                       "years": used, "inputs": "outlook + calibrated GEFS 11-member event fractions", "features": names}
        # final stacker: all reforecast seasons, all-season calibration; applied unchanged to the operational years
        trf = okf & isref[:, None, None] & gsel[None, None, :]
        mu, sd = Xf[trf].mean(0), Xf[trf].std(0) + 1e-6
        w = fit_offset((Xf[trf] - mu) / sd, off[trf], yv[trf])
        mo = okf & isops[:, None, None]
        if mo.any():
            ps[mo] = predict_offset(w, (Xf[mo] - mu) / sd, off[mo])
            metrics[ev]["ops_test"] = {"years": [y for a, y in enumerate(ALL) if mo[a].any()],
                                       "bss_outlook": round(1 - bs(p, mo) / bs(c, mo), 4), "bss_stacked": round(1 - bs(ps, mo) / bs(c, mo), 4),
                                       "n": int(mo.sum())}
        joblib.dump({"w": w, "mu": mu, "sd": sd, "features": names, "qm": qms["all"], "normal": normals["all"], "C": C},
                    MOD / f"stack_gefs2_{ev}.joblib", compress=3)
        stacked[ev] = ps.astype(np.float16)
        o = metrics[ev].get("ops_test")
        print(f"{ev:9s} outlook {metrics[ev]['bss_outlook']:+.3f} -> v2 {metrics[ev]['bss_stacked']:+.3f} "
              f"[{metrics[ev]['ci90_stacked'][0]:+.3f}, {metrics[ev]['ci90_stacked'][1]:+.3f}]"
              + (f" | ops {o['bss_outlook']:+.3f}->{o['bss_stacked']:+.3f}" if o else "")
              + f" | coef " + " ".join(f"{n} {v:+.2f}" for n, v in zip(names, w[1:])) + f" | {time.time() - t0:.0f}s", flush=True)
    json.dump(metrics, open(RES / "stack_gefs2_metrics.json", "w"), indent=1)
    np.savez_compressed(RES / "stack_gefs2.npz", years=np.array(ALL), **stacked)
    blend(stacked, yi, rng)


def blend(gefs2, yi_all, rng):
    """equal-weight mean of the GFS hybrid (LOSO 2015-2023) and GEFS v2 (LOSO 2015-19, operational-test 2021-23)."""
    sg = np.load(RES / "stack.npz"); gy = [int(y) for y in sg["years"]]
    both = [y for y in gy if y in ALL and y != 2020]
    gd = np.load(DATA / "gp_daily.npz"); yrs_all = [int(y) for y in gd["years"]]
    metrics, out = {}, {}
    for ev in [t for t in sg.files if t in gefs2]:
        z = np.load(RES / f"oof_{ev}.npz")
        rows = [yrs_all.index(y) for y in both]
        p, c, yv = (z[k].astype(np.float32)[rows] for k in ("p", "clim", "y"))
        a = sg[ev].astype(np.float32)[[gy.index(y) for y in both]]
        b = gefs2[ev].astype(np.float32)[[ALL.index(y) for y in both]]
        q = 0.5 * (a + b)
        m = np.isfinite(yv) & np.isfinite(q) & (a != p) & (b != p)                          # rows where both hybrids ran
        bs = lambda x: float(np.mean((x[m] - yv[m]) ** 2))
        yr_of = np.broadcast_to(np.arange(len(both))[:, None, None], m.shape)[m]
        groups = [g_ for g_ in (np.where(yr_of == k)[0] for k in range(len(both))) if len(g_)]
        qv, cv, yy = q[m], c[m], yv[m]
        boots = [1 - np.mean((qv[s_] - yy[s_]) ** 2) / np.mean((cv[s_] - yy[s_]) ** 2)
                 for s_ in (np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))]) for _ in range(400))]
        metrics[ev] = {"bss_outlook": round(1 - bs(p) / bs(c), 4), "bss_stacked": round(1 - bs(q) / bs(c), 4),
                       "bss_gfs_same_rows": round(1 - bs(a) / bs(c), 4), "bss_gefs2_same_rows": round(1 - bs(b) / bs(c), 4),
                       "ci90_stacked": [round(float(np.percentile(boots, 5)), 4), round(float(np.percentile(boots, 95)), 4)],
                       "n": int(m.sum()), "seasons": f"{len(both)} seasons {both[0]}-{both[-1]} (no fitting)", "years": both,
                       "inputs": "mean of GFS and GEFS-v2 hybrids"}
        out[ev] = q.astype(np.float16)
        mm = metrics[ev]
        print(f"blend {ev:9s} outlook {mm['bss_outlook']:+.3f} | gfs {mm['bss_gfs_same_rows']:+.3f} | gefs2 {mm['bss_gefs2_same_rows']:+.3f} "
              f"| blend {mm['bss_stacked']:+.3f} [{mm['ci90_stacked'][0]:+.3f}, {mm['ci90_stacked'][1]:+.3f}]", flush=True)
    json.dump(metrics, open(RES / "stack_blend_metrics.json", "w"), indent=1)
    np.savez_compressed(RES / "stack_blend.npz", years=np.array(both), **out)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
