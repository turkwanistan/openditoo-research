param([string]$Distro = 'Ubuntu', [string]$Repo = '/home/wan/Projects/openditoo-research')
# Desktop shortcut for the W10C on-demand webcam. It only runs the launcher, which refuses before
# touching the dashboard unless the standing webcam policy is granted. Delete the .lnk to remove it.
$ErrorActionPreference = 'Stop'
$link = Join-Path ([Environment]::GetFolderPath('Desktop')) 'OpenDitoo Webcam.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $env:WINDIR 'System32\wsl.exe'
$shortcut.Arguments = "-d $Distro -- bash -lc `"$Repo/scripts/webcam_on_demand.sh; echo; read -rp 'Press Enter to close this window'`""
$shortcut.IconLocation = Join-Path $env:LOCALAPPDATA 'OpenDitoo\WebcamStudio\OpenDitoo.Webcam.Studio.exe'
$shortcut.Description = 'OpenDitoo live webcam on the Ditoo; close the Studio window to return to the MCP dashboard'
$shortcut.Save()
"WEBCAM_SHORTCUT_INSTALLED $link"
