"""工具基类模块"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from pydantic import BaseModel
from langchain_core.tools import StructuredTool

from ai_agent.types import ToolResult, AnyDict

P = TypeVar("P", bound=BaseModel)
R = TypeVar("R")


class BaseAgentTool(ABC, Generic[P, R]):
    """工具基类，所有工具继承此类

    泛型参数:
        P: 参数 Pydantic 模型类型
        R: 返回数据类型

    Example:
        class SearchParams(BaseModel):
            query: str

        class SearchTool(BaseAgentTool[SearchParams, list[str]]):
            @property
            def name(self) -> str:
                return "search"

            @property
            def description(self) -> str:
                return "Search for items"

            @property
            def params_schema(self) -> type[SearchParams]:
                return SearchParams

            async def run(self, params: SearchParams) -> ToolResult[list[str]]:
                results = await self._search(params.query)
                return ToolResult(success=True, data=results)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，供 LLM 理解用途"""
        ...

    @property
    @abstractmethod
    def params_schema(self) -> type[BaseModel]:
        """参数的 Pydantic 模型类"""
        ...

    @property
    def parameters(self) -> AnyDict:
        """自动生成 JSON Schema（向后兼容）

        从 params_schema 自动生成，无需手写。
        """
        schema: AnyDict = self.params_schema.model_json_schema()
        return schema

    @abstractmethod
    async def run(self, params: P) -> ToolResult[R]:
        """执行工具逻辑（异步）

        Args:
            params: 类型化的参数对象

        Returns:
            ToolResult 包含执行结果
        """
        ...

    def to_langchain_tool(self) -> StructuredTool:
        """转换为 LangChain StructuredTool 格式"""
        import asyncio

        args_schema: type[BaseModel] = self.params_schema

        async def async_wrapper(**kwargs: Any) -> str:
            """异步包装器"""
            # 将 kwargs 转换为 Pydantic 模型
            params: P = args_schema(**kwargs)  # type: ignore
            result: ToolResult[R] = await self.run(params)
            if result.success:
                return str(result.data)
            return f"Error: {result.error}"

        def sync_wrapper(**kwargs: Any) -> str:
            """同步包装器：处理异步调用"""
            coro = async_wrapper(**kwargs)
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    import threading

                    result_container: list[str] = []
                    exception_container: list[Exception] = []

                    def run_in_new_loop() -> None:
                        try:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            result_container.append(new_loop.run_until_complete(coro))
                            new_loop.close()
                        except Exception as e:
                            exception_container.append(e)

                    thread = threading.Thread(target=run_in_new_loop)
                    thread.start()
                    thread.join(timeout=30)

                    if exception_container:
                        raise exception_container[0]
                    if result_container:
                        return result_container[0]
                    raise TimeoutError("Tool execution timeout")
                else:
                    return asyncio.run(coro)
            except RuntimeError:
                return asyncio.run(coro)

        return StructuredTool(
            name=self.name,
            description=self.description,
            func=sync_wrapper,
            coroutine=async_wrapper,
            args_schema=args_schema,
        )
