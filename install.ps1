# Spyder AI Assist 一键安装（Windows）
# 自动定位「装有 Spyder 的那个 Python」，把插件装进它，并做一次入口点自检。
$ErrorActionPreference = "Continue"
try { $here = Split-Path -Parent $MyInvocation.MyCommand.Definition } catch { $here = (Get-Location).Path }

function Get-SpyderInfo($exe) {
    if (-not $exe) { return $null }
    try {
        $out = & $exe -c "import spyder,sys;print(sys.executable);print(getattr(spyder,'__version__','?'))" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $lines = @($out | Where-Object { $_ -ne '' })
            if ($lines.Count -ge 1) {
                return [pscustomobject]@{ Python = $lines[0].Trim(); Version = $lines[-1].Trim() }
            }
        }
    } catch {}
    return $null
}

Write-Host "============================================"
Write-Host "  Spyder AI Assist  一键安装"
Write-Host "============================================"

$cands = New-Object System.Collections.Generic.List[string]
$sp = Get-Command spyder -ErrorAction SilentlyContinue
if ($sp) {
    $p = Join-Path (Split-Path $sp.Source) "python.exe"
    if (Test-Path $p) { $cands.Add($p) }
}
foreach ($n in @("python","python3","py")) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { $cands.Add($c.Source) }
}
foreach ($g in @(
    "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
    "$env:ProgramData\miniconda3\python.exe",
    "$env:ProgramData\anaconda3\python.exe",
    "$env:ProgramData\Miniconda3\python.exe",
    "$env:ProgramData\Anaconda3\python.exe",
    "$env:USERPROFILE\anaconda3\python.exe",
    "$env:USERPROFILE\miniconda3\python.exe")) {
    Get-ChildItem $g -ErrorAction SilentlyContinue | ForEach-Object { $cands.Add($_.FullName) }
}

$found = $null
foreach ($exe in ($cands | Select-Object -Unique)) {
    $r = Get-SpyderInfo $exe
    if ($r) { $found = $r; break }
}

if (-not $found) {
    Write-Host "[未找到] 本机没有能 import spyder 的 Python。" -ForegroundColor Yellow
    Write-Host "请先安装 Spyder（https://www.spyder-ide.org/ ，或 pip install spyder），再运行本安装。" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 2
}

Write-Host ("[找到] Python     : " + $found.Python) -ForegroundColor Cyan
Write-Host ("[找到] Spyder 版本: " + $found.Version) -ForegroundColor Cyan
$py = $found.Python

Write-Host "[安装] 正在把插件装进该环境（pip install）..." -ForegroundColor Cyan
& $py -m pip install --upgrade --no-deps --no-build-isolation "$here"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[重试] 改用构建隔离再试一次 ..." -ForegroundColor Yellow
    & $py -m pip install --upgrade --no-deps "$here"
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[失败] pip 安装未成功，请把上面的报错发给作者。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

Write-Host "[验证] 检查 Spyder 是否已能发现插件 ..." -ForegroundColor Cyan
& $py "$here\verify_install.py"
$vrc = $LASTEXITCODE
Write-Host ""
if ($vrc -ne 0) {
    Write-Host "[警告] 入口点自检未通过，请把上面的输出发给作者。" -ForegroundColor Yellow
} else {
    Write-Host "=== 安装完成 ===" -ForegroundColor Green
    Write-Host "请重启 Spyder，在「视图(View) → 窗格(Panes)」里勾选「洄·讲解」。" -ForegroundColor Green
    Write-Host "首次使用请点面板工具栏「设置AI」，选一个接口并填 Key。" -ForegroundColor Green
}
Read-Host "按回车退出"
exit 0
