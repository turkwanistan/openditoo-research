param(
    [string]$StageDir = 'C:\temp\openditoo-webcam-runner',
    [string]$Distro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = Split-Path $PSScriptRoot -Parent
$project = Join-Path $repo 'runtime\windows\OpenDitoo.Webcam.Runner'
$manifestPath = Join-Path $repo 'experiments\DAY1-WEBCAM-N980P-002.json'
$transformFixture = Join-Path $repo 'tests\frame_transform_cases.json'
$encoderFixture = Join-Path $repo 'tests\ditoo_encoder_cases.json'
$release = Join-Path $project 'bin\Release\net8.0-windows10.0.19041.0'
$evidencePath = Join-Path $repo 'captures\OPENDITOO-WEBCAM-W7-RERUN-PREPARATION-2026-09-09.json'

function Require([bool]$Condition, [string]$Reason) {
    if (-not $Condition) { throw $Reason }
}

Write-Output 'W7_RERUN_PREP_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-002 device_io=false host_session_io=false claim_created=false'

# Rebuild only the corrected webcam runner. The Day1 Host / Runtime 003 is not rebuilt or stopped.
& dotnet build (Join-Path $project 'OpenDitoo.Webcam.Runner.csproj') -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'W7_RERUN_RUNNER_BUILD_FAILED' }

if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir | Out-Null
Copy-Item (Join-Path $release '*') $StageDir -Recurse
$runner = Join-Path $StageDir 'OpenDitoo.Webcam.Runner.exe'
Require (Test-Path $runner) 'W7_RERUN_STAGED_RUNNER_MISSING'

& $runner selftest
if ($LASTEXITCODE -ne 0) { throw 'W7_RERUN_ADAPTER_SELFTEST_FAILED' }
& $runner transform-selftest $transformFixture
if ($LASTEXITCODE -ne 0) { throw 'W7_RERUN_TRANSFORM_PARITY_FAILED' }
& $runner encoder-selftest $encoderFixture
if ($LASTEXITCODE -ne 0) { throw 'W7_RERUN_ENCODER_PARITY_FAILED' }

# Critical regression check: exercise the corrected C# parser against the REAL established
# /v1/status contract. This endpoint is read-only and the runner does not open a session here.
$statusLines = @(& $runner host-status-selftest $repo)
$statusExit = $LASTEXITCODE
foreach ($line in $statusLines) { Write-Output $line }
if ($statusExit -ne 0) { throw ('W7_RERUN_LIVE_STATUS_SELFTEST_FAILED ' + ($statusLines -join ' ')) }
$statusPass = $null
foreach ($line in $statusLines) {
    try {
        $item = $line | ConvertFrom-Json
        if ($item.kind -eq 'host_status_selftest_pass') { $statusPass = $item }
    } catch { }
}
Require ($null -ne $statusPass) 'W7_RERUN_LIVE_STATUS_PASS_RECORD_MISSING'
Require ($statusPass.target -eq '11:75:58:CE:DE:C7') 'W7_RERUN_LIVE_STATUS_TARGET_MISMATCH'
Require ($statusPass.status_has_ok_field -eq $false) 'W7_RERUN_STATUS_CONTRACT_UNEXPECTED_OK_FIELD'
Require ($statusPass.device_io -eq $false) 'W7_RERUN_STATUS_SELFTEST_TOUCHED_DEVICE'
Require ($statusPass.host_session_io -eq $false) 'W7_RERUN_STATUS_SELFTEST_OPENED_SESSION'

# Freeze the exact just-built source/build artifacts into the fresh 002 envelope. Authority is
# deliberately untouched: preparation can never grant itself permission to transmit.
$doc = Get-Content $manifestPath -Raw | ConvertFrom-Json
Require ($doc.experiment_id -eq 'OPENDITOO-WEBCAM-N980P-002') 'W7_RERUN_MANIFEST_ID_MISMATCH'
Require ($doc.authority.transmission_authorized -eq $false) 'W7_RERUN_PREP_REFUSES_PREAUTHORIZED_MANIFEST'
Require ($doc.authority.authorization_consumed -eq $false) 'W7_RERUN_PREP_REFUSES_CONSUMED_MANIFEST'
foreach ($property in $doc.stream.live_source.producer_code_sha256.PSObject.Properties) {
    $relative = $property.Name
    $sourcePath = Join-Path $repo $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
    Require (Test-Path $sourcePath) ('W7_RERUN_PRODUCER_MISSING ' + $relative)
    $property.Value = (Get-FileHash -Algorithm SHA256 $sourcePath).Hash.ToLowerInvariant()
}

$escapedRepo = $WslRepositoryPath.Replace("'", "'\"'\"'")
$gitHead = (& wsl.exe -d $Distro -- bash -lc "cd '$escapedRepo' && git rev-parse HEAD").Trim()
if ($LASTEXITCODE -ne 0) { throw 'W7_RERUN_GIT_HEAD_LOOKUP_FAILED' }
$evidence = [ordered]@{
    schema_version = 1
    experiment_id = 'OPENDITOO-WEBCAM-N980P-002'
    milestone = 'W7 rerun preparation after attempt-001 status-contract failure'
    status = 'pass'
    prepared_from_git_head = $gitHead
    correction = 'GET /v1/status is accepted by HTTP success plus exact identity validation and does not require the POST command-result ok field; POST routes still require ok=true.'
    build = [ordered]@{ release = 'pass'; warnings = 0; errors = 0; stage = $StageDir }
    checks = [ordered]@{
        adapter_selftest = 'pass'
        transform_selftest_cases = 15
        encoder_selftest_cases = 6
        real_host_status_selftest = 'pass'
        real_host_status_has_ok_field = $false
        exact_target = '11:75:58:CE:DE:C7'
    }
    operation = [ordered]@{ claim_created = $false; host_session_io = $false; device_io = $false }
    prior_attempt = [ordered]@{ experiment_id = 'OPENDITOO-WEBCAM-N980P-001'; outcome = 'not_opened'; frames = 0; tx_bytes = 0; replay_forbidden = $true }
}
$evidence | ConvertTo-Json -Depth 20 | Set-Content -Path $evidencePath -Encoding UTF8
$evidenceSha = (Get-FileHash -Algorithm SHA256 $evidencePath).Hash.ToLowerInvariant()

$doc.status = 'grant_ready_awaiting_named_grant'
$doc.readiness.execution_ready = $false
$doc.readiness.grant_ready = $true
$doc.readiness.blockers = @()
$doc.readiness.required_followup = 'Obtain the fresh exact grant `Grant OPENDITOO-WEBCAM-N980P-002`. Only after that grant: stop Runtime 003, verify Host idle, allow the camera-ready nonce claim handshake, and execute the single bounded 10-second W7 rerun. Never replay attempt 001.'
$doc.build.source_checkpoint = $gitHead + ' + Windows corrected-runner rebuild/freeze'
$doc.build.identity_note = 'Corrected runner rebuilt/staged and its C# status parser passed against the real read-only Day1 Host /v1/status contract, which has no ok field. Adapter/transform/encoder selftests also passed. Runtime 003 was neither rebuilt nor stopped and no Host session/device I/O occurred.'
$doc.adapter.deployment_state = 'PASS rerun preparation: corrected Windows runner rebuilt/staged; adapter/parity tests and real read-only Host status-contract selftest passed; no claim/session/device I/O.'
$doc | Add-Member -Force -NotePropertyName w7_rerun_preparation -NotePropertyValue ([pscustomobject]@{
    status = 'pass'
    evidence_file = 'captures/OPENDITOO-WEBCAM-W7-RERUN-PREPARATION-2026-09-09.json'
    evidence_sha256 = $evidenceSha
    real_host_status_selftest = $true
    status_has_ok_field = $false
    claim_created = $false
    host_session_io = $false
    device_io = $false
})
$doc | ConvertTo-Json -Depth 30 | Set-Content -Path $manifestPath -Encoding UTF8
$manifestSha = (Get-FileHash -Algorithm SHA256 $manifestPath).Hash.ToLowerInvariant()

# Re-enter WSL only for read-only/offline validation of the just-frozen manifest.
$validate = "cd '$escapedRepo' && python3 scripts/verify_day1_offline.py && python3 scripts/check_webcam_trial.py"
& wsl.exe -d $Distro -- bash -lc $validate
if ($LASTEXITCODE -ne 0) { throw 'W7_RERUN_WSL_OFFLINE_VALIDATION_FAILED' }

Write-Output ("W7_RERUN_PREP_PASS experiment_id=OPENDITOO-WEBCAM-N980P-002 manifest_sha256={0} evidence_sha256={1} claim_created=false host_session_io=false device_io=false" -f $manifestSha, $evidenceSha)
Write-Output 'W7_RERUN_NEXT_GRANT=Grant OPENDITOO-WEBCAM-N980P-002'
