"""Agent 相关类型定义

这些类型用于 Agent 执行过程中的事件和数据结构。
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from .common import AnyDict


class AgentEventType(str, Enum):
    """Agent 事件类型枚举（tool_calling 模式）"""

    TEXT = "text"  # LLM 文本输出
    TOOL_CALL = "tool_call"  # 工具调用请求
    TOOL_RESULT = "tool_result"  # 工具执行结果
    THINKING = "thinking"  # 思考/推理过程
    ERROR = "error"  # 错误
    DONE = "done"  # 完成


class AgentEvent(BaseModel):
    """Agent 执行事件

    用于表示 Agent 执行过程中的各类事件，支持 SSE 格式输出。

    Data 字段说明:
        - text: content
        - tool_call: tool_name, arguments
        - tool_result: tool_name, result
        - thinking: content
        - error: message, details
        - done: answer
    """

    type: AgentEventType = Field(description="事件类型")
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
                "type": self.type.value,
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


class AgentState(TypedDict):
    """Agent 状态（基于 LangGraph 的消息列表模式）

    用于 tool_calling 模式的 ReAct Agent。
    messages 使用 add_messages reducer 支持增量追加。
    """

    messages: Annotated[list[BaseMessage], add_messages]
    step_count: int


@dataclass
class AgentContext:
    """Agent 运行上下文配置

    传递可选的运行时配置参数，用于覆盖默认行为。
    """

    system_prompt_override: str | None = None
    memory_text: str | None = None
    max_steps_override: int | None = None
