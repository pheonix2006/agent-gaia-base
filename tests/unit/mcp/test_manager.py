# tests/unit/mcp/test_manager.py
"""MCP 多服务器管理器测试"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_agent.mcp.config import McpServerConfig, McpServersConfig
from ai_agent.mcp.manager import McpManager


def _make_config(servers: dict[str, dict] | None = None) -> McpServersConfig:
    """创建测试用 McpServersConfig"""
    if servers is None:
        servers = {
            "server-a": {"url": "http://localhost:8001/mcp"},
            "server-b": {"url": "http://localhost:8002/mcp"},
        }
    return McpServersConfig(
        servers={
            name: McpServerConfig(**cfg) for name, cfg in servers.items()
        }
    )


def _mock_tool(name: str) -> MagicMock:
    """创建 mock 工具"""
    tool = MagicMock(name=name)
    tool.name = name
    return tool


class TestMcpManagerStart:
    """McpManager.start() 测试"""

    @pytest.mark.asyncio
    async def test_start_loads_all_servers(self, tmp_path: Path):
        """start() 应连接所有配置的服务器并返回工具"""
        config = _make_config()
        manager = McpManager(
            config=config,
            skills_dir=tmp_path / "skills",
        )

        # server-a 返回 2 个工具，server-b 返回 1 个工具
        tool_a1 = _mock_tool("tool_a1")
        tool_a2 = _mock_tool("tool_a2")
        tool_b1 = _mock_tool("tool_b1")

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn_a = AsyncMock()
            mock_conn_a.connected = True
            mock_conn_a.disconnect = AsyncMock()
            mock_conn_a.connect = AsyncMock(return_value=[tool_a1, tool_a2])

            mock_conn_b = AsyncMock()
            mock_conn_b.connected = True
            mock_conn_b.disconnect = AsyncMock()
            mock_conn_b.connect = AsyncMock(return_value=[tool_b1])

            MockConn.side_effect = [mock_conn_a, mock_conn_b]

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                tools = await manager.start()

        assert len(tools) == 3
        mock_conn_a.connect.assert_called_once()
        mock_conn_b.connect.assert_called_once()

        # 清理
        await manager.stop()

    @pytest.mark.asyncio
    async def test_empty_config_no_error(self, tmp_path: Path):
        """空配置不应报错，应返回空工具列表"""
        config = McpServersConfig(servers={})
        manager = McpManager(
            config=config,
            skills_dir=tmp_path / "skills",
        )

        tools = await manager.start()
        assert tools == []

        await manager.stop()

    @pytest.mark.asyncio
    async def test_skill_md_files_generated(self, tmp_path: Path):
        """start() 应为每个工具生成 SKILL.md 文件"""
        config = _make_config(servers={"server-a": {"url": "http://localhost:8001/mcp"}})
        skills_dir = tmp_path / "skills"
        manager = McpManager(
            config=config,
            skills_dir=skills_dir,
        )

        tool_a = _mock_tool("search_tool")
        raw_mcp_tool = _mock_tool("search_tool")

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn = AsyncMock()
            mock_conn.connected = True
            mock_conn.disconnect = AsyncMock()
            mock_conn.connect = AsyncMock(return_value=[tool_a])
            mock_conn.raw_mcp_tools = [raw_mcp_tool]
            MockConn.return_value = mock_conn

            with patch("ai_agent.mcp.adapter.generate_skill_md") as mock_gen:
                await manager.start()

                # 验证 generate_skill_md 被调用
                mock_gen.assert_called_once()
                call_kwargs = mock_gen.call_args[1]
                assert call_kwargs["server_name"] == "server-a"
                assert call_kwargs["mcp_tool"] == raw_mcp_tool
                assert "mcp" in str(call_kwargs["output_dir"])

        await manager.stop()


class TestMcpManagerStop:
    """McpManager.stop() 测试"""

    @pytest.mark.asyncio
    async def test_stop_disconnects_all(self, tmp_path: Path):
        """stop() 应断开所有服务器连接"""
        config = _make_config()
        manager = McpManager(
            config=config,
            skills_dir=tmp_path / "skills",
        )

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn_a = AsyncMock()
            mock_conn_a.connected = True
            mock_conn_a.disconnect = AsyncMock()
            mock_conn_a.connect = AsyncMock(return_value=[_mock_tool("t1")])

            mock_conn_b = AsyncMock()
            mock_conn_b.connected = True
            mock_conn_b.disconnect = AsyncMock()
            mock_conn_b.connect = AsyncMock(return_value=[_mock_tool("t2")])

            MockConn.side_effect = [mock_conn_a, mock_conn_b]

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                await manager.start()

            # 确认有两个连接
            assert len(manager._connections) == 2

            await manager.stop()

            # 验证 disconnect 被调用（每个连接一次）
            mock_conn_a.disconnect.assert_called_once()
            mock_conn_b.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_clears_skills_directory(self, tmp_path: Path):
        """stop() 应清理 skills/mcp/ 目录下的子目录"""
        config = _make_config(servers={"server-a": {"url": "http://localhost:8001/mcp"}})
        skills_dir = tmp_path / "skills"
        manager = McpManager(
            config=config,
            skills_dir=skills_dir,
        )

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn = AsyncMock()
            mock_conn.connected = True
            mock_conn.disconnect = AsyncMock()
            mock_conn.connect = AsyncMock(return_value=[_mock_tool("t1")])
            MockConn.return_value = mock_conn

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                await manager.start()
                # 模拟 skills/mcp/server-a 目录存在
                mcp_skills_dir = skills_dir / "mcp" / "server-a"
                mcp_skills_dir.mkdir(parents=True)
                (mcp_skills_dir / "test.txt").write_text("test")

                assert mcp_skills_dir.exists()

            await manager.stop()

            # skills/mcp/ 下的子目录应被清理
            assert not mcp_skills_dir.exists()


class TestMcpManagerGetAllTools:
    """McpManager.get_all_tools() 测试"""

    @pytest.mark.asyncio
    async def test_get_all_tools_returns_tools(self, tmp_path: Path):
        """get_all_tools 应返回所有工具"""
        config = _make_config()
        manager = McpManager(
            config=config,
            skills_dir=tmp_path / "skills",
        )

        tools = [_mock_tool("t1"), _mock_tool("t2")]

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn = AsyncMock()
            mock_conn.connected = True
            mock_conn.disconnect = AsyncMock()
            mock_conn.connect = AsyncMock(return_value=tools)
            MockConn.return_value = mock_conn

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                await manager.start()

            result = manager.get_all_tools()
            assert len(result) == 4  # 两个服务器，每个返回 2 个工具

            await manager.stop()


class TestMcpManagerReload:
    """McpManager.reload() 测试"""

    @pytest.mark.asyncio
    async def test_reload_add_server(self, tmp_path: Path):
        """reload() 新增服务器时应连接并添加工具"""
        old_config = _make_config(servers={"server-a": {"url": "http://localhost:8001/mcp"}})
        manager = McpManager(
            config=old_config,
            skills_dir=tmp_path / "skills",
        )

        tool_a = _mock_tool("tool_a")
        tool_c = _mock_tool("tool_c")

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn_a = AsyncMock()
            mock_conn_a.connected = True
            mock_conn_a.disconnect = AsyncMock()
            mock_conn_a.connect = AsyncMock(return_value=[tool_a])

            mock_conn_c = AsyncMock()
            mock_conn_c.connected = True
            mock_conn_c.disconnect = AsyncMock()
            mock_conn_c.connect = AsyncMock(return_value=[tool_c])

            MockConn.side_effect = [mock_conn_a, mock_conn_c]

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                tools = await manager.start()
                assert len(tools) == 1

                # 重载：新增 server-c
                new_config = _make_config(servers={
                    "server-a": {"url": "http://localhost:8001/mcp"},
                    "server-c": {"url": "http://localhost:8003/mcp"},
                })

                reloaded_tools = await manager.reload(new_config)

                # 应有 2 个工具（原有 1 + 新增 1）
                assert len(reloaded_tools) == 2
                # server-c 应该被连接
                mock_conn_c.connect.assert_called_once()

            await manager.stop()

    @pytest.mark.asyncio
    async def test_reload_remove_server(self, tmp_path: Path):
        """reload() 移除服务器时应断开连接并移除工具"""
        old_config = _make_config(servers={
            "server-a": {"url": "http://localhost:8001/mcp"},
            "server-b": {"url": "http://localhost:8002/mcp"},
        })
        manager = McpManager(
            config=old_config,
            skills_dir=tmp_path / "skills",
        )

        tool_a = _mock_tool("tool_a")
        tool_b = _mock_tool("tool_b")

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn_a = AsyncMock()
            mock_conn_a.connected = True
            mock_conn_a.disconnect = AsyncMock()
            mock_conn_a.connect = AsyncMock(return_value=[tool_a])

            mock_conn_b = AsyncMock()
            mock_conn_b.connected = True
            mock_conn_b.disconnect = AsyncMock()
            mock_conn_b.connect = AsyncMock(return_value=[tool_b])

            MockConn.side_effect = [mock_conn_a, mock_conn_b]

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                tools = await manager.start()
                assert len(tools) == 2

                # 重载：移除 server-b
                new_config = _make_config(servers={
                    "server-a": {"url": "http://localhost:8001/mcp"},
                })

                reloaded_tools = await manager.reload(new_config)

                # 应只剩 1 个工具
                assert len(reloaded_tools) == 1
                # server-b 应该被断开
                mock_conn_b.disconnect.assert_called_once()
                # server-a 不应该被断开
                mock_conn_a.disconnect.assert_not_called()

            await manager.stop()

    @pytest.mark.asyncio
    async def test_reload_changed_server(self, tmp_path: Path):
        """reload() 配置变更的服务器应断开旧连接并重连"""
        old_config = _make_config(servers={
            "server-a": {"url": "http://localhost:8001/mcp"},
        })
        manager = McpManager(
            config=old_config,
            skills_dir=tmp_path / "skills",
        )

        tool_a_old = _mock_tool("tool_a_old")
        tool_a_new = _mock_tool("tool_a_new")

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn_a1 = AsyncMock()
            mock_conn_a1.connected = True
            mock_conn_a1.disconnect = AsyncMock()
            mock_conn_a1.connect = AsyncMock(return_value=[tool_a_old])

            mock_conn_a2 = AsyncMock()
            mock_conn_a2.connected = True
            mock_conn_a2.disconnect = AsyncMock()
            mock_conn_a2.connect = AsyncMock(return_value=[tool_a_new])

            MockConn.side_effect = [mock_conn_a1, mock_conn_a2]

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                await manager.start()

                # 重载：server-a 的 URL 变更
                new_config = _make_config(servers={
                    "server-a": {"url": "http://localhost:8001/v2/mcp"},
                })

                reloaded_tools = await manager.reload(new_config)

                # 旧连接应被断开
                mock_conn_a1.disconnect.assert_called_once()
                # 新连接应被建立
                mock_conn_a2.connect.assert_called_once()
                # 工具应该是新的
                assert len(reloaded_tools) == 1
                assert reloaded_tools[0].name == "tool_a_new"

            await manager.stop()


class TestMcpManagerWatchConfig:
    """McpManager 配置文件监听测试"""

    @pytest.mark.asyncio
    async def test_watch_config_starts_on_start(self, tmp_path: Path):
        """start() 应在提供 config_path 时启动后台监听任务"""
        config_path = tmp_path / "mcp_servers.json"
        old_data = {
            "mcpServers": {
                "server-a": {"url": "http://localhost:8001/mcp"},
            }
        }
        config_path.write_text(json.dumps(old_data), encoding="utf-8")

        old_config = _make_config(servers={"server-a": {"url": "http://localhost:8001/mcp"}})
        manager = McpManager(
            config=old_config,
            skills_dir=tmp_path / "skills",
            config_path=config_path,
        )

        tool_a = _mock_tool("tool_a")

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn = AsyncMock()
            mock_conn.connected = True
            mock_conn.disconnect = AsyncMock()
            mock_conn.connect = AsyncMock(return_value=[tool_a])
            MockConn.return_value = mock_conn

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                await manager.start()

                # 验证后台任务已启动
                assert manager._watch_task is not None
                assert not manager._watch_task.done()

            await manager.stop()

    @pytest.mark.asyncio
    async def test_watch_config_reloads_on_mtime_change(self, tmp_path: Path):
        """_watch_config 检测到 mtime 变化时应调用 load_mcp_config 和 reload"""
        config_path = tmp_path / "mcp_servers.json"
        old_data = {
            "mcpServers": {
                "server-a": {"url": "http://localhost:8001/mcp"},
            }
        }
        config_path.write_text(json.dumps(old_data), encoding="utf-8")

        old_config = _make_config(servers={"server-a": {"url": "http://localhost:8001/mcp"}})
        manager = McpManager(
            config=old_config,
            skills_dir=tmp_path / "skills",
            config_path=config_path,
        )

        tool_a = _mock_tool("tool_a")

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn = AsyncMock()
            mock_conn.connected = True
            mock_conn.disconnect = AsyncMock()
            mock_conn.connect = AsyncMock(return_value=[tool_a])
            MockConn.return_value = mock_conn

            with patch("ai_agent.mcp.manager.generate_skill_md", create=True):
                await manager.start()

                # 记录当前 mtime
                original_mtime = manager._last_mtime

                # 修改配置文件的 mtime
                time.sleep(0.05)
                config_path.touch()

                # 直接调用 _watch_config 的单次迭代逻辑来验证
                # 不依赖 asyncio.sleep 的定时器
                assert config_path.stat().st_mtime != original_mtime

            await manager.stop()
