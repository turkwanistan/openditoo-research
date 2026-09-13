Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.Vram8B.Runner003\OpenDitoo.Vram8B.Runner003.csproj'
$Dotnet = (Get-Command dotnet.exe -ErrorAction Stop).Source
Write-Host 'VRAM8B_EXECUTION_ID=OPENDITOO-VRAM8B-CANARY-003'
Write-Host 'VRAM8B_TARGET=11:75:58:CE:DE:C7'
Write-Host 'VRAM8B_RFCOMM_CHANNEL=1'
Write-Host 'VRAM8B_APPLICATION_SENDS=8'
Write-Host 'VRAM8B_CUSTOM_0X6C=1'
Write-Host 'VRAM8B_TYPED_EXPECTED=0->1->0'
Write-Host 'VRAM8B_RETRY=false'
& $Dotnet run --project $Project --configuration Release --no-build -- --repo-root $RepoRoot
exit $LASTEXITCODE
