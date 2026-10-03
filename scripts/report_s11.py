"""Sprint 11 results -> docs/results_s11.md: history length x forecast history (selection on 2022, test 2023
reported), post-training improvements (seed averaging, probability-matched mean, rain tail cap) and the
averaged-residual denoiser."""
import glob
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from sihv3.metrics import composite_skill  # noqa: E402


def res(tag):
    f = glob.glob(str(REPO / "results" / "*" / "out" / tag / "result.json"))
    return json.load(open(f[0])) if f else None


def css(r, sp):
    a = r[sp]
    return composite_skill(a["aggregate"], a["reference_gfs_bilinear"]["aggregate"])


def ms(v):
    v = [x for x in v if x is not None]
    if not v:
        return "_pending_"
    return f"{np.mean(v):.4f} ± {np.std(v, ddof=1):.4f} (n={len(v)})" if len(v) > 1 else f"{v[0]:.4f} (n=1)"


def main():
    md = ["# Sprint 11 — history, forecast history and post-training improvements\n",
          "Selection season 2022 (models trained 2015–2021); 2023 test reported only. Recipe = the shipped deterministic",
          "backbone (MoE S, E8 top-2 50 %, N/M 2.5, no mm-loss, 50 epochs). Means ± seed SD over seeds 0–2.\n",
          "## 1. History length H × forecast history\n",
          "`obs` = observed ERA5 history only (as shipped); `+fc` = observed history plus the GFS forecast that was valid",
          "on each history day (from the run issued that day), i.e. GFS's recent errors are visible to the model.\n",
          "| H | input | 2022 val CSS | 2023 test CSS | 2022 Tmax MAE | 2022 rain CSI30 | paired Δ(+fc − obs) 2022 |",
          "|---|---|---|---|---|---|---|"]
    best = {}
    for H in (3, 5, 7, 10, 14):
        per = {}
        for kind in ("obs", "fc"):
            rs = [res(f"s11_h{H}_{kind}_s{s}") for s in range(3)]
            per[kind] = rs
            v = [css(r, "val") if r else None for r in rs]
            t = [css(r, "test") if r else None for r in rs]
            tm = [r["val"]["aggregate"]["tmax_mae"] if r else None for r in rs]
            c30 = [r["val"]["aggregate"]["precip_csi30"] if r else None for r in rs]
            best[(H, kind)] = [x for x in v if x is not None]
            dd = ""
            if kind == "fc":
                d = [css(f, "val") - css(o, "val") for o, f in zip(per["obs"], per["fc"]) if o and f]
                if d:
                    se = np.std(d, ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
                    dd = f"{np.mean(d):+.4f} (SE {se:.4f}, n={len(d)})"
            tmv = [x for x in tm if x is not None]
            c3v = [x for x in c30 if x is not None]
            md.append(f"| {H} | {'obs + fc' if kind == 'fc' else 'obs'} | {ms(v)} | {ms(t)} | "
                      f"{np.mean(tmv):.3f} | {np.mean(c3v):.3f} | {dd} |" if tmv else
                      f"| {H} | {'obs + fc' if kind == 'fc' else 'obs'} | _pending_ | | | | |")
    md += ["", "## 2. Post-training improvements on the shipped model (s11-post, s11-post2)\n"]
    for job, tags in (("s11-post", ("post22", "post23")), ("s11-post2", ("post22b", "post23b"))):
        for t in tags:
            f = glob.glob(str(REPO / "results" / job / "out" / t / "post.json"))
            if not f:
                continue
            r = json.load(open(f[0]))
            md += [f"\n**{t}** (season {r['eval_year']})\n", "| variant | CSS | rain CRPS | rain SSR | Brier>30 | CSI30 | CSI64.5 | POD64.5 | rain bias |",
                   "|---|---|---|---|---|---|---|---|---|"]
            for row in r["rows"]:
                a = row["aggregate"]
                g = lambda k, d=3: f"{a[k]:.{d}f}" if k in a else "–"
                md.append(f"| {row['variant']} | {row['css']:.4f} | {g('precip_crps')} | {g('precip_ssr', 2)} | {g('brier30', 4)} | "
                          f"{g('precip_csi30')} | {g('precip_csi64.5')} | {g('precip_pod64.5', 2)} | {g('precip_bias_ratio', 2)} |")
            if "member_tails" in r:
                md.append("\nMember rain tails on land (mm/day): " + "; ".join(
                    f"{k}: p99 {v['0.99']:.0f}, p99.9 {v['0.999']:.0f}, p99.99 {v['0.9999']:.0f}, max {v['max']:.0f}, "
                    f"above training block max {100 * v['frac_above_cap']:.3f} %" for k, v in r["member_tails"].items()))
    md += ["", "## 3. Denoiser trained on the 3-seed averaged backbone (s11-davg)\n",
           "| denoiser trained on | 2022 val CSS | 2022 rain CRPS | 2023 CSS | 2023 rain CRPS |", "|---|---|---|---|---|"]
    for name, cal, fin in (("single-seed residuals (shipped)", "s10f_diff_oof_S_cal_s0", "s10f_diff_oof_S_s0"),
                           ("3-seed averaged residuals", "s11_diff_avg3_cal_s0", "s11_diff_avg3_s0")):
        c, f = res(cal), res(fin)
        if c and f:
            md.append(f"| {name} | {css(c, 'val'):.4f} | {c['val']['aggregate']['precip_crps']:.3f} | {css(f, 'test'):.4f} | "
                      f"{f['test']['aggregate']['precip_crps']:.3f} |")
    (REPO / "docs" / "results_s11.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
