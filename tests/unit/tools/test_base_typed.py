# tests/unit/tools/test_base_typed.py
"""测试泛型工具基类"""

import pytest
from pydantic import BaseModel, Field

from ai_agent.types import ToolResult


class SampleParams(BaseModel):
    """示例参数"""

    query: str = Field(description="查询字符串")
    limit: int = Field(default=10, ge=1, le=100)


def test_tool_result_generic():
    """测试 ToolResult 泛型"""
    result: ToolResult[str] = ToolResult(
        success=True,
        data="test output",
    )
    assert result.success is True
    assert result.data == "test output"


def test_tool_result_with_dict():
    """测试 ToolResult 返回字典"""
    result: ToolResult[dict[str, str]] = ToolResult(
        success=True,
        data={"key": "value"},
    )
    assert result.data["key"] == "value"


def test_tool_result_with_error():
    """测试 ToolResult 包含错误"""
    result: ToolResult[str] = ToolResult(
        success=False,
        data="",
        error="Something went wrong",
    )
    assert result.success is False
    assert result.error == "Something went wrong"


def test_tool_result_with_metrics():
    """测试 ToolResult 包含指标"""
    result: ToolResult[str] = ToolResult(
        success=True,
        data="test",
        metrics={"duration_ms": 100, "tokens": 50},
    )
    assert result.metrics["duration_ms"] == 100
    assert result.metrics["tokens"] == 50


def test_tool_result_with_list():
    """测试 ToolResult 返回列表"""
    result: ToolResult[list[int]] = ToolResult(
        success=True,
        data=[1, 2, 3],
    )
    assert result.data == [1, 2, 3]


def test_tool_result_with_complex_data():
    """测试 ToolResult 返回复杂数据结构"""
    result: ToolResult[dict[str, list[str]]] = ToolResult(
        success=True,
        data={"items": ["a", "b", "c"], "empty": []},
    )
    assert result.data["items"] == ["a", "b", "c"]
    assert result.data["empty"] == []


@pytest.mark.asyncio
async def test_base_agent_tool_generic():
    """测试泛型 BaseAgentTool"""
    from ai_agent.tools.base import BaseAgentTool

    class EchoParams(BaseModel):
        text: str = Field(description="要回显的文本")

    class EchoTool(BaseAgentTool[EchoParams, str]):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Echo back the input"

        @property
        def params_schema(self) -> type[EchoParams]:
            return EchoParams

        async def run(self, params: EchoParams) -> ToolResult[str]:
            return ToolResult(success=True, data=params.text)

    tool = EchoTool()
    assert tool.name == "echo"
    assert tool.description == "Echo back the input"
    assert tool.params_schema == EchoParams

    result = await tool.run(EchoParams(text="hello"))
    assert result.success is True
    assert result.data == "hello"


@pytest.mark.asyncio
async def test_base_agent_tool_params_schema_auto_parameters():
    """测试 params_schema 自动生成 parameters JSON Schema"""
    from ai_agent.tools.base import BaseAgentTool

    class SearchParams(BaseModel):
        query: str = Field(description="搜索查询")
        limit: int = Field(default=10, ge=1, le=100, description="结果数量限制")

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
            return ToolResult(success=True, data=[params.query])

    tool = SearchTool()

    # 验证 parameters 是从 params_schema 自动生成的 JSON Schema
    params = tool.parameters
    assert params["type"] == "object"
    assert "query" in params["properties"]
    assert "limit" in params["properties"]
    # 验证 description 被保留
    assert params["properties"]["query"]["description"] == "搜索查询"
    assert params["properties"]["limit"]["description"] == "结果数量限制"


@pytest.mark.asyncio
async def test_base_agent_tool_to_langchain():
    """测试泛型工具转换为 LangChain StructuredTool"""
    from langchain_core.tools import StructuredTool

    from ai_agent.tools.base import BaseAgentTool

    class AddParams(BaseModel):
        a: int = Field(description="第一个数")
        b: int = Field(description="第二个数")

    class AddTool(BaseAgentTool[AddParams, int]):
        @property
        def name(self) -> str:
            return "add"

        @property
        def description(self) -> str:
            return "Add two numbers"

        @property
        def params_schema(self) -> type[AddParams]:
            return AddParams

        async def run(self, params: AddParams) -> ToolResult[int]:
            return ToolResult(success=True, data=params.a + params.b)

    tool = AddTool()
    lc_tool = tool.to_langchain_tool()

    assert isinstance(lc_tool, StructuredTool)
    assert lc_tool.name == "add"
    assert lc_tool.description == "Add two numbers"

    # 验证 args_schema 正确
    assert lc_tool.args_schema is not None
    schema = lc_tool.get_input_jsonschema()
    assert "a" in schema["properties"]
    assert "b" in schema["properties"]


def test_base_agent_tool_langchain_execution():
    """测试 LangChain StructuredTool 执行（同步包装器）"""
    from ai_agent.tools.base import BaseAgentTool

    class UpperParams(BaseModel):
        text: str = Field(description="要转换的文本")

    class UpperTool(BaseAgentTool[UpperParams, str]):
        @property
        def name(self) -> str:
            return "upper"

        @property
        def description(self) -> str:
            return "Convert to uppercase"

        @property
        def params_schema(self) -> type[UpperParams]:
            return UpperParams

        async def run(self, params: UpperParams) -> ToolResult[str]:
            return ToolResult(success=True, data=params.text.upper())

    tool = UpperTool()
    lc_tool = tool.to_langchain_tool()

    # 同步调用
    result = lc_tool.func(text="hello")
    assert result == "HELLO"


def test_base_agent_tool_langchain_with_optional_params():
    """测试 LangChain StructuredTool 执行带可选参数"""
    from ai_agent.tools.base import BaseAgentTool

    class GreetParams(BaseModel):
        name: str = Field(description="名字")
        greeting: str = Field(default="Hello", description="问候语")

    class GreetTool(BaseAgentTool[GreetParams, str]):
        @property
        def name(self) -> str:
            return "greet"

        @property
        def description(self) -> str:
            return "Greet someone"

        @property
        def params_schema(self) -> type[GreetParams]:
            return GreetParams

        async def run(self, params: GreetParams) -> ToolResult[str]:
            return ToolResult(success=True, data=f"{params.greeting}, {params.name}!")

    tool = GreetTool()
    lc_tool = tool.to_langchain_tool()

    # 使用默认值
    result = lc_tool.func(name="World")
    assert result == "Hello, World!"

    # 指定可选参数
    result = lc_tool.func(name="Alice", greeting="Hi")
    assert result == "Hi, Alice!"


@pytest.mark.asyncio
async def test_base_agent_tool_error_handling():
    """测试工具错误处理"""
    from ai_agent.tools.base import BaseAgentTool

    class DivideParams(BaseModel):
        a: float = Field(description="被除数")
        b: float = Field(description="除数")

    class DivideTool(BaseAgentTool[DivideParams, float]):
        @property
        def name(self) -> str:
            return "divide"

        @property
        def description(self) -> str:
            return "Divide two numbers"

        @property
        def params_schema(self) -> type[DivideParams]:
            return DivideParams

        async def run(self, params: DivideParams) -> ToolResult[float]:
            if params.b == 0:
                return ToolResult(success=False, data=0.0, error="Division by zero")
            return ToolResult(success=True, data=params.a / params.b)

    tool = DivideTool()

    # 正常情况
    result = await tool.run(DivideParams(a=10, b=2))
    assert result.success is True
    assert result.data == 5.0

    # 错误情况
    result = await tool.run(DivideParams(a=10, b=0))
    assert result.success is False
    assert result.error == "Division by zero"


def test_base_agent_tool_langchain_error_result():
    """测试 LangChain StructuredTool 返回错误信息"""
    from ai_agent.tools.base import BaseAgentTool

    class FailParams(BaseModel):
        pass

    class FailTool(BaseAgentTool[FailParams, str]):
        @property
        def name(self) -> str:
            return "fail"

        @property
        def description(self) -> str:
            return "Always fails"

        @property
        def params_schema(self) -> type[FailParams]:
            return FailParams

        async def run(self, params: FailParams) -> ToolResult[str]:
            return ToolResult(success=False, data="", error="Intentional failure")

    tool = FailTool()
    lc_tool = tool.to_langchain_tool()

    result = lc_tool.func()
    assert "Error: Intentional failure" == result
