param(
    [string]$Repository = '\\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\.openditoo-local\worktrees\media-avrcp',
    [ValidatePattern('^\d{3}$')][string]$Runtime = '018',
    [switch]$Uninstall
)
# One-time elevated install of a Runtime 017+ raw-AVRCP sidecar as an on-demand, highest-privilege scheduled task.
# Only this sidecar is elevated (BTVS requires it). Every file the task can launch is copied from a hash-verified
# source into an admin-only directory, and its arguments are fixed here from the committed policy, so the
# unelevated WSL runtime can only run the task and refresh its lease. Re-run after any broker rebuild.
# Each runtime has its own root + task (from its policy), so installing a successor never touches the bytes a
# live/rollback runtime's policy pins.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Step([string]$Name, [string]$Value) { Write-Host "$Name=$Value" }
function Need([bool]$Ok, [string]$Message) { if (-not $Ok) { throw $Message } }
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

$principalNow = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
Need ($principalNow.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Run from Administrator PowerShell'

$policy = Get-Content -LiteralPath (Join-Path $Repository "product\OPENDITOO-PRODUCT-RUNTIME-$Runtime.json") -Raw -Encoding UTF8 | ConvertFrom-Json
Need ($policy.authority.persistent_runtime_authorized -eq $false) "committed Runtime $Runtime template must remain unauthorized"
$broker = $policy.pagination.broker
$launch = $broker.launch
$task = [string]$launch.task_name
$root = [string]$launch.install_root
Need ($launch.kind -eq 'scheduled_task_highest_on_demand' -and $task -like 'OpenDitoo Raw AVRCP Broker*') 'policy launch mismatch'
Need ($root -match '^C:\\Program Files\\OpenDitoo\\RawAvrcpBroker\d*$') "install root must be admin-only under Program Files: $root"

if ($Uninstall) {
    Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
    Step "R${Runtime}_TASK_UNINSTALLED" 'PASS'
    exit 0
}

$build = Join-Path $Repository 'runtime\windows\OpenDitoo.RawAvrcpBroker\bin\Release\net8.0-windows10.0.19041.0'
function Source([string]$Dest) {
    $rel = $Dest.Substring($root.Length + 1)
    if ($rel.StartsWith('sink\')) { return Join-Path ([string]$launch.sources.sink) $rel.Substring(5) }
    if ($rel -eq 'btvs\btvs.exe') { return [string]$launch.sources.btvs }
    return Join-Path $build $rel
}
$pins = @{}
foreach ($group in 'raw_avrcp_broker_sha256', 'raw_avrcp_dependencies_sha256') {
    foreach ($prop in $policy.build.$group.PSObject.Properties) {
        if ($prop.Name.StartsWith("$root\")) { $pins[$prop.Name] = [string]$prop.Value }
    }
}
Need ($pins.Count -eq 11) "expected 11 admin-only files, policy pins $($pins.Count)"
foreach ($launched in @($broker.exe, $broker.sink_exe, $broker.btvs_exe)) {
    Need ($pins.ContainsKey([string]$launched)) "launched executable is not pinned under the admin-only root: $launched"
}

# Verify every source before touching the install root.
foreach ($dest in $pins.Keys) {
    $src = Source $dest
    Need (Test-Path -LiteralPath $src -PathType Leaf) "source missing: $src"
    Need ((Hash $src) -eq $pins[$dest]) "source hash mismatch: $src (build/stage the frozen bytes first)"
}
Step "R${Runtime}_TASK_SOURCES_VERIFIED" "$($pins.Count)"

Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
foreach ($dest in $pins.Keys) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath (Source $dest) -Destination $dest
}
foreach ($dest in $pins.Keys) { Need ((Hash $dest) -eq $pins[$dest]) "installed hash mismatch: $dest" }

# The whole point: nothing the elevated task launches may be writable by a non-admin.
$writeMask = 2 -bor 4 -bor 0x10000 -bor 0x40000 -bor 0x80000 -bor 0x40000000 -bor 0x10000000
$trusted = '^(NT AUTHORITY\\SYSTEM|BUILTIN\\Administrators|NT SERVICE\\TrustedInstaller|CREATOR OWNER)$'
foreach ($item in @((Get-Item -LiteralPath $root)) + @(Get-ChildItem -LiteralPath $root -Recurse)) {
    $writers = @((Get-Acl -LiteralPath $item.FullName).Access | Where-Object {
        $_.AccessControlType -eq 'Allow' -and ([int64]$_.FileSystemRights -band $writeMask) -ne 0 -and
        $_.IdentityReference.Value -notmatch $trusted })
    Need ($writers.Count -eq 0) "non-admin write access on $($item.FullName): $(($writers | ForEach-Object { $_.IdentityReference.Value }) -join ',')"
}
Step "R${Runtime}_TASK_INSTALL_ROOT_ADMIN_ONLY" 'PASS'

$selftest = & (Join-Path $root 'OpenDitoo.RawAvrcpBroker.exe') --selftest | Out-String
Need ($LASTEXITCODE -eq 0 -and $selftest -match 'RAW_AVRCP_BROKER_SELFTEST=PASS') "installed broker selftest failed: $selftest"
Step "R${Runtime}_TASK_INSTALLED_SELFTEST" 'PASS'

# Must match host/raw_avrcp_input.task_arguments exactly (checked by `python3 -m host.raw_avrcp_input verify-task`).
$values = @('--seconds', '0', '--target', [string]$policy.target.exact_unit_id,
    '--events', [string]$broker.events_windows_path, '--sink-log', [string]$broker.sink_log_windows_path,
    '--sink-exe', [string]$broker.sink_exe, '--btvs', [string]$broker.btvs_exe, '--tshark', [string]$broker.tshark_exe,
    '--port', [string]$broker.port, '--lease', [string]$launch.lease_windows_path)
foreach ($v in $values) { Need (-not $v.Contains('"') -and -not $v.EndsWith('\')) "unquotable task argument: $v" }
$arguments = ($values | ForEach-Object { '"' + $_ + '"' }) -join ' '

$user = (Get-CimInstance Win32_ComputerSystem).UserName
Need (-not [string]::IsNullOrWhiteSpace($user)) 'no interactive console user to run the task as'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent ([string]$launch.lease_windows_path)) | Out-Null
$action = New-ScheduledTaskAction -Execute ([string]$broker.exe) -Argument $arguments -WorkingDirectory $root
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings -Force `
    -Description "OpenDitoo Runtime $Runtime receive-only raw AVRCP sidecar (BTVS needs elevation). On demand only; exits when the WSL lease stops." | Out-Null
Step "R${Runtime}_TASK_REGISTERED" "$task as $user"
Step "R${Runtime}_TASK_INSTALL" 'PASS'
