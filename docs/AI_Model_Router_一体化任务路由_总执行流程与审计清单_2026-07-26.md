# AI Model Router 一体化任务路由 · 总执行流程与审计清单

> 编制日期：2026-07-26
> 仓库：`C:\Codex\luyou`　远端：`https://github.com/Glock-Ckly/luyou.git`　分支：`main`
> 本文用途：把下列两份文档中的全部待办任务，合并成一条**无歧义、可逐阶段交付、可审计**的执行流水线，直接交给 Codex 或其他工程 Agent 执行。
>
> 上游事实源（本文不替代，只做统一调度）：
> 1. `docs/AI_Model_Router_当前仓库状态审计与一体化任务路由实施路线图_2026-07-26.md`（下称**路线图**）
> 2. `docs/AI_Model_Router_任务执行闭环_DDD_TDD改正清单.md`（下称**改正清单**）
> 3. `docs/assessment/2026-07-26-phase-14-repository-audit-and-claude-handoff.md`（下称**P14 评估**）
>
> 本文只包含流程、清单与验收判据，**不包含任何实现代码**。

---

## 如何使用本文

| 角色 | 用法 |
|---|---|
| 执行 Agent（Codex） | 从 §3 阶段表选择**编号最小的未完成阶段**，只做该阶段。按 §5 该阶段的小节逐条执行，用 §6 审计清单自检，产出 §7 交付物。 |
| 审计 Agent | 只用 §6 与 §9，不看实现细节，只看证据是否存在、是否可复跑、声明是否越界。 |
| 用户 | 用 §3 看整体进度，用 §9 判断"是否真的完成了"。 |

三条不可协商的红线，贯穿全文：

1. **一次只做一个阶段。** 跨阶段实现即视为该阶段失败，必须回退。
2. **先 Red 后 Green。** Red 测试与实现必须是**两个独立 commit**（改正清单未强制，本文强制，理由见 §6.D）。
3. **不许越界声明。** `queued ≠ running ≠ answered ≠ executed ≠ verified ≠ delivered`，术语定义见 §8。

---

## 1. 事实基线校准（2026-07-26 实测）

执行前必须以本节为准。本节数据由实际命令产出，与上游文档不一致处以本节为准。

### 1.1 已实测确认

| 项 | 实测值 | 命令 |
|---|---|---|
| 离线测试 | **40 通过** | `python -m unittest discover -s tests` |
| Dashboard 检查 | **8 通过** | `python scripts/test_dashboard_demo.py` |
| 本地 HEAD | `8babba4 docs: add repository audit and Claude handoff roadmap` | `git log -1` |
| origin/main | `1183926 feat: add persistent execution task CRUD` | `git status -sb` |
| 领先远端 | **2 个提交**（`2e8d962` + `8babba4`） | `git status -sb` |
| 工作区 | clean | `git status --short` |
| 测试文件 | 12 个（unit 5 / integration 5 / contract 2） | `find tests -name "*.py"` |
| 页面 | **6 个** HTML | `ls dashboard/*.html` |
| 源码规模 | 约 6000 行（最大 `dispatcher.py` 661 行） | `wc -l` |

### 1.2 上游文档需要修正的点（Phase 15 必须处理）

| 编号 | 上游说法 | 实测 | 处理 |
|---|---|---|---|
| F-1 | 路线图 §2.2「领先 1 个提交」 | 领先 **2** 个（路线图自身的提交也未推） | 推送时确认两个都上远端 |
| F-2 | 路线图 §21.2 / 改正清单 §13.1 要求「读取根目录 AGENTS.md」 | **仓库中不存在任何 AGENTS.md** | 二选一：创建根 AGENTS.md，或改写两份文档去掉该前置。**推荐创建**，因 Phase 17 的 ProjectContextSnapshot 要读它 |
| F-3 | `docs/checklist-matrix.md` 第 3 行引用 `AI_Model_Router_工程化项目设计与执行清单.md` 与 `新执行清单.md` 作为审计基准 | **两个文件都不在仓库中** | 改为引用现存文档，或补录为 `docs/archive/` |
| F-4 | `README.md` 声明「五页 Demo / 31 通过 / 7 通过」 | 6 页 / 40 / 8 | 更新 README |
| F-5 | `STATUS.md` 最后审计日期 `2026-07-23`，未含 Phase 11-14 | 落后 3 个阶段 | 更新 STATUS |
| F-6 | `scripts/test_dashboard_demo.py` 测试函数名仍为 `test_five_pages_*` | 已覆盖 6 页 | 重命名，避免命名漂移 |
| F-7 | 改正清单 §9 规划 `artifacts/execution-packages/` | 目录不存在，且 `.gitignore` 未涉及 | Phase 19 建目录时同步决定是否入库（推荐 gitignore + `.gitkeep`） |
| F-8 | 改正清单 §12「现有 31 项离线测试不回退」 | 基线已是 40 | 全文回归基线统一为 **40 + 8** |

### 1.3 已实测确认的代码缺陷（Phase 15 修复对象）

| 编号 | 位置 | 缺陷 | 根因 |
|---|---|---|---|
| D-1 | `application/task_service.py:27` | `PUT` 传 `version="abc"` → HTTP 500 | `int(supplied_version)` 抛裸 `ValueError`，`gateway.safe_error_payload` 只识别 `TaskValidationError`，落入 `internal_error` |
| D-2 | `domain/execution_task.py:57` `_strings()` | `tags="ab"` → `["a","b"]` | 对 `str` 直接迭代，未拒绝非 list/tuple 的可迭代对象 |
| D-3 | `application/task_service.py:35` `delete()` | `get` → `ensure_deletable` → `delete` 三步非原子，存在竞态窗口 | 无事务边界，仓储层 `DELETE` 无状态条件 |
| D-4 | `domain/execution_task.py:115` `update()` | 允许 `draft → completed` 任意跃迁 | 无状态机，`status` 只校验枚举成员 |
| D-5 | `adapters/persistence/sqlite_task_repository.py:110` | `delete` 不返回 `rowcount`，删除不存在的 id 静默成功 | 未校验影响行数 |
| D-6 | `runtime.py` | `execution_observer` 为进程内全局单例，重启丢失、多实例不共享 | 无持久化 Observer 适配器 |

> D-1..D-5 必须**先写 Red 测试**再修。D-6 属 Phase 25 范围，Phase 15 只记录不修。

## 2. 两份文档的任务合并与去重

两份上游文档有大量重叠但阶段编号冲突（路线图 Phase 0-12，改正清单 Phase 0-12，含义不同）。本文重新编号为 **P0..P15**，并映射到**仓库 assessment 文件名用的 Phase 15..Phase 30**（因仓库已用到 phase-14，不可复用编号）。

| 本文 | 仓库 Phase | 阶段名 | 路线图来源 | 改正清单来源 |
|---|---|---|---|---|
| P0 | 15 | 基线校准与事实同步 | §18 Phase 0 | §10 Phase 0（部分） |
| P1 | 16 | 执行闭环规格与 ADR | §18 Phase 0 | §10 Phase 0 |
| P2 | 17 | ExecutionJob 领域模型 | §18 Phase 1 | §10 Phase 1 |
| P3 | 18 | ProjectContextSnapshot | §18 Phase 2 | §10 Phase 2 |
| P4 | 19 | TaskSpecification 与 TaskPlan（DAG） | §18 Phase 3 | —（路线图新增） |
| P5 | 20 | 确定性 PromptPackage 编译器 | §18 Phase 4 | §10 Phase 3 |
| P6 | 21 | Job 仓储与 ArtifactStore | §18 Phase 4（隐含） | §10 Phase 8 |
| P7 | 22 | RouteDecision 与 ModelBinding | §18 Phase 5 | §10 Phase 4 |
| P8 | 23 | Execution Job API（异步） | §16 | §10 Phase 9 |
| P9 | 24 | Executor 契约与四类 Executor | §18 Phase 6 | §10 Phase 4/5/6 |
| P10 | 25 | Verification Service | §18 Phase 7 | §10 Phase 7 |
| P11 | 26 | Bounded Repair 循环 | §18 Phase 8 | §10 Phase 10 |
| P12 | 27 | 多 Agent DAG 调度与 Synthesis | §18 Phase 9 | —（路线图新增） |
| P13 | 28 | CostLedger 与可观测性持久化 | §18 Phase 11 | —（路线图新增） |
| P14 | 29 | 一体化 UI（9 页体系） | §18 Phase 10 | §10 Phase 11 |
| P15 | 30 | 最终验收与发布 | §18 Phase 12 | §10 Phase 12 |

### 2.1 里程碑分组

| 里程碑 | 含阶段 | 用户可见结果 | 可对外声明 |
|---|---|---|---|
| **M0 可信起点** | P0-P1 | 文档与代码一致，远端同步，已知缺陷修完 | "基线可信" |
| **M1 Preview 垂直切片** | P2-P8 | 点"分析任务"→ 持久化 Job + Prompt.md + 路由预览 + 成本估算，重启不丢 | "可审计的分析预览"（**不可**说已执行） |
| **M2 真实执行闭环** | P9-P11 | 真执行 → 真验证 → 受限修复 → 带证据的报告 | "单任务可完成并可验证" |
| **M3 多 Agent 与成本** | P12-P13 | 并行子任务 + 综合 + 真实成本台账 | "多 Agent 协作平台" |
| **M4 一体化交付** | P14-P15 | 9 页统一工作台 + 端到端验收 | "路由/任务完成系统完成" |

### 2.2 依赖图（不可乱序的硬依赖）

```text
P0 ──> P1 ──> P2 ──┬──> P3 ──┬──> P5 ──> P6 ──> P8 ──> P9 ──> P10 ──> P11 ──> P12 ──> P14 ──> P15
                    │         │                  ↑                                      ↑
                    └──> P4 ──┘                  │                                      │
                                     P7 ─────────┘                          P13 ────────┘
```

硬依赖理由：

- P5 需要 P3 的 Snapshot 与 P4 的 Subtask 才能编译完整 Prompt。
- P6 必须在 P8 之前：API 返回的 Job 必须已可持久化，否则 API 是假的。
- P7 可与 P3/P4/P5 并行开发，但必须在 P9 之前合并（Executor 需要 binding 契约）。
- P10 必须在 P11 之前：没有 Verification 就没有 Repair 的输入。
- P13 可与 P12 并行，但 P15 验收要求两者都在。

## 3. 阶段总表（进度看板）

状态图例：`☐` 未开始　`◐` 进行中　`☑` 已完成并已 push

| 本文 | 仓库 Phase | 阶段 | 状态 | 预计 commit 数 | 前置 | 阻塞风险 |
|---|---|---|---|---|---|---|
| P0 | 15 | 基线校准与事实同步 | ☐ | 3（Red / Fix / Docs） | 网络可达 GitHub | 无网络则只能本地 commit |
| P1 | 16 | 执行闭环规格与 ADR | ☐ | 2 | P0 | 无 |
| P2 | 17 | ExecutionJob 领域模型 | ☐ | 2 | P1 | 无 |
| P3 | 18 | ProjectContextSnapshot | ☐ | 2 | P2 | AGENTS.md 缺失（F-2） |
| P4 | 19 | TaskSpecification 与 TaskPlan | ☐ | 2 | P2 | 需在线 LLM 做 Plan，须可 mock |
| P5 | 20 | 确定性 PromptPackage 编译器 | ☐ | 2 | P3, P4 | 哈希稳定性（换行/编码） |
| P6 | 21 | Job 仓储与 ArtifactStore | ☐ | 2 | P5 | 路径逃逸安全 |
| P7 | 22 | RouteDecision 与 ModelBinding | ☐ | 2 | P1 | 不得破坏现有 29 条路由 |
| P8 | 23 | Execution Job API | ☐ | 2 | P6, P7 | 不得破坏 `/api/route` 与 `/v1/chat/completions` |
| P9 | 24 | Executor 契约与四类 Executor | ☐ | 4（每 Executor 1） | P8 | Codex CLI 模型参数能力未知 |
| P10 | 25 | Verification Service | ☐ | 2 | P9 | 命令白名单安全 |
| P11 | 26 | Bounded Repair | ☐ | 2 | P10 | 循环上限必须硬编码 |
| P12 | 27 | 多 Agent DAG 与 Synthesis | ☐ | 3 | P11 | 写路径冲突检测 |
| P13 | 28 | CostLedger 与持久化可观测性 | ☐ | 2 | P9 | 价格表外部依赖 |
| P14 | 29 | 一体化 UI | ☐ | 3-9（按页） | P12 | 无 E2E 框架 |
| P15 | 30 | 最终验收与发布 | ☐ | 2 | 全部 | Docker 未实跑 |

合计预计 **35-41 个 commit**，每个 commit 后立即 push。

---

## 4. 每阶段通用执行流程（Codex 必须逐步照做）

任何阶段都走同一条 12 步流水线。缺任何一步该阶段作废。

```text
 1 读取上下文  → 2 声明阶段边界 → 3 改规格/ADR → 4 写 Red 测试
      → 5 跑 Red 并留证据 → 6 commit(Red) → 7 最小实现 → 8 跑 Green
      → 9 全量回归 → 10 二次评估 → 11 commit(Green) → 12 push
```

### 4.1 逐步细则

**Step 1 · 读取上下文（每阶段开头必做，不许跳）**

- [ ] 本文（`docs/AI_Model_Router_一体化任务路由_总执行流程与审计清单_2026-07-26.md`）
- [ ] 根 `AGENTS.md` 与目标目录的嵌套 `AGENTS.md`（若 F-2 已修）
- [ ] 路线图 + 改正清单对应小节
- [ ] `specs/` 下相关规格、`docs/adr/` 全部 ADR 标题
- [ ] `docs/assessment/` 最近 2 份
- [ ] `git status --short --branch` + `git log -5 --oneline`
- [ ] 结构性检索优先用 CodeGraph（`codegraph_context` / `codegraph_impact`），不要 grep 找符号

**Step 2 · 声明阶段边界（写在 commit message 与 assessment 里）**

- [ ] 本阶段解决的**唯一**可验证问题（一句话）
- [ ] 所属 Bounded Context
- [ ] `allowed_write_paths`（精确到文件）
- [ ] `forbidden_paths`（至少含：其他 Context 的 domain、`src/routing_table.py` 的数据部分、`.env`）
- [ ] 明确非目标（至少 3 条）

**Step 3 · 改规格/ADR（行为变化前）**

- [ ] 新增或修改 `specs/**` 中对应契约
- [ ] 若引入新架构决策 → 新增 `docs/adr/ADR-0NN-*.md`（当前最新为 ADR-008）
- [ ] 规格先于测试，测试先于实现

**Step 4-6 · Red**

- [ ] 按该阶段 §5 的 Red 清单逐条写测试
- [ ] 运行并**把失败输出摘要粘进 assessment 的 TDD evidence**
- [ ] 独立 commit，message 前缀 `test:`
- [ ] Red commit **不得包含**任何生产代码改动

**Step 7-8 · Green**

- [ ] 只写使测试转绿的最小代码
- [ ] 禁止：降低断言、`skip`、`try/except: pass`、注释掉测试、放宽枚举
- [ ] 新领域逻辑**不得**写进 `scripts/dashboard_server.py`（该文件只做 HTTP 分发）

**Step 9 · 全量回归（四条命令，全绿才算过）**

```powershell
python -m unittest discover -s tests -v      # 必须 >= 40 且 0 失败
python scripts/test_dashboard_demo.py        # 必须 >= 8 且 0 失败
node --check dashboard/assets/app.js         # 改过 JS 时必跑
git diff --check                             # 空白字符
python skills/model-router-delivery/scripts/assess_phase.py --phase <phase-name>
```

改动 Provider 或可靠性路径时追加：

```powershell
python skills/provider-adapter-contract/scripts/validate_adapter_boundary.py
python skills/router-reliability-audit/scripts/audit_reliability.py
```

**Step 10 · 二次评估**

- [ ] 新建 `docs/assessment/2026-MM-DD-phase-NN-<slug>.md`
- [ ] 用 `skills/model-router-delivery/references/phase-assessment-template.md` 的 6 节结构
- [ ] 必含：Scope / TDD evidence（Red 原文摘要）/ Secondary assessment / Checklist status / Risks / Commit
- [ ] Checklist status 中 **Partial 不得写成 Completed**

**Step 11-12 · Commit 与 Push**

- [ ] Green commit 前缀 `feat:` / `fix:` / `refactor:`
- [ ] assessment 可与 Green 同 commit，也可单独 `docs:` commit（改正清单 §模板倾向单独）
- [ ] `git push origin main` 立即执行；失败则记录原因，**不得**开始下一阶段

## 5. 阶段明细

每个阶段固定 9 个字段：目标 / 前置 / 规格变更 / 边界 / Red 清单 / 最小实现 / 验证 / 非目标 / DoD。

---

### P0 · Phase 15 — 基线校准与事实同步

**目标**　让文档、UI 文案、远端与代码四者一致，并修完 §1.3 中 D-1..D-5 五个已实测缺陷。这是唯一允许"同时改多处"的阶段，因为它不引入新行为。

**前置**　网络可达 GitHub；工作区 clean。

**规格变更**

- [ ] `specs/task-execution/task-crud.md` 补充：非法 `version` 类型 → 400；集合字段必须是数组；删除的原子性；合法状态跃迁矩阵。

**边界**

- 允许写：`README.md`、`STATUS.md`、`docs/checklist-matrix.md`、`AGENTS.md`(新建)、`specs/task-execution/task-crud.md`、`src/model_router/domain/execution_task.py`、`src/model_router/application/task_service.py`、`src/model_router/ports/task_repository.py`、`src/model_router/adapters/persistence/sqlite_task_repository.py`、`src/model_router/adapters/http/gateway.py`、`tests/unit/test_execution_task.py`、`tests/integration/test_task_crud_http.py`、`tests/integration/test_sqlite_task_repository.py`、`scripts/test_dashboard_demo.py`
- 禁止写：`src/routing_table.py`、`src/dispatcher.py`、任何 Provider 适配器

**验收测试清单**（新增行为先写 Red；已满足行为写 Characterization，不得为制造 Red 而破坏现有实现）

| # | 类型 | 测试 | 期望 |
|---|---|---|---|
| R0-1 | Red | `PUT /api/tasks/<id>` body `{"version":"abc"}` | HTTP **400** `invalid_task`，非 500 |
| R0-2 | Red | `PUT` body `{"version":1.5}` | 400 |
| R0-3 | Red | `POST` body `{"tags":"ab"}` | 400（**不是**静默成 `["a","b"]`） |
| R0-4 | Red | `POST` body `{"technology_stack":"python"}` | 400 |
| R0-5 | Red | `POST` body `{"acceptance_criteria":{"a":1}}` | 400 |
| R0-6 | Characterization | `DELETE` 一个 `running` 任务 | 409，且**行仍存在**；当前 HTTP 行为已满足，保留为防回归证据 |
| R0-7 | Characterization | `DELETE` 不存在的 id | 404 `task_not_found`；2026-07-26 基线实测已满足 |
| R0-8 | Red | `update(status=...)` 走非法跃迁 `completed → draft` | `TaskValidationError` |
| R0-9 | Characterization | 合法跃迁矩阵逐项通过 | 见下表；实现跃迁守卫后继续保持通过 |
| R0-10 | Red | `docs`/`README`/`STATUS` 中的页数与测试数与实际一致 | Dashboard 检查新增断言 |
| R0-11 | Red | 仓储以 `expected_status_not_in` 删除 `running` 行 | 单条条件 `DELETE` 返回 409，且行仍存在 |
| R0-12 | Red | 仓储以 `expected_status_not_in` 删除不存在 id | 明确 `TaskNotFound`，不静默成功 |
| R0-13 | Red | 领域层集合字段传入 `bytes` | `TaskValidationError`，不得按字节迭代 |

**建议的合法跃迁矩阵**（P0 定稿，后续 Job 状态机不复用此表）

```text
draft      -> ready | cancelled
ready      -> running | draft | cancelled
running    -> validating | failed | cancelled
validating -> completed | failed | running
completed  -> (终态)
failed     -> ready | cancelled
cancelled  -> (终态)
```

**最小实现**

- [ ] `_strings()` 显式拒绝 `str`/`bytes`/`Mapping`，只接受 list/tuple/set
- [ ] `version` 解析包一层，抛 `TaskValidationError`（而非裸 `ValueError`）
- [ ] `ExecutionTask` 增加 `ensure_transition_allowed(new_status)`，在 `update()` 内调用
- [ ] 仓储 `delete(task_id, *, expected_status_not_in=...)` 用单条带条件 `DELETE` + `rowcount` 判定，把守卫下推到 SQL，消除竞态
- [ ] 仓储 `delete` 的 `rowcount == 0` → 区分 404 与 409
- [ ] 更新 `README.md`（6 页 / 40 / 8 / 补 `/api/tasks` 与 `/api/cursor/queue`）
- [ ] 更新 `STATUS.md`（补 Phase 11-14，日期改 2026-07-26）
- [ ] 修 `docs/checklist-matrix.md` 的失效引用（F-3）
- [ ] 新建根 `AGENTS.md`（内容见下）
- [ ] `test_dashboard_demo.py` 中 `five_pages` → `pages`

**根 AGENTS.md 至少包含**（供 P3 的 Snapshot 读取）

1. 仓库用途与运行时语言（Python 3.12，非 Java，引 ADR-001）
2. 目录职责表（domain / application / ports / adapters / scripts / dashboard）
3. 依赖方向规则（adapters → application → domain，反向禁止）
4. 禁止事项（领域逻辑不进 `dashboard_server.py`；Adapter 不做路由决策；Planner 不改安全边界）
5. 必跑质量门禁四条命令
6. 提交规范（阶段独立 commit + 立即 push + assessment 必写）
7. 术语表引用本文 §8

**验证**　§4.1 Step 9 四条命令 + 手动 `curl` 复跑 R0-1..R0-7。

**非目标**　不新增 ExecutionJob；不改路由数据；不动 Provider；不做 UI 结构变更。

**DoD**

- [ ] 10 条 Red 全部先失败后通过；3 条 Characterization 在 Red 阶段已通过且 Green 阶段不回退
- [ ] 回归 ≥ 40+8 且新增测试数 ≥ 13
- [ ] `2e8d962`、`8babba4` 及本阶段 commit 全部在 `origin/main`
- [ ] `docs/assessment/2026-07-26-phase-15-baseline-calibration.md` 已建
- [ ] README/STATUS/matrix 中不存在超前完成声明

---

### P1 · Phase 16 — 执行闭环规格与 ADR

**目标**　把后续 14 个阶段要用的全部契约、术语和边界一次性写成规格。**本阶段不写任何生产代码**，是纯文档阶段，但必须有可执行的规格一致性检查。

**前置**　P0 已 push。

**规格变更**（新增文件）

- [ ] `specs/execution-closure/overview.md` — 闭环总览：Task → Spec → Context → Plan → Prompt → Route → Job → Execute → Verify → Repair → Deliver
- [ ] `specs/execution-closure/job-lifecycle.md` — Job 状态机（见 P2 定稿表）
- [ ] `specs/execution-closure/prompt-package.md` — PromptPackage 24 个必需段落（路线图 §11）+ 编译规则 + 哈希算法
- [ ] `specs/execution-closure/model-binding.md` — 三种 binding_mode 语义 + ExecutionReceipt 11 字段
- [ ] `specs/execution-closure/verification.md` — 5 类 delivery_type × 验证策略矩阵 + VerificationReport 10 字段
- [ ] `specs/execution-closure/artifact-store.md` — Artifact 命名、路径规则、逃逸防护、保留策略
- [ ] `specs/execution-closure/cost-ledger.md` — 成本记账字段与预算预留语义
- [ ] `specs/execution-closure/terminology.md` — 引用本文 §8 术语表，作为唯一口径

**新增 ADR**

| ADR | 主题 | 必须记录的决策与代价 |
|---|---|---|
| ADR-009 | 确定性 Prompt Compiler + 可选 Planner Enrichment | 为什么安全边界由代码定而非 LLM 定；代价是灵活性下降 |
| ADR-010 | ExecutionJob 用持久化状态而非 HTTP 内阻塞 | 为什么 `POST` 返 202；对现有同步 `/api/route` 的兼容策略 |
| ADR-011 | 四类 Executor 能力边界与 binding 可信度分级 | Codex 只能 EXECUTOR_MANAGED 的理由与将来升级条件 |
| ADR-012 | Verification 决定成功，模型自述不作证据 | 为什么不信 LLM 自评；代价是必须能跑命令 |
| ADR-013 | MVP 存储选型 SQLite + Filesystem | 为什么不上 Postgres/S3；Port 如何保留替换能力 |
| ADR-014 | 多 Agent DAG 的并行准入条件 | 写路径冲突为何是硬阻塞 |

**边界**

- 允许写：`specs/**`、`docs/adr/**`、`docs/checklist-matrix.md`
- 禁止写：`src/**`、`tests/**`（本阶段例外：允许新增一个规格存在性检查测试）

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R1-1 | `/api/specs` 返回内容包含全部新增规格文件 | 通过 |
| R1-2 | Dashboard 检查断言 8 个新规格文件存在且非空 | 通过 |
| R1-3 | 断言 ADR-009..014 存在且含"决策/背景/后果"三段 | 通过 |
| R1-4 | 断言术语表中 6 个状态词各有唯一定义 | 通过 |

**最小实现**　只写文档 + 让上述 4 条断言通过所需的最小检查脚本改动。

**验证**　四条命令 + 人工通读规格自洽性（尤其 P2 状态机与 P10 验证矩阵不冲突）。

**非目标**　不实现任何领域类；不改 API；不改 UI。

**DoD**

- [ ] 8 个规格 + 6 个 ADR 全部落地
- [ ] `/api/specs` 能列出
- [ ] 术语表与本文 §8 逐字一致（避免两处定义漂移）
- [ ] assessment 明确写"本阶段无生产代码变更"

---

### P2 · Phase 17 — ExecutionJob 领域模型

**目标**　纯领域层的 ExecutionJob 聚合与状态机，零外部依赖（无 HTTP、无 sqlite3、无 subprocess、无 litellm）。

**前置**　P1 已 push（状态机规格已定稿）。

**状态机定稿**（路线图 §10.2 与改正清单 §3.3 冲突，本文取路线图的 10 态并补失败分支）

```text
DRAFT ─────────> ANALYZING ─────> WAITING_APPROVAL ─────> READY
                     │                    │                 │
                     v                    v                 v
                  FAILED               CANCELLED          RUNNING
                                                             │
                            ┌────────────────────────────────┤
                            v                                v
                        VERIFYING ──pass──> SUCCEEDED    FAILED
                            │
                       repairable
                            v
                        REPAIRING ──> RUNNING
                            │
                     上限耗尽 v
                          FAILED
```

补充规则：

- 任何非终态 → `CANCELLED` 合法。
- `SUCCEEDED` / `FAILED` / `CANCELLED` 为终态，出边为空。
- `READY → RUNNING` 需要 `approval_status == approved` 或 `approval_mode == auto`。
- `VERIFYING → SUCCEEDED` **必须**已挂载 `verification_report` 且其 `status == PASS`。

**边界**

- 允许写：`src/model_router/domain/execution_job.py`、`src/model_router/domain/execution_errors.py`、`src/model_router/domain/value_objects.py`（或扩展现有 `models.py`）、`tests/unit/test_execution_job.py`、`tests/unit/test_job_state_machine.py`
- 禁止写：任何 `adapters/**`、`application/**`、`scripts/**`

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R2-1 | 全部合法跃迁逐条通过 | 参数化覆盖状态机每条边 |
| R2-2 | 全部非法跃迁抛 `IllegalJobTransition` | 参数化覆盖 `n×n` 减合法边 |
| R2-3 | 终态再跃迁必失败 | 3 个终态 × 任意目标 |
| R2-4 | 同 `IdempotencyKey` 构造两次 → 同 `job_id` | 幂等 |
| R2-5 | `VERIFYING → SUCCEEDED` 无 report | 失败 |
| R2-6 | `VERIFYING → SUCCEEDED` report 为 FAIL | 失败 |
| R2-7 | `CANCELLED` 后追加 attempt | 失败 |
| R2-8 | attempt 序号必须连续递增 | 失败于乱序 |
| R2-9 | 每次状态变更 `version` +1 | 通过 |
| R2-10 | `ExecutionBudget` 超限时拒绝新 attempt | 抛 `BudgetExhausted` |
| R2-11 | `FileScope` 值对象拒绝 `..` 与绝对路径逃逸 | 抛错 |
| R2-12 | 模块 import 不引入 sqlite3/http/litellm | 用 `sys.modules` 断言 |

**最小实现**

- [ ] 值对象：`JobId`、`IdempotencyKey`、`JobState`(Enum)、`ExecutionBudget`、`FileScope`、`CommandPolicy`、`QualityTarget`、`AcceptanceCriterion`
- [ ] 聚合 `ExecutionJob`：字段按路线图 §10.2；所有状态变更走方法，禁止外部直接赋值
- [ ] 错误：`IllegalJobTransition`、`BudgetExhausted`、`JobConflict`、`VerificationMissing`
- [ ] 复用现有 `TraceId`、`ModelId`（`domain/models.py`），**不要重造**

**验证**　四条命令；`tests/unit` 新增数 ≥ 25。

**非目标**　不持久化（P6）；不接 API（P8）；不编译 Prompt（P5）。

**DoD**

- [ ] 状态机测试覆盖**全部** `n×n` 组合，不是抽样
- [ ] R2-12 证明领域层零外部依赖
- [ ] 回归 ≥ 40+8，且总测试数明显上升

---

### P3 · Phase 18 — ProjectContextSnapshot

**目标**　把仓库现状压缩成一个有大小上限、脱敏、可哈希、可重建的快照，供 Prompt 编译使用。

**前置**　P2 已 push；根 `AGENTS.md` 存在（P0 已建）。

**规格变更**　`specs/execution-closure/project-context.md`：采集清单、优先级裁剪顺序、脱敏规则、哈希输入范围。

**边界**

- 允许写：`src/model_router/ports/project_context_port.py`、`src/model_router/adapters/context/repository_context.py`、`src/model_router/domain/project_snapshot.py`、`tests/unit/test_project_snapshot.py`、`tests/integration/test_repository_context.py`
- 禁止写：domain 中已有文件的既有行为；任何执行器

**采集清单与优先级**（超预算时**从下往上**裁）

| 优先级 | 内容 | 来源 |
|---|---|---|
| P1 最高 | 适用 AGENTS 指令（根 + 目标目录嵌套，就近覆盖） | `AGENTS.md` |
| P1 | 相关 specs 与 ADR 标题+摘要 | `specs/**`、`docs/adr/**` |
| P2 | Git branch / HEAD / dirty file 列表（只名不内容） | `git` |
| P2 | 目标文件的**符号签名**（类/函数签名，不含实现体） | CodeGraph 优先，退化用受限解析 |
| P3 | 相关测试文件名 + 测试方法名 | `tests/**` |
| P3 | 依赖清单 | `pyproject.toml` |
| P4 最低 | 相关源文件正文片段 | 按需截取 |

**脱敏硬规则**（命中即拒绝进入快照，并在 `redaction_report` 记数）

- [ ] 路径黑名单：`.env`、`*.env`（除 `config/relay.env.example`）、`.runtime/`、`.git/`、`__pycache__/`、`.cursor/`、`.dispatch/`
- [ ] 内容黑名单正则：`sk-`、`api[_-]?key`、`token`、`secret`、`password`、`Bearer `、私钥头 `-----BEGIN`
- [ ] 命中内容替换为 `[REDACTED:<reason>]`，**不得**静默丢弃（否则哈希不可解释）

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R3-1 | 读取根 AGENTS.md 内容进入快照 | 通过 |
| R3-2 | 嵌套 AGENTS.md 就近覆盖根同名条目 | 通过 |
| R3-3 | 采集 branch/HEAD/dirty | 通过 |
| R3-4 | 只收集与任务相关的 spec/ADR，不全量 | 断言无关文件不在 |
| R3-5 | 超预算时按 P4→P1 顺序裁剪 | 断言 P1 内容仍在 |
| R3-6 | `.env` 文件不被读取 | 断言路径未被 open |
| R3-7 | 内容中的 `sk-xxx` 被替换 | 断言输出无原文 |
| R3-8 | `forbidden_paths` 内文件不进快照 | 通过 |
| R3-9 | 相同仓库状态 → 相同 `snapshot_hash` | 连跑两次相等 |
| R3-10 | 仅 dirty state 变化 → hash 变化 | 通过 |
| R3-11 | 快照可序列化/反序列化后 hash 不变 | 通过 |
| R3-12 | 单文件超大时截断并标记 `truncated=true` | 通过 |
| R3-13 | CodeGraph 不可用时降级到受限搜索且不报错 | 通过 |

**最小实现**

- [ ] `ProjectContextSnapshot` 值对象（含 `snapshot_id`、`snapshot_hash`、`redaction_report`、`truncations`、`size_bytes`）
- [ ] `ProjectContextPort` Protocol
- [ ] `RepositoryContextAdapter`：只读，绝不写文件
- [ ] 哈希用规范化 JSON（键排序、`\n` 统一、UTF-8、无时间戳）

**验证**　四条命令 + 手工在真仓库上跑一次并人工检查输出**无任何密钥**。

**非目标**　不做向量检索/RAG（属 `docs/pending/07`）；不修改仓库；不跑测试命令。

**DoD**

- [ ] 13 条 Red 全过
- [ ] 哈希稳定性连跑 3 次一致
- [ ] 人工确认脱敏有效（assessment 中记录检查方式）

---

### P4 · Phase 19 — TaskSpecification 与 TaskPlan（DAG）

**目标**　把用户 Goal 变成结构化可审批的 Specification，再变成带依赖边的子任务 DAG。

**前置**　P2 已 push。

**规格变更**　`specs/execution-closure/task-plan.md`：Specification 字段、DAG 合法性规则、并行组划分算法、综合策略枚举。

**边界**

- 允许写：`src/model_router/domain/task_plan.py`、`src/model_router/domain/task_specification.py`、`src/model_router/application/build_task_plan.py`、`src/model_router/ports/planner_port.py`、`tests/unit/test_task_plan.py`、`tests/unit/test_task_specification.py`
- 禁止写：`src/task_decomposer.py` 的现有行为（保持兼容，新代码走新路径）

**TaskSpecification 必需字段**

`spec_id` / `task_id` / `goal` / `delivery_type` / `in_scope` / `out_of_scope`(非目标) / `constraints` / `assumptions` / `open_questions`(歧义清单) / `acceptance_criteria`(Given-When-Then) / `quality_target` / `risk_level` / `approval_status` / `version`

**DAG 合法性硬规则**

- [ ] 无环（拓扑排序必须成功）
- [ ] 无孤立节点（每节点或有入边或是根）
- [ ] 每节点必有 `acceptance_criteria` 非空
- [ ] 每节点必有 `inputs` / `outputs` Artifact 声明
- [ ] 同一并行组内**写路径两两不相交**
- [ ] 子任务数上限（建议 12），超限必须二次拆分或拒绝
- [ ] 估算总成本 ≤ `max_cost_usd`，否则 `WAITING_APPROVAL`

**必须串行的固定约束**（路线图 §12.3）

设计先于实现；Schema 先于 API/前端；实现先于验证；Verification 失败后的 Repair；多 Agent 改同一文件。

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R4-1 | 含环的 DAG 被拒 | 抛 `InvalidPlan` |
| R4-2 | 孤立节点被拒 | 抛错 |
| R4-3 | 缺 acceptance_criteria 的节点被拒 | 抛错 |
| R4-4 | 写路径冲突的两节点不得同组 | 自动分到不同组或抛错 |
| R4-5 | 拓扑序输出稳定（同输入同序） | 通过 |
| R4-6 | 并行组划分正确（给定依赖图断言组内容） | 通过 |
| R4-7 | 子任务数超上限 | 抛错 |
| R4-8 | 估算成本超预算 → `WAITING_APPROVAL` | 通过 |
| R4-9 | LLM 规划失败 → 回退单节点计划，不崩 | 通过 |
| R4-10 | LLM 返回非法 JSON → 一次纠正重试后回退 | 通过 |
| R4-11 | 重复子任务（标题+写路径相同）被合并或拒 | 通过 |
| R4-12 | Specification 缺 acceptance_criteria → 生成草案 + `WAITING_APPROVAL`，**不得**假设完成标准 | 通过 |
| R4-13 | Planner 建议的 `write_paths` 超出后端允许集 → 被裁剪，不扩大 | 通过 |

**最小实现**

- [ ] `PlannerPort` Protocol，使 LLM 可 mock（测试必须离线）
- [ ] `TaskPlan` 聚合：`plan_id`/`task_id`/`version`/`subtasks`/`dependency_edges`/`parallel_groups`/`synthesis_strategy`/`risk_level`/`estimated_cost`/`approval_status`
- [ ] 拓扑排序 + 冲突检测为纯函数，无 IO

**验证**　四条命令；所有 P4 测试**必须离线可跑**（禁止真实 LLM 调用）。

**非目标**　不执行子任务；不编译 Prompt；不并行调度（P12）。

**DoD**

- [ ] 13 条 Red 全过且全离线
- [ ] 现有 `task_decomposer` 相关测试不回退
- [ ] `docs/pending/05-子任务并行执行.md` 更新为"计划层已完成，调度层待 P12"

---

### P5 · Phase 20 — 确定性 PromptPackage 编译器

**目标**　给定（Specification + Snapshot + Subtask + RouteDecision 预览 + 模板版本），确定性产出 JSON + Markdown 双表示与内容哈希。**这是整个系统的可审计性支点。**

**前置**　P3、P4 已 push。

**规格变更**　`specs/execution-closure/prompt-package.md` 定稿（P1 已建，此处补哈希算法与段落顺序）。

**边界**

- 允许写：`src/model_router/domain/prompt_package.py`、`src/model_router/ports/prompt_compiler_port.py`、`src/model_router/adapters/prompts/markdown_prompt_compiler.py`、`src/prompts/templates/**`、`tests/unit/test_prompt_package.py`、`tests/contract/test_prompt_compiler.py`
- 禁止写：`src/prompts/planner.txt` 的现有行为；任何 Executor

**24 个必需段落**（路线图 §11，顺序固定，缺一即编译失败）

1 Original Goal · 2 Current Subtask · 3 Why This Subtask Exists · 4 Dependency Inputs · 5 Project Context Summary · 6 Applicable AGENTS Instructions · 7 Relevant Specs and ADRs · 8 DDD Bounded Context · 9 Owned Invariants · 10 Explicit Non-goals · 11 Allowed Read Paths · 12 Allowed Write Paths · 13 Forbidden Paths · 14 Allowed Commands · 15 Forbidden Commands · 16 Execution Budget · 17 TDD Red/Green Workflow · 18 Acceptance Criteria · 19 Required Artifacts · 20 Verification Commands · 21 Return JSON Schema · 22 Human-readable Report Format · 23 Template Version · 24 Content Hash

**哈希算法（必须写进规格，避免将来不可复现）**

- [ ] 输入 = 规范化 JSON（键排序、缩进固定、`ensure_ascii=false`、行尾统一 `\n`）
- [ ] 排除字段：`content_hash` 自身、任何时间戳、任何随机 id
- [ ] 算法：SHA-256，十六进制小写，取全长
- [ ] Markdown 由 JSON 单向渲染，**不得**反向影响 hash

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R5-1 | 相同输入连跑 3 次 → 同一 `content_hash` | 通过 |
| R5-2 | 相同输入 → 逐字节相同 Markdown | 通过 |
| R5-3 | 任一输入字段变化 → hash 变化 | 参数化每字段 |
| R5-4 | 缺任一必需段落 → 编译失败 | 参数化 24 段 |
| R5-5 | 段落顺序固定 | 断言 Markdown 中标题序 |
| R5-6 | Planner 建议扩大 `allowed_write_paths` → 被忽略 | 断言输出等于后端值 |
| R5-7 | Planner 试图改 `acceptance_criteria` → 被忽略 | 通过 |
| R5-8 | Planner 试图改 `forbidden_paths` / `command_policy` / `budget` → 被忽略 | 通过 |
| R5-9 | Prompt 中不含 `sk-`、`Bearer `、`.env` 全文 | 正则断言 |
| R5-10 | 超上下文预算时保留规格/边界/签名/测试，裁掉大文件正文 | 断言保留项 |
| R5-11 | JSON 与 Markdown 语义一致（关键字段双向核对） | 通过 |
| R5-12 | 模板版本变化 → hash 变化且旧包仍可加载 | 通过 |
| R5-13 | `prompt.md` 以 UTF-8 编码写出且无 BOM | 通过 |
| R5-14 | 缺 `acceptance_criteria` 时编译草案并标 `requires_approval=true` | 通过 |
| R5-15 | 包可从 JSON 完整重建（round-trip） | 通过 |
| R5-16 | 编译器不发起任何网络/LLM 调用 | mock 断言 |

**最小实现**

- [ ] `PromptPackage` 聚合（字段按路线图 §10.2）
- [ ] `MarkdownPromptCompiler`：纯函数式，输入→输出，无 IO（写盘交给 P6 的 ArtifactStore）
- [ ] 模板放 `src/prompts/templates/execution-package-v1.md`，版本号进 `template_version`

**验证**　四条命令 + 手工产出一份 `prompt.md` 通读，确认人类可读且无敏感信息。

**非目标**　不落盘（P6）；不路由（P7）；不执行。

**DoD**

- [ ] 16 条 Red 全过
- [ ] R5-6..R5-8 三条**必须**存在，这是"Planner 不得越权"的唯一证据
- [ ] 编译器零 IO 零网络（测试证明）

---

### P6 · Phase 21 — Job 仓储与 ArtifactStore

**目标**　让 Job 与 Artifact 跨进程重启存活，且路径不可逃逸。

**前置**　P5 已 push。

**规格变更**　`specs/execution-closure/artifact-store.md` 定稿。

**边界**

- 允许写：`src/model_router/ports/execution_repository.py`、`src/model_router/ports/artifact_store.py`、`src/model_router/adapters/persistence/sqlite_execution_repository.py`、`src/model_router/adapters/persistence/filesystem_artifact_store.py`、`tests/integration/test_sqlite_execution_repository.py`、`tests/integration/test_artifact_store.py`、`.gitignore`
- 禁止写：`sqlite_task_repository.py` 的既有表结构（只能新增表，不得改 `execution_tasks`）

**存储约定**

| 项 | 值 |
|---|---|
| 数据库 | 复用 `.runtime/model-router.db`（同一文件，新增表） |
| 新增表 | `execution_jobs`、`job_attempts`、`job_artifacts`、`prompt_packages` |
| Artifact 根 | `artifacts/`（`.gitignore` 加 `artifacts/` + 保留 `artifacts/.gitkeep`） |
| Prompt 包 | `artifacts/execution-packages/<job_id>.{md,json}` |
| 执行结果 | `artifacts/execution-results/<job_id>/<attempt_n>/**` |
| 并发控制 | 乐观锁：`UPDATE ... WHERE job_id=? AND version=?`，`rowcount!=1` → `JobConflict` |

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R6-1 | Job 写入后新建 repository 实例可读回，字段全等 | 通过 |
| R6-2 | 状态机历史（attempts）顺序保留 | 通过 |
| R6-3 | 同 `IdempotencyKey` 二次创建返回既有 Job，不新建 | 通过 |
| R6-4 | 并发更新：旧 version 更新失败 | 抛 `JobConflict` |
| R6-5 | Artifact 路径含 `..` → 拒绝 | 抛错 |
| R6-6 | Artifact 绝对路径 → 拒绝 | 抛错 |
| R6-7 | Artifact 符号链接指向根外 → 拒绝 | 抛错 |
| R6-8 | 写入后可按 `artifact_id` 读回，字节相等 | 通过 |
| R6-9 | `prompt.md` 读回为 UTF-8 且 hash 与库中记录一致 | 通过 |
| R6-10 | 现有 `execution_tasks` 表与数据不受影响 | 回归通过 |
| R6-11 | 数据库文件被删后重建不崩（重新 `CREATE TABLE IF NOT EXISTS`） | 通过 |
| R6-12 | 列表查询支持按 state / task_id / 时间倒序 | 通过 |

**最小实现**　按 ADR-013：SQLite + Filesystem，Port 保留将来替换。

**验证**　四条命令 + 手工重启服务后 `GET` 已建 Job（P8 后再验；本阶段用集成测试代替）。

**非目标**　不做对象存储；不做保留期清理任务；不接 API。

**DoD**

- [ ] 12 条 Red 全过
- [ ] R6-5..R6-7 三条路径逃逸测试必须存在
- [ ] `.gitignore` 已含 `artifacts/`，且 `git status` 干净

---

### P7 · Phase 22 — RouteDecision 与 ModelBinding

**目标**　把当前返回松散 dict 的路由升级为强类型 `RouteDecision`，并引入可证明的绑定模式。**必须保持现有 29 条路由行为不变。**

**前置**　P1 已 push（ADR-011 已定）。

**规格变更**　`specs/routing/routing-policy.md` 增补评分函数与硬约束；`specs/execution-closure/model-binding.md` 定稿。

**边界**

- 允许写：`src/model_router/domain/route_decision.py`、`src/model_router/domain/model_binding.py`、`src/model_router/application/route_preview.py`、`tests/unit/test_route_decision.py`、`tests/unit/test_model_binding.py`、`tests/contract/test_route_preview.py`
- 允许**谨慎**写：`src/routing_table.py`（只允许新增能力元数据字段，**不得**改现有 29 条的 primary/fallback 取值）
- 禁止写：Provider 适配器内部选路逻辑

**路由输入扩展**（路线图 §13.1，共 13 项）

`required_capabilities` / `delivery_type` / `repository_access_required` / `context_window_required` / `tool_use_required` / `structured_output_required` / `quality_target` / `max_cost_usd` / `max_latency_ms` / `provider_availability` / `historical_success_rate` / `historical_verification_pass_rate` / `model_binding_requirement`

**两段式选择（顺序不可颠倒）**

1. **硬约束过滤**：能力下限、必需工具、上下文窗口、Provider 许可、绑定模式、预算、显式禁用列表。过滤后为空 → `NoEligibleModel` 错误，**不得**降级到不合格模型。
2. **评分排序**（仅在合法候选内）：
   `capability_fit·W1 + quality_fit·W2 + pass_rate·W3 + availability·W4 − cost·W5 − latency·W6 − binding_risk·W7`
   权重必须是**配置常量**且在规格中列出，不得散落在代码里。

**分层执行策略**（路线图 §13.3）

| 复杂度 | 策略 |
|---|---|
| T0/T1 | 优先 flash/economy；本地规则能解决时**不调用 LLM** |
| T2 | workhorse，必要时 1 个 Reviewer |
| T3 | brain 规划 + workhorse 实现 + 独立验证 |
| T4 | brain 主模型 + **不同 Provider** 的 Reviewer，受预算硬限 |

**三种 binding_mode 语义**

| 模式 | 含义 | 何时可用 |
|---|---|---|
| `ENFORCED` | 执行器必须用 `required_model`，且可从 argv/config/响应证明 | LiteLLM Provider 路径 |
| `VERIFIED_FALLBACK` | 只许白名单模型，必须返回 `fallback_reason` | Provider 降级路径 |
| `EXECUTOR_MANAGED` | 执行器自管模型，系统**不得**宣称强制 | Codex CLI 当前唯一可用模式 |

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R7-1 | 现有 29 条路由的 primary/fallback 取值逐条不变 | 快照对比测试 |
| R7-2 | 4 个预算区间行为不变（green/yellow/orange/red） | 通过 |
| R7-3 | 关键任务（architecture/system_design/deep_reasoning）不被降级 | 通过 |
| R7-4 | 硬约束过滤后为空 → `NoEligibleModel`，不返回不合格模型 | 通过 |
| R7-5 | 能力下限被违反的候选不出现在结果中 | 通过 |
| R7-6 | 评分排序稳定（同输入同序） | 通过 |
| R7-7 | `binding_mode=ENFORCED` 但执行器不支持 → 拒绝或改判 `EXECUTOR_MANAGED` | 通过 |
| R7-8 | 声明 `ENFORCED` 却只把模型名写进 Prompt → 测试失败 | 反例测试 |
| R7-9 | Route Preview **不**发起任何 Provider / Codex / Cursor 调用 | mock 断言全部未被调用 |
| R7-10 | `max_cost_usd` 过低时无候选 → 明确错误而非静默选最便宜 | 通过 |
| R7-11 | `RouteDecision` 为不可变值对象 | 通过 |
| R7-12 | T0/T1 且本地规则可解 → `executor=local`，不调 LLM | 通过 |

**验证**　四条命令 + `skills/router-reliability-audit/scripts/audit_reliability.py`。

**非目标**　不改 Provider 适配器；不执行；不做真实成本台账（P13）。

**DoD**

- [ ] 12 条 Red 全过，R7-1 快照证明零回归
- [ ] R7-9 是"预览不执行"的唯一证据，必须存在
- [ ] 权重常量在规格与代码中一致

---

### P8 · Phase 23 — Execution Job API（异步）

**目标**　对外暴露 Job 生命周期 API，`POST` 返 202，长任务不再堵在 HTTP 请求里。

**前置**　P6、P7 已 push。

**规格变更**　`specs/gateway/request-contract.md` 增补 Job API；`specs/gateway/authentication.md` 增补 approve/cancel 的权限要求。

**边界**

- 允许写：`src/model_router/adapters/http/execution_gateway.py`、`scripts/dashboard_server.py`（**仅**新增路由分发，不得含领域逻辑）、`src/model_router/application/analyze_task.py`、`tests/contract/test_execution_gateway.py`、`tests/integration/test_execution_job_http.py`
- 禁止写：现有 `/api/route`、`/v1/chat/completions` 的行为

**API 清单**（路线图 §16）

| 方法 | 路径 | 本阶段 | 说明 |
|---|---|---|---|
| POST | `/api/execution/jobs` | ✅ | 返 **202** + `job_id` / `state` / `trace_id` / `status_url` |
| GET | `/api/execution/jobs` | ✅ | 列表，支持 state/task_id 过滤 |
| GET | `/api/execution/jobs/<id>` | ✅ | 详情 |
| GET | `/api/execution/jobs/<id>/plan` | ✅ | TaskPlan + DAG |
| GET | `/api/execution/jobs/<id>/prompt.md` | ✅ | UTF-8 Markdown 下载 |
| GET | `/api/execution/jobs/<id>/artifacts` | ✅ | 列表 |
| GET | `/api/execution/jobs/<id>/events` | ✅ | 事件流（本阶段可轮询版） |
| POST | `/api/execution/jobs/<id>/approve` | ✅ | `WAITING_APPROVAL → READY` |
| POST | `/api/execution/jobs/<id>/cancel` | ✅ | 任意非终态 → `CANCELLED` |
| POST | `/api/route/preview` | ✅ | 纯预览，不执行 |
| POST | `/api/execution/jobs/<id>/retry` | P9 | 需要 Executor |
| POST | `/api/execution/jobs/<id>/repair` | P11 | 需要 Verification |
| GET | `/api/costs/summary` | P13 | 需要 CostLedger |
| GET | `/api/providers/health` | P13 | 需要主动探测 |

**创建请求最小字段**（改正清单 §8）

`goal` / `task_id`(可选) / `workdir` / `delivery_type` / `allowed_write_paths` / `acceptance_criteria` / `approval_mode` / `max_steps` / `max_cost_usd` / `timeout_seconds` / `idempotency_key`

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R8-1 | `POST` 返 **202** 且含 `job_id`/`state`/`trace_id`/`status_url` | 通过 |
| R8-2 | 相同 `idempotency_key` 二次 `POST` → 同一 `job_id`，不新建 | 通过 |
| R8-3 | `workdir` 越界 → **403** `workdir_forbidden` | 通过 |
| R8-4 | 非法 `allowed_write_paths`（含 `..`/绝对路径）→ **400** | 通过 |
| R8-5 | 缺 `goal` → 400 | 通过 |
| R8-6 | 未授权 `approve`/`cancel` → 401/403 | 通过 |
| R8-7 | `GET` 详情**不回显**完整敏感 Prompt（只给摘要 + 下载链接） | 通过 |
| R8-8 | `prompt.md` 返回 `Content-Type: text/markdown; charset=utf-8` | 通过 |
| R8-9 | 服务重启后 `GET` 已建 Job 仍成功 | 真实重启集成测试 |
| R8-10 | `cancel` 后再 `approve` → 409 | 通过 |
| R8-11 | 不存在的 `job_id` → 404 | 通过 |
| R8-12 | `POST /api/route/preview` 不执行任何 Executor | mock 断言 |
| R8-13 | 现有 `/api/route`、`/v1/chat/completions`、`/api/tasks` 行为不变 | 回归 |
| R8-14 | 超频 → 429（沿用现有限流） | 通过 |
| R8-15 | Job 状态**从不**在预览阶段显示为 `RUNNING`/`SUCCEEDED` | 通过 |

**最小实现**

- [ ] `AnalyzeTask` 用例：创建 Job → 建 Snapshot(P3) → 建 Plan(P4) → 编译 Prompt(P5) → 存 Artifact(P6) → 生成 Route Preview(P7) → 状态落 `WAITING_APPROVAL` 或 `READY`
- [ ] `dashboard_server.py` 只做路径匹配与委派

**验证**　四条命令 + 手工 `curl` 全部 10 个已启用端点 + **真实重启验证**。

**非目标**　不执行 Job（P9）；不验证（P10）；不修复（P11）。

**DoD**

- [ ] 15 条 Red 全过
- [ ] R8-9 真实重启测试存在
- [ ] `dashboard_server.py` 新增行数中**零**领域逻辑（人工 review 记录进 assessment）
- [ ] **M1 里程碑达成**：可对外说"可审计的分析预览"，仍**不得**说"已执行"

---

### P9 · Phase 24 — Executor 契约与四类 Executor

**目标**　统一 `TaskExecutor` Port，四类执行器都返回标准 `ExecutionReceipt`。本阶段建议拆 **4 个 commit**（Port+Provider / Codex / Cursor / Document）。

**前置**　P8 已 push。

**规格变更**　`specs/agent/agent-contract.md` 增补 Executor 契约；`specs/provider/provider-contract.md` 增补 receipt 字段。

**边界**

- 允许写：`src/model_router/ports/task_executor_port.py`、`src/model_router/adapters/executors/**`、`src/model_router/application/execute_routed_job.py`、`tests/contract/test_task_executor_*.py`、`tests/integration/test_executor_*.py`
- 允许**迁移**：`src/codex_executor.py`、`src/cursor_queue.py` 移入 Adapter 边界（保留原模块为薄壳以兼容 `orchestrator.py`）
- 禁止写：`execution_service.py` 的既有 Retry/Fallback 语义

**ExecutionReceipt 必需 11 字段**（路线图 §14）

`requested_model` / `actual_model` / `binding_mode` / `binding_status` / `executor_id` / `executor_version` / `fallback_reason` / `input_tokens` / `output_tokens` / `actual_cost_usd` / `started_at`+`completed_at`

追加（仓库类执行必需）：`changed_files` / `exit_codes` / `commands_run` / `final_message` / `artifact_ids`

**四类 Executor 能力矩阵**

| Executor | delivery_type | 可改仓库 | 可跑命令 | binding | 成功语义 |
|---|---|---|---|---|---|
| `ProviderAnswerExecutor` | ANSWER / DOCUMENT | ✗ | ✗ | ENFORCED / VERIFIED_FALLBACK | 返回文本且 Schema 合规 |
| `CodexRepositoryExecutor` | PATCH / REPOSITORY_CHANGE | ✓ | ✓（白名单） | EXECUTOR_MANAGED（除非证明可传模型） | 退出码 0 + changed_files 在范围内 |
| `CursorWorkerExecutor` | PATCH / FILE_EDIT | ✓（经 Worker） | 由 Worker 决定 | EXECUTOR_MANAGED | **结果回写后**才算，queued 不算 |
| `DocumentExecutor` | DOCUMENT | 只写 artifacts | ✗ | 本地代码 | 文件存在 + 结构合规 |

**Red 清单 · 通用契约**

| # | 测试 | 期望 |
|---|---|---|
| R9-1 | `WorkOrder` 缺 `required_model` 或 `binding_mode` → 拒绝 | 通过 |
| R9-2 | Receipt 缺任一必需字段 → 拒绝 | 参数化 11 字段 |
| R9-3 | `EXECUTOR_MANAGED` 的 receipt 中 `binding_status` **不得**为 `enforced` | 通过 |
| R9-4 | Fallback 发生时 `fallback_reason` 非空 | 通过 |

**Red 清单 · ProviderAnswerExecutor**

| # | 测试 | 期望 |
|---|---|---|
| R9-5 | `actual_model` 不在允许列表 → `ModelBindingViolation`，**不得**静默成功 | 通过 |
| R9-6 | 返回文本时 `changed_files` 必须为空 | 通过 |
| R9-7 | 不得声明"已运行测试" | Schema 层禁止该字段为真 |
| R9-8 | 现有 Retry/Fallback/Trace 行为不回退 | 回归 |

**Red 清单 · CodexRepositoryExecutor**

| # | 测试 | 期望 |
|---|---|---|
| R9-9 | 完整 PromptPackage 被传入（不是截断摘要） | 通过 |
| R9-10 | `workdir` / `timeout` 正确设置 | 通过 |
| R9-11 | 捕获 `exit_code` / stdout 摘要 / `final_message` / `changed_files` | 通过 |
| R9-12 | 超时 → 终止进程并返回标准错误，不挂起 | 通过 |
| R9-13 | 写出 `allowed_write_paths` 之外 → 失败并标记 `forbidden_path_hits` | 通过 |
| R9-14 | CLI 不存在 → 任务 **FAILED**，不得伪成功 | 通过 |
| R9-15 | 若 CLI 支持模型参数 → argv **实际包含**路由模型；若不支持 → 明确返回 `EXECUTOR_MANAGED` | 二选一，必须有一个通过 |
| R9-16 | subprocess 细节不泄漏到 application 层 | 边界断言 |

**Red 清单 · CursorWorkerExecutor**

| # | 测试 | 期望 |
|---|---|---|
| R9-17 | `claim` 产生租约（`lease_until`） | 通过 |
| R9-18 | 同一任务不能被两个 Worker 同时 claim | 通过 |
| R9-19 | `heartbeat` 延长租约 | 通过 |
| R9-20 | 租约超时后任务可被重新 claim（崩溃恢复） | 通过 |
| R9-21 | 结果回写后 Job 进入 `VERIFYING`，**不是** `SUCCEEDED` | 通过 |
| R9-22 | 仅 `queued` 时 `job_success == false`（`dispatch_success` 与 `job_success` 分离） | 通过 |
| R9-23 | 同一 `idempotency_key` 重复回写只生效一次 | 通过 |
| R9-24 | 保留人工模式，但人工模式下状态仍不是 `SUCCEEDED` | 通过 |

**Red 清单 · DocumentExecutor**

| # | 测试 | 期望 |
|---|---|---|
| R9-25 | 产出文件存在、UTF-8、含必需章节 | 通过 |
| R9-26 | 只写 artifacts 根内 | 通过 |
| R9-27 | 敏感信息扫描通过后才算成功 | 通过 |

**验证**　四条命令 + `validate_adapter_boundary.py` + 一次**真实 Codex 受限任务**（改单文件、跑单测试）。

**非目标**　不做自动验证（P10）；不做修复（P11）；不并行（P12）。

**DoD**

- [ ] 27 条 Red 全过
- [ ] R9-15 明确落地为其中一种，并在 `specs` 与 UI 文案中一致
- [ ] R9-22 是"queued ≠ success"的唯一证据
- [ ] 真实 Codex 任务的 receipt 存档于 `docs/assessment/`

---

### P10 · Phase 25 — Verification Service

**目标**　成功状态由验证证据决定，不再由模型自述或退出码单独决定。

**前置**　P9 已 push。

**规格变更**　`specs/execution-closure/verification.md` 定稿；`specs/acceptance-criteria.md` 增补验证矩阵。

**边界**

- 允许写：`src/model_router/domain/verification.py`、`src/model_router/ports/verification_port.py`、`src/model_router/adapters/verification/command_verifier.py`、`src/model_router/adapters/verification/secret_scanner.py`、`src/model_router/application/verify_execution.py`、`tests/**` 对应
- 禁止写：Executor 内部；`response_validator.py` 的既有行为（可复用，不可破坏）

**验证策略矩阵**（路线图 §15 + 改正清单 §7.1）

| delivery_type | 必需验证项 |
|---|---|
| ANSWER | 非空、Return Schema 合规、禁止虚假执行声明、敏感信息扫描 |
| PLAN | 必需章节齐全、边界存在、Acceptance Criteria 可执行性、无空承诺 |
| PATCH | patch 可 apply、目标文件在 FileScope 内、`git diff --check` |
| REPOSITORY_CHANGE | Red/Green 证据、完整离线回归、lint/build、changed_files 在范围、forbidden 未命中 |
| DOCUMENT | 文件存在、UTF-8、结构章节、敏感信息、可读性 |
| RELEASE | 以上全部 + 版本与状态文档一致 + Commit/Push 权限确认 |

**VerificationReport 必需 10 字段**

`status`(PASS / REPAIRABLE_FAILURE / FINAL_FAILURE) / `criterion_results` / `commands` / `exit_codes` / `changed_files` / `forbidden_path_hits` / `secret_scan` / `artifacts` / `repairable` / `evidence_summary`

**成功的 7 个必要条件（全部满足才可 PASS，改正清单 §7.3）**

1. Executor 返回成功
2. `actual_model` 与绑定契约一致
3. 所有必需 Artifact 存在
4. Acceptance Criteria 全部通过
5. 必需验证命令退出码为 0
6. `forbidden_paths` 未被修改
7. 敏感信息扫描通过

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R10-1 | 无任何测试证据的仓库变更 → 不得 PASS | 通过 |
| R10-2 | 修改 `forbidden_paths` → FINAL_FAILURE | 通过 |
| R10-3 | `git diff --check` 失败 → 失败 | 通过 |
| R10-4 | 密钥命中 → FINAL_FAILURE（不可修复） | 通过 |
| R10-5 | 测试失败 → REPAIRABLE_FAILURE | 通过 |
| R10-6 | 模型自称"已通过测试"但无命令记录 → 不得 PASS | 通过 |
| R10-7 | `changed_files` 超出 FileScope → 失败 | 通过 |
| R10-8 | 验证命令必须来自白名单，任意命令注入被拒 | 通过 |
| R10-9 | 命令超时 → 记录并判失败，不挂起 | 通过 |
| R10-10 | 7 个必要条件逐条缺失时均不得 PASS | 参数化 7 条 |
| R10-11 | 5 类 delivery_type 各自策略被正确选中 | 参数化 |
| R10-12 | Verification **不得**修改 Acceptance Criteria | 通过 |
| R10-13 | 报告可持久化并可从 API 读回 | 通过 |

**验证**　四条命令 + 手工构造一次真失败（改坏一个测试）确认判为 REPAIRABLE_FAILURE。

**非目标**　不做修复（P11）；不改验收标准；不评价代码风格。

**DoD**

- [ ] 13 条 Red 全过
- [ ] R10-6 是"不信模型自述"的唯一证据
- [ ] 命令白名单在规格中列明，代码与规格一致

---

### P11 · Phase 26 — Bounded Repair 循环

**目标**　验证失败后自动修复，但**上限硬编码**，绝不无限循环、绝不扩权。

**前置**　P10 已 push。

**规格变更**　`specs/execution-closure/repair.md`：上限、Prompt 最小化规则、不可修复分类。

**边界**

- 允许写：`src/model_router/domain/repair_work_order.py`、`src/model_router/application/repair_execution.py`、`src/model_router/application/finalize_delivery.py`、`tests/**`
- 禁止写：Verification 的判定逻辑；FileScope 的构造逻辑

**Repair 六条硬规则**

1. 只发送**失败证据 + 原 PromptPackage 引用**，不重发全部上下文
2. **不得**扩大 `FileScope`
3. **不得**改 `Acceptance Criteria`
4. **不得**换用未授权模型
5. 同时受 `max_repair_attempts`（建议 2）、`max_cost_usd`、`max_steps`、`timeout` 四个上限约束，任一触顶即停
6. 达到上限 → `FAILED_WITH_EVIDENCE`，报告必须含全部尝试的证据链

**不可修复（直接 FINAL_FAILURE，不进 Repair）**

- 密钥泄漏命中
- 写入 `forbidden_paths`
- `ModelBindingViolation`
- 预算已耗尽
- 非确定性在线故障连续 N 次（避免烧钱）

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R11-1 | 首次 REPAIRABLE_FAILURE → 创建 1 个 Repair WorkOrder | 通过 |
| R11-2 | Repair Prompt 只含失败证据 + 原包引用（断言不含无关上下文） | 通过 |
| R11-3 | Repair 试图扩大 FileScope → 被拒 | 通过 |
| R11-4 | Repair 试图改 Acceptance Criteria → 被拒 | 通过 |
| R11-5 | Repair 换到未授权模型 → 被拒 | 通过 |
| R11-6 | `max_repair_attempts=2` 时第 3 次不发生 | 通过 |
| R11-7 | 成本触顶时立即停止，即使次数未满 | 通过 |
| R11-8 | 步数触顶时停止 | 通过 |
| R11-9 | 超时触顶时停止 | 通过 |
| R11-10 | 修复成功 → 生成最终报告且状态 `SUCCEEDED` | 通过 |
| R11-11 | 上限耗尽 → `FAILED_WITH_EVIDENCE`，含全部 attempt 证据 | 通过 |
| R11-12 | 密钥泄漏类失败**不进入** Repair | 通过 |
| R11-13 | 循环不可能无限：构造持续失败场景，断言必然终止 | 通过 |

**验证**　四条命令 + 手工场景 C（首次故意失败 → 修复 → 上限停止）。

**非目标**　不并行修复；不自动 push 生产代码；不放宽验证。

**DoD**

- [ ] 13 条 Red 全过
- [ ] R11-13 必须存在（终止性证明）
- [ ] **M2 里程碑达成**：可说"单任务可完成并可验证"

---

### P12 · Phase 27 — 多 Agent DAG 调度与 Synthesis

**目标**　把 P4 的计划真正并行跑起来，并用基于 Artifact 的综合替代字符串拼接。建议拆 **3 个 commit**（调度器 / Reviewer / Synthesis）。

**前置**　P11 已 push。

**规格变更**　`specs/execution-closure/orchestration.md`：并行准入、预算预留、冲突处理、综合算法。

**边界**

- 允许写：`src/model_router/application/orchestrate_plan.py`、`src/model_router/domain/synthesis.py`、`src/model_router/application/synthesize_results.py`、`tests/**`
- 禁止写：`src/dispatcher.py` 的既有串行路径（保留兼容）；Verification 判定

**并行准入五条（全满足才并行，路线图 §12.3）**

1. 子任务写路径两两不相交
2. 不依赖未完成的 Artifact
3. 总预算允许（须先做 **budget reservation**，不能乐观超发）
4. 并发 Provider 配额允许
5. 每子任务有独立幂等键

**Agent 角色表**（路线图 §12.2，10 角色）

Intent Analyst / Architect / Planner / Prompt Compiler(本地代码) / Repository Implementer / Content-Data Worker / Reviewer / Verifier(本地代码) / Synthesis Agent / Release Auditor

**Synthesis 六步（禁止字符串拼接）**

1. 按 Artifact 类型读取结果
2. 检查冲突、缺失、重复
3. 优先采用**通过验证**的输出
4. 冲突 → 触发 Reviewer 或重新规划，不自行裁决
5. 保留每段结论的来源 Agent / 模型 / Attempt / 成本
6. 生成统一 `DeliveryReport`

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R12-1 | 无冲突子任务真并行（断言并发度 > 1） | 通过 |
| R12-2 | 写路径冲突的子任务被强制串行 | 通过 |
| R12-3 | 依赖未满足的子任务不启动 | 通过 |
| R12-4 | 预算不足时不启动新子任务（预留生效） | 通过 |
| R12-5 | Provider 配额超限时排队而非失败 | 通过 |
| R12-6 | 一个子任务失败不导致整图崩溃，其余按依赖继续或正确阻塞 | 通过 |
| R12-7 | 全部子任务完成后才进入 Synthesis | 通过 |
| R12-8 | Synthesis 不是字符串拼接（断言存在冲突检测调用） | 通过 |
| R12-9 | 两个子任务输出冲突 → 触发 Reviewer，不静默取其一 | 通过 |
| R12-10 | 未通过验证的输出不得被采用 | 通过 |
| R12-11 | `DeliveryReport` 中每段有来源 Agent/模型/Attempt/成本 | 通过 |
| R12-12 | 取消 Job → 全部在跑子任务被终止 | 通过 |
| R12-13 | 并行执行结果确定性可复现（给定 mock，输出稳定） | 通过 |
| R12-14 | 现有串行 Dispatcher 路径不回退 | 回归 |

**验证**　四条命令 + 一次 3 节点 DAG 的 mock 端到端。

**非目标**　不做分布式调度；不做跨机 Worker；不引入消息队列。

**DoD**

- [ ] 14 条 Red 全过
- [ ] R12-8/R12-9 是"综合非拼接"的证据
- [ ] 并行度在 assessment 中有实测记录

---

### P13 · Phase 28 — CostLedger 与可观测性持久化

**目标**　成本从"静态价格表 + 外部 pressure 值"升级为可审计台账；指标不再重启丢失。

**前置**　P9 已 push（有 receipt 才有成本源）。

**规格变更**　`specs/execution-closure/cost-ledger.md` 定稿；`specs/execution/reliability.md` 增补主动 health 探测。

**边界**

- 允许写：`src/model_router/domain/cost_ledger.py`、`src/model_router/adapters/persistence/sqlite_cost_ledger.py`、`src/model_router/adapters/observability/sqlite_observer.py`、`src/budget_adapter.py`、`tests/**`
- 禁止写：路由决策逻辑（成本只作为路由输入，不在此阶段改选路）

**必须新增的 8 项**（路线图 §13.4）

`CostLedger` / per-job `max_cost` / per-subtask estimate+actual / token usage persistence / provider quota snapshot / budget reservation / cancellation on budget breach / cost-aware repair limit

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R13-1 | 每次 attempt 的 token 与成本写入台账 | 通过 |
| R13-2 | Job 总成本 = 各 attempt 之和 | 通过 |
| R13-3 | 预留后可用预算立即下降（不等实际扣费） | 通过 |
| R13-4 | 超 `max_cost_usd` → Job 被取消并记录原因 | 通过 |
| R13-5 | Repair 受成本上限约束（与 R11-7 一致） | 通过 |
| R13-6 | `budget_ratio` 不可用时**明确标记 unknown**，不静默返回 0.0 | 通过（当前是静默 0.0，属缺陷） |
| R13-7 | 指标重启后仍可读（持久化 Observer） | 通过 |
| R13-8 | Provider 主动 health 探测有超时与缓存，失败不阻塞主路径 | 通过 |
| R13-9 | LiteLLM 远程价格表拉取失败 → 用本地缓存副本且记警告 | 通过 |
| R13-10 | 本地价格缓存文件纳入版本控制且有版本号 | 通过 |
| R13-11 | `GET /api/costs/summary` 返回 job/subtask/model 三级汇总 | 通过 |
| R13-12 | 现有 `/api/metrics` 契约不破坏 | 回归 |

**验证**　四条命令 + 重启后 `GET /api/metrics` 与 `/api/costs/summary` 数据仍在。

**非目标**　不接 Prometheus/OTel（可留 Port）；不做计费出账；不改路由权重。

**DoD**

- [ ] 12 条 Red 全过
- [ ] R13-6 修掉"静默 0.0"这个隐蔽风险
- [ ] `docs/pending/04-预算精确计量.md`、`06-成本追踪持久化.md`、`02-看板服务稳定性.md` 更新状态

---

### P14 · Phase 29 — 一体化 UI（9 页体系）

**目标**　把 6 页扩到 9 页统一工作台，让每个结论都能点进去看到证据。建议**每页 1 个 commit**。

**前置**　P12 已 push（UI 要显示的东西必须先真实存在）。

**规格变更**　`specs/ui/information-architecture.md`：全局框架、9 页职责、状态色彩语义、响应式断点。

**边界**

- 允许写：`dashboard/**`、`scripts/test_dashboard_demo.py`
- 禁止写：任何 `src/**` 领域逻辑（UI 只消费 API）

**视觉与合规原则**

- [ ] 采用类淘宝的**密集嵌套信息架构 + 橙色行动强调 + 多层导航**
- [ ] **不复制**淘宝 Logo、图片、商标、文案或精确 trade dress
- [ ] 定位是工作台，不是营销页
- [ ] 桌面高密度 / 平板两栏 / 移动单栏，**无横向溢出、无控件重叠**
- [ ] 全站 UTF-8，无乱码

**9 页职责**

| # | 页面 | 核心内容 | 依赖阶段 |
|---|---|---|---|
| 1 | 任务工作台 | Task CRUD、批量、状态分类、**创建 Job 按钮** | P0, P8 |
| 2 | 任务分析页 | Goal、Specification、歧义清单、Acceptance Criteria、审批 | P4, P8 |
| 3 | 拆分与规划页 | DAG 图、子任务、依赖、并行组、PromptPackage 预览 | P4, P5 |
| 4 | 路由分析页 | 候选模型对比、能力/成本/质量、fallback 链、binding 状态 | P7 |
| 5 | 执行中心 | Job 状态机、Worker、Attempt、lease、实时事件 | P8, P9 |
| 6 | 验证与修复页 | 测试证据、失败原因、Repair 时间线、最终判定 | P10, P11 |
| 7 | Provider/成本中心 | health、quota、token、cost、成功率、P95 | P13 |
| 8 | Artifact/报告页 | Prompt Markdown、Patch、文件、结果、最终报告下载 | P6 |
| 9 | 架构与策略页 | DDD、ADR、路由规则、权限、模型目录 | 现有 |

**全局框架**

- 顶部：项目切换、全局 Task/Job 搜索、预算指示、Provider 状态、用户入口
- 左侧：Task / Planning / Routing / Execution / Verification / Artifacts / Settings
- 主区：当前页
- 右侧：选中对象详情、风险、成本、快捷操作

**状态显示铁律（违反即阶段失败）**

| 后端状态 | UI 必须显示 | UI 禁止显示 |
|---|---|---|
| `WAITING_APPROVAL` | 待审批（预览） | 运行中 / 已完成 |
| Cursor `queued` | 已入队，待处理 | 已完成 / 成功 |
| `RUNNING` | 运行中 | 已完成 |
| `VERIFYING` | 验证中 | 已完成 |
| `REPAIRING` | 修复中（第 N/上限 次） | 运行中 |
| `FAILED_WITH_EVIDENCE` | 失败（附证据链接） | 部分成功 |

**Red 清单**

| # | 测试 | 期望 |
|---|---|---|
| R14-1 | 9 页文件存在且非空、UTF-8 | 通过 |
| R14-2 | 每页含 live-data marker（不是硬编码假数据） | 通过 |
| R14-3 | 任务页有"分析并执行"入口且调 `/api/execution/jobs` | 通过 |
| R14-4 | 路由页明确区分 Route Preview 与 Execute Job | 通过 |
| R14-5 | 显示 `requested_model` / `actual_model` / `binding_status` 三者 | 通过 |
| R14-6 | `prompt.md` 有预览与下载入口 | 通过 |
| R14-7 | `queued` 不显示为 completed | 断言文案映射 |
| R14-8 | 显示 changed_files 与 Verification Evidence | 通过 |
| R14-9 | 区分 Retry / Fallback / Repair 三种概念 | 通过 |
| R14-10 | 所有异步操作（刷新/筛选/删除/审批）有统一错误处理与可见错误提示 | 通过 |
| R14-11 | `node --check dashboard/assets/app.js` 通过 | 通过 |
| R14-12 | 三档断点无横向溢出（E2E 或 DOM 尺寸断言） | 通过 |
| R14-13 | 导航在 9 页间一致且当前项高亮 | 通过 |
| R14-14 | 成本页显示 token 与 cost 真实值（非占位 0） | 通过 |

**建议引入的 E2E**（当前只有 DOM marker 检查，属已知缺口）

- [ ] 选一个轻量方案（Playwright 或 Puppeteer），只跑关键路径：创建任务 → 分析 → 看 Prompt → 审批 → 看 Job 状态
- [ ] 桌面 + 移动两个视口
- [ ] 断言控制台无 error
- [ ] 若因环境无法安装浏览器 → 在 assessment 中**明确写"未做浏览器 E2E"**，不得含糊

**验证**　四条命令 + 人工 9 页浏览器走查（记录截图或检查项清单）。

**非目标**　不改后端契约；不引入前端框架重写（保持原生 JS）；不做国际化。

**DoD**

- [ ] 14 条 Red 全过
- [ ] R14-7 是"UI 不虚报"的证据
- [ ] E2E 要么跑通，要么明确声明未做

---

### P15 · Phase 30 — 最终验收与发布

**目标**　用可复跑的证据证明整条闭环成立，并让全部文档与事实一致。

**前置**　P0-P14 全部已 push。

**边界**　允许写全仓库文档 + 验收脚本；**禁止**在本阶段新增功能。

**验收矩阵**（每行都要有可复跑命令与结果记录）

| # | 验收项 | 证据形式 |
|---|---|---|
| A-1 | 全部离线测试通过且总数 ≥ 基线 | `unittest discover` 输出 |
| A-2 | Dashboard 检查全过 | 脚本输出 |
| A-3 | 三个 Skill 脚本全过 | 脚本输出 |
| A-4 | `git diff --check` 干净 | 命令输出 |
| A-5 | Mock Executor 端到端 REPOSITORY_CHANGE | 集成测试 |
| A-6 | 真实 Provider 文本任务（ANSWER） | receipt 存档 |
| A-7 | 真实 Codex 受限仓库任务 | receipt + changed_files + 测试证据 |
| A-8 | Cursor Worker 演示（claim → heartbeat → 回写 → VERIFYING → PASS） | 事件时间线存档 |
| A-9 | 场景 C：首次失败 → 修复 → 上限停止 | 报告存档 |
| A-10 | Docker 镜像构建成功 | 构建日志 |
| A-11 | 容器重启后 Job 可恢复 | 重启前后 `GET` 对比 |
| A-12 | 9 页浏览器验收 | 走查清单 |
| A-13 | 最终 Markdown DeliveryReport 可下载且内容完整 | 文件存档 |
| A-14 | README / STATUS / checklist-matrix / UI 文案与事实一致 | 人工核对表 |
| A-15 | 在线评估与确定性测试**分开报告** | 两份独立记录 |
| A-16 | 术语表 6 状态在代码/API/UI 三处口径一致 | 核对表 |

**Docker 说明**（当前主机无 Docker Engine，属已知阻塞）

- [ ] 若本机仍无 Docker → 在 GitHub Actions 加 workflow 做 build + `/health` + `/v1/chat/completions` 契约测试
- [ ] 若 CI 也做不了 → assessment 中写明"Docker 未实跑"，**不得**在 README 声明容器化已验证

**非目标**　不新增功能；不改路由数据；不放宽任何验收判据。

**DoD**

- [ ] 16 行验收矩阵全部有证据或有明确的"未做+原因"
- [ ] `docs/checklist-matrix.md` 的 Partial 项逐条给出当前真实状态
- [ ] 最终 assessment `docs/assessment/2026-MM-DD-phase-30-final-acceptance.md`
- [ ] **M4 里程碑达成**，方可对外称"路由/任务完成系统完成"

---

## 6. 审计清单（每阶段收尾必跑，逐条打勾）

审计与实现应由**不同视角**执行（改正清单 §skills 已提供 `release-audit-agent`）。审计只看证据，不看意图。任何一条打 ✗ → 该阶段不得 commit。

### 6.A 边界审计（DDD）

| # | 检查项 | ✓/✗ |
|---|---|---|
| A1 | 本阶段改动**只落在**声明的 `allowed_write_paths` 内 | |
| A2 | `domain/**` 未 import `sqlite3`、`http`、`subprocess`、`litellm`、`requests` | |
| A3 | 依赖方向为 adapters → application → domain，无反向 | |
| A4 | 新领域逻辑**不在** `scripts/dashboard_server.py` | |
| A5 | Provider / Executor 适配器**未**做路由决策 | |
| A6 | Planner / LLM 输出**未**覆盖 FileScope、CommandPolicy、Budget、Acceptance Criteria | |
| A7 | 每个新 Port 有 Protocol 定义且至少一个可替换实现或 fake | |
| A8 | 未在两处重复定义同一值对象（复用 `TraceId`、`ModelId`、`TaskRepository`） | |
| A9 | 未重写已通过测试的 Routing / ExecutionService / Provider 边界 | |

### 6.B 契约审计

| # | 检查项 | ✓/✗ |
|---|---|---|
| B1 | 现有 `/v1/chat/completions` 请求与响应字段未变 | |
| B2 | 现有 `/api/route`、`/api/tasks`、`/api/metrics`、`/api/catalog`、`/api/specs`、`/api/cursor/queue`、`/api/reliability/simulate` 行为未变 | |
| B3 | 新 API 的错误码走统一 `safe_error_payload`（400/401/403/404/409/429/500 语义一致） | |
| B4 | 破坏性变更有 ADR 记录与迁移/回滚方案 | |
| B5 | 规格文件与实现一致（枚举值、字段名、必填性逐条核对） | |
| B6 | `proto/model_router.proto` 若未实现，仍明确标注为未来边界 | |

### 6.C 安全审计

| # | 检查项 | ✓/✗ |
|---|---|---|
| C1 | 无任何密钥/Token/`.env` 内容进入代码、测试、Prompt、Artifact、日志、assessment | |
| C2 | 路径参数经过归一化，`..`、绝对路径、符号链接逃逸均被拒 | |
| C3 | 所有外部命令走白名单，参数不做字符串拼接注入 | |
| C4 | 工作目录仍受 `MODEL_ROUTER_ALLOWED_WORKDIRS` 约束 | |
| C5 | 新增写操作端点受 Bearer 鉴权保护（`approve`/`cancel`/`retry`/`repair` 必须） | |
| C6 | CORS allowlist 未被放宽为 `*` | |
| C7 | 限流覆盖新增端点 | |
| C8 | 错误响应不泄漏栈、绝对路径、内部模型名之外的敏感细节 | |
| C9 | 新依赖（若有）为固定版本、来源可信、非疑似仿冒包 | |
| C10 | Artifact 目录不进 Git（除 `.gitkeep`） | |

### 6.D TDD 真实性审计（本文强化项）

| # | 检查项 | ✓/✗ |
|---|---|---|
| D1 | Red 测试与实现是**两个独立 commit**，且 Red 在前 | |
| D2 | Red commit 中**不含**生产代码改动（`git show --stat` 可证） | |
| D3 | assessment 中粘有 Red 的**真实失败输出摘要**，不是"应当失败"的描述 | |
| D4 | 无 `skipTest`、无注释掉的断言、无 `assertTrue(True)` 之类空断言 | |
| D5 | 无为过测试而放宽的枚举、阈值或 try/except 吞异常 | |
| D6 | 新增测试数 ≥ 该阶段 Red 清单条数 | |
| D7 | 需要外部 LLM/网络的逻辑有 mock 版本，离线套件可独跑 | |
| D8 | 参数化测试确实覆盖全组合（状态机类必须 `n×n`，不许抽样） | |

> D1/D2 是本文相对改正清单**新增的硬约束**。理由：P14 评估已确认"Red 测试和实现经常位于同一个 Git 提交，历史无法严格证明先 Red 后 Green"。不修这一点，整套 TDD 声明不可审计。

### 6.E 真实性审计（防越界声明）

| # | 检查项 | ✓/✗ |
|---|---|---|
| E1 | 未把 `queued` 写成 `completed` / `success`（代码、API、UI、文档四处） | |
| E2 | 未把 `route` 写成 `executed` | |
| E3 | 未把 `recommended model` 写成 `enforced binding` | |
| E4 | 未在无 VerificationReport 时返回 `SUCCEEDED` | |
| E5 | 未在未跑命令时返回 `verified=true` | |
| E6 | 未在未改仓库时声明 `repository_completed` / `changed_files` 非空 | |
| E7 | 未把在线评估结果当作确定性发布门禁 | |
| E8 | assessment 的 Checklist status 中 Partial 未被写成 Completed | |
| E9 | README / STATUS / UI 无超前完成声明 | |
| E10 | 阶段"未做的事"在 assessment 的非目标中显式列出 | |

### 6.F 可观测性审计

| # | 检查项 | ✓/✗ |
|---|---|---|
| F1 | 新路径贯穿同一 `TraceId` | |
| F2 | 每次 attempt 产生结构化事件（含 job_id / subtask_id / model / 耗时 / 结果） | |
| F3 | 失败事件含可定位原因（错误类型 + 证据引用），不是 "unknown error" | |
| F4 | 指标新增项在 `/api/metrics` 可见 | |
| F5 | 长任务有进度可查（events 端点或状态字段） | |

### 6.G 文档与发布审计

| # | 检查项 | ✓/✗ |
|---|---|---|
| G1 | `docs/assessment/` 新增本阶段文件，含模板 6 节 | |
| G2 | `docs/checklist-matrix.md` 对应行已更新 | |
| G3 | `STATUS.md` 的日期与结论已更新 | |
| G4 | `README.md` 的 API 列表、页数、测试数与实际一致 | |
| G5 | `docs/pending/**` 中被本阶段解决的条目已迁移或标注 | |
| G6 | 新增/修改的规格与 ADR 已在 `/api/specs` 可见 | |
| G7 | commit message 说明阶段编号与唯一问题 | |
| G8 | 已 `git push origin main`，且 `git status -sb` 显示无 ahead | |

### 6.H 回归审计（数值门禁）

| # | 检查项 | 门槛 | ✓/✗ |
|---|---|---|---|
| H1 | 离线测试通过数 | ≥ 40 且 ≥ 上一阶段数 | |
| H2 | 离线测试失败数 | = 0 | |
| H3 | Dashboard 检查 | ≥ 8 且 = 0 失败 | |
| H4 | `node --check` | 通过（改过 JS 时） | |
| H5 | `git diff --check` | 通过 | |
| H6 | `assess_phase.py` | `passed=true` | |
| H7 | `validate_adapter_boundary.py` | 通过（改过 Provider 时） | |
| H8 | `audit_reliability.py` | 通过（改过可靠性路径时） | |

---

## 7. 交付物总表

### 7.1 新增规格与 ADR

| 阶段 | 文件 |
|---|---|
| P0 | 更新 `specs/task-execution/task-crud.md`；新建根 `AGENTS.md` |
| P1 | `specs/execution-closure/{overview,job-lifecycle,prompt-package,model-binding,verification,artifact-store,cost-ledger,terminology}.md`；`docs/adr/ADR-009..014` |
| P3 | `specs/execution-closure/project-context.md` |
| P4 | `specs/execution-closure/task-plan.md` |
| P7 | 更新 `specs/routing/routing-policy.md` |
| P8 | 更新 `specs/gateway/{request-contract,authentication}.md` |
| P10 | 更新 `specs/acceptance-criteria.md` |
| P11 | `specs/execution-closure/repair.md` |
| P12 | `specs/execution-closure/orchestration.md` |
| P13 | 更新 `specs/execution/reliability.md` |
| P14 | `specs/ui/information-architecture.md` |

### 7.2 新增源码结构（目标形态，按改正清单 §9）

```text
src/model_router/
  domain/
    execution_job.py          P2      prompt_package.py      P5
    value_objects.py          P2      route_decision.py      P7
    execution_errors.py       P2      model_binding.py       P7
    project_snapshot.py       P3      verification.py        P10
    task_specification.py     P4      repair_work_order.py   P11
    task_plan.py              P4      synthesis.py           P12
                                      cost_ledger.py         P13
  application/
    build_project_context.py  P3      execute_routed_job.py  P9
    build_task_plan.py        P4      verify_execution.py    P10
    route_preview.py          P7      repair_execution.py    P11
    analyze_task.py           P8      finalize_delivery.py   P11
                                      orchestrate_plan.py    P12
                                      synthesize_results.py  P12
  ports/
    project_context_port.py   P3      task_executor_port.py  P9
    planner_port.py           P4      verification_port.py   P10
    prompt_compiler_port.py   P5
    execution_repository.py   P6      artifact_store.py      P6
  adapters/
    context/repository_context.py             P3
    prompts/markdown_prompt_compiler.py       P5
    persistence/sqlite_execution_repository.py P6
    persistence/filesystem_artifact_store.py   P6
    persistence/sqlite_cost_ledger.py          P13
    http/execution_gateway.py                  P8
    executors/{provider_answer,codex_repository,cursor_worker,document}_executor.py P9
    verification/{command_verifier,secret_scanner}.py P10
    observability/sqlite_observer.py           P13

artifacts/execution-packages/    P6（gitignored）
artifacts/execution-results/     P6（gitignored）
src/prompts/templates/           P5
```

### 7.3 每阶段必产文档

| 交付物 | 位置 | 何时 |
|---|---|---|
| 二次评估 | `docs/assessment/2026-MM-DD-phase-NN-<slug>.md` | 每阶段 |
| 矩阵更新 | `docs/checklist-matrix.md` | 每阶段 |
| STATUS 更新 | `STATUS.md` | 每阶段（至少改日期与结论） |
| README 更新 | `README.md` | 有对外 API/页面变化时 |
| 最终报告 | `docs/assessment/...phase-30-final-acceptance.md` | P15 |

---

## 8. 术语字典（唯一口径，代码/API/UI/文档四处必须一致）

这是防止"虚报完成"的核心工具。P1 会把本表复制进 `specs/execution-closure/terminology.md`。

| 术语 | 严格含义 | 允许的下一步 | 明确**不**代表 |
|---|---|---|---|
| `previewed` | 已生成 Plan / Prompt / RouteDecision，未调用任何模型或执行器 | approve → ready | 不代表已路由执行 |
| `routed` | 已产出 RouteDecision（选定候选模型） | dispatch | **不**代表已执行 |
| `queued` | 已投递到队列（Cursor 等），等待外部处理 | claim | **不**代表已开始、更不代表完成 |
| `dispatched` | 已交给执行器，执行器已接收 | running | 不代表已产出结果 |
| `running` | 执行器正在工作，有活跃 attempt | verifying / failed | 不代表有结果 |
| `answered` | 模型返回了文本 | verifying | **不**代表内容正确、**不**代表仓库被改 |
| `executed` | 执行器完成且返回 ExecutionReceipt | verifying | **不**代表结果正确 |
| `verified` | VerificationReport.status == PASS，7 个必要条件全满足 | delivered | — |
| `repairing` | 验证失败且在上限内进行第 N 次修复 | running / failed | 不代表将会成功 |
| `delivered` | 已产出 DeliveryReport 与全部 Artifact，可下载 | — | 不代表已 commit/push 到用户仓库 |
| `dispatch_success` | 投递动作本身成功 | — | **不**等于 `job_success` |
| `job_success` | Job 状态为 `SUCCEEDED`（含 verified） | — | — |
| `ENFORCED` | 可从 argv/config/响应**证明**用了指定模型 | — | 只写进 Prompt **不算** |
| `VERIFIED_FALLBACK` | 用了白名单内替代模型且有 `fallback_reason` | — | 不代表用了首选模型 |
| `EXECUTOR_MANAGED` | 执行器自管模型，系统不掌握 | — | **不得**对外显示为强制绑定 |

### 8.1 UI 文案映射（P14 直接照用）

| 状态 | 中文文案 | 颜色语义 |
|---|---|---|
| DRAFT | 草稿 | 灰 |
| ANALYZING | 分析中 | 蓝（进行） |
| WAITING_APPROVAL | 待审批（预览） | 橙（需操作） |
| READY | 待执行 | 蓝 |
| RUNNING | 执行中 | 蓝（进行） |
| VERIFYING | 验证中 | 蓝（进行） |
| REPAIRING | 修复中 N/上限 | 橙 |
| SUCCEEDED | 已完成并验证通过 | 绿 |
| FAILED | 失败（附证据） | 红 |
| CANCELLED | 已取消 | 灰 |
| Cursor queued | 已入队待处理 | 黄（**非**绿） |

---

## 9. 总验收判据（判断"是否真的完成了"）

以下 12 条**同时成立**才可宣称"一体化任务路由与完成系统已完成"。任何一条不成立，只能声明对应里程碑。

| # | 判据 | 验证方式 | 对应阶段 |
|---|---|---|---|
| 1 | 用户 Goal 被结构化为**可审批**的 Specification（含歧义清单与非目标） | `GET /jobs/<id>` + 分析页 | P4, P14 |
| 2 | 多角度子任务具有**依赖、边界、验收标准**三者 | `GET /jobs/<id>/plan` | P4 |
| 3 | 每个 PromptPackage **可重建、可哈希、可下载** | 同输入连跑 3 次 hash 相同 + `prompt.md` 下载 | P5, P6 |
| 4 | 路由模型与实际执行模型的关系**可验证** | receipt 中 `requested/actual/binding_status` | P7, P9 |
| 5 | 至少一个 Executor 能**真实完成仓库任务并返回证据** | 真实 Codex 任务的 changed_files + 测试输出 | P9 |
| 6 | 所有 `SUCCEEDED` 都由 VerificationReport 支撑 | 反例测试 R10-1/R10-6 | P10 |
| 7 | Repair 循环有**次数/成本/步数/时间**四重硬上限 | R11-6..R11-9, R11-13 | P11 |
| 8 | 多子任务能**并行**且综合基于 Artifact 而非字符串拼接 | R12-1, R12-8 | P12 |
| 9 | 成本、模型、Attempt、Artifact、报告**全链可追溯** | `/api/costs/summary` + Artifact 页 | P13, P14 |
| 10 | UI 全程准确显示 7 种状态，不虚报 | R14-7 + 走查 | P14 |
| 11 | 服务/容器重启后 Job 与证据**可恢复** | R8-9 + A-11 | P6, P8, P15 |
| 12 | 所有阶段有 **Red/Green 双 commit + 二次评估 + push** 证据 | `git log` 逐阶段核对 | 全部 |

### 9.1 里程碑级可声明话术（防越界）

| 达成 | 可以说 | 不可以说 |
|---|---|---|
| M0 | "基线可信，文档与代码一致" | "执行闭环已完成" |
| M1 | "可生成可审计的分析预览与完整提示词包" | "任务已自动完成" |
| M2 | "单任务可真实执行、自动验证、受限修复" | "多 Agent 平台已完成" |
| M3 | "多 Agent 并行协作与成本台账可用" | "生产就绪" |
| M4 | "一体化任务路由与完成系统已完成（本地单实例）" | "分布式生产平台"（除非另做 P16+） |

---

## 10. 风险登记与处置预案

在路线图 §20 的 13 项之上，补充本次实测新发现的 6 项（R-14..R-19）。

| # | 风险 | 严重度 | 触发信号 | 处置 |
|---|---|---|---|---|
| R-1 | UI/审计提交未推送 | 高 | `git status -sb` 显示 ahead | P0 首要动作；无网络则记录并在恢复后立即补推 |
| R-2 | 完整清单被误报完成 | 高 | README/STATUS 与实测不符 | §6.E + §6.G 每阶段拦截 |
| R-3 | Codex 模型绑定不可证明 | 高 | argv 中无模型参数 | 落 `EXECUTOR_MANAGED` 并在 UI 明示；不得伪装 ENFORCED |
| R-4 | `queued` 被当作 success | 高 | Dispatcher 对入队返回 `success=true` | P9 拆分 `dispatch_success` / `job_success` |
| R-5 | 无持久化 Job，长任务堵在 HTTP | 高 | 请求超时 | P6 + P8 |
| R-6 | 无自动验证 | 高 | 文本结果直接标成功 | P10 |
| R-7 | 成本控制不精确 | 中 | 只有静态价格 + pressure | P13 |
| R-8 | Planner 缺项目上下文 | 中 | Prompt 不含 AGENTS/specs | P3 + P5 |
| R-9 | 子任务串行 | 中 | 无并行度指标 | P12 |
| R-10 | Task CRUD 输入缺陷 | 中 | D-1..D-5 | P0 |
| R-11 | 指标重启丢失 | 中 | 重启后 `/api/metrics` 归零 | P13 |
| R-12 | Provider health 过于乐观 | 中 | health 只反映"已配置" | P13 主动探测 |
| R-13 | Docker 未实跑 | 中 | 无构建日志 | P15，或 CI，或明确声明未做 |
| **R-14** | **根 AGENTS.md 不存在，但两份文档都要求先读它** | 高 | Codex 报"文件不存在"后可能自行编造上下文 | P0 必须创建；否则 P3 的 Snapshot 无输入 |
| **R-15** | `checklist-matrix.md` 引用两个不存在的基线文档 | 中 | 审计时无法回溯基准 | P0 修正引用 |
| **R-16** | `budget_adapter` 不可用时静默返回 `0.0`（伪装成"预算充足"） | 高 | `/api/meta` 显示 0.0 却无 Oracle | P13 改为显式 `unknown` 并保守降级 |
| **R-17** | 领域层无状态机，`ExecutionTask` 可任意跃迁 | 中 | `draft → completed` 成功 | P0 加跃迁矩阵 |
| **R-18** | Red 与实现同 commit，TDD 不可审计 | 高 | `git show --stat` 显示同一 commit 含测试与实现 | §6.D1/D2 强制双 commit |
| **R-19** | LiteLLM 远程价格表拉取失败依赖网络 | 低 | 启动日志出现价格表警告 | P13 本地缓存入库 + 版本号 |

### 10.1 遇阻处置规则（Codex 必须遵守）

| 情况 | 动作 |
|---|---|
| 同一方法**第 2 次**失败 | 停止微调，写明根因，换一条技术路线 |
| 需要扩大写入范围 | **停止**，在 assessment 记录并向用户请示，不得自行扩权 |
| 测试无法通过且怀疑规格错 | 先改规格/ADR，再改测试，不得直接改测试断言迁就实现 |
| 需要真实密钥或外网 | 停止该子项，标记 `BLOCKED` 并继续其余可做部分 |
| 无法证明模型绑定 | 如实返回 `unsupported` / `EXECUTOR_MANAGED` |
| 发现敏感信息将进入产物 | 立即中止该产物生成，判 FINAL_FAILURE |
| 阶段范围被发现估计过大 | 拆成 NNa / NNb 两个阶段，各自走完整 12 步 |

---

## 11. 单阶段执行模板（Codex 复制此块开工）

```markdown
## 阶段 P<n> / 仓库 Phase <NN> — <阶段名>

### 0 上下文已读
- [ ] 本文 §5 对应小节
- [ ] AGENTS.md（根 + 嵌套）
- [ ] 路线图 §__ / 改正清单 §__
- [ ] specs：____________
- [ ] 最近 2 份 assessment：____________
- [ ] git status -sb / git log -5 输出（粘贴）

### 1 边界声明
- 唯一问题：__________（一句话）
- Bounded Context：__________
- allowed_write_paths：
  - __________
- forbidden_paths：
  - 其他 Context 的 domain
  - src/routing_table.py 的路由数据
  - .env / .runtime / artifacts 之外的运行时目录
- 非目标（≥3）：
  1. __________
  2. __________
  3. __________

### 2 规格变更
- [ ] 新增/修改：__________
- [ ] ADR：__________ 或「无新架构决策」

### 3 Red
| # | 测试文件::方法 | 期望 | 实际失败原因（粘贴摘要） |
|---|---|---|---|
| 1 | | | |

- [ ] commit（test: ...）hash：__________
- [ ] 该 commit `git show --stat` 中**无**生产代码

### 4 Green
- [ ] 最小实现文件清单：__________
- [ ] 无 skip / 无空断言 / 无吞异常
- [ ] commit（feat|fix: ...）hash：__________

### 5 回归
| 命令 | 结果 |
|---|---|
| unittest discover | __/__ 通过 |
| test_dashboard_demo | __/__ 通过 |
| node --check app.js | 通过 / 未涉及 |
| git diff --check | 通过 |
| assess_phase.py | passed=true |
| validate_adapter_boundary.py | 通过 / 未涉及 |
| audit_reliability.py | 通过 / 未涉及 |

### 6 审计清单（§6 全表）
- 6.A 边界 A1-A9：__/9
- 6.B 契约 B1-B6：__/6
- 6.C 安全 C1-C10：__/10
- 6.D TDD D1-D8：__/8
- 6.E 真实性 E1-E10：__/10
- 6.F 可观测 F1-F5：__/5
- 6.G 文档 G1-G8：__/8
- 6.H 回归 H1-H8：__/8
- 未通过项与处置：__________

### 7 二次评估
- [ ] docs/assessment/2026-MM-DD-phase-NN-<slug>.md 已建
- [ ] Checklist status 中 Partial 未写成 Completed
- [ ] 新风险已登记

### 8 发布
- [ ] git push origin main 成功
- [ ] git status -sb 无 ahead
- [ ] 本文 §3 表中该行状态改为 ☑
```

---

## 12. 快速开始命令

```powershell
Set-Location C:\Codex\luyou

# 起点确认
git status --short --branch
git log -8 --oneline --decorate

# 确定性门禁基线（当前应为 40 / 8）
python -m unittest discover -s tests -v
python scripts/test_dashboard_demo.py
node --check dashboard/assets/app.js
git diff --check
python skills/model-router-delivery/scripts/assess_phase.py --phase baseline

# 边界与可靠性（改 Provider / 可靠性路径时）
python skills/provider-adapter-contract/scripts/validate_adapter_boundary.py
python skills/router-reliability-audit/scripts/audit_reliability.py

# 本地服务（验证 API 时）
python scripts/dashboard_server.py     # http://127.0.0.1:1785
```

P0 的第一个动作（网络可达时）：

```powershell
git push origin main    # 推送 2e8d962 与 8babba4
git status --short --branch    # 确认无 ahead
```

---

## 13. 与上游文档的差异说明

本文在合并两份文档时做了 7 处**主动决策**，均已在正文标注，此处集中列出以便追责：

| # | 决策 | 理由 |
|---|---|---|
| 1 | 阶段重编号为 P0-P15 / 仓库 Phase 15-30 | 两份上游文档都用 Phase 0-12 且含义不同；仓库 assessment 已占用 phase-01..14 |
| 2 | Job 状态机取路线图 §10.2 的 10 态，弃用改正清单 §3.3 的 13 态 | 10 态更少歧义；13 态中 `CONTEXT_BUILDING`/`PROMPT_COMPILING` 等属实现细节，不该进领域状态 |
| 3 | 强制 Red 与 Green **双 commit** | P14 评估已确认单 commit 导致 TDD 不可审计 |
| 4 | 回归基线统一为 **40+8**（改正清单写的 31 已过时） | 实测 |
| 5 | 把"创建根 AGENTS.md"提到 P0 且列为高危风险 | 实测该文件不存在，而两份文档都要求先读它 |
| 6 | 新增 P4（TaskSpecification/TaskPlan）为独立阶段 | 改正清单把它混在 Prompt 阶段里，导致 DAG 无处落地 |
| 7 | 新增 §8 术语字典并要求四处一致 | 两份文档反复强调"queued ≠ completed"，但无单一口径表，易漂移 |

其余内容均为两份上游文档的忠实合并，未删减任何待办项。

---

## 14. 结语

当前仓库是**可运行的模型路由 Demo + Task CRUD 工作台**，不是可审计的多 Agent 任务完成平台。差距不在模型数量或页面数量，而在缺少一条把 Task、Prompt、Route、Execution、Verification、Delivery 串起来的**持久化事实链**。

正确路径是先做 **P0-P1 让基线可信**，再做 **P2-P8 的 ExecutionJob + PromptPackage Preview 垂直切片**，然后才接真实 Executor、Verification、Repair 和多 Agent DAG。

任何跳过 P0-P1 直接做 P9 的尝试，都会在缺少规格与术语口径的情况下产生新一轮"看起来完成了"的技术债。
