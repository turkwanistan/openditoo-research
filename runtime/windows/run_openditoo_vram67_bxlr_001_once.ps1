Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.Vram67.Runner\OpenDitoo.Vram67.Runner.csproj'

Write-Host 'VRAM67_EXECUTION_ID=OPENDITOO-VRAM67-BXLR-001'
Write-Host 'VRAM67_TARGET=11:75:58:CE:DE:C7'
Write-Host 'VRAM67_RFCOMM_CHANNEL=1'
Write-Host 'VRAM67_PACKETS=3'
Write-Host 'VRAM67_CUSTOM_0X6C=1'
Write-Host 'VRAM67_RETRY=false'
Write-Host 'VRAM67_PRIME_SHA256=9f643ace4ce755ddcd04446c0cb21bbaa23b53f123788a225d1c9eda81e213ec'
Write-Host 'VRAM67_VOICETIP_SHA256=4cf9f3d0458664a2c99681e6a672b8eaefea3a043d83a2f15a751aabcd9d0316'
Write-Host 'VRAM67_OVERWRITE_SHA256=c3fbc813e2646b44ace4a2105163fe7bc2622d5e6cc61477ac6098d0b23b12cd'

& dotnet.exe run --project $Project --configuration Release -- --repo-root $RepoRoot
exit $LASTEXITCODE
