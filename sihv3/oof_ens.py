"""
Out-of-fold diffusion ensembles for one held-out season (PS 26086 heavy-rain features).

The backbone forecast y_det comes from the out-of-fold file (fold models that never saw the season) and the residual
denoiser from a fold trained WITHOUT the season, so every member is out-of-sample for that season. No spread
calibration (its factors were fitted on in-sample seasons); the downstream logistic stacker calibrates the fractions.

  python -m sihv3.oof_ens --diff_ckpt '**/f2019/best.pt' --det_pred_file '**/oof/ydet.npz' --year 2019 --members 16 --tag ens2019
-> <out>/<tag>/ens_<year>.npz {dates, rain [n, K, 7, 80, 80] mm/day float16}
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np
import torch

from sihv3.data import V3Data
from sihv3.modes import load
from sihv3.train import parse_years, resolve, sample


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--diff_ckpt", required=True)
    p.add_argument("--det_pred_file", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--members", type=int, default=16)
    p.add_argument("--steps", type=int, default=24)
    p.add_argument("--bs", type=int, default=1)
    p.add_argument("--max_n", type=int, default=0, help="smoke test: first n dates only")
    p.add_argument("--tag", default="ens")
    p.add_argument("--out", default=os.environ.get("SIH_OUT", "/kaggle/working/out" if Path("/kaggle").exists() else "out"))
    a = p.parse_args()
    t0 = time.time()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(a.out) / a.tag
    out.mkdir(parents=True, exist_ok=True)
    diff, sigma, fa = load(a.diff_ckpt, dev, True)
    ty = parse_years(fa.train_years)
    print(f"[{a.tag}] denoiser trained on {ty} | held-out season {a.year}", flush=True)
    assert a.year not in ty, "the season must be held out of the denoiser's training"
    data = V3Data(history_len=fa.H, context=fa.N, fc_history=getattr(fa, "fc_history", False))
    z = np.load(resolve(a.det_pred_file))
    assert list(z["dates"].astype(str)) == list(data.dates) and str(z["kind"]) == "oof"
    det = torch.from_numpy(z["ydet"].astype(np.float32))
    years = np.array([int(d[:4]) for d in data.dates])
    sel = np.where(years == a.year)[0]
    if a.max_n:
        sel = sel[:a.max_n]
    data.idx["_y"] = sel
    g = torch.Generator(device=dev).manual_seed(11)
    rain, dates = [], []
    with torch.no_grad():
        for b in data.batches("_y", a.bs, False, dev):
            yd = det[b["index"]].to(dev)
            with torch.autocast(dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                ens = sample(diff, b, yd, sigma, steps=a.steps, members=a.members, sampler="dpmpp2m", gen=g, batch_members=True)
            E = data.norm.inv(ens.float(), axis=3).cpu().numpy()                      # [K, B, 7, 6, 80, 80]
            rain.append(np.maximum(E[:, :, :, 0], 0).transpose(1, 0, 2, 3, 4).astype(np.float16))
            dates += [str(data.dates[i]) for i in b["index"].tolist()]
    rain = np.concatenate(rain)
    np.savez_compressed(out / f"ens_{a.year}.npz", dates=np.array(dates), rain=rain)
    print(f"[{a.tag}] DONE {rain.shape} mean {rain.astype(np.float32).mean():.2f} mm/day | {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
