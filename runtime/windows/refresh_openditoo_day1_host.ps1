param(
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName = 'OpenDitoo Day1 Host'
$Port = 8796
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Project = Join-Path $RepoRoot 'runtime\windows\OpenDitoo.Day1.Host\OpenDitoo.Day1.Host.csproj'
$TokenFile = Join-Path $RepoRoot '.openditoo-local\host.token'
$WindowsRoot = Join-Path $env:LOCALAPPDATA 'OpenDitoo\Day1Host'
$InstalledExe = Join-Path $WindowsRoot 'OpenDitoo.Day1.Host.exe'
$Stage = Join-Path $env:TEMP ('OpenDitoo-Day1Host-Refresh-' + [Guid]::NewGuid().ToString('N'))
$Backup = Join-Path $env:TEMP ('OpenDitoo-Day1Host-Backup-' + [Guid]::NewGuid().ToString('N'))
$refreshSucceeded = $false
$updateStarted = $false

function Step([string]$Name, [string]$Value) { Write-Host "$Name=$Value" }

if ($Port -eq 8779) { throw 'OpenDitoo port collides with OpenTivoo.' }
if (-not (Get-Command dotnet.exe -ErrorAction SilentlyContinue)) { throw '.NET 8 SDK is required.' }
if (-not (Test-Path -LiteralPath $TokenFile -PathType Leaf)) { throw "OpenDitoo token is missing: $TokenFile" }
$token = (Get-Content -LiteralPath $TokenFile -Raw -Encoding utf8).Trim()
if ($token.Length -lt 32) { throw 'OpenDitoo token is too short.' }

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$actions = @($task.Actions)
if ($actions.Count -ne 1) { throw "Task '$TaskName' must have exactly one action." }
$actualExecute = [System.IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables([string]$actions[0].Execute))
$expectedExecute = [System.IO.Path]::GetFullPath($InstalledExe)
if (-not $actualExecute.Equals($expectedExecute, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Task '$TaskName' action does not match owned runtime. Expected '$expectedExecute'; got '$actualExecute'."
}
if (-not (Test-Path -LiteralPath $WindowsRoot -PathType Container)) { throw "Owned runtime root is missing: $WindowsRoot" }

$openTivooTask = Get-ScheduledTask -TaskName 'OpenTivoo Product Runtime' -ErrorAction SilentlyContinue
Step 'OPENTIVOO_TASK' ($(if ($null -eq $openTivooTask) { 'not_observed' } else { 'preserved' }))
Step 'TASK_NAME' $TaskName
Step 'HOST_PORT' $Port
Step 'OWNED_RUNTIME_ROOT' $WindowsRoot
Step 'APPLY' $Apply.IsPresent.ToString().ToLowerInvariant()

New-Item -ItemType Directory -Path $Stage -Force | Out-Null
try {
    & dotnet.exe publish $Project --nologo --configuration Release --output $Stage
    if ($LASTEXITCODE -ne 0) { throw 'OpenDitoo Host publish failed.' }
    $stagedExe = Join-Path $Stage 'OpenDitoo.Day1.Host.exe'
    if (-not (Test-Path -LiteralPath $stagedExe -PathType Leaf)) { throw 'Published Host executable missing.' }
    Step 'WINDOWS_BUILD' 'PASS'

    if (-not $Apply) {
        Write-Host 'REFRESH_DRY_RUN_PASS: existing task/runtime unchanged.'
        exit 0
    }

    New-Item -ItemType Directory -Path $Backup -Force | Out-Null
    Copy-Item -Path (Join-Path $WindowsRoot '*') -Destination $Backup -Recurse -Force
    $backupRoot = $Backup

    try {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $deadline = [DateTime]::UtcNow.AddSeconds(6)
        do {
            $owner = $null
            foreach ($line in @(& netstat.exe -ano -p tcp 2>$null)) {
                $parts = @(([string]$line).Trim() -split '\s+')
                if ($parts.Count -ge 5 -and $parts[0] -eq 'TCP' -and $parts[1] -eq "127.0.0.1:$Port" -and $parts[3] -eq 'LISTENING') {
                    $owner = [int]$parts[4]
                    break
                }
            }
            if ($null -eq $owner) { break }
            Start-Sleep -Milliseconds 150
        } while ([DateTime]::UtcNow -lt $deadline)
        if ($null -ne $owner) { throw "Port $Port remained owned by PID $owner after stopping only '$TaskName'; refusing process kill." }

        $updateStarted = $true
        Copy-Item -Path (Join-Path $Stage '*') -Destination $WindowsRoot -Recurse -Force
        Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop

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
            [int]$status.port -ne $Port -or $status.masterTransmitEnabled -ne $true -or
            $status.transportConfigured -ne $true -or $status.targetBound -ne $true -or
            $status.rawSendEnabled -ne $false -or -not (@($status.capabilities) -contains 'image-show')) {
            throw 'Refreshed OpenDitoo Host failed typed-image identity gate.'
        }
        $refreshSucceeded = $true
        Step 'REFRESH_STATUS' 'PASS_TYPED_IMAGE'
    }
    catch {
        $refreshError = $_
        try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
        if ($updateStarted) {
            Get-ChildItem -LiteralPath $WindowsRoot -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Copy-Item -Path (Join-Path $backupRoot '*') -Destination $WindowsRoot -Recurse -Force
            Step 'ROLLBACK_RUNTIME' 'RESTORED'
        }
        try { Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
        throw $refreshError
    }
}
finally {
    if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue }
    if ($refreshSucceeded -and (Test-Path -LiteralPath $Backup)) { Remove-Item -LiteralPath $Backup -Recurse -Force -ErrorAction SilentlyContinue }
    elseif ((-not $refreshSucceeded) -and (Test-Path -LiteralPath $Backup)) { Step 'ROLLBACK_BACKUP_PRESERVED' $Backup }
}
