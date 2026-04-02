"""Agent 基类模块"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types.agents import AgentContext, AgentEvent


class BaseAgent(ABC):
    """Agent 基类，定义统一接口

    所有 Agent 实现必须继承此类并实现三个抽象方法:
    - run(): 同步返回最终结果
    - stream(): 流式返回 AgentEvent 事件
    - get_graph(): 返回编译后的 LangGraph 状态图

    Attributes:
        llm: LangChain 聊天模型实例
        tools: Agent 可用的工具列表
        _tool_map: 工具名称到工具实例的映射，用于快速查找
    """

    def __init__(
        self, llm: BaseChatModel, tools: list[BaseAgentTool]
    ) -> None:
        self.llm = llm
        self.tools = tools
        self._tool_map: dict[str, BaseAgentTool] = {
            t.name: t for t in tools
        }

    @abstractmethod
    async def run(
        self, message: str, *, context: AgentContext | None = None
    ) -> str:
        """运行 Agent，返回响应

        Args:
            message: 用户输入消息
            context: 可选的运行上下文配置

        Returns:
            最终响应字符串
        """
        ...

    @abstractmethod
    def stream(
        self, message: str, *, context: AgentContext | None = None
    ) -> AsyncIterator[AgentEvent]:
        """流式运行 Agent，逐步 yield 事件

        Args:
            message: 用户输入消息
            context: 可选的运行上下文配置

        Yields:
            AgentEvent: 执行过程中的各类事件
        """
        ...

    @abstractmethod
    def get_graph(self) -> CompiledStateGraph:
        """获取 LangGraph 编译后的状态图

        Returns:
            编译后的状态图实例
        """
        ...
