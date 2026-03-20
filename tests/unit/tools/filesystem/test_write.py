"""Write 工具测试"""

import tempfile
from pathlib import Path

import pytest


class TestWriteTool:
    """Write 工具测试"""

    def test_write_file_success(self):
        """测试成功写入文件"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"

            tool = WriteTool()
            result = tool.run_sync(
                WriteParams(path=str(test_file), content="# Hello World")
            )

            assert result.success is True
            assert result.data["bytes_written"] == len("# Hello World".encode("utf-8"))
            assert test_file.read_text(encoding="utf-8") == "# Hello World"

    def test_write_file_with_mode_append(self):
        """测试追加模式写入"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Line 1\n", encoding="utf-8")

            tool = WriteTool()
            result = tool.run_sync(
                WriteParams(
                    path=str(test_file), content="Line 2\n", mode="a"
                )
            )

            assert result.success is True
            assert test_file.read_text(encoding="utf-8") == "Line 1\nLine 2\n"

    def test_write_creates_parent_directories(self):
        """测试自动创建父目录"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams

        with tempfile.TemporaryDirectory() as tmpdir:
            # 嵌套目录，父目录不存在
            test_file = Path(tmpdir) / "sub1" / "sub2" / "test.md"

            tool = WriteTool()
            result = tool.run_sync(
                WriteParams(path=str(test_file), content="nested content")
            )

            assert result.success is True
            assert test_file.read_text(encoding="utf-8") == "nested content"
            assert test_file.parent.exists()

    def test_write_overwrites_existing_file(self):
        """测试覆盖写入已存在的文件"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "existing.txt"
            test_file.write_text("old content", encoding="utf-8")

            tool = WriteTool()
            result = tool.run_sync(
                WriteParams(path=str(test_file), content="new content")
            )

            assert result.success is True
            assert test_file.read_text(encoding="utf-8") == "new content"

    def test_write_returns_bytes_written(self):
        """测试返回写入的字节数"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "bytes.txt"
            content = "Hello, 世界!"  # 包含中文

            tool = WriteTool()
            result = tool.run_sync(
                WriteParams(path=str(test_file), content=content)
            )

            assert result.success is True
            expected_bytes = len(content.encode("utf-8"))
            assert result.data["bytes_written"] == expected_bytes

    def test_write_invalid_mode(self):
        """测试无效的写入模式"""
        from ai_agent.tools.filesystem.write import WriteParams
        from pydantic import ValidationError

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"

            # Pydantic 在参数构造时就会验证模式
            with pytest.raises(ValidationError) as exc_info:
                WriteParams(path=str(test_file), content="test", mode="x")

            assert "mode" in str(exc_info.value).lower()


class TestWriteToolPermissions:
    """Write 工具权限测试"""

    def test_write_allowed_path(self):
        """测试写入允许的路径"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams
        from ai_agent.tools.filesystem.permissions import (
            PermissionManager,
            OperationType,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_dir = Path(tmpdir)
            test_file = allowed_dir / "test.md"

            # 设置权限：允许写入该目录
            pm = PermissionManager()
            pm.allow_path(allowed_dir, [OperationType.WRITE])

            tool = WriteTool(permission_manager=pm)
            result = tool.run_sync(
                WriteParams(path=str(test_file), content="content")
            )

            assert result.success is True

    def test_write_denied_path(self):
        """测试写入禁止的路径"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams
        from ai_agent.tools.filesystem.permissions import (
            PermissionManager,
            OperationType,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            denied_dir = Path(tmpdir) / "protected"
            denied_dir.mkdir()
            test_file = denied_dir / "secret.md"

            # 设置权限：禁止写入该目录
            pm = PermissionManager()
            pm.deny_path(denied_dir, [OperationType.WRITE])

            tool = WriteTool(permission_manager=pm)
            result = tool.run_sync(
                WriteParams(path=str(test_file), content="content")
            )

            assert result.success is False
            assert "权限" in result.error or "denied" in result.error.lower()

    def test_write_readonly_path(self):
        """测试只读路径（有读权限但无写权限）"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams
        from ai_agent.tools.filesystem.permissions import (
            PermissionManager,
            OperationType,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            readonly_dir = Path(tmpdir)
            test_file = readonly_dir / "readonly.md"

            # 设置权限：只允许读取，不允许写入
            pm = PermissionManager()
            pm.allow_path(readonly_dir, [OperationType.READ])

            tool = WriteTool(permission_manager=pm)
            result = tool.run_sync(
                WriteParams(path=str(test_file), content="content")
            )

            assert result.success is False
            assert "权限" in result.error or "denied" in result.error.lower()


class TestWriteToolIntegration:
    """Write 工具与 LangChain 集成测试"""

    def test_to_langchain_tool(self):
        """测试转换为 LangChain 工具"""
        from ai_agent.tools.filesystem.write import WriteTool
        from langchain_core.tools import StructuredTool

        tool = WriteTool()
        langchain_tool = tool.to_langchain_tool()

        assert isinstance(langchain_tool, StructuredTool)
        assert langchain_tool.name == "write"

    @pytest.mark.asyncio
    async def test_async_run(self):
        """测试异步执行"""
        from ai_agent.tools.filesystem.write import WriteTool, WriteParams

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "async_test.md"

            tool = WriteTool()
            result = await tool.run(
                WriteParams(path=str(test_file), content="async content")
            )

            assert result.success is True
            assert test_file.read_text(encoding="utf-8") == "async content"


class TestWriteParams:
    """WriteParams 参数验证测试"""

    def test_default_mode(self):
        """测试默认写入模式为 'w'"""
        from ai_agent.tools.filesystem.write import WriteParams

        params = WriteParams(path="/tmp/test.txt", content="content")
        assert params.mode == "w"

    def test_valid_modes(self):
        """测试有效的写入模式"""
        from ai_agent.tools.filesystem.write import WriteParams

        # 写入模式
        params_w = WriteParams(path="/tmp/test.txt", content="content", mode="w")
        assert params_w.mode == "w"

        # 追加模式
        params_a = WriteParams(path="/tmp/test.txt", content="content", mode="a")
        assert params_a.mode == "a"

    def test_path_required(self):
        """测试 path 参数必填"""
        from ai_agent.tools.filesystem.write import WriteParams
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            WriteParams(content="content")  # type: ignore

    def test_content_required(self):
        """测试 content 参数必填"""
        from ai_agent.tools.filesystem.write import WriteParams
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            WriteParams(path="/tmp/test.txt")  # type: ignore
