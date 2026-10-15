# 启动小罗Bot 的 Gradio 调试界面（默认 127.0.0.1:7860）
#
# 正式入口是论坛网页的 /bot 页面（vue-ui + springboot）。
# 这个界面用于在不启动前端/后台的情况下单独调试 Agent 与知识库，
# 它和正式页面共用同一套多智能体实现（agent/ 包）。

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[提示] 未找到 .venv，改用系统 python" -ForegroundColor Yellow
    $python = "python"
}

$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

& $python -X utf8 -m graph.workflow_gradio
