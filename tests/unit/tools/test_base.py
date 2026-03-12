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


def test_base_agent_tool_is_abstract():
    """测试基类是抽象类"""
    from ai_agent.tools.base import BaseAgentTool

    with pytest.raises(TypeError):
        BaseAgentTool()


def test_concrete_tool_implementation():
    """测试具体工具实现"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class EchoTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Echo back the input"

        def run(self, text: str) -> ToolResult:
            return ToolResult(success=True, data=text)

    tool = EchoTool()
    assert tool.name == "echo"
    assert tool.description == "Echo back the input"

    result = tool.run("hello")
    assert result.success is True
    assert result.data == "hello"


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

        def run(self, x: str) -> ToolResult:
            return ToolResult(success=True, data=f"processed: {x}")

    tool = TestTool()
    lc_tool = tool.to_langchain_tool()

    assert isinstance(lc_tool, Tool)
    assert lc_tool.name == "test_tool"
    assert lc_tool.description == "A test tool"
