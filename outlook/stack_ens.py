"""
Week-1 hybrid with the v3 diffusion ENSEMBLE (16 members, out-of-fold), per gram panchayat, 2015-2023.

Every member is out-of-sample for its season: the backbone forecast is out-of-fold and the residual denoiser of each
season 2015-2022 was trained without that season (kaggle runs ens-*); 2023 uses the shipped denoiser (trained 2015-2022).
Members are averaged over each panchayat (area weights). Event-matched member fractions for week 1 (days 1-7 from the
issue day): heavy day (>= 30 mm), dry week (all days < 2.5 mm), wet week (>= 1.5 x the panchayat normal), plus the
ensemble-mean weekly total / wettest day. Offset logistic stacker (outlook logit fixed, as in stack_gefs2), LOSO.

  python -m outlook.stack_ens ckpts/ens   -> outlook/results/stack_ens.npz, stack_ens_metrics.json, outlook/models/stack_ens_*.joblib
"""
from __future__ import annotations

import glob
import json
import sys
import time
from datetime import date
from pathlib import Path

import joblib
import numpy as np

from outlook.model import DATA, DRY, HEAVY, MOD, NI, RES
from outlook.stack_gefs import logit
from outlook.stack_gefs2 import fit_offset, predict_offset, weekly_normal

REPO = Path(__file__).resolve().parents[1]
YEARS = list(range(2015, 2024))
FEATS = {"heavy_1": ["fheavy", "mx"], "dry_1": ["tot", "fdry"], "wet_1": ["tot", "fwet"]}


def gp_weights():
    cells = json.load(open(REPO / "demo" / "data" / "serving" / "gp_cells.json", encoding="utf-8"))
    codes = sorted(cells)
    W = np.zeros((len(codes), 6400), np.float32)
    for i, c in enumerate(codes):
        for r, col, w in cells[c]["cells"]:
            W[i, r * 80 + col] = w
    return codes, W


def member_gp(ens_dir: Path, W):
    """-> {year: [NI, G, K, 7] GP-mean member rain (NaN where no run)}"""
    out = {}
    for y in YEARS:
        fs = glob.glob(str(ens_dir / "**" / f"ens_{y}.npz"), recursive=True)
        if not fs:
            print(f"ensemble {y} missing", flush=True)
            continue
        z = np.load(fs[0])
        R = z["rain"]                                                      # [n, K, 7, 80, 80] float16
        A = np.full((NI, W.shape[0], R.shape[1], 7), np.nan, np.float32)
        for n, ds in enumerate(z["dates"].astype(str)):
            i = (date.fromisoformat(ds) - date(y, 5, 1)).days
            if 0 <= i < NI:
                A[i] = (R[n].astype(np.float32).reshape(R.shape[1], 7, 6400) @ W.T).transpose(2, 0, 1)
        out[y] = A
        print(f"ensemble {y}: {len(z['dates'])} dates x {R.shape[1]} members", flush=True)
    return out


def feats(A, normal1):
    """A [NI, G, K, 7], normal1 [NI, G] week-1 normal -> dict [NI, G]"""
    S = A.sum(-1)
    run = np.isfinite(A[..., 0, 0])                                      # [NI, G] issue days with an ensemble
    with np.errstate(invalid="ignore"):
        f = {"tot": np.log1p(S.mean(-1)), "mx": np.log1p(A.max(-1).mean(-1)),
             "fheavy": (A >= HEAVY).any(-1).mean(-1), "fdry": (A < DRY).all(-1).mean(-1),
             "fwet": (S >= 1.5 * normal1[..., None]).mean(-1)}
    return {k: np.where(run, v, np.nan).astype(np.float32) for k, v in f.items()}


def main(ens_dir: Path):
    t0 = time.time()
    gd = np.load(DATA / "gp_daily.npz")
    r = gd["rain"].astype(np.float32); yrs_all = [int(y) for y in gd["years"]]
    codes, W = gp_weights()
    assert codes == [str(c) for c in gd["codes"]]
    ens = member_gp(ens_dir, W)
    yi = [yrs_all.index(y) for y in YEARS]
    gsel = np.arange(W.shape[0]) % 2 == 0
    rng = np.random.default_rng(0)
    metrics, stacked = {}, {}
    for ev, names in FEATS.items():
        z = np.load(RES / f"oof_{ev}.npz")
        p, c, yv = (z[k].astype(np.float32)[yi] for k in ("p", "clim", "y"))
        # features per season; the wet-week normal excludes the season itself
        X = np.full(p.shape + (len(names),), np.nan, np.float32)
        for a, y in enumerate(YEARS):
            if y in ens:
                f = feats(ens[y], weekly_normal(r, yrs_all, [y])[..., 0])
                X[a] = np.stack([f[n] for n in names], -1)
        off = logit(p)
        m = np.isfinite(X[..., 0]) & np.isfinite(yv) & np.isfinite(p)
        ps = p.copy()
        for a, y in enumerate(YEARS):
            tr = m & gsel[None, None, :]; tr[a] = False
            te = np.zeros_like(m); te[a] = m[a]
            if not te.any() or not tr.any():
                continue
            mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
            w = fit_offset((X[tr] - mu) / sd, off[tr], yv[tr])
            ps[te] = predict_offset(w, (X[te] - mu) / sd, off[te])
        used = [y for a, y in enumerate(YEARS) if m[a].any()]
        bs = lambda q: float(np.mean((q[m] - yv[m]) ** 2))
        yr_of = np.broadcast_to(np.arange(len(YEARS))[:, None, None], m.shape)[m]
        groups = [g_ for g_ in (np.where(yr_of == a)[0] for a in range(len(YEARS))) if len(g_)]
        sv, cv, yy = ps[m], c[m], yv[m]
        boots = [1 - np.mean((sv[s_] - yy[s_]) ** 2) / np.mean((cv[s_] - yy[s_]) ** 2)
                 for s_ in (np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))]) for _ in range(400))]
        metrics[ev] = {"bss_outlook": round(1 - bs(p) / bs(c), 4), "bss_stacked": round(1 - bs(ps) / bs(c), 4),
                       "ci90_stacked": [round(float(np.percentile(boots, 5)), 4), round(float(np.percentile(boots, 95)), 4)],
                       "n": int(m.sum()), "seasons": f"{len(used)} seasons {used[0]}-{used[-1]} (leave-one-season-out)",
                       "years": used, "inputs": "outlook + v3 16-member diffusion ensemble (out-of-fold)", "features": names}
        tr = m & gsel[None, None, :]
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
        w = fit_offset((X[tr] - mu) / sd, off[tr], yv[tr])
        joblib.dump({"w": w, "mu": mu, "sd": sd, "features": names}, MOD / f"stack_ens_{ev}.joblib", compress=3)
        stacked[ev] = ps.astype(np.float16)
        mm = metrics[ev]
        print(f"{ev:8s} outlook {mm['bss_outlook']:+.3f} -> v3-ens {mm['bss_stacked']:+.3f} [{mm['ci90_stacked'][0]:+.3f}, "
              f"{mm['ci90_stacked'][1]:+.3f}] n {mm['n']} | coef " + " ".join(f"{n} {v:+.2f}" for n, v in zip(names, w[1:]))
              + f" | {time.time() - t0:.0f}s", flush=True)
    json.dump(metrics, open(RES / "stack_ens_metrics.json", "w"), indent=1)
    np.savez_compressed(RES / "stack_ens.npz", years=np.array(YEARS), **stacked)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
