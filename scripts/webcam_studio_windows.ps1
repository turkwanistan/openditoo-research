param([ValidateSet('preview','dryrun','selftest')][string]$Mode = 'preview',
      [string]$StageDir = 'C:\temp\openditoo-webcam-studio')
# W10 Studio. No mode here reaches the Host or the Ditoo: `preview` is camera-only, `dryrun`
# streams 60 s into the in-memory Host through the real window, `selftest` has no camera.
# WinRT capture fails from the WSL share (0x80070490), so the build is always staged locally.
# Staging here never touches C:\temp\openditoo-webcam-studio-w10, the stage W10-001 is frozen to.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$project = Join-Path $repo 'runtime\windows\OpenDitoo.Webcam.Studio'
& dotnet build (Join-Path $project 'OpenDitoo.Webcam.Studio.csproj') -c Release --nologo -v q
if ($LASTEXITCODE -ne 0) { throw 'W10_STUDIO_BUILD_FAILED' }
if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir | Out-Null
Copy-Item (Join-Path $project 'bin\Release\net8.0-windows10.0.19041.0\*') $StageDir -Recurse
$extra = if ($Mode -eq 'dryrun') { @('60') } else { @() }
& (Join-Path $StageDir 'OpenDitoo.Webcam.Studio.exe') $Mode @extra
exit $LASTEXITCODE
