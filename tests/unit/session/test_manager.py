"""SessionManager 类的单元测试

测试对象: src/ai_agent/session/manager.py

TDD 流程: 先写失败测试，再实现最小代码使测试通过
"""

from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from ai_agent.session.types import Message, Session, Trace


class TestSessionManagerInit:
    """SessionManager 初始化测试"""

    def test_init_with_dependencies(self, tmp_path: Path):
        """初始化时应正确接收依赖"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        history_path = tmp_path / "history"
        config_dir = tmp_path / "config"

        store = HistoryStore(history_path)
        project_manager = ProjectManager(config_dir)

        manager = SessionManager(store=store, project_manager=project_manager)

        assert manager.store is store
        assert manager.project_manager is project_manager


class TestSessionManagerCreateSession:
    """SessionManager 创建会话测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        # 使用 manager 的 project_manager 注册项目
        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_create_session_returns_session(
        self, manager: "SessionManager", registered_project: str
    ):
        """创建会话应返回 Session 对象"""
        session = manager.create_session(registered_project, "测试会话")

        assert isinstance(session, Session)
        assert session.project_slug == registered_project
        assert session.title == "测试会话"

    def test_create_session_generates_valid_id(
        self, manager: "SessionManager", registered_project: str
    ):
        """创建会话应生成有效的 ID (YYYYMMDD-NNN 格式)"""
        session = manager.create_session(registered_project)

        import re
        assert re.match(r"^\d{8}-\d{3}$", session.id)

    def test_create_session_id_increments_daily(
        self, manager: "SessionManager", registered_project: str
    ):
        """同一天的会话 ID 应递增"""
        session1 = manager.create_session(registered_project)
        session2 = manager.create_session(registered_project)
        session3 = manager.create_session(registered_project)

        # 提取序号部分
        seq1 = int(session1.id.split("-")[1])
        seq2 = int(session2.id.split("-")[1])
        seq3 = int(session3.id.split("-")[1])

        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1

    def test_create_session_sets_created_at(
        self, manager: "SessionManager", registered_project: str
    ):
        """创建会话应设置 created_at"""
        before = datetime.now()
        session = manager.create_session(registered_project)
        after = datetime.now()

        assert before <= session.created_at <= after

    def test_create_session_persists_metadata(
        self, manager: "SessionManager", registered_project: str
    ):
        """创建会话应持久化元数据"""
        session = manager.create_session(registered_project, "持久化测试")

        # 重新加载验证
        loaded = manager.store.load_session_metadata(registered_project, session.id)
        assert loaded is not None
        assert loaded.title == "持久化测试"

    def test_create_session_updates_active_session(
        self, manager: "SessionManager", registered_project: str
    ):
        """创建会话应更新项目的 active_session"""
        session = manager.create_session(registered_project)

        project = manager.project_manager.get_project(registered_project)
        assert project is not None
        assert project.active_session == session.id

    def test_create_session_default_title(
        self, manager: "SessionManager", registered_project: str
    ):
        """不提供标题时应使用默认标题"""
        session = manager.create_session(registered_project)

        assert session.title == "新会话"

    def test_create_session_for_nonexistent_project_raises(
        self, manager: "SessionManager"
    ):
        """为不存在的项目创建会话应抛出异常"""
        with pytest.raises(ValueError, match="项目不存在"):
            manager.create_session("nonexistent-project")


class TestSessionManagerGetSession:
    """SessionManager 获取会话测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_get_session_returns_session(
        self, manager: "SessionManager", registered_project: str
    ):
        """获取会话应返回 Session 对象"""
        created = manager.create_session(registered_project, "测试会话")

        session = manager.get_session(registered_project, created.id)

        assert session is not None
        assert session.id == created.id
        assert session.title == "测试会话"

    def test_get_session_not_found_returns_none(
        self, manager: "SessionManager", registered_project: str
    ):
        """获取不存在的会话应返回 None"""
        session = manager.get_session(registered_project, "20260320-999")

        assert session is None

    def test_get_session_nonexistent_project_returns_none(
        self, manager: "SessionManager"
    ):
        """获取不存在项目的会话应返回 None"""
        session = manager.get_session("nonexistent-project", "20260320-001")

        assert session is None


class TestSessionManagerGetOrCreateActiveSession:
    """SessionManager 获取或创建活跃会话测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_get_or_create_creates_new_session(
        self, manager: "SessionManager", registered_project: str
    ):
        """没有活跃会话时应创建新会话"""
        session = manager.get_or_create_active_session(registered_project)

        assert session is not None
        assert session.project_slug == registered_project

    def test_get_or_create_returns_existing_session(
        self, manager: "SessionManager", registered_project: str
    ):
        """有活跃会话时应返回现有会话"""
        # 创建第一个会话
        session1 = manager.create_session(registered_project)

        # 再次调用应返回同一个会话
        session2 = manager.get_or_create_active_session(registered_project)

        assert session2 is not None
        assert session2.id == session1.id

    def test_get_or_create_returns_session_with_metadata(
        self, manager: "SessionManager", registered_project: str
    ):
        """返回的会话应包含完整的元数据"""
        # 先创建并添加一些数据
        session = manager.create_session(registered_project)
        msg = Message(
            role="user",
            content="测试消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_message(registered_project, session.id, msg)

        # 获取活跃会话
        active = manager.get_or_create_active_session(registered_project)

        assert active is not None
        assert active.message_count == 1

    def test_get_or_create_nonexistent_project_raises(
        self, manager: "SessionManager"
    ):
        """为不存在的项目获取会话应抛出异常"""
        with pytest.raises(ValueError, match="项目不存在"):
            manager.get_or_create_active_session("nonexistent-project")


class TestSessionManagerListSessions:
    """SessionManager 列出会话测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_list_sessions_empty(
        self, manager: "SessionManager", registered_project: str
    ):
        """列出空项目的会话应返回空列表"""
        sessions = manager.list_sessions(registered_project)

        assert sessions == []

    def test_list_sessions_returns_sessions(
        self, manager: "SessionManager", registered_project: str
    ):
        """列出会话应返回 Session 列表"""
        session1 = manager.create_session(registered_project, "会话1")
        session2 = manager.create_session(registered_project, "会话2")

        sessions = manager.list_sessions(registered_project)

        assert len(sessions) == 2
        ids = [s.id for s in sessions]
        assert session1.id in ids
        assert session2.id in ids

    def test_list_sessions_ordered_by_updated_at(
        self, manager: "SessionManager", registered_project: str
    ):
        """会话应按更新时间倒序排列"""
        session1 = manager.create_session(registered_project, "会话1")
        session2 = manager.create_session(registered_project, "会话2")

        # 更新 session1
        msg = Message(
            role="user",
            content="更新会话1",
            timestamp=datetime(2026, 3, 20, 15, 0, 0),
        )
        manager.append_message(registered_project, session1.id, msg)

        sessions = manager.list_sessions(registered_project)

        # session1 应该排在前面（最新更新）
        assert sessions[0].id == session1.id
        assert sessions[1].id == session2.id

    def test_list_sessions_nonexistent_project_returns_empty(
        self, manager: "SessionManager"
    ):
        """列出不存在项目的会话应返回空列表"""
        sessions = manager.list_sessions("nonexistent-project")

        assert sessions == []


class TestSessionManagerAppendMessage:
    """SessionManager 追加消息测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_append_message_increments_count(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加消息应增加消息计数"""
        session = manager.create_session(registered_project)
        assert session.message_count == 0

        msg = Message(
            role="user",
            content="测试消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_message(registered_project, session.id, msg)

        updated = manager.get_session(registered_project, session.id)
        assert updated is not None
        assert updated.message_count == 1

    def test_append_message_updates_timestamp(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加消息应更新 updated_at"""
        session = manager.create_session(registered_project)
        assert session.updated_at is None

        msg = Message(
            role="user",
            content="测试消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_message(registered_project, session.id, msg)

        updated = manager.get_session(registered_project, session.id)
        assert updated is not None
        assert updated.updated_at is not None

    def test_append_multiple_messages(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加多条消息应正确计数"""
        session = manager.create_session(registered_project)

        for i in range(5):
            msg = Message(
                role="user",
                content=f"消息{i}",
                timestamp=datetime(2026, 3, 20, 10, 5 + i, 0),
            )
            manager.append_message(registered_project, session.id, msg)

        updated = manager.get_session(registered_project, session.id)
        assert updated is not None
        assert updated.message_count == 5

    def test_append_message_persists_to_store(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加消息应持久化到存储"""
        session = manager.create_session(registered_project)

        msg = Message(
            role="user",
            content="持久化测试",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_message(registered_project, session.id, msg)

        # 直接从 store 加载验证
        messages = manager.store.load_messages(registered_project, session.id)
        assert len(messages) == 1
        assert messages[0].content == "持久化测试"

    def test_append_message_nonexistent_session_raises(
        self, manager: "SessionManager", registered_project: str
    ):
        """向不存在的会话追加消息应抛出异常"""
        msg = Message(
            role="user",
            content="测试",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )

        with pytest.raises(ValueError, match="会话不存在"):
            manager.append_message(registered_project, "20260320-999", msg)


class TestSessionManagerAppendTrace:
    """SessionManager 追加调用记录测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_append_trace_increments_count(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加调用记录应增加计数"""
        session = manager.create_session(registered_project)
        assert session.trace_count == 0

        trace = Trace(
            id="trace-001",
            tool="read",
            params={},
            result_status="success",
            duration_ms=50,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_trace(registered_project, session.id, trace)

        updated = manager.get_session(registered_project, session.id)
        assert updated is not None
        assert updated.trace_count == 1

    def test_append_trace_updates_timestamp(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加调用记录应更新 updated_at"""
        session = manager.create_session(registered_project)
        assert session.updated_at is None

        trace = Trace(
            id="trace-001",
            tool="read",
            params={},
            result_status="success",
            duration_ms=50,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_trace(registered_project, session.id, trace)

        updated = manager.get_session(registered_project, session.id)
        assert updated is not None
        assert updated.updated_at is not None

    def test_append_multiple_traces(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加多条调用记录应正确计数"""
        session = manager.create_session(registered_project)

        for i in range(3):
            trace = Trace(
                id=f"trace-{i:03d}",
                tool="read",
                params={},
                result_status="success",
                duration_ms=10 * (i + 1),
                timestamp=datetime(2026, 3, 20, 10, 5 + i, 0),
            )
            manager.append_trace(registered_project, session.id, trace)

        updated = manager.get_session(registered_project, session.id)
        assert updated is not None
        assert updated.trace_count == 3

    def test_append_trace_persists_to_store(
        self, manager: "SessionManager", registered_project: str
    ):
        """追加调用记录应持久化到存储"""
        session = manager.create_session(registered_project)

        trace = Trace(
            id="trace-001",
            tool="read",
            params={"path": "/test.py"},
            result_status="success",
            duration_ms=50,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_trace(registered_project, session.id, trace)

        # 直接从 store 加载验证
        traces = manager.store.load_traces(registered_project, session.id)
        assert len(traces) == 1
        assert traces[0].tool == "read"

    def test_append_trace_nonexistent_session_raises(
        self, manager: "SessionManager", registered_project: str
    ):
        """向不存在的会话追加调用记录应抛出异常"""
        trace = Trace(
            id="trace-001",
            tool="read",
            params={},
            result_status="success",
            duration_ms=50,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )

        with pytest.raises(ValueError, match="会话不存在"):
            manager.append_trace(registered_project, "20260320-999", trace)


class TestSessionManagerLoadSessionData:
    """SessionManager 加载完整会话数据测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_load_session_data_returns_dict(
        self, manager: "SessionManager", registered_project: str
    ):
        """加载会话数据应返回字典"""
        session = manager.create_session(registered_project)

        data = manager.load_session_data(registered_project, session.id)

        assert isinstance(data, dict)

    def test_load_session_data_contains_metadata(
        self, manager: "SessionManager", registered_project: str
    ):
        """加载会话数据应包含元数据"""
        session = manager.create_session(registered_project, "完整测试")

        data = manager.load_session_data(registered_project, session.id)

        assert "session" in data
        assert data["session"].title == "完整测试"

    def test_load_session_data_contains_messages(
        self, manager: "SessionManager", registered_project: str
    ):
        """加载会话数据应包含消息列表"""
        session = manager.create_session(registered_project)

        msg = Message(
            role="user",
            content="测试消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_message(registered_project, session.id, msg)

        data = manager.load_session_data(registered_project, session.id)

        assert "messages" in data
        assert len(data["messages"]) == 1
        assert data["messages"][0].content == "测试消息"

    def test_load_session_data_contains_traces(
        self, manager: "SessionManager", registered_project: str
    ):
        """加载会话数据应包含调用记录列表"""
        session = manager.create_session(registered_project)

        trace = Trace(
            id="trace-001",
            tool="read",
            params={},
            result_status="success",
            duration_ms=50,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_trace(registered_project, session.id, trace)

        data = manager.load_session_data(registered_project, session.id)

        assert "traces" in data
        assert len(data["traces"]) == 1
        assert data["traces"][0].tool == "read"

    def test_load_session_data_full_workflow(
        self, manager: "SessionManager", registered_project: str
    ):
        """加载完整会话数据工作流"""
        session = manager.create_session(registered_project, "完整工作流测试")

        # 添加消息
        msg1 = Message(
            role="user",
            content="问题1",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        msg2 = Message(
            role="assistant",
            content="回答1",
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )
        manager.append_message(registered_project, session.id, msg1)
        manager.append_message(registered_project, session.id, msg2)

        # 添加调用记录
        trace = Trace(
            id="trace-001",
            tool="read",
            params={"path": "test.py"},
            result_status="success",
            duration_ms=50,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_trace(registered_project, session.id, trace)

        # 加载完整数据
        data = manager.load_session_data(registered_project, session.id)

        assert data["session"].title == "完整工作流测试"
        assert len(data["messages"]) == 2
        assert len(data["traces"]) == 1

    def test_load_session_data_nonexistent_returns_none(
        self, manager: "SessionManager", registered_project: str
    ):
        """加载不存在的会话数据应返回 None"""
        data = manager.load_session_data(registered_project, "20260320-999")

        assert data is None


class TestSessionManagerSessionIdGeneration:
    """SessionManager 会话 ID 生成测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_session_id_format_yyyymmdd_nnn(
        self, manager: "SessionManager", registered_project: str
    ):
        """会话 ID 应符合 YYYYMMDD-NNN 格式"""
        session = manager.create_session(registered_project)

        import re
        pattern = r"^\d{4}\d{2}\d{2}-\d{3}$"
        assert re.match(pattern, session.id), f"ID {session.id} 不符合 YYYYMMDD-NNN 格式"

    def test_session_id_starts_from_001(
        self, manager: "SessionManager", registered_project: str
    ):
        """会话 ID 序号应从 001 开始"""
        session = manager.create_session(registered_project)

        seq = int(session.id.split("-")[1])
        assert seq == 1

    def test_session_id_increments_sequentially(
        self, manager: "SessionManager", registered_project: str
    ):
        """会话 ID 序号应顺序递增"""
        sessions = [manager.create_session(registered_project) for _ in range(5)]

        seqs = [int(s.id.split("-")[1]) for s in sessions]
        assert seqs == [1, 2, 3, 4, 5]

    def test_session_id_respects_existing_sessions(
        self, manager: "SessionManager", registered_project: str
    ):
        """会话 ID 应考虑已存在的会话"""
        # 创建会话
        session1 = manager.create_session(registered_project)
        session2 = manager.create_session(registered_project)

        # 手动删除 session2 的元数据（模拟部分损坏）
        manager.store._get_metadata_file(registered_project, session2.id).unlink()

        # 创建新会话，应该跳过已使用的 ID
        # 注意：这个测试验证的是根据现有存储的会话来确定序号
        session3 = manager.create_session(registered_project)

        # 至少应该比 session1 的序号大
        seq1 = int(session1.id.split("-")[1])
        seq3 = int(session3.id.split("-")[1])
        assert seq3 > seq1


class TestSessionManagerIntegration:
    """SessionManager 集成测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "SessionManager":
        """创建 SessionManager 实例"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.store import HistoryStore

        store = HistoryStore(tmp_path / "history")
        project_manager = ProjectManager(tmp_path / "config")
        return SessionManager(store=store, project_manager=project_manager)

    @pytest.fixture
    def registered_project(self, manager: "SessionManager") -> str:
        """注册一个测试项目并返回 slug"""
        from pathlib import Path
        import tempfile

        project = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "测试项目"
        )
        return project.slug

    def test_full_conversation_workflow(
        self, manager: "SessionManager", registered_project: str
    ):
        """完整对话工作流测试"""
        # 1. 获取或创建活跃会话
        session = manager.get_or_create_active_session(registered_project)
        assert session is not None

        # 2. 用户提问
        user_msg = Message(
            role="user",
            content="帮我分析这个项目",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        manager.append_message(registered_project, session.id, user_msg)

        # 3. 工具调用
        trace = Trace(
            id="trace-001",
            tool="list_files",
            params={"path": "."},
            result_status="success",
            duration_ms=100,
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )
        manager.append_trace(registered_project, session.id, trace)

        # 4. 助手回复
        assistant_msg = Message(
            role="assistant",
            content="项目包含以下文件...",
            timestamp=datetime(2026, 3, 20, 10, 5, 2),
        )
        manager.append_message(registered_project, session.id, assistant_msg)

        # 5. 加载完整数据验证
        data = manager.load_session_data(registered_project, session.id)

        assert data is not None
        assert data["session"].message_count == 2
        assert data["session"].trace_count == 1
        assert len(data["messages"]) == 2
        assert len(data["traces"]) == 1

    def test_multiple_projects_isolated(
        self, manager: "SessionManager"
    ):
        """多项目会话应相互隔离"""
        # 使用 manager 的 project_manager 注册两个项目
        import tempfile
        from pathlib import Path

        project1 = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "项目1"
        )
        project2 = manager.project_manager.register_project(
            Path(tempfile.mkdtemp()), "项目2"
        )

        # 创建会话
        session1 = manager.create_session(project1.slug, "项目1会话")
        session2 = manager.create_session(project2.slug, "项目2会话")

        # 添加消息
        msg1 = Message(
            role="user",
            content="项目1消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        msg2 = Message(
            role="user",
            content="项目2消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )
        manager.append_message(project1.slug, session1.id, msg1)
        manager.append_message(project2.slug, session2.id, msg2)

        # 验证隔离
        data1 = manager.load_session_data(project1.slug, session1.id)
        data2 = manager.load_session_data(project2.slug, session2.id)

        assert data1 is not None
        assert data2 is not None
        assert data1["session"].project_slug == project1.slug
        assert data2["session"].project_slug == project2.slug
        assert data1["messages"][0].content == "项目1消息"
        assert data2["messages"][0].content == "项目2消息"

    def test_session_switching(
        self, manager: "SessionManager", registered_project: str
    ):
        """会话切换测试"""
        # 创建两个会话
        session1 = manager.create_session(registered_project, "会话1")
        session2 = manager.create_session(registered_project, "会话2")

        # 活跃会话应该是 session2
        active = manager.get_or_create_active_session(registered_project)
        assert active.id == session2.id

        # 切换回 session1
        manager.project_manager.set_active_session(registered_project, session1.id)
        active = manager.get_or_create_active_session(registered_project)
        assert active.id == session1.id
