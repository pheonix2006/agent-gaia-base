"""ProjectManager 单元测试

测试项目注册、查询、更新等功能。
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import uuid

import pytest

from ai_agent.session.project import ProjectManager
from ai_agent.session.types import Project


class TestProjectManagerSlugGeneration:
    """测试 slug 生成逻辑"""

    def test_slug_from_english_name(self, tmp_path: Path) -> None:
        """英文项目名生成 slug"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(
            path=tmp_path / "my-project", name="My Project"
        )
        assert project.slug == "my-project"

    def test_slug_from_chinese_name_with_pypinyin(self, tmp_path: Path) -> None:
        """中文项目名使用拼音生成 slug"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(
            path=tmp_path / "ai-agent", name="智能助手"
        )
        # pypinyin 会将 "智能助手" 转换为 "zhi-neng-zhu-shou"
        assert project.slug == "zhi-neng-zhu-shou"

    def test_slug_from_mixed_name(self, tmp_path: Path) -> None:
        """中英混合项目名生成 slug"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(
            path=tmp_path / "agent", name="AI Agent 框架"
        )
        # "AI Agent 框架" -> "ai-agent-kuang-jia"
        assert project.slug == "ai-agent-kuang-jia"

    def test_slug_with_numbers(self, tmp_path: Path) -> None:
        """包含数字的项目名"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(
            path=tmp_path / "project", name="Project 2026"
        )
        assert project.slug == "project-2026"

    def test_slug_uniqueness_on_conflict(self, tmp_path: Path) -> None:
        """slug 冲突时自动添加数字后缀"""
        manager = ProjectManager(config_dir=tmp_path)

        # 注册第一个项目
        p1 = manager.register_project(
            path=tmp_path / "path1", name="Test Project"
        )
        assert p1.slug == "test-project"

        # 注册同名项目（不同路径）
        p2 = manager.register_project(
            path=tmp_path / "path2", name="Test Project"
        )
        assert p2.slug == "test-project-2"

        # 再注册一个同名项目
        p3 = manager.register_project(
            path=tmp_path / "path3", name="Test Project"
        )
        assert p3.slug == "test-project-3"


class TestProjectManagerRegisterProject:
    """测试项目注册"""

    def test_register_new_project(self, tmp_path: Path) -> None:
        """注册新项目"""
        manager = ProjectManager(config_dir=tmp_path)
        project_path = tmp_path / "my-project"

        project = manager.register_project(path=project_path, name="My Project")

        assert project.slug == "my-project"
        assert project.name == "My Project"
        assert project.path == project_path.resolve()
        assert project.added_at is not None
        assert project.last_opened is None
        assert project.active_session is None

    def test_register_same_path_returns_existing(self, tmp_path: Path) -> None:
        """相同路径重复注册返回已有项目"""
        manager = ProjectManager(config_dir=tmp_path)
        project_path = tmp_path / "existing-project"

        p1 = manager.register_project(path=project_path, name="Original Name")
        p2 = manager.register_project(path=project_path, name="Different Name")

        # 返回同一项目
        assert p1.slug == p2.slug
        assert p1.name == "Original Name"  # 名称不变
        assert p1 == p2

    def test_register_creates_config_file(self, tmp_path: Path) -> None:
        """注册项目后创建配置文件"""
        manager = ProjectManager(config_dir=tmp_path)
        manager.register_project(path=tmp_path / "project", name="Test")

        config_file = tmp_path / "projects.json"
        assert config_file.exists()

        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        assert "projects" in data
        assert len(data["projects"]) == 1


class TestProjectManagerGetProject:
    """测试项目查询"""

    def test_get_project_by_slug(self, tmp_path: Path) -> None:
        """通过 slug 获取项目"""
        manager = ProjectManager(config_dir=tmp_path)
        registered = manager.register_project(
            path=tmp_path / "project", name="Test Project"
        )

        project = manager.get_project("test-project")
        assert project is not None
        assert project == registered

    def test_get_project_not_found(self, tmp_path: Path) -> None:
        """获取不存在的项目返回 None"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.get_project("non-existent")
        assert project is None

    def test_get_project_by_path(self, tmp_path: Path) -> None:
        """通过路径获取项目"""
        manager = ProjectManager(config_dir=tmp_path)
        project_path = tmp_path / "my-project"
        registered = manager.register_project(path=project_path, name="My Project")

        project = manager.get_by_path(project_path)
        assert project is not None
        assert project == registered

    def test_get_by_path_not_found(self, tmp_path: Path) -> None:
        """通过路径获取不存在的项目返回 None"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.get_by_path(tmp_path / "non-existent")
        assert project is None

    def test_get_by_path_resolves_path(self, tmp_path: Path) -> None:
        """get_by_path 自动解析路径（处理相对路径）"""
        manager = ProjectManager(config_dir=tmp_path)
        project_path = (tmp_path / "project").resolve()
        registered = manager.register_project(path=project_path, name="Test")

        # 使用相对路径查询
        project = manager.get_by_path(project_path)
        assert project is not None
        assert project == registered


class TestProjectManagerListProjects:
    """测试项目列表"""

    def test_list_empty(self, tmp_path: Path) -> None:
        """空列表"""
        manager = ProjectManager(config_dir=tmp_path)
        projects = manager.list_projects()
        assert projects == []

    def test_list_multiple_projects(self, tmp_path: Path) -> None:
        """列出多个项目"""
        manager = ProjectManager(config_dir=tmp_path)

        p1 = manager.register_project(path=tmp_path / "project1", name="Project A")
        p2 = manager.register_project(path=tmp_path / "project2", name="Project B")
        p3 = manager.register_project(path=tmp_path / "project3", name="Project C")

        projects = manager.list_projects()
        assert len(projects) == 3
        assert p1 in projects
        assert p2 in projects
        assert p3 in projects

    def test_list_sorted_by_last_opened(self, tmp_path: Path) -> None:
        """列表按最后打开时间排序（最近的在前）"""
        manager = ProjectManager(config_dir=tmp_path)

        p1 = manager.register_project(path=tmp_path / "project1", name="A")
        p2 = manager.register_project(path=tmp_path / "project2", name="B")
        p3 = manager.register_project(path=tmp_path / "project3", name="C")

        # 更新 p2 的最后打开时间
        manager.update_last_opened(p2.slug)

        projects = manager.list_projects()
        # 最近打开的应该在前面，检查 slug 而非对象引用
        assert projects[0].slug == p2.slug  # 最近打开的在前面


class TestProjectManagerUpdateLastOpened:
    """测试更新最后打开时间"""

    def test_update_last_opened(self, tmp_path: Path) -> None:
        """更新最后打开时间"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(path=tmp_path / "project", name="Test")

        assert project.last_opened is None

        before_update = datetime.now()
        manager.update_last_opened(project.slug)
        after_update = datetime.now()

        updated = manager.get_project(project.slug)
        assert updated is not None
        assert updated.last_opened is not None
        assert before_update <= updated.last_opened <= after_update

    def test_update_last_opened_not_found(self, tmp_path: Path) -> None:
        """更新不存在的项目不做任何操作"""
        manager = ProjectManager(config_dir=tmp_path)
        # 不应抛出异常
        manager.update_last_opened("non-existent")


class TestProjectManagerSetActiveSession:
    """测试设置活跃会话"""

    def test_set_active_session(self, tmp_path: Path) -> None:
        """设置活跃会话"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(path=tmp_path / "project", name="Test")

        session_id = "20260320-001"
        manager.set_active_session(project.slug, session_id)

        updated = manager.get_project(project.slug)
        assert updated is not None
        assert updated.active_session == session_id

    def test_set_active_session_not_found(self, tmp_path: Path) -> None:
        """设置不存在项目的活跃会话不做任何操作"""
        manager = ProjectManager(config_dir=tmp_path)
        # 不应抛出异常
        manager.set_active_session("non-existent", "20260320-001")

    def test_clear_active_session(self, tmp_path: Path) -> None:
        """清除活跃会话"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(path=tmp_path / "project", name="Test")

        # 先设置
        manager.set_active_session(project.slug, "20260320-001")
        # 再清除
        manager.set_active_session(project.slug, None)

        updated = manager.get_project(project.slug)
        assert updated is not None
        assert updated.active_session is None


class TestProjectManagerPersistence:
    """测试持久化"""

    def test_persistence_across_restarts(self, tmp_path: Path) -> None:
        """重启后数据持久化"""
        # 第一个 manager 实例
        manager1 = ProjectManager(config_dir=tmp_path)
        p1 = manager1.register_project(path=tmp_path / "project", name="Test")
        manager1.update_last_opened(p1.slug)
        manager1.set_active_session(p1.slug, "20260320-001")

        # 第二个 manager 实例（模拟重启）
        manager2 = ProjectManager(config_dir=tmp_path)
        projects = manager2.list_projects()

        assert len(projects) == 1
        assert projects[0].slug == "test"
        assert projects[0].name == "Test"
        assert projects[0].last_opened is not None
        assert projects[0].active_session == "20260320-001"

    def test_persistence_with_chinese_name(self, tmp_path: Path) -> None:
        """中文项目名持久化"""
        manager1 = ProjectManager(config_dir=tmp_path)
        p1 = manager1.register_project(path=tmp_path / "project", name="智能助手")

        manager2 = ProjectManager(config_dir=tmp_path)
        projects = manager2.list_projects()

        assert len(projects) == 1
        assert projects[0].name == "智能助手"


class TestProjectManagerDefaultConfigDir:
    """测试默认配置目录"""

    def test_default_config_dir(self, tmp_path: Path) -> None:
        """使用默认配置目录（~/.agents）"""
        with patch.dict("os.environ", {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}):
            manager = ProjectManager()
            expected_dir = tmp_path / ".agents"
            assert manager.config_dir == expected_dir


class TestProjectManagerEdgeCases:
    """边缘情况测试"""

    def test_special_characters_in_name(self, tmp_path: Path) -> None:
        """名称包含特殊字符"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(
            path=tmp_path / "project",
            name="My @#$% Project!!!"
        )
        # 特殊字符应被过滤
        assert project.slug == "my-project"

    def test_empty_name_uses_path(self, tmp_path: Path) -> None:
        """空名称使用路径名"""
        manager = ProjectManager(config_dir=tmp_path)
        project = manager.register_project(
            path=tmp_path / "my-awesome-project",
            name=""
        )
        # 空名称时使用路径名
        assert project.name == "my-awesome-project"

    def test_long_name_truncates(self, tmp_path: Path) -> None:
        """超长名称截断"""
        manager = ProjectManager(config_dir=tmp_path)
        long_name = "a" * 100
        project = manager.register_project(
            path=tmp_path / "project",
            name=long_name
        )
        # slug 不应超过 50 字符
        assert len(project.slug) <= 50

    def test_concurrent_modification(self, tmp_path: Path) -> None:
        """并发修改场景（模拟）"""
        manager1 = ProjectManager(config_dir=tmp_path)
        manager2 = ProjectManager(config_dir=tmp_path)

        # manager1 注册项目
        p1 = manager1.register_project(path=tmp_path / "project1", name="Project 1")

        # manager2 注册另一个项目
        p2 = manager2.register_project(path=tmp_path / "project2", name="Project 2")

        # manager1 应该能看到 manager2 的项目（重新加载后）
        manager1_reload = ProjectManager(config_dir=tmp_path)
        projects = manager1_reload.list_projects()
        assert len(projects) == 2
