param(
    [switch]$Apply,
    [string]$WslDistro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName = 'OpenDitoo Day1 Host'
$Port = 8796
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.Day1.Host\OpenDitoo.Day1.Host.csproj'
$Local = Join-Path $RepoRoot '.openditoo-local'
$TokenFile = Join-Path $Local 'host.token'
$WindowsRoot = Join-Path $env:LOCALAPPDATA 'OpenDitoo\Day1Host'
$Stage = Join-Path $env:TEMP ('OpenDitoo-Day1Host-' + [Guid]::NewGuid().ToString('N'))

function Step([string]$Name, [string]$Value) { Write-Host "$Name=$Value" }

if ($TaskName -eq 'OpenTivoo Product Runtime') { throw 'Task identity collision with OpenTivoo.' }
if ($Port -eq 8779) { throw 'Port identity collision with OpenTivoo.' }
if (-not (Get-Command dotnet.exe -ErrorAction SilentlyContinue)) { throw '.NET 8 SDK is required.' }
$sdks = @(& dotnet.exe --list-sdks)
if ($LASTEXITCODE -ne 0 -or -not ($sdks | Where-Object { $_ -match '^8\.' })) { throw '.NET 8 SDK is required.' }
if (-not (Test-Path -LiteralPath $TokenFile -PathType Leaf)) {
    throw "OpenDitoo token is missing: $TokenFile. Run 'python3 cli/openditoo.py auth-init' through WSL_MCP first."
}
$token = (Get-Content -LiteralPath $TokenFile -Raw -Encoding utf8).Trim()
if ($token.Length -lt 32) { throw 'OpenDitoo token is too short.' }

# Environment setup must never interfere with OpenTivoo. Observe ownership only.
$TivooOwner = $null
$DitooOwner = $null
foreach ($line in @(& netstat.exe -ano -p tcp 2>$null)) {
    $parts = @(([string]$line).Trim() -split '\s+')
    if ($parts.Count -ge 5 -and $parts[0] -eq 'TCP' -and $parts[3] -eq 'LISTENING') {
        if ($parts[1] -eq '127.0.0.1:8779') { $TivooOwner = [int]$parts[4] }
        if ($parts[1] -eq "127.0.0.1:$Port") { $DitooOwner = [int]$parts[4] }
    }
}
Step 'OPENTIVOO_8779_OBSERVED_PID' ($(if ($null -eq $TivooOwner) { 'none' } else { $TivooOwner }))
Step 'OPENDITOO_8796_OBSERVED_PID' ($(if ($null -eq $DitooOwner) { 'none' } else { $DitooOwner }))
if ($null -ne $DitooOwner) {
    throw "Port $Port is already in use by PID $DitooOwner; refusing ambiguous replacement."
}

New-Item -ItemType Directory -Path $Stage -Force | Out-Null
try {
    & dotnet.exe publish $Project --nologo --configuration Release --output $Stage
    if ($LASTEXITCODE -ne 0) { throw 'OpenDitoo Day1 Host publish failed.' }
    $HostExe = Join-Path $Stage 'OpenDitoo.Day1.Host.exe'
    if (-not (Test-Path -LiteralPath $HostExe -PathType Leaf)) { throw 'Published OpenDitoo Host executable missing.' }
    Step 'WINDOWS_BUILD' 'PASS'
    Step 'TASK_NAME' $TaskName
    Step 'HOST_PORT' $Port
    Step 'WINDOWS_RUNTIME_ROOT' $WindowsRoot
    Step 'WSL_REPOSITORY_PATH' $WslRepositoryPath
    Step 'DEVICE_IO' 'false'
    Step 'BLUETOOTH_CONFIGURED' 'false'
    Step 'TARGET_BOUND' 'false'
    Step 'APPLY' $Apply.IsPresent.ToString().ToLowerInvariant()

    if (-not $Apply) {
        Write-Host 'DRY_RUN_PASS: no task/process/settings/device changes made.'
        exit 0
    }

    if (Get-ScheduledTask -TaskName 'OpenTivoo Product Runtime' -ErrorAction SilentlyContinue) {
        Step 'OPENTIVOO_TASK' 'preserved'
    }
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        throw "Task '$TaskName' already exists; refusing replacement without a separately reviewed ownership/update path."
    }

    New-Item -ItemType Directory -Path $WindowsRoot -Force | Out-Null
    Copy-Item -Path (Join-Path $Stage '*') -Destination $WindowsRoot -Recurse -Force
    $InstalledExe = Join-Path $WindowsRoot 'OpenDitoo.Day1.Host.exe'
    $action = New-ScheduledTaskAction -Execute $InstalledExe -Argument ('--token-file "' + $TokenFile + '"')
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    Start-ScheduledTask -TaskName $TaskName

    $deadline = [DateTime]::UtcNow.AddSeconds(8)
    $status = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $headers = @{ Authorization = "Bearer $token"; Accept = 'application/json' }
            $status = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:$Port/v1/status" -Headers $headers -TimeoutSec 1
            break
        } catch { Start-Sleep -Milliseconds 200 }
    }
    if ($null -eq $status -or [string]$status.service -ne 'OpenDitoo Day1 Host' -or
        [int]$status.port -ne $Port -or $status.masterTransmitEnabled -ne $false -or
        $status.bluetoothTouched -ne $false -or $status.transportConfigured -ne $false -or
        $status.targetBound -ne $false) {
        throw 'Installed OpenDitoo Host failed its exact status-only identity gate.'
    }
    Step 'INSTALL_STATUS' 'PASS_STATUS_ONLY'
} finally {
    if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue }
}
