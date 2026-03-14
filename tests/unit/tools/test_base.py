# tests/unit/tools/test_base.py
"""工具基类测试"""
import pytest
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool


def test_tool_result_model():
    """测试工具结果模型"""
    from ai_agent.tools.base import ToolResult

    result = ToolResult(success=True, data="test data")
    assert result.success is True
    assert result.data == "test data"
    assert result.error is None

    error_result = ToolResult(success=False, data="", error="test error")
    assert error_result.success is False
    assert error_result.error == "test error"


def test_tool_result_with_complex_data():
    """测试工具结果支持复杂数据结构"""
    from ai_agent.tools.base import ToolResult

    # 支持字典数据
    dict_result = ToolResult(
        success=True,
        data={"key": "value", "nested": {"a": 1}},
        metrics={"duration_ms": 100, "tokens": 50},
    )
    assert dict_result.data["key"] == "value"
    assert dict_result.metrics["duration_ms"] == 100

    # 支持列表数据
    list_result = ToolResult(
        success=True,
        data=[1, 2, 3],
    )
    assert list_result.data == [1, 2, 3]


def test_base_agent_tool_is_abstract():
    """测试基类是抽象类"""
    from ai_agent.tools.base import BaseAgentTool

    with pytest.raises(TypeError):
        BaseAgentTool()


class EchoParams(BaseModel):
    text: str = Field(default="", description="输入文本")


@pytest.mark.asyncio
async def test_concrete_tool_implementation():
    """测试具体工具实现"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

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

    result = await tool.run(EchoParams(text="hello"))
    assert result.success is True
    assert result.data == "hello"


class ParamToolParams(BaseModel):
    query: str = Field(description="搜索查询")


@pytest.mark.asyncio
async def test_tool_with_parameters():
    """测试工具参数定义"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class ToolWithParams(BaseAgentTool[ParamToolParams, str]):
        @property
        def name(self) -> str:
            return "param_tool"

        @property
        def description(self) -> str:
            return "A tool with parameters"

        @property
        def params_schema(self) -> type[ParamToolParams]:
            return ParamToolParams

        async def run(self, params: ParamToolParams) -> ToolResult[str]:
            return ToolResult(success=True, data=params.query)

    tool = ToolWithParams()
    assert tool.parameters["type"] == "object"
    assert "query" in tool.parameters["properties"]


class SimpleInputParams(BaseModel):
    x: str = Field(default="", description="输入值")


def test_tool_to_langchain_conversion():
    """测试转换为 LangChain StructuredTool"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class TestTool(BaseAgentTool[SimpleInputParams, str]):
        @property
        def name(self) -> str:
            return "test_tool"

        @property
        def description(self) -> str:
            return "A test tool"

        @property
        def params_schema(self) -> type[SimpleInputParams]:
            return SimpleInputParams

        async def run(self, params: SimpleInputParams) -> ToolResult[str]:
            return ToolResult(success=True, data=f"processed: {params.x}")

    tool = TestTool()
    lc_tool = tool.to_langchain_tool()

    assert isinstance(lc_tool, StructuredTool)
    assert lc_tool.name == "test_tool"
    assert lc_tool.description == "A test tool"


class SimpleToolParams(BaseModel):
    pass


def test_langchain_tool_execution():
    """测试 LangChain StructuredTool 执行（同步包装器）"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class TestTool(BaseAgentTool[SimpleToolParams, str]):
        @property
        def name(self) -> str:
            return "test_tool"

        @property
        def description(self) -> str:
            return "A test tool"

        @property
        def params_schema(self) -> type[SimpleToolParams]:
            return SimpleToolParams

        async def run(self, params: SimpleToolParams) -> ToolResult[str]:
            return ToolResult(success=True, data="async result")

    tool = TestTool()
    lc_tool = tool.to_langchain_tool()

    # 同步调用异步工具（通过 ainvoke 或直接调用 func）
    result = lc_tool.func()
    assert result == "async result"


class ToolWithLimitParams(BaseModel):
    query: str = Field(description="搜索查询")
    limit: int = Field(default=10, description="结果数量限制")


def test_structured_tool_with_parameters():
    """测试 StructuredTool 正确保留参数 schema"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class ToolWithParams(BaseAgentTool[ToolWithLimitParams, dict]):
        @property
        def name(self) -> str:
            return "param_tool"

        @property
        def description(self) -> str:
            return "A tool with parameters"

        @property
        def params_schema(self) -> type[ToolWithLimitParams]:
            return ToolWithLimitParams

        async def run(self, params: ToolWithLimitParams) -> ToolResult[dict]:
            return ToolResult(success=True, data={"query": params.query, "limit": params.limit})

    tool = ToolWithParams()
    lc_tool = tool.to_langchain_tool()

    # 验证是 StructuredTool
    assert isinstance(lc_tool, StructuredTool)

    # 验证 args_schema 存在
    assert lc_tool.args_schema is not None

    # 验证参数 schema 包含正确的字段
    schema = lc_tool.get_input_jsonschema()
    assert "properties" in schema
    assert "query" in schema["properties"]
    assert "limit" in schema["properties"]
    assert "required" in schema
    assert "query" in schema["required"]

    # 验证参数描述被保留
    assert schema["properties"]["query"]["description"] == "搜索查询"
    assert schema["properties"]["limit"]["description"] == "结果数量限制"
