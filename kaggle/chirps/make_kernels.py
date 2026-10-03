"""Kaggle CPU kernels that download UCSB CHIRPS v2.0 p05 daily (one global netCDF per year), crop to the v3 fine grid
(80x80 cells, centres 14.975..11.025 N x 74.025..77.975 E, rows N->S) for May 1 - Oct 31, and save float16 npz."""
import json, sys
from pathlib import Path

SCRIPT = r'''
import os, sys, time, json, numpy as np, requests, xarray as xr
YEARS = {years}
out = "/kaggle/working/chirps"; os.makedirs(out, exist_ok=True)
FLAT = np.round(np.arange(14.975, 11.0, -0.05), 3); FLON = np.round(np.arange(74.025, 78.0, 0.05), 3)
log = {{}}
for y in YEARS:
    t0 = time.time()
    url = f"https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/netcdf/p05/chirps-v2.0.{{y}}.days_p05.nc"
    fn = f"/kaggle/tmp/c{{y}}.nc"; os.makedirs("/kaggle/tmp", exist_ok=True)
    for attempt in range(4):
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(fn, "wb") as f:
                    for ch in r.iter_content(1 << 22):
                        f.write(ch)
            break
        except Exception as e:
            print(y, "retry", attempt, e, flush=True); time.sleep(10)
    ds = xr.open_dataset(fn)
    sub = ds["precip"].sel(time=slice(f"{{y}}-05-01", f"{{y}}-10-31"))
    sub = sub.sel(latitude=FLAT, longitude=FLON, method="nearest", tolerance=0.001)
    a = sub.values.astype(np.float32)
    assert np.allclose(sub.latitude.values, FLAT, atol=1e-3) and np.allclose(sub.longitude.values, FLON, atol=1e-3)
    np.savez_compressed(f"{{out}}/chirps_{{y}}.npz", precip=a.astype(np.float16), dates=np.array([str(t)[:10] for t in sub.time.values]))
    ds.close(); os.remove(fn)
    log[y] = {{"days": int(a.shape[0]), "nan": int(np.isnan(a).sum()), "mean": float(np.nanmean(a)), "sec": round(time.time() - t0)}}
    print(y, log[y], flush=True)
json.dump(log, open(f"{{out}}/log.json", "w"), indent=1)
print("DONE", flush=True)
'''

def main(user, groups):
    for name, years in groups.items():
        d = Path("runs") / name; d.mkdir(parents=True, exist_ok=True)
        (d / "job.py").write_text(SCRIPT.format(years=years))
        meta = {"id": f"{user}/sih26074-{name}", "title": f"sih26074-{name}", "code_file": "job.py", "language": "python",
                "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_tpu": False, "enable_internet": True,
                "dataset_sources": [], "competition_sources": [], "kernel_sources": []}
        (d / "kernel-metadata.json").write_text(json.dumps(meta, indent=1))
        print("prepared", d)

if __name__ == "__main__":
    main(sys.argv[1], {"chirps-a": list(range(1981, 1996)), "chirps-b": list(range(1996, 2010)), "chirps-c": list(range(2010, 2024))})
