# 多模型路由系统 — 实施状态
> 2026-06-14 全部里程碑完成

---

## 验收结果

| 脚本 | 结果 |
|---|---|
| `python scripts/smoke_relay.py` | 15/15 |
| `python scripts/eval_l2.py` | 25/25 (100%) |
| `python scripts/eval_decomposer.py` | 10/10 (100%) |
| `python scripts/eval_e2e.py` | 13/13 |
| `python scripts/run_acceptance.py` | 一键跑以上全部 |

**进度看板：** `python scripts/dashboard_server.py` → http://127.0.0.1:1785

---

## 已完成里程碑

1. ✅ API Key / 中转站接入
2. ✅ Smoke S0–S6
3. ✅ L2 分类 25 样本
4. ✅ TaskDecomposer 10 样本
5. ✅ llm-router MCP（`~/.cursor/mcp.json`）+ Claude Code hooks（`llm-router install --headless`）
6. ✅ Cursor Queue CLI（`scripts/cursor_cli.py`）
7. ✅ 4 场景端到端
8. ✅ 预算接入（`src/budget_adapter.py`）

---

## 安装命令

```powershell
# Windows 需 UTF-8，否则 llm-router doctor/install 可能 GBK 崩溃
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'

# Cursor MCP
python scripts/install_cursor_mcp.py --apply
# 或
.\scripts\install_llm_router.ps1 -Cursor

# Claude Code hooks + MCP（已在本机执行）
.\scripts\install_llm_router.ps1 -Headless

# 检查
.\scripts\install_llm_router.ps1 -Check
```

---

## Cursor Queue

```bash
python scripts/cursor_cli.py list
python scripts/cursor_cli.py pop
python scripts/cursor_cli.py done <task_id>
```

---

## 架构

```
Prompt → Decomposer → L1 → L2 → Router(+budget) → Model/Cursor → Validator → Aggregate
```

中转站：`relay_config.py` + `relay_llm.py`（绕过 llm-router 缺 standard.yaml）

---

## `/luyou` Skill

`C:\Users\32402\.claude\skills\luyou\SKILL.md`
