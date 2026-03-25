"""MCP 工具适配器单元测试"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_agent.mcp.adapter import (
    McpToolAdapter,
    _extract_text_content,
    generate_skill_md,
    schema_to_params_model,
)


class TestSchemaToParamsModel:
    """测试 schema_to_params_model 函数"""

    def test_simple_string_params(self) -> None:
        """测试简单的字符串参数"""
        schema = {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["q"],
        }
        model = schema_to_params_model("test_tool", schema)

        assert model.__name__ == "test_tool_Params"

        # 必填参数无默认值
        fields_info = model.model_fields
        assert "q" in fields_info
        assert fields_info["q"].is_required()

    def test_mixed_params(self) -> None:
        """测试混合必填和可选参数"""
        schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标 URL"},
                "count": {"type": "integer", "description": "返回数量"},
            },
            "required": ["url"],
        }
        model = schema_to_params_model("fetch_tool", schema)

        fields_info = model.model_fields
        assert fields_info["url"].is_required()
        assert not fields_info["count"].is_required()

        # 可选参数可以不传
        instance = model(url="https://example.com")
        assert instance.url == "https://example.com"
        assert instance.count is None

        # 可选参数可以传值
        instance2 = model(url="https://example.com", count=10)
        assert instance2.count == 10

    def test_empty_properties(self) -> None:
        """测试空属性的 schema"""
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        model = schema_to_params_model("empty_tool", schema)

        instance = model()
        assert model.__name__ == "empty_tool_Params"

    def test_json_schema_generation(self) -> None:
        """测试生成的模型能正确生成 JSON Schema"""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "score": {"type": "number"},
                "active": {"type": "boolean"},
                "tags": {"type": "array"},
                "metadata": {"type": "object"},
            },
            "required": ["name"],
        }
        model = schema_to_params_model("full_tool", schema)

        json_schema = model.model_json_schema()
        assert "properties" in json_schema
        props = json_schema["properties"]
        assert "name" in props
        assert "age" in props
        assert "score" in props
        assert "active" in props
        assert "tags" in props
        assert "metadata" in props


class TestMcpToolAdapter:
    """测试 McpToolAdapter 类"""

    def _make_mcp_tool(
        self,
        name: str = "test_tool",
        description: str = "A test tool",
        input_schema: dict | None = None,
    ) -> MagicMock:
        """创建 mock MCP Tool"""
        mcp_tool = MagicMock()
        mcp_tool.name = name
        mcp_tool.description = description
        mcp_tool.inputSchema = input_schema or {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        }
        return mcp_tool

    def test_name_and_description(self) -> None:
        """测试适配器的名称和描述属性"""
        mcp_tool = self._make_mcp_tool(
            name="search",
            description="Search the web",
        )
        call_fn = AsyncMock()
        adapter = McpToolAdapter(
            server_name="web_server",
            mcp_tool=mcp_tool,
            call_fn=call_fn,
        )

        assert adapter.name == "search"
        assert adapter.description == "Search the web"
        assert adapter.params_schema is not None

    @pytest.mark.asyncio
    async def test_run_success(self) -> None:
        """测试成功执行工具"""
        mcp_tool = self._make_mcp_tool()
        call_fn = AsyncMock()
        call_fn.return_value = MagicMock(
            content=[MagicMock(type="text", text="search result")],
            isError=False,
        )

        adapter = McpToolAdapter(
            server_name="test_server",
            mcp_tool=mcp_tool,
            call_fn=call_fn,
        )

        params = adapter.params_schema(q="hello")
        result = await adapter.run(params)

        assert result.success is True
        assert result.data == "search result"
        assert result.error is None
        call_fn.assert_called_once_with("test_tool", {"q": "hello"})

    @pytest.mark.asyncio
    async def test_run_error(self) -> None:
        """测试工具执行错误"""
        mcp_tool = self._make_mcp_tool()
        call_fn = AsyncMock()
        call_fn.return_value = MagicMock(
            content=[MagicMock(type="text", text="tool error occurred")],
            isError=True,
        )

        adapter = McpToolAdapter(
            server_name="test_server",
            mcp_tool=mcp_tool,
            call_fn=call_fn,
        )

        params = adapter.params_schema(q="test")
        result = await adapter.run(params)

        assert result.success is False
        assert result.data == ""
        assert result.error == "tool error occurred"

    def test_to_langchain_tool(self) -> None:
        """测试转换为 LangChain StructuredTool"""
        mcp_tool = self._make_mcp_tool()
        call_fn = AsyncMock()
        adapter = McpToolAdapter(
            server_name="test_server",
            mcp_tool=mcp_tool,
            call_fn=call_fn,
        )

        lc_tool = adapter.to_langchain_tool()
        assert lc_tool.name == "test_tool"
        assert lc_tool.description == "A test tool"
        assert lc_tool.args_schema is not None


class TestGenerateSkillMd:
    """测试 generate_skill_md 函数"""

    def test_basic_generation(self, tmp_path: Path) -> None:
        """测试基本 SKILL.md 生成"""
        mcp_tool = MagicMock()
        mcp_tool.name = "web_search"
        mcp_tool.description = "Search the web for information"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "结果数量"},
            },
            "required": ["query"],
        }

        result_path = generate_skill_md("search_server", mcp_tool, tmp_path)

        assert result_path.exists()
        assert result_path == tmp_path / "web_search" / "SKILL.md"

        content = result_path.read_text(encoding="utf-8")

        # 验证 frontmatter
        assert "---" in content
        assert "name: web_search" in content
        assert "description: Search the web for information" in content

        # 验证 action 名称
        assert '"action": web_search' in content

        # 验证参数表格（5 列格式）
        assert "query" in content
        assert "limit" in content
        assert "| 默认值 |" in content

    def test_enhanced_table_with_defaults_and_enums(self, tmp_path: Path) -> None:
        """测试增强模板：区分必填/选填、默认值列、枚举值"""
        mcp_tool = MagicMock()
        mcp_tool.name = "web_search_prime"
        mcp_tool.description = "Search web information."
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "Content to be searched",
                },
                "search_recency_filter": {
                    "type": "string",
                    "description": 'Time range. Available values:- oneDay, within one day- oneWeek, within one week- noLimit, no limit (default)',
                },
                "content_size": {
                    "type": "string",
                    "description": "Control summary size; default value is medium - medium: balanced, high: comprehensive",
                },
            },
            "required": ["search_query"],
        }

        result_path = generate_skill_md("search_server", mcp_tool, tmp_path)
        content = result_path.read_text(encoding="utf-8")

        # 应有两个表格标题：必填参数 + 可选参数
        assert "### 必填参数" in content
        assert "### 可选参数" in content

        # 表格应有 5 列：参数 | 类型 | 必填 | 默认值 | 说明
        assert "| 参数 | 类型 | 必填 | 默认值 | 说明 |" in content

        # 枚举值应出现在参数说明下方
        assert "search_recency_filter 可选值" in content
        assert "`oneDay`" in content
        assert "`noLimit`" in content

        # 默认值应出现在表格中
        assert "medium" in content

    def test_tool_name_with_dashes(self, tmp_path: Path) -> None:
        """测试带横线的工具名：目录保留原始名称，action 中横线替换为下划线"""
        mcp_tool = MagicMock()
        mcp_tool.name = "my-cool-tool"
        mcp_tool.description = "A cool tool with dashes"
        mcp_tool.inputSchema = {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入内容"},
            },
            "required": ["input"],
        }

        result_path = generate_skill_md("cool_server", mcp_tool, tmp_path)

        # 目录名保留原始名称（带横线）
        assert result_path == tmp_path / "my-cool-tool" / "SKILL.md"
        assert result_path.parent.name == "my-cool-tool"

        content = result_path.read_text(encoding="utf-8")

        # action 名称中横线替换为下划线
        assert '"action": my_cool_tool' in content
        # frontmatter 保留原始名称
        assert "name: my-cool-tool" in content

        # 验证 5 列表格格式
        assert "| 默认值 |" in content


class TestExtractTextContent:
    """测试 _extract_text_content 辅助函数"""

    def test_extract_from_objects_with_text_attr(self) -> None:
        """测试从具有 .text 属性的对象提取文本"""
        content = [
            MagicMock(type="text", text="line 1"),
            MagicMock(type="text", text="line 2"),
        ]
        result = _extract_text_content(content)
        assert result == "line 1\nline 2"

    def test_extract_from_dicts(self) -> None:
        """测试从字典中提取文本"""
        content = [
            {"type": "text", "text": "dict line 1"},
            {"type": "text", "text": "dict line 2"},
        ]
        result = _extract_text_content(content)
        assert result == "dict line 1\ndict line 2"

    def test_extract_empty(self) -> None:
        """测试空列表"""
        result = _extract_text_content([])
        assert result == ""


class TestParseDescriptionHints:
    """测试从参数 description 文本中解析默认值和枚举值"""

    def test_parse_default_simple(self) -> None:
        """简单 default 值提取"""
        from ai_agent.mcp.adapter import _parse_default_from_desc

        assert (
            _parse_default_from_desc(
                "Request timeout(unit is second), default is 20"
            )
            == "20"
        )

    def test_parse_default_with_quotes(self) -> None:
        """带引号的默认值"""
        from ai_agent.mcp.adapter import _parse_default_from_desc

        assert _parse_default_from_desc("default is markdown") == "markdown"

    def test_parse_default_none(self) -> None:
        """无默认值返回 None"""
        from ai_agent.mcp.adapter import _parse_default_from_desc

        assert _parse_default_from_desc("The URL of the website to fetch") is None

    def test_parse_enums_from_desc(self) -> None:
        """从 description 提取 Available values 枚举"""
        from ai_agent.mcp.adapter import _parse_enums_from_desc

        desc = (
            "Search within time range. Available values:- oneDay,"
            " within one day- oneWeek, within one week- oneYear,"
            " within one year- noLimit, no limit (default)"
        )
        result = _parse_enums_from_desc(desc)
        assert result == ["oneDay", "oneWeek", "oneYear", "noLimit"]

    def test_parse_enums_none(self) -> None:
        """无枚举值返回 None"""
        from ai_agent.mcp.adapter import _parse_enums_from_desc

        assert _parse_enums_from_desc("Just a plain description") is None

    def test_parse_default_false_bool(self) -> None:
        """布尔默认值"""
        from ai_agent.mcp.adapter import _parse_default_from_desc

        assert (
            _parse_default_from_desc("Disable cache(true/false), default is false")
            == "false"
        )

    def test_parse_default_with_value_keyword(self) -> None:
        """'default value is' 格式"""
        from ai_agent.mcp.adapter import _parse_default_from_desc

        assert (
            _parse_default_from_desc(
                "Control summary words; default value is medium"
            )
            == "medium"
        )
