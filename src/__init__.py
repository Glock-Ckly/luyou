"""
multi-llm-router — Personal Multi-LLM Routing System

基于 llm-router (ypollak2) 基础设施，集成 brentsWorks 分类机制，
为个人编码工作流提供任务类型→模型精确路由。

Modules:
  l1_classifier      — 关键词快速分类 (移植自 brentsWorks)
  routing_table      — 核心映射 + 任务感知降级链
  task_decomposer    — 大任务拆分子任务
  cursor_queue       — Cursor 手动交付队列
  response_validator — 轻量后验校验
  orchestrator       — 中央编排器
"""

from .routing_table import (
    route,
    RoutingDecision,
    TaskType,
    CostLevel,
    TASK_TO_MODEL,
    FALLBACK_CHAINS,
)
from .l1_classifier import classify_l1, L1Result
from .cursor_queue import push as cursor_push, pop as cursor_pop, list_tasks as cursor_list
from .orchestrator import MultiModelOrchestrator, handle_prompt

__version__ = "0.1.0"
__all__ = [
    "MultiModelOrchestrator",
    "handle_prompt",
    "route",
    "RoutingDecision",
    "TaskType",
    "CostLevel",
    "TASK_TO_MODEL",
    "FALLBACK_CHAINS",
    "classify_l1",
    "L1Result",
    "cursor_push",
    "cursor_pop",
    "cursor_list",
]
