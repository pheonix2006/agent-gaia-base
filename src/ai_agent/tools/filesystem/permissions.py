"""文件系统权限管理

支持三级权限 (allow/deny/ask) 和按操作类型区分的权限管理。
"""

from __future__ import annotations

from collections.abc import Awaitable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    pass


class OperationType(str, Enum):
    """文件操作类型枚举

    Attributes:
        READ: 读取文件/目录
        WRITE: 写入/创建文件
        EDIT: 编辑/修改文件
        LIST: 列出目录内容
        DELETE: 删除文件/目录
    """

    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    LIST = "list"
    DELETE = "delete"


class PermissionCallback(Protocol):
    """权限确认回调协议

    当权限检查返回 ASK 时，需要通过此回调请求用户确认。
    """

    def __call__(
        self, path: Path, operation: OperationType
    ) -> Awaitable[bool]: ...


class _PathPermission:
    """路径权限配置

    存储单个路径的权限配置，包括允许的操作和需要确认的操作。
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.allowed_operations: set[OperationType] | None = None  # None 表示所有操作
        self.ask_operations: set[OperationType] = set()


class PermissionManager:
    """权限管理器

    管理文件系统访问权限，支持三级权限 (allow/deny/ask)。
    支持按操作类型区分权限 (read/write/edit/list/delete)。
    支持异步回调用于 ASK 权限的确认。

    权限优先级: deny > ask > allow
    """

    def __init__(self, callback: PermissionCallback | None = None) -> None:
        """初始化权限管理器

        Args:
            callback: 可选的权限确认回调，用于处理 ASK 权限
        """
        self._callback = callback
        self._allowed_paths: dict[Path, _PathPermission] = {}
        self._denied_paths: dict[Path, _PathPermission] = {}
        self._ask_paths: dict[Path, _PathPermission] = {}

    def allow_path(
        self,
        path: Path | str,
        operations: list[OperationType] | None = None,
    ) -> None:
        """添加允许访问的路径

        Args:
            path: 要允许的路径
            operations: 允许的操作类型列表，None 或空列表表示所有操作
        """
        resolved_path = Path(path).resolve()

        if resolved_path not in self._allowed_paths:
            self._allowed_paths[resolved_path] = _PathPermission(resolved_path)

        perm = self._allowed_paths[resolved_path]
        if operations:  # 非空列表才设置特定操作
            ops_set = set(operations)
            if perm.allowed_operations is None:
                perm.allowed_operations = ops_set
            else:
                perm.allowed_operations.update(ops_set)
        # None 或空列表保持 allowed_operations 为 None（表示所有操作）

    def deny_path(
        self,
        path: Path | str,
        operations: list[OperationType] | None = None,
    ) -> None:
        """添加禁止访问的路径

        Args:
            path: 要禁止的路径
            operations: 禁止的操作类型列表，None 表示所有操作
        """
        resolved_path = Path(path).resolve()

        if resolved_path not in self._denied_paths:
            self._denied_paths[resolved_path] = _PathPermission(resolved_path)

        perm = self._denied_paths[resolved_path]
        if operations is not None:
            ops_set = set(operations)
            if perm.allowed_operations is None:
                perm.allowed_operations = ops_set
            else:
                perm.allowed_operations.update(ops_set)

    def ask_path(
        self,
        path: Path | str,
        operations: list[OperationType] | None = None,
    ) -> None:
        """添加需要确认的路径

        Args:
            path: 需要确认的路径
            operations: 需要确认的操作类型列表，None 表示所有操作
        """
        resolved_path = Path(path).resolve()

        if resolved_path not in self._ask_paths:
            self._ask_paths[resolved_path] = _PathPermission(resolved_path)

        perm = self._ask_paths[resolved_path]
        if operations is not None:
            perm.ask_operations.update(operations)
        else:
            # None 表示所有操作都需要确认
            perm.ask_operations = set(OperationType)

    def check(
        self,
        path: Path | str,
        operation: OperationType,
    ) -> str:
        """检查路径的操作权限

        Args:
            path: 要检查的路径
            operation: 操作类型

        Returns:
            权限级别字符串: "allow", "deny", 或 "ask"
        """
        from ai_agent.session.types import Permission

        resolved_path = Path(path).resolve()

        # 1. 检查 deny 列表（最高优先级）
        for denied_path, perm in self._denied_paths.items():
            if self._is_subpath(resolved_path, denied_path):
                if perm.allowed_operations is None or operation in perm.allowed_operations:
                    return Permission.DENY

        # 2. 检查 ask 列表
        for ask_path, perm in self._ask_paths.items():
            if self._is_subpath(resolved_path, ask_path):
                if operation in perm.ask_operations or not perm.ask_operations:
                    # 如果 ask_operations 为空，但路径在 ask 列表中，检查是否有特定配置
                    pass
                if operation in perm.ask_operations:
                    return Permission.ASK

        # 3. 检查 allow 列表
        if not self._allowed_paths:
            # 如果没有设置 allow 列表，默认允许
            return Permission.ALLOW

        for allowed_path, perm in self._allowed_paths.items():
            if self._is_subpath(resolved_path, allowed_path):
                if perm.allowed_operations is None or operation in perm.allowed_operations:
                    return Permission.ALLOW

        # 4. 不在允许列表中，返回 deny
        return Permission.DENY

    async def request(
        self,
        path: Path | str,
        operation: OperationType,
    ) -> bool:
        """请求执行操作的权限（异步）

        对于 ASK 权限，会触发回调获取用户确认。

        Args:
            path: 要操作的路径
            operation: 操作类型

        Returns:
            bool: 是否允许执行操作
        """
        from ai_agent.session.types import Permission

        permission = self.check(path, operation)

        if permission == Permission.ALLOW:
            return True
        elif permission == Permission.DENY:
            return False
        elif permission == Permission.ASK:
            if self._callback is not None:
                return await self._callback(Path(path).resolve(), operation)
            return False  # 无回调时默认拒绝

        return False

    def is_allowed(self, path: Path | str) -> bool:
        """检查路径是否允许访问（向后兼容方法）

        优先级：deny > allow

        Args:
            path: 要检查的路径

        Returns:
            bool: 是否允许访问
        """
        from ai_agent.session.types import Permission

        # 默认使用 READ 操作检查
        return self.check(path, OperationType.READ) == Permission.ALLOW

    def list_allowed(self) -> list[Path]:
        """列出所有允许的路径

        Returns:
            允许的路径列表
        """
        return list(self._allowed_paths.keys())

    def list_denied(self) -> list[Path]:
        """列出所有禁止的路径

        Returns:
            禁止的路径列表
        """
        return list(self._denied_paths.keys())

    def clear_allowed(self) -> None:
        """清除所有允许配置"""
        self._allowed_paths.clear()

    def clear_denied(self) -> None:
        """清除所有禁止配置"""
        self._denied_paths.clear()
        self._ask_paths.clear()

    def clear_all(self) -> None:
        """清除所有权限配置"""
        self._allowed_paths.clear()
        self._denied_paths.clear()
        self._ask_paths.clear()

    @staticmethod
    def _is_subpath(path: Path, parent: Path) -> bool:
        """检查 path 是否是 parent 的子路径或相同路径

        Args:
            path: 要检查的路径
            parent: 父路径

        Returns:
            bool: 是否是子路径
        """
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
