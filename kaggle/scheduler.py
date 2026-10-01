"""
Autonomous overnight scheduler.

* kaggle/queue.json holds job specs {name, account|None, lanes, expected_min, sprint, kernel_sources, needs}.
* Every 2 min: refresh job states, download finished results, retry failed jobs once, and launch pending
  jobs whose dependencies are complete onto accounts with a free slot (MAX_PER_ACCOUNT sessions each).
* Planner hooks append dependent phases automatically:
    - Phase A complete -> pick H*, N* (scripts/summarize.py rules) -> Sprint 6 (det + diffusion) and
      Sprint 9 (dense M/L, MoE grid) at (H*, N*)
    - Sprint 6 diffusion complete -> Sprint 7/8 evaluation jobs
* Every action is appended to kaggle/scheduler.log and decisions to docs/decision_log.md.
Run:  python kaggle/scheduler.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dashboard import FINAL, STATUS, load, refresh, render  # noqa: E402
from launch import REGISTRY, REPO, USERS  # noqa: E402

QUEUE = REPO / "kaggle" / "queue.json"
LOG = REPO / "kaggle" / "scheduler.log"
DLOG = REPO / "docs" / "decision_log.md"
STATE = REPO / "kaggle" / "scheduler_state.json"
MAX_PER_ACCOUNT = 2
IST = timezone(timedelta(hours=5, minutes=30))
S_ARGS = "--mode det --size S --epochs 50 --time_budget_min 55 --patience 10"


def now():
    return datetime.now(IST).strftime("%H:%M")


def log(msg):
    line = f"{datetime.now(IST):%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def decide(msg, why):
    with open(DLOG, "a", encoding="utf-8") as f:
        f.write(f"| {now()} | {msg} | {why} |\n")
    log(f"DECISION {msg} -- {why}")


def save(q):
    QUEUE.write_text(json.dumps(q, indent=1))


def job_state(name, status, reg):
    """latest registry entry for this job name -> (status, entry)"""
    es = [e for e in reg if e["name"] == name]
    if not es:
        return None, None
    e = max(es, key=lambda x: x["launched_utc"])
    st = status.get(f"{e['name']}@{e['launched_utc']:.0f}", {}).get("status", e["status"])
    return st, e


def tag_owner(tag, reg):
    """(account, slug) of the job whose lanes produced run `tag`."""
    for e in sorted(reg, key=lambda x: -x["launched_utc"]):
        if any(f"--tag {tag}" in c for lane in e["lanes"] for c in lane):
            return e["account"], e["slug"]
    return None, None


def launch(job):
    cmd = [sys.executable, str(REPO / "kaggle" / "launch.py"), "--account", job["account"], "--name", job["name"],
           "--expected_min", str(job["expected_min"]), "--sprint", job.get("sprint", "")]
    for lane in job["lanes"]:
        cmd += ["--lane", *lane]
    if job.get("kernel_sources"):
        cmd += ["--kernel_sources", *job["kernel_sources"]]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    ok = r.returncode == 0
    log(f"LAUNCH {job['name']} on {job['account']} -> {'ok' if ok else 'FAILED ' + (r.stdout + r.stderr)[-300:]}")
    return ok


def summarize():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "summarize.py")], capture_output=True, text=True,
                       cwd=REPO, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    m = re.search(r"WINNERS (\{.*\})", r.stdout)
    return eval(m.group(1)) if m else {}


# ------------------------------------------------------------------------------- planners
def plan_phase_bc(q, reg, st):
    w = summarize()
    h_cfg, n_cfg, l_cfg = w.get("Sprint 4"), w.get("Sprint 5"), w.get("Sprint 3")
    H = int(re.search(r"_h(\d+)", h_cfg).group(1)) if h_cfg else 7
    N = int(re.search(r"_n(\d+)", n_cfg).group(1)) if n_cfg else 16
    lin = bool(l_cfg and l_cfg.startswith("lin_"))
    extra = " --precip_lin_w 1.0" if lin else ""
    decide(f"H* = {H}, N* = {N} (N/M = {N / 16:.2f}), precip mm-loss = {lin}",
           f"Sprint 4 winner {h_cfg}, Sprint 5 winner {n_cfg}, Sprint 3 winner {l_cfg} (seed-mean val CSS, ties to cheaper)")
    st.update(H=H, N=N, lin=lin)
    base = f"--H {H} --N {N}{extra}"
    # Sprint 6: deterministic at (H*,N*) -- reuse a Phase A run if one matches exactly, else train it.
    cand = f"s4_h{H}_n16" if N == 16 else (f"s5_h7_n{N}" if H == 7 else None)
    if lin:
        cand = None
    own0 = tag_owner(f"{cand}_s0", reg) if cand else (None, None)
    if cand and own0[0]:
        det_tag, det_acct, det_job = f"{cand}_s0", own0[0], None
        decide(f"S6 deterministic = existing {cand}_s0", "already trained at (H*, N*)")
    else:
        det_tag, det_acct, det_job = "s6_det_s0", "a1", "b-s6-det"
        q.append({"name": det_job, "account": det_acct, "sprint": "S6", "expected_min": 65, "needs": [],
                  "lanes": [[f"{S_ARGS} {base} --seed 0 --tag s6_det_s0"], [f"{S_ARGS} {base} --seed 1 --tag s6_det_s1"]]})
    det_src = [tag_owner(det_tag, reg)[1]] if det_job is None else ["sih26074-v3-" + det_job]
    D = f"--mode diff --size S --epochs 40 --time_budget_min 80 --patience 8 {base} --det_ckpt **/{det_tag}/best.pt"
    q.append({"name": "b-s6-diff", "account": det_acct, "sprint": "S6", "expected_min": 120,
              "needs": [det_job] if det_job else [], "kernel_sources": det_src,
              "lanes": [[f"{D} --seed 0 --tag s6_diff_s0"], [f"{D} --seed 1 --tag s6_diff_s1"]]})
    # Sprint 9: capacity ladder + MoE at (H*, N*)  (S rows come from Sprint 6 det / Phase A)
    M = f"--mode det --size M --epochs 50 --time_budget_min 85 --patience 10 {base}"
    L_ = f"--mode det --size L --epochs 50 --time_budget_min 115 --patience 10 {base}"
    q.append({"name": "c-s9-M", "account": None, "sprint": "S9", "expected_min": 95, "needs": [],
              "lanes": [[f"{M} --seed 0 --tag s9_dense_M_s0"], [f"{M} --seed 1 --tag s9_dense_M_s1"]]})
    q.append({"name": "c-s9-L", "account": None, "sprint": "S9", "expected_min": 125, "needs": [],
              "lanes": [[f"{L_} --seed 0 --tag s9_dense_L_s0"], [f"{L_} --seed 1 --tag s9_dense_L_s1"]]})
    moe = [(4, 1, 0.5), (8, 1, 0.5), (16, 1, 0.5), (4, 2, 0.5), (8, 2, 0.5), (16, 2, 0.5), (8, 1, 0.25), (8, 1, 1.0)]
    for e, k, fr in moe:
        tag = f"s9_moe_e{e}k{k}f{int(fr * 100)}"
        A = f"{S_ARGS.replace('--time_budget_min 55', '--time_budget_min 70')} {base} --moe_experts {e} --moe_topk {k} --moe_frac {fr}"
        q.append({"name": f"c-{tag.replace('_', '-')}", "account": None, "sprint": "S9", "expected_min": 80, "needs": [],
                  "lanes": [[f"{A} --seed 0 --tag {tag}_s0"], [f"{A} --seed 1 --tag {tag}_s1"]]})
    q.append({"planner": "phase_d", "needs": ["b-s6-diff"]})
    log(f"PLANNED Phase B/C: {sum(1 for j in q if j.get('name', '').startswith(('b-', 'c-')))} jobs")


def plan_phase_d(q, reg, st):
    acct = next(j["account"] for j in q if j.get("name") == "b-s6-diff")
    det_tag = next(c for j in q if j.get("name") == "b-s6-diff" for c in j["lanes"][0]).split("**/")[1].split("/")[0]
    srcs = sorted({tag_owner(det_tag, reg)[1], tag_owner("s6_diff_s0", reg)[1]})
    E = f"--diff_ckpt **/s6_diff_s0/best.pt --det_ckpt **/{det_tag}/best.pt"
    for study, parts, exp in (("s7", 4, 110), ("s8", 2, 110)):
        for p in range(0, parts, 2):
            q.append({"name": f"d-{study}-p{p}", "account": acct, "sprint": study.upper(), "expected_min": exp,
                      "needs": [], "kernel_sources": srcs, "module": "eval_diff",
                      "lanes": [[f"{E} --study {study} --part {p} --nparts {parts} --tag {study}_p{p}"],
                                [f"{E} --study {study} --part {p + 1} --nparts {parts} --tag {study}_p{p + 1}"]]})
    decide(f"Sprint 7/8 evaluation on s6_diff_s0 (det {det_tag})", "diffusion seed 0 trained; seed 1 kept for training-noise check")
    log("PLANNED Phase D")


PLANNERS = {"phase_bc": plan_phase_bc, "phase_d": plan_phase_d}


# ------------------------------------------------------------------------------- main loop
def main():
    st = load(STATE, {})
    status = load(STATUS, {})
    quota = {}
    log("scheduler started")
    while True:
        try:
            refresh(status, quota)
            reg = load(REGISTRY, [])
            q = load(QUEUE, [])
            done = {j["name"] for j in q if j.get("name") and "complete" in (job_state(j["name"], status, reg)[0] or "")}
            # retries + bookkeeping
            for j in q:
                if not j.get("name") or j.get("state") != "launched":
                    continue
                s, _ = job_state(j["name"], status, reg)
                if s and ("error" in s or "cancel" in s or s == "push_failed"):
                    if j.get("retries", 0) < 1:
                        j["retries"] = j.get("retries", 0) + 1
                        j["state"] = "pending"
                        log(f"RETRY {j['name']} after status {s}")
                    else:
                        j["state"] = "failed"
                        log(f"GAVE UP {j['name']} after status {s}")
                elif s and "complete" in s and j["state"] != "done":
                    j["state"] = "done"
                    log(f"DONE {j['name']}")
            # planners whose needs are met
            for j in list(q):
                if j.get("planner") and not j.get("planned") and all(n in done for n in j["needs"]):
                    j["planned"] = True
                    PLANNERS[j["planner"]](q, reg, st)
            # launches
            running = {a: 0 for a in USERS}
            for e in reg:
                s = status.get(f"{e['name']}@{e['launched_utc']:.0f}", {}).get("status", e["status"])
                if not any(f in s for f in FINAL) and s != "push_failed":
                    running[e["account"]] += 1
            for j in q:
                if not j.get("name") or j.get("state", "pending") != "pending":
                    continue
                if not all(n in done for n in j.get("needs", [])):
                    continue
                accts = [j["account"]] if j.get("account") else sorted(USERS, key=lambda a: running[a])
                acct = next((a for a in accts if running[a] < MAX_PER_ACCOUNT), None)
                if acct is None:
                    continue
                j["account"] = acct
                if j.get("module"):
                    j["lanes"] = [[f"@{j['module']} {c}" for c in lane] for lane in j["lanes"]]
                    j.pop("module")
                if launch(j):
                    j["state"] = "launched"
                    running[acct] += 1
                else:
                    j["retries"] = j.get("retries", 0) + 1
                    if j["retries"] > 2:
                        j["state"] = "failed"
            save(q)
            STATE.write_text(json.dumps(st))
            STATUS.write_text(json.dumps(status, indent=1))
            pend = sum(1 for j in q if j.get("name") and j.get("state", "pending") == "pending")
            tail = LOG.read_text(encoding="utf-8").splitlines()[-8:] if LOG.exists() else []
            nl = chr(10)
            screen = (render(status, quota) + nl * 2 + f"queued (waiting for slot/dependency): {pend}" + nl * 2
                      + "recent scheduler events:" + nl + nl.join(tail) + nl)
            sys.stdout.write(chr(27) + "[2J" + chr(27) + "[H" + screen)
            sys.stdout.flush()
        except Exception:
            log("ERROR " + traceback.format_exc()[-800:])
        time.sleep(120)


if __name__ == "__main__":
    main()
