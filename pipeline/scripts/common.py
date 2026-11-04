"""Shared helpers for the mosaic_ucayali pipeline: config, paths, logging, step CLI, manifest,
layer registry, MBTiles/PMTiles. Every path comes from pipeline/config.toml - nothing depends on
where the repo folder sits. Import side effect: the config is loaded and the module-level paths
below are set (00_check_setup.py gives the friendly message when config.toml is missing).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:          # Python < 3.11
    import tomli as tomllib

PIPELINE = Path(__file__).resolve().parents[1]          # <repo>/pipeline
REPO = PIPELINE.parent
CONFIG_PATH = PIPELINE / "config.toml"

if not CONFIG_PATH.exists():
    sys.exit(f"pipeline/config.toml not found.\nCopy {PIPELINE / 'config.example.toml'} to "
             f"{CONFIG_PATH} and edit the [paths] section for this machine.")

with open(CONFIG_PATH, "rb") as f:
    CFG = tomllib.load(f)

INPUTS = Path(CFG["paths"]["inputs_dir"])
COOLEY = Path(CFG["paths"]["cooley_dir"])
WORK_ROOT = Path(CFG["paths"]["work_dir"])
DATA_FULL = Path(CFG["paths"]["data_dir"]) if CFG["paths"].get("data_dir") else REPO / "data"

# set by setup() according to --area; sensible defaults so ad-hoc imports work
AREA = "full"
DATA = DATA_FULL
WORK = WORK_ROOT
LOGS = WORK_ROOT / "logs"

log = logging.getLogger("pipeline")


def bbox() -> tuple[float, float, float, float]:
    return tuple(CFG["area"]["pilot_bbox" if AREA == "pilot" else "full_bbox"])


def setup(step: str, extra_args=None) -> argparse.Namespace:
    """Parse the step CLI (--area pilot|full, --force), set paths, logging and GDAL limits.
    With --area pilot every output goes to <work_dir>/pilot_data (the app's data/ stays clean)."""
    global AREA, DATA, WORK, LOGS
    ap = argparse.ArgumentParser(description=step)
    ap.add_argument("--area", choices=["pilot", "full"], default="full",
                    help="pilot = small test box around Pucallpa; outputs under <work_dir>/pilot_data")
    ap.add_argument("--force", action="store_true", help="rebuild outputs even if they look fresh")
    for name, kw in (extra_args or []):
        ap.add_argument(name, **kw)
    args = ap.parse_args()

    AREA = args.area
    DATA = (WORK_ROOT / "pilot_data") if AREA == "pilot" else DATA_FULL
    WORK = WORK_ROOT / ("pilot_work" if AREA == "pilot" else "work")
    LOGS = WORK_ROOT / "logs"
    for d in (DATA / "tiles", DATA / "vectors", DATA / "meta", DATA / "series", WORK, LOGS):
        d.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True,
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(LOGS / f"{step}.log", encoding="utf-8")])
    os.environ.setdefault("GDAL_CACHEMAX", str(CFG["memory"]["gdal_cachemax_mb"]))
    log.info("step %s | area=%s | data=%s | work=%s", step, AREA, DATA, WORK)
    return args


def fresh(out: Path, *sources: Path) -> bool:
    """True when `out` exists and is newer than every source (step skips it unless --force)."""
    if not out.exists():
        return False
    t = out.stat().st_mtime
    return all((not s.exists()) or s.stat().st_mtime <= t for s in sources)


# ----------------------------------------------------------------- manifest

def record(step: str, path: Path, note: str = ""):
    """Append one output to <work_dir>/manifest.jsonl (file, size, sha256, step, date), so outputs
    can be copied between machines and verified (python scripts/common.py verify)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    try:                       # work-root-relative path, so a manifest copied from another machine verifies
        rel = str(Path(path).resolve().relative_to(WORK_ROOT.resolve()))
    except ValueError:
        rel = ""               # outputs under data/ (another machine resolves them by absolute path only)
    entry = {"file": str(path), "rel": rel, "bytes": path.stat().st_size, "sha256": h.hexdigest(),
             "step": step, "area": AREA, "date": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note}
    mf = WORK_ROOT / "manifest.jsonl"
    with open(mf, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    log.info("manifest: %s (%.1f MB)", Path(path).name, entry["bytes"] / 1e6)


def verify_manifest() -> int:
    """Re-hash every manifest entry that still exists; report mismatches. Returns the bad count."""
    mf = WORK_ROOT / "manifest.jsonl"
    if not mf.exists():
        print("no manifest yet:", mf)
        return 0
    seen, bad = {}, 0
    for line in mf.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        seen[e["file"]] = e                    # last write wins
    for file, e in seen.items():
        p = Path(file)
        if not p.exists() and e.get("rel"):      # manifest written on another machine: try this work root
            p = WORK_ROOT / e["rel"]
        if not p.exists():
            print("missing:", file)
            continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != e["sha256"]:
            print("CHANGED since manifest:", file)
            bad += 1
    print(f"verified {len(seen)} entries, {bad} mismatches")
    return bad


# ----------------------------------------------------------------- layer registry

def update_registry(layer_id: str, entry: dict):
    """Merge one layer entry into <data>/meta/layers.json (keyed by id, order preserved)."""
    meta = DATA / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    path = meta / "layers.json"
    reg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"layers": []}
    entry = {"id": layer_id, **entry}
    ids = [l["id"] for l in reg["layers"]]
    if layer_id in ids:
        reg["layers"][ids.index(layer_id)] = entry
    else:
        reg["layers"].append(entry)
    path.write_text(json.dumps(reg, indent=1), encoding="utf-8")
    log.info("registry updated: %s", layer_id)


# ----------------------------------------------------------------- MBTiles / PMTiles

def open_mbtiles(path: Path, name: str, fmt: str, minzoom: int, maxzoom: int, bounds, extra_meta=None):
    """Create a fresh MBTiles file and return its sqlite connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    db.execute("CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)")
    db.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)")
    meta = {"name": name, "format": fmt, "minzoom": str(minzoom), "maxzoom": str(maxzoom),
            "bounds": ",".join(f"{b:.6f}" for b in bounds), "type": "overlay", "version": "1",
            **(extra_meta or {})}
    db.executemany("INSERT INTO metadata VALUES (?,?)", meta.items())
    return db


def put_tile(db, z: int, x: int, y: int, data: bytes):
    """Insert one XYZ tile (converts to the TMS row scheme MBTiles uses)."""
    db.execute("INSERT OR REPLACE INTO tiles VALUES (?,?,?,?)", (z, x, (1 << z) - 1 - y, sqlite3.Binary(data)))


def mbtiles_to_pmtiles(src: Path, dst: Path, maxzoom: int):
    from pmtiles.convert import mbtiles_to_pmtiles as conv
    if dst.exists():
        dst.unlink()
    conv(str(src), str(dst), maxzoom)
    log.info("wrote %s (%.1f MB)", dst, dst.stat().st_size / 1e6)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        sys.exit(1 if verify_manifest() else 0)
    print(f"repo={REPO}\ninputs={INPUTS}\nwork={WORK_ROOT}\ndata={DATA_FULL}")
