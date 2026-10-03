"""
PS 26086 outlook data: daily gram-panchayat (GP) rain for Mandya, 1 May - 31 Oct, 1981-2023, from UCSB CHIRPS v2.0
p05 (cropped to the v3 0.05 deg grid by kaggle/chirps kernels), plus the climate indices at every issue date.

  python -m outlook.build <chirps_npz_dir> <index_dir>
-> outlook/data/gp_daily.npz : rain [Y, D, G] mm/day, years [Y], doy0 (day index 0 = 1 May), codes [G], taluk [G]
-> outlook/data/indices.npz  : omi_pc1/omi_pc2 (issue day - 1), nino34 (latest week <= issue - 4 d), dmi (previous month),
                               shape [Y, D] each (NaN where the index does not exist yet, e.g. OMI before 1991)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outlook" / "data"
YEARS = list(range(1981, 2024))
D = 184                                    # 1 May .. 31 Oct
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def day(y, i):
    return date(y, 5, 1) + timedelta(days=i)


def gp_weights():
    cells = json.load(open(REPO / "demo" / "data" / "serving" / "gp_cells.json", encoding="utf-8"))
    codes = sorted(cells)
    W = np.zeros((len(codes), 6400), np.float32)
    for i, c in enumerate(codes):
        for r, col, w in cells[c]["cells"]:
            W[i, r * 80 + col] = w
    return codes, W, cells


INDEX_KEYS = ("omi_pc1", "omi_pc2", "nino34", "dmi", "bsiso_x", "bsiso_y")


def index_series(idx_dir: Path):
    """Parse the raw index files once."""
    # MJO: NOAA PSL *real-time* OMI (ROMI, causal: no band-pass filter using future days). The plain OMI file is
    # 20-96-day band-pass filtered with a centred filter and leaks the following weeks into the issue date.
    omi = {}
    for line in open(idx_dir / "romi.txt"):
        p = line.split()
        if len(p) >= 7:
            omi[date(int(p[0]), int(p[1]), int(p[2]))] = (float(p[4]), float(p[5]))
    # BSISO: Kikuchi real-time bimodal-ISO PCs (2002-03 .. 2022-12; missing elsewhere)
    bs = {}
    for line in open(idx_dir / "bsiso_rt.txt"):
        p = line.split()
        if len(p) >= 5 and p[0].isdigit():
            bs[date(int(p[0]), int(p[1]), int(p[2]))] = (float(p[3]), float(p[4]))
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
    return {"omi": omi, "bsiso": bs, "nino": nino, "nino_dates": [d for d, _ in nino], "dmi": dmi}


def index_at(S, t: date):
    """Index values usable for an outlook issued on day t (NaN where not yet published)."""
    out = dict.fromkeys(INDEX_KEYS, np.nan)
    o = S["omi"].get(t - timedelta(days=1))
    if o:
        out["omi_pc1"], out["omi_pc2"] = o
    b = S["bsiso"].get(t - timedelta(days=1))
    if b:
        out["bsiso_x"], out["bsiso_y"] = b
    j = np.searchsorted(S["nino_dates"], t - timedelta(days=4), side="right") - 1
    if j >= 0 and (t - S["nino_dates"][j]).days <= 14:
        out["nino34"] = S["nino"][j][1]
    pm = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
    out["dmi"] = S["dmi"].get(pm, np.nan)
    return out


def main(chirps_dir: Path, idx_dir: Path):
    OUT.mkdir(parents=True, exist_ok=True)
    codes, W, cells = gp_weights()
    rain = np.full((len(YEARS), D, len(codes)), np.nan, np.float32)
    for k, y in enumerate(YEARS):
        z = np.load(chirps_dir / f"chirps_{y}.npz")
        dates = [str(x) for x in z["dates"]]
        assert dates[0] == f"{y}-05-01" and len(dates) == D, (y, dates[0], len(dates))
        P = np.nan_to_num(z["precip"].astype(np.float32), nan=0.0)      # [D,80,80]; sea cells are not used by any GP
        rain[k] = P.reshape(D, 6400) @ W.T
    np.savez_compressed(OUT / "gp_daily.npz", rain=rain, years=np.array(YEARS), codes=np.array(codes),
                        taluk=np.array([cells[c]["taluk"] for c in codes]), lat=np.array([cells[c]["lat"] for c in codes]),
                        lon=np.array([cells[c]["lon"] for c in codes]))
    print(f"GP daily rain {rain.shape}: mean {np.nanmean(rain):.2f} mm/day, Jun-Sep mean "
          f"{np.nanmean(rain[:, 31:153]):.2f}, NaN {int(np.isnan(rain).sum())}")

    # ---- climate indices known at issue time ----
    series = index_series(idx_dir)
    shape = (len(YEARS), D)
    arr = {k: np.full(shape, np.nan, np.float32) for k in INDEX_KEYS}
    for a, y in enumerate(YEARS):
        for i in range(D):
            for k, v in index_at(series, day(y, i)).items():
                arr[k][a, i] = v
    pc1, pc2, n34, dm, bx, by = (arr[k] for k in INDEX_KEYS)
    np.savez_compressed(OUT / "indices.npz", omi_pc1=pc1, omi_pc2=pc2, nino34=n34, dmi=dm, bsiso_x=bx, bsiso_y=by, years=np.array(YEARS))
    print(f"indices: real-time MJO coverage {np.isfinite(pc1).mean():.0%}, BSISO {np.isfinite(bx).mean():.0%}, "
          f"Nino3.4 {np.isfinite(n34).mean():.0%}, DMI {np.isfinite(dm).mean():.0%}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
