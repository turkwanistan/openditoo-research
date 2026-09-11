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
function Quote-WindowsArg([string]$Value) {
    if ($Value.Length -eq 0) { return '""' }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"'); $slashes = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ($ch -eq '\') { $slashes++; continue }
        if ($ch -eq '"') {
            [void]$sb.Append(('\' * ($slashes * 2 + 1))); [void]$sb.Append('"'); $slashes=0; continue
        }
        if ($slashes -gt 0) { [void]$sb.Append(('\' * $slashes)); $slashes=0 }
        [void]$sb.Append($ch)
    }
    if ($slashes -gt 0) { [void]$sb.Append(('\' * ($slashes * 2))) }
    [void]$sb.Append('"'); return $sb.ToString()
}
Need (Is-Admin) 'BTVS requires elevation; run from Administrator PowerShell'
$policy = Get-Content -LiteralPath (Join-Path $Repository 'product\OPENDITOO-PRODUCT-RUNTIME-017.json') -Raw | ConvertFrom-Json
$btvs=[string]$policy.pagination.broker.btvs_exe
$tshark=[string]$policy.pagination.broker.tshark_exe
Need (Test-Path -LiteralPath $btvs -PathType Leaf) "BTVS missing: $btvs"
Need (Test-Path -LiteralPath $tshark -PathType Leaf) "tshark missing: $tshark"
Get-Process btvs,tshark -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$port=24356
$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmssZ')
$out=Join-Path $env:TEMP "openditoo-r017-raw-acl-$stamp.tsv"
$err=Join-Path $env:TEMP "openditoo-r017-raw-acl-$stamp.err"
$btvsProc=Start-Process -FilePath $btvs -ArgumentList @('-Mode','Wireshark','-Remote','on','-Port',[string]$port) -PassThru
Start-Sleep -Seconds 1
$args=@('-i',"TCP@127.0.0.1:$port",'-a','duration:18','-l','-Y','bthci_acl','-T','fields','-E','separator=\t',
        '-e','frame.time_relative','-e','bthci_acl.chandle','-e','bthci_acl.pb_flag','-e','bthci_acl.length',
        '-e','btl2cap.cid','-e','btl2cap.payload','-e','data.data')
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
Start-Sleep -Seconds 8
Write-Host '*** RUNTIME 016 STOPPED AGAIN ***' -ForegroundColor Cyan
& wsl.exe -d Ubuntu -- bash -lc 'systemctl --user stop openditoo-product.service'
$ts.WaitForExit()
[IO.File]::WriteAllText($out,$outTask.GetAwaiter().GetResult())
[IO.File]::WriteAllText($err,$errTask.GetAwaiter().GetResult())
Stop-Process -Id $btvsProc.Id -Force -ErrorAction SilentlyContinue

$preambleA='0103009fa20002'; $preambleB='010400bd31f20002'
$rows=@(Get-Content -LiteralPath $out | Where-Object { $_.Trim() })
$perHandle=@{}
$hits=@()
foreach($line in $rows){
    $c=$line -split "`t",7
    if($c.Count -lt 2){ continue }
    $handle=$c[1]
    if([string]::IsNullOrWhiteSpace($handle)){ continue }
    $hex=''
    foreach($ix in 5,6){ if($c.Count -gt $ix -and $c[$ix]){ $hex += ($c[$ix] -replace '[^0-9A-Fa-f]','').ToLowerInvariant() } }
    if(-not $perHandle.ContainsKey($handle)){ $perHandle[$handle]=New-Object System.Text.StringBuilder }
    if($hex){ [void]$perHandle[$handle].Append($hex) }
    if($hex.Contains($preambleA)){ $hits += "$handle A $($c[0])" }
    if($hex.Contains($preambleB)){ $hits += "$handle B $($c[0])" }
}
Write-Host '===== RAW-ACL ATTRIBUTION RESULT =====' -ForegroundColor Green
foreach($h in ($perHandle.Keys | Sort-Object)){
    $joined=$perHandle[$h].ToString()
    $a=$joined.Contains($preambleA); $b=$joined.Contains($preambleB)
    Write-Host "R017_RAW_ACL_HANDLE=$h PREAMBLE_A=$a PREAMBLE_B=$b HEX_CHARS=$($joined.Length)"
}
foreach($hit in $hits){ Write-Host "R017_RAW_ACL_DIRECT_HIT=$hit" }
Write-Host "R017_RAW_ACL_RESULT_FILE=$out"
Write-Host "R017_RAW_ACL_TSHARK_ERR=$err"
if($rows.Count -eq 0 -and (Test-Path -LiteralPath $err)){
    $errText=(Get-Content -LiteralPath $err -Raw -ErrorAction SilentlyContinue).Trim()
    if($errText){ Write-Host "R017_RAW_ACL_TSHARK_STDERR=$errText" }
}
