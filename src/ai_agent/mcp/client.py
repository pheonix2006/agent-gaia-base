"""MCP 服务器连接管理

提供与单个 MCP 服务器的连接、工具发现和工具调用功能。
连接失败时优雅降级，不会中断整体服务启动。
"""

from __future__ import annotations

import logging
from typing import Any, AsyncContextManager

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

from ai_agent.mcp.config import McpServerConfig
from ai_agent.tools.base import BaseAgentTool

logger = logging.getLogger(__name__)


class McpServerConnection:
    """管理到单个 MCP 服务器的连接

    负责建立连接、发现工具、调用工具以及断开连接。
    所有操作都具有容错性——连接失败时返回空工具列表。

    Attributes:
        server_name: 服务器名称标识
        config: 服务器连接配置
    """

    def __init__(self, server_name: str, config: McpServerConfig) -> None:
        self._server_name = server_name
        self._config = config
        self._connected = False
        self._session: ClientSession | None = None
        self._transport_cm: AsyncContextManager[Any] | None = None

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> list[BaseAgentTool]:
        """连接 MCP 服务器，获取工具列表

        使用 streamable HTTP transport 连接到配置的 MCP 服务器，
        初始化 session 后获取可用工具列表，并通过 McpToolAdapter
        将每个 MCP 工具包装为 BaseAgentTool。

        Session 在 connect() 返回后保持活跃状态，直到调用 disconnect()。

        Returns:
            包装后的工具列表，连接失败时返回空列表
        """
        try:
            # 创建自定义 httpx 客户端（如果配置了 headers）
            http_client: httpx.AsyncClient | None = None
            if self._config.headers:
                http_client = httpx.AsyncClient(headers=self._config.headers)

            # 建立传输层连接
            transport_cm = streamable_http_client(
                self._config.url,
                http_client=http_client,
            )
            read_stream, write_stream, _get_session_id = await transport_cm.__aenter__()
            self._transport_cm = transport_cm

            # 创建并启动 session（手动管理生命周期）
            session = ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            )
            await session.__aenter__()
            self._session = session

            await session.initialize()
            list_result = await session.list_tools()

            # 用 McpToolAdapter 包装每个工具
            from ai_agent.mcp.adapter import McpToolAdapter

            tools: list[BaseAgentTool] = []
            for mcp_tool in list_result.tools:
                adapter = McpToolAdapter(
                    server_name=self._server_name,
                    mcp_tool=mcp_tool,
                    call_fn=self.call_tool,
                )
                tools.append(adapter)

            self._connected = True

            logger.info(
                "MCP 服务器 '%s' 连接成功，发现 %d 个工具",
                self._server_name,
                len(tools),
            )
            return tools

        except Exception:
            logger.exception(
                "连接 MCP 服务器 '%s' 失败",
                self._server_name,
            )
            # 清理可能已部分创建的资源
            await self._cleanup()
            return []

    async def disconnect(self) -> None:
        """断开连接，清理状态

        关闭 session 和 transport 连接。
        """
        await self._cleanup()
        logger.info("MCP 服务器 '%s' 已断开", self._server_name)

    async def _cleanup(self) -> None:
        """清理 session 和 transport 资源"""
        self._connected = False

        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                logger.debug(
                    "清理 MCP session '%s' 时出错（可忽略）",
                    self._server_name,
                )
            self._session = None

        if self._transport_cm is not None:
            try:
                await self._transport_cm.__aexit__(None, None, None)
            except Exception:
                logger.debug(
                    "清理 MCP transport '%s' 时出错（可忽略）",
                    self._server_name,
                )
            self._transport_cm = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        """调用 MCP 工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            MCP 工具调用结果

        Raises:
            RuntimeError: 未连接到服务器时抛出
        """
        if not self._connected or self._session is None:
            raise RuntimeError(
                f"未连接到 MCP 服务器 '{self._server_name}'，无法调用工具 '{name}'"
            )
        return await self._session.call_tool(name, arguments)
