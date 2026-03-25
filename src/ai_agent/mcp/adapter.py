"""MCP 工具适配器：将 MCP 工具转换为 BaseAgentTool 接口。

提供以下功能：
- schema_to_params_model: 从 JSON Schema 动态创建 Pydantic 模型
- McpToolAdapter: MCP Tool → BaseAgentTool 适配器
- generate_skill_md: 自动生成 SKILL.md 文件
"""

import json
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, create_model

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types.tools import ToolResult


@runtime_checkable
class McpToolLike(Protocol):
    """MCP Tool 对象的最小协议。"""

    name: str
    description: str | None
    inputSchema: dict[str, Any]


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
            texts.append(str(item.text))
        elif isinstance(item, dict):
            texts.append(str(item.get("text", "")))
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
        description: str = prop_schema.get("description", "")

        if prop_name in required:
            fields[prop_name] = (python_type, Field(default=..., description=description))
        else:
            fields[prop_name] = (python_type | None, Field(default=None, description=description))

    model_name = f"{name}_Params"
    return create_model(model_name, __base__=BaseModel, **fields)


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
        mcp_tool: McpToolLike,
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
        return self._mcp_tool.description or ""

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
        try:
            call_result = await self._call_fn(self.name, params.model_dump())
            text = _extract_text_content(call_result.content)

            if call_result.isError:
                return ToolResult(success=False, data="", error=text)
            return ToolResult(success=True, data=text)
        except Exception as e:
            logger.error(
                "MCP 工具调用失败 [%s/%s]: %s", self._server_name, self.name, e
            )
            return ToolResult(success=False, data="", error=str(e))


# 需要在类定义后才能导入 logger（避免循环引用）
import logging
logger = logging.getLogger(__name__)

# description 文本解析：提取默认值和枚举值
_DEFAULT_PATTERN = re.compile(
    r"""default\s+(?:value\s+)?is\s+"""
    r"""(?:"([^"]+)"|'([^']+)'|([^\s.,;:]+))""",
    re.IGNORECASE,
)
_ENUM_PATTERN = re.compile(
    r"""Available\s+values\s*[:-]\s*(.*?)(?=\n\s*\n|\Z)""",
    re.IGNORECASE | re.DOTALL,
)
_ENUM_ITEM_PATTERN = re.compile(r"""-\s+([A-Za-z_][\w]*)""")


def _parse_default_from_desc(description: str) -> str | None:
    """从参数 description 文本中解析默认值。

    支持格式:
    - "default is 20"
    - "default is markdown"
    - "default is false"
    - 'default is "some value"'

    Args:
        description: 参数的 description 字符串。

    Returns:
        解析到的默认值字符串，或 None。
    """
    match = _DEFAULT_PATTERN.search(description)
    if not match:
        return None
    return match.group(1) or match.group(2) or match.group(3)


def _parse_enums_from_desc(description: str) -> list[str] | None:
    """从参数 description 文本中解析枚举值列表。

    支持格式:
    - "Available values: - oneDay - oneWeek - noLimit"
    - "Available values: cn, Chinese region - us, non-Chinese region"

    Args:
        description: 参数的 description 字符串。

    Returns:
        枚举值字符串列表，或 None。
    """
    match = _ENUM_PATTERN.search(description)
    if not match:
        return None
    block = match.group(1)
    items = _ENUM_ITEM_PATTERN.findall(block)
    return items if items else None


def generate_skill_md(
    server_name: str,
    mcp_tool: McpToolLike,
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
    description: str = mcp_tool.description or ""
    input_schema: dict[str, Any] = mcp_tool.inputSchema

    # action 名称中横线替换为下划线（匹配 ReActAgent._build_action_space 逻辑）
    action_name: str = tool_name.replace("-", "_")

    # 目录名保留原始名称
    tool_dir = output_dir / tool_name
    tool_dir.mkdir(parents=True, exist_ok=True)

    # 构建参数表格
    properties: dict[str, Any] = input_schema.get("properties", {})
    required: set[str] = set(input_schema.get("required", []))

    # 将参数分为必填和可选两组
    required_params: list[tuple[str, str, str, str, str]] = []
    optional_params: list[tuple[str, str, str, str, str]] = []
    enum_sections: list[str] = []
    default_values: dict[str, str] = {}

    for param_name, param_info in properties.items():
        param_type: str = param_info.get("type", "string")
        param_desc: str = param_info.get("description", "")
        is_required: bool = param_name in required
        is_required_str: str = "是" if is_required else "否"

        # 解析默认值
        default_val: str | None = _parse_default_from_desc(param_desc)
        default_str: str = f"`{default_val}`" if default_val else "-"

        # 解析枚举值
        enums: list[str] | None = _parse_enums_from_desc(param_desc)

        # 记录默认值用于示例 JSON
        if default_val:
            default_values[param_name] = default_val

        # 清理描述中的枚举和默认值部分，只保留纯描述
        clean_desc: str = _ENUM_PATTERN.sub("", param_desc).strip()
        clean_desc = _DEFAULT_PATTERN.sub("", clean_desc).strip()
        clean_desc = re.sub(r"\s*-.*", "", clean_desc, count=0).strip()
        # 取第一句话作为简洁描述
        if not clean_desc:
            clean_desc = param_desc.split(".")[0].strip()

        row = (param_name, param_type, is_required_str, default_str, clean_desc)

        if is_required:
            required_params.append(row)
        else:
            optional_params.append(row)

        # 有枚举值的参数补充枚举说明
        if enums:
            enum_items = ", ".join(f"`{v}`" for v in enums)
            enum_sections.append(f"**{param_name} 可选值：** {enum_items}")

    # 生成参数表格（5 列格式）
    table_header = "| 参数 | 类型 | 必填 | 默认值 | 说明 |"
    table_separator = "|------|------|------|--------|------|"

    def _build_table(rows: list[tuple[str, str, str, str, str]]) -> str:
        lines = [table_header, table_separator]
        for name, ptype, req, default, desc in rows:
            lines.append(f"| {name} | {ptype} | {req} | {default} | {desc} |")
        return "\n".join(lines)

    params_section_parts: list[str] = []
    if required_params:
        params_section_parts.append(f"### 必填参数\n\n{_build_table(required_params)}")
    if optional_params:
        params_section_parts.append(f"### 可选参数\n\n{_build_table(optional_params)}")

    if not params_section_parts:
        params_section = "无参数"
    else:
        params_section = "\n\n".join(params_section_parts)

    # 枚举值补充区域
    enum_block: str = ""
    if enum_sections:
        enum_block = "\n\n" + "\n".join(enum_sections)

    # 构建示例 JSON（有默认值的可选参数使用默认值）
    example_params: dict[str, Any] = {}
    for param_name in properties:
        if param_name in default_values:
            example_params[param_name] = default_values[param_name]
        else:
            example_params[param_name] = f"<{param_name}>"
    params_json: str = json.dumps(example_params, ensure_ascii=False, indent=4)
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

{params_section}{enum_block}

## 使用示例

```json
{example_json}
```
"""

    skill_path = tool_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")
    return skill_path
