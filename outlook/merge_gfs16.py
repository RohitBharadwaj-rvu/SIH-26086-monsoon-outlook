"""Merge each year's main + fill GFS16 kernel outputs into ckpts/gfs16/all/gfs16_<year>.npz (sorted by init date)."""
import glob
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "ckpts" / "gfs16"
(ROOT / "all").mkdir(parents=True, exist_ok=True)
for y in range(2015, 2024):
    parts = [f for f in glob.glob(str(ROOT / "**" / f"gfs16_{y}.npz"), recursive=True) if "all" not in Path(f).parts]
    if not parts:
        print(y, "missing")
        continue
    rec = {}
    for f in parts:
        z = np.load(f)
        lat, lon = z["lat"], z["lon"]
        for d, a in zip(z["dates"].astype(str), z["pr"]):
            rec[d] = a
    ds = sorted(rec)
    np.savez_compressed(ROOT / "all" / f"gfs16_{y}.npz", dates=np.array(ds), lat=lat, lon=lon, pr=np.stack([rec[d] for d in ds]))
    print(y, len(ds), "inits from", len(parts), "file(s)")
