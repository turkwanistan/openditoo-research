param(
    [string]$StageDir = 'C:\temp\openditoo-webcam-runner'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = Split-Path $PSScriptRoot -Parent
$project = Join-Path $repo 'runtime\windows\OpenDitoo.Webcam.Runner'
$manifestPath = Join-Path $repo 'experiments\DAY1-WEBCAM-N980P-001.json'
$transformFixture = Join-Path $repo 'tests\frame_transform_cases.json'
$encoderFixture = Join-Path $repo 'tests\ditoo_encoder_cases.json'
$release = Join-Path $project 'bin\Release\net8.0-windows10.0.19041.0'

function Require([bool]$Condition, [string]$Reason) {
    if (-not $Condition) { throw $Reason }
}

Write-Output 'W6_WINDOWS_OFFLINE_BEGIN device_io=false host_session_io=false claim_created=false'

# Rebuild the exact Windows-native runner. Do not rebuild/deploy the Day1 Host here.
& dotnet build (Join-Path $project 'OpenDitoo.Webcam.Runner.csproj') -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'W6_RUNNER_BUILD_FAILED' }

# MediaCapture is known to fail when the executable itself runs from \\wsl.localhost.
# Stage only this runner under a fixed local Windows path.
if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir | Out-Null
Copy-Item (Join-Path $release '*') $StageDir -Recurse
$runner = Join-Path $StageDir 'OpenDitoo.Webcam.Runner.exe'
Require (Test-Path $runner) 'W6_STAGED_RUNNER_MISSING'

& $runner selftest
if ($LASTEXITCODE -ne 0) { throw 'W6_ADAPTER_SELFTEST_FAILED' }
& $runner transform-selftest $transformFixture
if ($LASTEXITCODE -ne 0) { throw 'W6_TRANSFORM_PARITY_FAILED' }
& $runner encoder-selftest $encoderFixture
if ($LASTEXITCODE -ne 0) { throw 'W6_ENCODER_PARITY_FAILED' }

# Exercise the real camera-ready nonce boundary without a Ditoo claim or Host session.
# Trial.Load requires a structurally authorized manifest before it will touch the camera, so use
# a temporary OFFLINE-ONLY synthetic identity. We intentionally never create its claim file and
# never write execute:<nonce> to stdin; the runner therefore cannot cross into TypedSession.Live.
$offlineId = 'OPENDITOO-WEBCAM-N980P-998'
$offlineManifest = Join-Path ([IO.Path]::GetTempPath()) ('openditoo-w6-handshake-' + [guid]::NewGuid().ToString('N') + '.json')
$doc = Get-Content $manifestPath -Raw | ConvertFrom-Json
$doc.experiment_id = $offlineId
$doc.readiness.execution_ready = $true
$doc.readiness.grant_ready = $true
$doc.readiness.blockers = @()
$doc.authority.experiment_id = $offlineId
$doc.authority.transmission_authorized = $true
$doc.authority.authorization_consumed = $false
$doc.authority.granted_by = 'OFFLINE_HANDSHAKE_SELFTEST_ONLY'
$doc.authority.grant_text = 'Grant ' + $offlineId
$doc.authority.expires_at = (Get-Date).ToUniversalTime().AddMinutes(10).ToString('o')
$doc | ConvertTo-Json -Depth 30 | Set-Content -Path $offlineManifest -Encoding UTF8
$manifestSha = (Get-FileHash -Algorithm SHA256 $offlineManifest).Hash.ToLowerInvariant()
$claimPath = Join-Path $repo ('.openditoo-local\session-claims\' + $offlineId + '.json')
Require (-not (Test-Path $claimPath)) 'W6_OFFLINE_HANDSHAKE_ID_ALREADY_CLAIMED'

$psi = [Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $runner
$psi.Arguments = ('live "{0}" "{1}"' -f $offlineManifest, $repo)
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$proc = [Diagnostics.Process]::new()
$proc.StartInfo = $psi
Require ($proc.Start()) 'W6_HANDSHAKE_PROCESS_START_FAILED'
try {
    $lineTask = $proc.StandardOutput.ReadLineAsync()
    Require ($lineTask.Wait([TimeSpan]::FromSeconds(20))) 'W6_CAMERA_READY_TIMEOUT'
    $readyLine = $lineTask.Result
    $ready = $readyLine | ConvertFrom-Json
    Require ($ready.kind -eq 'camera_ready') 'W6_CAMERA_READY_KIND_MISMATCH'
    Require ($ready.experiment_id -eq $offlineId) 'W6_CAMERA_READY_ID_MISMATCH'
    Require ($ready.manifest_sha256 -eq $manifestSha) 'W6_CAMERA_READY_MANIFEST_HASH_MISMATCH'
    Require ($ready.nonce -match '^[a-f0-9]{32}$') 'W6_CAMERA_READY_NONCE_INVALID'
    # Closing stdin is the negative control: no execute:<nonce>, no claim, no Host session.
    $proc.StandardInput.Close()
    Require ($proc.WaitForExit(20000)) 'W6_HANDSHAKE_PROCESS_DID_NOT_EXIT'
    Require ($proc.ExitCode -ne 0) 'W6_HANDSHAKE_NEGATIVE_CONTROL_UNEXPECTED_SUCCESS'
    Require (-not (Test-Path $claimPath)) 'W6_HANDSHAKE_CREATED_CLAIM'
    Write-Output ("W6_CAMERA_READY_HANDSHAKE_PASS id={0} nonce_length=32 claim_created=false host_session_io=false device_io=false" -f $offlineId)
}
finally {
    if (-not $proc.HasExited) { $proc.Kill(); $proc.WaitForExit() }
    $proc.Dispose()
    Remove-Item $offlineManifest -Force -ErrorAction SilentlyContinue
}

# Five real-camera minutes through the exact transform/encoder/sender serialization path and an
# in-memory typed Host only. The runner reports a bounded telemetry window and memory growth after
# warmup. No token or Host endpoint is opened by soak mode.
$soakLines = @(& $runner soak)
$soakExit = $LASTEXITCODE
if ($soakExit -ne 0) { throw ('W6_SOAK_FAILED ' + ($soakLines -join ' ')) }
$soakPass = $null
foreach ($line in $soakLines) {
    Write-Output $line
    try {
        $item = $line | ConvertFrom-Json
        if ($item.kind -eq 'soak_pass') { $soakPass = $item }
    } catch { }
}
Require ($null -ne $soakPass) 'W6_SOAK_PASS_RECORD_MISSING'
Require ($soakPass.seconds -ge 295) 'W6_SOAK_TOO_SHORT'
Require ([int64]$soakPass.growthAfterWarmupBytes -lt 8388608) 'W6_SOAK_MEMORY_GROWTH_EXCEEDED'

Write-Output ("W6_WINDOWS_OFFLINE_PASS stage={0} soak_seconds={1} growth_after_warmup_bytes={2} claim_created=false host_session_io=false device_io=false" -f $StageDir, $soakPass.seconds, $soakPass.growthAfterWarmupBytes)
