param([string]$Distro='Ubuntu',[string]$WslRepositoryPath='/home/wan/Projects/openditoo-research')
$ErrorActionPreference='Stop'
Write-Output 'W8_RERUN_WINDOWS_LAUNCH_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-004'
if ($WslRepositoryPath -notmatch '^/[A-Za-z0-9._/-]+$') { throw 'W8R_WSL_REPOSITORY_PATH_INVALID' }
if ($Distro -notmatch '^[A-Za-z0-9._-]+$') { throw 'W8R_WSL_DISTRO_INVALID' }
& wsl.exe -d $Distro -- bash ($WslRepositoryPath + '/scripts/run_webcam_w8_rerun_once.sh')
$rc=$LASTEXITCODE
if ($rc -ne 0) { throw "W8_RERUN_WINDOWS_LAUNCH_FAILED exit_code=$rc" }
Write-Output 'W8_RERUN_WINDOWS_LAUNCH_PASS'
