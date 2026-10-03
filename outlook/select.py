"""
Choose, per target, which validated forecast the system ships, by a rule fixed before the final run:

  candidates  outlook   sub-seasonal model (climatology, recent rain, real-time MJO/BSISO, ENSO, IOD), 43-season CV
              v3        + the v3 deep downscaling model's week-1 forecast (week-1 targets), 9-season LOSO
              gfs       + GFS days 1-16 and v3 week 1 (weeks 1-2 targets), 9-season LOSO
  rule        a hybrid replaces the outlook only if, on the same 2015-2023 rows, its Brier skill beats the outlook's
              AND the lower end of its 90 % season-bootstrap interval is above zero; the best such hybrid wins.

  python -m outlook.select  -> outlook/results/final_selection.json
"""
from __future__ import annotations

import json
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "outlook" / "results"


def main():
    cv = json.load(open(RES / "cv_metrics.json"))
    cands = {"v3": json.load(open(RES / "stack_week1_metrics.json")), "gfs": json.load(open(RES / "stack_metrics.json"))}
    out = {}
    for t, m in cv.items():
        best = {"source": "outlook", "bss": m["bss"], "ci90": m["ci90"], "seasons": "1981-2023 (season-blocked CV)"}
        pick = None
        for name, cm in cands.items():
            c = cm.get(t)
            if not c:
                continue
            if c["bss_stacked"] > c["bss_outlook"] and c["ci90_stacked"][0] > 0:
                if pick is None or c["bss_stacked"] > pick[1]["bss_stacked"]:
                    pick = (name, c)
        if pick:
            best = {"source": pick[0], "bss": pick[1]["bss_stacked"], "ci90": pick[1]["ci90_stacked"],
                    "outlook_bss_same_rows": pick[1]["bss_outlook"], "seasons": pick[1]["seasons"]}
        out[t] = best
        print(f"{t:9s} -> {best['source']:7s} BSS {best['bss']:+.3f} [{best['ci90'][0]:+.3f}, {best['ci90'][1]:+.3f}]")
    json.dump(out, open(RES / "final_selection.json", "w"), indent=1)


if __name__ == "__main__":
    main()
