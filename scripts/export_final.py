"""Export the shipped SIH-26074 system (seed 0) into models/final with the pre-registered mode settings.

  python scripts/export_final.py --det ckpts/.../s10f_fin_det_s0/best.pt --diff ckpts/.../s10f_diff_oof_S_s0/best.pt \
      --cal results/s10-modes/out/modes_a/calibration_params.npz
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sihv3.data import V3Data, find  # noqa: E402
from sihv3.predict import export_bundle  # noqa: E402

MODES = {  # pre-registered in docs/decision_log.md before the 2023 modes grid was seen
    "FAST": {"members": 1, "rain_qm": True},
    "BALANCED": {"steps": 16, "members": 8, "spread_calibration": True},
    "ACCURATE": {"steps": 32, "members": 8, "spread_calibration": True},
    "ENSEMBLE": {"steps": 24, "members": 16, "spread_calibration": True},
}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--det", required=True)
    p.add_argument("--diff", required=True)
    p.add_argument("--cal", required=True)
    p.add_argument("--out", default="models/final")
    a = p.parse_args()
    data = V3Data(history_len=3, context=40)
    c = np.load(a.cal)
    export_bundle(a.out, a.det, a.diff, c["alpha"], (c["qm_pq"], c["qm_oq"]), data.static,
                  find("normalization_stats_v3.yaml"), MODES)
    print("bundle written to", a.out)
