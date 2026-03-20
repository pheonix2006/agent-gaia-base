"""PermissionManager 单元测试

测试三级权限系统：
- allow/deny/ask 权限级别
- 按操作类型区分权限 (read/write/edit/list)
- 异步回调支持
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_agent.session.types import Permission
from ai_agent.tools.filesystem.permissions import (
    OperationType,
    PermissionCallback,
    PermissionManager,
)


class TestOperationType:
    """OperationType 枚举测试"""

    def test_operation_types_exist(self) -> None:
        """测试所有操作类型都已定义"""
        assert OperationType.READ == "read"
        assert OperationType.WRITE == "write"
        assert OperationType.EDIT == "edit"
        assert OperationType.LIST == "list"

    def test_operation_type_is_str_enum(self) -> None:
        """测试 OperationType 是字符串枚举"""
        assert isinstance(OperationType.READ, str)
        assert OperationType.READ in iter(OperationType)


class TestPermissionManagerInit:
    """PermissionManager 初始化测试"""

    def test_init_empty(self) -> None:
        """测试初始化为空状态"""
        manager = PermissionManager()
        assert manager.list_allowed() == []
        assert manager.list_denied() == []

    def test_init_with_callback(self) -> None:
        """测试使用回调初始化"""
        callback = AsyncMock(spec=PermissionCallback)
        manager = PermissionManager(callback=callback)
        assert manager._callback is callback


class TestPermissionManagerAllowDeny:
    """PermissionManager allow/deny 配置测试"""

    def test_allow_single_path(self) -> None:
        """测试允许单个路径"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")

        allowed = manager.list_allowed()
        assert len(allowed) == 1
        assert allowed[0] == Path("/tmp/test").resolve()

    def test_allow_multiple_paths(self) -> None:
        """测试允许多个路径"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test1")
        manager.allow_path("/tmp/test2")

        allowed = manager.list_allowed()
        assert len(allowed) == 2

    def test_allow_path_no_duplicate(self) -> None:
        """测试重复添加不会产生重复"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")
        manager.allow_path("/tmp/test")

        assert len(manager.list_allowed()) == 1

    def test_deny_single_path(self) -> None:
        """测试禁止单个路径"""
        manager = PermissionManager()
        manager.deny_path("/tmp/secret")

        denied = manager.list_denied()
        assert len(denied) == 1
        assert denied[0] == Path("/tmp/secret").resolve()

    def test_allow_with_specific_operations(self) -> None:
        """测试允许路径时指定操作类型"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test", operations=[OperationType.READ])

        # 验证 check 方法返回正确结果
        assert manager.check("/tmp/test", OperationType.READ) == Permission.ALLOW
        assert manager.check("/tmp/test", OperationType.WRITE) == Permission.DENY

    def test_deny_with_specific_operations(self) -> None:
        """测试禁止路径时指定操作类型"""
        manager = PermissionManager()
        manager.deny_path("/tmp/test", operations=[OperationType.WRITE, OperationType.EDIT])

        assert manager.check("/tmp/test", OperationType.WRITE) == Permission.DENY
        assert manager.check("/tmp/test", OperationType.EDIT) == Permission.DENY
        assert manager.check("/tmp/test", OperationType.READ) == Permission.ALLOW


class TestPermissionManagerCheck:
    """PermissionManager check 方法测试"""

    def test_check_default_allow(self) -> None:
        """测试未配置时默认允许"""
        manager = PermissionManager()
        assert manager.check("/any/path", OperationType.READ) == Permission.ALLOW

    def test_check_deny_over_allow(self) -> None:
        """测试 deny 优先于 allow"""
        manager = PermissionManager()
        manager.allow_path("/tmp")
        manager.deny_path("/tmp/secret")

        assert manager.check("/tmp/secret/file.txt", OperationType.READ) == Permission.DENY

    def test_check_subpath_allowed(self) -> None:
        """测试子路径继承权限"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")

        assert manager.check("/tmp/test/subdir/file.txt", OperationType.READ) == Permission.ALLOW

    def test_check_subpath_denied(self) -> None:
        """测试子路径继承禁止"""
        manager = PermissionManager()
        manager.deny_path("/tmp/secret")

        assert manager.check("/tmp/secret/deep/file.txt", OperationType.READ) == Permission.DENY

    def test_check_not_in_allow_list(self) -> None:
        """测试不在允许列表中返回 deny"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")

        assert manager.check("/other/path", OperationType.READ) == Permission.DENY

    def test_check_with_ask_permission(self) -> None:
        """测试 ASK 权限级别"""
        manager = PermissionManager()
        manager.ask_path("/tmp/confirm", operations=[OperationType.DELETE])

        # 先添加允许，这样特定操作会返回 ASK
        manager.allow_path("/tmp/confirm")
        manager.ask_path("/tmp/confirm", operations=[OperationType.DELETE])

        # DELETE 操作需要确认
        assert manager.check("/tmp/confirm", OperationType.DELETE) == Permission.ASK
        # READ 操作直接允许
        assert manager.check("/tmp/confirm", OperationType.READ) == Permission.ALLOW


class TestPermissionManagerAsk:
    """PermissionManager ask_path 方法测试"""

    def test_ask_path_basic(self) -> None:
        """测试设置需要确认的路径"""
        manager = PermissionManager()
        manager.allow_path("/tmp")
        manager.ask_path("/tmp/sensitive")

        assert manager.check("/tmp/sensitive", OperationType.READ) == Permission.ASK

    def test_ask_path_with_operations(self) -> None:
        """测试针对特定操作设置 ASK"""
        manager = PermissionManager()
        manager.allow_path("/tmp")
        manager.ask_path("/tmp/file.txt", operations=[OperationType.WRITE])

        # READ 直接允许
        assert manager.check("/tmp/file.txt", OperationType.READ) == Permission.ALLOW
        # WRITE 需要确认
        assert manager.check("/tmp/file.txt", OperationType.WRITE) == Permission.ASK


class TestPermissionManagerRequest:
    """PermissionManager request 异步方法测试"""

    @pytest.mark.asyncio
    async def test_request_allow_without_callback(self) -> None:
        """测试无回调时 allow 权限直接返回 True"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")

        result = await manager.request("/tmp/test", OperationType.READ)
        assert result is True

    @pytest.mark.asyncio
    async def test_request_deny_without_callback(self) -> None:
        """测试无回调时 deny 权限直接返回 False"""
        manager = PermissionManager()
        manager.deny_path("/tmp/test")

        result = await manager.request("/tmp/test", OperationType.READ)
        assert result is False

    @pytest.mark.asyncio
    async def test_request_ask_with_callback_approved(self) -> None:
        """测试 ASK 权限触发回调且用户批准"""
        callback = AsyncMock(spec=PermissionCallback, return_value=True)
        manager = PermissionManager(callback=callback)
        manager.allow_path("/tmp")
        manager.ask_path("/tmp/sensitive")

        result = await manager.request("/tmp/sensitive", OperationType.WRITE)

        assert result is True
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_ask_with_callback_denied(self) -> None:
        """测试 ASK 权限触发回调且用户拒绝"""
        callback = AsyncMock(spec=PermissionCallback, return_value=False)
        manager = PermissionManager(callback=callback)
        manager.allow_path("/tmp")
        manager.ask_path("/tmp/sensitive")

        result = await manager.request("/tmp/sensitive", OperationType.WRITE)

        assert result is False
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_ask_without_callback_defaults_deny(self) -> None:
        """测试 ASK 权限无回调时默认拒绝"""
        manager = PermissionManager()
        manager.allow_path("/tmp")
        manager.ask_path("/tmp/sensitive")

        result = await manager.request("/tmp/sensitive", OperationType.READ)
        assert result is False


class TestPermissionCallback:
    """PermissionCallback 协议测试"""

    def test_callback_protocol_is_callable(self) -> None:
        """测试协议是可调用的"""
        async def my_callback(path: Path, operation: OperationType) -> bool:
            return True

        # 验证函数符合协议
        callback: PermissionCallback = my_callback
        assert callable(callback)


class TestPermissionManagerEdgeCases:
    """边缘情况测试"""

    def test_check_with_string_path(self) -> None:
        """测试使用字符串路径"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")

        assert manager.check("/tmp/test/file.txt", OperationType.READ) == Permission.ALLOW

    def test_check_with_path_object(self) -> None:
        """测试使用 Path 对象"""
        manager = PermissionManager()
        manager.allow_path(Path("/tmp/test"))

        assert manager.check(Path("/tmp/test/file.txt"), OperationType.READ) == Permission.ALLOW

    def test_check_relative_path_resolution(self) -> None:
        """测试相对路径解析"""
        manager = PermissionManager()
        manager.allow_path(".")

        # 相对路径应该被解析为绝对路径
        assert manager.check(".", OperationType.READ) == Permission.ALLOW

    def test_empty_operations_list_allows_all(self) -> None:
        """测试空操作列表表示允许所有操作"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test", operations=[])

        # 空列表应表示所有操作
        for op in OperationType:
            assert manager.check("/tmp/test", op) == Permission.ALLOW

    def test_priority_order(self) -> None:
        """测试权限优先级: deny > ask > allow"""
        manager = PermissionManager()

        # 设置允许
        manager.allow_path("/tmp")
        # 设置需要确认
        manager.ask_path("/tmp/confirm")
        # 设置禁止
        manager.deny_path("/tmp/confirm/denied")

        # deny 优先级最高
        assert manager.check("/tmp/confirm/denied", OperationType.READ) == Permission.DENY

        # ask 次之
        assert manager.check("/tmp/confirm", OperationType.READ) == Permission.ASK

        # allow 最低
        assert manager.check("/tmp/other", OperationType.READ) == Permission.ALLOW


class TestPermissionManagerClear:
    """PermissionManager 清除权限测试"""

    def test_clear_allowed(self) -> None:
        """测试清除允许列表"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")
        manager.clear_allowed()

        assert manager.list_allowed() == []

    def test_clear_denied(self) -> None:
        """测试清除禁止列表"""
        manager = PermissionManager()
        manager.deny_path("/tmp/secret")
        manager.clear_denied()

        assert manager.list_denied() == []

    def test_clear_all(self) -> None:
        """测试清除所有权限"""
        manager = PermissionManager()
        manager.allow_path("/tmp/test")
        manager.deny_path("/tmp/secret")
        manager.ask_path("/tmp/confirm")
        manager.clear_all()

        assert manager.list_allowed() == []
        assert manager.list_denied() == []
        # 清除后应该恢复默认允许
        assert manager.check("/any/path", OperationType.READ) == Permission.ALLOW
