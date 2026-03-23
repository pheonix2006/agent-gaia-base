"""McpServerConnection 单元测试"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 如果 adapter 模块尚未被其他子 Agent 创建，
# 注册一个模拟模块以使 patch 工作
if "ai_agent.mcp.adapter" not in sys.modules:
    _adapter_mock = types.ModuleType("ai_agent.mcp.adapter")
    _adapter_mock.McpToolAdapter = MagicMock  # type: ignore[attr-defined]
    sys.modules["ai_agent.mcp.adapter"] = _adapter_mock

from ai_agent.mcp.client import McpServerConnection
from ai_agent.tools.base import BaseAgentTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(
    url: str = "http://localhost:8000",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """创建模拟的 McpServerConfig 对象。"""
    config = MagicMock()
    config.url = url
    config.headers = headers
    return config


def _make_mcp_tool(name: str = "test_tool") -> MagicMock:
    """创建模拟的 MCP Tool 对象。"""
    tool = MagicMock()
    tool.name = name
    tool.description = "A test tool"
    tool.inputSchema = {"type": "object", "properties": {}}
    return tool


def _make_transport_cm() -> AsyncMock:
    """创建模拟的 transport context manager，返回 3 个值。"""
    mock_transport_cm = AsyncMock()
    mock_transport_cm.__aenter__ = AsyncMock(
        return_value=(AsyncMock(), AsyncMock(), AsyncMock())
    )
    mock_transport_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_transport_cm


def _make_session(tools: list[MagicMock] | None = None) -> AsyncMock:
    """创建模拟的 ClientSession。"""
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(
        return_value=MagicMock(tools=tools or [])
    )
    return mock_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperties:
    """server_name 和 connected 初始值测试。"""

    def test_properties(self) -> None:
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        assert conn.server_name == "test-server"
        assert conn.connected is False


class TestConnectSuccess:
    """连接成功场景测试。"""

    async def test_connect_success(self) -> None:
        """连接 MCP 服务器成功，返回包装后的工具列表。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        mock_transport_cm = _make_transport_cm()
        mock_session = _make_session()
        mock_tool = _make_mcp_tool("search")
        mock_session.list_tools = AsyncMock(
            return_value=MagicMock(tools=[mock_tool])
        )

        with (
            patch(
                "ai_agent.mcp.client.streamable_http_client",
                return_value=mock_transport_cm,
            ),
            patch(
                "ai_agent.mcp.client.ClientSession",
                return_value=mock_session,
            ),
            patch(
                "ai_agent.mcp.adapter.McpToolAdapter",
                return_value=MagicMock(spec=BaseAgentTool),
            ) as mock_adapter_cls,
        ):
            tools = await conn.connect()

        # 验证返回了工具列表
        assert len(tools) == 1
        assert isinstance(tools[0], BaseAgentTool)

        # 验证 McpToolAdapter 被正确调用
        mock_adapter_cls.assert_called_once_with(
            server_name="test-server",
            mcp_tool=mock_tool,
            call_fn=conn.call_tool,
        )

        # 验证 connected 状态
        assert conn.connected is True

        # 验证 session 被正确初始化
        mock_session.initialize.assert_awaited_once()

    async def test_connect_success_with_headers(self) -> None:
        """连接时传递自定义 headers。"""
        config = _make_config(headers={"Authorization": "Bearer token123"})
        conn = McpServerConnection("test-server", config)

        mock_transport_cm = _make_transport_cm()
        mock_session = _make_session()

        with (
            patch(
                "ai_agent.mcp.client.streamable_http_client",
                return_value=mock_transport_cm,
            ) as mock_transport_fn,
            patch(
                "ai_agent.mcp.client.ClientSession",
                return_value=mock_session,
            ),
            patch("ai_agent.mcp.client.httpx"),
            patch(
                "ai_agent.mcp.adapter.McpToolAdapter",
                return_value=MagicMock(spec=BaseAgentTool),
            ),
        ):
            await conn.connect()

        # 验证 streamable_http_client 被调用
        mock_transport_fn.assert_called_once()
        call_args = mock_transport_fn.call_args
        assert call_args[0][0] == "http://localhost:8000"


class TestConnectFailure:
    """连接失败场景测试。"""

    async def test_connect_failure_graceful(self) -> None:
        """连接失败时优雅降级，返回空列表。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        mock_transport_cm = _make_transport_cm()
        mock_transport_cm.__aenter__ = AsyncMock(
            side_effect=ConnectionError("Connection refused")
        )

        with (
            patch(
                "ai_agent.mcp.client.streamable_http_client",
                return_value=mock_transport_cm,
            ),
            patch("ai_agent.mcp.client.ClientSession"),
        ):
            tools = await conn.connect()

        # 验证返回空列表
        assert tools == []
        assert conn.connected is False

    async def test_connect_failure_initialization_error(self) -> None:
        """session.initialize() 失败时优雅降级。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        mock_transport_cm = _make_transport_cm()
        mock_session = _make_session()
        mock_session.initialize = AsyncMock(side_effect=RuntimeError("Init failed"))

        with (
            patch(
                "ai_agent.mcp.client.streamable_http_client",
                return_value=mock_transport_cm,
            ),
            patch(
                "ai_agent.mcp.client.ClientSession",
                return_value=mock_session,
            ),
        ):
            tools = await conn.connect()

        assert tools == []
        assert conn.connected is False

    async def test_connect_failure_list_tools_error(self) -> None:
        """list_tools() 失败时优雅降级。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        mock_transport_cm = _make_transport_cm()
        mock_session = _make_session()
        mock_session.list_tools = AsyncMock(side_effect=RuntimeError("List failed"))

        with (
            patch(
                "ai_agent.mcp.client.streamable_http_client",
                return_value=mock_transport_cm,
            ),
            patch(
                "ai_agent.mcp.client.ClientSession",
                return_value=mock_session,
            ),
        ):
            tools = await conn.connect()

        assert tools == []
        assert conn.connected is False


class TestDisconnect:
    """断开连接测试。"""

    async def test_disconnect(self) -> None:
        """断开后 connected 应为 False。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        mock_transport_cm = _make_transport_cm()
        mock_session = _make_session()

        with (
            patch(
                "ai_agent.mcp.client.streamable_http_client",
                return_value=mock_transport_cm,
            ),
            patch(
                "ai_agent.mcp.client.ClientSession",
                return_value=mock_session,
            ),
            patch(
                "ai_agent.mcp.adapter.McpToolAdapter",
                return_value=MagicMock(spec=BaseAgentTool),
            ),
        ):
            await conn.connect()

        assert conn.connected is True

        # 断开连接
        await conn.disconnect()
        assert conn.connected is False

    async def test_disconnect_when_not_connected(self) -> None:
        """未连接时调用 disconnect 不应报错。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        await conn.disconnect()
        assert conn.connected is False


class TestCallTool:
    """工具调用测试。"""

    async def test_call_tool(self) -> None:
        """验证 call_tool 转发到 session.call_tool。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        mock_transport_cm = _make_transport_cm()
        mock_session = _make_session()

        with (
            patch(
                "ai_agent.mcp.client.streamable_http_client",
                return_value=mock_transport_cm,
            ),
            patch(
                "ai_agent.mcp.client.ClientSession",
                return_value=mock_session,
            ),
            patch(
                "ai_agent.mcp.adapter.McpToolAdapter",
                return_value=MagicMock(spec=BaseAgentTool),
            ),
        ):
            await conn.connect()

        # 调用工具
        mock_call_result = MagicMock()
        mock_call_result.content = [MagicMock(text="result")]
        mock_session.call_tool = AsyncMock(return_value=mock_call_result)

        result = await conn.call_tool("search", {"query": "test"})

        mock_session.call_tool.assert_awaited_once_with("search", {"query": "test"})
        assert result == mock_call_result

    async def test_call_tool_not_connected_raises(self) -> None:
        """未连接时调用 call_tool 应抛出 RuntimeError。"""
        config = _make_config()
        conn = McpServerConnection("test-server", config)

        with pytest.raises(RuntimeError, match="未连接"):
            await conn.call_tool("search", {"query": "test"})
