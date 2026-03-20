"""Edit 工具测试"""

import tempfile
from pathlib import Path

import pytest


class TestEditTool:
    """Edit 工具测试"""

    def test_edit_replace_success(self):
        """测试成功替换内容"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Hello World\nThis is a test\nGoodbye World")
            f.flush()

            tool = EditTool()
            result = tool.run_sync(EditParams(
                path=f.name,
                old_text="World",
                new_text="Python",
            ))

            assert result.success is True
            assert result.data["replacements"] == 2  # World 出现两次

            # 验证文件内容已更改
            content = Path(f.name).read_text(encoding="utf-8")
            assert "Hello Python" in content
            assert "Goodbye Python" in content
            assert "World" not in content

    def test_edit_single_replacement(self):
        """测试替换单个匹配"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("def old_function():\n    pass")
            f.flush()

            tool = EditTool()
            result = tool.run_sync(EditParams(
                path=f.name,
                old_text="old_function",
                new_text="new_function",
            ))

            assert result.success is True
            assert result.data["replacements"] == 1

            content = Path(f.name).read_text(encoding="utf-8")
            assert "def new_function():" in content

    def test_edit_multiline_text(self):
        """测试替换多行文本"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Header\n\nOld paragraph\nwith multiple\nlines\n\n## Footer")
            f.flush()

            tool = EditTool()
            old_text = "Old paragraph\nwith multiple\nlines"
            new_text = "New paragraph\nalso multiline"

            result = tool.run_sync(EditParams(
                path=f.name,
                old_text=old_text,
                new_text=new_text,
            ))

            assert result.success is True
            assert result.data["replacements"] == 1

            content = Path(f.name).read_text(encoding="utf-8")
            assert "New paragraph\nalso multiline" in content
            assert "Old paragraph" not in content

    def test_edit_text_not_found(self):
        """测试要替换的文本不存在"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Hello World")
            f.flush()

            tool = EditTool()
            result = tool.run_sync(EditParams(
                path=f.name,
                old_text="Python",
                new_text="Java",
            ))

            assert result.success is False
            assert "未找到" in result.error or "not found" in result.error.lower()

    def test_edit_file_not_found(self):
        """测试编辑不存在的文件"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        tool = EditTool()
        result = tool.run_sync(EditParams(
            path="/nonexistent/file/12345.txt",
            old_text="old",
            new_text="new",
        ))

        assert result.success is False
        assert "不存在" in result.error or "not found" in result.error.lower()

    def test_edit_path_is_directory(self):
        """测试编辑目录路径"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = EditTool()
            result = tool.run_sync(EditParams(
                path=tmpdir,
                old_text="old",
                new_text="new",
            ))

            assert result.success is False
            assert "不是文件" in result.error or "not a file" in result.error.lower()

    def test_edit_empty_old_text(self):
        """测试空 old_text 应该失败（Pydantic 验证）"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams
        from pydantic import ValidationError

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Some content")
            f.flush()

            tool = EditTool()
            # 空字符串应该在 Pydantic 验证阶段就被拒绝
            with pytest.raises(ValidationError) as exc_info:
                EditParams(
                    path=f.name,
                    old_text="",  # 空字符串应该被 Pydantic 拒绝
                    new_text="new",
                )

            # 验证错误信息包含 old_text 相关内容
            assert "old_text" in str(exc_info.value).lower() or "不能为空" in str(exc_info.value)

    def test_edit_preserve_encoding(self):
        """测试保留文件编码"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("你好世界\nHello World")
            f.flush()

            tool = EditTool()
            result = tool.run_sync(EditParams(
                path=f.name,
                old_text="你好",
                new_text="您好",
            ))

            assert result.success is True

            content = Path(f.name).read_text(encoding="utf-8")
            assert "您好世界" in content


class TestEditToolPermissions:
    """Edit 工具权限测试"""

    def test_edit_allowed_path(self):
        """测试编辑允许的路径"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams
        from ai_agent.tools.filesystem.permissions import PermissionManager, OperationType

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_dir = Path(tmpdir)
            test_file = allowed_dir / "test.txt"
            test_file.write_text("old content", encoding="utf-8")

            # 设置权限：允许编辑该目录
            pm = PermissionManager()
            pm.allow_path(allowed_dir, [OperationType.EDIT])

            tool = EditTool(permission_manager=pm)
            result = tool.run_sync(EditParams(
                path=str(test_file),
                old_text="old",
                new_text="new",
            ))

            assert result.success is True

    def test_edit_denied_path(self):
        """测试编辑禁止的路径"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams
        from ai_agent.tools.filesystem.permissions import PermissionManager, OperationType

        with tempfile.TemporaryDirectory() as tmpdir:
            denied_dir = Path(tmpdir) / "protected"
            denied_dir.mkdir()
            protected_file = denied_dir / "protected.txt"
            protected_file.write_text("secret content", encoding="utf-8")

            # 设置权限：禁止编辑该目录
            pm = PermissionManager()
            pm.deny_path(denied_dir, [OperationType.EDIT])

            tool = EditTool(permission_manager=pm)
            result = tool.run_sync(EditParams(
                path=str(protected_file),
                old_text="secret",
                new_text="public",
            ))

            assert result.success is False
            assert "权限" in result.error or "denied" in result.error.lower()

    def test_edit_read_only_permission(self):
        """测试只有读取权限，没有编辑权限"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams
        from ai_agent.tools.filesystem.permissions import PermissionManager, OperationType

        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            test_file = test_dir / "readonly.txt"
            test_file.write_text("readonly content", encoding="utf-8")

            # 设置权限：只允许读取
            pm = PermissionManager()
            pm.allow_path(test_dir, [OperationType.READ])
            pm.deny_path(test_dir, [OperationType.EDIT])

            tool = EditTool(permission_manager=pm)
            result = tool.run_sync(EditParams(
                path=str(test_file),
                old_text="readonly",
                new_text="writable",
            ))

            assert result.success is False


class TestEditToolIntegration:
    """Edit 工具与 LangChain 集成测试"""

    def test_to_langchain_tool(self):
        """测试转换为 LangChain 工具"""
        from ai_agent.tools.filesystem.edit import EditTool
        from langchain_core.tools import StructuredTool

        tool = EditTool()
        langchain_tool = tool.to_langchain_tool()

        assert isinstance(langchain_tool, StructuredTool)
        assert langchain_tool.name == "edit"

    def test_edit_params_schema(self):
        """测试参数 Schema 正确"""
        from ai_agent.tools.filesystem.edit import EditTool, EditParams

        tool = EditTool()
        schema = tool.parameters

        assert "path" in schema["properties"]
        assert "old_text" in schema["properties"]
        assert "new_text" in schema["properties"]
        assert "path" in schema["required"]
        assert "old_text" in schema["required"]
        assert "new_text" in schema["required"]
