# llm-router 安装包装 — 修复 Windows GBK 控制台崩溃
# 用法:
#   .\scripts\install_llm_router.ps1 -Check
#   .\scripts\install_llm_router.ps1 -Headless
#   .\scripts\install_llm_router.ps1 -Cursor

param(
    [switch]$Check,
    [switch]$Headless,
    [switch]$Cursor
)

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

if ($Check) {
    llm-router install --check
    exit $LASTEXITCODE
}
if ($Cursor) {
    python "$PSScriptRoot\install_cursor_mcp.py" --apply
    exit $LASTEXITCODE
}
if ($Headless) {
    llm-router install --headless
    exit $LASTEXITCODE
}

Write-Host "Usage: -Check | -Headless | -Cursor"
exit 1
