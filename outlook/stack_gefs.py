"""
Weeks 1-4 hybrid with the NOAA GEFSv12 11-member ensemble (35-day reforecasts, 2000-2019), per gram panchayat.

Every issue day uses the latest Wednesday 00Z run on or before it (0-6 days old; the operational GEFS runs to 35 days
every day, so validation with stale runs is conservative). From the 11 members, bilinear at each panchayat, for the 28
days from the issue day: per week k = 1..4, the ensemble-mean total, the fraction of members with a dry week, with a
heavy day (>= 30 mm) and with a 2-day >= 20 mm wet start; the fraction with a >= 7-day dry run inside days 1-21; and
the run's age. A logistic stacker per target on [logit(outlook p)] + these features (standardised, strong L2) is
validated leave-one-season-out over the 20 seasons, on top of outlook probabilities that are themselves out-of-fold.

  python -m outlook.stack_gefs ckpts/gefs   -> outlook/results/stack_gefs.npz, stack_gefs_metrics.json,
                                               outlook/models/stack_gefs_<target>.joblib
"""
from __future__ import annotations

import glob
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from outlook.model import DATA, DRY, HEAVY, MOD, NI, RES

YEARS = list(range(2000, 2020))              # reforecasts: training + leave-one-season-out validation
OPS_YEARS = [2021, 2022, 2023]               # operational GEFS (35-day since GEFSv12): independent test of the final stackers
ALL = YEARS + [2020] + OPS_YEARS             # 2020: GEFSv11 ran only 16 days -> no features (outlook kept)
TARGETS = [f"{e}_{k}" for e in ("dry", "wet", "heavy", "onset") for k in range(1, 5)] + ["break3w", "false3w"]
STACK_C = 0.005
FEATURE_NAMES = ["logit_p"] + [f"{n}_w{k}" for k in range(1, 5) for n in ("tot", "fdry", "fheavy", "fws")] + ["fbreak", "age"]


def bil(P, lat, lon, glat, glon):
    """P [..., nlat, nlon] on a regular grid (lat descending) -> [..., G] bilinear at the panchayat centroids."""
    dl, dn = lat[0] - lat[1], lon[1] - lon[0]
    fi = (lat[0] - glat) / dl; fj = (glon - lon[0]) / dn
    i0, j0 = np.floor(fi).astype(int), np.floor(fj).astype(int)
    wi, wj = fi - i0, fj - j0
    return (P[..., i0, j0] * (1 - wi) * (1 - wj) + P[..., i0 + 1, j0] * wi * (1 - wj)
            + P[..., i0, j0 + 1] * (1 - wi) * wj + P[..., i0 + 1, j0 + 1] * wi * wj)


def ens_feats(E, age):
    """E [..., M, 28] mm/day for the 28 days from the issue day (members on axis -2) -> [..., 18] (no logit_p)."""
    f = []
    for k in range(4):
        w = E[..., 7 * k:7 * k + 7]
        two = w[..., :-1] + w[..., 1:]
        f += [np.log1p(w.sum(-1).mean(-1)), (w < DRY).all(-1).mean(-1), (w >= HEAVY).any(-1).mean(-1),
              ((w[..., :-1] >= 1.0) & (two >= 20.0)).any(-1).mean(-1)]
    run = np.zeros(E.shape[:-1], np.int16); hit = np.zeros(E.shape[:-1], bool)
    for d in range(21):
        run = np.where(E[..., d] < DRY, run + 1, 0); hit |= run >= 7
    f += [hit.mean(-1), np.broadcast_to(np.float32(age), f[0].shape)]
    return np.stack(f, -1).astype(np.float32)


def gefs_gp(gefs_dir: Path, glat, glon):
    """-> {year: (init dates, R [n, M, G, 35] mm/day)}"""
    out = {}
    for y in ALL:
        fs = glob.glob(str(gefs_dir / "**" / f"gefs35_{y}.npz"), recursive=True)
        if not fs:
            print(f"GEFS {y} missing", flush=True)
            continue
        z = np.load(fs[0])
        a = bil(z["pr10"].astype(np.float32), z["lat25"], z["lon25"], glat, glon)          # [n, M, 10, G]
        b = bil(z["pr35"].astype(np.float32), z["lat50"], z["lon50"], glat, glon)          # [n, M, 25, G]
        R = np.maximum(np.concatenate([a, b], 2), 0).transpose(0, 1, 3, 2)                 # [n, M, G, 35]
        out[y] = ([date.fromisoformat(s) for s in z["inits"].astype(str)], R)
    return out


def issue_feats(runs, y, G):
    """-> X [NI, G, 18] (NaN where no run within 6 days)."""
    X = np.full((NI, G, 18), np.nan, np.float32)
    if y not in runs:
        return X
    inits, R = runs[y]
    for i in range(NI):
        t = date(y, 5, 1) + timedelta(days=i)
        c = [n for n, d in enumerate(inits) if 0 <= (t - d).days <= 6]
        if not c:
            continue
        n = c[-1]; age = (t - inits[n]).days
        X[i] = ens_feats(R[n][..., age:age + 28].transpose(1, 0, 2), age)                  # [G, M, 28] -> [G, 18]
    return X


def logit(p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return np.log(p / (1 - p))


def main(gefs_dir: Path):
    gd = np.load(DATA / "gp_daily.npz")
    glat, glon = gd["lat"].astype(np.float64), gd["lon"].astype(np.float64)
    G = len(glat)
    t0 = time.time()
    runs = gefs_gp(gefs_dir, glat, glon)
    F = np.stack([issue_feats(runs, y, G) for y in ALL])                                    # [Y, NI, G, 18]
    okg = np.isfinite(F[..., 0])
    print(f"GEFS features on {okg.mean():.0%} of issue days x {len(runs)} seasons | {time.time() - t0:.0f}s", flush=True)
    yrs_all = list(gd["years"]); yi = [yrs_all.index(y) for y in ALL]
    NT = len(YEARS); ops = np.array([y in OPS_YEARS for y in ALL])
    MOD.mkdir(parents=True, exist_ok=True)
    gsel = np.arange(G) % 2 == 0                                                            # fit on every 2nd GP (near-duplicates)
    metrics, stacked = {}, {}
    for ev in TARGETS:
        z = np.load(RES / f"oof_{ev}.npz")
        p, c, yv = (z[k].astype(np.float32)[yi] for k in ("p", "clim", "y"))
        X = np.concatenate([logit(p)[..., None], F], -1)
        m = okg & np.isfinite(yv) & np.isfinite(p)
        m_ops = m & ops[:, None, None]
        m = m & (np.arange(len(ALL)) < NT)[:, None, None]                                  # validation rows: reforecast seasons
        mf = m & gsel[None, None, :]
        ps = p.copy()
        for k in range(NT):
            tr = mf.copy(); tr[k] = False
            te = np.zeros_like(m); te[k] = m[k]
            if not te.any() or not tr.any():
                continue
            Xtr = X[tr]; mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
            lr = LogisticRegression(C=STACK_C, max_iter=1000).fit((Xtr - mu) / sd, yv[tr])
            ps[te] = lr.predict_proba((X[te] - mu) / sd)[:, 1]
        used = [YEARS[k] for k in range(NT) if m[k].any()]
        bs = lambda q: float(np.mean((q[m] - yv[m]) ** 2))
        rng = np.random.default_rng(0)
        yr_of = np.broadcast_to(np.arange(len(ALL))[:, None, None], m.shape)[m]
        groups = [g_ for g_ in (np.where(yr_of == k)[0] for k in range(NT)) if len(g_)]
        sv, cv, yy = ps[m], c[m], yv[m]
        boots = [1 - np.mean((sv[s_] - yy[s_]) ** 2) / np.mean((cv[s_] - yy[s_]) ** 2)
                 for s_ in (np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))]) for _ in range(400))]
        metrics[ev] = {"bss_outlook": round(1 - bs(p) / bs(c), 4), "bss_stacked": round(1 - bs(ps) / bs(c), 4),
                       "ci90_stacked": [round(float(np.percentile(boots, 5)), 4), round(float(np.percentile(boots, 95)), 4)],
                       "n": int(m.sum()), "seasons": f"{len(used)} seasons {used[0]}-{used[-1]} (leave-one-season-out)",
                       "years": used, "inputs": "outlook + GEFS 11-member days 1-28"}
        stacked[ev] = ps.astype(np.float16)
        Xa = X[mf]; mu, sd = Xa.mean(0), Xa.std(0) + 1e-6                                   # operational stacker: all seasons
        lr = LogisticRegression(C=STACK_C, max_iter=1000).fit((Xa - mu) / sd, yv[mf])
        joblib.dump({"lr": lr, "mu": mu, "sd": sd, "C": STACK_C, "years": used, "features": FEATURE_NAMES},
                    MOD / f"stack_gefs_{ev}.joblib", compress=3)
        if m_ops.any():                                                                     # independent operational test
            ps[m_ops] = lr.predict_proba((X[m_ops] - mu) / sd)[:, 1]
            q, cq, yq, po = ps[m_ops], c[m_ops], yv[m_ops], p[m_ops]
            bsq = lambda a: float(np.mean((a - yq) ** 2))
            metrics[ev]["ops_test"] = {"years": [y for y in OPS_YEARS if m_ops[ALL.index(y)].any()],
                                       "bss_outlook": round(1 - bsq(po) / bsq(cq), 4), "bss_stacked": round(1 - bsq(q) / bsq(cq), 4),
                                       "n": int(m_ops.sum())}
        top = np.argsort(-np.abs(lr.coef_[0]))[:4]
        print(f"{ev:9s} outlook {metrics[ev]['bss_outlook']:+.3f} -> hybrid {metrics[ev]['bss_stacked']:+.3f} "
              f"[{metrics[ev]['ci90_stacked'][0]:+.3f}, {metrics[ev]['ci90_stacked'][1]:+.3f}]"
              + (f" | ops {metrics[ev]['ops_test']['bss_outlook']:+.3f}->{metrics[ev]['ops_test']['bss_stacked']:+.3f}" if "ops_test" in metrics[ev] else "")
              + " | top "
              + ", ".join(f"{FEATURE_NAMES[j]} {lr.coef_[0][j]:+.2f}" for j in top) + f" | {time.time() - t0:.0f}s", flush=True)
        json.dump(metrics, open(RES / "stack_gefs_metrics.json", "w"), indent=1)
    np.savez_compressed(RES / "stack_gefs.npz", years=np.array(ALL), **stacked)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
