# README 与 Skill 同步（待完成）

## 现状

| 文件 | 问题 |
|------|------|
| 根目录 `README.md` | 仅列 smoke + eval_l2，缺 decomposer/e2e/acceptance/看板 |
| `STATUS.md` | 简短，与 `docs/completed/` 有重叠 |
| `~/.claude/skills/luyou/SKILL.md` | 阻塞项过时（仍写「无 API Key」「L2 未实测」） |

## 待办

- [ ] README 增加 `run_acceptance.py`、1785 看板、cursor_cli
- [ ] luyou Skill 指向 `docs/completed/README.md` 作权威索引
- [ ] Skill 阻塞表改为「待完成见 docs/pending/」

## 验收

新会话 `/luyou` 激活后，Agent 读到的状态与仓库 docs 一致。
