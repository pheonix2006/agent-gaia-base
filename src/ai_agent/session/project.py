"""项目管理器模块

提供项目注册、查询、更新等功能。
支持中文名称的拼音转换生成 slug。
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_agent.session.types import Project

# 尝试导入 pypinyin，用于中文转拼音
try:
    from pypinyin import lazy_pinyin

    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False


class ProjectManager:
    """项目管理器

    负责项目的注册、查询、更新和持久化。

    Attributes:
        config_dir: 配置文件存储目录
        config_file: 项目配置文件路径

    Example:
        >>> manager = ProjectManager()
        >>> project = manager.register_project("/path/to/project", "我的项目")
        >>> print(project.slug)  # "wo-de-xiang-mu"
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """初始化项目管理器

        Args:
            config_dir: 配置文件存储目录，默认为 ~/.agents
        """
        if config_dir is None:
            config_dir = Path.home() / ".agents"
        self.config_dir = config_dir
        self.config_file = config_dir / "projects.json"
        self._projects: dict[str, Project] = {}
        self._deleted_slugs: set[str] = set()  # 跟踪已删除的项目
        self._load_projects()

    def _load_projects(self) -> None:
        """从配置文件加载项目列表"""
        if not self.config_file.exists():
            self._projects = {}
            return

        try:
            with open(self.config_file, encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("projects", []):
                # 转换路径为 Path 对象
                item["path"] = Path(item["path"])
                project = Project(**item)
                self._projects[project.slug] = project
        except (json.JSONDecodeError, KeyError, ValueError):
            # 配置文件损坏时重置
            self._projects = {}

    def _save_projects(self) -> None:
        """保存项目列表到配置文件

        在写入前重新加载文件，合并其他实例的修改（乐观并发）。
        已删除的项目不会被重新加载。
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 乐观并发：在写入前重新加载，合并其他实例的修改
        # 仅合并新增的项目（基于 slug），当前实例的修改优先
        # 已删除的项目不会被重新加载
        if self.config_file.exists():
            try:
                with open(self.config_file, encoding="utf-8") as f:
                    data = json.load(f)

                for item in data.get("projects", []):
                    slug = item.get("slug")
                    # 只合并不存在且未被删除的项目
                    if slug and slug not in self._projects and slug not in self._deleted_slugs:
                        item["path"] = Path(item["path"])
                        project = Project(**item)
                        self._projects[slug] = project
            except (json.JSONDecodeError, KeyError, ValueError):
                pass  # 文件损坏时忽略

        data = {
            "version": 1,
            "projects": [
                {
                    "slug": p.slug,
                    "name": p.name,
                    "path": str(p.path),
                    "added_at": p.added_at.isoformat(),
                    "last_opened": p.last_opened.isoformat() if p.last_opened else None,
                    "active_session": p.active_session,
                }
                for p in self._projects.values()
            ],
        }

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _generate_slug(self, name: str) -> str:
        """生成项目 slug

        优先使用 pypinyin 将中文转为拼音，
        否则使用 hash 作为备用方案。

        Args:
            name: 项目名称

        Returns:
            小写连字符格式的 slug
        """
        # 处理空名称
        if not name or not name.strip():
            return "project"

        # 移除特殊字符，保留字母、数字、中文
        cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff\s-]", "", name)
        cleaned = cleaned.strip()

        if not cleaned:
            # 如果清理后为空，使用 hash
            return self._hash_slug(name)

        # 转换为小写连字符格式
        if HAS_PYPINYIN:
            # 使用 pypinyin 将中文转为拼音
            # lazy_pinyin 返回拼音列表，如 ["zhi", "neng", "zhu", "shou"]
            parts: list[str] = []
            current_word = ""
            current_number = ""

            for char in cleaned:
                if char.isalpha() or "\u4e00" <= char <= "\u9fff":
                    # 先处理累积的数字
                    if current_number:
                        parts.append(current_number)
                        current_number = ""
                    current_word += char
                elif char.isdigit():
                    # 先处理累积的单词
                    if current_word:
                        parts.extend(self._to_pinyin_parts(current_word))
                        current_word = ""
                    current_number += char
                else:  # 空格或连字符
                    if current_number:
                        parts.append(current_number)
                        current_number = ""
                    if current_word:
                        parts.extend(self._to_pinyin_parts(current_word))
                        current_word = ""

            # 处理末尾剩余内容
            if current_number:
                parts.append(current_number)
            if current_word:
                parts.extend(self._to_pinyin_parts(current_word))

            slug = "-".join(part.lower() for part in parts if part)
        else:
            # 备用方案：只保留 ASCII 字符
            ascii_only = re.sub(r"[^a-zA-Z0-9\s-]", "", cleaned)
            words = re.split(r"[\s-]+", ascii_only)
            slug = "-".join(word.lower() for word in words if word)

            if not slug:
                return self._hash_slug(name)

        # 截断到 50 字符
        if len(slug) > 50:
            slug = slug[:50].rstrip("-")

        return slug or self._hash_slug(name)

    def _to_pinyin_parts(self, text: str) -> list[str]:
        """将文本转换为拼音部分

        Args:
            text: 输入文本（可能包含中英文混合）

        Returns:
            拼音/英文部分列表
        """
        if not HAS_PYPINYIN:
            return [text.lower()]

        parts: list[str] = []
        current_ascii = ""

        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                # 中文字符
                if current_ascii:
                    parts.append(current_ascii.lower())
                    current_ascii = ""
                # lazy_pinyin 返回单个字符的拼音
                pinyin_list = lazy_pinyin(char)
                parts.extend(pinyin_list)
            else:
                # ASCII 字符
                current_ascii += char

        if current_ascii:
            parts.append(current_ascii.lower())

        return parts

    def _hash_slug(self, name: str) -> str:
        """使用 hash 生成 slug

        Args:
            name: 项目名称

        Returns:
            基于 hash 的 slug
        """
        hash_value = hashlib.md5(name.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"project-{hash_value}"

    def _ensure_unique_slug(self, base_slug: str) -> str:
        """确保 slug 唯一

        如果 slug 已存在，添加数字后缀。

        Args:
            base_slug: 基础 slug

        Returns:
            唯一的 slug
        """
        if base_slug not in self._projects:
            return base_slug

        # 查找可用的数字后缀
        counter = 2
        while f"{base_slug}-{counter}" in self._projects:
            counter += 1

        return f"{base_slug}-{counter}"

    def register_project(self, path: Path | str, name: str) -> Project:
        """注册项目

        如果相同路径已注册，返回已有项目。

        Args:
            path: 项目路径
            name: 项目名称

        Returns:
            项目对象
        """
        # 解析路径
        project_path = Path(path).resolve()

        # 检查是否已存在
        existing = self.get_by_path(project_path)
        if existing is not None:
            return existing

        # 处理空名称
        if not name or not name.strip():
            name = project_path.name

        # 生成唯一 slug
        base_slug = self._generate_slug(name)
        slug = self._ensure_unique_slug(base_slug)

        # 创建项目
        project = Project(
            slug=slug,
            name=name,
            path=project_path,
            added_at=datetime.now(),
        )

        self._projects[slug] = project
        self._save_projects()

        return project

    def get_project(self, slug: str) -> Project | None:
        """通过 slug 获取项目

        Args:
            slug: 项目 slug

        Returns:
            项目对象，不存在返回 None
        """
        return self._projects.get(slug)

    def get_by_path(self, path: Path | str) -> Project | None:
        """通过路径获取项目

        Args:
            path: 项目路径

        Returns:
            项目对象，不存在返回 None
        """
        resolved_path = Path(path).resolve()
        for project in self._projects.values():
            if project.path == resolved_path:
                return project
        return None

    def list_projects(self) -> list[Project]:
        """列出所有项目

        按最后打开时间排序（最近的在前），未打开的按添加时间排序。

        Returns:
            项目列表
        """
        projects = list(self._projects.values())

        def sort_key(p: Project) -> tuple[int, float]:
            # 首先按是否打开过排序（打开过的在前）
            has_opened = 0 if p.last_opened else 1
            # 然后按时间排序（最近的在前，所以取负）
            time = p.last_opened or p.added_at
            return (has_opened, -time.timestamp())

        projects.sort(key=sort_key)
        return projects

    def update_last_opened(self, slug: str) -> None:
        """更新最后打开时间

        Args:
            slug: 项目 slug
        """
        project = self._projects.get(slug)
        if project is None:
            return

        # 创建更新后的项目对象
        updated = Project(
            slug=project.slug,
            name=project.name,
            path=project.path,
            added_at=project.added_at,
            last_opened=datetime.now(),
            active_session=project.active_session,
        )

        self._projects[slug] = updated
        self._save_projects()

    def set_active_session(self, slug: str, session_id: str | None) -> None:
        """设置活跃会话

        Args:
            slug: 项目 slug
            session_id: 会话 ID，None 表示清除活跃会话
        """
        project = self._projects.get(slug)
        if project is None:
            return

        # 创建更新后的项目对象
        updated = Project(
            slug=project.slug,
            name=project.name,
            path=project.path,
            added_at=project.added_at,
            last_opened=project.last_opened,
            active_session=session_id,
        )

        self._projects[slug] = updated
        self._save_projects()

    def rename_project(self, slug: str, new_name: str) -> Project | None:
        """重命名项目

        Args:
            slug: 项目 slug
            new_name: 新的项目名称

        Returns:
            更新后的项目对象，不存在返回 None

        Raises:
            ValueError: 新名称与其他项目冲突
        """
        project = self._projects.get(slug)
        if project is None:
            return None

        # 检查新名称是否与其他项目冲突
        new_slug = self._generate_slug(new_name)
        if new_slug != slug and new_slug in self._projects:
            raise ValueError(f"项目名称冲突：slug '{new_slug}' 已存在")

        # 创建更新后的项目对象
        updated = Project(
            slug=new_slug,
            name=new_name,
            path=project.path,
            added_at=project.added_at,
            last_opened=project.last_opened,
            active_session=project.active_session,
        )

        # 如果 slug 改变，删除旧键，添加新键
        if new_slug != slug:
            del self._projects[slug]
        self._projects[new_slug] = updated
        self._save_projects()

        return updated

    def delete_project(self, slug: str) -> bool:
        """删除项目

        Args:
            slug: 项目 slug

        Returns:
            是否成功删除
        """
        if slug not in self._projects:
            return False

        del self._projects[slug]
        self._deleted_slugs.add(slug)  # 标记为已删除，防止乐观并发重新加载
        self._save_projects()
        return True
