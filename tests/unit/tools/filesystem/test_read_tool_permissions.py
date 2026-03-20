"""测试 ReadTool 权限检查使用统一的 check(path, OperationType) 接口"""

import pytest
from pathlib import Path

from ai_agent.tools.filesystem.read import ReadTool, ReadParams
from ai_agent.tools.filesystem.permissions import PermissionManager, OperationType
from ai_agent.session.types import Permission


def test_read_tool_uses_check_with_operation_type(tmp_path: Path) -> None:
    """验证 ReadTool 使用 check(path, OperationType.READ)"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    pm = PermissionManager()
    pm.ask_path(tmp_path)

    tool = ReadTool(permission_manager=pm)
    params = ReadParams(path=str(test_file), offset=0, limit=100)
    result = tool.run_sync(params)

    assert result.success is False
    assert "权限不足" in result.error


def test_read_tool_allows_when_permitted(tmp_path: Path) -> None:
    """验证 ReadTool 在有权限时正常读取"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    pm = PermissionManager()
    pm.allow_path(tmp_path, operations=[OperationType.READ])

    tool = ReadTool(permission_manager=pm)
    params = ReadParams(path=str(test_file), offset=0, limit=100)
    result = tool.run_sync(params)

    assert result.success is True
    assert "hello world" in result.data
