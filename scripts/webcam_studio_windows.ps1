param([ValidateSet('preview','selftest')][string]$Mode = 'preview',
      [string]$StageDir = 'C:\temp\openditoo-webcam-studio')
# W10 Studio. Neither mode reaches the Host or the Ditoo: `preview` is camera-only and
# `selftest` uses the in-memory Host. WinRT capture fails from the WSL share (0x80070490),
# so the build is always staged to a local directory first.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$project = Join-Path $repo 'runtime\windows\OpenDitoo.Webcam.Studio'
& dotnet build (Join-Path $project 'OpenDitoo.Webcam.Studio.csproj') -c Release --nologo -v q
if ($LASTEXITCODE -ne 0) { throw 'W10_STUDIO_BUILD_FAILED' }
if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir | Out-Null
Copy-Item (Join-Path $project 'bin\Release\net8.0-windows10.0.19041.0\*') $StageDir -Recurse
& (Join-Path $StageDir 'OpenDitoo.Webcam.Studio.exe') $Mode
exit $LASTEXITCODE
