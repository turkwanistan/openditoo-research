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
Need (Is-Admin) 'BTVS requires elevation; run from Administrator PowerShell'
$policy = Get-Content -LiteralPath (Join-Path $Repository 'product\OPENDITOO-PRODUCT-RUNTIME-017.json') -Raw | ConvertFrom-Json
$btvs=[string]$policy.pagination.broker.btvs_exe
$tshark=[string]$policy.pagination.broker.tshark_exe
Need (Test-Path -LiteralPath $btvs -PathType Leaf) "BTVS missing: $btvs"
Need (Test-Path -LiteralPath $tshark -PathType Leaf) "tshark missing: $tshark"
Get-Process btvs,tshark -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$port=24355
$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmssZ')
$out=Join-Path $env:TEMP "openditoo-r017-frame-attr-$stamp.tsv"
$err=Join-Path $env:TEMP "openditoo-r017-frame-attr-$stamp.err"
$btvsProc=Start-Process -FilePath $btvs -ArgumentList @('-Mode','Wireshark','-Remote','on','-Port',[string]$port) -PassThru
Start-Sleep -Seconds 1
$filter='btl2cap.payload contains 01:03:00:9f:a2:00:02 || btl2cap.payload contains 01:04:00:bd:31:f2:00:02'
$args=@('-i',"TCP@127.0.0.1:$port",'-a','duration:15','-l','-Y',$filter,'-T','fields','-E','separator=\\t',
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
Write-Host '*** STARTING ACCEPTED RUNTIME 016 BRIEFLY; MEDIA SHOULD BE PAUSED/OFF ***' -ForegroundColor Cyan
& wsl.exe -d Ubuntu -- bash -lc 'systemctl --user start openditoo-product.service'
Start-Sleep -Seconds 7
& wsl.exe -d Ubuntu -- bash -lc 'systemctl --user stop openditoo-product.service'
Write-Host '*** RUNTIME 016 STOPPED AGAIN ***' -ForegroundColor Cyan
$ts.WaitForExit()
[IO.File]::WriteAllText($out,$outTask.GetAwaiter().GetResult())
[IO.File]::WriteAllText($err,$errTask.GetAwaiter().GetResult())
Stop-Process -Id $btvsProc.Id -Force -ErrorAction SilentlyContinue
Write-Host '===== FRAME-ATTRIBUTION RESULT =====' -ForegroundColor Green
Get-Content -LiteralPath $out
Write-Host "R017_FRAME_ATTR_RESULT_FILE=$out"
Write-Host "R017_FRAME_ATTR_TSHARK_ERR=$err"
