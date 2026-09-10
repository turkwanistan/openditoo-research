# Switch the existing 'OpenDitoo Day1 Host' task to a headless console launch and restart it.
# Same installed exe, arguments, trigger and principal; only the launcher changes (conhost --headless),
# so the Host has no window that can be closed. No binary change, so no policy hash moves.
$ErrorActionPreference = 'Stop'
$TaskName = 'OpenDitoo Day1 Host'
$InstalledExe = Join-Path $env:LOCALAPPDATA 'OpenDitoo\Day1Host\OpenDitoo.Day1.Host.exe'
$conhost = Join-Path $env:WINDIR 'System32\conhost.exe'
$task = Get-ScheduledTask -TaskName $TaskName
$current = @($task.Actions)[0]
if ($current.Execute -ieq $conhost) { 'HOST_TASK_ALREADY_HEADLESS'; exit 0 }
if ([System.IO.Path]::GetFullPath($current.Execute) -ne [System.IO.Path]::GetFullPath($InstalledExe)) { throw 'HOST_TASK_ACTION_NOT_OWNED' }
$action = New-ScheduledTaskAction -Execute $conhost -Argument ('--headless "' + $InstalledExe + '" ' + $current.Arguments)
Set-ScheduledTask -TaskName $TaskName -Action $action | Out-Null
Stop-ScheduledTask -TaskName $TaskName
Get-Process OpenDitoo.Day1.Host -ErrorAction SilentlyContinue | Where-Object { $_.Path -ieq $InstalledExe } |
    ForEach-Object { $_.CloseMainWindow() | Out-Null; if (-not $_.WaitForExit(8000)) { throw 'HOST_DID_NOT_STOP' } }
Start-ScheduledTask -TaskName $TaskName
'HOST_TASK_HEADLESS_APPLIED'
