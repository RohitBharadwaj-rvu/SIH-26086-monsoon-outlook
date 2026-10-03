"""
Build the data bundle the PS 26086 web app reads (monsoon/frontend/data/):

  meta.json            panchayats, taluks, event keys/labels, advisory templates (en/kn), seasons, default view
  season_<Y>.json      weekly issues (Mondays, May-Sep): climate indices per issue, and per panchayat per issue the 18
                       outlook probabilities, ranked advisories [id, level, week, vals], v3 week-1 daily rain, observed
                       weekly totals and the season's observed onset date (replay verification)
  model.json           the ML view: model cards, cross-validated skill, reliability, feature importance, v3 card

  python -m monsoon.build_bundle --source synthetic     (interim: synthetic probabilities, real climate indices)
  python -m monsoon.build_bundle --source real          (outlook/results + v3 week-1; after outlook.model has run)
"""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from outlook.advisory import TEMPLATES, THRESH, advise

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "monsoon" / "frontend" / "data"
EVENTS = [f"onset_{k}" for k in range(1, 5)] + ["false3w", "break3w"] + [f"{e}_{k}" for e in ("dry", "wet", "heavy") for k in range(1, 5)]
LABELS = {
    "onset": {"en": "Monsoon onset", "kn": "ಮುಂಗಾರು ಆರಂಭ"},
    "false3w": {"en": "False-onset risk", "kn": "ಸುಳ್ಳು ಮುಂಗಾರು ಅಪಾಯ"},
    "break3w": {"en": "Dry spell (7+ days) in 3 weeks", "kn": "3 ವಾರಗಳಲ್ಲಿ ಒಣ ಹವೆ (7+ ದಿನ)"},
    "dry": {"en": "Dry week", "kn": "ಒಣ ವಾರ"},
    "wet": {"en": "Wet week", "kn": "ಮಳೆಯ ವಾರ"},
    "heavy": {"en": "Heavy downpour", "kn": "ಭಾರಿ ಮಳೆ"},
}
SEASONS = list(range(2015, 2024))
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
IDX_DIR = Path(r"C:/Users/rohit/AppData/Local/Temp/claude/C--Users-rohit-claude/1cb502c9-03b5-4b89-bde6-f17bfe369352/scratchpad/idx")


def issues(y):
    d = date(y, 5, 1)
    d += timedelta(days=(7 - d.weekday()) % 7)            # first Monday on/after 1 May
    out = []
    while d <= date(y, 9, 30):
        out.append(d)
        d += timedelta(days=7)
    return out


def load_indices(idx_dir=IDX_DIR):
    omi = {}
    for line in open(idx_dir / "romi.txt"):                 # real-time OMI (causal), as used by the models
        p = line.split()
        if len(p) >= 7:
            omi[date(int(p[0]), int(p[1]), int(p[2]))] = (float(p[4]), float(p[5]))
    pat = re.compile(r"(\d{2})([A-Z]{3})(\d{4})\s+[\d.]+\s*(-?[\d.]+)\s+[\d.]+\s*(-?[\d.]+)\s+[\d.]+\s*(-?[\d.]+)")
    nino = []
    for line in open(idx_dir / "nino34w.txt"):
        m = pat.search(line)
        if m:
            nino.append((date(int(m.group(3)), MON[m.group(2)], int(m.group(1))), float(m.group(6))))
    nino.sort()
    dmi = {}
    for line in open(idx_dir / "dmi.txt"):
        p = line.split()
        if len(p) == 13 and p[0].isdigit():
            for k in range(12):
                v = float(p[k + 1])
                if v > -99:
                    dmi[(int(p[0]), k + 1)] = v

    def at(t):
        o = omi.get(t - timedelta(days=1))
        n = [v for d, v in nino if d <= t - timedelta(days=4)]
        pm = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
        rec = {"date": t.isoformat(), "nino34": n[-1] if n else None, "dmi": dmi.get(pm)}
        if o:
            amp = math.hypot(*o)
            # NOAA PSL: OMI is comparable with RMM when plotted as x = PC2, y = -PC1; RMM phase 1 spans 180-225 deg,
            # then counter-clockwise (2: 225-270 ... 5: 0-45 ... 8: 135-180)
            x, yv = o[1], -o[0]
            ang = math.degrees(math.atan2(yv, x)) % 360
            rec.update({"mjo_pc1": round(o[0], 3), "mjo_pc2": round(o[1], 3), "mjo_x": round(x, 3), "mjo_y": round(yv, 3),
                        "mjo_amp": round(amp, 3), "mjo_phase": int(((ang - 180) % 360) // 45) + 1})
        return rec
    return at


def gp_list():
    cells = json.load(open(REPO / "demo" / "data" / "serving" / "gp_cells.json", encoding="utf-8"))
    return [{"code": c, "name": cells[c]["name"].title(), "taluk": cells[c]["taluk"], "lat": cells[c]["lat"], "lon": cells[c]["lon"]}
            for c in sorted(cells)]


def synthetic_season(y, gps, idx_at, rng):
    """Interim probabilities with realistic structure (seasonal cycle, spatial gradient, MJO modulation, onset timing)."""
    lat = np.array([g["lat"] for g in gps]); lon = np.array([g["lon"] for g in gps])
    sp = 0.6 * np.sin((lat - 12.2) * 6) + 0.4 * np.cos((lon - 76.3) * 5)            # smooth spatial pattern
    onset_day = 34 + rng.normal(0, 9) + 6 * (lon - 76.8) + rng.normal(0, 2.5, len(gps))  # days after 1 May
    out = {"issues": [], "gp": {g["code"]: {"p": [], "adv": [], "v3w1": [], "obs": []} for g in gps}}
    sig = lambda x: 1 / (1 + np.exp(-x))
    for t in issues(y):
        i = (t - date(y, 5, 1)).days
        ix = idx_at(t)
        out["issues"].append(ix)
        mjo = (ix.get("mjo_pc1") or 0) * 0.6 - (ix.get("mjo_pc2") or 0) * 0.4
        season = math.sin(math.pi * min(max((i - 20) / 130, 0), 1))
        n34 = ix.get("nino34") or 0.0
        for g_i, g in enumerate(gps):
            ph = {}
            for k in range(1, 5):
                lo = i + 7 * (k - 1)
                sd = 5 + 3 * k
                cdf = lambda x: 0.5 * (1 + math.erf((x - onset_day[g_i]) / (sd * math.sqrt(2))))
                ph[f"onset_{k}"] = 0.0 if i > onset_day[g_i] else max(0.0, cdf(lo + 7) - cdf(lo))
                fade = 0.85 ** (k - 1)
                ph[f"dry_{k}"] = float(sig(-1.2 + 0.9 * (1 - season) - 0.6 * fade * mjo + 0.25 * n34 - 0.3 * sp[g_i]))
                ph[f"wet_{k}"] = float(sig(-1.3 + 0.5 * season + 0.6 * fade * mjo - 0.2 * n34 + 0.3 * sp[g_i]))
                ph[f"heavy_{k}"] = float(sig(-3.4 + 0.8 * season + 0.5 * fade * mjo + 0.4 * sp[g_i]))
            ph["false3w"] = float(sig(-0.9 - 0.8 * mjo + 0.3 * n34)) if i <= onset_day[g_i] else 0.0
            ph["break3w"] = float(sig(-0.4 + 0.6 * season - 0.7 * mjo + 0.3 * n34 - 0.2 * sp[g_i]))
            p = [round(ph[e], 3) for e in EVENTS]
            onset_seen = i > onset_day[g_i] + 3
            adv = advise(ph, onset_seen, t.month, ix.get("nino34"), ix.get("dmi"))
            wk = np.clip(rng.gamma(0.7, 4 + 6 * season, 7) * (rng.random(7) > 0.45 - 0.2 * mjo), 0, 120)
            d = out["gp"][g["code"]]
            d["p"].append(p); d["adv"].append(adv); d["v3w1"].append([round(float(x), 1) for x in wk])
            d["obs"].append([round(float(x), 1) for x in rng.gamma(1.2, 8 + 14 * season, 4)])
        for g_i, g in enumerate(gps):
            out["gp"][g["code"]]["onset_obs"] = (date(y, 5, 1) + timedelta(days=int(onset_day[g_i]))).isoformat()
    return out


def model_card():
    """ML view content from REAL measurements available now (feasibility study + v3 reports); replaced by the 43-season
    cross-validation when outlook.model has run."""
    feas = json.load(open(REPO / "results" / "feasibility_ps26086.json"))
    split = json.load(open(REPO / "results" / "feasibility_ps26086_split.json")) if (REPO / "results" / "feasibility_ps26086_split.json").exists() else {}
    card = {
        "generated": datetime.now().isoformat(timespec="minutes"),
        "pipeline": [
            {"id": "v3", "name": "v3 spatiotemporal transformer + residual diffusion", "role": "Days 1-7: downscales the GFS 0.25° forecast to 0.05° (all 6 variables), 4 operating modes",
             "inputs": ["GFS 0.25° 7-day forecast (40×40 context)", "ERA5 last 3 days", "terrain, land mask"], "params": "28.8 M (19.3 M active, MoE) + 17.8 M denoiser",
             "training": "2015-2022 monsoons, 2023 held out", "status": "trained"},
            {"id": "outlook", "name": "Sub-seasonal outlook (gradient-boosted, one model per event × week)", "role": "Weeks 1-4: probabilities of onset, false onset, dry spells, wet weeks and heavy downpours per panchayat",
             "inputs": ["MJO (OMI PC1/PC2, amplitude)", "ENSO (weekly Niño 3.4)", "IOD (DMI)", "panchayat climatology", "recent observed rain", "calendar, location", "v3 week-1 forecast"],
             "params": "18 models", "training": "CHIRPS 1981-2023 (43 monsoons), season-blocked cross-validation", "status": "training"},
            {"id": "expert", "name": "Agronomic expert system", "role": "Probabilities → ranked, crop-specific advisories (Kannada / English), SMS and WhatsApp texts",
             "inputs": ["18 outlook probabilities", "observed onset status", "crop calendar", "ENSO/IOD state"], "params": f"{len(TEMPLATES)} rule templates · explicit, tunable probability thresholds", "status": "ready",
             "thresholds": THRESH},
        ],
        "feasibility_9_seasons": {"source": "scripts/feasibility_ps26086.py (2015-2023, leave-one-season-out, Brier skill vs climatology, 90% CI)",
                                  "all_predictors": feas, "by_index": split},
        "v3_gp_skill_2023": json.load(open(REPO / "monsoon" / "frontend" / "data" / "_v3_skill.json")) if (REPO / "monsoon" / "frontend" / "data" / "_v3_skill.json").exists() else None,
        "cv_43_seasons": None,
    }
    cv = REPO / "outlook" / "results" / "cv_metrics.json"
    if cv.exists():
        card["cv_43_seasons"] = json.load(open(cv))
        card["pipeline"][1]["status"] = "trained"
        card["pipeline"][1]["name"] = "Sub-seasonal outlook (regularised logistic, one model per event × week)"
        card["pipeline"][1]["params"] = "18 models · MJO × season interactions"
    fs = REPO / "outlook" / "results" / "final_selection.json"
    if fs.exists():
        card["final_selection"] = json.load(open(fs))
        card["pipeline"][1]["role"] = ("Weeks 1-4: probabilities of onset, false onset, dry spells, wet weeks and heavy downpours per "
                                       "panchayat; weeks 1-2 blended with GFS days 1-16 and the v3 week-1 forecast where that is validated to help")
        card["pipeline"][1]["inputs"] = ["real-time MJO (ROMI) and BSISO", "ENSO (weekly Niño 3.4)", "IOD (DMI)", "panchayat climatology",
                                         "recent observed rain", "GFS days 1-16 (weeks 1-2)", "v3 week-1 forecast"]
    card["definitions"] = {
        "dry": "all 7 days < 2.5 mm (IMD dry day)", "wet": "weekly total ≥ 1.5 × the panchayat's normal for that week",
        "heavy": "any day ≥ 30 mm", "break3w": "a run of ≥ 7 dry days within the next 3 weeks",
        "onset": "first 2-day rain ≥ 20 mm from 25 May not followed by a 7-day dry spell (< 5 mm) within 20 days",
        "false3w": "sowing rains (2-day ≥ 20 mm) followed by such a dry spell, within the next 3 weeks"}
    return card


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synthetic", "real"], default="synthetic")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    gps = gp_list()
    idx_at = load_indices()
    rng = np.random.default_rng(2026)
    meta = {"region": {"en": "Mandya district, Karnataka", "kn": "ಮಂಡ್ಯ ಜಿಲ್ಲೆ, ಕರ್ನಾಟಕ"}, "seasons": SEASONS,
            "default": {"season": 2023, "issue": "2023-06-12"}, "events": EVENTS, "labels": LABELS,
            "templates": TEMPLATES, "thresholds": THRESH,
            "taluks": sorted({g["taluk"] for g in gps}), "gps": gps, "source": a.source}
    json.dump(meta, open(OUT / "meta.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for y in SEASONS:
        s = synthetic_season(y, gps, idx_at, rng) if a.source == "synthetic" else real_season(y, gps, idx_at)
        s["season"] = y
        json.dump(s, open(OUT / f"season_{y}.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(model_card(), open(OUT / "model.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sizes = {f.name: f.stat().st_size // 1024 for f in OUT.glob("*.json")}
    print("bundle written:", sizes)


_REAL = {}


def _real():
    """Load the out-of-fold outlook probabilities, the week-1 hybrid and observations once."""
    if _REAL:
        return _REAL
    R = REPO / "outlook" / "results"
    gd = np.load(REPO / "outlook" / "data" / "gp_daily.npz")
    _REAL["rain"], _REAL["years"], _REAL["codes"] = gd["rain"].astype(np.float32), list(gd["years"]), [str(c) for c in gd["codes"]]
    _REAL["p"] = {e: np.load(R / f"oof_{e}.npz")["p"].astype(np.float32) for e in EVENTS}
    st = np.load(R / "stack_week1.npz")
    _REAL["stack_years"] = list(st["years"])
    _REAL["v3"] = st["v3_display"].astype(np.float32)
    # per target, the validated source chosen by outlook.select (rule fixed before the final run)
    sel = json.load(open(R / "final_selection.json")) if (R / "final_selection.json").exists() else {}
    srcs = {"v3": st, "gfs": np.load(R / "stack.npz") if (R / "stack.npz").exists() else None}
    _REAL["stack"] = {}
    for e, v in sel.items():
        f = srcs.get(v["source"])
        if f is not None and e in f.files:
            _REAL["stack"][e] = f[e].astype(np.float32)
    _REAL["selection"] = sel
    _REAL["onset"] = np.load(R / "onset.npz")["onset"]
    return _REAL


CONFIRM = 22      # an onset on day d is confirmed (no 7-day dry spell in d+2..d+21) from issue day d+22


def real_season(y, gps, idx_at):
    """Out-of-sample outlook for one replay season: every probability comes from models that never saw season y
    (season-blocked CV for weeks 1-4; leave-one-season-out week-1 hybrid with v3 where a v3 run exists)."""
    D = _real()
    a, sy = D["years"].index(y), D["stack_years"].index(y)
    order = [D["codes"].index(g["code"]) for g in gps]
    out = {"issues": [], "gp": {g["code"]: {"p": [], "adv": [], "v3w1": [], "obs": []} for g in gps}}
    for t in issues(y):
        i = (t - date(y, 5, 1)).days
        ix = idx_at(t)
        out["issues"].append(ix)
        for g_i, g in enumerate(gps):
            j = order[g_i]
            ph = {e: float(D["p"][e][a, i, j]) for e in EVENTS}
            for e, arr in D["stack"].items():                      # week-1 hybrid with v3 (falls back where no v3 run)
                v = float(arr[sy, i, j])
                if np.isfinite(v):
                    ph[e] = v
            od = D["onset"][a, j]
            seen = bool(np.isfinite(od) and od + CONFIRM <= i)          # causal: onset counts once its 21-day check is observed
            if seen:
                for k in range(1, 5):
                    ph[f"onset_{k}"] = 0.0
                ph["false3w"] = 0.0
            p = [round(min(max(ph[e], 0.0), 1.0), 3) for e in EVENTS]
            adv = advise(ph, seen, t.month, ix.get("nino34"), ix.get("dmi"))
            w1 = D["v3"][sy, i, j]
            r = D["rain"][a, :, j]
            d = out["gp"][g["code"]]
            d["p"].append(p); d["adv"].append(adv)
            d["v3w1"].append([round(float(x), 1) for x in w1] if (w1 >= 0).all() else [])
            d["obs"].append([round(float(r[i + 7 * k:i + 7 * k + 7].sum()), 1) for k in range(4)])
        for g_i, g in enumerate(gps):
            od = D["onset"][a, order[g_i]]
            out["gp"][g["code"]]["onset_obs"] = (date(y, 5, 1) + timedelta(days=int(od))).isoformat() if np.isfinite(od) else None
    return out


if __name__ == "__main__":
    main()
