"""工具基类模块"""

from abc import ABC, abstractmethod
from pydantic import BaseModel
from langchain_core.tools import Tool


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool
    data: str
    error: str | None = None


class BaseAgentTool(ABC):
    """工具基类，所有工具继承此类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，供 LLM 理解用途"""
        pass

    @abstractmethod
    def run(self, *args, **kwargs) -> ToolResult:
        """执行工具逻辑"""
        pass

    def to_langchain_tool(self) -> Tool:
        """转换为 LangChain 工具格式"""
        return Tool(
            name=self.name,
            description=self.description,
            func=lambda *args, **kwargs: self.run(*args, **kwargs).data,
        )
