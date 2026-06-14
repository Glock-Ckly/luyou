# luyou — 多模型路由系统

个人编码工作流：任务类型 → 模型精确路由 + Cursor 手动交付。

基于 [llm-router](https://github.com/ypollak2/llm-router) wrapper，不修改其源码。

## 快速开始

1. 复制 `config/relay.env.example` → `~/.llm-router/.env`，填入中转站密钥与 Base URL
2. 按需调整 `config/relay_models.yaml` 模型映射
3. 验收：`python scripts/smoke_relay.py`（须 **15/15 通过**）
4. 端到端：`cd src && python -c "import asyncio; from orchestrator import handle_prompt; print(asyncio.run(handle_prompt('hello')))"`

## 提交前必跑验收

每个任务完成后：

```bash
python scripts/smoke_relay.py
```

仅当输出 `Done: 15 passed, 0 failed` 时再 `git commit` / `git push`。

## 架构

```
Prompt → TaskDecomposer → L1(关键词) → L2(DeepSeek) → Router → Model/Cursor → Validator
```

详见 [multi-llm-router-design.md](multi-llm-router-design.md) 与 [STATUS.md](STATUS.md)。

## 密钥

- **切勿**将 `~/.llm-router/.env` 或含真实 `sk-` 的文件提交到仓库
- 仓库内仅保留 `config/relay.env.example` 模板
