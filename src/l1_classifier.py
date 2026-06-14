"""
L1 Heuristic Classifier — 关键词匹配快筛层

移植自 brentsWorks/llm-router 的 KeywordClassifier (backend/classification.py)，
扩展到支持 9 种编码任务类型。

决策逻辑:
  - >= 3 个关键词匹配 → confidence 0.7+ → 跳过 L2
  - 1-2 个关键词匹配 → confidence 0.3-0.6 → 进入 L2
  - 0 个匹配 → confidence 0.0 → 进入 L2

来源:
  - 核心算法: brentsWorks `_count_keyword_matches` + 置信度评分逻辑
  - 关键词库: 根据用户需求自定义 (9 种编码任务类型)
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 扩展关键词库 ─────────────────────────────────────────────────
# brentsWorks 原有 3 类 (code/creative/qa)，现扩展为 9 类编码任务

KEYWORD_MAP: dict[str, list[str]] = {
    "architecture": [
        "架构", "architecture", "系统设计", "system design",
        "技术选型", "design pattern", "设计模式", "模块划分",
        "微服务", "数据库设计", "schema design", "api design",
        "整体规划", "技术方案", "选型", "整体架构",
        "rewrite the whole", "from scratch", "重新设计",
    ],
    "implementation": [
        "implement", "develop", "coding",
        "add feature", "添加功能", "实现功能",
        "编写代码", "编写函数", "写段代码", "写个函数",
        "帮我写", "帮我做一个", "帮我实现",
        "写一个", "写个", "写段", "做一", "实现一",
    ],
    "debugging": [
        "调试", "debug", "报错", "error", "bug", "修复",
        "fix", "崩溃", "crash", "不工作", "not working",
        "异常", "exception", "stack trace", "traceback",
        "修好", "修一下", "定位问题", "排查",
    ],
    "refactor": [
        "重构", "refactor", "优化代码", "改进结构",
        "clean up", "整理", "拆分", "extract method",
        "rename", "重组", "重写", "rewrite",
        "简化", "简化代码", "去重", "消除重复",
    ],
    "boilerplate": [
        "模板", "template", "脚手架", "scaffold", "crud",
        "配置文件", "config", "样板代码", "boilerplate",
        "生成器", "生成", "generate", "创建项目",
        "初始化", "init", "起一个", "搭一个",
    ],
    "bulk_generation": [
        "批量", "bulk", "测试用例", "test case", "单元测试",
        "重复", "循环生成", "mass produce", "文档生成",
        "docstring", "批处理", "全部测试", "覆盖",
        "测试文件", "test file", "spec", "50个", "100个",
    ],
    "data_processing": [
        "数据清洗", "data clean", "转换", "transform",
        "csv", "json parse", "格式化", "format",
        "解析", "parse", "提取", "extract", "etl",
        "数据迁移", "migrate", "导入", "导出",
    ],
    "code_patch": [
        "修改文件", "edit file", "改这个", "fix this file",
        "更新代码", "update code", "改一行", "change line",
        "替换", "replace in", "改文件", "修文件",
        "在这个文件", "in this file",
    ],
    "file_edit": [
        "编辑", "edit", "rewrite", "重写", "修改",
        "更新文件", "update file", "patch", "diff",
        "改 [a-z]+\\.(py|js|ts|go|rs|java)", "修改.*\\.(py|js|ts)",
    ],
}


@dataclass
class L1Result:
    """L1 分类结果"""
    task_type: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    reasoning: str = ""


def classify_l1(prompt: str, confidence_threshold: float = 0.7) -> L1Result | None:
    """L1 关键词快速分类。

    移植自 brentsWorks KeywordClassifier.classify()，
    核心改动: 分类维度从 3 类 (code/creative/qa) 扩展为 9 类编码任务。

    Args:
        prompt: 用户输入 prompt
        confidence_threshold: 置信度阈值，>= 此值视为"高置信"，可跳过 L2。

    Returns:
        L1Result 如果高置信 (跳过 L2)，None 如果低置信 (进入 L2)。
    """
    if not prompt or not prompt.strip():
        return None

    prompt_lower = prompt.strip().lower()

    # 计算每类关键词匹配数 (移植自 brentsWorks _count_keyword_matches)
    category_scores: dict[str, tuple[int, list[str]]] = {}
    for category, keywords in KEYWORD_MAP.items():
        matched = [kw for kw in keywords if kw in prompt_lower]
        if matched:
            category_scores[category] = (len(matched), matched)

    if not category_scores:
        return None  # 无匹配 → 进入 L2

    # 取最高分类别 (移植自 brentsWorks max() 逻辑)
    best_category = max(category_scores, key=lambda c: category_scores[c][0])
    best_score, matched_keywords = category_scores[best_category]

    # 置信度评分 (移植自 brentsWorks，调整为 9 类场景)
    total_keywords = len(KEYWORD_MAP[best_category])
    if best_score >= 3:
        confidence = min(0.9, 0.7 + (best_score / total_keywords) * 0.2)
    elif best_score >= 2:
        confidence = min(0.75, 0.55 + (best_score / total_keywords) * 0.2)
    else:
        confidence = min(0.55, 0.30 + (best_score / total_keywords) * 0.25)

    reasoning = f"Matched {best_score} keyword(s): {', '.join(matched_keywords)}"

    # 门控: 低于阈值返回 None → 进入 L2
    if confidence < confidence_threshold:
        return None

    return L1Result(
        task_type=best_category,
        confidence=confidence,
        matched_keywords=matched_keywords,
        reasoning=reasoning,
    )


# ── 自测 ─────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        # (prompt, expected_task_type_or_None_if_L2)
        # 单关键词匹配 → 置信度 ~0.3 → L2 needed (设计如此，交给 L2 准确分类)
        ("帮我写一个 Python 装饰器测量函数执行时间", None),
        # 3 关键词匹配 (调试+报错+error) → 置信度 0.73 → 高置信跳过 L2
        ("调试这个报错: TypeError: 'NoneType' object is not iterable", "debugging"),
        # 单关键词 (设计) → L2 needed
        ("设计一个微服务架构的用户认证系统", None),
        # 2 关键词 (修改文件+in this file? no...) → 需要检查
        ("帮我修改 src/auth.py 里的过期时间改成 3600 秒", None),
        # 写个+模板+crud → 3匹配 → 高置信
        ("写个 crud 接口的模板代码和脚手架配置文件", "boilerplate"),
        # 无匹配 → L2
        ("今天天气怎么样", None),
    ]

    passed = 0
    failed = 0
    for prompt, expected in tests:
        result = classify_l1(prompt)
        if result:
            ok = result.task_type == expected
            status = "OK" if ok else f"FAIL(got {result.task_type}, expected {expected})"
            print(f"{status} [{result.confidence:.2f}] {prompt[:40]}... -> {result.task_type}")
            if ok: passed += 1
            else: failed += 1
        else:
            ok = expected is None
            status = "OK" if ok else f"FAIL(expected {expected}, got L2)"
            print(f"{status} [LOW]  {prompt[:40]}... -> L2 needed")
            if ok: passed += 1
            else: failed += 1

    print(f"\n{passed}/{passed+failed} tests passed")
