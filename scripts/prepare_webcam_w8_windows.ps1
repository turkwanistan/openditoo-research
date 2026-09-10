param(
    [string]$StageDir = 'C:\temp\openditoo-webcam-runner',
    [string]$Distro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = Split-Path $PSScriptRoot -Parent
$project = Join-Path $repo 'runtime\windows\OpenDitoo.Webcam.Runner'
$manifestPath = Join-Path $repo 'experiments\DAY1-WEBCAM-N980P-003.json'
$transformFixture = Join-Path $repo 'tests\frame_transform_cases.json'
$encoderFixture = Join-Path $repo 'tests\ditoo_encoder_cases.json'
$release = Join-Path $project 'bin\Release\net8.0-windows10.0.19041.0'
$evidencePath = Join-Path $repo 'captures\OPENDITOO-WEBCAM-W8-PREPARATION-2026-09-09.json'

function Require([bool]$Condition, [string]$Reason) {
    if (-not $Condition) { throw $Reason }
}

Write-Output 'W8_PREP_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-003 device_io=false host_session_io=false claim_created=false'

$doc = Get-Content $manifestPath -Raw | ConvertFrom-Json
Require ($doc.experiment_id -eq 'OPENDITOO-WEBCAM-N980P-003') 'W8_MANIFEST_ID_MISMATCH'
Require ($doc.authority.transmission_authorized -eq $false) 'W8_PREP_REFUSES_PREAUTHORIZED_MANIFEST'
Require ($doc.authority.authorization_consumed -eq $false) 'W8_PREP_REFUSES_CONSUMED_MANIFEST'
Require ($doc.stream.playback_interval_ms -eq 40) 'W8_CLIENT_INTERVAL_DRIFT'
Require ($doc.session.min_frame_interval_ms -eq 40) 'W8_HOST_FLOOR_DRIFT'
Require ($doc.budgets.max_frames -eq 251 -and $doc.budgets.max_application_packets -eq 753 -and $doc.budgets.max_tx_bytes -eq 264554) 'W8_BUDGET_DRIFT'

& dotnet build (Join-Path $project 'OpenDitoo.Webcam.Runner.csproj') -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'W8_RUNNER_BUILD_FAILED' }

if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir | Out-Null
Copy-Item (Join-Path $release '*') $StageDir -Recurse
$runner = Join-Path $StageDir 'OpenDitoo.Webcam.Runner.exe'
Require (Test-Path $runner) 'W8_STAGED_RUNNER_MISSING'

$adapterLines = @(& $runner selftest)
$adapterExit = $LASTEXITCODE
foreach ($line in $adapterLines) { Write-Output $line }
if ($adapterExit -ne 0) { throw 'W8_ADAPTER_SELFTEST_FAILED' }
Require (($adapterLines -join "`n") -match 'ADAPTER_W8_ACK_FLOOR_PASS') 'W8_ACK_FLOOR_SELFTEST_MISSING'

& $runner transform-selftest $transformFixture
if ($LASTEXITCODE -ne 0) { throw 'W8_TRANSFORM_PARITY_FAILED' }
& $runner encoder-selftest $encoderFixture
if ($LASTEXITCODE -ne 0) { throw 'W8_ENCODER_PARITY_FAILED' }

# Read-only real Host identity/contract check. No session open and no device I/O.
$statusLines = @(& $runner host-status-selftest $repo)
$statusExit = $LASTEXITCODE
foreach ($line in $statusLines) { Write-Output $line }
if ($statusExit -ne 0) { throw ('W8_LIVE_STATUS_SELFTEST_FAILED ' + ($statusLines -join ' ')) }
$statusPass = $null
foreach ($line in $statusLines) {
    try {
        $item = $line | ConvertFrom-Json
        if ($item.kind -eq 'host_status_selftest_pass') { $statusPass = $item }
    } catch { }
}
Require ($null -ne $statusPass) 'W8_LIVE_STATUS_PASS_RECORD_MISSING'
Require ($statusPass.target -eq '11:75:58:CE:DE:C7') 'W8_LIVE_STATUS_TARGET_MISMATCH'
Require ($statusPass.device_io -eq $false -and $statusPass.host_session_io -eq $false) 'W8_STATUS_SELFTEST_IO_BOUNDARY_BROKEN'

# Freeze exact source + just-built binaries. Authority remains untouched.
foreach ($property in $doc.stream.live_source.producer_code_sha256.PSObject.Properties) {
    $relative = $property.Name
    $sourcePath = Join-Path $repo $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
    Require (Test-Path $sourcePath) ('W8_PRODUCER_MISSING ' + $relative)
    $property.Value = (Get-FileHash -Algorithm SHA256 $sourcePath).Hash.ToLowerInvariant()
}
$gitHeadLines = @(& wsl.exe -d $Distro -- git -C $WslRepositoryPath rev-parse HEAD)
if ($LASTEXITCODE -ne 0) { throw 'W8_GIT_HEAD_LOOKUP_FAILED' }
$gitHead = ($gitHeadLines | Select-Object -Last 1)
Require (-not [string]::IsNullOrWhiteSpace($gitHead)) 'W8_GIT_HEAD_EMPTY'
$gitHead = $gitHead.Trim()

$evidence = [ordered]@{
    schema_version = 1
    experiment_id = 'OPENDITOO-WEBCAM-N980P-003'
    milestone = 'W8 near-ceiling webcam preparation'
    status = 'pass'
    prepared_from_git_head = $gitHead
    pacing = [ordered]@{
        session_profile = 'streaming_ack_clock'
        host_floor_ms = 40
        client_dispatch_floor_ms = 40
        rule = 'one frame in flight; prior ACK required; dispatch start no earlier than 40 ms after previous dispatch start'
    }
    budgets = [ordered]@{ lifetime_seconds = 10; max_frames = 251; max_application_packets = 753; max_tx_bytes = 264554 }
    checks = [ordered]@{
        adapter_selftest = 'pass'
        fast_ack_40ms_floor_control = 'pass'
        transform_selftest_cases = 15
        encoder_selftest_cases = 6
        real_host_status_selftest = 'pass'
        exact_target = '11:75:58:CE:DE:C7'
    }
    telemetry = @('effectiveFps','framesByQuarter','fpsByQuarter','sourceAgeAtSendMsByQuarter','dispatchIntervalMs','ackMs','hostFrameMs','httpOverheadMs','duplicateSourceFrames','captured','processed','replaced','replacementPercent','rawQueueDepthMax','readyQueueDepthMax')
    operation = [ordered]@{ claim_created = $false; host_session_io = $false; device_io = $false }
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($evidencePath, ($evidence | ConvertTo-Json -Depth 20), $utf8NoBom)
$evidenceSha = (Get-FileHash -Algorithm SHA256 $evidencePath).Hash.ToLowerInvariant()

$doc.status = 'grant_ready_awaiting_named_grant'
$doc.readiness.execution_ready = $false
$doc.readiness.grant_ready = $true
$doc.readiness.blockers = @()
$doc.readiness.required_followup = 'Obtain the fresh exact grant `Grant OPENDITOO-WEBCAM-N980P-003`. Then execute only scripts/run_webcam_w8_windows.ps1 for one 10-second characterization. Never reuse W7 authority and never create a rate ladder.'
$doc.build.source_checkpoint = $gitHead + ' + Windows W8 runner rebuild/freeze'
$doc.build.identity_note = 'W8 runner rebuilt/staged; fast-ACK 40 ms pacing control, adapter/parity tests and real read-only Host status check passed. Deployed Host/Runtime 003 unchanged. No claim/session/device I/O occurred.'
$doc.adapter.deployment_state = 'PASS W8 preparation: corrected W8 runner rebuilt/staged and frozen; no claim/session/device I/O.'
$doc | Add-Member -Force -NotePropertyName w8_preparation -NotePropertyValue ([pscustomobject]@{
    status = 'pass'
    evidence_file = 'captures/OPENDITOO-WEBCAM-W8-PREPARATION-2026-09-09.json'
    evidence_sha256 = $evidenceSha
    fast_ack_40ms_floor_control = $true
    real_host_status_selftest = $true
    claim_created = $false
    host_session_io = $false
    device_io = $false
})
[System.IO.File]::WriteAllText($manifestPath, ($doc | ConvertTo-Json -Depth 30), $utf8NoBom)
$manifestSha = (Get-FileHash -Algorithm SHA256 $manifestPath).Hash.ToLowerInvariant()

& wsl.exe -d $Distro -- python3 ($WslRepositoryPath + '/scripts/verify_day1_offline.py')
if ($LASTEXITCODE -ne 0) { throw 'W8_WSL_OFFLINE_VALIDATION_FAILED_VERIFY' }
& wsl.exe -d $Distro -- python3 ($WslRepositoryPath + '/scripts/check_webcam_w8.py')
if ($LASTEXITCODE -ne 0) { throw 'W8_WSL_OFFLINE_VALIDATION_FAILED_CHECK' }

Write-Output ("W8_PREP_PASS experiment_id=OPENDITOO-WEBCAM-N980P-003 manifest_sha256={0} evidence_sha256={1} claim_created=false host_session_io=false device_io=false" -f $manifestSha, $evidenceSha)
Write-Output 'W8_NEXT_GRANT=Grant OPENDITOO-WEBCAM-N980P-003'
