"""
Final SIH-26074 downscaler: one trained system, four operating modes.

    from sihv3.predict import FinalDownscaler
    model = FinalDownscaler("models/final")                 # bundle written by sihv3.predict.export_bundle
    out = model.predict(history, forecast, mode="BALANCED")  # normalised model inputs, see data.V3Data
    out["mean"]    # [B,7,6,80,80] physical (mm/day, C, C, %, m/s, m/s)
    out["members"] # [K,B,7,6,80,80] (diffusion modes)
    out["prob"]    # {"precip>15": [B,7,80,80], "precip>30": ...} (diffusion modes)

Modes (settings in configs/final/modes.yaml):
  FAST      deterministic MoE transformer + rain quantile mapping (multi-season out-of-fold fit)
  BALANCED  + cross-fitted residual diffusion, DPM-Solver++, moderate steps x 8 members, spread-calibrated
  ACCURATE  more denoising steps
  ENSEMBLE  more members, for threshold probabilities used by agro-advisories
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import yaml

from sihv3.calibrate import apply_spread
from sihv3.data import Normalizer
from sihv3.modes import apply_qm
from sihv3.train import build, det_predict, sample

THRESHOLDS = (15.0, 30.0, 64.5)


class FinalDownscaler:
    def __init__(self, bundle_dir, device=None):
        b = Path(bundle_dir)
        self.dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.modes = yaml.safe_load(open(b / "modes.yaml"))
        self.norm = Normalizer(b / "normalization_stats_v3.yaml")
        self.det, _, self.args = self._load(b / "det.pt", False)
        self.diff, self.sigma, _ = self._load(b / "diff.pt", True)
        cal = np.load(b / "calibration.npz")
        self.alpha = cal["alpha"].reshape(7, 6, 1, 1)
        self.qm = (cal["qm_pq"], cal["qm_oq"])
        self.static = torch.from_numpy(np.load(b / "static.npy")).to(self.dev)

    def _load(self, path, diffusion):
        ck = torch.load(path, map_location=self.dev, weights_only=False)
        a = argparse.Namespace(**ck["args"])
        m = build(a, diffusion=diffusion, size=a.size).to(self.dev)
        m.load_state_dict(ck["ema"])
        sig = torch.tensor(ck["sigma"], device=self.dev).view(1, 1, 6, 1, 1) if diffusion else None
        return m.eval().requires_grad_(False), sig, a

    @torch.no_grad()
    def predict(self, history, forecast, mode="BALANCED", seed=0):
        """history [B,H,6,N,N], forecast [B,7,6,N,N] normalised tensors (H=3, N=40 for the shipped model)."""
        cfg = self.modes[mode]
        bsz = forecast.shape[0]
        batch = {"history": history.to(self.dev), "forecast": forecast.to(self.dev),
                 "static": self.static[None].expand(bsz, -1, -1, -1)}
        amp = dict(device_type=self.dev.type, dtype=torch.float16, enabled=self.dev.type == "cuda")
        with torch.autocast(**amp):
            yd = det_predict(self.det, batch).float()
        if cfg["members"] <= 1:  # FAST
            mean = self.norm.inv(yd, axis=2).cpu().numpy()
            if cfg.get("rain_qm", True):
                mean = apply_qm(mean, self.qm)
            return {"mean": mean, "mode": mode}
        g = torch.Generator(device=self.dev).manual_seed(seed)
        with torch.autocast(**amp):
            ens = sample(self.diff, batch, yd, self.sigma, steps=cfg["steps"], members=cfg["members"],
                         sampler="dpmpp2m", gen=g, batch_members=True)
        E = self.norm.inv(ens.float(), axis=3).cpu().numpy().transpose(1, 0, 2, 3, 4, 5)  # [B,K,...]
        if cfg.get("spread_calibration", True):
            E = apply_spread(E, self.alpha)
        prob = {f"precip>{t:g}": (E[:, :, :, 0] >= t).mean(1) for t in THRESHOLDS}
        return {"mean": E.mean(1), "members": E.transpose(1, 0, 2, 3, 4, 5), "prob": prob, "mode": mode}


def export_bundle(out_dir, det_ckpt, diff_ckpt, alpha, qm, static, stats_yaml, modes):
    """Write the self-contained final model bundle."""
    import shutil
    o = Path(out_dir)
    o.mkdir(parents=True, exist_ok=True)
    shutil.copy(det_ckpt, o / "det.pt")
    shutil.copy(diff_ckpt, o / "diff.pt")
    shutil.copy(stats_yaml, o / "normalization_stats_v3.yaml")
    np.savez(o / "calibration.npz", alpha=np.asarray(alpha, np.float32), qm_pq=qm[0], qm_oq=qm[1])
    np.save(o / "static.npy", np.asarray(static, np.float32))
    (o / "modes.yaml").write_text(yaml.safe_dump(modes, sort_keys=False))
    json.dump({"det": str(det_ckpt), "diff": str(diff_ckpt)}, open(o / "provenance.json", "w"), indent=1)
