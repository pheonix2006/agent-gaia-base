"""MCP 工具适配器：将 MCP 工具转换为 BaseAgentTool 接口。

提供以下功能：
- schema_to_params_model: 从 JSON Schema 动态创建 Pydantic 模型
- McpToolAdapter: MCP Tool → BaseAgentTool 适配器
- generate_skill_md: 自动生成 SKILL.md 文件
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types.tools import ToolResult


# JSON Schema 类型 → Python 类型映射
_JSON_TYPE_MAP: dict[str, type[Any]] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _extract_text_content(content: list[Any]) -> str:
    """从 MCP content 列表中提取文本内容。

    Args:
        content: MCP ToolResult.content 列表，每个元素可能为
            具有 .text 属性的对象，或包含 "text" 键的字典。

    Returns:
        拼接后的文本字符串，多个内容以换行分隔。
    """
    texts: list[str] = []
    for item in content:
        if hasattr(item, "text"):
            texts.append(item.text)
        elif isinstance(item, dict):
            texts.append(item.get("text", ""))
    return "\n".join(texts)


def schema_to_params_model(
    name: str,
    schema: dict[str, Any],
) -> type[BaseModel]:
    """从 JSON Schema 动态创建 Pydantic 模型。

    Args:
        name: 工具名称，用于生成模型类名。
        schema: JSON Schema 对象，包含 properties 和 required 字段。

    Returns:
        动态创建的 Pydantic 模型类。
    """
    properties: dict[str, Any] = schema.get("properties", {})
    required: set[str] = set(schema.get("required", []))

    fields: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        json_type: str = prop_schema.get("type", "string")
        python_type: type[Any] = _JSON_TYPE_MAP.get(json_type, str)

        if prop_name in required:
            fields[prop_name] = (python_type, ...)
        else:
            fields[prop_name] = (python_type | None, None)

    model_name = f"{name}_Params"
    return pydantic.create_model(model_name, **fields)  # type: ignore[return-value]


# 需要在函数外部 import pydantic 才能在 type annotation 中使用
import pydantic  # noqa: E402


class McpToolAdapter(BaseAgentTool[BaseModel, str]):
    """将 MCP 工具适配为 BaseAgentTool 接口。

    Args:
        server_name: MCP 服务器名称。
        mcp_tool: 原始 MCP Tool 对象，需具有 .name、.description、.inputSchema 属性。
        call_fn: 异步调用函数，签名为 async (name, args) -> CallToolResult。
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
        self._params_model: type[BaseModel] = schema_to_params_model(
            mcp_tool.name, mcp_tool.inputSchema
        )

    @property
    def name(self) -> str:
        """工具名称"""
        return self._mcp_tool.name

    @property
    def description(self) -> str:
        """工具描述"""
        return self._mcp_tool.description

    @property
    def params_schema(self) -> type[BaseModel]:
        """参数的 Pydantic 模型类"""
        return self._params_model

    async def run(self, params: BaseModel) -> ToolResult[str]:
        """执行 MCP 工具调用。

        Args:
            params: 参数模型实例。

        Returns:
            ToolResult 包含执行结果或错误信息。
        """
        call_result = await self._call_fn(self.name, params.model_dump())
        text = _extract_text_content(call_result.content)

        if call_result.isError:
            return ToolResult(success=False, data="", error=text)
        return ToolResult(success=True, data=text)


def generate_skill_md(
    server_name: str,
    mcp_tool: Any,
    output_dir: Path,
) -> Path:
    """为 MCP 工具自动生成 SKILL.md 文件。

    Args:
        server_name: MCP 服务器名称。
        mcp_tool: MCP Tool 对象，需具有 .name、.description、.inputSchema 属性。
        output_dir: SKILL.md 输出的根目录。

    Returns:
        生成的 SKILL.md 文件路径。
    """
    tool_name: str = mcp_tool.name
    description: str = mcp_tool.description
    input_schema: dict[str, Any] = mcp_tool.inputSchema

    # action 名称中横线替换为下划线（匹配 ReActAgent._build_action_space 逻辑）
    action_name: str = tool_name.replace("-", "_")

    # 目录名保留原始名称
    tool_dir = output_dir / tool_name
    tool_dir.mkdir(parents=True, exist_ok=True)

    # 构建参数表格
    properties: dict[str, Any] = input_schema.get("properties", {})
    required: set[str] = set(input_schema.get("required", []))

    param_rows: list[str] = []
    for param_name, param_info in properties.items():
        param_type: str = param_info.get("type", "string")
        is_required: str = "是" if param_name in required else "否"
        param_desc: str = param_info.get("description", "")
        param_rows.append(f"| {param_name} | {param_type} | {is_required} | {param_desc} |")

    params_table: str = "\n".join(param_rows) if param_rows else "无参数"

    # 构建示例 JSON（action 值不带引号，匹配 ReActAgent skill 格式）
    import json

    example_params: dict[str, Any] = {}
    for param_name in properties:
        example_params[param_name] = f"<{param_name}>"
    params_json: str = json.dumps(example_params, ensure_ascii=False, indent=4)
    # 缩进 params 使其与 action 对齐
    indented_params: str = "\n".join(
        "    " + line for line in params_json.splitlines()
    )
    example_json: str = (
        "{\n"
        f'    "action": {action_name},\n'
        f'    "params": {indented_params.lstrip()}\n'
        "}"
    )

    # 生成 SKILL.md 内容
    content: str = f"""\
---
name: {tool_name}
description: {description}
---

# {tool_name}

来源: MCP 服务器 `{server_name}`

{description}

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
{params_table}

## 使用示例

```json
{example_json}
```
"""

    skill_path = tool_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")
    return skill_path
