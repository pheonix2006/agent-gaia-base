"""文件系统权限管理"""

from pathlib import Path


class PermissionManager:
    """权限管理器

    管理文件系统访问权限，支持 allow/deny 列表。
    """

    def __init__(self) -> None:
        self._allowed_paths: list[Path] = []
        self._denied_paths: list[Path] = []

    def allow_path(self, path: Path | str) -> None:
        """添加允许访问的路径"""
        path = Path(path).resolve()
        if path not in self._allowed_paths:
            self._allowed_paths.append(path)

    def deny_path(self, path: Path | str) -> None:
        """添加禁止访问的路径"""
        path = Path(path).resolve()
        if path not in self._denied_paths:
            self._denied_paths.append(path)

    def is_allowed(self, path: Path | str) -> bool:
        """检查路径是否允许访问

        优先级：deny > allow

        Args:
            path: 要检查的路径

        Returns:
            bool: 是否允许访问
        """
        path = Path(path).resolve()

        # 检查是否在 deny 列表中
        for denied in self._denied_paths:
            try:
                path.relative_to(denied)
                return False
            except ValueError:
                pass

        # 如果没有设置 allow 列表，默认允许
        if not self._allowed_paths:
            return True

        # 检查是否在 allow 列表中
        for allowed in self._allowed_paths:
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                pass

        return False
