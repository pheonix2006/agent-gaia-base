"""工具相关类型定义"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

from .common import AnyDict

# 泛型类型变量
P = TypeVar("P", bound=BaseModel)  # 参数类型
R = TypeVar("R")  # 返回类型


class ToolResult(BaseModel, Generic[R]):
    """泛型工具执行结果

    使用泛型支持不同工具指定返回类型。

    Example:
        class SearchParams(BaseModel):
            query: str

        class SearchTool(BaseAgentTool[SearchParams, list[str]]):
            async def run(self, params: SearchParams) -> ToolResult[list[str]]:
                ...
    """

    success: bool = Field(description="执行是否成功")
    data: R = Field(description="返回数据")
    error: str | None = Field(default=None, description="错误信息")
    metrics: AnyDict = Field(default_factory=dict, description="执行指标")


# 常用返回类型别名
ToolDataStr = ToolResult[str]
ToolDataDict = ToolResult[AnyDict]
ToolDataList = ToolResult[list[Any]]
