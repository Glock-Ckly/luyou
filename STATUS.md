# 多模型路由系统 — 实施状态与待办
> 2026-06-14 更新（中转站密钥接入 + smoke 验收通过）

---

## 中转站接入状态（2026-06-14）

| Provider | Base URL | 密钥位置 | 模型映射（relay_models.yaml） |
|---|---|---|---|
| OpenAI（Ccode） | `https://all-api.ccode.dev/v1` | `~/.llm-router/.env` | `openai/gpt-4o` → `openai/gpt-5.5` |
| Anthropic（Ccode） | `https://all-api.ccode.dev` | `~/.llm-router/.env` | `anthropic/claude-sonnet-4-6` 同名 |
| DeepSeek（官方 API） | `https://api.deepseek.com/v1` | `~/.llm-router/.env` | `deepseek/deepseek-chat` → `deepseek/deepseek-v4-flash` |

**说明：** DeepSeek 密钥在 Ccode 网关返回 401，走 DeepSeek 官方 API；OpenAI/Anthropic 走 Ccode 中转站。

**Smoke 验收：** `python scripts/smoke_relay.py` — **15/15 通过**（S0–S6，含端到端 hello world）

**新增文件：**
- `src/relay_config.py` — 加载 `~/.llm-router/.env`，注入 LiteLLM 环境变量
- `src/relay_llm.py` — 直接调 LiteLLM（绕过 llm-router 缺 `standard.yaml` 的打包问题）
- `config/relay.env.example` / `config/relay_models.yaml`
- `scripts/smoke_relay.py`

---

## 已完成

| 文件 | 说明 | 自测 |
|---|---|---|
| `multi-llm-router-design.md` | 完整架构设计文档 | — |
| `src/l1_classifier.py` | 关键词快筛 (9 类) | ✅ 6/6 |
| `src/routing_table.py` | 核心映射 + 降级链 + 预算 4 区 | ✅ |
| `src/response_validator.py` | 3 层后验校验 | ✅ 4/4 |
| `src/cursor_queue.py` | Cursor 手动交付容器 | ✅ |
| `src/relay_config.py` | 中转站环境注入 | ✅ S0 |
| `src/relay_llm.py` | LiteLLM 薄封装 | ✅ S2–S4 |
| `src/task_decomposer.py` | 大任务拆分 | ⚠️ 端到端待专项验证 |
| `src/orchestrator.py` | 全流程编排器 | ✅ S6 通过 |
| `src/prompts/classifier_v3.txt` | L2 分类 prompt | ⚠️ 未做 20+ 样本调优 |
| `src/prompts/decomposer.txt` | 拆分 prompt | ⚠️ 未做 10 条大任务验证 |
| `src/policies/custom.yaml` | llm-router YAML 策略 | — |
| `scripts/smoke_relay.py` | 分阶段验收脚本 | ✅ 15/15 |

---

## 阻塞项 (需要用户介入)

### ~~1. API Key 配置~~ ✅ 已解决（2026-06-14）
密钥写入 `~/.llm-router/.env`，smoke S0–S6 全部通过。**建议轮换密钥**（曾在对话中明文出现）。

### 2. L2 分类器 prompt 调优
**需要:** 跑 20+ 条样本，检查 `classifier_v3.txt` 的 task_type 准确率

### 3. TaskDecomposer 验证
**需要:** 跑 10 条大任务，检查 split JSON 质量

### 4. 预算状态接口
**原因:** `llm_router.budget.get_budget_state()` 当前未接入（orchestrator 用 mock 0.0）
**需要:** 若需渐进预算，单独适配或放弃 llm-router budget 模块

### 5. MCP 注册
**需要:** 用户手动 `llm-router install`（交互式）

### 6. Cursor Queue CLI 未接入
**需要:** 评估独立 CLI 或集成 llm-router MCP

### 7. llm-router 打包缺陷（已绕过）
**现象:** 已安装的 `llm-router` 缺少 `policies/standard.yaml`，`llm_router.providers` 无法导入
**当前方案:** 使用 `relay_llm.py` 直接调 LiteLLM，不依赖 llm-router 的 call_llm

---

## 下一步（按顺序）

1. ~~配置 API Key~~ ✅
2. ~~首次 smoke 验收~~ ✅ `python scripts/smoke_relay.py`
3. L2 分类 20+ 样本 → 调 `classifier_v3.txt`
4. Decomposer 10 条大任务 → 调 `decomposer.txt`
5. `llm-router install`（可选，MCP 接入）
6. Cursor Queue CLI 注册
7. 4 场景完整端到端测试

---

## `/luyou` 快捷入口

Skill: `C:\Users\32402\.claude\skills\luyou\SKILL.md`

---

## 文件清单

```
多模型路由系统/
├── multi-llm-router-design.md
├── STATUS.md
├── config/
│   ├── relay.env.example
│   └── relay_models.yaml
├── scripts/
│   └── smoke_relay.py
└── src/
    ├── relay_config.py
    ├── relay_llm.py
    ├── l1_classifier.py
    ├── routing_table.py
    ├── response_validator.py
    ├── cursor_queue.py
    ├── task_decomposer.py
    ├── orchestrator.py
    ├── prompts/
    └── policies/
```
