# 启动小罗Bot 的 AI 服务（FastAPI，默认 127.0.0.1:7861）
#
# 这是「vue-ui → springboot bbs-rest → 本服务」链路里的最后一段。
# 启动后：
#   1) 启动 springboot 的 bbs-rest（端口 7010）
#   2) 启动 vue-ui（npm run serve，端口 8082）
#   3) 浏览器打开 http://localhost:8082/bot
#
# 说明：优先使用项目内的 .venv，没有则回退到系统 python。

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[提示] 未找到 .venv，改用系统 python（请确认依赖已安装：pip install -r requirements.txt）" -ForegroundColor Yellow
    $python = "python"
}

$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

Write-Host "启动小罗Bot AI 服务 ..." -ForegroundColor Cyan
& $python -X utf8 -m server.app
