# luyou — AI Model Router 五页 Demo

个人编码工作流：任务类型 → 模型精确路由 + Cursor 手动交付，并提供可运行的五页工程化控制台。

基于 [llm-router](https://github.com/ypollak2/llm-router) wrapper，不修改其源码。

## 快速开始

1. 复制 `config/relay.env.example` → `~/.llm-router/.env`，填入中转站密钥与 Base URL
2. 按需调整 `config/relay_models.yaml` 模型映射
3. 验收（提交前必跑）：
   - `python scripts/smoke_relay.py` — 须 **15/15 通过**
   - `python scripts/eval_l2.py` — L2 分类评估（当前基线 **25/25**）
4. 端到端：`cd src && python -c "import asyncio; from orchestrator import handle_prompt; print(asyncio.run(handle_prompt('hello')))"`

## 提交前必跑验收

每个任务完成后：

```bash
python scripts/smoke_relay.py
python scripts/eval_l2.py
python scripts/test_dashboard_demo.py
```

仅当 smoke `15 passed, 0 failed` 且 eval `PASS` 时再 `git commit` / `git push`。

## 五页 Demo

启动服务：

    python scripts/dashboard_server.py

打开 http://127.0.0.1:1785：

| 页面 | 地址 | 实际能力 |
|---|---|---|
| Command Center | / | Git、预算、Provider、Model 与路由统计 |
| Routing Lab | /routing.html | 调用真实 /api/route 分发链路 |
| Provider Registry | /providers.html | 读取运行时模型目录、成本与 Contract |
| Reliability Lab | /reliability.html | Retry / Fallback 故障注入与 Trace |
| Architecture & Specs | /architecture.html | DDD 边界、生命周期、ADR 与质量门禁 |

新增 API：GET /api/catalog、GET /api/specs、POST /api/reliability/simulate。

完整落地计划见 [docs/AI_MODEL_ROUTER_DEMO_PLAN.md](docs/AI_MODEL_ROUTER_DEMO_PLAN.md)。

## 架构

```
Prompt → TaskDecomposer → L1(关键词) → L2(DeepSeek) → Router → Model/Cursor → Validator
```

详见 [multi-llm-router-design.md](multi-llm-router-design.md) 与 [STATUS.md](STATUS.md)。

## 密钥

- **切勿**将 `~/.llm-router/.env` 或含真实 `sk-` 的文件提交到仓库
- 仓库内仅保留 `config/relay.env.example` 模板
