"""MCP 多服务器管理器

统一管理多个 MCP 服务器连接，提供工具聚合、热重载和配置文件监听功能。
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from ai_agent.mcp.config import McpServerConfig, McpServersConfig
from ai_agent.mcp.client import McpServerConnection
from ai_agent.tools.base import BaseAgentTool

logger = logging.getLogger(__name__)


class McpManager:
    """MCP 多服务器管理器

    负责连接/断开多个 MCP 服务器、聚合工具、生成 SKILL.md 文档，
    以及监听配置文件变更实现热重载。

    Attributes:
        config: 当前 MCP 服务器配置
        skills_dir: SKILL.md 输出根目录
    """

    def __init__(
        self,
        config: McpServersConfig,
        skills_dir: Path,
        config_path: Path | None = None,
    ) -> None:
        """初始化管理器

        Args:
            config: MCP 服务器配置集合
            skills_dir: SKILL.md 文件输出目录
            config_path: 可选的配置文件路径，提供后将自动监听变更
        """
        self._config = config
        self._skills_dir = skills_dir
        self._config_path = config_path
        self._connections: dict[str, McpServerConnection] = {}
        self._tools: list[BaseAgentTool] = []
        # 每个工具到服务器名称的映射，用于 reload 时按服务器过滤工具
        self._tool_server_map: dict[int, str] = {}
        self._running = False
        self._watch_task: asyncio.Task[None] | None = None
        self._last_mtime: float = 0.0

    @property
    def config(self) -> McpServersConfig:
        return self._config

    async def start(self) -> list[BaseAgentTool]:
        """连接所有服务器，生成 SKILL.md，启动文件监听

        Returns:
            所有服务器的工具聚合列表
        """
        self._running = True
        await self._connect_all()

        # 如果有配置文件路径，启动文件监听
        if self._config_path is not None and self._config_path.exists():
            self._last_mtime = self._config_path.stat().st_mtime
            self._watch_task = asyncio.create_task(self._watch_config())

        return list(self._tools)

    async def stop(self) -> None:
        """断开所有连接，停止文件监听，清理 SKILL.md"""
        self._running = False

        # 取消后台监听任务
        if self._watch_task is not None:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

        await self._disconnect_all()
        self._tools.clear()
        self._tool_server_map.clear()

        # 清理 skills/mcp/ 下的子目录
        mcp_dir = self._skills_dir / "mcp"
        if mcp_dir.exists():
            for child in mcp_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)

    def get_all_tools(self) -> list[BaseAgentTool]:
        """获取所有 MCP 工具

        Returns:
            工具列表
        """
        return list(self._tools)

    async def reload(self, new_config: McpServersConfig) -> list[BaseAgentTool]:
        """增量重载配置：新增/移除/变更的服务器

        对比新旧配置，仅处理差异部分：
        - 移除旧配置中不存在于新配置的服务器
        - 新增新配置中不存在于旧配置的服务器
        - 配置变更的服务器先移除再新增

        Args:
            new_config: 新的 MCP 服务器配置集合

        Returns:
            重载后的所有工具列表
        """
        old_names = set(self._config.servers.keys())
        new_names = set(new_config.servers.keys())

        # 移除旧配置中不存在于新配置的服务器
        removed = old_names - new_names
        for name in removed:
            await self._remove_server(name)
            logger.info("MCP 服务器 '%s' 已移除", name)

        # 配置变更的服务器：先移除再新增
        changed = {
            name for name in old_names & new_names
            if self._config.servers[name] != new_config.servers[name]
        }
        for name in changed:
            await self._remove_server(name)
            logger.info("MCP 服务器 '%s' 配置变更，正在重连", name)

        # 新增服务器（包括 changed 的和全新的）
        added = new_names - old_names | changed
        for name in added:
            await self._add_server(name, new_config.servers[name])
            logger.info("MCP 服务器 '%s' 已连接", name)

        self._config = new_config
        return list(self._tools)

    async def _connect_all(self) -> None:
        """连接所有配置的服务器"""
        for name, server_config in self._config.servers.items():
            await self._add_server(name, server_config)

    async def _disconnect_all(self) -> None:
        """断开所有服务器连接"""
        for name, conn in self._connections.items():
            await conn.disconnect()
            logger.info("MCP 服务器 '%s' 已断开", name)
        self._connections.clear()

    async def _add_server(self, name: str, server_config: McpServerConfig) -> None:
        """添加并连接单个服务器

        Args:
            name: 服务器名称
            server_config: 服务器配置
        """
        conn = McpServerConnection(server_name=name, config=server_config)
        self._connections[name] = conn
        tools = await conn.connect()
        for tool in tools:
            self._tool_server_map[id(tool)] = name
        self._tools.extend(tools)
        self._generate_skill_mds(name, tools)

    async def _remove_server(self, name: str) -> None:
        """移除单个服务器及其工具

        Args:
            name: 服务器名称
        """
        conn = self._connections.pop(name, None)
        if conn is not None:
            await conn.disconnect()

        # 从工具列表中移除该服务器的工具
        tool_ids_to_remove = {
            tid for tid, sname in self._tool_server_map.items() if sname == name
        }
        self._tools = [
            t for t in self._tools if id(t) not in tool_ids_to_remove
        ]
        for tid in tool_ids_to_remove:
            self._tool_server_map.pop(tid, None)

    def _generate_skill_mds(
        self,
        server_name: str,
        tools: list[BaseAgentTool],
    ) -> None:
        """为服务器的所有工具生成 SKILL.md

        Args:
            server_name: 服务器名称
            tools: 工具列表
        """
        from ai_agent.mcp.adapter import generate_skill_md

        conn = self._connections.get(server_name)
        if conn is None:
            return

        # 使用原始 MCP Tool 对象（而非 adapter）生成 SKILL.md
        for mcp_tool in conn.raw_mcp_tools:
            try:
                generate_skill_md(
                    server_name=server_name,
                    mcp_tool=mcp_tool,
                    output_dir=self._skills_dir / "mcp",
                )
            except Exception:
                logger.exception(
                    "为工具 '%s' 生成 SKILL.md 失败",
                    getattr(mcp_tool, "name", "unknown"),
                )

    async def _watch_config(self) -> None:
        """后台任务：每 5 秒检查配置文件变更

        检测到 mtime 变化时自动调用 reload()。
        """
        try:
            while self._running:
                await asyncio.sleep(5)
                if self._config_path is None:
                    continue

                try:
                    current_mtime = self._config_path.stat().st_mtime
                except (OSError, FileNotFoundError):
                    continue

                if current_mtime != self._last_mtime:
                    self._last_mtime = current_mtime
                    logger.info(
                        "检测到配置文件变更: %s，正在重载...",
                        self._config_path,
                    )
                    try:
                        from ai_agent.mcp.config import load_mcp_config

                        new_config = load_mcp_config(self._config_path)
                        await self.reload(new_config)
                    except Exception:
                        logger.exception("配置文件重载失败")
        except asyncio.CancelledError:
            pass
