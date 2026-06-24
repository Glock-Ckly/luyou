# 已完成文档索引

> 多模型路由系统（luyou）— 截至 2026-06-14 已落地并验收通过的部分  
> 源码仓库：[Glock-Ckly/luyou](https://github.com/Glock-Ckly/luyou)

本目录与 `docs/pending/` 分离：**此处仅描述已实现、可运行、已测试的内容**。

| 文档 | 说明 |
|------|------|
| [01-项目概述.md](01-项目概述.md) | 项目目标、模型职责、输出格式 |
| [02-架构与流水线.md](02-架构与流水线.md) | 端到端数据流与模块依赖 |
| [03-中转站接入.md](03-中转站接入.md) | Ccode 网关、密钥、模型映射 |
| [04-任务分级系统.md](04-任务分级系统.md) | Decomposer、L1、L2 分级逻辑 |
| [05-路由表与预算.md](05-路由表与预算.md) | task_type→model、降级链、四区预算 |
| [06-编排器与执行.md](06-编排器与执行.md) | Orchestrator、Validator、relay_llm |
| [07-Cursor队列.md](07-Cursor队列.md) | 手动交付容器与 CLI |
| [08-验收与测试.md](08-验收与测试.md) | smoke / eval / acceptance 脚本 |
| [09-进度看板.md](09-进度看板.md) | 1785 端口可视化看板 |
| [10-MCP与安装.md](10-MCP与安装.md) | Cursor MCP、Claude hooks、安装脚本 |
| [11-里程碑与验收结果.md](11-里程碑与验收结果.md) | 7+1 里程碑与数字验收 |
| [12-文件清单.md](12-文件清单.md) | 仓库内已实现文件一览 |

## 一键验收

```bash
python scripts/run_acceptance.py
```

## 设计原文

完整设计见仓库根目录 `multi-llm-router-design.md`（设计阶段文档，部分表述早于实施）。
