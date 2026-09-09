param(
    [switch]$Apply,
    [switch]$Uninstall,
    [string]$WslDistro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName = 'OpenDitoo Product Runtime'
$HostTaskName = 'OpenDitoo Day1 Host'
$OpenTivooTaskName = 'OpenTivoo Product Runtime'
$WslExe = Join-Path $env:WINDIR 'System32\wsl.exe'

function Step([string]$Name, [string]$Value) { Write-Host "$Name=$Value" }
function Assert-SafeWslValue([string]$Value, [string]$Name) {
    if ($Value -notmatch '^[A-Za-z0-9._/-]+$') { throw "$Name contains unsupported shell characters." }
}
function Invoke-WslProduct([string]$Action) {
    $command = "cd $WslRepositoryPath && runtime/wsl/install_openditoo_product.sh $Action"
    & $WslExe -d $WslDistro -- bash -lc $command
    if ($LASTEXITCODE -ne 0) { throw "WSL product action '$Action' failed with exit $LASTEXITCODE." }
}

Assert-SafeWslValue $WslDistro 'WslDistro'
Assert-SafeWslValue $WslRepositoryPath 'WslRepositoryPath'
if (-not (Test-Path -LiteralPath $WslExe -PathType Leaf)) { throw "wsl.exe missing: $WslExe" }
if ($TaskName -eq $OpenTivooTaskName) { throw 'Task identity collision with OpenTivoo.' }

$hostTask = Get-ScheduledTask -TaskName $HostTaskName -ErrorAction SilentlyContinue
if ($null -eq $hostTask) { throw "Required Host task '$HostTaskName' is missing." }
$openTivooTask = Get-ScheduledTask -TaskName $OpenTivooTaskName -ErrorAction SilentlyContinue
Step 'OPENTIVOO_TASK' ($(if ($null -eq $openTivooTask) { 'not_observed' } else { 'preserved' }))
Step 'HOST_TASK' 'preserved'
Step 'PRODUCT_TASK' $TaskName
Step 'WSL_DISTRO' $WslDistro
Step 'WSL_REPOSITORY_PATH' $WslRepositoryPath
Step 'APPLY' $Apply.IsPresent.ToString().ToLowerInvariant()
Step 'UNINSTALL' $Uninstall.IsPresent.ToString().ToLowerInvariant()

$startCommand = "cd $WslRepositoryPath && runtime/wsl/install_openditoo_product.sh --start"
$taskArguments = "-d $WslDistro -- bash -lc `"$startCommand`""

if ($Uninstall) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        $actions = @($existing.Actions)
        if ($actions.Count -ne 1) { throw "Owned product task has unexpected action count; refusing removal." }
        $execute = [Environment]::ExpandEnvironmentVariables([string]$actions[0].Execute)
        $args = [string]$actions[0].Arguments
        if (-not ([IO.Path]::GetFullPath($execute)).Equals([IO.Path]::GetFullPath($WslExe), [StringComparison]::OrdinalIgnoreCase) -or
            $args -notlike '*install_openditoo_product.sh --start*') {
            throw "Task '$TaskName' is not the OpenDitoo-owned bootstrap; refusing removal."
        }
    }
    if (-not $Apply) {
        Step 'UNINSTALL_DRY_RUN' 'PASS_NO_CHANGES'
        exit 0
    }
    if ($null -ne $existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
    Invoke-WslProduct '--uninstall'
    Step 'PRODUCT_UNINSTALL' 'PASS'
    exit 0
}

# Product policy validation is read-only and performs zero device I/O.
$checkCommand = "cd $WslRepositoryPath && python3 cli/openditoo.py product-check --policy .openditoo-local/product-runtime-policy.json"
$checkOutput = @(& $WslExe -d $WslDistro -- bash -lc $checkCommand)
if ($LASTEXITCODE -ne 0) { throw 'Persistent product policy check failed.' }
$checkText = ($checkOutput -join "`n").Trim()
$check = $checkText | ConvertFrom-Json
if ($check.execution_ready -ne $true) { throw "Persistent product policy is not execution-ready: $checkText" }
Step 'PRODUCT_POLICY_CHECK' 'PASS'
Step 'EXACT_TARGET' ([string]$check.exact_unit_id)
Step 'AUTO_RECONNECT' ([string]$check.automatic_reconnect).ToLowerInvariant()
Step 'RECLAIM_STOCK' ([string]$check.reclaim_on_canvas_invalidated).ToLowerInvariant()

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $existing) { throw "Task '$TaskName' already exists; use the future refresh path or uninstall it first." }

if (-not $Apply) {
    Step 'INSTALL_DRY_RUN' 'PASS_NO_CHANGES'
    Step 'DEVICE_IO' 'false'
    exit 0
}

$prepared = $false
$registered = $false
try {
    Invoke-WslProduct '--prepare'
    $prepared = $true

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ([string]::IsNullOrWhiteSpace($identity) -or $identity -notmatch '\\') {
        throw 'Could not resolve fully-qualified current Windows account.'
    }
    $action = New-ScheduledTaskAction -Execute $WslExe -Argument $taskArguments
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::FromMinutes(2))
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings
    Register-ScheduledTask -TaskName $TaskName -InputObject $task -ErrorAction Stop | Out-Null
    $registered = $true
    Step 'SCHEDULED_TASK_USER' $identity

    # Starting this bootstrap may cause product device I/O; reaching this point requires
    # the explicit persistent product policy to have passed above.
    Start-ScheduledTask -TaskName $TaskName
    $deadline = [DateTime]::UtcNow.AddSeconds(12)
    $active = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $probe = @(& $WslExe -d $WslDistro -- bash -lc 'systemctl --user is-active openditoo-product.service 2>/dev/null || true')
        if (($probe -join '').Trim() -eq 'active') { $active = $true; break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $active) { throw 'OpenDitoo WSL product service did not become active.' }
    Step 'PRODUCT_SERVICE' 'ACTIVE'
    Step 'WINDOWS_STARTUP' 'AT_LOGON_START_WHEN_AVAILABLE'
    Step 'INSTALL_STATUS' 'PASS_PRODUCT_RUNTIME'
}
catch {
    $installError = $_
    if ($registered) {
        try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
    }
    if ($prepared) {
        try { Invoke-WslProduct '--rollback' } catch { Step 'ROLLBACK_WARNING' $_.Exception.Message }
    }
    throw $installError
}
