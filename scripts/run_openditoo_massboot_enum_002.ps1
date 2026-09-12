# OPENDITOO-MASSBOOT-ENUM-002
# Enumeration only. No custom USB/SCSI/vendor command; no disk/volume access; no firmware/RAM read/write.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$exp = 'OPENDITOO-MASSBOOT-ENUM-002'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outDir = Join-Path $root 'captures/private/massboot-enum-002'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runDir = Join-Path $outDir $stamp
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Run this script from Administrator PowerShell.'
}

function Get-EnumSnapshot {
  param([string]$Name)
  $items = Get-PnpDevice -PresentOnly | Where-Object {
    $_.Class -in @('USB','DiskDrive','WPD') -or $_.InstanceId -like 'USB*' -or $_.InstanceId -like 'SCSI*'
  } | Select-Object Status,Class,FriendlyName,InstanceId
  $json = Join-Path $runDir ($Name + '.json')
  $txt  = Join-Path $runDir ($Name + '.txt')
  $items | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $json
  $items | Sort-Object Class,FriendlyName,InstanceId | Format-Table -AutoSize | Out-String -Width 4096 | Set-Content -Encoding UTF8 $txt
  return @($items)
}

function Get-Key([object]$x) { return [string]$x.InstanceId }

Write-Host "=== $exp ===" -ForegroundColor Cyan
Write-Host 'BOUNDARY: Windows PnP enumeration only. Do NOT initialize/format/browse any new device or volume.' -ForegroundColor Yellow
Write-Host 'Make sure the SD card is REMOVED.
Write-Host 'PRECHECK: Before involving the Ditoo, prove this NEW cable carries data with another known USB data device on this same PC/port.' -ForegroundColor Yellow' -ForegroundColor Yellow
Write-Host ''
Write-Host 'PHASE A — normal USB baseline'
Write-Host '1) Ditoo fully OFF.'
Write-Host '2) Connect the NEW data-validated USB cable to the PC/Ditoo.'
Write-Host '3) Boot normally with NO special key held.'
Write-Host '4) Wait until normal startup is stable, then press Enter here.'
Read-Host | Out-Null
$baseline = Get-EnumSnapshot 'phase-a-normal-usb'
Write-Host "Baseline captured: $($baseline.Count) relevant PnP entries."

Write-Host ''
Write-Host 'Prepare candidate: power the Ditoo fully OFF and UNPLUG its USB cable. Press Enter when it is off/unplugged.'
Read-Host | Out-Null
$disconnected = Get-EnumSnapshot 'between-phases-disconnected'

$automountDisabled = $false
try {
  Write-Host 'Disabling automatic mounting of newly discovered volumes...'
  & mountvol.exe /N | Out-File -Encoding utf8 (Join-Path $runDir 'mountvol-disable.txt')
  $automountDisabled = $true

  Write-Host ''
  Write-Host 'PHASE B — MassBoot candidate' -ForegroundColor Cyan
  Write-Host '1) HOLD the LIGHTING key.' -ForegroundColor Yellow
  Write-Host '2) While holding it, attach the NEW data-validated USB cable.' -ForegroundColor Yellow
  Write-Host '3) If cable insertion does not start the Ditoo, use only the normal POWER-ON action while STILL holding Lighting.' -ForegroundColor Yellow
  Write-Host '4) Keep Lighting held through startup; release after stable behavior or ~5 seconds of boot activity.' -ForegroundColor Yellow
  Write-Host '5) Do NOT click any Windows initialize/format/repair prompt. Cancel/dismiss only.' -ForegroundColor Red
  Write-Host '6) Once Windows/device behavior is stable, press Enter here ONCE.'
  Read-Host | Out-Null

  $candidate = Get-EnumSnapshot 'phase-b-lighting-usb'

  $baseIds = @{}; foreach ($x in $baseline) { $baseIds[(Get-Key $x)] = $true }
  $discIds = @{}; foreach ($x in $disconnected) { $discIds[(Get-Key $x)] = $true }
  $newVsBaseline = @($candidate | Where-Object { -not $baseIds.ContainsKey((Get-Key $_)) })
  $newVsDisconnected = @($candidate | Where-Object { -not $discIds.ContainsKey((Get-Key $_)) })

  $newVsBaseline | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $runDir 'new-vs-baseline.json')
  $newVsDisconnected | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $runDir 'new-vs-disconnected.json')

  Write-Host ''
  Write-Host '=== CANDIDATE NEW VS NORMAL BASELINE ===' -ForegroundColor Green
  if ($newVsBaseline.Count -eq 0) {
    Write-Host 'No new relevant PnP identity detected versus normal USB baseline.'
  } else {
    $newVsBaseline | Format-Table Status,Class,FriendlyName,InstanceId -AutoSize | Out-String -Width 4096 | Write-Host
  }

  $summary = [ordered]@{
    experiment_id = $exp
    captured_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    run_dir = $runDir
    baseline_count = $baseline.Count
    disconnected_count = $disconnected.Count
    candidate_count = $candidate.Count
    new_vs_baseline_count = $newVsBaseline.Count
    new_vs_baseline = $newVsBaseline
    new_vs_disconnected_count = $newVsDisconnected.Count
    new_vs_disconnected = $newVsDisconnected
    custom_usb_requests = $false
    massboot_protocol_commands = $false
    firmware_read = $false
    firmware_write = $false
  }
  $summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $runDir 'summary.json')
  Write-Host "Evidence: $runDir"
}
finally {
  if ($automountDisabled) {
    Write-Host 'Restoring Windows automount...'
    & mountvol.exe /E | Out-File -Encoding utf8 (Join-Path $runDir 'mountvol-enable.txt')
  }
}

Write-Host ''
Write-Host 'EXPERIMENT COMPLETE. Do not interact with any newly exposed interface.' -ForegroundColor Cyan
Write-Host 'Power-cycle the Ditoo normally with Lighting released.'
Write-Host "RESULT_DIR=$runDir"
