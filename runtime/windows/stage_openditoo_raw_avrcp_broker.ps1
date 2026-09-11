# Build + selftest + print frozen hashes. Installing is install_openditoo_raw_avrcp_task.ps1 (elevated).
param(
    [string]$WslDistro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Step([string]$Name, [string]$Value) { Write-Host "$Name=$Value" }

$repo = "\\wsl.localhost\$WslDistro" + ($WslRepositoryPath -replace '/', '\')
$proj = Join-Path $repo 'runtime\windows\OpenDitoo.RawAvrcpBroker\OpenDitoo.RawAvrcpBroker.csproj'
$out = Join-Path $repo 'runtime\windows\OpenDitoo.RawAvrcpBroker\bin\Release\net8.0-windows10.0.19041.0'

if (-not (Test-Path $proj -PathType Leaf)) { throw "broker project missing: $proj" }
& dotnet.exe build $proj -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'raw AVRCP broker build failed' }
$exe = Join-Path $out 'OpenDitoo.RawAvrcpBroker.exe'
$selftest = & $exe --selftest | Out-String  # WinExe: capture stdout so PowerShell waits for the exit code
if ($LASTEXITCODE -ne 0 -or $selftest -notmatch 'RAW_AVRCP_BROKER_SELFTEST=PASS') { throw "raw AVRCP broker selftest failed: $selftest" }
Step 'RAW_AVRCP_BROKER_BUILD' 'PASS'
Step 'RAW_AVRCP_BROKER_SELFTEST' 'PASS'

$files = @(
  'OpenDitoo.RawAvrcpBroker.exe',
  'OpenDitoo.RawAvrcpBroker.dll',
  'OpenDitoo.RawAvrcpBroker.deps.json',
  'OpenDitoo.RawAvrcpBroker.runtimeconfig.json'
)
foreach ($name in $files) {
    $path = Join-Path $out $name
    if (-not (Test-Path $path -PathType Leaf)) { throw "build output missing: $path" }
    Step ("RAW_AVRCP_BUILD_SHA256_" + ($name -replace '[^A-Za-z0-9]','_')) ((Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant())
}
Step 'RAW_AVRCP_STAGE' 'BUILT'
