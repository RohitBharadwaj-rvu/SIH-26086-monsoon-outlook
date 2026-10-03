"""
Feasibility study for SIH PS 26086 (hyperlocal monsoon onset / break outlook, 1-4 weeks, panchayat scale).

How much week-1..4 signal is there for Mandya's 234 gram panchayats, from what we can actually get?
  * observed rain (CHIRPS 0.05 deg, area-weighted per GP) 2015-2023, Jun 1 - Oct 6, from the v3 dataset targets
  * climate indices at the issue date: MJO (NOAA PSL OMI PC1/PC2, daily), ENSO (CPC weekly Nino 3.4 anomaly),
    IOD (HadISST DMI, previous month: what is known at issue time)
  * persistence (the GP's observed rain over the 7 days before issue)
  * our v3 deterministic model's week-1 rain (out-of-fold for 2015-2022, final model for 2023)

Events per GP and forecast week w (days 7(w-1) .. 7w-1 after issue):
  dry week   all 7 days < 2.5 mm (IMD dry day)                     -> break / dry-spell signal
  heavy week at least one day >= 30 mm                             -> heavy downpour signal
  wet week   weekly total >= 1.5 x the GP's climatological weekly total for that calendar week

Skill = Brier skill score vs a leave-one-season-out (LOSO) day-of-season climatology, every model LOSO over the 9
seasons; 90 % CI from a season-block bootstrap (seasons are the independent units, GPs are not).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from sihv3.data import V3Data  # noqa: E402

IDX = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
EVENTS = tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ("dry", "heavy", "wet")
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def load_indices():
    omi = {}
    for line in open(IDX / "omi.txt"):
        p = line.split()
        if len(p) >= 6:
            omi[date(int(p[0]), int(p[1]), int(p[2]))] = (float(p[3]), float(p[4]))
    nino = []
    pat = re.compile(r"(\d{2})([A-Z]{3})(\d{4})\s+[\d.]+\s*(-?[\d.]+)\s+[\d.]+\s*(-?[\d.]+)\s+[\d.]+\s*(-?[\d.]+)")
    for line in open(IDX / "nino34w.txt"):
        m = pat.search(line)
        if m:
            nino.append((date(int(m.group(3)), MON[m.group(2)], int(m.group(1))), float(m.group(6))))
    dmi = {}
    for line in open(IDX / "dmi.txt"):
        p = line.split()
        if len(p) == 13 and p[0].isdigit():
            for k in range(12):
                v = float(p[k + 1])
                if v > -99:
                    dmi[(int(p[0]), k + 1)] = v
    return omi, sorted(nino), dmi


def main():
    omi, nino, dmi = load_indices()
    cells = json.load(open(REPO / "demo" / "data" / "serving" / "gp_cells.json", encoding="utf-8"))
    codes = sorted(cells)
    W = np.zeros((len(codes), 6400), np.float32)
    for i, c in enumerate(codes):
        for r, col, w in cells[c]["cells"]:
            W[i, r * 80 + col] = w
    d = V3Data(history_len=3, context=40)
    # observed daily GP rain: lead-0 target of every init + leads 1..6 of the last inits (to reach Oct 6)
    P = d.norm.inv(d.targ, axis=2)[:, :, 0]                          # [n,7,80,80] physical mm
    M = d.mask[:, :, 0]
    P = np.where(M, P, 0.0)
    gp = P.reshape(P.shape[0], 7, 6400) @ W.T                         # [n,7,G]
    dates = [date.fromisoformat(x) for x in d.dates]
    obs = {}
    for i, t in enumerate(dates):
        for l in range(7):
            obs.setdefault(t + timedelta(days=l), gp[i, l])
    years = sorted({t.year for t in dates})
    # v3 week-1 forecast (seed-0 OOF: fold models for 2015-22, final model for 2023)
    z = np.load(REPO / "ckpts" / "s10f-oof" / "out" / "oof" / "ydet.npz")
    yd = d.norm.inv(z["ydet"].astype(np.float32), axis=2)[:, :, 0]
    v3w1 = np.maximum(yd, 0).reshape(len(dates), 7, 6400) @ W.T       # [n,7,G]
    G = len(codes)

    rows = []  # one per (init, week): features shared across GPs + per-GP arrays
    for i, t in enumerate(dates):
        if t.month == 9 and t.day > 8:                                # need 4 full weeks of observations (to Oct 6)
            continue
        past = [obs.get(t - timedelta(days=k)) for k in range(1, 8)]
        if any(p is None for p in past):
            pers = None
        else:
            pers = np.sum(past, 0)
        o = omi.get(t - timedelta(days=1))
        n34 = [v for (dd, v) in nino if dd <= t - timedelta(days=4)][-1]
        pm = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
        for w in range(1, 5):
            days = [t + timedelta(days=7 * (w - 1) + k) for k in range(7)]
            if any(x not in obs for x in days):
                continue
            wk = np.stack([obs[x] for x in days])                     # [7,G]
            rows.append({"year": t.year, "doy": t.timetuple().tm_yday, "w": w, "pers": pers, "omi": o, "n34": n34,
                         "dmi": dmi.get(pm, np.nan), "dry": (wk < 2.5).all(0), "heavy": (wk >= 30).any(0), "tot": wk.sum(0),
                         "v3w1": v3w1[i].sum(0) if w == 1 else None})
    print(f"{len(rows)} (issue date, week) cases, {G} GPs, seasons {years}")

    out = {}
    rng = np.random.default_rng(0)
    for w in (1, 2, 3, 4):
        R = [r for r in rows if r["w"] == w and r["pers"] is not None and r["omi"] is not None]
        yr = np.array([r["year"] for r in R]); doy = np.array([r["doy"] for r in R])
        near = np.abs(doy[:, None] - doy[None, :]) <= 15                  # +-15-day calendar window
        TOT = np.stack([r["tot"] for r in R]); EV = {"dry": np.stack([r["dry"] for r in R]).astype(float),
                                                     "heavy": np.stack([r["heavy"] for r in R]).astype(float)}
        base = {"pers": np.log1p(np.stack([r["pers"] for r in R])),
                "idx": np.array([[r["omi"][0], r["omi"][1], r["n34"], r["dmi"]] for r in R]),
                "v3": np.log1p(np.stack([r["v3w1"] for r in R])) if w == 1 else None}
        for ev in EVENTS:
            ys, cs, preds, yrs = [], [], {k: [] for k in ("pers", "idx", "mjo", "enso_iod", "all", "v3")}, []
            for vy in years:
                trm = yr != vy
                A = near & trm[None, :]                                    # neighbours from training seasons only
                A = A / np.maximum(A.sum(1, keepdims=True), 1)
                if ev == "wet":
                    thr = 1.5 * (A @ TOT)                                  # GP's climatological weekly total x 1.5
                    Y = (TOT >= thr).astype(float)
                else:
                    Y = EV[ev]
                C = np.clip(A @ Y, 0.005, 0.995)                           # LOSO climatological probability [cases, G]
                lc = np.log(C / (1 - C))
                te, tr = ~trm, trm
                if not te.any():
                    continue
                def X(kind, m):
                    f = [lc[m].ravel()]
                    if kind in ("pers", "all", "v3"):
                        f.append(base["pers"][m].ravel())
                    if kind in ("idx", "all", "v3"):
                        f += [np.repeat(base["idx"][m][:, k], G) for k in range(4)]
                    if kind == "mjo":
                        f += [np.repeat(base["idx"][m][:, k], G) for k in (0, 1)]
                    if kind == "enso_iod":
                        f += [np.repeat(base["idx"][m][:, k], G) for k in (2, 3)]
                    if kind == "v3":
                        f.append(base["v3"][m].ravel())
                    return np.stack(f, 1)
                ys.append(Y[te].ravel()); cs.append(C[te].ravel()); yrs.append(np.full(te.sum() * G, vy))
                for kind in ("pers", "idx", "mjo", "enso_iod", "all") + (("v3",) if w == 1 else ()):
                    Xtr, Xte = X(kind, tr), X(kind, te)
                    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
                    mdl = LogisticRegression(C=0.5, max_iter=500).fit((Xtr - mu) / sd, Y[tr].ravel())
                    preds[kind].append(mdl.predict_proba((Xte - mu) / sd)[:, 1])
            y, c, yv = np.concatenate(ys), np.concatenate(cs), np.concatenate(yrs)
            bs_c = np.mean((c - y) ** 2)
            row = {"base_rate": round(float(y.mean()), 3), "n_gp_cases": int(len(y))}
            uy = np.unique(yv)
            groups = [np.where(yv == q)[0] for q in uy]
            for kind, pl in preds.items():
                if not pl:
                    continue
                p = np.concatenate(pl)
                bss = 1 - np.mean((p - y) ** 2) / bs_c
                boots = []
                for _ in range(400):
                    idx = np.concatenate([groups[k] for k in rng.integers(0, len(uy), len(uy))])
                    boots.append(1 - np.mean((p[idx] - y[idx]) ** 2) / np.mean((c[idx] - y[idx]) ** 2))
                row[kind] = [round(float(bss), 3), round(float(np.percentile(boots, 5)), 3), round(float(np.percentile(boots, 95)), 3)]
            out.setdefault(ev, {})[w] = row
            print(f"{ev:5s} week {w}: {row}", flush=True)
    json.dump({e: {str(k): v for k, v in d_.items()} for e, d_ in out.items()},
              open(REPO / "results" / ("feasibility_ps26086.json" if len(sys.argv) <= 2 else "feasibility_ps26086_split.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
