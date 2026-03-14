"""ReAct Agent 事件定义

注意：此模块保留以向后兼容。
新代码应使用 ai_agent.types 模块中的类型。
"""

# 从类型模块重新导出，保持兼容
from ai_agent.types import AgentEvent, AgentEventType  # noqa: F401

__all__ = ["AgentEvent", "AgentEventType"]
