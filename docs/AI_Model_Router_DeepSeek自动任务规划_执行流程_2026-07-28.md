# AI Model Router DeepSeek 自动任务规划执行流程

> 日期：2026-07-28
> 仓库：`C:\Codex\luyou`
> 流程：Specification -> DDD -> Contract -> Red -> Red-only Commit/Push -> Minimal Green -> Regression -> Secondary Audit -> Commit/Push

## 1. 目标

用户在新建任务时只需输入完整 Goal。后端使用 DeepSeek 生成结构化任务预览，自动建议最适合的技术栈、任务类型、复杂度、优先级、标签、可量化验收标准、可拆分子任务和候选模型，并生成可阅读 Markdown 清单。用户确认后创建 Task；分析、创建与执行保持三个独立动作。

## 2. 当前事实与问题

- 已有 `task_decomposer.py`、`l2_classifier.py`、`relay_llm.py` 和模型路由表，可复用 DeepSeek 调用与基础拆分逻辑。
- 已有 Task CRUD，但创建表单要求用户手工填写分类、状态、技术栈、验收标准和标签。
- Task 页面通过 `localStorage.model_router_api_token` 加 Bearer Token，却没有 Token 设置或 401 恢复入口；启用鉴权时首次访问会连接失败。
- 刷新、搜索、筛选和删除的异步回调没有统一错误处理。
- 当前 Task 不持有 Planning Artifact；不存在“分析预览”和 Markdown 清单 API。
- 顶部全局 `data-header` 与用户要求冲突，Task 页面应移除该区域，但保留任务工作台本身。

## 3. 安全边界

- `DEEPSEEK_API_KEY` 只从进程环境读取，不写入 Git、SQLite、Markdown、日志、API 响应或前端。
- Prompt 只包含 Goal、可选范围和经过筛选的模型能力目录，不包含环境变量或 Provider 凭据。
- DeepSeek 输出是建议，不可直接扩大工作目录、命令、权限或安全边界。
- 后端校验并规范化所有 JSON 字段；无法解析或字段越界时返回 `task_analysis_failed`，不静默伪造成功。
- “推荐模型”不等于实际绑定；输出必须包含 `binding_mode`，当前 Codex/Cursor 最多为 `EXECUTOR_MANAGED`。
- 分析不创建 Task、不执行模型任务、不写用户仓库。只有确认创建时才持久化 Task 与计划 Artifact。

## 4. DDD 设计

### 4.1 Task Context

继续拥有 `ExecutionTask`、状态转换、版本和 CRUD。Scope 保持可选。创建状态不由 LLM 任意指定：后端根据 `needs_clarification` 映射为 `draft` 或 `ready`。

### 4.2 Planning Context

新增 `TaskAnalysis` 值对象，拥有：

- `goal_summary`、`suggested_title`、`task_type`、`complexity`
- `technology_stack`、`priority`、`tags`
- `acceptance_criteria`、`coverage_target_percent`
- `split_recommended`、`subtasks`、`scope`、`needs_clarification`
- `recommended_models`、`planner_model`、`reasoning`
- `checklist_markdown`、`content_hash`

新增 `TaskPlannerPort`。DeepSeek Adapter 只负责调用和响应解析；领域对象负责枚举、范围、百分比、子任务和模型建议结构校验；Application Use Case 负责传入模型目录、映射初始状态并生成预览。

### 4.3 Artifact Boundary

确认创建后，将 Markdown 写入 `.runtime/task-plans/<task_id>.md`。路径由后端从 Task ID 构造，禁止客户端提交文件路径。Task API 返回相对下载 URL，不返回磁盘绝对路径。

## 5. API 契约

### 5.1 分析预览

`POST /api/tasks/analyze`

请求：

```json
{
  "goal": "完整任务描述",
  "scope": "可选范围边界"
}
```

响应 200：

```json
{
  "analysis_id": "analysis_<hash>",
  "task": {
    "title": "...",
    "description": "...",
    "task_type": "implementation",
    "status": "ready",
    "priority": "high",
    "technology_stack": ["Python"],
    "scope": "",
    "acceptance_criteria": ["..."],
    "tags": ["..."]
  },
  "complexity": "T3",
  "coverage_target_percent": 95,
  "split_recommended": true,
  "subtasks": [],
  "recommended_models": [],
  "checklist_markdown": "# ...",
  "planner_model": "deepseek/deepseek-chat",
  "content_hash": "sha256"
}
```

### 5.2 确认创建

`POST /api/tasks` 接受现有 Task 字段，并可附带服务端签发的 `analysis_id` 与 `checklist_markdown`。Application Service 重新校验分析摘要，创建 Task 后通过 `TaskPlanArtifactPort` 写入 Markdown。未附分析时保持现有手工 CRUD 兼容。

### 5.3 清单读取

`GET /api/tasks/<task_id>/plan.md` 返回 UTF-8 Markdown。不存在时返回 404；必须经过现有 Bearer 鉴权和限流。

## 6. DeepSeek Prompt 与算法

使用温度 0 的结构化 JSON Prompt，要求：

1. 从开放语言集合中按生态、库、部署、性能、安全和团队维护成本选择技术栈，不维护“所有语言”的硬编码穷举表。
2. 仅使用现有 Task Type 枚举；复杂度输出 T0-T4。
3. 将大任务拆为 2-12 个可独立验收子任务；小任务保持单体。
4. 每个验收标准必须可测量，覆盖正常路径、边界、异常、安全、性能、兼容和回归；覆盖目标限制在 60-100。
5. 根据仓库模型能力目录给出主模型、Fallback、原因和 binding mode；不得编造目录外模型。
6. 输出标签去重、技术栈去重，字符串去空白，Markdown 由后端确定性编译，不直接信任模型提供的文件内容。
7. 规范化 JSON 使用排序键、UTF-8 和 SHA-256，生成稳定 `analysis_id` 与 `content_hash`。

## 7. UI 流程

1. Task 页面移除顶部全局白色导航区域。
2. 新建任务第一步只显示 Goal 与可选 Scope。
3. 点击“DeepSeek 分析”后展示技术栈、分类、状态、优先级、标签、验收覆盖率、子任务和模型建议。
4. 用户可修改非安全字段并确认创建；范围始终可空。
5. 创建后详情区展示“查看 Markdown 清单”。
6. API 401 时弹出 Token 输入，写入 localStorage 后只重试一次；取消则显示明确错误。
7. 所有刷新、筛选、搜索、删除和提交统一捕获错误并恢复按钮状态。

## 8. 分阶段实施与推送

### Phase A - Specification and Red

- 新增 Planning Contract、JSON Schema、Prompt 模板和失败契约。
- 先写领域、Adapter、HTTP 和 Dashboard Red Tests。
- Red-only commit 必须只含规格、模板和测试；二次审计后立即 push。

### Phase B - Planning Domain and DeepSeek Adapter

- 实现 `TaskAnalysis`、`TaskPlannerPort`、DeepSeek Adapter、确定性 Markdown Compiler。
- 使用 Mock Provider 让领域/Contract Tests 转绿。
- 完整回归、密钥扫描、二次审计、commit、push。

### Phase C - Task Integration and Artifact

- 实现分析预览、确认创建、Markdown Artifact 与读取 API。
- 保持现有 CRUD 向后兼容；失败不产生半成品 Task/Artifact。
- HTTP/持久化集成测试、二次审计、commit、push。

### Phase D - Task UI and Connection Repair

- 移除 Task 页全局顶部区域，改为 Goal-first 两步创建。
- 增加分析预览、子任务、模型建议和 Markdown 入口。
- 修复 Token 首次连接及所有异步错误处理。
- Desktop/Mobile 检查、JS 语法、二次审计、commit、push。

### Phase E - Real DeepSeek Acceptance and Deployment

- 使用环境变量中的临时 Key 做一次最小真实分析，不输出 Key 或完整敏感响应。
- 复跑离线测试、Dashboard、Provider 边界、可靠性和 secret scan。
- 重启本地服务并验证分析、创建、读取清单完整链路。
- 写最终 assessment，commit、push；随后轮换已暴露的 Key。

## 9. 完成定义

- Goal-only 输入可生成结构化分析预览。
- 技术栈、类型、状态、优先级、标签和验收标准均有后端校验。
- 大任务可拆分，小任务不会被强制拆分。
- 模型推荐仅来自当前模型目录并准确表达绑定边界。
- 创建后存在 UTF-8 Markdown 清单且可通过 API 读取。
- Scope 为空时合法。
- 启用 API Token 后浏览器首次访问可恢复连接。
- Task 页面无顶部全局白色区域，桌面和移动布局无溢出。
- 密钥不进入 Git、日志、Artifact、SQLite 或 API 响应。
- 每个 Phase 都有 Red/Green、二次审计、独立 commit 和成功 push 证据。
