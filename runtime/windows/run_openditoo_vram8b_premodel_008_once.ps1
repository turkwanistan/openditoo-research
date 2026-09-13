Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.Vram8B.Premodel008\OpenDitoo.Vram8B.Premodel008.csproj'
$Dotnet = (Get-Command dotnet.exe -ErrorAction Stop).Source
Write-Host 'PREMODEL008_EXECUTION_ID=OPENDITOO-VRAM8B-PREMODEL-008'
Write-Host 'PREMODEL008_TARGET=11:75:58:CE:DE:C7'
Write-Host 'PREMODEL008_RFCOMM_CHANNEL=1'
Write-Host 'PREMODEL008_APPLICATION_SENDS=3'
Write-Host 'PREMODEL008_CUSTOM_0X6C=1'
Write-Host 'PREMODEL008_CAPTURE_MS=75000'
Write-Host 'PREMODEL008_SOURCE_LENGTH=0x410'
Write-Host 'PREMODEL008_RETRY=false'
& $Dotnet run --project $Project --configuration Release --no-build -- --repo-root $RepoRoot
exit $LASTEXITCODE
