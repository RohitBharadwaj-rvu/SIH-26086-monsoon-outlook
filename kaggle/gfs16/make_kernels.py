"""Kaggle CPU kernels: GFS 0.25 deg daily precipitation for forecast days 1-16 over a Mandya box (11.75-13.5 N,
75.75-77.75 E), every 00Z init 1 May - 30 Sep of one year. Output: gfs16_<year>.npz {dates, lat, lon, pr[n,16,lat,lon] mm/day}.

  AWS (2021-2023): the running total "APCP:surface:0-N ..." at f024, f048, ..., f384 (byte range from the .idx),
                   daily total = difference of consecutive running totals.
  NCAR (2015-2020): NCSS subset; f006..f240 6-h mean rate (x 21600 = 6-h total), f252..f384 12-h accumulation.
"""
import json
import sys
from pathlib import Path

SCRIPT = r'''
import os, sys, time, json, io, numpy as np, requests
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
YEAR = {year}
MODE = "aws" if YEAR >= 2021 else "ncar"
N, S, E, W = 13.5, 11.75, 77.75, 75.75
LAT = np.round(np.arange(N, S - 1e-6, -0.25), 2); LON = np.round(np.arange(W, E + 1e-6, 0.25), 2)
out = "/kaggle/working/gfs16"; os.makedirs(out, exist_ok=True)
sess = requests.Session()
def get(url, headers=None, tries=6):
    for k in range(tries):
        try:
            r = sess.get(url, headers=headers, timeout=90)
            if r.status_code in (200, 206):
                return r
            last = f"HTTP {{r.status_code}}"
            if r.status_code == 400:            # variable not in this file: retrying cannot help
                break
        except Exception as e:
            last = repr(e)
        time.sleep(2 + 3 * k)
    raise RuntimeError(f"{{url}}: {{last}}")
if MODE == "aws":
    for pk in ([], ["eccodes"], ["eccodes", "ecmwflibs"]):
        try:
            if pk: os.system(f"{{sys.executable}} -m pip install -q {{' '.join(pk)}} 2>&1 | tail -1")
            import eccodes; eccodes.codes_get_api_version(); break
        except Exception as e:
            print("eccodes not ready", e, flush=True)
    import eccodes
    def running_total(d, h):
        base = f"https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{{d:%Y%m%d}}/00/atmos/gfs.t00z.pgrb2.0p25.f{{h:03d}}"
        lines = get(base + ".idx").text.strip().split("\n")
        for k, l in enumerate(lines):
            p = l.split(":")
            if p[3] == "APCP" and p[4] == "surface" and p[5].startswith("0-"):
                a, b = int(p[1]), int(lines[k + 1].split(":")[1]) - 1
                msg = get(base, headers={{"Range": f"bytes={{a}}-{{b}}"}}).content
                gid = eccodes.codes_new_from_message(msg)
                try:
                    ni, nj = eccodes.codes_get(gid, "Ni"), eccodes.codes_get(gid, "Nj")
                    v = eccodes.codes_get_values(gid).reshape(nj, ni)        # lat 90 -> -90, lon 0 -> 359.75
                finally:
                    eccodes.codes_release(gid)
                lat = 90 - 0.25 * np.arange(nj); lon = 0.25 * np.arange(ni)
                ri = [int(np.argmin(np.abs(lat - x))) for x in LAT]; ci = [int(np.argmin(np.abs(lon - x))) for x in LON]
                return v[np.ix_(ri, ci)].astype(np.float32)
        raise RuntimeError(f"no running APCP total at f{{h:03d}} {{d}}")
    def one_init(d):
        cum = [np.zeros((len(LAT), len(LON)), np.float32)] + [running_total(d, 24 * k) for k in range(1, 17)]
        return np.stack([np.maximum(cum[k + 1] - cum[k], 0) for k in range(16)])
else:
    import xarray as xr
    NCSS = "https://thredds.rda.ucar.edu/thredds/ncss/grid/files/g/d084001/{{y}}/{{d}}/gfs.0p25.{{d}}00.f{{h:03d}}.grib2"
    BB = f"&north={{N}}&south={{S}}&east={{E}}&west={{W}}&accept=netcdf"
    def fetch(d, h, var):
        url = NCSS.format(y=d.year, d=d.strftime("%Y%m%d"), h=h) + f"?var={{var}}" + BB
        r = get(url)
        ds = xr.open_dataset(io.BytesIO(r.content), engine="h5netcdf" if r.content[:4] == b"\x89HDF" else None, decode_times=False)
        da = ds[var]
        latd = [c for c in da.dims if "lat" in c.lower()][0]; lond = [c for c in da.dims if "lon" in c.lower()][0]
        da = da.isel({{k: 0 for k in da.dims if k not in (latd, lond)}}).transpose(latd, lond)
        lat = np.asarray(ds[latd].values, float); lon = np.asarray(ds[lond].values, float) % 360
        if da.size == 0:
            raise RuntimeError("empty field")
        ri = [int(np.argmin(np.abs(lat - x))) for x in LAT]; ci = [int(np.argmin(np.abs(lon - x))) for x in LON]
        assert max(abs(lat[ri] - LAT)) < 0.13 and max(abs(lon[ci] - LON)) < 0.13, "grid mismatch"
        return np.asarray(da.values)[np.ix_(ri, ci)].astype(np.float32)
    def bucket(d, h):
        if h <= 240:
            return h, fetch(d, h, "Precipitation_rate_surface_6_Hour_Average") * 21600.0      # 6-h total ending at h
        # pre-FV3 files: a 12-h accumulation; FV3-era files (from mid-2019) only keep the 6-h mean rate at the
        # 12-hourly steps, so the 12-h total is approximated as that rate x 12 h
        for var, f in (("Total_precipitation_surface_12_Hour_Accumulation", 1.0), ("Precipitation_rate_surface_12_Hour_Average", 43200.0),
                       ("Precipitation_rate_surface_6_Hour_Average", 43200.0)):
            try:
                return h, fetch(d, h, var) * f                                                       # 12-h total ending at h
            except Exception:
                pass
        raise RuntimeError(f"no 12-h precip at f{{h:03d}} {{d}}")
    STEPS = list(range(6, 241, 6)) + list(range(252, 385, 12))
    def one_init(d):
        with ThreadPoolExecutor(8) as ex:
            res = dict(ex.map(lambda h: bucket(d, h), STEPS))
        day = np.zeros((16, len(LAT), len(LON)), np.float32)
        for h, v in res.items():
            day[(h - 1) // 24] += v                                                # bucket ending at h belongs to day (h-1)//24
        return day
inits = []
d = date(YEAR, 5, 1)
while d <= date(YEAR, 9, 30):
    inits.append(d); d += timedelta(days=1)
ONLY = {only}
if ONLY:
    inits = [date.fromisoformat(x) for x in ONLY]
t0, arr, ok, bad = time.time(), {{}}, 0, []
def job(d):
    try:
        return d, one_init(d)
    except Exception as e:
        return d, e
with ThreadPoolExecutor(4 if MODE == "ncar" else 8) as ex:
    for d, v in ex.map(job, inits):
        if isinstance(v, Exception):
            bad.append((d.isoformat(), repr(v)[:200]))
        else:
            arr[d.isoformat()] = v; ok += 1
        if (ok + len(bad)) % 10 == 0:
            el = time.time() - t0; n = ok + len(bad)
            print(f"{{n}}/{{len(inits)}} ok={{ok}} bad={{len(bad)}} | {{el/60:.1f}} min | ETA {{el/n*(len(inits)-n)/60:.1f}} min", flush=True)
ds_ = sorted(arr)
np.savez_compressed(f"{{out}}/gfs16_{{YEAR}}.npz", dates=np.array(ds_), lat=LAT, lon=LON, pr=np.stack([arr[k] for k in ds_]).astype(np.float32))
json.dump({{"ok": ok, "bad": bad, "min": (time.time() - t0) / 60}}, open(f"{{out}}/log_{{YEAR}}.json", "w"), indent=1)
print("DONE", ok, "bad", len(bad), flush=True)
'''


ONLY_DATES = {}
SUFFIX = ""


def main(user, years, tag):
    for y in years:
        d = Path(__file__).parent / "runs" / f"{tag}{y}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "job.py").write_text(SCRIPT.format(year=y, only=repr(ONLY_DATES.get(y, []))))
        slug = f"sih26074-gfs16-{y}" + ("-fill" if ONLY_DATES.get(y) else "") + SUFFIX
        meta = {"id": f"{user}/{slug}", "title": slug, "code_file": "job.py", "language": "python",
                "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_tpu": False, "enable_internet": True,
                "dataset_sources": [], "competition_sources": [], "kernel_sources": []}
        (d / "kernel-metadata.json").write_text(json.dumps(meta, indent=1))
        print("prepared", d)


if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2].split(",")], sys.argv[3] if len(sys.argv) > 3 else "")
