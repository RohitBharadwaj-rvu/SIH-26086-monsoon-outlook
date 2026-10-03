"""
Weeks 1-2 hybrid: combine the sub-seasonal outlook with numerical forecasts, per gram panchayat, 2015-2023.

  * GFS 0.25 deg daily rain for forecast days 1-16 (kaggle/gfs16), bilinear to each panchayat: weekly totals, wettest
    2-day total and dry days in week 1 (days 1-7) and week 2 (days 8-14), and the day 1-16 total
  * the v3 deep downscaling model's week-1 forecast (out-of-fold, 3-seed average) where a v3 run exists (Jun-Sep)
  * logit of the outlook probability for the target (climatology, recent rain, MJO/BSISO, ENSO, IOD)
A logistic stacker per target is validated leave-one-season-out over the 9 seasons (each season predicted by a stacker
that never saw it, on top of outlook models that never saw it).

  python -m outlook.stack_gfs <gfs16_dir> [C]   -> outlook/results/stack.npz, stack_metrics.json, outlook/models/stack_gfs_*.joblib
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

import joblib

from outlook.model import MOD, NI, RES

REPO = Path(__file__).resolve().parents[1]
YEARS = list(range(2015, 2024))
STACK_C = 0.005                  # strong L2: 12 features, few seasons (0.05 overfit in the 7-season preview)
TARGETS = ["dry_1", "wet_1", "heavy_1", "onset_1", "false3w", "break3w", "dry_2", "wet_2", "heavy_2", "onset_2"]


def gfs_gp(gfs_dir: Path, gps):
    """-> [9, NI, G, 16] mm/day (NaN where the init is missing)."""
    out = np.full((len(YEARS), NI, len(gps), 16), np.nan, np.float32)
    glat = np.array([g["lat"] for g in gps]); glon = np.array([g["lon"] for g in gps])
    for a, y in enumerate(YEARS):
        if not (gfs_dir / f"gfs16_{y}.npz").exists():
            print(f"GFS16 {y} missing: treated as no GFS run", flush=True)
            continue
        z = np.load(gfs_dir / f"gfs16_{y}.npz")
        lat, lon, pr = z["lat"], z["lon"], z["pr"]                  # lat descending
        for n, ds in enumerate(z["dates"].astype(str)):
            i = (date.fromisoformat(ds) - date(y, 5, 1)).days
            if 0 <= i < NI:
                out[a, i] = to_gp(pr[n], lat, lon, glat, glon)
    return out


def to_gp(P, lat, lon, glat, glon):
    """P [16, nlat, nlon] on the 0.25 deg box (lat descending) -> [G, 16], bilinear at each panchayat centroid."""
    fi = (lat[0] - glat) / 0.25; fj = (glon - lon[0]) / 0.25
    i0, j0 = np.floor(fi).astype(int), np.floor(fj).astype(int)
    wi, wj = fi - i0, fj - j0
    v = (P[:, i0, j0] * (1 - wi) * (1 - wj) + P[:, i0 + 1, j0] * wi * (1 - wj)
         + P[:, i0, j0 + 1] * (1 - wi) * wj + P[:, i0 + 1, j0 + 1] * wi * wj)
    return v.T


def week_feats(R, lo, hi):
    w = R[..., lo:hi]
    two = w[..., :-1] + w[..., 1:]
    return [np.log1p(np.nansum(w, -1)), np.log1p(np.nanmax(two, -1)), (w < 2.5).sum(-1).astype(np.float32)]


def logit(p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return np.log(p / (1 - p))


def stack_X(p, G, v3):
    """p [...] outlook probability, G [..., 16] GFS mm/day, v3 [..., 7] mm/day (NaN where no v3 run) -> [..., 12]."""
    okv = np.isfinite(v3[..., 0])
    gf = week_feats(G, 0, 7) + week_feats(G, 7, 14) + [np.log1p(np.nansum(G, -1))]
    vf = [np.nan_to_num(f, nan=0.0) for f in week_feats(v3, 0, 7)] + [okv.astype(np.float32)]
    return np.stack([logit(p)] + gf + vf, -1)


def main(gfs_dir: Path):
    cells = json.load(open(REPO / "demo" / "data" / "serving" / "gp_cells.json", encoding="utf-8"))
    gps = [{"code": c, "lat": cells[c]["lat"], "lon": cells[c]["lon"]} for c in sorted(cells)]
    G = gfs_gp(gfs_dir, gps)
    okg = np.isfinite(G[..., 0])
    st = np.load(RES / "stack_week1.npz")                              # v3 week-1 (raw, for features)
    v3 = st["v3"].astype(np.float32); v3[v3 < 0] = np.nan
    okv = np.isfinite(v3[..., 0])
    print(f"GFS days 1-16 on {okg.mean():.0%} of issue days | v3 week 1 on {okv.mean():.0%}", flush=True)
    yrs_all = list(np.load(REPO / "outlook" / "data" / "gp_daily.npz")["years"])
    yi = [yrs_all.index(y) for y in YEARS]
    MOD.mkdir(parents=True, exist_ok=True)
    metrics, stacked = {}, {}
    for ev in TARGETS:
        z = np.load(RES / f"oof_{ev}.npz")
        p, c, y = (z[k].astype(np.float32)[yi] for k in ("p", "clim", "y"))
        X = stack_X(p, G, v3)
        m = okg & np.isfinite(y)
        ps = p.copy()
        for k in range(len(YEARS)):
            tr = m.copy(); tr[k] = False
            te = np.zeros_like(m); te[k] = m[k]
            if not te.any():
                continue
            Xtr = X[tr]; mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
            lr = LogisticRegression(C=STACK_C, max_iter=1000).fit((Xtr - mu) / sd, y[tr])
            ps[te] = lr.predict_proba((X[te] - mu) / sd)[:, 1]
        used = [YEARS[k] for k in range(len(YEARS)) if m[k].any()]
        bs = lambda q: float(np.mean((q[m] - y[m]) ** 2))
        rng = np.random.default_rng(0)
        yr_of = np.broadcast_to(np.arange(len(YEARS))[:, None, None], m.shape)[m]
        groups = [np.where(yr_of == k)[0] for k in range(len(YEARS))]
        sv, cv, yv, pv = ps[m], c[m], y[m], p[m]
        boots = [1 - np.mean((sv[s_] - yv[s_]) ** 2) / np.mean((cv[s_] - yv[s_]) ** 2)
                 for s_ in (np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))]) for _ in range(400))]
        metrics[ev] = {"bss_outlook": round(1 - bs(p) / bs(c), 4), "bss_stacked": round(1 - bs(ps) / bs(c), 4),
                       "ci90_stacked": [round(float(np.percentile(boots, 5)), 4), round(float(np.percentile(boots, 95)), 4)],
                       "n": int(m.sum()), "seasons": f"{len(used)} seasons {used[0]}-{used[-1]} (leave-one-season-out)", "years": used, "inputs": "outlook + GFS days 1-16 + v3 week 1"}
        stacked[ev] = ps.astype(np.float16)
        Xa = X[m]; mu, sd = Xa.mean(0), Xa.std(0) + 1e-6                 # operational stacker: all seasons
        joblib.dump({"lr": LogisticRegression(C=STACK_C, max_iter=1000).fit((Xa - mu) / sd, y[m]), "mu": mu, "sd": sd,
                     "C": STACK_C, "years": used}, MOD / f"stack_gfs_{ev}.joblib", compress=3)
        print(f"{ev:9s} outlook {metrics[ev]['bss_outlook']:+.3f} -> hybrid {metrics[ev]['bss_stacked']:+.3f} "
              f"[{metrics[ev]['ci90_stacked'][0]:+.3f}, {metrics[ev]['ci90_stacked'][1]:+.3f}]", flush=True)
    np.savez_compressed(RES / "stack.npz", years=np.array(YEARS), gfs=np.nan_to_num(G, nan=-1).astype(np.float16), **stacked)
    json.dump(metrics, open(RES / "stack_metrics.json", "w"), indent=1)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        STACK_C = float(sys.argv[2])
    main(Path(sys.argv[1]))
