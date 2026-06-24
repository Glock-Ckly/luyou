# llm-router 原生 Provider（待完成 / 低优先级）

## 现状

PyPI `llm-router` 安装包缺少 `policies/standard.yaml`，导致：

```text
llm_router.providers 无法导入
```

**已绕过：** `src/relay_llm.py` 直接调 LiteLLM + `relay_config` 环境变量。

## 待办选项

| 选项 | 说明 |
|------|------|
| A | 向 upstream 提 PR / 等版本修复 |
| B | 本地 patch site-packages 补 `standard.yaml` |
| C | 维持 relay_llm，删除对 llm-router providers 的依赖声明 |

## 若完成原生集成

- orchestrator 可改用 `llm_router.providers.call_llm`
- 与 MCP hooks 成本统计、断路器统一
- 需回归：`run_acceptance.py` 全绿

## 当前建议

**C — 维持 bypass**，除非需要 llm-router 高级 scorer/team 功能。
