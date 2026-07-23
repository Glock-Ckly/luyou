# AI Model Router 五页 Demo 落地计划

本文件整理两份用户清单，并把工程目标收敛为仓库现有 Python 路由核心之上的五页可运行 Demo。

## 目标

```text
用户任务 → 分类与复杂度 → 路由与预算 → Provider / Model → 执行 → Retry / Fallback → Trace
```

- 复用现有 `dispatcher`、`routing_table`、预算适配器和 Cursor Queue。
- 路由实验室调用真实 `/api/route`，不制作静态假数据流程。
- Provider 页面从路由代码生成模型目录。
- 可靠性页面执行可重复的 Fallback 演练并输出 Trace。
- 架构页面呈现 Specification、DDD、Port / Adapter 与工程决策。
- 不读取、展示或提交真实 API Key。

## MVP 边界

### 本次实现

- 统一的本地 HTTP 控制台与 JSON API。
- 任务类型、复杂度和预算压力驱动的模型路由。
- Provider、模型层级、成本和路由使用情况展示。
- 真实任务分发、执行时间线与 Cursor Queue 状态。
- Retry / Fallback 演练、错误分类和 Trace ID。
- 响应式五页界面与基础无障碍支持。

### 暂不实现

- 多租户、计费结算、复杂权限和数据库。
- 生产级熔断、限流、分布式状态和 Kubernetes。
- 为展示效果强行把现有单体改成 Spring Boot / gRPC 微服务。
- 未配置密钥时主动调用收费 Provider。

核心业务正确、边界清晰且 Contract 稳定后，再评估服务拆分与 gRPC。

## 五页信息架构

### 1. Command Center

展示 Git 版本、预算压力、模型与 Provider 数量、Request Lifecycle，并提供五页入口。

### 2. Routing Lab

提交真实任务，展示 Task Type、Complexity、Model、Executor、Budget、时间线、子任务和 Cursor Queue。

### 3. Provider Registry

按 Provider 聚合模型，展示 Tier、输入/输出成本、路由使用情况、Provider Contract 与 Adapter 接入步骤。

### 4. Reliability Lab

选择任务、复杂度、预算和故障模型，执行 Retry / Fallback 演练，展示候选链、错误分类、最终模型与 Trace ID。

### 5. Architecture & Specs

展示 Gateway、Routing、Provider、Execution、Skill、Agent 边界，主流程、失败流程、ADR 和测试闭环。

## API Contract

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/api/meta` | 项目、Git、预算与统计 |
| `GET` | `/api/catalog` | Provider、Model 与路由目录 |
| `GET` | `/api/specs` | 领域边界、生命周期与 ADR |
| `GET` | `/api/cursor/queue` | Cursor 待执行任务 |
| `POST` | `/api/route` | 真实任务分发 |
| `POST` | `/api/reliability/simulate` | Retry / Fallback 演练 |

所有 API 使用 UTF-8 JSON。错误响应至少包含 `error`；可靠性响应包含 `trace_id`、`attempts` 和 `outcome`。

## 领域边界

| Domain | 负责 | 不负责 |
|---|---|---|
| Gateway | HTTP、校验、响应标准化 | 模型选择、Provider 细节 |
| Routing | 分类、策略、模型决策、预算 | 直接调用 Provider API |
| Provider | 模型目录、能力、成本、适配契约 | 用户认证、路由决策 |
| Execution | 执行器、超时、结果归一化 | 修改路由规则 |
| Skill | 可复用的确定性能力 | 自主规划与无限循环 |
| Agent | 受约束的目标分解和决策增强 | 成为基础路由单点依赖 |

## 可靠性规则

- 临时网络错误、超时和部分 `5xx` 可重试。
- 认证、校验和策略禁止错误直接失败。
- 模型不可用、重试耗尽和速率限制触发 Fallback。
- 尝试次数受候选链长度限制，不允许无限重试。
- 每次演练记录 Trace ID、候选模型、错误类型、动作和耗时。
- 全部候选失败时返回结构化 `all_providers_failed`。

## 执行顺序

1. 整理规格、MVP 边界和五页验收标准。
2. 扩展服务端静态资源、Catalog、Specs、Reliability API。
3. 建立共享 Design System、导航与五个页面。
4. 接入真实路由和可靠性演练交互。
5. 增加测试与文档并运行仓库验收。
6. 每个逻辑修改完成后单独提交并推送。

## 完成标准

- [ ] 五页可以互相导航，桌面和移动宽度均可使用。
- [ ] `/api/route` 保持兼容并继续使用真实路由链路。
- [ ] Catalog 数据来自 `routing_table.py`，不重复维护。
- [ ] Fallback 覆盖首选成功、一次降级和全部失败。
- [ ] Trace、错误分类、候选链与最终结果可见。
- [ ] 无 Provider 密钥也可完整演示控制台。
- [ ] 新增测试和原有 acceptance 均通过。
- [ ] README 包含启动方式与五页地址。

