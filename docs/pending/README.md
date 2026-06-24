# 待完成文档索引

> 多模型路由系统（luyou）— 设计中有、或运行中仍缺的能力  
> 与 `docs/completed/` 分开存放，便于排期与分工。

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [01-用户对话界面.md](01-用户对话界面.md) | 网页输入 prompt、展示路由结果 | 高 |
| [02-看板服务稳定性.md](02-看板服务稳定性.md) | 1785 单进程、防阻塞、自动拉起 | 中 |
| [03-llm-router原生Provider.md](03-llm-router原生Provider.md) | 绕过 relay_llm，修复 standard.yaml | 低 |
| [04-预算精确计量.md](04-预算精确计量.md) | 真实 spend/cap、session hook 联动 | 中 |
| [05-子任务并行执行.md](05-子任务并行执行.md) | Decomposer 后并行调模型 | 中 |
| [06-成本追踪持久化.md](06-成本追踪持久化.md) | 每次路由落库、报表 | 低 |
| [07-RAG分类层.md](07-RAG分类层.md) | 设计中的 L1.5 RAG（已明确不做） | 搁置 |
| [08-README与Skill同步.md](08-README与Skill同步.md) | 根 README、luyou Skill 与现状对齐 | 低 |

## 与已完成的关系

待办项**不推翻**现有 `orchestrator.handle_prompt()` 主路径，而是在其外围补 UI、运维与可观测性。
