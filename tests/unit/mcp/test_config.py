# tests/unit/mcp/test_config.py
"""MCP 配置加载模块测试"""

import json
import os
from pathlib import Path

import pytest


class TestMcpServerConfig:
    """McpServerConfig 模型测试"""

    def test_valid_streamable_http_config(self) -> None:
        """测试有效配置通过验证"""
        from ai_agent.mcp.config import McpServerConfig

        config = McpServerConfig(url="http://localhost:8080/mcp")
        assert config.type == "streamableHttp"
        assert config.url == "http://localhost:8080/mcp"

    def test_default_type_is_streamable_http(self) -> None:
        """测试默认 type 为 streamableHttp"""
        from ai_agent.mcp.config import McpServerConfig

        config = McpServerConfig(url="http://example.com/mcp")
        assert config.type == "streamableHttp"

    def test_headers_is_optional(self) -> None:
        """测试 headers 可选"""
        from ai_agent.mcp.config import McpServerConfig

        config = McpServerConfig(url="http://localhost:8080/mcp")
        assert config.headers is None

        config_with_headers = McpServerConfig(
            url="http://localhost:8080/mcp",
            headers={"Authorization": "Bearer test-token"},
        )
        assert config_with_headers.headers == {"Authorization": "Bearer test-token"}


class TestLoadMcpConfig:
    """load_mcp_config 函数测试"""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """测试加载有效 JSON 配置"""
        from ai_agent.mcp.config import load_mcp_config

        config_data = {
            "mcpServers": {
                "my-server": {
                    "type": "streamableHttp",
                    "url": "http://localhost:8080/mcp",
                }
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        result = load_mcp_config(config_file)
        assert "my-server" in result.servers
        assert result.servers["my-server"].url == "http://localhost:8080/mcp"
        assert result.servers["my-server"].type == "streamableHttp"

    def test_env_var_substitution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试 ${ENV_VAR} 环境变量替换"""
        monkeypatch.setenv("MCP_API_KEY", "secret-token")
        from ai_agent.mcp.config import load_mcp_config

        config_data = {
            "mcpServers": {
                "server-a": {
                    "url": "http://localhost:8080/mcp",
                    "headers": {
                        "Authorization": "Bearer ${MCP_API_KEY}",
                    },
                }
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        result = load_mcp_config(config_file)
        assert result.servers["server-a"].headers == {
            "Authorization": "Bearer secret-token",
        }

    def test_missing_env_var_raises(self, tmp_path: Path) -> None:
        """测试未定义的环境变量抛出 ValueError"""
        # 确保环境变量不存在
        os.environ.pop("UNDEFINED_MCP_VAR", None)
        from ai_agent.mcp.config import load_mcp_config

        config_data = {
            "mcpServers": {
                "server-b": {
                    "url": "http://localhost:8080/mcp",
                    "headers": {
                        "X-Custom": "${UNDEFINED_MCP_VAR}",
                    },
                }
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        with pytest.raises(ValueError, match="UNDEFINED_MCP_VAR"):
            load_mcp_config(config_file)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """测试文件不存在时抛出 FileNotFoundError"""
        from ai_agent.mcp.config import load_mcp_config

        nonexistent = tmp_path / "nonexistent_mcp.json"
        with pytest.raises(FileNotFoundError):
            load_mcp_config(nonexistent)

    def test_empty_servers(self, tmp_path: Path) -> None:
        """测试空的 mcpServers"""
        from ai_agent.mcp.config import load_mcp_config

        config_data = {"mcpServers": {}}
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        result = load_mcp_config(config_file)
        assert result.servers == {}

    def test_multiple_servers(self, tmp_path: Path) -> None:
        """测试多服务器配置"""
        from ai_agent.mcp.config import load_mcp_config

        config_data = {
            "mcpServers": {
                "server-a": {
                    "type": "streamableHttp",
                    "url": "http://localhost:8080/mcp",
                },
                "server-b": {
                    "type": "sse",
                    "url": "http://localhost:9090/mcp",
                    "headers": {"X-Token": "abc123"},
                },
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        result = load_mcp_config(config_file)
        assert len(result.servers) == 2
        assert result.servers["server-a"].url == "http://localhost:8080/mcp"
        assert result.servers["server-a"].type == "streamableHttp"
        assert result.servers["server-b"].url == "http://localhost:9090/mcp"
        assert result.servers["server-b"].type == "sse"
        assert result.servers["server-b"].headers == {"X-Token": "abc123"}
