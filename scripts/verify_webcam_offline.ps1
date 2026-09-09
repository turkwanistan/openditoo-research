param([switch]$CameraFaults)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$project = Join-Path $repo 'runtime\windows\OpenDitoo.Webcam.Probe'
& dotnet build (Join-Path $project 'OpenDitoo.Webcam.Probe.csproj') -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'Webcam build failed' }
# WinRT capture fails from a WSL share. Use a new local directory, preserving prior builds.
$staging = Join-Path ([IO.Path]::GetTempPath()) ('openditoo-webcam-check-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $staging | Out-Null
Copy-Item (Join-Path $project 'bin\Release\net8.0-windows10.0.19041.0\*') $staging -Recurse
$probe = Join-Path $staging 'OpenDitoo.Webcam.Probe.exe'
& $probe fault-selftest
if ($LASTEXITCODE -ne 0) { throw 'Fault selftest failed' }
& $probe transform-selftest (Join-Path $repo 'tests\frame_transform_cases.json')
if ($LASTEXITCODE -ne 0) { throw 'Transform parity failed' }
& $probe encoder-selftest (Join-Path $repo 'tests\ditoo_encoder_cases.json')
if ($LASTEXITCODE -ne 0) { throw 'Encoder parity failed' }
if ($CameraFaults) {
    foreach ($fault in @('none', 'camera_before_open', 'camera_mid_session', 'host_frame_fault', 'close_fault')) {
        $output = & $probe dryrun NV12 640 480 60 3 65 $fault
        $exitCode = $LASTEXITCODE
        $result = ($output -join "`n") | ConvertFrom-Json
        $expected = switch ($fault) {
            'camera_before_open' { 'not_opened' }
            'host_frame_fault' { 'unknown' }
            'close_fault' { 'unknown' }
            default { 'stopped_clean' }
        }
        $expectedExit = if ($expected -eq 'stopped_clean') { 0 } else { 2 }
        $expectedOpens = if ($fault -eq 'camera_before_open') { 0 } else { 1 }
        $expectedSends = switch ($fault) {
            'camera_before_open' { 0 }
            'host_frame_fault' { 2 }
            'none' { $result.sendAttempts }
            default { 1 }
        }
        if ($result.terminalOutcome -ne $expected -or $exitCode -ne $expectedExit -or
            $result.openAttempts -ne $expectedOpens -or $result.closeAttempts -ne $expectedOpens -or
            $result.sendAttempts -ne $expectedSends -or
            ($fault -eq 'none' -and $result.framesSent -lt 2) -or
            $result.queueDepth.maxRaw -gt 1 -or $result.queueDepth.maxReady -gt 1) {
            throw "Camera fault check failed: $fault $($output -join ' ')"
        }
        Write-Output "CAMERA_FAULT_PASS name=$fault opens=$($result.openAttempts) sends=$($result.sendAttempts) closes=$($result.closeAttempts) outcome=$($result.terminalOutcome)"
    }
}
Write-Output "WEBCAM_OFFLINE_PASS staging=$staging device_io=false"
