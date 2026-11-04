#!/usr/bin/env bash
# MOSAIC Ucayali pipeline - the one place the full command sequence lives (RUN.md points here).
# Usage: ./run_all.sh [pilot|full] [GEDI_MONTH|skipgedi]
set -euo pipefail
cd "$(dirname "$0")"
AREA="${1:-full}"
GEDI="${2:-}"
MW=(python scripts/memwatch.py --min-free-gb 4 --)

step() { echo; echo "=== $1 ==="; shift; "${MW[@]}" python "$@" --area "$AREA"; }

python scripts/00_check_setup.py --area "$AREA"

step "01 boundaries"      scripts/01_boundary.py
step "02 terrain"         scripts/02_terrain.py
step "03 sentinel-2"      scripts/03_s2.py
step "04 osm labels"      scripts/04_osm_labels.py
step "05 cooley polygons" scripts/05_cooley_polygons.py

step "20 forest loss"     scripts/20_forest_loss.py
step "21 land cover"      scripts/21_landcover.py
step "22 canopy height"   scripts/22_canopy_height.py
step "23 protected areas" scripts/23_protected_areas.py
step "24 fires"           scripts/24_fires.py

if [ "$GEDI" != "skipgedi" ]; then
  step "10 gedi search"   scripts/10_gedi_search.py
  if [ -n "$GEDI" ]; then
    step "11 gedi subset" scripts/11_gedi_subset.py --month "$GEDI"
  else
    step "11 gedi subset" scripts/11_gedi_subset.py
  fi
  step "12 gedi filter"   scripts/12_gedi_filter.py
  step "13 gedi stats"    scripts/13_gedi_stats.py
fi

python scripts/91_publish_check.py --area "$AREA"
echo; echo "pipeline finished (area=$AREA)"
