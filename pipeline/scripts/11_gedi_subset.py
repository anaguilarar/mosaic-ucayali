"""Step 11 - GEDI subsetting through NASA Harmony: spatial (bbox) + variable subsets of GEDI02_A,
so full ~1.3 GB granules are never downloaded. Login comes from EARTHDATA_USERNAME/
EARTHDATA_PASSWORD or ~/.netrc (urs.earthdata.nasa.gov) - never written to files or logs.

One Harmony job per calendar month (keeps jobs small and restartable); results land in
<work>/gedi/subsets/<YYYY-MM>/. A month whose directory already holds results is skipped
unless --force. If Harmony rejects the variable subset, the job is retried spatial-only
(bigger files, same shots) and the log says so.

Usage:  python scripts/11_gedi_subset.py [--area pilot|full] [--month YYYY-MM] [--force]
        (no --month: every month in config [gedi] period_start..period_end - the FULL RUN;
         the Phase-1 pilot passes one month)
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

from harmony import BBox, Client, Collection, Request


def month_range(start, end):
    cur = datetime.fromisoformat(start).replace(day=1)
    stop = datetime.fromisoformat(end)
    while cur <= stop:
        yield cur.strftime("%Y-%m")
        cur = cur.replace(year=cur.year + (cur.month == 12), month=cur.month % 12 + 1)


def month_bounds(month):
    y, m = int(month[:4]), int(month[5:])
    nxt = datetime(y + (m == 12), m % 12 + 1, 1)
    return datetime(y, m, 1), nxt


def run_month(client, concept, month, variables):
    outdir = common.WORK / "gedi" / "subsets" / month
    done = outdir / "job.json"
    if done.exists():
        log.info("%s: already subset (%s); --force removes it", month, done)
        return json.loads(done.read_text())
    have = sorted(outdir.glob("*.h5"))
    if have:                 # an earlier run downloaded but crashed before writing job.json
        size_mb = sum(f.stat().st_size for f in have) / 1e6
        info = {"month": month, "job": "recovered", "files": [str(f) for f in have],
                "mb": round(size_mb, 1), "seconds": 0, "variables": True}
        done.write_text(json.dumps(info, indent=1), encoding="utf-8")
        log.info("%s: recovered %d existing files (%.0f MB)", month, len(have), size_mb)
        return info
    outdir.mkdir(parents=True, exist_ok=True)
    w, s, e, n = common.bbox()
    start, stop = month_bounds(month)
    t0 = time.time()
    req = Request(collection=Collection(id=concept), spatial=BBox(w, s, e, n),
                  temporal={"start": start, "stop": stop}, variables=variables)
    if not req.is_valid():
        sys.exit(f"invalid Harmony request: {req.error_messages()}")
    try:
        job = client.submit(req)
    except Exception as err:
        if variables:
            log.warning("%s: variable subset rejected (%s); retrying spatial-only", month, err)
            return run_month(client, concept, month, None)
        raise
    log.info("%s: Harmony job %s submitted, waiting...", month, job)
    client.wait_for_processing(job, show_progress=False)
    futures = client.download_all(job, directory=str(outdir), overwrite=False)
    files = [f.result() if hasattr(f, "result") else str(f) for f in futures]
    dt = time.time() - t0
    size_mb = sum(Path(f).stat().st_size for f in files) / 1e6
    info = {"month": month, "job": str(job), "files": [str(f) for f in files],
            "mb": round(size_mb, 1), "seconds": round(dt), "variables": bool(variables)}
    done.write_text(json.dumps(info, indent=1), encoding="utf-8")
    log.info("%s: %d files, %.0f MB in %.1f min", month, len(files), size_mb, dt / 60)
    return info


def main():
    args = common.setup("11_gedi_subset", extra_args=[
        ("--month", dict(default="", help="one YYYY-MM (pilot); default runs the whole period"))])
    g = common.CFG["gedi"]
    search = common.WORK / "gedi" / "search.json"
    if not search.exists():
        sys.exit("run 10_gedi_search.py first (needs its search.json for the collection id)")
    concept = json.loads(search.read_text())["concept_id"]

    variables = [f"/{b}/{v}" for b in g["beams"] for v in g["variables"]]
    client = Client()                      # auth: env vars or ~/.netrc; nothing logged

    months = [args.month] if args.month else (
        [g["pilot_month"]] if g.get("pilot_month") and common.AREA == "pilot"
        else list(month_range(g["period_start"], g["period_end"])))
    if args.force:
        for m in months:
            j = common.WORK / "gedi" / "subsets" / m / "job.json"
            if j.exists():
                j.unlink()
    total_mb, t0 = 0.0, time.time()
    for m in months:
        info = run_month(client, concept, m, variables)
        total_mb += info["mb"]
    log.info("done: %d month(s), %.0f MB, %.1f min wall", len(months), total_mb, (time.time() - t0) / 60)


if __name__ == "__main__":
    main()
