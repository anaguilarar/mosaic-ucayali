# MOSAIC Ucayali pipeline - the one place the full command sequence lives (RUN.md points here).
# Runs steps sequentially under memwatch. Usage:
#   .\run_all.ps1                                       # every step, full area
#   .\run_all.ps1 -Area pilot                           # small test box around Pucallpa (minutes)
#   .\run_all.ps1 -Area full -GediMonth 2020-07         # base layers + a one-month GEDI pilot
#   .\run_all.ps1 -Area full -Steps 10,11,12,13         # only the GEDI steps (e.g. on a server)
#   .\run_all.ps1 -Area full -Steps 11 -GediWindow mission   # mission-window subsets only
# Steps skip outputs that are already fresh; re-running resumes where it stopped.
param(
  [ValidateSet('pilot', 'full')] [string]$Area = 'full',
  [string]$GediMonth = '',      # empty = the whole chosen window (the full GEDI run)
  [ValidateSet('replication', 'mission')] [string]$GediWindow = 'replication',
  [string[]]$Steps = @(),       # step numbers to run, e.g. 10,11,12,13; empty = all
  [switch]$SkipGedi
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$mw = @('scripts/memwatch.py', '--min-free-gb', '4', '--')
function Wanted([string]$N) { return ($Steps.Count -eq 0) -or ($Steps -contains $N) }

function Step([string]$N, [string]$Name, [string[]]$Cmd) {
  if (-not (Wanted $N)) { return }
  Write-Host "`n=== $N $Name ===" -ForegroundColor Cyan
  python @mw python @Cmd --area $Area
  if ($LASTEXITCODE -ne 0) { throw "$N $Name failed (exit $LASTEXITCODE)" }
}

if (Wanted '00') {
  python scripts/00_check_setup.py --area $Area
  if ($LASTEXITCODE -ne 0) { throw '00_check_setup failed' }
}

Step '01' 'boundaries'      @('scripts/01_boundary.py')
Step '02' 'terrain'         @('scripts/02_terrain.py')
Step '03' 'sentinel-2'      @('scripts/03_s2.py')
Step '04' 'osm labels'      @('scripts/04_osm_labels.py')
Step '05' 'cooley polygons' @('scripts/05_cooley_polygons.py')

if (-not $SkipGedi) {
  Step '10' 'gedi search'   @('scripts/10_gedi_search.py', '--window', $GediWindow)
  if ($GediMonth) {
    Step '11' 'gedi subset' @('scripts/11_gedi_subset.py', '--month', $GediMonth)
  } else {
    Step '11' 'gedi subset' @('scripts/11_gedi_subset.py', '--window', $GediWindow)
  }
  Step '12' 'gedi filter'   @('scripts/12_gedi_filter.py')
  Step '13' 'gedi stats'    @('scripts/13_gedi_stats.py')
}

if (Wanted '91') { python scripts/91_publish_check.py --area $Area }
Write-Host "`npipeline finished (area=$Area)" -ForegroundColor Green
