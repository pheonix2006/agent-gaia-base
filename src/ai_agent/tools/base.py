"""工具基类模块"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
from langchain_core.tools import Tool


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool
    data: Any  # 改为 Any 支持复杂结构
    error: str | None = None
    metrics: dict[str, Any] = {}  # 执行指标（耗时、token数等）


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

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema 格式的参数定义，供 LLM 理解参数结构"""
        return {}

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        """执行工具逻辑（异步）"""
        pass

    def to_langchain_tool(self) -> Tool:
        """转换为 LangChain 工具格式"""
        import asyncio

        def sync_wrapper(*args, **kwargs):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            coro = self.run(**kwargs)
            if loop and loop.is_running():
                # 如果已在事件循环中，创建新线程运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result().data
            else:
                return asyncio.run(coro).data

        return Tool(
            name=self.name,
            description=self.description,
            func=sync_wrapper,
        )
