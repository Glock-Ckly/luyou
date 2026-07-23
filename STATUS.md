# AI Model Router 实施状态

> 最后审计日期：2026-07-23

## 总体结论

五页工程化 Demo 已完成并可运行。DDD 执行核心、Provider Port/Adapter、统一 Dispatcher、OpenAI 兼容 Gateway、鉴权、校验、限流、健康过滤、Retry/Fallback、Trace、内存指标、Docker/Compose 定义、Skills 与边界 Agents 均已落地。

系统不是完整生产平台。gRPC 运行时、Runtime Agent、持久化 Observability、Circuit Breaker、Token/Cost 聚合、多实例状态和 Kubernetes 仍为部分或延期项。

## 当前验证

| 检查 | 2026-07-23 结果 |
|---|---|
| 离线 unit/contract/integration | 31/31 通过 |
| 五页 Demo 检查 | 7/7 通过 |
| Browser UI | 5 页通过，无乱码与控制台错误 |
| Smoke Relay | 15/15 通过 |
| L2 在线分类 | 20/25，80%，失败 |
| Decomposer 在线评估 | 10/10 通过 |
| E2E 在线评估 | 13/13 通过 |
| run_acceptance.py | 6/7 通过 |
| Docker image build | 未验证，当前主机无 Docker Engine |

## 已完成里程碑

1. Specification、Acceptance Criteria 与 ADR 基线
2. DDD 值对象、错误模型、执行结果与 Provider Port
3. LiteLLM Provider Contract 与标准错误映射
4. 有限 Retry、顺序 Fallback、Timeout 与 Fail-fast
5. 单一公开 Dispatcher 执行路径
6. OpenAI 兼容 HTTP、Bearer 鉴权、输入校验、安全错误、CORS、工作目录限制与基础限流
7. Provider Registry、健康过滤、结构化事件与内存 Metrics
8. UTF-8 五页 Demo 与真实 Trace/Attempt/Health/Metrics
9. Dockerfile、Compose、Healthcheck、环境说明与 Proto 边界
10. 三个 Skills 与四个边界 Agents

## 已知问题与建议

1. L2 在线分类波动：固定模型版本和响应 Schema；为 debugging/implementation 增加确定性关键字护栏；当 L2 返回 uncertain 时回退高置信 L1；把 5 个失败样本加入离线回归集。
2. Docker 未实跑：在 GitHub Actions 增加 docker build、容器 /health 和 /v1/chat/completions 契约测试。
3. Provider Health 为被动配置健康：增加短超时主动探测、缓存与熔断状态，但不要在 Adapter 内决定路由。
4. Metrics 非持久化：通过 ExecutionObserver Port 接入 OpenTelemetry/Prometheus，并聚合 Token Usage 与 Estimated Cost。
5. Agent 仅为工程角色：若引入 Runtime Agent，必须先实现 Max Steps、Max Cost、Timeout、Skill 白名单和权限边界。

完整矩阵见 docs/checklist-matrix.md，阶段证据见 docs/assessment/。
