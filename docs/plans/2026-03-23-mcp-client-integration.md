# MCP Client 集成实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 支持通过 `mcp_servers.json` 配置文件加载远程 MCP 服务器的工具，自动生成 SKILL.md 与现有 Skills 系统无缝融合，并支持配置热重载。

**Architecture:** 新增 `src/ai_agent/mcp/` 模块，使用官方 `mcp` Python SDK 的 `streamable_http_client` 连接远程服务器。每个 MCP 工具通过 `McpToolAdapter` 适配为 `BaseAgentTool`，同时自动生成 SKILL.md 文件到 `skills/mcp/` 目录，让现有 Skills 发现机制自动扫描。`McpManager` 管理多服务器生命周期，通过 mtime 轮询实现热重载。

**Tech Stack:** `mcp` (official Python SDK), `httpx`, `pydantic`, existing Skills system

---

## 前置知识

### 现有架构关键点

1. **工具基类** (`src/ai_agent/tools/base.py`): `BaseAgentTool[P, R]` 抽象基类，泛型参数为 Params 和 Result 的 Pydantic 模型。核心属性: `name`, `description`, `params_schema`, `run()`, `to_langchain_tool()`。

2. **Skills 系统** (`src/ai_agent/skills/`):
   - `discover_skills()` 扫描目录下的 SKILL.md 文件
   - `parse_skill_md()` 解析 YAML frontmatter (`name`, `description`) + Markdown body
   - `SkillCatalog` 管理 `list[SkillMeta]`，提供 `to_xml()` 生成 catalog prompt
   - Skills 目录: `skills/`，每个 skill 是一个子目录 + SKILL.md

3. **ReActAgent** (`src/ai_agent/agents/react/graph.py`):
   - Skills 模式: `_build_action_space()` 仅展示 SkillCatalog 中的 name + description
   - 工具执行: `_find_tool()` 在 `self.tools` (LangChain BaseTool) 中按名称查找
   - `self.tools` 是 LangChain `BaseTool` 列表，由 `BaseAgent.__init__` 设置

4. **集成入口** (`src/ai_agent/api/main.py`):
   - `lifespan()` 中创建内置工具 → `to_langchain_tool()` → 传给 `ReActAgent`
   - Skills 目录扫描 → `build_catalog_from_directory()` → `ReActPrompt.with_context()`
   - Agent 存储在 `app.state.agent`

### SKILL.md 格式

```markdown
---
name: skill-name
description: 简短描述，用于判断何时使用
---

# Skill 名称

详细说明。

## 何时使用
- 场景 1
- 场景 2

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| param1 | string | 是 | 描述 |

## 使用示例

```json
{
  "action": "tool_name",
  "params": {
    "param1": "value"
  }
}
```
```

### MCP SDK 关键 API

```python
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import httpx

# 带自定义 headers 的连接方式
http_client = httpx.AsyncClient(
    headers={"Authorization": "Bearer token"},
    timeout=30.0,
)
transport = streamable_http_client(url="https://...", http_client=http_client)

async with Client(transport) as client:
    tools = await client.list_tools()  # ListToolsResult
    result = await client.call_tool("tool_name", {"arg": "val"})  # CallToolResult
```

MCP Tool 结构: `Tool(name, description, inputSchema={...JSON Schema...})`
MCP Result 结构: `CallToolResult(content=[TextContent/ImageContent], isError=bool)`

---

## Task 1: 添加 mcp 依赖

**Files:**
- Modify: `pyproject.toml:7-21`

**Step 1: 添加 mcp 包到依赖**

在 `pyproject.toml` 的 `dependencies` 列表中添加 `mcp[cli]>=1.9.0`。

**Step 2: 安装依赖**

Run: `uv sync`
Expected: 成功安装 mcp 包

**Step 3: 验证导入**

Run: `uv run python -c "from mcp import Client; print('OK')"`
Expected: 输出 `OK`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add mcp SDK dependency for MCP client support"
```

---

## Task 2: 实现配置加载模块 `mcp/config.py`

**Files:**
- Create: `src/ai_agent/mcp/__init__.py`
- Create: `src/ai_agent/mcp/config.py`
- Test: `tests/unit/mcp/test_config.py`

**Step 1: 创建 `__init__.py`**

`src/ai_agent/mcp/__init__.py`:
```python
"""MCP (Model Context Protocol) 客户端集成模块。"""

from ai_agent.mcp.config import McpServerConfig, McpServersConfig, load_mcp_config

__all__ = ["McpServerConfig", "McpServersConfig", "load_mcp_config"]
```

**Step 2: 写失败测试**

`tests/unit/mcp/test_config.py`:
```python
"""MCP 配置加载单元测试。"""

import os
import tempfile
from pathlib import Path

import pytest

from ai_agent.mcp.config import McpServerConfig, McpServersConfig, load_mcp_config


class TestMcpServerConfig:
    """McpServerConfig 验证测试。"""

    def test_valid_streamable_http_config(self):
        """有效的 streamableHttp 配置应通过验证。"""
        config = McpServerConfig(
            type="streamableHttp",
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer token"},
        )
        assert config.type == "streamableHttp"
        assert config.url == "https://example.com/mcp"
        assert config.headers["Authorization"] == "Bearer token"

    def test_default_type_is_streamable_http(self):
        """未指定 type 时默认为 streamableHttp。"""
        config = McpServerConfig(url="https://example.com/mcp")
        assert config.type == "streamableHttp"

    def test_headers_is_optional(self):
        """headers 是可选字段。"""
        config = McpServerConfig(url="https://example.com/mcp")
        assert config.headers is None

    def test_invalid_type_raises(self):
        """无效的 type 应引发验证错误。"""
        with pytest.raises(Exception):
            McpServerConfig(type="websocket", url="https://example.com/mcp")


class TestLoadMcpConfig:
    """load_mcp_config 函数测试。"""

    def test_load_valid_config(self, tmp_path: Path):
        """加载有效的配置文件。"""
        config_file = tmp_path / "mcp_servers.json"
        config_file.write_text(
            '{"mcpServers": {"test": {"type": "streamableHttp", '
            '"url": "https://example.com/mcp"}}}',
            encoding="utf-8",
        )
        config = load_mcp_config(config_file)
        assert "test" in config.servers
        assert config.servers["test"].url == "https://example.com/mcp"

    def test_env_var_substitution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """支持 ${ENV_VAR} 环境变量替换。"""
        monkeypatch.setenv("TEST_API_KEY", "secret123")

        config_file = tmp_path / "mcp_servers.json"
        config_file.write_text(
            '{"mcpServers": {"test": {"url": "https://example.com/mcp", '
            '"headers": {"Authorization": "Bearer ${TEST_API_KEY}"}}}}',
            encoding="utf-8",
        )
        config = load_mcp_config(config_file)
        assert config.servers["test"].headers["Authorization"] == "Bearer secret123"

    def test_missing_env_var_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """引用未定义的环境变量应引发错误。"""
        monkeypatch.delenv("NONEXISTENT_KEY", raising=False)

        config_file = tmp_path / "mcp_servers.json"
        config_file.write_text(
            '{"mcpServers": {"test": {"url": "https://example.com/mcp", '
            '"headers": {"Auth": "${NONEXISTENT_KEY}"}}}}',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="NONEXISTENT_KEY"):
            load_mcp_config(config_file)

    def test_missing_file_raises(self, tmp_path: Path):
        """配置文件不存在应引发 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            load_mcp_config(tmp_path / "not_exist.json")

    def test_empty_servers(self, tmp_path: Path):
        """空 mcpServers 应返回空配置。"""
        config_file = tmp_path / "mcp_servers.json"
        config_file.write_text('{"mcpServers": {}}', encoding="utf-8")
        config = load_mcp_config(config_file)
        assert config.servers == {}

    def test_multiple_servers(self, tmp_path: Path):
        """加载多个服务器配置。"""
        config_file = tmp_path / "mcp_servers.json"
        config_file.write_text(
            '{"mcpServers": {'
            '"server1": {"url": "https://a.com/mcp"}, '
            '"server2": {"url": "https://b.com/mcp", "headers": {"X-Key": "val"}}'
            "}}",
            encoding="utf-8",
        )
        config = load_mcp_config(config_file)
        assert len(config.servers) == 2
        assert config.servers["server2"].headers["X-Key"] == "val"
```

**Step 3: 运行测试确认失败**

Run: `uv run pytest tests/unit/mcp/test_config.py -v`
Expected: FAIL — module not found

**Step 4: 实现 `mcp/config.py`**

`src/ai_agent/mcp/config.py`:
```python
"""MCP 服务器配置加载与解析。

支持 JSON 配置文件格式，兼容 Claude Desktop 的 mcpServers 配置规范。
支持 ${ENV_VAR} 环境变量引用。
"""

import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 环境变量引用正则: ${VAR_NAME}
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class McpServerConfig(BaseModel):
    """单个 MCP 服务器配置。

    Attributes:
        type: 传输协议类型，当前仅支持 streamableHttp
        url: MCP 服务器端点 URL
        headers: 可选的自定义 HTTP headers（支持 ${ENV_VAR} 引用）
    """

    type: str = Field(default="streamableHttp", description="传输协议类型")
    url: str = Field(description="MCP 服务器端点 URL")
    headers: dict[str, str] | None = Field(default=None, description="自定义 HTTP headers")


class McpServersConfig(BaseModel):
    """MCP 服务器配置集合。

    Attributes:
        servers: 服务器名称到配置的映射
    """

    servers: dict[str, McpServerConfig] = Field(
        default_factory=dict, description="MCP 服务器配置映射"
    )


def _substitute_env_vars(value: str) -> str:
    """替换字符串中的 ${ENV_VAR} 引用为实际环境变量值。

    Args:
        value: 包含 ${ENV_VAR} 引用的字符串

    Returns:
        替换后的字符串

    Raises:
        ValueError: 引用了未定义的环境变量
    """
    def _replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_val = os.environ.get(var_name)
        if env_val is None:
            raise ValueError(f"环境变量 '{var_name}' 未定义")
        return env_val

    # 需要导入 os
    import os
    return _ENV_VAR_PATTERN.sub(_replacer, value)


def _process_headers(headers: dict[str, str] | None) -> dict[str, str] | None:
    """处理 headers 中的环境变量引用。

    Args:
        headers: 原始 headers 字典

    Returns:
        处理后的 headers 字典

    Raises:
        ValueError: 引用了未定义的环境变量
    """
    if headers is None:
        return None
    return {k: _substitute_env_vars(v) for k, v in headers.items()}


def load_mcp_config(config_path: Path | str) -> McpServersConfig:
    """从 JSON 文件加载 MCP 服务器配置。

    配置文件格式:
    ```json
    {
        "mcpServers": {
            "server-name": {
                "type": "streamableHttp",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer ${API_KEY}"}
            }
        }
    }
    ```

    Args:
        config_path: JSON 配置文件路径

    Returns:
        McpServersConfig: 解析后的配置对象

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置格式错误或环境变量未定义
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"MCP 配置文件不存在: {config_path}")

    try:
        raw = config_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"MCP 配置文件 JSON 解析失败: {e}") from e

    servers_raw = data.get("mcpServers", {})

    servers: dict[str, McpServerConfig] = {}
    for name, server_data in servers_raw.items():
        # 处理 headers 中的环境变量引用
        if isinstance(server_data, dict) and "headers" in server_data:
            server_data["headers"] = _process_headers(server_data["headers"])
        servers[name] = McpServerConfig.model_validate(server_data)

    logger.info(f"已加载 {len(servers)} 个 MCP 服务器配置: {list(servers.keys())}")
    return McpServersConfig(servers=servers)
```

**Step 5: 运行测试确认通过**

Run: `uv run pytest tests/unit/mcp/test_config.py -v`
Expected: 7 passed

**Step 6: Commit**

```bash
git add src/ai_agent/mcp/__init__.py src/ai_agent/mcp/config.py tests/unit/mcp/test_config.py
git commit -m "feat(mcp): add config loading with env var substitution"
```

---

## Task 3: 实现 MCP 工具适配器 `mcp/adapter.py`

**Files:**
- Create: `src/ai_agent/mcp/adapter.py`
- Test: `tests/unit/mcp/test_adapter.py`

**Step 1: 写失败测试**

`tests/unit/mcp/test_adapter.py`:
```python
"""MCP 工具适配器单元测试。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_agent.mcp.adapter import (
    McpToolAdapter,
    generate_skill_md,
    schema_to_params_model,
)


class TestSchemaToParamsModel:
    """JSON Schema → Pydantic 模型转换测试。"""

    def test_simple_string_params(self):
        """简单字符串参数。"""
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        }
        model = schema_to_params_model("TestParams", schema)
        assert model.__name__ == "TestParams"
        instance = model(query="hello")
        assert instance.query == "hello"

    def test_mixed_params(self):
        """混合类型参数。"""
        schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL"},
                "count": {"type": "integer", "description": "数量"},
            },
            "required": ["url"],
        }
        model = schema_to_params_model("MixedParams", schema)
        instance = model(url="https://example.com")
        assert instance.url == "https://example.com"
        assert instance.count is None  # optional, default None

    def test_empty_properties(self):
        """无参数的 schema。"""
        schema = {"type": "object", "properties": {}, "required": []}
        model = schema_to_params_model("EmptyParams", schema)
        instance = model()
        assert instance is not None

    def test_json_schema_generation(self):
        """生成的模型能正确产生 JSON Schema。"""
        schema = {
            "type": "object",
            "properties": {"q": {"type": "string", "description": "查询词"}},
            "required": ["q"],
        }
        model = schema_to_params_model("QueryParams", schema)
        json_schema = model.model_json_schema()
        assert "q" in json_schema["properties"]


class TestMcpToolAdapter:
    """McpToolAdapter 测试。"""

    def test_name_and_description(self):
        """name 和 description 正确传递。"""
        mcp_tool = MagicMock()
        mcp_tool.name = "test_tool"
        mcp_tool.description = "A test tool"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        adapter = McpToolAdapter(
            server_name="test_server",
            mcp_tool=mcp_tool,
            call_fn=AsyncMock(return_value=MagicMock(
                content=[MagicMock(type="text", text="result")],
                isError=False,
            )),
        )
        assert adapter.name == "test_tool"
        assert adapter.description == "A test tool"

    @pytest.mark.asyncio
    async def test_run_success(self):
        """成功执行工具调用。"""
        mcp_tool = MagicMock()
        mcp_tool.name = "my_tool"
        mcp_tool.description = "desc"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {"arg1": {"type": "string"}},
            "required": ["arg1"],
        }

        call_fn = AsyncMock(return_value=MagicMock(
            content=[MagicMock(type="text", text="hello world")],
            isError=False,
        ))

        adapter = McpToolAdapter(
            server_name="srv",
            mcp_tool=mcp_tool,
            call_fn=call_fn,
        )

        result = await adapter.run(adapter.params_schema(arg1="test"))
        assert result.success is True
        assert result.data == "hello world"
        call_fn.assert_called_once_with("my_tool", {"arg1": "test"})

    @pytest.mark.asyncio
    async def test_run_error(self):
        """工具调用返回错误。"""
        mcp_tool = MagicMock()
        mcp_tool.name = "fail_tool"
        mcp_tool.description = "desc"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        call_fn = AsyncMock(return_value=MagicMock(
            content=[MagicMock(type="text", text="something went wrong")],
            isError=True,
        ))

        adapter = McpToolAdapter(
            server_name="srv",
            mcp_tool=mcp_tool,
            call_fn=call_fn,
        )

        result = await adapter.run(adapter.params_schema())
        assert result.success is False
        assert "something went wrong" in result.error

    def test_to_langchain_tool(self):
        """to_langchain_tool 返回可用的 StructuredTool。"""
        mcp_tool = MagicMock()
        mcp_tool.name = "lc_tool"
        mcp_tool.description = "desc"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        }

        adapter = McpToolAdapter(
            server_name="srv",
            mcp_tool=mcp_tool,
            call_fn=AsyncMock(),
        )

        lc_tool = adapter.to_langchain_tool()
        assert lc_tool.name == "lc_tool"


class TestGenerateSkillMd:
    """SKILL.md 自动生成测试。"""

    def test_basic_generation(self, tmp_path: Path):
        """基本 SKILL.md 生成。"""
        output_dir = tmp_path / "mcp_skills"
        output_dir.mkdir()

        mcp_tool = MagicMock()
        mcp_tool.name = "web_search"
        mcp_tool.description = "搜索互联网获取实时信息"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "count": {"type": "integer", "description": "返回结果数"},
            },
            "required": ["query"],
        }

        path = generate_skill_md(
            server_name="test_server",
            mcp_tool=mcp_tool,
            output_dir=output_dir,
        )

        assert path.exists()
        content = path.read_text(encoding="utf-8")

        # 验证 frontmatter
        assert "name: web_search" in content
        assert "description: 搜索互联网获取实时信息" in content

        # 验证 action 名称使用下划线格式
        assert '"action": "web_search"' in content

        # 验证参数说明
        assert "query" in content
        assert "count" in content

    def test_tool_name_with_dashes(self, tmp_path: Path):
        """工具名含连字符时，目录和 action 名称正确处理。"""
        output_dir = tmp_path / "mcp_skills"
        output_dir.mkdir()

        mcp_tool = MagicMock()
        mcp_tool.name = "my-cool-tool"
        mcp_tool.description = "A cool tool"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {"arg": {"type": "string"}},
            "required": ["arg"],
        }

        path = generate_skill_md(
            server_name="srv",
            mcp_tool=mcp_tool,
            output_dir=output_dir,
        )

        # 目录名使用原始名称
        assert path.parent.name == "my-cool-tool"
        # action 名使用下划线（匹配 _build_action_space 的转换逻辑）
        assert '"action": "my_cool_tool"' in path.read_text(encoding="utf-8")
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/mcp/test_adapter.py -v`
Expected: FAIL — module not found

**Step 3: 实现 `mcp/adapter.py`**

`src/ai_agent/mcp/adapter.py`:
```python
"""MCP 工具适配器：将 MCP 工具转换为 BaseAgentTool 并自动生成 SKILL.md。

关键设计：
- schema_to_params_model: 动态从 JSON Schema 创建 Pydantic 模型
- McpToolAdapter: 实现 BaseAgentTool 接口，封装 MCP 远程调用
- generate_skill_md: 从 MCP 工具元数据自动生成 SKILL.md 文件
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types.tools import ToolResult

logger = logging.getLogger(__name__)

# JSON Schema type → Python type 映射
_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def schema_to_params_model(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """从 JSON Schema 动态创建 Pydantic 模型。

    Args:
        name: 模型类名
        schema: JSON Schema 对象（必须包含 type=object + properties）

    Returns:
        动态创建的 Pydantic 模型类
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields: dict[str, tuple[type, Any]] = {}

    for prop_name, prop_def in properties.items():
        json_type = prop_def.get("type", "string")
        python_type = _JSON_TYPE_MAP.get(json_type, str)
        description = prop_def.get("description", "")

        if prop_name not in required:
            python_type = python_type | None

        default = ... if prop_name in required else None
        fields[prop_name] = (python_type, Field(default=default, description=description))

    return type(name, (BaseModel,), {
        "__annotations__": {k: v[0] for k, v in fields.items()},
        **{k: Field(v[1] if isinstance(v[1], Field) else v[1], default=v[1] if not isinstance(v[1], Field) else v[1].default, description=getattr(v[1], 'description', '') if isinstance(v[1], Field) else '')
           for k, v in fields.items()},
    })
```

等等，上面这种方式不太对。让我用 `pydantic.create_model` 更可靠：

```python
def schema_to_params_model(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """从 JSON Schema 动态创建 Pydantic 模型。"""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields: dict[str, Any] = {}

    for prop_name, prop_def in properties.items():
        json_type = prop_def.get("type", "string")
        python_type = _JSON_TYPE_MAP.get(json_type, str)
        description = prop_def.get("description", "")

        if prop_name not in required:
            python_type = python_type | None

        default = ... if prop_name in required else None
        fields[prop_name] = (python_type, Field(default=default, description=description))

    return pydantic.create_model(name, __base__=BaseModel, **fields)
```

完整的 `adapter.py`:

```python
"""MCP 工具适配器：将 MCP 工具转换为 BaseAgentTool 并自动生成 SKILL.md。"""

import json
import logging
from pathlib import Path
from typing import Any, Awaitable

from pydantic import BaseModel, Field, create_model

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types.tools import ToolResult

logger = logging.getLogger(__name__)

# JSON Schema type → Python type 映射
_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def schema_to_params_model(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """从 JSON Schema 动态创建 Pydantic 模型。

    Args:
        name: 模型类名
        schema: JSON Schema 对象

    Returns:
        动态创建的 Pydantic 模型类
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields: dict[str, Any] = {}

    for prop_name, prop_def in properties.items():
        json_type = prop_def.get("type", "string")
        python_type = _JSON_TYPE_MAP.get(json_type, str)
        description = prop_def.get("description", "")

        if prop_name not in required:
            python_type = python_type | None

        default = ... if prop_name in required else None
        fields[prop_name] = (python_type, Field(default=default, description=description))

    return create_model(name, __base__=BaseModel, **fields)


class McpToolAdapter(BaseAgentTool[BaseModel, str]):
    """将 MCP 工具适配为 BaseAgentTool。

    Attributes:
        server_name: MCP 服务器名称（用于日志和标识）
        _mcp_tool: 原始 MCP Tool 对象
        _call_fn: 异步调用函数，签名为 async (name, args) -> CallToolResult
    """

    def __init__(
        self,
        server_name: str,
        mcp_tool: Any,
        call_fn: Any,
    ) -> None:
        self._server_name = server_name
        self._mcp_tool = mcp_tool
        self._call_fn = call_fn

        # 从 MCP 工具的 inputSchema 动态创建参数模型
        schema = mcp_tool.inputSchema or {"type": "object", "properties": {}, "required": []}
        model_name = f"{mcp_tool.name.replace('-', '_').replace('.', '_')}_Params"
        self._params_model = schema_to_params_model(model_name, schema)

    @property
    def name(self) -> str:
        """工具名称（MCP 工具原始名称）。"""
        return self._mcp_tool.name

    @property
    def description(self) -> str:
        """工具描述。"""
        return self._mcp_tool.description or ""

    @property
    def params_schema(self) -> type[BaseModel]:
        """参数的 Pydantic 模型（动态生成）。"""
        return self._params_model

    async def run(self, params: BaseModel) -> ToolResult[str]:
        """执行 MCP 工具调用。

        Args:
            params: Pydantic 参数模型实例

        Returns:
            ToolResult 包含文本结果或错误信息
        """
        try:
            call_result = await self._call_fn(self.name, params.model_dump())

            if call_result.isError:
                error_text = _extract_text_content(call_result.content)
                return ToolResult(success=False, data="", error=error_text)

            text = _extract_text_content(call_result.content)
            return ToolResult(success=True, data=text)

        except Exception as e:
            logger.error(f"MCP 工具调用失败 [{self._server_name}/{self.name}]: {e}")
            return ToolResult(success=False, data="", error=str(e))


def _extract_text_content(content: list[Any]) -> str:
    """从 MCP CallToolResult.content 中提取文本。

    Args:
        content: MCP 内容列表

    Returns:
        合并后的文本字符串
    """
    texts: list[str] = []
    for item in content:
        if hasattr(item, "text"):
            texts.append(str(item.text))
        elif isinstance(item, dict) and item.get("type") == "text":
            texts.append(str(item.get("text", "")))
    return "\n".join(texts)


def generate_skill_md(
    server_name: str,
    mcp_tool: Any,
    output_dir: Path,
) -> Path:
    """为 MCP 工具自动生成 SKILL.md 文件。

    生成的文件符合现有 Skills 系统的 SKILL.md 格式规范，
    包含 YAML frontmatter 和参数说明。

    Args:
        server_name: MCP 服务器名称
        mcp_tool: MCP Tool 对象
        output_dir: 输出目录（skills/mcp/）

    Returns:
        生成的 SKILL.md 文件路径
    """
    tool_name = mcp_tool.name
    tool_desc = mcp_tool.description or ""
    schema = mcp_tool.inputSchema or {"type": "object", "properties": {}, "required": []}

    # action 名称使用下划线（匹配 ReActAgent._build_action_space 的转换逻辑）
    action_name = tool_name.replace("-", "_")

    # 构建 SKILL.md 内容
    lines: list[str] = []
    lines.append("---")
    lines.append(f"name: {tool_name}")
    lines.append(f"description: {tool_desc}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {tool_name}")
    lines.append("")
    lines.append(f"来源: MCP 服务器 `{server_name}`")
    lines.append("")
    lines.append(f"{tool_desc}")
    lines.append("")
    lines.append("## 参数说明")
    lines.append("")
    lines.append("| 参数 | 类型 | 必填 | 说明 |")
    lines.append("|------|------|------|------|")

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for prop_name, prop_def in properties.items():
        prop_type = prop_def.get("type", "string")
        is_required = "是" if prop_name in required else "否"
        prop_desc = prop_def.get("description", "")
        lines.append(f"| {prop_name} | {prop_type} | {is_required} | {prop_desc} |")

    lines.append("")
    lines.append("## 使用示例")
    lines.append("")
    lines.append("```json")

    if properties:
        # 生成包含所有 required 参数的示例
        example_params: dict[str, str] = {}
        for prop_name in properties:
            if prop_name in required:
                prop_type = properties[prop_name].get("type", "string")
                if prop_type == "string":
                    example_params[prop_name] = f"<{prop_name}>"
                elif prop_type == "integer":
                    example_params[prop_name] = 0
                elif prop_type == "number":
                    example_params[prop_name] = 0.0
                elif prop_type == "boolean":
                    example_params[prop_name] = True
                else:
                    example_params[prop_name] = f"<{prop_name}>"

        example = {"action": action_name, "params": example_params}
    else:
        example = {"action": action_name, "params": {}}

    lines.append(json.dumps(example, indent=2, ensure_ascii=False))
    lines.append("```")

    content = "\n".join(lines)

    # 写入文件：每个工具一个子目录
    tool_dir = output_dir / tool_name
    tool_dir.mkdir(parents=True, exist_ok=True)
    skill_md_path = tool_dir / "SKILL.md"
    skill_md_path.write_text(content, encoding="utf-8")

    logger.debug(f"已生成 SKILL.md: {skill_md_path}")
    return skill_md_path
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/mcp/test_adapter.py -v`
Expected: 全部通过

**Step 5: Commit**

```bash
git add src/ai_agent/mcp/adapter.py tests/unit/mcp/test_adapter.py
git commit -m "feat(mcp): add tool adapter with SKILL.md auto-generation"
```

---

## Task 4: 实现单服务器连接 `mcp/client.py`

**Files:**
- Create: `src/ai_agent/mcp/client.py`
- Test: `tests/unit/mcp/test_client.py`

**Step 1: 写失败测试**

`tests/unit/mcp/test_client.py`:
```python
"""MCP 服务器连接单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_agent.mcp.client import McpServerConnection
from ai_agent.mcp.config import McpServerConfig


class TestMcpServerConnection:
    """McpServerConnection 测试。"""

    def test_properties(self):
        """连接属性正确设置。"""
        config = McpServerConfig(
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer token123"},
        )
        conn = McpServerConnection(server_name="test", config=config)
        assert conn.server_name == "test"
        assert conn.connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """成功连接并获取工具列表。"""
        config = McpServerConfig(url="https://example.com/mcp")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        }
        mock_client.list_tools = AsyncMock(return_value=MagicMock(tools=[mock_tool]))

        with patch("ai_agent.mcp.client.Client", return_value=mock_client):
            conn = McpServerConnection(server_name="test", config=config)
            tools = await conn.connect()

        assert conn.connected is True
        assert len(tools) == 1
        assert tools[0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_connect_failure_graceful(self):
        """连接失败时优雅降级，不抛出异常。"""
        config = McpServerConfig(url="https://invalid.example.com/mcp")

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ai_agent.mcp.client.Client", return_value=mock_client):
            conn = McpServerConnection(server_name="test", config=config)
            tools = await conn.connect()

        assert conn.connected is False
        assert tools == []

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """断开连接清理状态。"""
        config = McpServerConfig(url="https://example.com/mcp")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=MagicMock(tools=[]))

        with patch("ai_agent.mcp.client.Client", return_value=mock_client):
            conn = McpServerConnection(server_name="test", config=config)
            await conn.connect()
            assert conn.connected is True

            await conn.disconnect()
            assert conn.connected is False

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """调用工具转发到 MCP 客户端。"""
        config = McpServerConfig(url="https://example.com/mcp")

        mock_result = MagicMock()
        mock_result.content = [MagicMock(type="text", text="result text")]
        mock_result.isError = False

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        with patch("ai_agent.mcp.client.Client", return_value=mock_client):
            conn = McpServerConnection(server_name="test", config=config)
            await conn.connect()

            result = await conn.call_tool("my_tool", {"arg": "val"})

        assert result.isError is False
        assert result.content[0].text == "result text"
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/mcp/test_client.py -v`
Expected: FAIL

**Step 3: 实现 `mcp/client.py`**

`src/ai_agent/mcp/client.py`:
```python
"""MCP 服务器连接管理。

封装官方 mcp.Client，管理单个 MCP 服务器的连接、工具发现和调用。
"""

import logging
from typing import Any

import httpx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from ai_agent.mcp.adapter import McpToolAdapter
from ai_agent.mcp.config import McpServerConfig
from ai_agent.tools.base import BaseAgentTool

logger = logging.getLogger(__name__)


class McpServerConnection:
    """管理单个 MCP 服务器的连接和工具。

    Attributes:
        server_name: 服务器名称（配置中的 key）
        config: 服务器配置
        connected: 是否已连接
    """

    def __init__(self, server_name: str, config: McpServerConfig) -> None:
        self.server_name = server_name
        self.config = config
        self._client: Client | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        """是否已成功连接。"""
        return self._connected

    async def connect(self) -> list[BaseAgentTool]:
        """连接 MCP 服务器并获取工具列表。

        Returns:
            适配后的工具列表。连接失败时返回空列表（优雅降级）。
        """
        try:
            transport = self._create_transport()
            client = Client(transport)

            self._client = await client.__aenter__()
            # initialize 由 Client.__aenter__ 自动调用

            tools_result = await self._client.list_tools()
            tools = self._create_tool_adapters(tools_result.tools)

            self._connected = True
            logger.info(
                f"MCP 服务器 [{self.server_name}] 连接成功，"
                f"发现 {len(tools)} 个工具: {[t.name for t in tools]}"
            )
            return tools

        except Exception as e:
            logger.error(f"MCP 服务器 [{self.server_name}] 连接失败: {e}")
            self._connected = False
            self._client = None
            return []

    async def disconnect(self) -> None:
        """断开 MCP 服务器连接。"""
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"MCP 服务器 [{self.server_name}] 断开连接异常: {e}")
            finally:
                self._client = None
                self._connected = False
                logger.info(f"MCP 服务器 [{self.server_name}] 已断开")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """调用 MCP 服务器上的工具。

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            MCP CallToolResult
        """
        if not self._connected or self._client is None:
            raise RuntimeError(f"MCP 服务器 [{self.server_name}] 未连接")

        return await self._client.call_tool(name, arguments)

    def _create_transport(self) -> Any:
        """创建 MCP transport。

        根据 headers 配置决定是否使用自定义 httpx.AsyncClient。
        """
        url = self.config.url
        headers = self.config.headers

        if headers:
            http_client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
            return streamable_http_client(url, http_client=http_client)

        return streamable_http_client(url)

    def _create_tool_adapters(self, mcp_tools: list[Any]) -> list[BaseAgentTool]:
        """将 MCP 工具列表转换为 BaseAgentTool 适配器。"""
        adapters: list[BaseAgentTool] = []
        for tool in mcp_tools:
            adapter = McpToolAdapter(
                server_name=self.server_name,
                mcp_tool=tool,
                call_fn=self.call_tool,
            )
            adapters.append(adapter)
        return adapters
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/mcp/test_client.py -v`
Expected: 全部通过

**Step 5: Commit**

```bash
git add src/ai_agent/mcp/client.py tests/unit/mcp/test_client.py
git commit -m "feat(mcp): add server connection with graceful degradation"
```

---

## Task 5: 实现多服务器管理器 `mcp/manager.py`

**Files:**
- Create: `src/ai_agent/mcp/manager.py`
- Test: `tests/unit/mcp/test_manager.py`

**Step 1: 写失败测试**

`tests/unit/mcp/test_manager.py`:
```python
"""MCP Manager 单元测试。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_agent.mcp.config import McpServersConfig, McpServerConfig
from ai_agent.mcp.manager import McpManager


class TestMcpManager:
    """McpManager 测试。"""

    def _make_config(self, servers: dict[str, McpServerConfig]) -> McpServersConfig:
        return McpServersConfig(servers=servers)

    @pytest.mark.asyncio
    async def test_start_loads_all_servers(self, tmp_path: Path):
        """启动时连接所有配置的服务器。"""
        config = self._make_config({
            "srv1": McpServerConfig(url="https://a.com/mcp"),
            "srv2": McpServerConfig(url="https://b.com/mcp"),
        })

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn1 = AsyncMock()
            mock_conn1.connect = AsyncMock(return_value=[
                MagicMock(name="tool1"), MagicMock(name="tool2"),
            ])
            mock_conn2 = AsyncMock()
            mock_conn2.connect = AsyncMock(return_value=[
                MagicMock(name="tool3"),
            ])
            MockConn.side_effect = [mock_conn1, mock_conn2]

            manager = McpManager(config=config, skills_dir=tmp_path / "skills")
            await manager.start()

        tools = manager.get_all_tools()
        assert len(tools) == 3

    @pytest.mark.asyncio
    async def test_stop_disconnects_all(self, tmp_path: Path):
        """停止时断开所有连接。"""
        config = self._make_config({
            "srv1": McpServerConfig(url="https://a.com/mcp"),
        })

        with patch("ai_agent.mcp.manager.McpServerConnection") as MockConn:
            mock_conn = AsyncMock()
            mock_conn.connect = AsyncMock(return_value=[])
            MockConn.return_value = mock_conn

            manager = McpManager(config=config, skills_dir=tmp_path / "skills")
            await manager.start()
            await manager.stop()

        mock_conn.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_config_no_error(self, tmp_path: Path):
        """空配置不报错。"""
        config = self._make_config({})

        manager = McpManager(config=config, skills_dir=tmp_path / "skills")
        await manager.start()

        assert manager.get_all_tools() == []

    def test_skill_md_files_generated(self, tmp_path: Path):
        """连接后应生成 SKILL.md 文件。"""
        skills_dir = tmp_path / "skills"
        config = self._make_config({
            "srv1": McpServerConfig(url="https://a.com/mcp"),
        })

        manager = McpManager(config=config, skills_dir=skills_dir)

        # 模拟已加载的工具
        mock_tool = MagicMock()
        mock_tool._mcp_tool = MagicMock()
        mock_tool._mcp_tool.name = "test_tool"
        mock_tool._mcp_tool.description = "Test"
        mock_tool._mcp_tool.inputSchema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        mcp_dir = skills_dir / "mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        from ai_agent.mcp.adapter import generate_skill_md
        generate_skill_md("srv1", mock_tool._mcp_tool, mcp_dir)

        assert (mcp_dir / "test_tool" / "SKILL.md").exists()
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/mcp/test_manager.py -v`
Expected: FAIL

**Step 3: 实现 `mcp/manager.py`**

`src/ai_agent/mcp/manager.py`:
```python
"""MCP 多服务器管理器。

负责：
- 启动时连接所有 MCP 服务器
- 为 MCP 工具自动生成 SKILL.md 到 skills/mcp/ 目录
- 后台监听配置文件变更实现热重载
- 提供统一的工具列表获取接口
"""

import asyncio
import logging
from pathlib import Path

from ai_agent.mcp.adapter import generate_skill_md
from ai_agent.mcp.client import McpServerConnection
from ai_agent.mcp.config import McpServersConfig
from ai_agent.tools.base import BaseAgentTool

logger = logging.getLogger(__name__)

# 配置文件轮询间隔（秒）
_POLL_INTERVAL = 5


class McpManager:
    """管理多个 MCP 服务器的连接生命周期。

    Attributes:
        config: MCP 服务器配置
        skills_dir: Skills 根目录（用于生成 SKILL.md）
    """

    def __init__(
        self,
        config: McpServersConfig,
        skills_dir: Path,
        config_path: Path | None = None,
    ) -> None:
        self._config = config
        self._skills_dir = skills_dir
        self._config_path = config_path
        self._connections: dict[str, McpServerConnection] = {}
        self._tools: list[BaseAgentTool] = []
        self._watch_task: asyncio.Task[None] | None = None
        self._running = False
        self._last_mtime: float = 0.0

    async def start(self) -> list[BaseAgentTool]:
        """启动：连接所有服务器，生成 SKILL.md，启动文件监听。

        Returns:
            所有 MCP 工具的列表
        """
        self._running = True
        await self._connect_all()

        # 启动配置文件监听（如果提供了配置路径）
        if self._config_path and self._config_path.exists():
            self._last_mtime = self._config_path.stat().st_mtime
            self._watch_task = asyncio.create_task(self._watch_config())

        return list(self._tools)

    async def stop(self) -> None:
        """停止：断开所有连接，停止文件监听。"""
        self._running = False

        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

        await self._disconnect_all()
        self._tools.clear()

        # 清理生成的 SKILL.md
        mcp_dir = self._skills_dir / "mcp"
        if mcp_dir.exists():
            for item in mcp_dir.iterdir():
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item, ignore_errors=True)

    def get_all_tools(self) -> list[BaseAgentTool]:
        """获取所有 MCP 工具。"""
        return list(self._tools)

    def get_all_skills_dir(self) -> Path:
        """获取 MCP Skills 目录路径（用于 Skills 发现）。"""
        return self._skills_dir / "mcp"

    async def reload(self, new_config: McpServersConfig) -> list[BaseAgentTool]:
        """重新加载配置（增量更新）。

        Args:
            new_config: 新的配置对象

        Returns:
            更新后的工具列表
        """
        old_names = set(self._connections.keys())
        new_names = set(new_config.servers.keys())

        # 移除不再存在的服务器
        for name in old_names - new_names:
            conn = self._connections.pop(name)
            await conn.disconnect()
            logger.info(f"MCP 热重载: 移除服务器 [{name}]")

        # 连接新增的服务器
        for name in new_names - old_names:
            server_config = new_config.servers[name]
            conn = McpServerConnection(server_name=name, config=server_config)
            tools = await conn.connect()
            if conn.connected:
                self._connections[name] = conn
                self._tools.extend(tools)
                self._generate_skill_mds(name, tools)
                logger.info(f"MCP 热重载: 新增服务器 [{name}]，{len(tools)} 个工具")

        # URL 或 headers 变更的服务器需要重连
        for name in old_names & new_names:
            old_conn = self._connections[name]
            new_server_config = new_config.servers[name]
            if (
                old_conn.config.url != new_server_config.url
                or old_conn.config.headers != new_server_config.headers
            ):
                # 移除旧工具
                self._tools = [t for t in self._tools if not (
                    hasattr(t, '_server_name') and t._server_name == name
                )]
                await old_conn.disconnect()

                # 重连
                conn = McpServerConnection(server_name=name, config=new_server_config)
                tools = await conn.connect()
                if conn.connected:
                    self._connections[name] = conn
                    self._tools.extend(tools)
                    self._generate_skill_mds(name, tools)
                    logger.info(f"MCP 热重载: 重连服务器 [{name}]")

        self._config = new_config
        return list(self._tools)

    async def _connect_all(self) -> None:
        """连接所有配置的服务器。"""
        mcp_dir = self._skills_dir / "mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        for name, server_config in self._config.servers.items():
            conn = McpServerConnection(server_name=name, config=server_config)
            tools = await conn.connect()

            if conn.connected:
                self._connections[name] = conn
                self._tools.extend(tools)
                self._generate_skill_mds(name, tools)

    async def _disconnect_all(self) -> None:
        """断开所有连接。"""
        for name, conn in self._connections.items():
            try:
                await conn.disconnect()
            except Exception as e:
                logger.warning(f"断开 [{name}] 时异常: {e}")
        self._connections.clear()

    def _generate_skill_mds(self, server_name: str, tools: list[BaseAgentTool]) -> None:
        """为指定服务器的所有工具生成 SKILL.md。"""
        mcp_dir = self._skills_dir / "mcp"
        for tool in tools:
            if hasattr(tool, '_mcp_tool'):
                try:
                    generate_skill_md(
                        server_name=server_name,
                        mcp_tool=tool._mcp_tool,
                        output_dir=mcp_dir,
                    )
                except Exception as e:
                    logger.warning(f"为工具 [{tool.name}] 生成 SKILL.md 失败: {e}")

    async def _watch_config(self) -> None:
        """后台任务：监听配置文件变更。"""
        while self._running:
            try:
                await asyncio.sleep(_POLL_INTERVAL)

                if self._config_path is None or not self._config_path.exists():
                    continue

                current_mtime = self._config_path.stat().st_mtime
                if current_mtime <= self._last_mtime:
                    continue

                self._last_mtime = current_mtime
                logger.info("检测到 MCP 配置文件变更，重新加载...")

                from ai_agent.mcp.config import load_mcp_config
                new_config = load_mcp_config(self._config_path)
                await self.reload(new_config)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"配置文件监听异常: {e}")
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/unit/mcp/test_manager.py -v`
Expected: 全部通过

**Step 5: Commit**

```bash
git add src/ai_agent/mcp/manager.py tests/unit/mcp/test_manager.py
git commit -m "feat(mcp): add multi-server manager with hot reload"
```

---

## Task 6: 集成到 lifespan

**Files:**
- Modify: `src/ai_agent/api/main.py:43-143`
- Modify: `src/ai_agent/agents/react/graph.py:89-117`

**Step 1: 为 ReActAgent 添加 `update_tools` 方法**

在 `src/ai_agent/agents/react/graph.py` 的 `ReActAgent` 类中添加方法：

```python
def update_tools(self, new_tools: list[BaseTool]) -> None:
    """更新工具列表（支持运行时热重载）。

    Args:
        new_tools: 新的 LangChain 工具列表
    """
    self.tools = new_tools
    logger.info(f"工具列表已更新: {len(new_tools)} 个工具")
```

添加位置：`__init__` 方法之后，`_build_graph` 之前。

**Step 2: 修改 `lifespan` 集成 MCP**

在 `src/ai_agent/api/main.py` 的 `lifespan` 函数中，在 Skills 目录扫描之后、创建 Agent 之前，添加 MCP 初始化：

```python
# === MCP 工具集成 ===
from ai_agent.mcp.config import load_mcp_config
from ai_agent.mcp.manager import McpManager

mcp_config_path = project_root / "mcp_servers.json"
mcp_manager: McpManager | None = None
mcp_tools: list[BaseAgentTool] = []

if mcp_config_path.exists():
    try:
        mcp_config = load_mcp_config(mcp_config_path)
        mcp_manager = McpManager(
            config=mcp_config,
            skills_dir=project_root / "skills",
            config_path=mcp_config_path,
        )
        mcp_tools = await mcp_manager.start()
        logger.info(f"MCP 已加载 {len(mcp_tools)} 个远程工具")
    except Exception as e:
        logger.warning(f"MCP 初始化失败（可选功能）: {e}")
        mcp_manager = None

app.state.mcp_manager = mcp_manager
```

然后修改工具合并部分：

```python
# 工具列表：内置 + MCP
tools: list[BaseAgentTool] = [
    search_tool,
    WebContentTool(),
    ImageAnalysisTool(),
    AudioParseTool(),
    ReadTool(),
] + mcp_tools
```

并在 lifespan 的 cleanup 部分（`yield` 之后）添加 MCP 清理：

```python
# MCP 清理
if mcp_manager:
    await mcp_manager.stop()
```

**Step 3: 验证启动无报错**

Run: `uv run python -c "from ai_agent.api.main import app; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add src/ai_agent/api/main.py src/ai_agent/agents/react/graph.py
git commit -m "feat(mcp): integrate MCP tools into lifespan with hot reload support"
```

---

## Task 7: 创建示例配置文件

**Files:**
- Create: `mcp_servers.json`

**Step 1: 创建配置文件**

`mcp_servers.json`:
```json
{
  "mcpServers": {
    "zread": {
      "type": "streamableHttp",
      "url": "https://open.bigmodel.cn/api/mcp/zread/mcp",
      "headers": {
        "Authorization": "Bearer ${OPENAI_API_KEY}"
      }
    }
  }
}
```

**Step 2: 添加到 .gitignore（可选）**

如果配置中包含敏感信息，可考虑在 `.gitignore` 中添加 `mcp_servers.json`。
但示例文件可以保留作为模板（不含真实 key）。

**Step 3: Commit**

```bash
git add mcp_servers.json
git commit -m "chore: add example mcp_servers.json config"
```

---

## Task 8: 全量测试与验证

**Step 1: 运行所有单元测试**

Run: `uv run pytest tests/unit -v`
Expected: 全部通过

**Step 2: 类型检查**

Run: `uv run mypy src/ai_agent/mcp --ignore-missing-imports`
Expected: 无错误

**Step 3: 手动验证（如需真实 API 测试）**

Run: `uv run python main.py`
Expected:
- 日志输出 "MCP 服务器 [zread] 连接成功"
- 日志输出 "MCP 已加载 N 个远程工具"
- `skills/mcp/` 目录下生成对应的 SKILL.md 文件
- Skills catalog 包含 MCP 工具

---

## 关键注意事项

1. **工具名称冲突**: MCP 工具与内置工具同名时，`_find_tool()` 返回第一个匹配。如需解决，可在 McpToolAdapter 的 name 中添加前缀（如 `mcp__tool_name`），但需要同步更新 SKILL.md 的 action 名。当前方案暂不处理，保持 KISS。

2. **SKILL.md 目录命名**: MCP 工具名称中的 `-` 和 `.` 保留在目录名中（如 `my-cool-tool/SKILL.md`），action 名使用 `_` 替换 `-`（与 ReActAgent._build_action_space 的转换逻辑一致）。

3. **热重载时 Skills Catalog**: 当前热重载只更新工具列表和 SKILL.md 文件，不自动更新已注入到 ReActPrompt 的 Catalog prompt。需要重启服务才能让新 MCP 工具出现在 Catalog 中。这是一个可接受的简化。

4. **连接失败不影响启动**: 所有 MCP 连接失败都是优雅降级，不影响内置工具和 Agent 正常运行。
