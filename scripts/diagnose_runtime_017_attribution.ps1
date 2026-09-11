param(
    [string]$Repository = '\\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\.openditoo-local\worktrees\media-avrcp'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Need([bool]$Ok,[string]$Message){ if(-not $Ok){ throw $Message } }
function Quote-WindowsArg([string]$Value) {
    if ($Value.Length -eq 0) { return '""' }
    $sb = New-Object System.Text.StringBuilder; [void]$sb.Append('"'); $slashes=0
    foreach($ch in $Value.ToCharArray()){
        if($ch -eq '\'){ $slashes++; continue }
        if($ch -eq '"'){ [void]$sb.Append(('\' * ($slashes*2+1))); [void]$sb.Append('"'); $slashes=0; continue }
        if($slashes -gt 0){ [void]$sb.Append(('\' * $slashes)); $slashes=0 }
        [void]$sb.Append($ch)
    }
    if($slashes -gt 0){ [void]$sb.Append(('\' * ($slashes*2))) }
    [void]$sb.Append('"'); $sb.ToString()
}
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
Need ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Run this diagnostic from Administrator PowerShell'
$policy = Get-Content -Raw -Encoding UTF8 (Join-Path $Repository 'product\OPENDITOO-PRODUCT-RUNTIME-017.json') | ConvertFrom-Json
$broker=$policy.pagination.broker
$btvs=[string]$broker.btvs_exe; $tshark=[string]$broker.tshark_exe; $sink=[string]$broker.sink_exe; $port=[int]$broker.port
foreach($p in @($btvs,$tshark,$sink)){ Need (Test-Path -LiteralPath $p -PathType Leaf) "missing helper: $p" }
Get-Process btvs,tshark,OpenDitoo.ButtonProbe -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmssZ')
$sinkLog=Join-Path $env:TEMP "openditoo-r017-attr-sink-$stamp.ndjson"
$out=Join-Path $env:TEMP "openditoo-r017-attr-$stamp.tsv"
$err=Join-Path $env:TEMP "openditoo-r017-attr-$stamp.err"
$sinkProc=Start-Process -FilePath $sink -ArgumentList @('--seconds','0','--status','playing','--log',$sinkLog) -PassThru
$btvsProc=Start-Process -FilePath $btvs -ArgumentList @('-Mode','Wireshark','-Remote','on','-Port',[string]$port) -PassThru
Start-Sleep -Seconds 2
$filter='btl2cap.payload contains 11:0e:00:48:7c:4b:00 || btl2cap.payload contains 11:0e:00:48:7c:4c:00 || btl2cap.payload contains 11:0e:00:48:7c:44:00 || btl2cap.payload contains 11:0e:00:48:7c:46:00'
$args=@('-i',"TCP@127.0.0.1:$port",'-a','duration:30','-l','-Y',$filter,'-T','fields','-E','separator=\t','-e','frame.time_relative','-e','bthci_acl.chandle','-e','bthci_acl.src.bd_addr','-e','bthci_acl.dst.bd_addr','-e','btl2cap.payload')
$psi=New-Object System.Diagnostics.ProcessStartInfo; $psi.FileName=$tshark; $psi.UseShellExecute=$false; $psi.CreateNoWindow=$true; $psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true; $psi.Arguments=(($args|%{Quote-WindowsArg ([string]$_)}) -join ' ')
$ts=[Diagnostics.Process]::Start($psi); Need ($null -ne $ts) 'failed to start tshark'
$stdoutTask=$ts.StandardOutput.ReadToEndAsync(); $stderrTask=$ts.StandardError.ReadToEndAsync()
Start-Sleep -Seconds 2
function Cue([string]$x){ Write-Host "*** $x ***" -ForegroundColor Yellow; Start-Sleep -Milliseconds 2600 }
Cue 'DITOO LEFT once'; Cue 'DITOO RIGHT once'; 1..4 | % { Cue "DITOO LEVER $_/4" }; Cue 'TIVOO VOLUME-KNOB SHORT PRESS once'; Write-Host '*** HANDS OFF ***' -ForegroundColor Green
$ts.WaitForExit(); $stdoutTask.Result | Set-Content -LiteralPath $out -Encoding UTF8; $stderrTask.Result | Set-Content -LiteralPath $err -Encoding UTF8
Stop-Process -Id $sinkProc.Id,$btvsProc.Id -Force -ErrorAction SilentlyContinue
Write-Host '===== ATTRIBUTION RESULT =====' -ForegroundColor Green
Get-Content -LiteralPath $out
Write-Host "R017_ATTR_RESULT_FILE=$out"
Write-Host "R017_ATTR_TSHARK_ERR=$err"
