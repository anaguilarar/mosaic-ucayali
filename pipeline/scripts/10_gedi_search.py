"""Step 10 - GEDI granule search (CMR via earthaccess; no download, no login needed for search).

Writes <work>/gedi/search.json: the collection concept-id and, per granule, name, size and time.
--pick-month prints granule counts per calendar month (over the configured period) and suggests
the best pilot month; put it in config [gedi].pilot_month or pass --month to step 11.

Usage:  python scripts/10_gedi_search.py [--area pilot|full] [--month YYYY-MM] [--pick-month]
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import earthaccess


def search(bbox, start, end):
    return earthaccess.search_data(short_name=common.CFG["gedi"]["product"],
                                   version=common.CFG["gedi"]["version"],
                                   bounding_box=tuple(bbox),
                                   temporal=(start, end))


def main():
    args = common.setup("10_gedi_search", extra_args=[
        ("--month", dict(default="", help="limit to one YYYY-MM")),
        ("--pick-month", dict(action="store_true", help="rank months by granule count"))])
    g = common.CFG["gedi"]
    start, end = g["period_start"], g["period_end"]
    if args.month:
        y, m = args.month.split("-")
        start = f"{y}-{m}-01"
        end = f"{y}-{int(m):02d}-28" if m == "02" else f"{y}-{m}-{30 if m in ('04','06','09','11') else 31}"

    cols = earthaccess.search_datasets(short_name=g["product"], version=g["version"])
    cid = cols[0].concept_id
    concept = cid() if callable(cid) else cid
    log.info("collection %s v%s -> %s", g["product"], g["version"], concept)

    granules = search(common.bbox(), start, end)
    val = (lambda x: x() if callable(x) else x)      # earthaccess exposes size/concept_id as either
    sizes = [float(val(gr.size)) for gr in granules]
    log.info("%d granules, %.1f GB total (mean %.0f MB)", len(granules), sum(sizes) / 1e3,
             (sum(sizes) / max(len(sizes), 1)))

    if args.pick_month:
        months = Counter(gr["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:7]
                         for gr in granules)
        for mo, n in sorted(months.items()):
            log.info("  %s: %d granules", mo, n)
        best = max(months, key=months.get)
        log.info("suggested pilot month: %s (%d granules) -> config [gedi].pilot_month", best, months[best])

    out = common.WORK / "gedi"
    out.mkdir(parents=True, exist_ok=True)
    doc = {"concept_id": concept, "bbox": list(common.bbox()), "start": start, "end": end,
           "granules": [{"name": gr["umm"]["GranuleUR"], "mb": float(val(gr.size)),
                         "begin": gr["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]}
                        for gr in granules]}
    (out / "search.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    log.info("wrote %s", out / "search.json")


if __name__ == "__main__":
    main()
