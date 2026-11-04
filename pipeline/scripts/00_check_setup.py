"""Step 00 - check the machine is ready: config, packages, credentials (presence only, never values),
inputs with the expected CRS/extent, tool paths and free disk. Stops with a clear message on the
first problem; exits 0 when everything a run needs is in place.

Usage:  python scripts/00_check_setup.py [--area pilot|full]
"""
import importlib
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

problems = []
say = print


def need(cond, ok_msg, bad_msg):
    if cond:
        say(f"  ok   {ok_msg}")
    else:
        say(f"  FAIL {bad_msg}")
        problems.append(bad_msg)


# ---- config (common.py exits with its own message if config.toml is missing)
import common  # noqa: E402
args = common.setup("00_check_setup")
cfg = common.CFG
say("config: " + str(common.CONFIG_PATH))

# ---- packages
say("packages:")
for mod in ["rasterio", "geopandas", "shapely", "mercantile", "PIL", "pmtiles", "scipy",
            "psutil", "numpy", "pandas", "pyarrow", "h5py", "earthaccess", "harmony", "duckdb"]:
    try:
        importlib.import_module(mod)
        say(f"  ok   {mod}")
    except ImportError:
        problems.append(f"python package missing: {mod} (see pipeline/environment.yml)")
        say(f"  FAIL {mod} missing")

# ---- credentials: presence only, values never read into variables we print
say("credentials (GEDI steps only):")
has_env = bool(os.environ.get("EARTHDATA_USERNAME")) and bool(os.environ.get("EARTHDATA_PASSWORD"))
has_netrc = False
import netrc  # noqa: E402
for f in ("~/.netrc", "~/_netrc"):
    try:
        if "urs.earthdata.nasa.gov" in netrc.netrc(os.path.expanduser(f)).hosts:
            has_netrc = True
    except (FileNotFoundError, netrc.NetrcParseError):
        pass
need(has_env or has_netrc,
     "Earthdata login found (" + ("env vars" if has_env else "~/.netrc") + ")",
     "no Earthdata login: set EARTHDATA_USERNAME/EARTHDATA_PASSWORD or add urs.earthdata.nasa.gov "
     "to ~/.netrc (see ACCESS.md). Steps 00-05 run without it.")

# ---- inputs
say("inputs:")
import rasterio  # noqa: E402
import geopandas as gpd  # noqa: E402

EXPECT = {"crs": "EPSG:4326", "size": (20237, 15535)}
for key in ("dem", "s2_mosaic"):
    p = common.INPUTS / cfg["inputs"][key]
    if not p.exists():
        need(False, "", f"missing input: {p}")
        continue
    with rasterio.open(p) as r:
        ok = str(r.crs) == EXPECT["crs"] and (r.width, r.height) == EXPECT["size"]
        need(ok, f"{p.name}: {r.crs}, {r.width}x{r.height}, {r.count} band(s)",
             f"{p.name}: unexpected grid {r.crs} {r.width}x{r.height} (expected {EXPECT})")

for key in ("department", "departments_all"):
    p = common.INPUTS / cfg["inputs"][key]
    if not p.exists():
        need(False, "", f"missing input: {p}")
        continue
    g = gpd.read_file(p)
    need(str(g.crs) == "EPSG:4326", f"{p.name}: {len(g)} feature(s), {g.crs}",
         f"{p.name}: CRS {g.crs}, expected EPSG:4326")

p = common.COOLEY / cfg["inputs"]["cooley_geojson"]
if p.exists():
    g = gpd.read_file(p)
    need(len(g) == 324, f"{p.name}: {len(g)} polygons",
         f"{p.name}: {len(g)} polygons, expected 324 (dataset v4, doi:10.22002/D1.2318)")
else:
    need(False, "", f"missing input: {p}")

# ---- tools
say("tools:")
cli = cfg["paths"].get("pmtiles_cli", "")
if cli:
    need(Path(cli).exists() or shutil.which(cli), f"go-pmtiles: {cli}",
         f"pmtiles_cli set but not found: {cli}")
else:
    say("  note pmtiles_cli not set: 04_osm_labels.py will refuse to run (every other step is fine)")

# ---- disk
say("disk:")
common.WORK_ROOT.mkdir(parents=True, exist_ok=True)
free_gb = shutil.disk_usage(common.WORK_ROOT).free / 2**30
need(free_gb > (5 if args.area == "pilot" else 15),
     f"{free_gb:.0f} GB free on {common.WORK_ROOT.drive or common.WORK_ROOT}",
     f"only {free_gb:.0f} GB free on the work drive (base layers need ~15 GB of intermediates)")
if args.area == "full" and free_gb < 25:
    say(f"  note {free_gb:.0f} GB free: enough for base layers and the GEDI subsets (pilot measured "
        "~3 GB replication / ~6 GB mission window), but keep an eye on 13_gedi_stats' projection")

say("")
if problems:
    say(f"{len(problems)} problem(s):")
    for p in problems:
        say("  - " + p)
    sys.exit(1)
say("setup looks good for --area " + args.area)
