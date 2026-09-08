Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.M4.Runner\OpenDitoo.M4.Runner.csproj'

Write-Host 'M4_EXECUTION_ID=OPENDITOO-DAY1-M4-FILE-VERSION-001'
Write-Host 'M4_TARGET=11:75:58:CE:DE:C7'
Write-Host 'M4_RFCOMM_CHANNEL=1'
Write-Host 'M4_TX=01040097009B0002'
Write-Host 'M4_RETRY=false'
Write-Host 'M4_MAX_REQUESTS=1'
Write-Host 'M4_MAX_CONNECTIONS=1'

& dotnet.exe run --project $Project --configuration Release
exit $LASTEXITCODE
