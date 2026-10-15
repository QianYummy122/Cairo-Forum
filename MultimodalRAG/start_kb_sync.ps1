# 同步论坛内容到小罗Bot 知识库
#
# 数据源优先级（自动探测）：
#   1) springboot 的 REST 网关 bbs-rest（http://127.0.0.1:7010/api）—— 推荐
#   2) 直连 MySQL（open_bbs 只读）—— 网关/Dubbo 没起来时的兜底
#   3) 本地 forum_snapshot/ 目录 —— 完全离线时使用
#
# 用法：
#   .\start_kb_sync.ps1                 # 全量同步（含图片理解）
#   .\start_kb_sync.ps1 -NoImages       # 跳过图片理解，快很多
#   .\start_kb_sync.ps1 -Source mysql   # 只用某个数据源
#   .\start_kb_sync.ps1 -Status         # 只看状态，不同步

param(
    [ValidateSet("auto", "springboot-rest", "mysql", "local-snapshot")]
    [string]$Source = "auto",
    [switch]$NoImages,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[提示] 未找到 .venv，改用系统 python" -ForegroundColor Yellow
    $python = "python"
}

$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

if ($Status) {
    & $python -X utf8 -m ingestion.cli status
    exit $LASTEXITCODE
}

$cliArgs = @("-X", "utf8", "-m", "ingestion.cli", "sync")
if ($Source -ne "auto") { $cliArgs += @("--source", $Source) }
if ($NoImages) { $cliArgs += "--no-images" }

Write-Host "开始同步论坛内容到知识库（数据源：$Source）..." -ForegroundColor Cyan
& $python @cliArgs
