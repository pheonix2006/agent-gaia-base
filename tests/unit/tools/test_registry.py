# tests/unit/tools/test_registry.py
"""工具注册中心测试"""
import pytest
from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.tools.registry import ToolRegistry


class MockTool(BaseAgentTool):
    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    def run(self, x: str) -> ToolResult:
        return ToolResult(success=True, data=x)


class AnotherTool(BaseAgentTool):
    @property
    def name(self) -> str:
        return "another_tool"

    @property
    def description(self) -> str:
        return "Another mock tool"

    def run(self, x: str) -> ToolResult:
        return ToolResult(success=True, data=x.upper())


@pytest.fixture(autouse=True)
def clear_registry():
    """每个测试前清空注册中心"""
    ToolRegistry._tools = {}
    yield
    ToolRegistry._tools = {}


def test_register_tool():
    """测试注册工具"""
    tool = MockTool()
    ToolRegistry.register(tool)

    assert "mock_tool" in ToolRegistry._tools
    assert ToolRegistry._tools["mock_tool"] == tool


def test_get_tool():
    """测试获取工具"""
    tool = MockTool()
    ToolRegistry.register(tool)

    retrieved = ToolRegistry.get("mock_tool")
    assert retrieved == tool


def test_get_nonexistent_tool():
    """测试获取不存在的工具"""
    retrieved = ToolRegistry.get("nonexistent")
    assert retrieved is None


def test_get_all_tools():
    """测试获取所有工具"""
    tool1 = MockTool()
    tool2 = AnotherTool()
    ToolRegistry.register(tool1)
    ToolRegistry.register(tool2)

    all_tools = ToolRegistry.get_all()
    assert len(all_tools) == 2
    assert tool1 in all_tools
    assert tool2 in all_tools


def test_get_langchain_tools():
    """测试获取 LangChain 格式的工具"""
    tool = MockTool()
    ToolRegistry.register(tool)

    lc_tools = ToolRegistry.get_langchain_tools()
    assert len(lc_tools) == 1
    assert lc_tools[0].name == "mock_tool"


def test_registry_is_singleton():
    """测试注册中心是单例"""
    r1 = ToolRegistry()
    r2 = ToolRegistry()
    assert r1 is r2
