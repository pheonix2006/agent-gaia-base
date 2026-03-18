"""Read 工具测试"""

import tempfile
from pathlib import Path

import pytest


class TestReadTool:
    """Read 工具测试"""

    def test_read_file_success(self):
        """测试成功读取文件"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Test Content\n\nHello World")
            f.flush()

            tool = ReadTool()
            result = tool.run_sync(ReadParams(path=f.name))

            assert result.success is True
            assert "# Test Content" in result.data

    def test_read_file_not_found(self):
        """测试文件不存在"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        tool = ReadTool()
        result = tool.run_sync(ReadParams(path="/nonexistent/file/12345.md"))

        assert result.success is False
        assert "不存在" in result.error or "not found" in result.error.lower()

    def test_read_with_line_limit(self):
        """测试限制读取行数"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            for i in range(100):
                f.write(f"Line {i}\n")
            f.flush()

            tool = ReadTool()
            result = tool.run_sync(ReadParams(path=f.name, limit=10))

            assert result.success is True
            lines = result.data.split("\n")
            # 去掉可能的空行
            non_empty_lines = [l for l in lines if l.strip()]
            assert len(non_empty_lines) <= 10

    def test_read_with_offset(self):
        """测试从指定偏移读取"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            for i in range(10):
                f.write(f"Line {i}\n")
            f.flush()

            tool = ReadTool()
            result = tool.run_sync(ReadParams(path=f.name, offset=5))

            assert result.success is True
            assert "Line 5" in result.data
            assert "Line 0" not in result.data

    def test_read_skill_md_file(self):
        """测试读取 SKILL.md 文件（核心场景）"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: test-skill
description: 测试技能
---
# 使用说明
这是正文内容。
""", encoding="utf-8")

            tool = ReadTool()
            result = tool.run_sync(ReadParams(path=str(skill_md)))

            assert result.success is True
            assert "name: test-skill" in result.data
            assert "使用说明" in result.data


class TestReadToolPermissions:
    """Read 工具权限测试"""

    def test_read_allowed_path(self):
        """测试读取允许的路径"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams
        from ai_agent.tools.filesystem.permissions import PermissionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_dir = Path(tmpdir)
            test_file = allowed_dir / "test.md"
            test_file.write_text("content", encoding="utf-8")

            # 设置权限：允许读取该目录
            pm = PermissionManager()
            pm.allow_path(allowed_dir)

            tool = ReadTool(permission_manager=pm)
            result = tool.run_sync(ReadParams(path=str(test_file)))

            assert result.success is True

    def test_read_denied_path(self):
        """测试读取禁止的路径"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams
        from ai_agent.tools.filesystem.permissions import PermissionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            denied_dir = Path(tmpdir) / "secret"
            denied_dir.mkdir()
            secret_file = denied_dir / "secret.md"
            secret_file.write_text("secret content", encoding="utf-8")

            # 设置权限：禁止读取该目录
            pm = PermissionManager()
            pm.deny_path(denied_dir)

            tool = ReadTool(permission_manager=pm)
            result = tool.run_sync(ReadParams(path=str(secret_file)))

            assert result.success is False
            assert "权限" in result.error or "denied" in result.error.lower()


class TestReadToolIntegration:
    """Read 工具与 LangChain 集成测试"""

    def test_to_langchain_tool(self):
        """测试转换为 LangChain 工具"""
        from ai_agent.tools.filesystem.read import ReadTool
        from langchain_core.tools import StructuredTool

        tool = ReadTool()
        langchain_tool = tool.to_langchain_tool()

        assert isinstance(langchain_tool, StructuredTool)
        assert langchain_tool.name == "read"
