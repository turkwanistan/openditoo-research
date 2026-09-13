Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.Vram8B.Control007\OpenDitoo.Vram8B.Control007.csproj'
$Dotnet = (Get-Command dotnet.exe -ErrorAction Stop).Source
Write-Host 'CONTROL007_EXECUTION_ID=OPENDITOO-VRAM8B-CONTROL-007'
Write-Host 'CONTROL007_TARGET=11:75:58:CE:DE:C7'
Write-Host 'CONTROL007_RFCOMM_CHANNEL=1'
Write-Host 'CONTROL007_APPLICATION_SENDS=2'
Write-Host 'CONTROL007_CUSTOM_0X6C=0'
Write-Host 'CONTROL007_CAPTURE_MS=75000'
Write-Host 'CONTROL007_RETRY=false'
& $Dotnet run --project $Project --configuration Release --no-build -- --repo-root $RepoRoot
exit $LASTEXITCODE
