param(
    [string]$Repository = '\\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\.openditoo-local\worktrees\media-avrcp'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Need([bool]$Ok,[string]$Message){ if(-not $Ok){ throw $Message } }
function Is-Admin {
    $id=[Security.Principal.WindowsIdentity]::GetCurrent()
    $p=New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
Need (Is-Admin) 'BTVS requires elevation; run this harness from Administrator PowerShell'

$policy = Get-Content -LiteralPath (Join-Path $Repository 'product\OPENDITOO-PRODUCT-RUNTIME-017.json') -Raw | ConvertFrom-Json
$btvs=[string]$policy.pagination.broker.btvs_exe
$tshark=[string]$policy.pagination.broker.tshark_exe
Need (Test-Path -LiteralPath $btvs -PathType Leaf) "BTVS missing: $btvs"
Need (Test-Path -LiteralPath $tshark -PathType Leaf) "tshark missing: $tshark"

Get-Process btvs,tshark -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$port=24354
$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmssZ')
$out=Join-Path $env:TEMP "openditoo-r017-handle-$stamp.tsv"
$err=Join-Path $env:TEMP "openditoo-r017-handle-$stamp.err"
$btvsProc=Start-Process -FilePath $btvs -ArgumentList @('-Mode','Wireshark','-Remote','on','-Port',[string]$port) -PassThru
Start-Sleep -Seconds 1

# Capture L2CAP signalling and short data on every ACL handle. We specifically care about
# a connection request whose PSM is 0x0003 (RFCOMM) after Runtime 016 is started.
$filter='btl2cap.cid == 0x0001 || btl2cap.length <= 80'
$args=@('-i',"TCP@127.0.0.1:$port",'-a','duration:20','-l','-Y',$filter,'-T','fields','-E','separator=\\t',
        '-e','frame.time_relative','-e','bthci_acl.chandle','-e','btl2cap.cid','-e','btl2cap.payload')
function Quote-WindowsArg([string]$Value) {
    if ($Value.Length -eq 0) { return '\"\"' }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('\"'); $slashes = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ($ch -eq '\\') { $slashes++; continue }
        if ($ch -eq '\"') {
            [void]$sb.Append(('\\' * ($slashes * 2 + 1))); [void]$sb.Append('\"'); $slashes=0; continue
        }
        if ($slashes -gt 0) { [void]$sb.Append(('\\' * $slashes)); $slashes=0 }
        [void]$sb.Append($ch)
    }
    if ($slashes -gt 0) { [void]$sb.Append(('\\' * ($slashes * 2))) }
    [void]$sb.Append('\"'); return $sb.ToString()
}
$psi=New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName=$tshark; $psi.UseShellExecute=$false; $psi.CreateNoWindow=$true
$psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true
$psi.Arguments=(($args | ForEach-Object { Quote-WindowsArg ([string]$_) }) -join ' ')
$ts=[System.Diagnostics.Process]::Start($psi)
Need ($null -ne $ts) 'failed to start tshark'
$outTask=$ts.StandardOutput.ReadToEndAsync(); $errTask=$ts.StandardError.ReadToEndAsync()
Start-Sleep -Seconds 2

Write-Host '*** STARTING EXISTING ACCEPTED RUNTIME 016 FOR HANDLE-LEARNING ONLY ***' -ForegroundColor Cyan
& wsl.exe -d Ubuntu -- bash -lc 'systemctl --user start openditoo-product.service'
Start-Sleep -Seconds 8
Write-Host '*** STOPPING RUNTIME 016 AGAIN ***' -ForegroundColor Cyan
& wsl.exe -d Ubuntu -- bash -lc 'systemctl --user stop openditoo-product.service'

$ts.WaitForExit()
[IO.File]::WriteAllText($out,$outTask.GetAwaiter().GetResult())
[IO.File]::WriteAllText($err,$errTask.GetAwaiter().GetResult())
Stop-Process -Id $btvsProc.Id -Force -ErrorAction SilentlyContinue

Write-Host '===== HANDLE-LEARNING RESULT =====' -ForegroundColor Green
Get-Content -LiteralPath $out
Write-Host "R017_HANDLE_RESULT_FILE=$out"
Write-Host "R017_HANDLE_TSHARK_ERR=$err"
