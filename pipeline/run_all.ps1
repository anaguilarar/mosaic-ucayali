# MOSAIC Ucayali pipeline - the one place the full command sequence lives (RUN.md points here).
# Runs every step sequentially under memwatch. Usage:
#   .\run_all.ps1                 # full area
#   .\run_all.ps1 -Area pilot     # small test box around Pucallpa (minutes)
#   .\run_all.ps1 -Area full -GediMonth 2020-06   # base layers + a one-month GEDI pilot
# Steps skip outputs that are already fresh; re-running resumes where it stopped.
param(
  [ValidateSet('pilot', 'full')] [string]$Area = 'full',
  [string]$GediMonth = '',      # empty = whole configured period (the full GEDI run)
  [switch]$SkipGedi
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$mw = @('scripts/memwatch.py', '--min-free-gb', '4', '--')

function Step([string]$Name, [string[]]$Cmd) {
  Write-Host "`n=== $Name ===" -ForegroundColor Cyan
  python @mw python @Cmd --area $Area
  if ($LASTEXITCODE -ne 0) { throw "$Name failed (exit $LASTEXITCODE)" }
}

python scripts/00_check_setup.py --area $Area
if ($LASTEXITCODE -ne 0) { throw '00_check_setup failed' }

Step '01 boundaries'       @('scripts/01_boundary.py')
Step '02 terrain'          @('scripts/02_terrain.py')
Step '03 sentinel-2'       @('scripts/03_s2.py')
Step '04 osm labels'       @('scripts/04_osm_labels.py')
Step '05 cooley polygons'  @('scripts/05_cooley_polygons.py')

if (-not $SkipGedi) {
  Step '10 gedi search'    @('scripts/10_gedi_search.py')
  if ($GediMonth) {
    Step '11 gedi subset'  @('scripts/11_gedi_subset.py', '--month', $GediMonth)
  } else {
    Step '11 gedi subset'  @('scripts/11_gedi_subset.py')
  }
  Step '12 gedi filter'    @('scripts/12_gedi_filter.py')
  Step '13 gedi stats'     @('scripts/13_gedi_stats.py')
}

python scripts/91_publish_check.py --area $Area
Write-Host "`npipeline finished (area=$Area)" -ForegroundColor Green
