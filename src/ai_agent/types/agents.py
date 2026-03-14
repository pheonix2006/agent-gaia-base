"""Agent 相关类型定义

这些类型用于 Agent 执行过程中的事件和数据结构。
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import AnyDict


class AgentEventType(str, Enum):
    """Agent 事件类型枚举"""

    THINK = "think"  # 思考阶段
    ACT = "act"  # 行动阶段（调用工具）
    OBSERVE = "observe"  # 观察阶段（获取工具结果）
    ERROR = "error"  # 错误
    FINISH = "finish"  # 完成


class AgentAction(BaseModel):
    """LLM 返回的结构化动作

    表示 LLM 决定执行的动作，包括调用工具或完成任务。
    """

    action: str = Field(description="工具名称或 'finish'")
    params: AnyDict = Field(default_factory=dict, description="工具参数")
    memory: str = Field(default="", description="本轮观察/思考")


class AgentEvent(BaseModel):
    """Agent 执行事件

    用于表示 Agent 执行过程中的各类事件，支持 SSE 格式输出。

    Data 字段说明:
        - think: reasoning, raw_output
        - act: tool_name, params
        - observe: tool_name, result_summary
        - error: message, details
        - finish: answer
    """

    event: AgentEventType = Field(description="事件类型")
    data: AnyDict = Field(default_factory=dict, description="事件数据")
    step: int = Field(ge=0, description="步骤序号")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="事件时间戳"
    )

    model_config = ConfigDict(frozen=True)

    def to_json(self) -> str:
        """转换为 JSON 字符串

        Returns:
            JSON 格式的字符串
        """
        import json

        return json.dumps(
            {
                "event": self.event.value,
                "data": self.data,
                "timestamp": self.timestamp.isoformat(timespec="seconds"),
                "step": self.step,
            },
            ensure_ascii=False,
        )

    def to_sse(self) -> str:
        """转换为 SSE (Server-Sent Events) 格式字符串

        Returns:
            SSE 格式的字符串，如 "data: {...}\\n\\n"
        """
        return f"data: {self.to_json()}\n\n"
