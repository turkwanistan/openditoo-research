param(
    [switch]$Apply,
    [string]$WslDistro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Step([string]$Name, [string]$Value) { Write-Host "$Name=$Value" }

$repo = "\\wsl.localhost\$WslDistro" + ($WslRepositoryPath -replace '/', '\')
$proj = Join-Path $repo 'runtime\windows\OpenDitoo.RawAvrcpBroker\OpenDitoo.RawAvrcpBroker.csproj'
$out = Join-Path $repo 'runtime\windows\OpenDitoo.RawAvrcpBroker\bin\Release\net8.0-windows10.0.19041.0'
$dest = Join-Path $env:LOCALAPPDATA 'OpenDitoo\RawAvrcpBroker'

if (-not (Test-Path $proj -PathType Leaf)) { throw "broker project missing: $proj" }
& dotnet.exe build $proj -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'raw AVRCP broker build failed' }
$exe = Join-Path $out 'OpenDitoo.RawAvrcpBroker.exe'
& $exe --selftest
if ($LASTEXITCODE -ne 0) { throw 'raw AVRCP broker selftest failed' }
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
if (-not $Apply) { Step 'RAW_AVRCP_STAGE' 'DRY_RUN'; exit 0 }

$stage = Join-Path $env:TEMP ('OpenDitoo-RawAvrcpBroker-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    foreach ($name in $files) { Copy-Item (Join-Path $out $name) (Join-Path $stage $name) }
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    Move-Item $stage $dest
} finally {
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
}
& (Join-Path $dest 'OpenDitoo.RawAvrcpBroker.exe') --selftest
if ($LASTEXITCODE -ne 0) { throw 'staged broker selftest failed' }
Step 'RAW_AVRCP_STAGE' 'PASS'
