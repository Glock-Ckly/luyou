# 多模型路由系统 — 实施状态与待办
> 2026-06-14 更新（Decomposer + E2E + Cursor CLI 完成）

---

## 中转站接入状态（2026-06-14）

| Provider | Base URL | 密钥位置 | 模型映射（relay_models.yaml） |
|---|---|---|---|
| OpenAI（Ccode） | `https://all-api.ccode.dev/v1` | `~/.llm-router/.env` | `openai/gpt-4o` → `openai/gpt-5.5` |
| Anthropic（Ccode） | `https://all-api.ccode.dev` | `~/.llm-router/.env` | `anthropic/claude-sonnet-4-6` 同名 |
| DeepSeek（官方 API） | `https://api.deepseek.com/v1` | `~/.llm-router/.env` | `deepseek/deepseek-chat` → `deepseek/deepseek-v4-flash` |

**Smoke 验收：** `python scripts/smoke_relay.py` — **15/15 通过**

**L2 评估：** `python scripts/eval_l2.py` — **23/25 routing (92%) PASS**

**Decomposer 评估：** `python scripts/eval_decomposer.py` — **8/10 (80%) PASS**

**E2E 四场景：** `python scripts/eval_e2e.py` — **12/12 PASS**

**进度看板：** `python scripts/dashboard_server.py` → http://127.0.0.1:1785

---

## 已完成

| 文件 | 说明 | 自测 |
|---|---|---|
| `src/l2_classifier.py` | L2 LLM 分类器 | ✅ eval 25 样本 |
| `src/task_decomposer.py` | 大任务拆分 | ✅ eval 10 样本 80% |
| `src/orchestrator.py` | 全流程编排器 | ✅ S6 + e2e |
| `scripts/eval_decomposer.py` | Decomposer 评估 | ✅ 8/10 |
| `scripts/eval_e2e.py` | 4 场景端到端 | ✅ 12/12 |
| `scripts/cursor_cli.py` | Cursor Queue 独立 CLI | ✅ |
| `scripts/dashboard_server.py` | 进度可视化 (1785) | ✅ |
| `config/decomposer_eval_samples.json` | 10 条拆分样本 | — |
| `config/cursor_mcp_snippet.json` | Cursor MCP 配置片段 | — |

---

## 需用户手动操作（Agent 已停在此处）

### 1. llm-router MCP / Hooks 安装

**原因：** `llm-router install` 面向 **Claude Code** 生态（SessionStart/UserPromptSubmit 等 hooks），**不直接写入 Cursor MCP**。且 Windows 默认 GBK 控制台会导致 `doctor`/`install` 无 UTF-8 时崩溃。

**手动步骤：**

```powershell
$env:PYTHONIOENCODING='utf-8'
llm-router install --check          # 预览
llm-router install --headless       # 无 OAuth，写 Claude Code hooks + MCP
llm-router doctor                   # 验证
```

**注意：** 若你主要用 **Cursor + 本仓库 orchestrator**，hooks 可能与现有 `load-claude-md` 冲突，建议只装 MCP、不装 hooks，或跳过此步（当前 `relay_llm.py` 已可独立运行）。

### 2. Cursor MCP 注册（可选）

将 `config/cursor_mcp_snippet.json` 合并到 Cursor 的 MCP 配置（Settings → MCP，或项目/全局 `mcp.json`）：

```json
{
  "mcpServers": {
    "llm-router": {
      "command": "llm-router",
      "args": []
    }
  }
}
```

### 3. Cursor Queue 日常使用

```bash
python scripts/cursor_cli.py list
python scripts/cursor_cli.py pop
python scripts/cursor_cli.py done <task_id>
```

### 4. 预算状态接口（可选）

`orchestrator._get_budget_ratio()` 仍 fallback 0.0；需真实预算时接入 `llm_router.budget` 或自建计数。

---

## 已知小问题

| 项 | 说明 |
|---|---|
| Decomposer split-05/06 | 2 条复杂任务 LLM 返回 `split:false`，边界样本可后续调 prompt |
| L2 arch-01 / sd-02 | 偶发 `uncertain`，routing 仍 92% PASS |
| smoke S5 Windows | 已修 `encoding=utf-8` 防 GBK 解码失败 |

---

## 验收命令（提交前）

```bash
python scripts/smoke_relay.py    # 15 passed
python scripts/eval_l2.py        # PASS
python scripts/eval_decomposer.py
python scripts/eval_e2e.py
```

---

## `/luyou` 快捷入口

Skill: `C:\Users\32402\.claude\skills\luyou\SKILL.md`
