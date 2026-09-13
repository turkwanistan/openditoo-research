Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.Vram8B.ModelSentinel009\OpenDitoo.Vram8B.ModelSentinel009.csproj'
$Dotnet = (Get-Command dotnet.exe -ErrorAction Stop).Source
Write-Host 'MODEL009_EXECUTION_ID=OPENDITOO-VRAM8B-MODEL-SENTINEL-009'
Write-Host 'MODEL009_TARGET=11:75:58:CE:DE:C7'
Write-Host 'MODEL009_RFCOMM_CHANNEL=1'
Write-Host 'MODEL009_APPLICATION_SENDS=3'
Write-Host 'MODEL009_CUSTOM_0X6C=1'
Write-Host 'MODEL009_CAPTURE_MS=75000'
Write-Host 'MODEL009_SOURCE_LENGTH=0x411'
Write-Host 'MODEL009_RETRY=false'
& $Dotnet run --project $Project --configuration Release --no-build -- --repo-root $RepoRoot
exit $LASTEXITCODE
