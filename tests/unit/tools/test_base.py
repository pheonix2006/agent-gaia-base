# tests/unit/tools/test_base.py
"""工具基类测试"""
import pytest
from langchain_core.tools import Tool


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


@pytest.mark.asyncio
async def test_concrete_tool_implementation():
    """测试具体工具实现"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class EchoTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Echo back the input"

        async def run(self, **kwargs) -> ToolResult:
            text = kwargs.get("text", "")
            return ToolResult(success=True, data=text)

    tool = EchoTool()
    assert tool.name == "echo"
    assert tool.description == "Echo back the input"

    result = await tool.run(text="hello")
    assert result.success is True
    assert result.data == "hello"


@pytest.mark.asyncio
async def test_tool_with_parameters():
    """测试工具参数定义"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class ToolWithParams(BaseAgentTool):
        @property
        def name(self) -> str:
            return "param_tool"

        @property
        def description(self) -> str:
            return "A tool with parameters"

        @property
        def parameters(self) -> dict:
            return {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                },
                "required": ["query"],
            }

        async def run(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=kwargs.get("query"))

    tool = ToolWithParams()
    assert tool.parameters["type"] == "object"
    assert "query" in tool.parameters["properties"]


def test_tool_to_langchain_conversion():
    """测试转换为 LangChain 工具"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class TestTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "test_tool"

        @property
        def description(self) -> str:
            return "A test tool"

        async def run(self, **kwargs) -> ToolResult:
            x = kwargs.get("x", "")
            return ToolResult(success=True, data=f"processed: {x}")

    tool = TestTool()
    lc_tool = tool.to_langchain_tool()

    assert isinstance(lc_tool, Tool)
    assert lc_tool.name == "test_tool"
    assert lc_tool.description == "A test tool"


def test_langchain_tool_execution():
    """测试 LangChain 工具执行（同步包装器）"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class TestTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "test_tool"

        @property
        def description(self) -> str:
            return "A test tool"

        async def run(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data="async result")

    tool = TestTool()
    lc_tool = tool.to_langchain_tool()

    # 同步调用异步工具
    result = lc_tool.func()
    assert result == "async result"
