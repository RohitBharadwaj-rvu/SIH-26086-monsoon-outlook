"""
Week-1 hybrid: combine the sub-seasonal outlook (climate drivers + climatology + recent rain) with the v3 deep
downscaling model's week-1 forecast, per gram panchayat, 2015-2023.

v3 week-1 rain per GP comes from the 3-seed averaged deterministic backbone's OUT-OF-FOLD predictions (fold models
that never saw the season; the final model for 2023), aggregated with the GP area weights. A logistic stacker per
event (dry_1, wet_1, heavy_1) on [logit(outlook p), log1p(v3 weekly total), v3 wettest day, v3 dry days] is validated
leave-one-season-out over the 9 seasons; issue dates without a v3 run (May) keep the outlook probability.

  python -m outlook.stack_v3        -> outlook/results/stack_week1.npz, outlook/results/stack_week1_metrics.json
  python -m outlook.stack_v3 final  -> outlook/models/stack_v3_<event>.joblib (operational stackers, all 9 seasons)
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

from outlook.model import NI, RES

REPO = Path(__file__).resolve().parents[1]
YEARS = list(range(2015, 2024))


def v3_week1():
    """-> rain [9, NI, G, 7] mm/day (NaN where no v3 run on that issue day)."""
    from sihv3.data import V3Data
    cells = json.load(open(REPO / "demo" / "data" / "serving" / "gp_cells.json", encoding="utf-8"))
    codes = sorted(cells)
    W = np.zeros((len(codes), 6400), np.float32)
    for i, c in enumerate(codes):
        for r, col, w in cells[c]["cells"]:
            W[i, r * 80 + col] = w
    d = V3Data(history_len=3, context=40)
    z = np.load(REPO / "ckpts" / "ds_oof_avg3" / "oof_avg3.npz")
    ydet, zdates = z["ydet"][:, :, 0], z["dates"].astype(str)        # read once (npz re-reads the whole array per access)
    out = np.full((len(YEARS), NI, len(codes), 7), np.nan, np.float32)
    disp = np.full((len(YEARS), NI, len(codes), 7), np.nan, np.float32)
    from sihv3.modes import apply_qm
    cal = np.load(REPO / "models" / "final" / "calibration.npz")
    qm = (cal["qm_pq"], cal["qm_oq"])
    for n, ds in enumerate(zdates):
        t = date.fromisoformat(ds)
        if t.year not in YEARS:
            continue
        i = (t - date(t.year, 5, 1)).days
        if 0 <= i < NI:
            x = ydet[n].astype(np.float32)[None, :, None]                   # [1,7,1,80,80] rain channel only
            full = np.zeros((1, 7, 6, 80, 80), np.float32); full[:, :, 0] = x[:, :, 0]
            rain = np.maximum(d.norm.inv(full, axis=2)[0, :, 0], 0)         # [7,80,80] mm/day
            out[YEARS.index(t.year), i] = (rain.reshape(7, 6400) @ W.T).T
            ph = np.zeros((1, 7, 6, 80, 80), np.float32); ph[0, :, 0] = rain
            disp[YEARS.index(t.year), i] = (apply_qm(ph, qm)[0, :, 0].reshape(7, 6400) @ W.T).T
    return out, disp


def main():
    v3, v3_disp = v3_week1()
    ok_v3 = np.isfinite(v3[..., 0])
    print(f"v3 week-1 forecasts on {ok_v3.any(-1).sum()} issue days x 9 seasons", flush=True)
    yrs_all = np.load(REPO / "outlook" / "data" / "gp_daily.npz")["years"]
    yi = [int(np.where(yrs_all == y)[0][0]) for y in YEARS]
    metrics, stacked = {}, {}
    for ev in ("dry_1", "wet_1", "heavy_1", "onset_1", "false3w"):
        z = np.load(RES / f"oof_{ev}.npz")
        p, c, y = (z[k].astype(np.float32)[yi] for k in ("p", "clim", "y"))
        tot, mx = np.log1p(np.nansum(v3, -1)), np.log1p(np.nanmax(v3, -1))
        dryd = (v3 < 2.5).sum(-1).astype(np.float32)
        lp = np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
        X = np.stack([lp, tot, mx, dryd], -1)
        m = ok_v3 & np.isfinite(y)
        ps = p.copy()
        for k in range(len(YEARS)):
            tr = m.copy(); tr[k] = False
            te = m.copy(); te[:k] = False; te[k + 1:] = False
            lr = LogisticRegression(C=1.0, max_iter=500).fit(X[tr], y[tr])
            ps[te] = lr.predict_proba(X[te])[:, 1]
        bs = lambda q: float(np.mean((q[m] - y[m]) ** 2))
        rng = np.random.default_rng(0)
        yr_of = np.broadcast_to(np.arange(len(YEARS))[:, None, None], m.shape)[m]
        groups = [np.where(yr_of == k)[0] for k in range(len(YEARS))]
        pv, cv, sv, yv = p[m], c[m], ps[m], y[m]
        boots = []
        for _ in range(400):
            sel = np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))])
            boots.append(1 - np.mean((sv[sel] - yv[sel]) ** 2) / np.mean((cv[sel] - yv[sel]) ** 2))
        metrics[ev] = {"bss_outlook": round(1 - bs(p) / bs(c), 4), "bss_stacked": round(1 - bs(ps) / bs(c), 4),
                       "ci90_stacked": [round(float(np.percentile(boots, 5)), 4), round(float(np.percentile(boots, 95)), 4)],
                       "n": int(m.sum()), "seasons": "2015-2023 (leave-one-season-out)"}
        stacked[ev] = ps.astype(np.float16)
        print(ev, metrics[ev], flush=True)
    np.savez_compressed(RES / "stack_week1.npz", years=np.array(YEARS), v3=np.nan_to_num(v3, nan=-1).astype(np.float16),
                        v3_display=np.nan_to_num(v3_disp, nan=-1).astype(np.float16), **stacked)
    json.dump(metrics, open(RES / "stack_week1_metrics.json", "w"), indent=1)


def fit_final():
    """Operational week-1 v3 stackers on all 9 seasons (same features and C as the validated LOSO ones), from stack_week1.npz."""
    import joblib
    from outlook.model import MOD
    st = np.load(RES / "stack_week1.npz")
    v3 = st["v3"].astype(np.float32); v3[v3 < 0] = np.nan
    ok_v3 = np.isfinite(v3[..., 0])
    yrs_all = np.load(REPO / "outlook" / "data" / "gp_daily.npz")["years"]
    yi = [int(np.where(yrs_all == y)[0][0]) for y in YEARS]
    for ev in ("dry_1", "wet_1", "heavy_1", "onset_1", "false3w"):
        z = np.load(RES / f"oof_{ev}.npz")
        p, y = (z[k].astype(np.float32)[yi] for k in ("p", "y"))
        X = v3_X(p, v3)
        m = ok_v3 & np.isfinite(y)
        joblib.dump({"lr": LogisticRegression(C=1.0, max_iter=500).fit(X[m], y[m])}, MOD / f"stack_v3_{ev}.joblib", compress=3)
        print("final v3 stacker", ev, int(m.sum()), "rows")


def v3_X(p, v3):
    """p [...] outlook probability, v3 [..., 7] mm/day -> [..., 4] (as in main)."""
    lp = np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
    return np.stack([lp, np.log1p(np.nansum(v3, -1)), np.log1p(np.nanmax(v3, -1)), (v3 < 2.5).sum(-1).astype(np.float32)], -1)


if __name__ == "__main__":
    import sys
    fit_final() if sys.argv[1:] == ["final"] else main()
