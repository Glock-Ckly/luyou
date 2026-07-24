# AI Model Router 任务执行闭环 DDD/TDD 改正与实施清单

> 编制日期：2026-07-24  
> 适用仓库：C:/Codex/luyou  
> 目标：在现有路由、Provider、可靠性、Gateway 和五页 Demo 基础上，补齐“生成完整执行提示词 → 强制绑定路由模型/执行器 → 自动执行 → 验证结果 → 返回可阅读 Markdown 产物”的真实任务闭环。

---

# 0. 本轮改正的核心结论

当前项目已经完成：

- [x] 任务分解、分类和路由决策
- [x] Provider 模型调用与 Retry/Fallback
- [x] Codex CLI 非交互调用
- [x] Cursor Queue 入队
- [x] Trace、Attempt、Metrics 和 Gateway
- [x] 五页 Demo、Docker 定义、Skills 和边界 Agents

但当前“路由完成”等于“任务真实完成”的条件仍不成立：

- [ ] Codex 路径没有强制证明路由模型就是实际执行模型
- [ ] Codex 仅收到 Preferred execution model 文本提示，执行适配器没有模型绑定契约
- [ ] Cursor Queue 只是写入任务，仍需要人工 pop 和处理
- [ ] Provider 文本调用可以生成回答，但不能自动修改仓库、运行测试或提交变更
- [ ] Planner 只读取用户任务、分类结果和默认执行器，没有读取项目规格、AGENTS、相关代码、测试、Git 状态和文件边界
- [ ] Planner 输出仍是松散 dict，没有领域类型、Schema 版本和不可覆盖的安全边界
- [ ] 没有稳定生成并保存“可交给任意 AI 阅读”的完整 Markdown Execution Package
- [ ] 没有 Execution Job 状态机、租约、幂等键、取消、恢复和结果持久化
- [ ] 没有自动验证 AI 产物是否满足 Acceptance Criteria
- [ ] 没有统一管理 AI 允许修改的文件、命令、最大步骤、最大成本和超时
- [ ] 没有区分 Answer、Plan、Patch、Repository Change、Assessment Report 等不同交付类型

本轮目标不是继续增加模型数量，而是建立可验证的执行闭环：

    User Request
      → Context Snapshot
      → Prompt Package
      → Route Decision
      → Enforced Model Binding
      → Executor
      → Artifact / Repository Change
      → Verification
      → Repair or Final Result
      → Markdown Execution Report

---

# 1. 必须遵循的工程流程

每一个阶段严格执行：

    Problem
      → Specification
      → DDD Boundary
      → Contract
      → Red Test
      → Minimum Implementation
      → Green Test
      → Refactor
      → Secondary Assessment
      → Commit
      → Push

强制规则：

- [ ] 一个阶段只解决一个可验证问题
- [ ] 行为改变前先修改规格或 ADR
- [ ] 先记录 Red，再写最小实现
- [ ] 不允许通过降低断言、跳过测试或吞掉错误获得 Green
- [ ] 每次代码更新后运行相关测试和完整离线回归
- [ ] 每次代码更新后在 docs/assessment 生成二次评估
- [ ] 每个逻辑阶段独立 Commit 并立即 Push 到 main
- [ ] 在线模型评估与确定性测试分开报告
- [ ] 未强制绑定模型时不得返回 model_binding=enforced
- [ ] 未运行验证命令时不得返回 verified=true
- [ ] 未修改仓库时不得把文本回答描述为 repository_completed

---

# 2. DDD 领域划分

## 2.1 Request Context

负责：

- [ ] 接收用户目标、工作目录、交付类型和约束
- [ ] 生成 JobId、TraceId 和 IdempotencyKey
- [ ] 校验工作目录与权限范围

不负责：

- [ ] 不选择模型
- [ ] 不调用 Provider
- [ ] 不生成最终提示词

## 2.2 Project Context Domain

负责：

- [ ] 读取仓库级 AGENTS.md 和适用的嵌套 AGENTS.md
- [ ] 读取 specs、ADR、README、STATUS 和清单
- [ ] 收集 Git 分支、HEAD、工作区状态和最近提交
- [ ] 根据任务检索相关符号、文件、测试和依赖
- [ ] 生成有大小上限的 ProjectContextSnapshot

不负责：

- [ ] 不决定路由模型
- [ ] 不修改仓库
- [ ] 不把密钥、完整环境变量或无关文件放入上下文

## 2.3 Prompt Engineering Domain

负责：

- [ ] 将用户目标、项目上下文、DDD 边界、文件范围、Acceptance Criteria、TDD 流程和返回 Schema 编译成 PromptPackage
- [ ] 生成机器可读 JSON 和人类可读 Markdown 两种表示
- [ ] 为每个 PromptPackage 记录模板版本和内容哈希
- [ ] 保证安全边界由后端确定，Planner 只能补充建议，不能覆盖

不负责：

- [ ] 不选择 Provider
- [ ] 不执行命令
- [ ] 不直接提交代码

## 2.4 Routing Domain

负责：

- [x] 根据 TaskType、Complexity、Budget、Capability 和 Availability 选择候选模型
- [ ] 输出强类型 RouteDecision 和 ModelBindingRequirement
- [ ] 明确模型是否必须强制绑定、允许的替代模型和降级条件

不负责：

- [ ] 不拼装完整 PromptPackage
- [ ] 不调用 Codex、Cursor 或 Provider
- [ ] 不验证代码结果

## 2.5 Execution Domain

负责：

- [ ] 创建 ExecutionJob Aggregate
- [ ] 将 RouteDecision、PromptPackage 与 ExecutorBinding 组合成 WorkOrder
- [ ] 管理状态机、超时、取消、租约、Retry 和执行结果
- [ ] 通过 TaskExecutor Port 调用 Codex、Provider Worker 或 Cursor Worker

不负责：

- [ ] 不自行重新分类或改变业务路由
- [ ] 不允许执行器静默使用另一个模型

## 2.6 Verification Domain

负责：

- [ ] 根据交付类型选择验证策略
- [ ] 运行允许的测试、编译、Lint、diff 检查和验收脚本
- [ ] 将验证结果归一化为 VerificationReport
- [ ] 决定成功、可修复失败或最终失败

不负责：

- [ ] 不修改原始 Acceptance Criteria
- [ ] 不把在线模型自我评价当作唯一证据

## 2.7 Delivery Domain

负责：

- [ ] 保存 Prompt Markdown、执行日志摘要、Patch、测试证据和最终报告
- [ ] 返回可阅读的 Execution Report Markdown
- [ ] 在获得明确权限后执行 Commit/Push

不负责：

- [ ] 不自动扩大 Git 写入范围
- [ ] 不在验证失败时推送生产代码

---

# 3. 核心领域模型

## 3.1 Value Objects

- [ ] JobId
- [ ] TraceId
- [ ] IdempotencyKey
- [ ] ProjectSnapshotId
- [ ] PromptPackageId
- [ ] PromptTemplateVersion
- [ ] PromptContentHash
- [ ] ExecutorId
- [ ] ModelBinding
- [ ] FileScope
- [ ] CommandPolicy
- [ ] PermissionPolicy
- [ ] ExecutionBudget
- [ ] AcceptanceCriterion
- [ ] ArtifactId
- [ ] VerificationStatus

## 3.2 Entities

- [ ] ExecutionJob
- [ ] WorkOrder
- [ ] ExecutionAttempt
- [ ] Artifact
- [ ] VerificationRun

## 3.3 ExecutionJob Aggregate

必须拥有：

- [ ] job_id
- [ ] trace_id
- [ ] original_request
- [ ] project_snapshot_id
- [ ] prompt_package_id
- [ ] route_decision
- [ ] executor_binding
- [ ] state
- [ ] attempts
- [ ] artifacts
- [ ] verification_report
- [ ] created_at / updated_at

状态机：

    RECEIVED
      → CONTEXT_BUILDING
      → CONTEXT_READY
      → PROMPT_COMPILING
      → PROMPT_READY
      → ROUTED
      → DISPATCHED
      → RUNNING
      → VERIFYING
      → SUCCEEDED

失败与人工分支：

    RUNNING → RETRY_WAIT → DISPATCHED
    VERIFYING → REPAIRING → RUNNING
    ANY_ACTIVE_STATE → CANCELLED
    ANY_ACTIVE_STATE → FAILED
    ROUTED → WAITING_APPROVAL → DISPATCHED

非法转换必须抛出 Domain Error，并有单元测试。

---

# 4. PromptPackage 契约

## 4.1 后端必须自动生成的完整内容

每个任务生成：

    artifacts/execution-packages/<job_id>.md
    artifacts/execution-packages/<job_id>.json

Markdown 至少包含：

1. Execution Metadata
   - Job ID
   - Trace ID
   - Route Decision
   - Required Model
   - Actual Executor
   - Template Version

2. User Goal
   - 原始目标
   - 期望交付类型
   - 明确非目标

3. Repository Context
   - 仓库绝对路径
   - Branch / HEAD / Dirty State
   - 适用 AGENTS 指令
   - 相关 specs 和 ADR
   - 相关源文件和测试文件

4. DDD Boundary
   - 本任务属于哪个 Bounded Context
   - 允许修改什么
   - 禁止修改什么
   - 依赖方向

5. Requirements
   - 功能需求
   - 错误行为
   - 安全要求
   - 可观测性要求

6. TDD Procedure
   - 必须先创建的 Red Test
   - 最小 Green 条件
   - Refactor 限制
   - 完整回归命令

7. File Scope
   - allowed_read_paths
   - allowed_write_paths
   - forbidden_paths

8. Command Policy
   - allowed_commands
   - commands_requiring_approval
   - forbidden_commands

9. Acceptance Criteria
   - Given / When / Then
   - 可执行验证命令

10. Required Output Schema
    - summary
    - changed_files
    - tests_added
    - tests_run
    - verification
    - remaining_risks
    - artifacts
    - actual_model
    - model_binding_status

## 4.2 编译规则

- [ ] 基础模板必须是确定性的，不依赖 Planner 正确性
- [ ] Planner 只能填写 summary、direction 和建议步骤
- [ ] Planner 不得覆盖 allowed_write_paths、forbidden_paths、权限、预算和验收标准
- [ ] 缺少 Acceptance Criteria 时，后端必须先生成草案并进入 WAITING_APPROVAL 或安全默认策略
- [ ] 超出上下文预算时优先保留规格、边界、相关代码签名和测试，不保留无关大文件
- [ ] PromptPackage 必须可重建、可哈希、可审计
- [ ] PromptPackage 中不得写入 API Key、Token、完整环境变量和敏感日志

---

# 5. 模型真实绑定契约

## 5.1 必须解决的现有问题

当前 Codex 路径只是把以下文本加入 Prompt：

    Preferred execution model from router: <model>

这不是模型绑定，只是建议。

## 5.2 新契约

TaskExecutor.execute 必须接收：

    WorkOrder
      - required_model
      - allowed_fallback_models
      - binding_mode
      - prompt_package
      - workdir
      - timeout
      - permissions

binding_mode：

- [ ] ENFORCED：执行器必须使用 required_model
- [ ] VERIFIED_FALLBACK：执行器可以使用白名单中的替代模型，并返回原因
- [ ] EXECUTOR_MANAGED：执行器不能绑定具体模型，必须明确标识，不能伪装为 ENFORCED

执行结果必须返回：

- [ ] requested_model
- [ ] actual_model
- [ ] model_binding_status
- [ ] executor_id
- [ ] executor_version
- [ ] fallback_reason

硬性验收：

- [ ] 如果 Codex Adapter 支持模型参数，测试必须验证实际 argv/配置包含路由模型
- [ ] 如果 Codex Adapter 不支持该模型，必须拒绝、切换到可绑定的 Provider Worker，或标记 EXECUTOR_MANAGED
- [ ] 禁止只在 Prompt 中写模型名称后返回 enforced
- [ ] LiteLLM Provider 返回的实际模型必须与允许列表一致
- [ ] 模型不一致时生成 ModelBindingViolation，不得静默成功

---

# 6. Executor 类型与交付能力

## 6.1 ProviderAnswerExecutor

适用：

- [ ] 架构建议
- [ ] 文本生成
- [ ] 数据转换
- [ ] 不需要仓库工具的任务

交付类型：ANSWER 或 DOCUMENT。

不得宣称：

- [ ] 不得宣称修改了仓库
- [ ] 不得宣称运行了测试

## 6.2 CodexRepositoryExecutor

适用：

- [ ] 实现、调试、重构
- [ ] 需要读取和修改仓库
- [ ] 需要运行测试和生成 Patch

必须：

- [ ] 接收完整 PromptPackage
- [ ] 强制 FileScope 和 CommandPolicy
- [ ] 捕获 exit code、stdout 摘要、changed files 和最终消息
- [ ] 返回实际模型绑定信息
- [ ] 不在 Executor 内决定业务路由

## 6.3 CursorWorkerExecutor

当前 Cursor Queue 需要改成真实 Worker：

- [ ] 支持 claim/lease/heartbeat
- [ ] 支持 pending/running/verifying/succeeded/failed
- [ ] 支持结果回写和 Artifact 上传
- [ ] 支持幂等执行
- [ ] Worker 崩溃后租约超时可恢复
- [ ] 保留人工模式，但不能把 queued 当作 completed

## 6.4 DocumentExecutor

用于用户只需要可阅读 Markdown 的情况：

- [ ] 生成完整 Execution Package
- [ ] 可选择只输出计划而不修改代码
- [ ] 返回 Markdown 文件路径和内容摘要
- [ ] 仍需经过 Schema 和敏感信息验证

---

# 7. Verification 闭环

## 7.1 验证策略

按交付类型选择：

- ANSWER：Schema、引用完整性、禁止虚假执行声明
- DOCUMENT：Markdown 结构、必需章节、敏感信息扫描
- PATCH：diff、目标文件范围、单元测试
- REPOSITORY_CHANGE：Red/Green 证据、完整回归、git diff --check
- RELEASE：全部测试、版本、状态文档、Commit/Push 权限

## 7.2 自动修复循环

- [ ] Verification 失败后只允许在剩余 max_repair_attempts 内修复
- [ ] Repair Prompt 必须包含失败证据，不重新发送全部无关上下文
- [ ] 修复不得扩大 FileScope
- [ ] 非确定性在线失败不得无限重试
- [ ] 达到上限后返回 FAILED_WITH_EVIDENCE

## 7.3 成功定义

只有同时满足以下条件才可标记 SUCCEEDED：

- [ ] Executor 返回成功
- [ ] actual_model 与绑定契约一致
- [ ] 所有必需 Artifact 存在
- [ ] Acceptance Criteria 全部通过
- [ ] 必需验证命令返回 0
- [ ] 未修改 forbidden_paths
- [ ] 敏感信息扫描通过

---

# 8. API 改正清单

保留现有 POST /api/route 作为路由预览或同步简单任务入口。

新增：

- [ ] POST /api/execution/jobs
- [ ] GET /api/execution/jobs/<job_id>
- [ ] GET /api/execution/jobs/<job_id>/prompt.md
- [ ] GET /api/execution/jobs/<job_id>/artifacts
- [ ] POST /api/execution/jobs/<job_id>/approve
- [ ] POST /api/execution/jobs/<job_id>/cancel
- [ ] POST /api/execution/jobs/<job_id>/retry

创建请求至少包含：

    goal
    workdir
    delivery_type
    allowed_write_paths
    acceptance_criteria
    approval_mode
    max_steps
    max_cost_usd
    timeout_seconds
    idempotency_key

创建响应至少包含：

    job_id
    trace_id
    state
    route_decision
    requested_model
    model_binding_status
    prompt_package_url

---

# 9. 推荐项目结构

    src/model_router/
      domain/
        execution_job.py
        prompt_package.py
        work_order.py
        verification.py
        execution_errors.py
      application/
        create_execution_job.py
        build_project_context.py
        compile_prompt_package.py
        execute_routed_job.py
        verify_execution.py
        finalize_delivery.py
      ports/
        project_context_port.py
        prompt_compiler_port.py
        task_executor_port.py
        execution_repository.py
        verification_port.py
        artifact_store.py
        approval_port.py
      adapters/
        context/
          repository_context.py
        prompts/
          markdown_prompt_compiler.py
        executors/
          codex_executor.py
          provider_answer_executor.py
          cursor_worker_executor.py
          document_executor.py
        persistence/
          sqlite_execution_repository.py
          filesystem_artifact_store.py
        verification/
          command_verifier.py
        http/
          execution_gateway.py

    artifacts/execution-packages/
    artifacts/execution-results/
    tests/domain/
    tests/application/
    tests/contract/
    tests/integration/

---

# 10. 分阶段 TDD 实施清单

## Phase 0：规格、ADR 和兼容策略

Specification：

- [ ] 增加任务执行闭环规格
- [ ] 定义 Route Preview 与 Execute Job 的区别
- [ ] 定义模型绑定语义
- [ ] 定义 PromptPackage Contract
- [ ] 定义 Artifact 和 Verification Contract
- [ ] ADR：确定性 Prompt Compiler + 可选 Planner Enrichment
- [ ] ADR：执行 Job 使用持久化状态而不是 HTTP 请求内长时间阻塞
- [ ] ADR：Codex/Cursor/Provider 三类 Executor 能力边界

验收：

- [ ] 文档明确当前能力和目标能力
- [ ] 不破坏现有 /api/route
- [ ] 记录迁移和回滚方案

阶段完成后：评估、Commit、Push。

## Phase 1：ExecutionJob 领域模型

Red Tests：

- [ ] 合法状态转换
- [ ] 非法状态转换
- [ ] 幂等创建
- [ ] Attempt 追加规则
- [ ] 成功前必须存在 VerificationReport
- [ ] 取消后不得再次运行

Green：

- [ ] 实现强类型 Aggregate 和 Domain Errors
- [ ] 不引入 HTTP、LiteLLM、subprocess 或数据库依赖

阶段完成后：完整离线回归、评估、Commit、Push。

## Phase 2：Project Context Snapshot

Red Tests：

- [ ] 读取适用 AGENTS 指令
- [ ] 收集 Git branch/HEAD/dirty state
- [ ] 只收集相关 specs、ADR、代码和测试
- [ ] 超出预算时按优先级裁剪
- [ ] 不读取 .env、密钥和 forbidden_paths
- [ ] Snapshot 可重建且哈希稳定

Green：

- [ ] 实现 RepositoryContext Adapter
- [ ] 优先使用 CodeGraph 做符号和调用关系检索；不可用时使用受限原生搜索

阶段完成后：评估、Commit、Push。

## Phase 3：确定性 Prompt Compiler

Red Tests：

- [ ] 相同输入生成相同 Markdown 和 Hash
- [ ] 必需章节完整
- [ ] Planner 不能扩大文件权限
- [ ] Planner 不能修改 Acceptance Criteria
- [ ] Prompt 不包含密钥或完整环境变量
- [ ] JSON 与 Markdown 表示语义一致
- [ ] PromptPackage 可被重新加载

Green：

- [ ] 实现 MarkdownPromptCompiler
- [ ] 保存到 ArtifactStore
- [ ] 保留模板版本

阶段完成后：评估、Commit、Push。

## Phase 4：模型绑定与 Executor Contract

Red Tests：

- [ ] WorkOrder 必须包含 required_model 和 binding_mode
- [ ] Codex argv/config 与 required_model 一致或明确返回 unsupported
- [ ] Provider actual_model 不在允许列表时失败
- [ ] Executor Managed 模式不能返回 enforced
- [ ] Fallback 必须记录原因和实际模型

Green：

- [ ] 定义 TaskExecutor Port
- [ ] 实现 ModelBindingResult
- [ ] 改造 Codex 和 Provider Adapter

阶段完成后：评估、Commit、Push。

## Phase 5：Codex Repository Executor

Red Tests：

- [ ] 将完整 PromptPackage 交给 Codex
- [ ] 正确设置 workdir、timeout 和模型绑定
- [ ] 捕获 changed_files、exit_code 和 final_message
- [ ] 超时后终止进程并返回标准错误
- [ ] 不允许写出 FileScope
- [ ] CLI 不可用时任务失败而不是伪成功

Green：

- [ ] 将现有 codex_executor.py 移入 Executor Adapter 边界
- [ ] 保持 subprocess 细节不进入应用层

阶段完成后：评估、Commit、Push。

## Phase 6：Cursor Worker 执行闭环

Red Tests：

- [ ] Worker claim 具有租约
- [ ] 同一任务不能被两个 Worker 同时执行
- [ ] Heartbeat 延长租约
- [ ] Worker 崩溃后任务可恢复
- [ ] Result 回写后进入 VERIFYING
- [ ] queued 不等于 succeeded

Green：

- [ ] 扩展现有 Cursor Queue
- [ ] 增加 Worker API 和结果回调

阶段完成后：评估、Commit、Push。

## Phase 7：Verification Service

Red Tests：

- [ ] 无测试证据不能成功
- [ ] 修改 forbidden_paths 必须失败
- [ ] git diff --check 失败必须失败
- [ ] 敏感信息命中必须失败
- [ ] 可修复失败生成 Repair WorkOrder
- [ ] 修复次数达到上限后最终失败

Green：

- [ ] 实现 CommandVerifier
- [ ] 实现 VerificationReport 和 Evidence

阶段完成后：评估、Commit、Push。

## Phase 8：Execution Repository 与 Artifact Store

Red Tests：

- [ ] Job 重启后可恢复
- [ ] IdempotencyKey 防止重复任务
- [ ] 状态更新使用乐观锁或版本号
- [ ] Artifact 路径不能逃逸存储根目录
- [ ] Prompt、结果和验证证据可以下载

Green：

- [ ] MVP 使用 SQLite + Filesystem
- [ ] Port 保留未来数据库和对象存储替换能力

阶段完成后：评估、Commit、Push。

## Phase 9：Execution API

Red Tests：

- [ ] 创建 Job 返回 202 和 JobId
- [ ] 相同 IdempotencyKey 返回同一 Job
- [ ] 非法工作目录返回 403
- [ ] 非法 FileScope 返回 400
- [ ] 未授权 approve/cancel 返回 401 或 403
- [ ] Job 查询不泄漏完整敏感 Prompt
- [ ] prompt.md 下载返回 UTF-8 Markdown

Green：

- [ ] 实现异步 Job API
- [ ] 保持现有 OpenAI Chat 和 /api/route 兼容

阶段完成后：评估、Commit、Push。

## Phase 10：自动验证与修复编排

Red Tests：

- [ ] 第一次验证失败后创建一次 Repair WorkOrder
- [ ] Repair Prompt 只包含失败证据和原边界
- [ ] 修复成功后生成最终报告
- [ ] 修复不得更换到未授权模型
- [ ] Max Steps、Max Cost、Timeout 全部生效

Green：

- [ ] 实现 Execute → Verify → Repair → Finalize 用例
- [ ] 所有循环有硬上限

阶段完成后：评估、Commit、Push。

## Phase 11：五页 Demo 扩展

- [ ] Routing 页区分 Route Preview 和 Execute Job
- [ ] 显示 requested_model、actual_model 和 binding_status
- [ ] 显示 PromptPackage Markdown 链接
- [ ] 显示 Job 状态机和 Worker Lease
- [ ] 显示 changed_files 和 Verification Evidence
- [ ] 显示 Retry、Fallback、Repair 的区别
- [ ] 禁止把 queued 显示为 completed

浏览器验收后：评估、Commit、Push。

## Phase 12：最终验收与发布

- [ ] 领域、应用、契约、集成测试全部通过
- [ ] 现有 31 项离线测试不回退
- [ ] 新增执行闭环测试全部通过
- [ ] 五页浏览器验收通过
- [ ] Docker 容器重启后 Job 可恢复
- [ ] 使用 Mock Executor 完成端到端 Repository Change
- [ ] 使用真实 Codex 完成一个受限示例任务
- [ ] 验证实际模型绑定状态
- [ ] 生成最终 Markdown Execution Report
- [ ] README、STATUS、Checklist Matrix 与真实状态一致
- [ ] 最终评估、Commit、Push

---

# 11. 最小可演示场景

## 场景 A：只生成 Markdown 计划

输入：

    分析当前缓存模块并给出 DDD/TDD 改造计划，不修改代码。

预期：

- [ ] 路由到架构模型
- [ ] 生成完整 PromptPackage
- [ ] ProviderAnswerExecutor 返回 Markdown
- [ ] Artifact 可下载
- [ ] 不出现 changed_files 或测试已运行的虚假声明

## 场景 B：真实修改仓库

输入：

    在示例模块中增加一个经过测试的健康检查字段，只允许修改指定两个文件。

预期：

- [ ] 自动收集项目上下文
- [ ] 自动生成完整 PromptPackage
- [ ] 路由到支持仓库工具的 Executor
- [ ] 实际模型绑定可验证
- [ ] 先 Red 后 Green
- [ ] changed_files 未超出范围
- [ ] 自动运行验证
- [ ] 返回 Patch、测试证据和 Markdown 报告

## 场景 C：验证失败自动修复

- [ ] 第一次产物故意导致测试失败
- [ ] Verification 捕获失败
- [ ] 生成受限 Repair Prompt
- [ ] 第二次执行修复
- [ ] 达到上限后停止，不无限循环

## 场景 D：Cursor Worker

- [ ] Job 入队
- [ ] Worker claim 并 heartbeat
- [ ] Worker 返回结果
- [ ] Router 进入 VERIFYING
- [ ] 验证通过后才显示 SUCCEEDED

---

# 12. Definition of Done

本轮改正只有满足以下条件才可宣称完成：

- [ ] 后端能自动生成完整 PromptPackage Markdown 和 JSON
- [ ] PromptPackage 包含项目上下文、DDD 边界、文件权限、TDD 流程和验收标准
- [ ] 路由模型与实际执行模型关系可验证，不再只是 Prompt 建议
- [ ] 至少一个 Repository Executor 能真实修改代码并运行测试
- [ ] Cursor Queue 不再把 queued 当作 completed
- [ ] 每个 ExecutionJob 有持久化状态和可查询 Artifact
- [ ] 自动 Verification 决定成功或失败
- [ ] 修复循环有步骤、成本、次数和超时上限
- [ ] 最终返回人类可阅读 Markdown 报告
- [ ] 所有新功能具有 Red/Green 证据
- [ ] 每阶段有二次评估、Commit 和 Push
- [ ] README、STATUS 和 UI 不包含超前完成声明

---

# 13. 直接交给 AI 的执行指令

AI 在执行本清单时必须：

1. 先读取本文件、AGENTS.md、specs、ADR 和最近 assessment。
2. 一次只执行一个 Phase，不跨阶段实现。
3. Phase 开始前列出目标、Bounded Context、写入范围和 Red Test。
4. 先运行 Red Test 并记录失败原因。
5. 只实现使测试转绿的最小代码。
6. 运行相关测试、完整离线测试、Dashboard 检查和 git diff --check。
7. 在 docs/assessment 创建本阶段二次评估。
8. Commit 并 Push 后，才能开始下一 Phase。
9. 遇到模型无法强制绑定时必须如实返回 unsupported 或 executor_managed。
10. 遇到未授权写入、测试失败、敏感信息或边界不清时停止，不得自行扩大权限。

---

# 14. 最终审计判断

现有项目并非“完全没有执行能力”：Provider 路径已经真实调用模型，Codex 路径已经真实调用 Codex CLI，Cursor 路径已经真实入队。

真正未完成的是：

1. 将路由决定转成可证明的实际模型绑定；
2. 将用户短请求编译成包含项目上下文和工程边界的完整 PromptPackage；
3. 将一次调用升级为有状态、可恢复、可验证的 ExecutionJob；
4. 将 AI 的文本回答升级为可审计的 Artifact、代码变更和验证证据；
5. 将 queued、answered、executed、verified、delivered 五种状态严格区分。

本清单应作为下一轮开发的唯一主执行清单。旧清单继续作为总体工程原则和历史验收依据。
