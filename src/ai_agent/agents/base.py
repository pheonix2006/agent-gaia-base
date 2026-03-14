"""Agent 基类模块"""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel


class BaseAgent(ABC):
    """Agent 基类，定义统一接口"""

    def __init__(self, llm: BaseChatModel, tools: list[Any] | None = None) -> None:
        self.llm = llm
        self.tools = tools or []

    @abstractmethod
    async def run(self, message: str) -> str:
        """运行 Agent，返回响应"""
        pass

    @abstractmethod
    def get_graph(self) -> Any:
        """获取 LangGraph 编译后的图（用于调试/可视化）"""
        pass
