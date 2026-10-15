# 启动知识库构建界面（Gradio）：上传 PDF → DotsOCR 解析 → 分块 → 多模态向量化入库
#
# 论坛内容的知识库不走这里，请用 .\start_kb_sync.ps1 从 springboot 网关同步。
# 两者最终写进同一个集合 t_knowledge_collection，所以小罗Bot 检索时是一起被搜到的。

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[提示] 未找到 .venv，改用系统 python" -ForegroundColor Yellow
    $python = "python"
}

$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

& $python -X utf8 main.py
