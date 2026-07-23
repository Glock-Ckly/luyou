# luyou — AI Model Router

一个基于 Python 模块化单体、DDD/TDD 和 Ports & Adapters 的 AI Model Router Demo。系统提供 OpenAI 兼容 API、确定性路由、多 Provider 抽象、健康过滤、有限重试与 Fallback、Trace、指标、五页控制台和容器化交付。

## 快速开始

1. 使用 Python 3.12 安装依赖：pip install -e .
2. 从 config/relay.env.example 配置 Provider 密钥与 Base URL，切勿提交真实密钥。
3. 可选设置 MODEL_ROUTER_API_TOKEN、MODEL_ROUTER_ALLOWED_ORIGINS、MODEL_ROUTER_ALLOWED_WORKDIRS 和 MODEL_ROUTER_RATE_LIMIT_PER_MINUTE。
4. 启动：python scripts/dashboard_server.py
5. 打开：http://127.0.0.1:1785

Docker 方式见 docs/deployment.md。

## HTTP API

- GET /health
- POST /v1/chat/completions
- GET /api/meta
- GET /api/catalog
- GET /api/specs
- GET /api/metrics
- POST /api/route
- POST /api/reliability/simulate

## 五页 Demo

| 页面 | 地址 | 真实能力 |
|---|---|---|
| 系统总览 | / | Git、目录、请求指标与最近事件 |
| 路由实验室 | /routing.html | 统一 Dispatcher、Trace、子任务与 Provider 尝试链 |
| Provider 目录 | /providers.html | 运行时模型目录与 Provider 健康 |
| 可靠性实验室 | /reliability.html | 生产 ExecutionService 上的故障注入、Retry 与 Fallback |
| 架构与规格 | /architecture.html | DDD 边界、质量门禁与明确延期项 |

## 确定性质量门禁

- python -m unittest discover -s tests -v：31/31 通过（2026-07-23）
- python scripts/test_dashboard_demo.py：7/7 通过（2026-07-23）
- node --check dashboard/assets/app.js：通过
- 浏览器五页验收：中文、导航、动态数据、可靠性交互和控制台错误检查通过

## 在线评估

python scripts/run_acceptance.py 在 2026-07-23 的结果为 6/7。Smoke 15/15、Decomposer 10/10、E2E 13/13 均通过；L2 在线分类为 20/25（80%），因 2 个 implementation/debugging 关键样本被判为 uncertain 而失败。在线评估不能替代确定性单元、契约和集成测试，也不能继续宣称历史 25/25。

## 关键边界

- 当前运行时是 Python，而不是 Java/Spring Boot；理由见 ADR-001。
- 当前是模块化单体；proto/model_router.proto 仅定义未来边界，未实现 gRPC Client/Server。
- Runtime Agent Decision、持久化指标、Circuit Breaker、流式响应和 Kubernetes 均未宣称完成。
- 清单完成矩阵与解决方案见 docs/checklist-matrix.md。

## 可复用资产

- skills/model-router-delivery
- skills/provider-adapter-contract
- skills/router-reliability-audit
- skills/agents
