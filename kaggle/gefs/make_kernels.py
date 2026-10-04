"""Kaggle CPU kernels: GEFSv12 reforecast (NOAA, AWS noaa-gefs-retrospective) daily precipitation, days 1-35, over a
Mandya box, for every Wednesday 00Z init (the 11-member 35-day runs) from 24 Apr to 30 Sep of one year (2000-2019).

  days 1-10 : 0.25 deg, file Days:1-10/apcp_sfc_<init>_<mem>.grib2   (6-h buckets used; 3-h ones skipped)
  days 11-35: 0.5 deg,  file Days:10-35/apcp_sfc_<init>_<mem>.grib2  (6-h buckets)
Output gefs35_<year>.npz {inits, members, lat25, lon25, pr10 [n, m, 10, lat, lon], lat50, lon50, pr35 [n, m, 25, lat, lon]} mm/day

  python kaggle/gefs/make_kernels.py <user> <years,comma> [tag]     -> kaggle/gefs/runs/<tag><year>/
  python kaggle/gefs/make_kernels.py test                           -> decode one init/member locally
"""
import json
import sys
from pathlib import Path

SCRIPT = r'''
import os, sys, time, json, numpy as np, requests
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
YEAR = {year}
MEMBERS = {members}
ONLY = {only}
N, S, E, W = 14.0, 11.0, 78.5, 75.0                    # Mandya box + margin for bilinear on the 0.5 deg grid
OUT = "{out}"; os.makedirs(OUT, exist_ok=True)
BASE = "https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast"
try:
    import eccodes; eccodes.codes_get_api_version()
except Exception:
    for pk in (["eccodes"], ["eccodes", "ecmwflibs"]):
        os.system(f"{{sys.executable}} -m pip install -q {{' '.join(pk)}} 2>&1 | tail -1")
        try:
            import eccodes; eccodes.codes_get_api_version(); break
        except Exception as e:
            print("eccodes not ready", e, flush=True)
import eccodes
sess = requests.Session()
def get(url, tries=6):
    last = None
    for k in range(tries):
        try:
            r = sess.get(url, timeout=120)
            if r.status_code == 200:
                return r
            last = f"HTTP {{r.status_code}}"
            if r.status_code in (403, 404):
                break
        except Exception as e:
            last = repr(e)
        time.sleep(2 + 3 * k)
    raise RuntimeError(f"{{url}}: {{last}}")
def buckets(url):
    """-> {{end_hour: cropped 6-h total}}, lat, lon"""
    idx = get(url + ".idx").text.strip().split("\n")
    buf = get(url).content
    offs = [int(l.split(":")[1]) for l in idx] + [len(buf)]
    out, lat, lon = {{}}, None, None
    for k, l in enumerate(idx):
        rng = l.split(":")[5]                                         # e.g. "234-240 hour acc fcst"
        a, b = (int(x) for x in rng.split(" ")[0].split("-"))
        if b - a != 6:
            continue
        gid = eccodes.codes_new_from_message(buf[offs[k]:offs[k + 1]])
        try:
            ni, nj = eccodes.codes_get(gid, "Ni"), eccodes.codes_get(gid, "Nj")
            la0 = eccodes.codes_get(gid, "latitudeOfFirstGridPointInDegrees")
            lo0 = eccodes.codes_get(gid, "longitudeOfFirstGridPointInDegrees")
            di = eccodes.codes_get(gid, "iDirectionIncrementInDegrees")
            dj = eccodes.codes_get(gid, "jDirectionIncrementInDegrees")
            sc = eccodes.codes_get(gid, "jScansPositively")
            v = eccodes.codes_get_values(gid).reshape(nj, ni)
        finally:
            eccodes.codes_release(gid)
        la = la0 + (dj if sc else -dj) * np.arange(nj); lo = (lo0 + di * np.arange(ni)) % 360
        ri = np.where((la >= S - 1e-6) & (la <= N + 1e-6))[0]; ci = np.where((lo >= W - 1e-6) & (lo <= E + 1e-6))[0]
        ri = ri[np.argsort(-la[ri])]                                  # latitude descending
        out[b] = v[np.ix_(ri, ci)].astype(np.float32)
        lat, lon = la[ri], lo[ci]
    return out, lat, lon
def daily(bk, d0, nd):
    """6-h buckets -> daily totals for forecast days d0+1 .. d0+nd (bucket ending at h belongs to day ceil(h/24))."""
    ks = sorted(bk); shp = bk[ks[0]].shape
    D = np.zeros((nd,) + shp, np.float32); cnt = np.zeros(nd, int)
    for h in ks:
        d = (h - 1) // 24 - d0
        if 0 <= d < nd:
            D[d] += np.maximum(bk[h], 0); cnt[d] += 1
    assert (cnt == 4).all(), f"incomplete days {{cnt.tolist()}}"
    return D
OPS = "https://noaa-gefs-pds.s3.amazonaws.com"
def ops_bucket(url, h, res):
    """operational GEFS (2021+): one 6-h APCP message ending at lead h, by byte range from the .idx"""
    lines = get(url + ".idx").text.strip().split("\n")
    for k, l in enumerate(lines):
        q = l.split(":")
        if q[3] == "APCP" and q[5].startswith(f"{{h - 6}}-{{h}} hour"):
            a = int(q[1]); b = int(lines[k + 1].split(":")[1]) - 1 if k + 1 < len(lines) else ""
            r = sess.get(url, headers={{"Range": f"bytes={{a}}-{{b}}"}}, timeout=120)
            if r.status_code not in (200, 206):
                raise RuntimeError(f"{{url}} HTTP {{r.status_code}}")
            res[h] = r.content
            return
    raise RuntimeError(f"no 6-h APCP at f{{h:03d}} {{url}}")
def decode_msgs(msgs):
    out, lat, lon = {{}}, None, None
    for h, m in msgs.items():
        gid = eccodes.codes_new_from_message(m)
        try:
            ni, nj = eccodes.codes_get(gid, "Ni"), eccodes.codes_get(gid, "Nj")
            la0 = eccodes.codes_get(gid, "latitudeOfFirstGridPointInDegrees")
            lo0 = eccodes.codes_get(gid, "longitudeOfFirstGridPointInDegrees")
            di = eccodes.codes_get(gid, "iDirectionIncrementInDegrees")
            dj = eccodes.codes_get(gid, "jDirectionIncrementInDegrees")
            sc = eccodes.codes_get(gid, "jScansPositively")
            v = eccodes.codes_get_values(gid).reshape(nj, ni)
        finally:
            eccodes.codes_release(gid)
        la = la0 + (dj if sc else -dj) * np.arange(nj); lo = (lo0 + di * np.arange(ni)) % 360
        ri = np.where((la >= S - 1e-6) & (la <= N + 1e-6))[0]; ci = np.where((lo >= W - 1e-6) & (lo <= E + 1e-6))[0]
        ri = ri[np.argsort(-la[ri])]
        out[h] = v[np.ix_(ri, ci)].astype(np.float32); lat, lon = la[ri], lo[ci]
    return out, lat, lon
def one_ops(init, mem):
    m = "gec00" if mem == "c00" else "gep" + mem[1:]
    base = f"{{OPS}}/gefs.{{init:%Y%m%d}}/00/atmos"
    r25, r50 = {{}}, {{}}
    for h in range(6, 241, 6):
        ops_bucket(f"{{base}}/pgrb2sp25/{{m}}.t00z.pgrb2s.0p25.f{{h:03d}}", h, r25)
    for h in range(246, 841, 6):
        ops_bucket(f"{{base}}/pgrb2ap5/{{m}}.t00z.pgrb2a.0p50.f{{h:03d}}", h, r50)
    a, la25, lo25 = decode_msgs(r25); b, la50, lo50 = decode_msgs(r50)
    return daily(a, 0, 10), daily(b, 10, 25), (la25, lo25, la50, lo50)
def one(job):
    init, mem = job
    if init.year >= 2021:
        return one_ops(init, mem)
    tag = init.strftime("%Y%m%d") + "00"
    u = f"{{BASE}}/{{init.year}}/{{tag}}/{{mem}}"
    a, la25, lo25 = buckets(f"{{u}}/Days:1-10/apcp_sfc_{{tag}}_{{mem}}.grib2")
    b, la50, lo50 = buckets(f"{{u}}/Days:10-35/apcp_sfc_{{tag}}_{{mem}}.grib2")
    return daily(a, 0, 10), daily(b, 10, 25), (la25, lo25, la50, lo50)
inits = []
d = date(YEAR, 4, 24)
while d.weekday() != 2:
    d += timedelta(days=1)
while d <= date(YEAR, 9, 30):
    inits.append(d); d += timedelta(days=7)
if ONLY:
    inits = inits[:1]
jobs = [(i, m) for i in inits for m in MEMBERS]
t0, res, bad = time.time(), {{}}, []
def run(j):
    try:
        return j, one(j)
    except Exception as e:
        return j, e
with ThreadPoolExecutor(6 if YEAR < 2021 else 16) as ex:
    for n, (j, v) in enumerate(ex.map(run, jobs), 1):
        if isinstance(v, Exception):
            bad.append((j[0].isoformat(), j[1], repr(v)[:200]))
        else:
            res[j] = v
        if n % 11 == 0 or n == len(jobs):
            el = time.time() - t0
            print(f"{{n}}/{{len(jobs)}} bad={{len(bad)}} | {{el/60:.1f}} min | ETA {{el/n*(len(jobs)-n)/60:.1f}} min", flush=True)
g = next(iter(res.values()))[2]
ok_inits = [i for i in inits if all((i, m) in res for m in MEMBERS)]
pr10 = np.stack([np.stack([res[(i, m)][0] for m in MEMBERS]) for i in ok_inits]).astype(np.float16)
pr35 = np.stack([np.stack([res[(i, m)][1] for m in MEMBERS]) for i in ok_inits]).astype(np.float16)
np.savez_compressed(f"{{OUT}}/gefs35_{{YEAR}}.npz", inits=np.array([i.isoformat() for i in ok_inits]), members=np.array(MEMBERS),
                    lat25=g[0], lon25=g[1], lat50=g[2], lon50=g[3], pr10=pr10, pr35=pr35)
json.dump({{"inits": len(inits), "ok": len(ok_inits), "bad": bad, "min": (time.time() - t0) / 60}}, open(f"{{OUT}}/log_{{YEAR}}.json", "w"), indent=1)
print("DONE", len(ok_inits), "of", len(inits), "inits | bad", len(bad), flush=True)
'''

MEMBERS = ["c00"] + [f"p{k:02d}" for k in range(1, 11)]


def main(user, years, tag):
    for y in years:
        d = Path(__file__).parent / "runs" / f"{tag}{y}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "job.py").write_text(SCRIPT.format(year=y, members=repr(MEMBERS), only="False", out="/kaggle/working/gefs"))
        slug = f"sih26074-gefs35-{y}"
        meta = {"id": f"{user}/{slug}", "title": slug, "code_file": "job.py", "language": "python",
                "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_tpu": False, "enable_internet": True,
                "dataset_sources": [], "competition_sources": [], "kernel_sources": []}
        (d / "kernel-metadata.json").write_text(json.dumps(meta, indent=1))
        print("prepared", d)


if __name__ == "__main__":
    if sys.argv[1] == "test":
        out = Path(sys.argv[2])
        yr = int(sys.argv[3]) if len(sys.argv) > 3 else 2015
        (out / "job.py").write_text(SCRIPT.format(year=yr, members=repr(["c00"]), only="True", out=str(out).replace("\\", "/")))
        print("wrote", out / "job.py")
    else:
        main(sys.argv[1], [int(x) for x in sys.argv[2].split(",")], sys.argv[3] if len(sys.argv) > 3 else "")
