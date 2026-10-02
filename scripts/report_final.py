"""Final system report (Sprint 10): shipped model, seed selection, 3-seed spread, capacity points, operating modes,
test-time-compute matrix, latency/VRAM and multivariate consistency -> docs/final_system_report.md
Everything is scored on the 2023 test season, which no model, calibration or selection decision used."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from sihv3.metrics import composite_skill  # noqa: E402

PENDING = "_pending_"


def res(tag):
    f = glob.glob(str(REPO / "results" / "*" / "out" / tag / "result.json"))
    return json.load(open(f[0])) if f else None


def jload(pattern):
    f = sorted(glob.glob(str(REPO / "results" / pattern)))
    return json.load(open(f[0])) if f else None


def css(r, qm=False):
    t = r["test"]
    ref = t["reference_gfs_bilinear"]["aggregate"]
    a = t["precip_qm"]["aggregate"] if qm and t.get("precip_qm") else t["aggregate"]
    return composite_skill(a, ref)


def f(x, d=3):
    return PENDING if x is None else f"{x:.{d}f}"


def main():
    md = ["# SIH-26074 final system — Sprint 10 report\n",
          "GFS 0.25° → 0.05° downscaling over 11–15°N, 74–78°E, 7 daily leads × 6 variables (precipitation, Tmax, Tmin, RH,",
          "U, V). All numbers below are on the **2023 monsoon test season** (Jun–Sep, 122 forecasts), which no model,",
          "calibration fit or selection decision used. CSS = composite skill vs GFS-bilinear (higher is better; for",
          "ensembles, the ensemble mean). Tie rule: 1 SE of the paired difference.\n"]

    # 1. shipped system
    md += ["## 1. The shipped system\n",
           "* **Backbone (FAST):** spatiotemporal transformer, S size with an MoE FFN (8 experts, top-2, MoE in 50 % of",
           "  blocks), history H = 3 days, context N = 40 coarse cells (N/M = 2.5), trained 2015–2022, 50 epochs, no mm-loss.",
           "  Rain quantile mapping per lead and 5×5 block, fitted on the multi-season out-of-fold predictions (2015–2022).",
           "* **Generative stage (BALANCED / ACCURATE / ENSEMBLE):** CorrDiff-style residual diffusion (S denoiser,",
           "  v-prediction, cosine schedule, 80 epochs) trained on **cross-fitted** residuals: every training season's",
           "  residual comes from a deterministic model that never saw that season. Sampled with DPM-Solver++(2M), then",
           "  mean-preserving spread calibration per lead × variable, fitted on 2022 by a model trained without 2022.",
           "* **Mode settings** (pre-registered from Sprint 7/8 validation before the 2023 grid was run): FAST = 1 member;",
           "  BALANCED = 16 steps × 8 members; ACCURATE = 32 × 8; ENSEMBLE = 24 × 16.",
           "* Entry point: `sihv3.predict.FinalDownscaler(\"models/final\").predict(history, forecast, mode=...)`.\n"]

    # 2. seed selection
    md += ["## 2. Seed selection (out-of-fold, 2023 not used) and 3-seed spread\n",
           "| seed | OOF CSS 2015–22 (selection score) | final det test CSS | + rain QM | cross-fitted diffusion test CSS | rain CRPS | rain SSR |",
           "|---|---|---|---|---|---|---|"]
    for s, job, tag in [(0, "s10s0-oofm", "oofm"), (1, "s10s1-oof", "oof"), (2, "s10s2-oof", "oof")]:
        o = jload(f"{job}/out/{tag}/oof_metrics.json")
        d, g = res(f"s10f_fin_det_s{s}"), res(f"s10f_diff_oof_S_s{s}")
        ga = g["test"]["aggregate"] if g else {}
        md.append(f"| {s}{' **(shipped)**' if s == 0 else ''} | {f(o['all_oof']['css'], 4) if o else PENDING} | "
                  f"{f(css(d), 4) if d else PENDING} | {f(css(d, True), 4) if d else PENDING} | "
                  f"{f(css(g), 4) if g else PENDING} | {f(ga.get('precip_crps'))} | {f(ga.get('precip_ssr'), 2)} |")
    md += ["\nSeed 0 has the best OOF score but the seeds are tied within noise (paired season SE ≈ 0.004–0.006).",
           "The spread across seeds in the test column is the honest uncertainty of any single shipped model.\n"]

    # 3. cross-fitting
    md += ["## 3. Cross-fitted vs in-sample residual diffusion (seed 0, final recipe)\n",
           "| diffusion trained on | test CSS | rain CRPS | rain SSR | rain cov90 | rain bias | CSI30 |", "|---|---|---|---|---|---|---|"]
    for tag, name in [("s10f_diff_ins_S_s0", "in-sample residuals (standard)"), ("s10f_diff_oof_S_s0", "**cross-fitted residuals (shipped)**")]:
        r = res(tag)
        if not r:
            md.append(f"| {name} | {PENDING} |")
            continue
        a = r["test"]["aggregate"]
        md.append(f"| {name} | {css(r):.4f} | {a['precip_crps']:.3f} | {a['precip_ssr']:.2f} | {a['precip_cov90']:.2f} | "
                  f"{a['precip_bias_ratio']:.2f} | {a['precip_csi30']:.3f} |")

    # 4. capacity
    md += ["\n## 4. Capacity under the final recipe (deterministic, H3 N40, 50 ep, 2015–22)\n",
           "| model | params (active) | test CSS | + rain QM | final train loss |", "|---|---|---|---|---|"]
    for tag, name in [("s10cap_S_s0", "dense S"), ("s10cap_M_s0", "dense M"), ("s10cap_L_s0", "dense L"),
                      ("s10f_fin_det_s0", "MoE S, seed 0 (shipped)"), ("s10f_fin_det_s1", "MoE S, seed 1"), ("s10f_fin_det_s2", "MoE S, seed 2")]:
        r = res(tag)
        if not r:
            md.append(f"| {name} | | {PENDING} | | |")
            continue
        pa = f"{r['params_total'] / 1e6:.1f}M ({r['params_active'] / 1e6:.1f}M)" if r.get("params_total") else ""
        hist = r.get("history") or []
        tl = f"{hist[-1]['train_loss']:.3f}" if hist and "train_loss" in hist[-1] else ""
        md.append(f"| {name} | {pa} | {css(r):.4f} | {css(r, True):.4f} | {tl} |")
    md += ["\nMoE train losses include the Switch balance term (0.01 × ≈1 per MoE layer × 3 layers ≈ 0.03), i.e. a data loss",
           "of ≈ 0.027: the MoE and the larger dense models fit the 8 training seasons *better* than dense S, but test skill",
           "is flat within the seed spread (±0.014). Capacity is data-limited at this training-set size, not broken."]

    # 4a. diffusion-denoiser capacity
    md += ["\n## 4a. Diffusion-denoiser capacity (cross-fitted residuals, 80 ep, DPM-Solver++ 24 × 8)\n",
           "Selection evidence = 2022 validation (trained 2015–21, seed 1); 2023 test pairs share the OOF file and seed.\n",
           "| denoiser | params | 2022 val CSS | 2022 val rain CRPS | 2023 test CSS (s1 / s2) | 2023 rain CRPS (s1 / s2) | rain SSR (s1 / s2) |",
           "|---|---|---|---|---|---|---|"]
    for sz, tags in (("S", ["s10f_diff_oof_S_s1", "s10f_diff_oof_S_s2"]), ("M", ["s10dcap_M_s1", "s10dcap_M_s2"]),
                     ("L", ["s10dcap_L_s1", "s10dcap_L_s2"])):
        v = res(f"s10dcap_{sz}_val_s1")
        va = (v or {}).get("val", {}) if v else {}
        vcss = composite_skill(va["aggregate"], va["reference_gfs_bilinear"]["aggregate"]) if va.get("aggregate") else None
        rs = [res(t) for t in tags]
        pr = next((r for r in rs + [v] if r and r.get("params_total")), None)
        md.append(f"| {sz} | {pr['params_total'] / 1e6:.1f}M | " if pr else f"| {sz} | | ")
        md[-1] += (f"{f(vcss, 4)} | {f(va.get('aggregate', {}).get('precip_crps'))} | "
                   + " / ".join(f(css(r), 4) if r else PENDING for r in rs) + " | "
                   + " / ".join(f(r['test']['aggregate']['precip_crps']) if r else PENDING for r in rs) + " | "
                   + " / ".join(f(r['test']['aggregate']['precip_ssr'], 2) if r else PENDING for r in rs) + " |")

    # 4b. calibration
    c = jload("s10-calfit/out/calf/calibration.json")
    md += ["\n## 4b. Calibration: fitted on 2022 (model trained 2015–21), applied to the shipped model on 2023 (24 steps × 8)\n"]
    if c:
        import numpy as np
        al = np.array(c["alpha_spread"])
        md += ["Spread factors (mean over leads) P/Tmax/Tmin/RH/U/V: " + " / ".join(f"{x:.2f}" for x in al.mean(0))
               + f" (range {al.min():.1f}–{al.max():.1f}).\n",
               "| model | variant | CSS | rain CRPS | rain SSR | rain cov90 (ideal 0.70 for K=8) | rain bias | Brier>30 | Tmax CRPS |",
               "|---|---|---|---|---|---|---|---|---|"]
        for grp, label in (("model", "2015–21 model, 2022 (fit season: in-sample for α)"), ("applied", "shipped model, 2023")):
            for v, m in c.get(grp, {}).items():
                md.append(f"| {label} | {v} | {m['css_ensmean']:.4f} | {m['precip_crps']:.3f} | {m['precip_ssr']:.2f} | "
                          f"{m['precip_cov90']:.2f} | {m['precip_bias_ratio']:.2f} | {m['brier30']:.4f} | {m['tmax_crps']:.3f} |")
        md += ["\nSpread calibration lowers rain CRPS (−3 %) and Tmax CRPS (−9 %) with CSS and bias unchanged, but rain",
               "coverage overshoots (0.84 vs ideal 0.70): slightly over-dispersed for rain. Rain QM on the ensemble is not",
               "shipped: it worsens Brier>30 in both seasons and pushes the 2022 bias from 1.22 to 1.36."]
    else:
        md.append(PENDING)

    # 5. modes
    modes = {}
    for t in ("modes_a", "modes_b"):
        m = jload(f"s10-modes/out/{t}/modes.json")
        if m:
            modes[t] = m
    rows = [c for m in modes.values() for c in m["configs"]]

    def find(K, S, cal="spread-calibrated"):
        for c in rows:
            if c["members"] == K and c["steps"] == S and c.get("calibration", cal) == cal:
                return c

    md += ["\n## 5. Operating modes (2023 test)\n",
           "| mode | setting | CSS | rain CRPS | rain SSR | Brier>30 | Tmax CRPS | rain bias | latency s/forecast (T4, batch 1) | peak VRAM GB |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    fast = [c for c in rows if c["members"] == 1]
    spec = [("FAST", "det + rain QM", next((c for c in fast if "QM" in c["mode"]), None)),
            ("FAST (no QM)", "det only", next((c for c in fast if "raw" in c["mode"]), None)),
            ("BALANCED", "16 steps × 8", find(8, 16)), ("ACCURATE", "32 steps × 8", find(8, 32)),
            ("ENSEMBLE", "24 steps × 16", find(16, 24))]
    for name, setting, c in spec:
        if not c:
            md.append(f"| {name} | {setting} | {PENDING} |")
            continue
        a = c["aggregate"]
        md.append(f"| {name} | {setting} | {c['css']:.4f} | {f(a.get('precip_crps'))} | {f(a.get('precip_ssr'), 2)} | "
                  f"{f(a.get('brier30'), 4)} | {f(a.get('tmax_crps'))} | {a['precip_bias_ratio']:.2f} | "
                  f"{c['latency_s_one_forecast']:.2f} | {f(c.get('peak_vram_gb'), 1) if c.get('peak_vram_gb') else ''} |")

    # 6. test-time compute matrix
    md += ["\n## 6. Test-time compute matrix (spread-calibrated; cell = CSS / rain CRPS / latency s)\n"]
    Ks = sorted({c["members"] for c in rows if c["members"] > 1})
    Ss = sorted({c["steps"] for c in rows if c["members"] > 1})
    if Ks:
        md += ["| members \\ steps | " + " | ".join(str(s) for s in Ss) + " |", "|---|" + "---|" * len(Ss)]
        for K in Ks:
            cells = []
            for S in Ss:
                c = find(K, S)
                cells.append(f"{c['css']:.4f} / {c['aggregate']['precip_crps']:.3f} / {c['latency_s_one_forecast']:.1f}" if c else PENDING)
            md.append(f"| K={K} | " + " | ".join(cells) + " |")
        md += ["\nRaw (uncalibrated) vs spread-calibrated rain CRPS / SSR:\n",
               "| K | S | raw CRPS | cal CRPS | raw SSR | cal SSR |", "|---|---|---|---|---|---|"]
        for K in Ks:
            for S in Ss:
                r0, r1 = find(K, S, "raw"), find(K, S)
                if r0 and r1:
                    md.append(f"| {K} | {S} | {r0['aggregate']['precip_crps']:.3f} | {r1['aggregate']['precip_crps']:.3f} | "
                              f"{r0['aggregate'].get('precip_ssr', float('nan')):.2f} | {r1['aggregate'].get('precip_ssr', float('nan')):.2f} |")
    else:
        md.append(PENDING)

    # 7. consistency
    md += ["\n## 7. Multivariate physical consistency (per member; observed = ERA5-Land/CHIRPS targets)\n"]
    obs = next((m["observed_consistency"] for m in modes.values()), None)
    if obs:
        keys = list(obs)
        md += ["| | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys),
               "| observed | " + " | ".join(f"{obs[k]:.3f}" for k in keys) + " |"]
        for name, _, c in spec:
            if c and "consistency" in c:
                md.append(f"| {name} | " + " | ".join(f"{c['consistency']['model'][k]:.3f}" for k in keys) + " |")
    else:
        md.append(PENDING)
    fm = next((m.get("fast_vs_oof_file_maxdiff") for m in modes.values() if "fast_vs_oof_file_maxdiff" in m), None)
    if fm is not None:
        md.append(f"\nArtefact check: FAST output vs the OOF file's 2023 rows, max |diff| = {fm:.4f} (normalised units, fp16).")

    (REPO / "docs" / "final_system_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
