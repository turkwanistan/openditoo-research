param(
    [string]$StageDir = 'C:\temp\openditoo-webcam-runner',
    [string]$Distro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = Split-Path $PSScriptRoot -Parent
$project = Join-Path $repo 'runtime\windows\OpenDitoo.Webcam.Runner'
$manifestPath = Join-Path $repo 'experiments\DAY1-WEBCAM-N980P-006.json'
$transformFixture = Join-Path $repo 'tests\frame_transform_cases.json'
$encoderFixture = Join-Path $repo 'tests\ditoo_encoder_cases.json'
$release = Join-Path $project 'bin\Release\net8.0-windows10.0.19041.0'
$evidencePath = Join-Path $repo 'captures\OPENDITOO-WEBCAM-W9B-006-PREPARATION-2026-09-10.json'
function Require([bool]$Condition,[string]$Reason) { if (-not $Condition) { throw $Reason } }
Write-Output 'W9B_OPTICAL_PREP_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-006 device_io=false host_session_io=false claim_created=false'
$doc = Get-Content $manifestPath -Raw | ConvertFrom-Json
Require ($doc.experiment_id -eq 'OPENDITOO-WEBCAM-N980P-006') 'W9B_006_MANIFEST_ID_MISMATCH'
Require ($doc.authority.transmission_authorized -eq $false) 'W9B_006_PREP_REFUSES_PREAUTHORIZED_MANIFEST'
Require ($doc.authority.authorization_consumed -eq $false) 'W9B_006_PREP_REFUSES_CONSUMED_MANIFEST'
Require ($doc.stream.playback_interval_ms -eq 50) 'W9B_006_CLIENT_INTERVAL_DRIFT'
Require ($doc.session.min_frame_interval_ms -eq 40) 'W9B_006_HOST_FLOOR_DRIFT'
Require ($doc.budgets.max_frames -eq 201 -and $doc.budgets.max_application_packets -eq 603 -and $doc.budgets.max_tx_bytes -eq 211854) 'W9B_006_BUDGET_DRIFT'
& dotnet build (Join-Path $project 'OpenDitoo.Webcam.Runner.csproj') -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'W9B_006_RUNNER_BUILD_FAILED' }
if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir | Out-Null
Copy-Item (Join-Path $release '*') $StageDir -Recurse
$runner = Join-Path $StageDir 'OpenDitoo.Webcam.Runner.exe'
Require (Test-Path $runner) 'W9B_006_STAGED_RUNNER_MISSING'
$adapterLines = @(& $runner selftest); $adapterExit=$LASTEXITCODE
foreach ($line in $adapterLines) { Write-Output $line }
if ($adapterExit -ne 0) { throw 'W9B_006_ADAPTER_SELFTEST_FAILED' }
$adapterText=$adapterLines -join "`n"
Require ($adapterText -match 'ADAPTER_W8_40MS_ARRIVAL_JITTER_REPRO_PASS') 'W9B_006_40MS_FAILURE_REPRO_MISSING'
Require ($adapterText -match 'ADAPTER_W8_50MS_ARRIVAL_JITTER_PASS') 'W9B_006_50MS_MARGIN_PASS_MISSING'
Require ($adapterText -match 'ADAPTER_HOST_ELAPSED_CROSS_CLOCK_PASS') 'W9B_006_CROSS_CLOCK_TELEMETRY_PASS_MISSING'
Require ($adapterText -match 'ADAPTER_W9A_SOURCE_IDENTITY_PASS') 'W9B_006_SOURCE_IDENTITY_PASS_MISSING'
& $runner transform-selftest $transformFixture
if ($LASTEXITCODE -ne 0) { throw 'W9B_006_TRANSFORM_PARITY_FAILED' }
& $runner encoder-selftest $encoderFixture
if ($LASTEXITCODE -ne 0) { throw 'W9B_006_ENCODER_PARITY_FAILED' }
$statusLines=@(& $runner host-status-selftest $repo); $statusExit=$LASTEXITCODE
foreach ($line in $statusLines) { Write-Output $line }
if ($statusExit -ne 0) { throw 'W9B_006_LIVE_STATUS_SELFTEST_FAILED' }
$statusPass=$null
foreach ($line in $statusLines) { try { $item=$line|ConvertFrom-Json; if ($item.kind -eq 'host_status_selftest_pass') { $statusPass=$item } } catch {} }
Require ($null -ne $statusPass) 'W9B_006_LIVE_STATUS_PASS_RECORD_MISSING'
Require ($statusPass.target -eq '11:75:58:CE:DE:C7') 'W9B_006_LIVE_STATUS_TARGET_MISMATCH'
Require ($statusPass.device_io -eq $false -and $statusPass.host_session_io -eq $false) 'W9B_006_STATUS_SELFTEST_IO_BOUNDARY_BROKEN'
foreach ($property in $doc.stream.live_source.producer_code_sha256.PSObject.Properties) {
    $relative=$property.Name; $sourcePath=Join-Path $repo $relative.Replace('/',[IO.Path]::DirectorySeparatorChar)
    Require (Test-Path $sourcePath) ('W9B_006_PRODUCER_MISSING '+$relative)
    $property.Value=(Get-FileHash -Algorithm SHA256 $sourcePath).Hash.ToLowerInvariant()
}
$framingPath = Join-Path $repo 'captures\OPENDITOO-WEBCAM-W9B-FRAMING-VERIFICATION-2026-09-10.json'
Require (Test-Path $framingPath) 'W9B_006_FRAMING_EVIDENCE_MISSING'
$framing = Get-Content $framingPath -Raw | ConvertFrom-Json
Require ($framing.status -eq 'pass') 'W9B_006_FRAMING_NOT_PASS'
Require ($framing.monotonic -eq $true) 'W9B_006_FRAMING_SEQUENCE_NOT_MONOTONIC'
Require ($framing.operation.device_io -eq $false -and $framing.operation.claim_created -eq $false) 'W9B_006_FRAMING_IO_BOUNDARY_BROKEN'
$gitHeadLines=@(& wsl.exe -d $Distro -- git -C $WslRepositoryPath rev-parse HEAD)
if ($LASTEXITCODE -ne 0) { throw 'W9B_006_GIT_HEAD_LOOKUP_FAILED' }
$gitHead=($gitHeadLines|Select-Object -Last 1); Require (-not [string]::IsNullOrWhiteSpace($gitHead)) 'W9B_006_GIT_HEAD_EMPTY'; $gitHead=$gitHead.Trim()
$evidence=[ordered]@{
 schema_version=1; experiment_id='OPENDITOO-WEBCAM-N980P-006'; milestone='W9B optical/identity trial preparation'; status='pass'; prepared_from_git_head=$gitHead
 pacing=[ordered]@{session_profile='streaming_ack_clock';host_floor_ms=40;client_dispatch_floor_ms=50;arrival_jitter_margin_ms=10;rule='prior ACK required; client dispatch start >=50 ms after previous client dispatch; Host backstop remains 40 ms'}
 budgets=[ordered]@{lifetime_seconds=10;max_frames=201;max_application_packets=603;max_tx_bytes=211854}
 checks=[ordered]@{adapter_selftest='pass';unsafe_40ms_arrival_jitter_reproduced='pass';safe_50ms_arrival_jitter='pass';cross_clock_host_elapsed_telemetry='pass';source_identity_control='pass';transform_selftest_cases=15;encoder_selftest_cases=6;real_host_status_selftest='pass';operator_framing_verified='pass';exact_target='11:75:58:CE:DE:C7'}
 operation=[ordered]@{claim_created=$false;host_session_io=$false;device_io=$false}
}
$utf8NoBom=New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($evidencePath,($evidence|ConvertTo-Json -Depth 20),$utf8NoBom)
$evidenceSha=(Get-FileHash -Algorithm SHA256 $evidencePath).Hash.ToLowerInvariant()
$doc.status='grant_ready_awaiting_named_grant'
$doc.readiness.execution_ready=$false; $doc.readiness.grant_ready=$true; $doc.readiness.blockers=@()
$doc.readiness.required_followup='Obtain the fresh exact grant `Grant OPENDITOO-WEBCAM-N980P-006`. Then execute only scripts/run_webcam_w9b_optical_windows.ps1 once, with the operator filming. Never replay 002-005 and never create a rate ladder.'
$doc.build.source_checkpoint=$gitHead+' + Windows W8-005 runner rebuild/freeze'
$doc.build.identity_note='W9B-006 runner rebuilt/staged with W9A source identity. 40 ms failure reproduction, 50 ms pacing-margin control, cross-clock telemetry regression, W9A identity control, parity, and real read-only Host status checks passed. Transport unchanged from accepted 005. Host/Runtime 003 unchanged; no claim/session/device I/O.'
$doc.adapter.deployment_state='PASS W8-005 preparation: rebuilt/staged/frozen with 50 ms margin and corrected cross-clock telemetry semantics; no claim/session/device I/O.'
$doc|Add-Member -Force -NotePropertyName w9b_optical_preparation -NotePropertyValue ([pscustomobject]@{status='pass';evidence_file='captures/OPENDITOO-WEBCAM-W9B-006-PREPARATION-2026-09-10.json';evidence_sha256=$evidenceSha;unsafe_40ms_arrival_jitter_reproduced=$true;safe_50ms_arrival_jitter_pass=$true;cross_clock_host_elapsed_telemetry_pass=$true;source_identity_control_pass=$true;operator_framing_verified=$true;real_host_status_selftest=$true;claim_created=$false;host_session_io=$false;device_io=$false})
[System.IO.File]::WriteAllText($manifestPath,($doc|ConvertTo-Json -Depth 30),$utf8NoBom)
$manifestSha=(Get-FileHash -Algorithm SHA256 $manifestPath).Hash.ToLowerInvariant()
& wsl.exe -d $Distro -- python3 ($WslRepositoryPath + '/scripts/verify_day1_offline.py')
if ($LASTEXITCODE -ne 0) { throw 'W9B_006_WSL_OFFLINE_VALIDATION_FAILED_VERIFY' }
& wsl.exe -d $Distro -- python3 ($WslRepositoryPath + '/scripts/check_webcam_w9b_optical.py')
if ($LASTEXITCODE -ne 0) { throw 'W9B_006_WSL_OFFLINE_VALIDATION_FAILED_CHECK' }
Write-Output ("W9B_OPTICAL_PREP_PASS experiment_id=OPENDITOO-WEBCAM-N980P-006 manifest_sha256={0} evidence_sha256={1} claim_created=false host_session_io=false device_io=false" -f $manifestSha,$evidenceSha)
Write-Output 'W9B_OPTICAL_NEXT_GRANT=Grant OPENDITOO-WEBCAM-N980P-006'
