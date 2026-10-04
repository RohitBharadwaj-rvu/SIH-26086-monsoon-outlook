"""
Issue an operational PS 26086 outlook for one date: 18 probabilities per gram panchayat + ranked advisories.

Uses only information available on the issue day: observed GP rain up to the day before, the latest published indices
(real-time MJO/BSISO the day before, weekly Nino 3.4 >= 4 days old, previous month's DMI), the GFS 00Z run of the issue
day (days 1-16) and the v3 week-1 forecast when supplied. Models: the final outlook models (all 43 seasons) and, per
target, the hybrid chosen by outlook.select (operational stackers fitted on all validation seasons).

  python -m outlook.issue 2023-06-12 [--idx DIR] [--rain rain.npz] [--gfs gfs.npz] [--v3 v3.npz] [--out out.json]

  --idx   directory with romi.txt, bsiso_rt.txt, nino34w.txt, dmi.txt (default outlook/data/idx)
  --rain  npz {rain [days since 1 May, G] mm/day, codes [G]}   default: CHIRPS replay (seasons <= 2023), cut at the issue day
  --gfs   npz {lat, lon, pr [16, nlat, nlon] mm/day}           default: the replay archive ckpts/gfs16/all for that init
  --v3    npz {rain [G, 7] mm/day, codes [G]}                   default: the out-of-fold v3 replay (Jun-Sep 2015-2023)
  --gefs  npz in the kaggle/gefs format (inits, members, pr10, pr35, grids); the latest run <= 6 days old is used
                                                                 default: ckpts/gefs (reforecast 2000-2019, operational 2021-2023)
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np

from outlook.advisory import advise
from outlook.build import index_at, index_series
from outlook.model import DATA, MOD, NI, RES, features, load_model, observed_wet_starts, onset_and_false
from outlook.stack_gefs import bil, ens_feats, logit
from outlook.stack_gefs2 import apply_qm, member_feats, predict_offset
from outlook.stack_gfs import stack_X, to_gp
from outlook.stack_v3 import v3_X

REPO = Path(__file__).resolve().parents[1]
EVENTS = [f"{e}_{k}" for e in ("dry", "wet", "heavy", "onset") for k in range(1, 5)] + ["break3w", "false3w"]
CONFIRM = 22                     # onset on day d is confirmed (no 7-day dry spell in d+2..d+21) from issue day d+22
D = 184


def load_rain(t: date, path, codes):
    i = (t - date(t.year, 5, 1)).days
    r = np.zeros((1, D, len(codes)), np.float32)
    if path:
        z = np.load(path)
        src = [str(c) for c in z["codes"]]
        x = z["rain"].astype(np.float32)[:, [src.index(c) for c in codes]]
        n = min(i, len(x))
        r[0, :n] = x[:n]
    else:
        z = np.load(DATA / "gp_daily.npz")
        r[0, :i] = z["rain"][list(z["years"]).index(t.year), :i]
    r[0, i:] = 0.0                                         # nothing on or after the issue day is used
    return r, i


def load_gfs(t: date, path, glat, glon):
    if path:
        z = np.load(path)
        return to_gp(z["pr"].astype(np.float32), z["lat"], z["lon"], glat, glon)
    f = REPO / "ckpts" / "gfs16" / "all" / f"gfs16_{t.year}.npz"
    if f.exists():
        z = np.load(f)
        ds = list(z["dates"].astype(str))
        if t.isoformat() in ds:
            return to_gp(z["pr"][ds.index(t.isoformat())].astype(np.float32), z["lat"], z["lon"], glat, glon)
    return None


def load_gefs(t: date, path, glat, glon):
    """latest GEFS 35-day run within 6 days of t -> (member rain [G, M, 28] from the issue day, run age in days)
    (file format of kaggle/gefs: gefs35_<year>.npz)."""
    import glob
    fs = [path] if path else glob.glob(str(REPO / "ckpts" / "gefs" / "**" / f"gefs35_{t.year}.npz"), recursive=True)
    if not fs:
        return None
    z = np.load(fs[0])
    inits = [date.fromisoformat(s) for s in z["inits"].astype(str)]
    c = [n for n, d in enumerate(inits) if 0 <= (t - d).days <= 6]
    if not c:
        return None
    n = c[-1]; age = (t - inits[n]).days
    a = bil(z["pr10"][n].astype(np.float32), z["lat25"], z["lon25"], glat, glon)          # [M, 10, G]
    b = bil(z["pr35"][n].astype(np.float32), z["lat50"], z["lon50"], glat, glon)          # [M, 25, G]
    R = np.maximum(np.concatenate([a, b], 1), 0).transpose(2, 0, 1)                       # [G, M, 35]
    return R[..., age:age + 28], age


def gefs2_prob(e, p_out, raw, i, year):
    """calibrated-GEFS v2 hybrid for target e from the outlook probabilities [G] and the raw run."""
    E, age = raw
    k = joblib.load(MOD / f"stack_gefs2_{e}.joblib")
    X = np.full((NI,) + E.shape, np.nan, np.float32); X[i] = E
    ag = np.full(NI, np.nan, np.float32); ag[i] = age
    f = member_feats(apply_qm(X, k["qm"]), ag, k["normal"], year)
    Z = np.stack([f[n][i] for n in k["features"]], -1)
    return predict_offset(k["w"], (Z - k["mu"]) / k["sd"], logit(p_out))


def load_v3(t: date, path, codes):
    if path:
        z = np.load(path)
        src = [str(c) for c in z["codes"]]
        return z["rain"].astype(np.float32)[[src.index(c) for c in codes]]
    st = np.load(RES / "stack_week1.npz")
    ys = list(st["years"])
    if t.year in ys:
        v = st["v3"][ys.index(t.year), (t - date(t.year, 5, 1)).days].astype(np.float32)
        if (v >= 0).all():
            return v
    return None


def issue(t: date, idx_dir: Path, rain=None, gfs=None, v3=None, gefs=None):
    gd = np.load(DATA / "gp_daily.npz")
    codes = [str(c) for c in gd["codes"]]
    lat, lon = gd["lat"].astype(np.float32), gd["lon"].astype(np.float32)
    r, i = load_rain(t, rain, codes)
    assert 0 <= i < NI, "outlooks are issued 1 May - 30 Sep"
    ix = index_at(index_series(idx_dir), t)
    idx = {k: np.full((1, D), np.nan, np.float32) for k in ix}
    for k, v in ix.items():
        idx[k][0, i] = v
    ws = observed_wet_starts(r)
    G16 = load_gfs(t, gfs, gd["lat"], gd["lon"])
    V3 = load_v3(t, v3, codes)
    GR = load_gefs(t, gefs, gd["lat"].astype(np.float64), gd["lon"].astype(np.float64))
    GE = ens_feats(GR[0], GR[1]) if GR is not None else None
    sel = json.load(open(RES / "final_selection.json"))
    p, src = {}, {}
    for e in EVENTS:
        m = load_model(MOD / f"{e}.joblib")
        X = features(r, idx, ws, m["clim_prob"], m["clim_mean"], lat, lon, [i])[0, 0]      # [G, F]
        p[e] = m["model"].predict_proba(X)[:, 1]
        src[e] = "outlook"
    v3in = V3 if V3 is not None else np.full((len(codes), 7), np.nan, np.float32)

    def gfs_prob(e, po):
        k = joblib.load(MOD / f"stack_gfs_{e}.joblib")
        return k["lr"].predict_proba((stack_X(po, G16, v3in) - k["mu"]) / k["sd"])[:, 1]

    for e in EVENTS:                                       # validated hybrids on top of the outlook probabilities
        s = sel.get(e, {}).get("source")
        if s == "blend" and (G16 is not None or GR is not None):     # mean of both hybrids; either one alone if the other is missing
            parts = ([gfs_prob(e, p[e])] if G16 is not None else []) + ([gefs2_prob(e, p[e], GR, i, t.year)] if GR is not None else [])
            p[e] = np.mean(parts, 0)
            src[e] = "blend" if len(parts) == 2 else ("gfs" if G16 is not None else "gefs2")
        elif s == "gefs2" and GR is not None:
            p[e] = gefs2_prob(e, p[e], GR, i, t.year)
            src[e] = "gefs2"
        elif s == "gfs" and G16 is not None:
            p[e] = gfs_prob(e, p[e])
            src[e] = "gfs"
        elif s == "gefs" and GE is not None:
            k = joblib.load(MOD / f"stack_gefs_{e}.joblib")
            X = np.concatenate([logit(p[e])[:, None], GE], 1)
            p[e] = k["lr"].predict_proba((X - k["mu"]) / k["sd"])[:, 1]
            src[e] = "gefs"
        elif s == "v3" and V3 is not None:
            k = joblib.load(MOD / f"stack_v3_{e}.joblib")
            p[e] = k["lr"].predict_proba(v3_X(p[e], V3))[:, 1]
            src[e] = "v3"
    onset, _ = onset_and_false(np.where(np.arange(D)[None, :, None] < i, r, np.nan))
    seen = np.isfinite(onset[0]) & (onset[0] + CONFIRM <= i)
    fin = lambda v: float(v) if np.isfinite(v) else None
    out = {"issued": t.isoformat(), "indices": {k: (None if fin(v) is None else round(float(v), 3)) for k, v in ix.items()},
           "gfs": G16 is not None, "v3": V3 is not None, "gefs": GE is not None, "sources": src, "gp": {}}
    for j, c in enumerate(codes):
        ph = {e: float(p[e][j]) for e in EVENTS}
        if seen[j]:
            ph.update({f"onset_{k}": 0.0 for k in range(1, 5)}, false3w=0.0)
        out["gp"][c] = {"p": {e: round(v, 3) for e, v in ph.items()}, "onset_seen": bool(seen[j]),
                        "advisories": advise(ph, bool(seen[j]), t.month, fin(ix["nino34"]), fin(ix["dmi"]))}
    return out


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("date")
    a.add_argument("--idx", default=None)
    a.add_argument("--rain")
    a.add_argument("--gfs")
    a.add_argument("--v3")
    a.add_argument("--gefs")
    a.add_argument("--out")
    o = a.parse_args()
    idx_dir = Path(o.idx) if o.idx else REPO / "outlook" / "data" / "idx"
    res = issue(date.fromisoformat(o.date), idx_dir, o.rain, o.gfs, o.v3, o.gefs)
    if o.out:
        open(o.out, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    n_adv = sum(len(g["advisories"]) for g in res["gp"].values())
    print(f"issued {res['issued']} | GFS {res['gfs']} | GEFS {res['gefs']} | v3 {res['v3']} | {n_adv} advisories over {len(res['gp'])} GPs")
    print("sources:", {k: v for k, v in res["sources"].items() if v != "outlook"})
