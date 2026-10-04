"""
Reliability of every shipped forecast, on the same validation rows as its skill score (out-of-sample only).

  outlook  out-of-fold probabilities, 43 seasons (season-blocked CV)
  v3/gfs/v3ens  leave-one-season-out hybrid probabilities on the issue days where the hybrid ran
  gefs2    leave-one-season-out over the 2000-2019 reforecasts
  blend    mean of the gfs and gefs2 hybrids where both ran (2015-19, 2021-23)
Per target: 10 equal-width probability bins [mean forecast, observed frequency, rows], the expected calibration error
(row-weighted mean |forecast - observed|) and a season-bootstrap 90 % band of the observed frequency per bin.

  python -m outlook.reliability   -> outlook/results/reliability_shipped.json
"""
from __future__ import annotations

import json

import numpy as np

from outlook.model import RES

FILES = {"v3": "stack_week1.npz", "gfs": "stack.npz", "gefs2": "stack_gefs2.npz", "v3ens": "stack_ens.npz"}
METRICS = {"v3": "stack_week1_metrics.json", "gfs": "stack_metrics.json", "gefs2": "stack_gefs2_metrics.json",
           "v3ens": "stack_ens_metrics.json", "blend": "stack_blend_metrics.json"}


def rows(t, src, years_all):
    """-> forecast q, outcome y, season index s (1-D, validation rows only)."""
    z = np.load(RES / f"oof_{t}.npz")
    P, Y = z["p"].astype(np.float32), z["y"].astype(np.float32)
    if src == "outlook":
        m = np.isfinite(Y) & np.isfinite(P)
        s = np.broadcast_to(np.arange(len(years_all))[:, None, None], m.shape)[m]
        return P[m], Y[m], s

    def hybrid(name, yrs_keep):
        f = np.load(RES / FILES[name]); ys = [int(y) for y in f["years"]]
        idx = [years_all.index(y) for y in ys]
        q = f[t].astype(np.float32); p = P[idx]; y = Y[idx]
        keep = np.array([y_ in yrs_keep for y_ in ys])[:, None, None]
        return ys, q, p, y, (q != p) & np.isfinite(y) & keep

    if src == "blend":
        yrs = json.load(open(RES / METRICS["blend"]))[t]["years"]
        ga, qa, pa, ya, ma = hybrid("gfs", yrs)
        gb, qb, pb, yb, mb = hybrid("gefs2", yrs)
        ia = [ga.index(y) for y in yrs]; ib = [gb.index(y) for y in yrs]
        q = 0.5 * (qa[ia] + qb[ib]); m = ma[ia] & mb[ib]; y = ya[ia]
        s = np.broadcast_to(np.arange(len(yrs))[:, None, None], m.shape)[m]
        return q[m], y[m], s
    yrs = json.load(open(RES / METRICS[src]))[t].get("years", list(range(2015, 2024)))
    ys, q, p, y, m = hybrid(src, yrs)
    s = np.broadcast_to(np.arange(len(ys))[:, None, None], m.shape)[m]
    return q[m], y[m], s


def main():
    sel = json.load(open(RES / "final_selection.json"))
    years_all = [int(y) for y in np.load(RES.parent / "data" / "gp_daily.npz")["years"]]
    rng = np.random.default_rng(0)
    out = {}
    for t, f in sel.items():
        q, y, s = rows(t, f["source"], years_all)
        b = np.clip((q * 10).astype(int), 0, 9)
        bins = []
        seasons = np.unique(s)
        for k in range(10):
            sel_k = b == k
            if sel_k.sum() < 100:
                continue
            # season bootstrap of the observed frequency in this bin
            per = [(y[sel_k & (s == a)].sum(), (sel_k & (s == a)).sum()) for a in seasons]
            per = np.array(per, np.float64)
            bs = []
            for _ in range(300):
                d = per[rng.integers(0, len(per), len(per))]
                if d[:, 1].sum():
                    bs.append(d[:, 0].sum() / d[:, 1].sum())
            bins.append([round(float(q[sel_k].mean()), 4), round(float(y[sel_k].mean()), 4), int(sel_k.sum()),
                         round(float(np.percentile(bs, 5)), 4), round(float(np.percentile(bs, 95)), 4)])
        n = sum(x[2] for x in bins)
        ece = sum(x[2] * abs(x[0] - x[1]) for x in bins) / max(n, 1)
        out[t] = {"source": f["source"], "bins": bins, "ece": round(float(ece), 4), "n": int(len(q)),
                  "base_rate": round(float(y.mean()), 4), "seasons": f["seasons"], "bss": f["bss"], "ci90": f["ci90"]}
        print(f"{t:9s} {f['source']:7s} rows {len(q):7d} | ECE {ece:.3f} | bins " +
              " ".join(f"{x[0]:.2f}->{x[1]:.2f}" for x in bins), flush=True)
    json.dump(out, open(RES / "reliability_shipped.json", "w"), indent=1)


if __name__ == "__main__":
    main()
