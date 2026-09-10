param([string]$Distro='Ubuntu',[string]$WslRepositoryPath='/home/wan/Projects/openditoo-research')
$ErrorActionPreference='Stop'
Write-Output 'W9B_OPTICAL_WINDOWS_LAUNCH_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-007'
if ($WslRepositoryPath -notmatch '^/[A-Za-z0-9._/-]+$') { throw 'W9BR_WSL_REPOSITORY_PATH_INVALID' }
if ($Distro -notmatch '^[A-Za-z0-9._-]+$') { throw 'W9BR_WSL_DISTRO_INVALID' }
& wsl.exe -d $Distro -- bash ($WslRepositoryPath + '/scripts/run_webcam_w9b_optical_007_once.sh')
$rc=$LASTEXITCODE
if ($rc -ne 0) { throw "W9B_OPTICAL_WINDOWS_LAUNCH_FAILED exit_code=$rc" }
Write-Output 'W9B_OPTICAL_WINDOWS_LAUNCH_PASS'
