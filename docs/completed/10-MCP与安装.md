# MCP 与安装（已完成）

## Cursor MCP

- 配置片段：`config/cursor_mcp_snippet.json`
- 安装脚本：`scripts/install_cursor_mcp.py`
  - `--dry-run` 预览
  - `--apply` 执行（优先 `llm-router install --host cursor`，失败则合并 snippet 到 `~/.cursor/mcp.json`）
- PowerShell：`scripts/install_llm_router.ps1 -Cursor`

本机已注册：`~/.cursor/mcp.json` 含 `llm-router`  
规则：`~/.cursor/rules/llm-router.md`

## Claude Code Hooks

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
.\scripts\install_llm_router.ps1 -Headless
# 等价 llm-router install --headless
```

已安装到 `~/.claude/hooks/`（SessionStart、UserPromptSubmit、PreToolUse 等）及 `~/.claude/settings.json` MCP。

## 检查

```powershell
.\scripts\install_llm_router.ps1 -Check
```

## Windows GBK

`llm-router doctor` / `install` 在默认 GBK 控制台可能 Unicode 崩溃，**必须**设 `PYTHONIOENCODING=utf-8` 与 `PYTHONUTF8=1`。

## 与 luyou orchestrator 的关系

- **MCP/hooks**：在 Cursor/Claude Code 会话内自动路由（llm-router 生态）
- **orchestrator**：Python 侧独立全流程，经 `relay_llm` 调中转站  
两者可并存；主仓库验收以 orchestrator + eval 为准。
