Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.M5.Runner\OpenDitoo.M5.Runner.csproj'
& dotnet.exe run --project $Project --configuration Release
exit $LASTEXITCODE
