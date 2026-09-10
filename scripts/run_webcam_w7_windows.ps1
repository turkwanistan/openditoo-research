param(
    [string]$Distro = 'Ubuntu',
    [string]$WslRepositoryPath = '/home/wan/Projects/openditoo-research'
)

$ErrorActionPreference = 'Stop'
Write-Output 'W7_WINDOWS_LAUNCH_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-002'

if ($WslRepositoryPath -notmatch '^/[A-Za-z0-9._/-]+$') { throw 'W7_WSL_REPOSITORY_PATH_INVALID' }
if ($Distro -notmatch '^[A-Za-z0-9._-]+$') { throw 'W7_WSL_DISTRO_INVALID' }
$command = "cd '$WslRepositoryPath' && bash scripts/run_webcam_w7_once.sh"
& wsl.exe -d $Distro -- bash -lc $command
$rc = $LASTEXITCODE
if ($rc -ne 0) {
    throw "W7_WINDOWS_LAUNCH_FAILED exit_code=$rc"
}
Write-Output 'W7_WINDOWS_LAUNCH_PASS'
