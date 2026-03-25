"""MCP 配置加载模块

从 JSON 配置文件加载 MCP 服务器配置，支持环境变量替换。

配置文件格式示例::

    {
        "mcpServers": {
            "my-server": {
                "type": "streamableHttp",
                "url": "http://localhost:8080/mcp",
                "headers": {
                    "Authorization": "Bearer ${MY_API_KEY}"
                }
            }
        }
    }
"""

import json
import os
import re
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel

# 缓存项目根目录下的 .env 值（不覆盖已有的 os.environ）
_env_file_cache: dict[str, str] | None = None


def _ensure_env_cache(search_dir: Path) -> None:
    """确保 .env 缓存已初始化，从指定目录查找 .env 文件

    Args:
        search_dir: 搜索 .env 文件的目录
    """
    global _env_file_cache  # noqa: PLW0603
    if _env_file_cache is not None:
        return

    env_file = search_dir / ".env"
    if env_file.exists():
        _env_file_cache = {
            k: v for k, v in dotenv_values(env_file).items() if v is not None
        }
    else:
        # 回退到当前工作目录
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            _env_file_cache = {
                k: v for k, v in dotenv_values(cwd_env).items() if v is not None
            }
        else:
            _env_file_cache = {}


def _get_env_value(var_name: str) -> str | None:
    """从 os.environ 查找环境变量，找不到时回退到 .env 文件缓存

    Args:
        var_name: 环境变量名

    Returns:
        环境变量值，未找到则返回 None
    """
    # 优先使用 os.environ（已有值优先级最高）
    value = os.environ.get(var_name)
    if value is not None:
        return value

    # 回退到 .env 文件缓存
    if _env_file_cache is not None:
        return _env_file_cache.get(var_name)

    return None


class McpServerConfig(BaseModel):
    """单个 MCP 服务器配置

    Attributes:
        type: 传输协议类型，默认为 streamableHttp
        url: 服务器地址
        headers: 自定义请求头，可选
    """

    type: str = "streamableHttp"
    url: str
    headers: dict[str, str] | None = None


class McpServersConfig(BaseModel):
    """MCP 服务器配置集合

    Attributes:
        servers: 服务器名称到配置的映射
    """

    servers: dict[str, McpServerConfig]


def _substitute_env_vars(value: str) -> str:
    """替换字符串中的 ${ENV_VAR} 环境变量引用

    Args:
        value: 可能包含环境变量引用的字符串

    Returns:
        替换后的字符串

    Raises:
        ValueError: 引用的环境变量未定义时抛出
    """

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = _get_env_value(var_name)
        if env_value is None:
            raise ValueError(f"环境变量 '{var_name}' 未定义")
        return env_value

    return re.sub(r"\$\{([^}]+)\}", _replace, value)


def _process_headers(
    headers: dict[str, str] | None,
) -> dict[str, str] | None:
    """对 headers 中的值执行环境变量替换

    Args:
        headers: 原始 headers 字典

    Returns:
        替换后的 headers 字典，若输入为 None 则返回 None
    """
    if headers is None:
        return None
    return {key: _substitute_env_vars(value) for key, value in headers.items()}


def load_mcp_config(config_path: Path | str) -> McpServersConfig:
    """从 JSON 文件加载 MCP 配置

    读取 JSON 文件中的 ``mcpServers`` 字段，解析为配置模型。
    支持 headers 值中的 ``${ENV_VAR}`` 环境变量替换。

    Args:
        config_path: 配置文件路径

    Returns:
        解析后的 MCP 服务器配置集合

    Raises:
        FileNotFoundError: 配置文件不存在时抛出
        ValueError: JSON 解析失败或环境变量未定义时抛出
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"MCP 配置文件不存在: {path}")

    # 预热 .env 缓存：优先使用配置文件同级目录的 .env
    _ensure_env_cache(path.parent)

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"MCP 配置文件 JSON 解析失败: {exc}") from exc

    servers_data = data.get("mcpServers", {})
    processed_servers: dict[str, McpServerConfig] = {}

    for name, server_data in servers_data.items():
        if not isinstance(server_data, dict):
            raise ValueError(f"服务器 '{name}' 的配置必须是 JSON 对象")

        # 对 headers 进行环境变量替换
        headers = server_data.get("headers")
        server_data["headers"] = _process_headers(headers)

        processed_servers[name] = McpServerConfig(**server_data)

    return McpServersConfig(servers=processed_servers)
