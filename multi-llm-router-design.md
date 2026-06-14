# Multi-LLM Routing System — 完整设计文档

> **状态:** 设计完成，待实施
> **日期:** 2026-06-13
> **底子:** [llm-router (ypollak2)](https://github.com/ypollak2/llm-router) v10.1.4 · PyPI `llm-routing`
> **分类参考:** [brentsWorks/llm-router](https://github.com/brentsWorks/llm-router)
> **用途:** 个人开发工作流，非商业化

---

## 目录

1. [系统概述](#1-系统概述)
2. [核心架构](#2-核心架构)
3. [模块设计](#3-模块设计)
4. [分类系统](#4-分类系统)
5. [路由逻辑](#5-路由逻辑)
6. [模型适配器](#6-模型适配器)
7. [Cursor Queue (手动交付容器)](#7-cursor-queue)
8. [代码来源映射](#8-代码来源映射)
9. [改动清单](#9-改动清单)
10. [使用流程示例](#10-使用流程示例)

---

## 1. 系统概述

### 1.1 做什么

接受用户自然语言/任务输入 → 自动分类 → 路由到最合适的模型 → 返回统一 JSON 响应 + 追踪成本。

### 1.2 模型职责划分

| 任务类型 | 目标模型 | 原因 |
|---|---|---|
| `architecture` / `system_design` / `deep_reasoning` | **Claude** (Opus/Sonnet) | 高层面推理，架构设计 |
| `implementation` / `debugging` / `refactor` | **GPT** (GPT-4o/o3) | 代码实现，调试 |
| `boilerplate` / `bulk_generation` / `data_processing` | **DeepSeek** | 廉价批量生成 |
| `code_patch` / `file_edit` | **Cursor Queue** | 文件级修改，手动交付 |
| `uncertain` | **GPT** (默认) | 安全兜底 |

### 1.3 输出格式

```json
{
  "task_type": "implementation",
  "selected_model": "openai/gpt-4o",
  "reason": "matched via L2 LLM classifier, confidence 0.92",
  "steps": ["classify → route → execute → validate"],
  "result": "...",
  "cost_level": "low | medium | high"
}
```

---

## 2. 核心架构

```
                        ┌──────────────────────┐
                        │     User Prompt       │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ ① Orchestrator        │  中央控制器
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ ② TaskDecomposer (NEW)│  大任务→子任务列表
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ ③ Hybrid Classifier   │
                        │  L1: Heuristic (NEW)  │  关键词快筛
                        │  L2: LLM (MODIFIED)   │  DeepSeek 分类
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ ④ Router (MODIFIED)   │  task_type → model
                        │  (原: complexity→     │  1:1 精确映射
                        │   profile)            │  + 任务感知降级链
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼──────┐  ┌─────────▼──────┐  ┌─────────▼──────┐
     │ Claude Adapter│  │  GPT Adapter   │  │DeepSeek Adapter│
     │ (KEEP)        │  │  (KEEP)        │  │ (KEEP)          │
     └────────┬──────┘  └─────────┬──────┘  └─────────┬──────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ ⑤ Guards (KEEP)       │  断路器+健康检查
                        │ + 渐进预算 (MODIFIED)  │  4区: 0-60-75-90%
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ ⑥ Response Validator  │  语法/结构/完整性
                        │ (NEW)                 │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ ⑦ Response Aggregator │  合并子任务结果
                        │ (KEEP + MODIFY)       │  + Cursor Queue 输出
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │    Unified JSON       │
                        └──────────────────────┘
```

### 模块依赖 (接口视角)

```
Orchestrator
  ├── TaskDecomposer      decompose(text) → Subtask[]
  ├── HybridClassifier    classify(prompt) → Classification
  │     ├── L1 Heuristic  (快/免费，高置信直接返回)
  │     └── L2 LLM        (低置信兜底，DeepSeek)
  ├── Router              route(task_type, complexity) → ModelConfig
  │     └── FallbackMap   per-task-type 降级链
  ├── ModelAdapterFactory getAdapter(model) → IModelAdapter
  │     ├── ClaudeAdapter
  │     ├── GPTAdapter
  │     ├── DeepSeekAdapter
  │     └── CursorAdapter (→ Cursor Queue)
  ├── Guards              circuit_break() + health() + budget()
  ├── ResponseValidator   validate(response) → pass|fail|retry
  ├── ResponseAggregator  aggregate(results[]) → UnifiedJSON
  └── CostTracker         record(model, tokens, cost)
```

---

## 3. 模块设计

### 3.1 Orchestrator

**职责:** 中央控制器，协调所有模块的执行顺序。不包含业务逻辑。

**输入:** 用户自然语言 prompt
**输出:** 统一 JSON 响应

**伪代码:**

```python
async def handle_request(prompt: str) -> UnifiedResponse:
    # 1. 分解大任务
    subtasks = await task_decomposer.decompose(prompt)
    if not subtasks:
        subtasks = [Subtask(prompt=prompt)]

    results = []
    for subtask in subtasks:
        # 2. 分类
        classification = await classifier.classify(subtask.prompt)

        # 3. 路由
        model_config = router.route(classification)

        # 4. 守卫检查
        if not guards.check(model_config):
            model_config = router.fallback(classification)

        # 5. 调用模型
        adapter = adapter_factory.get(model_config.model)
        response = await adapter.call(subtask.prompt)

        # 6. 后验校验
        validation = validator.validate(response)
        if not validation.passed:
            response = await retry_or_upgrade(adapter, response)

        # 7. 记录成本
        cost_tracker.record(model_config.model, response.tokens)

        results.append(response)

    # 8. 聚合
    return aggregator.aggregate(results, classification)
```

### 3.2 TaskDecomposer (NEW)

**职责:** 判断单次 prompt 是否需要拆分为多个子任务。是系统的入口优化层。

**判定逻辑:**
- Prompt 长度 > 500 字符 → 考虑拆分
- Prompt 包含多个独立步骤 (编号列表/分号分隔) → 考虑拆分
- Prompt 涉及多文件/多模块操作 → 考虑拆分

**实现:** 调一次 DeepSeek (最便宜)，让它输出子任务 JSON 列表。

**Prompt 模板:**

```
Analyze if this coding task should be split into subtasks.
If YES, return: {"split": true, "subtasks": [{"prompt": "...", "type_hint": "architecture|implementation|boilerplate|..."}, ...]}
If NO, return: {"split": false}

Task: {user_prompt}
```

**输出:**
```json
{
  "split": true,
  "subtasks": [
    {"prompt": "设计数据库 schema", "type_hint": "architecture"},
    {"prompt": "实现 POST /login 路由", "type_hint": "implementation"},
    {"prompt": "写登录表单 HTML", "type_hint": "boilerplate"}
  ]
}
```

### 3.3 ResponseValidator (NEW)

**职责:** 对模型返回结果做轻量结构校验。不做内容正确性判定 (太贵)。

**校验项:**
| 层 | 检查内容 | 不合格动作 |
|---|---|---|
| 语法层 | 代码块完整? JSON 合法? | 自动重试 (同模型) |
| 结构层 | 包含要求的所有部分? 输出不截断? | 升级模型重试 |
| 标记层 | 是否含 "I cannot"/"as an AI"/"抱歉"? | 升级模型重试 |

**置信度:** 不合格率超过阈值 → 触发模型降权 (反馈到 router)。

---

## 4. 分类系统

### 4.1 两级分类架构

移植自 brentsWorks 的门控模式，但去掉了 RAG 层 (需要 Pinecone，个人使用太重)。

```
Prompt
  │
  ▼
┌─────────────────────────────┐
│ L1: Heuristic Classifier    │  移植自 brentsWorks
│     关键词匹配 + 置信度评分   │  扩展了6种编码任务关键词
├─────────────────────────────┤
│ 置信度 >= 0.7 → 跳过 L2 ✓   │
│ 置信度 < 0.7  → 进入 L2 ↓   │
└─────────────────────────────┘
  │
  ▼
┌─────────────────────────────┐
│ L2: LLM Classifier          │  复用 llm-router 现有
│     DeepSeek (最便宜)        │  改写 classifier prompt
│     输出: task_type +        │  从"复杂度分类"→"任务类型分类"
│            complexity +      │
│            confidence        │
└─────────────────────────────┘
```

### 4.2 L1 关键词映射 (移植+扩展自 brentsWorks KeywordClassifier)

```python
KEYWORD_MAP = {
    "architecture": [
        "架构", "architecture", "系统设计", "system design",
        "技术选型", "design pattern", "设计模式", "模块划分",
        "微服务", "数据库设计", "schema design", "api design",
        "整体规划", "技术方案"
    ],
    "implementation": [
        "实现", "implement", "编写代码", "写一个", "create",
        "build", "开发", "develop", "编写函数", "写个",
        "添加功能", "add feature"
    ],
    "debugging": [
        "调试", "debug", "报错", "error", "bug", "修复",
        "fix", "崩溃", "crash", "不工作", "not working",
        "异常", "exception", "stack trace"
    ],
    "refactor": [
        "重构", "refactor", "优化代码", "改进结构",
        "clean up", "整理", "拆分", "extract method",
        "rename", "重组"
    ],
    "boilerplate": [
        "模板", "template", "脚手架", "scaffold", "crud",
        "配置文件", "config", "样板代码", "boilerplate",
        "生成器", "生成", "generate", "创建项目"
    ],
    "bulk_generation": [
        "批量", "bulk", "测试用例", "test case", "单元测试",
        "重复", "循环生成", "mass produce", "文档生成",
        "docstring", "批处理"
    ],
    "data_processing": [
        "数据清洗", "data clean", "转换", "transform",
        "csv", "json parse", "格式化", "format",
        "解析", "parse", "提取", "extract", "etl"
    ],
    "code_patch": [
        "修改文件", "edit file", "改这个", "fix this file",
        "更新代码", "update code", "改一行", "change line",
        "替换", "replace in"
    ],
    "file_edit": [
        "编辑", "edit", "rewrite", "重写", "修改",
        "更新文件", "update file", "patch", "diff"
    ],
}
```

### 4.3 L2 LLM Classifier Prompt (改写自 classifier_v2.txt)

```
Classify this coding task. Respond with ONLY a single-line JSON object.

Task type: "architecture", "implementation", "debugging", "refactor",
           "boilerplate", "bulk_generation", "data_processing",
           "code_patch", "file_edit"

Complexity: "simple" (single file, straightforward),
            "moderate" (multi-file, some design),
            "complex" (system-level, novel design)

Example: {"task_type":"implementation","complexity":"moderate","confidence":0.92,"reasoning":"multi-file feature with dependency injection"}
```

### 4.4 与 llm-router 原始分类的差异

| 维度 | llm-router 原始 | 改造后 |
|---|---|---|
| 分类主维度 | 复杂度 (simple/moderate/complex) | **任务类型** (architecture/impl/boilerplate…) |
| 分类副维度 | task_type (query/code/research…) | **复杂度** (simple/moderate/complex) |
| 路由逻辑 | complexity → profile → chain | **task_type → model (1:1 精确映射)** |
| L1 关键词 | 无 | 有 (移植 brentsWorks) |
| 分类模型链 | 取最便宜的可用 LLM | **固定 DeepSeek** |

---

## 5. 路由逻辑

### 5.1 核心映射表

```python
TASK_TO_MODEL: dict[str, str] = {
    "architecture":      "anthropic/claude-sonnet-4-6",
    "system_design":     "anthropic/claude-sonnet-4-6",
    "deep_reasoning":    "anthropic/claude-opus-4-6",
    "implementation":    "openai/gpt-4o",
    "debugging":         "openai/gpt-4o",
    "refactor":          "openai/gpt-4o",
    "boilerplate":       "deepseek/deepseek-chat",
    "bulk_generation":   "deepseek/deepseek-chat",
    "data_processing":   "deepseek/deepseek-chat",
    "code_patch":        "cursor_queue",
    "file_edit":         "cursor_queue",
    "uncertain":         "openai/gpt-4o",           # 默认
}
```

### 5.2 任务感知降级链 (每条映射独立，不让 DeepSeek 做架构设计)

```python
FALLBACK_CHAINS: dict[str, list[str]] = {
    "architecture": [
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-4o",                     # 降级到 GPT，不继续下探
    ],
    "deep_reasoning": [
        "anthropic/claude-opus-4-6",
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-4o",
    ],
    "implementation": [
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-6",       # GPT 挂了用 Claude
        "deepseek/deepseek-chat",            # 都挂了用 DeepSeek
    ],
    "boilerplate": [
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",               # DeepSeek 挂了用 mini
    ],
    "code_patch": [
        "cursor_queue",                      # 无 API 回退 — 只能手动
    ],
}
```

### 5.3 复杂度修正 (复杂度 1-5 评分)

```python
def apply_complexity_adjustment(task_type: str, complexity: int, model: str) -> str:
    """复杂度 1-2 降档，4-5 升档"""
    if complexity <= 2:
        # 简单任务 → 可以降一档省钱
        downgrade = {
            "anthropic/claude-sonnet-4-6": "openai/gpt-4o",
            "openai/gpt-4o": "deepseek/deepseek-chat",
        }
        return downgrade.get(model, model)
    elif complexity >= 4:
        # 复杂任务 → 升一档保质量
        upgrade = {
            "openai/gpt-4o": "anthropic/claude-sonnet-4-6",
            "deepseek/deepseek-chat": "openai/gpt-4o",
        }
        return upgrade.get(model, model)
    return model
```

### 5.4 渐进预算控制 (4 区，替换单阈值)

```python
BUDGET_ZONES = [
    (0.00,  "green",   "不干预"),
    (0.60,  "yellow",  "复杂度≤2 的任务降一档"),
    (0.75,  "orange",  "非关键任务全部降级到最便宜可用模型"),
    (0.90,  "red",     "仅 architecture/deep_reasoning 用原模型，其他全部降级"),
]
```

### 5.5 路由决策完整流程

```
输入: (task_type, complexity, confidence)
  │
  ├─→ 查 TASK_TO_MODEL → 主模型
  │
  ├─→ 复杂度修正 (1-2降, 4-5升)
  │
  ├─→ 预算 zone 检查 → 必要时降级
  │
  ├─→ 健康检查 → 不可用? → 查 FALLBACK_CHAINS[task_type]
  │
  └─→ 返回 ModelConfig { model, cost_level, fallback_chain }
```

---

## 6. 模型适配器

### 6.1 统一接口 (llm-router 已有，不动)

```python
class IModelAdapter(Protocol):
    """统一模型适配器接口"""

    async def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """调用模型并返回统一格式"""
        ...

    def health_check(self) -> bool:
        """检查模型 API 是否可用"""
        ...

    @property
    def cost_per_1k_tokens(self) -> float:
        """每千 token 成本 (USD)"""
        ...
```

### 6.2 四个适配器

| 适配器 | 方式 | 状态 |
|---|---|---|
| ClaudeAdapter | Anthropic API | llm-router 已有 |
| GPTAdapter | OpenAI API / LiteLLM | llm-router 已有 |
| DeepSeekAdapter | DeepSeek API / LiteLLM | llm-router 已有 |
| CursorAdapter | 本地 JSON 队列 (无 API 调用) | **NEW** |

---

## 7. Cursor Queue (手动交付容器)

### 7.1 为什么是队列而不是 API

Cursor Composer 没有公开 API。路由到 Cursor 的任务不能自动执行。

### 7.2 实现方案

**存储:** `~/.llm-router/cursor_queue.json`

```json
{
  "tasks": [
    {
      "id": "cur_20260613_001",
      "type": "code_patch",
      "file": "src/auth/token.py",
      "instruction": "修复 JWT token 过期后不自动刷新的 bug",
      "context": "当前逻辑: token 过期直接返回 401。期望: 过期时用 refresh_token 自动续期",
      "suggested_diff": null,
      "status": "pending",
      "created": "2026-06-13T17:30:00Z"
    }
  ],
  "stats": {
    "total": 1,
    "pending": 1,
    "done": 0
  }
}
```

### 7.3 CLI 命令

```bash
# 查看队列
llm-router cursor-list

# 弹出一个待处理任务
llm-router cursor-pop

# 标记完成
llm-router cursor-done cur_20260613_001

# 查看统计
llm-router cursor-stats
```

### 7.4 工作流

```
① llm-router 路由判为 code_patch
② 不调 API → push 到 cursor_queue.json
③ 用户看到: "→ Cursor Queue (1 pending)"
④ 用户: llm-router cursor-pop → 复制内容
⑤ 用户: 粘贴到 Cursor Composer → 执行修改
⑥ 用户: llm-router cursor-done <id>
```

---

## 8. 代码来源映射

| 文件/模块 | 来源 | 操作 |
|---|---|---|
| `classifier.py` | llm-router 原有 | MODIFY: 增加 L1 关键词层 |
| `l1_classifier.py` | brentsWorks `classification.py` | NEW: 移植+扩展关键词 |
| `prompts/classifier_v3.txt` | llm-router `classifier_v2.txt` | MODIFY: 输出改为 task_type |
| `router.py` | llm-router 原有 | MODIFY: 路由维度翻转 |
| `profiles.py` → `routing_table.py` | llm-router 原有 | MODIFY: 改为 task_type→model |
| `policies/custom.yaml` | llm-router `standard.yaml` | NEW: 新策略文件 |
| `budget.py` | llm-router 原有 | MODIFY: 单阈值→4区 |
| `task_decomposer.py` | — | NEW: 约 200 行 |
| `cursor_queue.py` | — | NEW: 约 100 行 |
| `response_validator.py` | — | NEW: 约 100 行 |
| `orchestrator.py` | llm-router 原有 | KEEP (不改) |
| `gates.py` | llm-router 原有 | KEEP (不改) |
| `health.py` | llm-router 原有 | KEEP (不改) |
| `cost.py` | llm-router 原有 | KEEP (不改) |
| `cache.py` | llm-router 原有 | KEEP (不改) |
| `config.py` | llm-router 原有 | KEEP (不改) |
| 所有 `*_adapter.py` | llm-router 原有 | KEEP (不改) |

---

## 9. 改动清单

### 9.1 KEEP (不动) — llm-router 基础设施

- MCP 服务器框架 (`server.py`, `tools/`)
- 断路器 + 健康检查 (`gates.py`, `health.py`)
- 成本追踪 (`cost.py`, SQLite)
- Lit eLLM 集成 (`providers.py`, `router.py` 底层)
- 缓存 (`cache.py`, `semantic_cache.py`)
- 模型适配器 (`router.py` 中的 Claude/GPT/DeepSeek 调用)
- 安装钩子 (`install_hooks.py`, `hooks/`)

### 9.2 NEW (新增)

| 模块 | 文件 | 行数 (估) | 说明 |
|---|---|---|---|
| L1 关键词分类 | `l1_classifier.py` | ~120 | 移植 brentsWorks + 扩展 |
| TaskDecomposer | `task_decomposer.py` | ~200 | LLM 拆任务 |
| Cursor Queue | `cursor_queue.py` | ~100 | JSON 文件队列 |
| 后验校验 | `response_validator.py` | ~100 | 语法/结构/标记检查 |

### 9.3 MODIFY (修改)

| 文件 | 改什么 | 改动量 |
|---|---|---|
| `classifier.py` | 增加 L1 关键词层调用 | ~30行 |
| `prompts/classifier_v2.txt` → `classifier_v3.txt` | 输出从 complexity→task_type | 全改写 |
| `router.py` 路由核心 | `_COMPLEXITY_TO_PROFILE` → `TASK_TO_MODEL` | ~50行 |
| `profiles.py` | 加 `TASK_TO_MODEL` + `FALLBACK_CHAINS` | ~60行 |
| `policies/` | 写 `custom.yaml` 策略 | 新文件 |
| `budget.py` | 单阈值→4区渐进 | ~30行 |

---

## 10. 使用流程示例

### 示例 1: 简单实现任务

```
用户: "帮我写一个 Python 装饰器，用来测量函数执行时间"

→ L1 关键词匹配: "写一个"+"实现"+"编写" → implementation, confidence 0.85
→ 高置信度，跳过 L2
→ 路由: implementation → openai/gpt-4o
→ 预算: green zone (32%)
→ GPT-4o 调用 → 返回代码
→ 后验校验: 代码块完整 ✓

输出:
{
  "task_type": "implementation",
  "selected_model": "openai/gpt-4o",
  "reason": "L1 heuristic match: implementation, confidence 0.85",
  "cost_level": "medium",
  "result": "import time\nfrom functools import wraps\n\ndef measure_time(func):\n    ..."
}
```

### 示例 2: 大任务分解

```
用户: "帮我做一个用户登录系统，包括数据库设计、后端 API 和前端表单"

→ TaskDecomposer (DeepSeek): split=true, 5 个子任务
  ├→ "设计 users 表 schema" → architecture → Claude
  ├→ "实现 POST /login 路由" → implementation → GPT
  ├→ "实现 JWT token 生成验证" → implementation → GPT
  ├→ "写登录表单 HTML+CSS" → boilerplate → DeepSeek
  └→ "写登录单元测试" → bulk_generation → DeepSeek

→ 5 个子任务并行执行
→ ResponseAggregator 聚合输出
→ 成本: 1×Claude(高) + 2×GPT(中) + 2×DeepSeek(低)
```

### 示例 3: Cursor 文件修改

```
用户: "帮我把 src/auth.py 里的 JWT token 过期时间从 15 分钟改成 1 小时"

→ L1 关键词: "修改文件"+"改" → code_patch, confidence 0.78
→ 路由: code_patch → cursor_queue
→ push 到 cursor_queue.json
→ 用户看到: "→ Cursor Queue (1 pending, id: cur_20260613_003)"

输出:
{
  "task_type": "code_patch",
  "selected_model": "cursor_queue",
  "reason": "File-level edit — pushed to Cursor Queue",
  "cost_level": "low",
  "result": "Task queued. Run `llm-router cursor-pop` to retrieve."
}
```

### 示例 4: 预算渐进降级

```
预算消耗: 78% (orange zone)

用户: "帮我写 50 个测试用例"

→ L1+L2: bulk_generation → DeepSeek (正常)
→ 预算检查: orange zone → 已经是 DeepSeek (最便宜)，不降级 ✓

用户: "帮我设计一个新的支付系统架构"

→ L1+L2: architecture → Claude
→ 预算检查: orange zone → 非"关键任务"范畴? 不，architecture 是关键
→ 保持不变 → Claude ✓
→ 如果是 implementation 任务 → 会降级到 DeepSeek
```

---

## 附录 A: 竞品调研摘要

| 项目 | 匹配度 | 核心差异 |
|---|---|---|
| llm-router (ypollak2) | **4/6** | 底子 — MCP+断路+成本，分类为复杂度维度 |
| brentsWorks/llm-router | 3.5/6 | 分类参考 — 3 层门控 (关键词+RAG+LLM) |
| xRouter (Salesforce) | — | RL 训练路由器，学术方向，不可直接复用 |
| ClawRouter | 2/6 | 15 维评分，USDC 支付，个人用太重 |
| skill-model-router | 2/6 | 零依赖 Markdown，太轻 |

完整调研见 `market-research.html` (浏览器的第 4 屏)。

## 附录 B: 自我审查修正记录

设计过程中的 5 个不严谨点及修正：

| # | 原问题 | 修正 |
|---|---|---|
| 1 | 纯关键词分类太脆弱 | 加 L2 LLM 分类器兜底 |
| 2 | 降级链一刀切 (Claude→GPT→DeepSeek) | 任务感知降级: 每条映射独立链 |
| 3 | 只看类型不看复杂度 | 加 1-5 复杂度评分修正升/降档 |
| 4 | 预算断崖式控制 (80%) | 改 4 区渐进 (0-60-75-90%) |
| 5 | 无响应质量校验 | 加轻量后验 (语法/结构/标记) |

---

## 附录 C: 下一步实施计划

1. **安装 llm-router** — `pip install llm-routing` ✅ 已完成
2. **写 L1 关键词分类器** — 移植 brentsWorks KeywordClassifier
3. **改写分类 prompt** — `classifier_v3.txt`
4. **改写路由核心** — `router.py` 维度翻转
5. **写自定义 YAML 策略** — `custom.yaml`
6. **实现 TaskDecomposer** — 新模块
7. **实现 Cursor Queue** — 新模块
8. **实现后验校验** — 新模块
9. **渐进预算控制** — 改 budget.py
10. **端到端测试** — 覆盖 4 种示例场景

---

> **结论:** 拿 llm-router 做底子，不动基础设施，只改分类+路由+加 4 个新模块。
> 改动量: ~600 行新代码 + ~200 行修改 = 可控。
