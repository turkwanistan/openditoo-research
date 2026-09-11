param(
    [string]$Repository = '\\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\.openditoo-local\worktrees\media-avrcp'
)
# Receive-only Runtime 017 acceptance through the production launch path: a NORMAL (unelevated) caller runs the
# elevated on-demand task and keeps its lease alive, exactly as the WSL product runtime will.
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
$task = [string]$broker.launch.task_name
$lease = [string]$broker.launch.lease_windows_path
$events = [string]$broker.events_windows_path
$sinkLog = [string]$broker.sink_log_windows_path

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
Need (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) `
    'Run from a NORMAL (non-Administrator) PowerShell: this acceptance proves the unelevated product path'
Step 'R017_ACCEPT_UNELEVATED_CALLER' 'PASS'

# Installed admin-only bytes and the registered task must match the policy exactly.
foreach ($group in 'raw_avrcp_broker_sha256', 'raw_avrcp_dependencies_sha256', 'button_probe_sha256') {
    foreach ($prop in $policy.build.$group.PSObject.Properties) {
        Need (Test-Path -LiteralPath $prop.Name -PathType Leaf) "missing: $($prop.Name) (run install_openditoo_raw_avrcp_task.ps1 elevated)"
        Need ((Hash $prop.Name) -eq [string]$prop.Value) "hash mismatch: $($prop.Name) (re-run the elevated installer)"
    }
}
$wslRepo = '/' + (($Repository -replace '^\\\\wsl(\.localhost|\$)\\[^\\]+\\', '') -replace '\\', '/')
& wsl.exe -d Ubuntu -- bash -lc "cd '$wslRepo' && python3 -m host.raw_avrcp_input verify-task product/OPENDITOO-PRODUCT-RUNTIME-017.json"
Need ($LASTEXITCODE -eq 0) 'registered task does not match the policy (re-run the elevated installer)'
Step 'R017_ACCEPT_PREFLIGHT' 'PASS'

$names = @('OpenDitoo.RawAvrcpBroker', 'OpenDitoo.ButtonProbe', 'btvs', 'tshark')
$before = @{}
foreach ($name in $names) { $before[$name] = @((Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })) }
$existing = @()
foreach ($name in $before.Keys) { foreach ($procId in @($before[$name])) { $existing += "$name`:$procId" } }
Step 'R017_ACCEPT_PREEXISTING_HELPERS' ($(if ($existing.Count -eq 0) { '0' } else { $existing -join ',' }))
Need (@($before['OpenDitoo.RawAvrcpBroker']).Count -eq 0) 'a raw AVRCP broker is already running; stop it first'

Read-Host 'Media must be PAUSED/OFF for now (you will start it after the broker owns media keys). Press ENTER' | Out-Null

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $lease) | Out-Null
Remove-Item -LiteralPath $events, $sinkLog -Force -ErrorAction SilentlyContinue
# Lease writer: a changing counter every second, like host/raw_avrcp_input.RawAvrcpBroker.ensure().
$leaseJob = Start-Job -ArgumentList $lease -ScriptBlock {
    param($Path) $i = 0
    while ($true) { $i++; [IO.File]::WriteAllText($Path, "$i`n"); Start-Sleep -Seconds 1 }
}
Start-Sleep -Seconds 2
& schtasks.exe /run /tn $task | Out-Null
Need ($LASTEXITCODE -eq 0) "unelevated caller could not run the task ($LASTEXITCODE)"
Step 'R017_ACCEPT_TASK_RUN_UNELEVATED' 'PASS'
$leaseStopped = $false
try {
    $ready = $false
    foreach ($i in 1..50) {
        if (@(Get-Content -LiteralPath $events -ErrorAction SilentlyContinue | Where-Object { $_ -match '"type":"broker_started"' }).Count -gt 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 200
    }
    Need $ready 'elevated broker did not start (check Task Scheduler history for the task)'
    $elevated = @(Get-Process -Name btvs -ErrorAction SilentlyContinue).Count -gt 0
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
        Start-Sleep -Milliseconds 2000
    }

    foreach ($i in 1..3) { Cue "DITOO LEFT $i/3 -- press once" }
    foreach ($i in 1..3) { Cue "DITOO RIGHT $i/3 -- press once" }
    foreach ($i in 1..8) { Cue "DITOO LEVER $i/8 -- pull once" }
    Cue 'TIVOO VOLUME-KNOB SHORT PRESS ONCE -- negative-control; must NOT become OpenDitoo input'
    Write-Host '*** HANDS OFF (the sidecar now exits by itself once the lease stops; ~15 s) ***' -ForegroundColor Green
    Start-Sleep -Seconds 2

    # Production safety property: with no lease updates the elevated sidecar must exit on its own.
    Stop-Job $leaseJob; $leaseStopped = $true
    $expired = $false
    foreach ($i in 1..100) {
        if (@(Get-Content -LiteralPath $events -ErrorAction SilentlyContinue | Where-Object { $_ -match 'lease_expired' }).Count -gt 0 -and
            @(Get-Process -Name OpenDitoo.RawAvrcpBroker -ErrorAction SilentlyContinue).Count -eq 0) { $expired = $true; break }
        Start-Sleep -Milliseconds 250
    }
}
finally {
    if (-not $leaseStopped) { Stop-Job $leaseJob -ErrorAction SilentlyContinue }
    Remove-Job $leaseJob -Force -ErrorAction SilentlyContinue
    if (@(Get-Process -Name OpenDitoo.RawAvrcpBroker -ErrorAction SilentlyContinue).Count -gt 0) { & schtasks.exe /end /tn $task | Out-Null }
    & wsl.exe -d Ubuntu -- bash -lc 'systemctl --user stop openditoo-product.service'
}
Start-Sleep -Seconds 1

$rows = @()
if (Test-Path -LiteralPath $events) {
    $rows = @(Get-Content -LiteralPath $events | ForEach-Object { if ($_) { $_ | ConvertFrom-Json } })
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
foreach ($name in $names) {
    $old = @($before[$name])
    foreach ($p in @(Get-Process -Name $name -ErrorAction SilentlyContinue)) {
        if ($old -notcontains $p.Id) { $orphans += "$name`:$($p.Id)" }
    }
}

Step 'R017_ACCEPT_ELEVATED_BTVS_RAN' "$elevated"
Step 'R017_ACCEPT_LEFT' "$left/3"
Step 'R017_ACCEPT_RIGHT' "$right/3"
Step 'R017_ACCEPT_LEVER' "$lever/8"
Step 'R017_ACCEPT_LEVER_PLAY' "$play"
Step 'R017_ACCEPT_LEVER_PAUSE' "$pause"
Step 'R017_ACCEPT_TOTAL_INPUT' ([string]$inputs.Count)
Step 'R017_ACCEPT_FOREIGN_HANDLE_IGNORED' "$foreign"
Step 'R017_ACCEPT_UNBOUND_OR_UNBIND' "$unbound"
Step 'R017_ACCEPT_STALE_BACKLOG_DROPPED' "$staleRows"
Step 'R017_ACCEPT_ETW_FLUSH' ($(if ($flushOk) { 'PASS' } else { 'MISSING' }))
Step 'R017_ACCEPT_LATENCY_MS_P50' "$latP50"
Step 'R017_ACCEPT_LATENCY_MS_MAX' "$latMax"
Step 'R017_ACCEPT_LEASE_EXPIRY_EXIT' ($(if ($expired) { 'PASS' } else { 'FAIL' }))
Step 'R017_ACCEPT_NEW_HELPER_ORPHANS' ($(if ($orphans.Count -eq 0) { '0' } else { $orphans -join ',' }))
$media = Read-Host 'Did the browser/media skip, pause, or otherwise react to ANY of those Ditoo controls? Enter YES or NO'
Step 'R017_ACCEPT_MEDIA_REACTION' $media.Trim().ToUpperInvariant()
if ($media.Trim().ToUpperInvariant() -ne 'NO') {
    Step 'R017_ACCEPT_MEDIA_REACTION_DETAIL' (Read-Host 'Which controls did media react to (Left/Right/Lever/Tivoo), and how?')
}

$pass = ($left -eq 3 -and $right -eq 3 -and $lever -eq 8 -and $inputs.Count -eq 14 -and $foreign -ge 1 -and $unbound -eq 0 -and
         $flushOk -and $latMax -ge 0 -and $latMax -le 500 -and $expired -and $orphans.Count -eq 0 -and
         $media.Trim().ToUpperInvariant() -eq 'NO')
Step 'R017_ACCEPT_RESULT' ($(if ($pass) { 'PASS' } else { 'FAIL_OR_OPERATOR_REVIEW' }))
