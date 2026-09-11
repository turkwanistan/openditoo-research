param(
    [string]$Repository = '\\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\.openditoo-local\worktrees\media-avrcp'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Step([string]$Name, [string]$Value) { Write-Host "$Name=$Value" }
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Need([bool]$Ok, [string]$Message) { if (-not $Ok) { throw $Message } }

$policyPath = Join-Path $Repository 'product\OPENDITOO-PRODUCT-RUNTIME-017.json'
Need (Test-Path -LiteralPath $policyPath -PathType Leaf) "Runtime 017 policy missing: $policyPath"
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json
Need ($policy.runtime_revision -eq 12) 'Runtime 017 revision mismatch'
Need ($policy.authority.persistent_runtime_authorized -eq $false) 'Committed Runtime 017 template must remain unauthorized'

$broker = $policy.pagination.broker
$out = Join-Path $Repository 'runtime\windows\OpenDitoo.RawAvrcpBroker\bin\Release\net8.0-windows10.0.19041.0'
$exe = Join-Path $out 'OpenDitoo.RawAvrcpBroker.exe'
Need (Test-Path -LiteralPath $exe -PathType Leaf) 'Raw AVRCP broker Release build missing; build it first'

# Freeze-check the exact built broker by leaf name against the policy's staged-destination map.
$expectedBroker = @{}
foreach ($prop in $policy.build.raw_avrcp_broker_sha256.PSObject.Properties) {
    $expectedBroker[[IO.Path]::GetFileName($prop.Name)] = [string]$prop.Value
}
foreach ($name in $expectedBroker.Keys) {
    $path = Join-Path $out $name
    Need (Test-Path -LiteralPath $path -PathType Leaf) "broker output missing: $path"
    Need ((Hash $path) -eq $expectedBroker[$name]) "broker hash mismatch: $name"
}

# Freeze-check capture dependencies and the accepted ButtonProbe ownership sink.
foreach ($prop in $policy.build.raw_avrcp_dependencies_sha256.PSObject.Properties) {
    Need (Test-Path -LiteralPath $prop.Name -PathType Leaf) "dependency missing: $($prop.Name)"
    Need ((Hash $prop.Name) -eq [string]$prop.Value) "dependency hash mismatch: $($prop.Name)"
}
foreach ($prop in $policy.build.button_probe_sha256.PSObject.Properties) {
    Need (Test-Path -LiteralPath $prop.Name -PathType Leaf) "ButtonProbe missing: $($prop.Name)"
    Need ((Hash $prop.Name) -eq [string]$prop.Value) "ButtonProbe hash mismatch: $($prop.Name)"
}

& $exe --selftest
Need ($LASTEXITCODE -eq 0) 'Raw AVRCP broker selftest failed'
Step 'R017_ACCEPT_PREFLIGHT' 'PASS'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Need $isAdmin 'BTVS requires elevation on this machine; reopen PowerShell as Administrator and rerun this harness'
Step 'R017_ACCEPT_ELEVATED' 'PASS'

$before = @{}
foreach ($name in @('OpenDitoo.RawAvrcpBroker','OpenDitoo.ButtonProbe','btvs','tshark')) {
    $before[$name] = @((Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object { $_.Id }))
}
$existing = @()
foreach ($name in $before.Keys) { foreach ($procId in @($before[$name])) { $existing += "$name`:$procId" } }
Step 'R017_ACCEPT_PREEXISTING_HELPERS' ($(if ($existing.Count -eq 0) { '0' } else { $existing -join ',' }))

Read-Host 'Media must be PAUSED/OFF for now (you will start it after the broker owns media keys). Press ENTER' | Out-Null

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmssZ')
$events = Join-Path $env:TEMP "openditoo-r017-raw-input-$stamp.ndjson"
$sinkLog = Join-Path $env:TEMP "openditoo-r017-sink-$stamp.ndjson"
Remove-Item -LiteralPath $events,$sinkLog -Force -ErrorAction SilentlyContinue

$brokerArgs = @(
    '--seconds','0',  # unbounded: the harness stops the broker in finally
    '--target',[string]$policy.target.exact_unit_id,
    '--events',$events,
    '--sink-log',$sinkLog,
    '--sink-exe',[string]$broker.sink_exe,
    '--btvs',[string]$broker.btvs_exe,
    '--tshark',[string]$broker.tshark_exe,
    '--port',[string]$broker.port
)
# Windows PowerShell 5.1 lacks ProcessStartInfo.ArgumentList. Build one
# CreateProcess-safe command line instead; every argument is quoted and embedded
# backslashes/quotes are escaped with the standard Windows argv rules.
function Quote-WindowsArg([string]$Value) {
    if ($Value.Length -eq 0) { return '""' }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"')
    $slashes = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ($ch -eq '\') { $slashes++; continue }
        if ($ch -eq '"') {
            [void]$sb.Append(('\' * ($slashes * 2 + 1)))
            [void]$sb.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) { [void]$sb.Append(('\' * $slashes)); $slashes = 0 }
        [void]$sb.Append($ch)
    }
    if ($slashes -gt 0) { [void]$sb.Append(('\' * ($slashes * 2))) }
    [void]$sb.Append('"')
    return $sb.ToString()
}
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$brokerStdout = Join-Path $env:TEMP "openditoo-r017-broker-$stamp.stdout.log"
$brokerStderr = Join-Path $env:TEMP "openditoo-r017-broker-$stamp.stderr.log"
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.Arguments = (($brokerArgs | ForEach-Object { Quote-WindowsArg ([string]$_) }) -join ' ')
$proc = [System.Diagnostics.Process]::Start($psi)
Need ($null -ne $proc) 'failed to start raw AVRCP broker process'
try {
    $ready = $false
    foreach ($i in 1..30) {
        if ($proc.HasExited) {
            $stdoutText = $proc.StandardOutput.ReadToEnd()
            $stderrText = $proc.StandardError.ReadToEnd()
            if ($stdoutText) { $stdoutText | Set-Content -LiteralPath $brokerStdout -Encoding UTF8; Write-Host "BROKER_STDOUT=$stdoutText" }
            if ($stderrText) { $stderrText | Set-Content -LiteralPath $brokerStderr -Encoding UTF8; Write-Host "BROKER_STDERR=$stderrText" }
            Write-Host "R017_ACCEPT_BROKER_STDOUT_FILE=$brokerStdout"
            Write-Host "R017_ACCEPT_BROKER_STDERR_FILE=$brokerStderr"
            throw "broker exited during startup: $($proc.ExitCode)"
        }
        if (Test-Path -LiteralPath $events) {
            $first = Get-Content -LiteralPath $events -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($first -match 'broker_started') { $ready = $true; break }
        }
        Start-Sleep -Milliseconds 200
    }
    Need $ready 'broker did not become ready'
    Step 'R017_ACCEPT_BROKER_READY' 'PASS'

    # The broker learns the Ditoo ACL handle only from OpenDitoo's own image frames. Standalone acceptance has
    # no product running, so briefly run the accepted Runtime 016 (hands off) to send frames, then stop it so its
    # mirror-mode ButtonProbe cannot compete during the cues. RFCOMM closes; the ACL link and binding remain.
    Write-Host '*** HANDS OFF: RUNTIME 016 BRIEFLY SENDS FRAMES SO THE BROKER CAN LEARN THE DITOO LINK ***' -ForegroundColor Cyan
    & wsl.exe -d Ubuntu -- bash -lc 'systemctl --user start openditoo-product.service'
    $bound = $false
    foreach ($i in 1..60) {
        if (@(Get-Content -LiteralPath $events -ErrorAction SilentlyContinue | Where-Object { $_ -match '"type":"handle_bound"' }).Count -gt 0) { $bound = $true; break }
        Start-Sleep -Milliseconds 250
    }
    Start-Sleep -Seconds 2
    & wsl.exe -d Ubuntu -- bash -lc 'systemctl --user stop openditoo-product.service'
    Need $bound 'broker did not learn the Ditoo ACL handle from Runtime 016 frames'
    Step 'R017_ACCEPT_HANDLE_BOUND' 'PASS'
    # The broker starts its Playing ownership sink on first bind; the product order is sink first, media later.
    $sinkUp = $false
    foreach ($i in 1..40) {
        if (@(Get-Content -LiteralPath $sinkLog -ErrorAction SilentlyContinue | Where-Object { $_ -match '"type":"probe_started"' }).Count -gt 0) { $sinkUp = $true; break }
        Start-Sleep -Milliseconds 250
    }
    Need $sinkUp 'ownership sink did not start after bind'
    Step 'R017_ACCEPT_SINK_AFTER_BIND' 'PASS'
    Read-Host 'Now start media playing through the EDIFIER. Press ENTER when it is definitely playing' | Out-Null

    function Cue([string]$Text) {
        Write-Host "*** $Text ***" -ForegroundColor Yellow
        Start-Sleep -Milliseconds 2400
    }

    foreach ($i in 1..5) { Cue "DITOO LEFT $i/5 -- press once" }
    foreach ($i in 1..5) { Cue "DITOO RIGHT $i/5 -- press once" }
    foreach ($i in 1..20) { Cue "DITOO LEVER $i/20 -- pull once" }
    Cue 'TIVOO VOLUME-KNOB SHORT PRESS 1/2 -- negative-control; must NOT become OpenDitoo input'
    Cue 'TIVOO VOLUME-KNOB SHORT PRESS 2/2'
    Write-Host '*** HANDS OFF ***' -ForegroundColor Green
    Start-Sleep -Seconds 2
}
finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        try { $proc.WaitForExit(5000) | Out-Null } catch {}
    }
}

Start-Sleep -Seconds 1
$rows = @()
if (Test-Path -LiteralPath $events) {
    $rows = @(Get-Content -LiteralPath $events | ForEach-Object { if ($_){ $_ | ConvertFrom-Json } })
}
$inputs = @($rows | Where-Object { $_.type -eq 'event' -and $_.source -eq 'avrcp_raw' })
$left = @($inputs | Where-Object { $_.normalized_candidate -eq 'nav_left' }).Count
$right = @($inputs | Where-Object { $_.normalized_candidate -eq 'nav_right' }).Count
$lever = @($inputs | Where-Object { $_.normalized_candidate -eq 'lever_candidate' }).Count
$play = @($inputs | Where-Object { $_.operation -eq '0x44' }).Count
$pause = @($inputs | Where-Object { $_.operation -eq '0x46' }).Count
$foreign = @($rows | Where-Object { $_.type -eq 'ignored_foreign_handle' }).Count
$boundSeq = @($rows | Where-Object { $_.type -eq 'handle_bound' } | ForEach-Object { [long]$_.seq } | Select-Object -First 1)
$unbound = @($rows | Where-Object { $_.type -eq 'handle_unbound' -or ($_.type -eq 'ignored_unbound' -and $boundSeq.Count -gt 0 -and [long]$_.seq -gt $boundSeq[0]) }).Count
$staleRows = (@($rows | Where-Object { $_.type -eq 'stale_backlog_dropped' } | ForEach-Object { [long]$_.rows }) | Measure-Object -Sum).Sum
$flushOk = @($rows | Where-Object { $_.type -eq 'etw_flush_ok' }).Count -gt 0
$latency = @($inputs | ForEach-Object {
    ([DateTimeOffset]::Parse($_.at_utc).ToUnixTimeMilliseconds() - [double]::Parse($_.capture_time_epoch, [Globalization.CultureInfo]::InvariantCulture) * 1000)
} | Sort-Object)
$latP50 = if ($latency.Count) { [int]$latency[[int][Math]::Floor(($latency.Count - 1) / 2)] } else { -1 }
$latMax = if ($latency.Count) { [int]$latency[-1] } else { -1 }

$orphans = @()
foreach ($name in @('OpenDitoo.RawAvrcpBroker','OpenDitoo.ButtonProbe','btvs','tshark')) {
    $old = @($before[$name])
    foreach ($p in @(Get-Process -Name $name -ErrorAction SilentlyContinue)) {
        if ($old -notcontains $p.Id) { $orphans += "$name`:$($p.Id)" }
    }
}

Step 'R017_ACCEPT_LEFT' "$left/5"
Step 'R017_ACCEPT_RIGHT' "$right/5"
Step 'R017_ACCEPT_LEVER' "$lever/20"
Step 'R017_ACCEPT_LEVER_PLAY' "$play"
Step 'R017_ACCEPT_LEVER_PAUSE' "$pause"
Step 'R017_ACCEPT_TOTAL_INPUT' ([string]$inputs.Count)
Step 'R017_ACCEPT_FOREIGN_HANDLE_IGNORED' "$foreign"
Step 'R017_ACCEPT_UNBOUND_OR_UNBIND' "$unbound"
Step 'R017_ACCEPT_STALE_BACKLOG_DROPPED' "$staleRows"
Step 'R017_ACCEPT_ETW_FLUSH' ($(if ($flushOk) { 'PASS' } else { 'MISSING' }))
Step 'R017_ACCEPT_LATENCY_MS_P50' "$latP50"
Step 'R017_ACCEPT_LATENCY_MS_MAX' "$latMax"
Step 'R017_ACCEPT_NEW_HELPER_ORPHANS' ($(if ($orphans.Count -eq 0) { '0' } else { $orphans -join ',' }))
Step 'R017_ACCEPT_EVENTS_FILE' $events
Step 'R017_ACCEPT_SINK_FILE' $sinkLog
$media = Read-Host 'Did the browser/media skip, pause, or otherwise react to ANY of those Ditoo controls? Enter YES or NO'
Step 'R017_ACCEPT_MEDIA_REACTION' $media.Trim().ToUpperInvariant()
if ($media.Trim().ToUpperInvariant() -ne 'NO') {
    Step 'R017_ACCEPT_MEDIA_REACTION_DETAIL' (Read-Host 'Which controls did media react to (Left/Right/Lever/Tivoo), and how?')
}

$pass = ($left -eq 5 -and $right -eq 5 -and $lever -eq 20 -and $inputs.Count -eq 30 -and $foreign -ge 1 -and $unbound -eq 0 -and $flushOk -and $latMax -ge 0 -and $latMax -le 500 -and $orphans.Count -eq 0 -and $media.Trim().ToUpperInvariant() -eq 'NO')
Step 'R017_ACCEPT_RESULT' ($(if ($pass) { 'PASS' } else { 'FAIL_OR_OPERATOR_REVIEW' }))
