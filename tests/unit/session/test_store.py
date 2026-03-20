"""HistoryStore 类的单元测试

测试对象: src/ai_agent/session/store.py

TDD 流程: 先写失败测试，再实现最小代码使测试通过
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from ai_agent.session.types import Message, Session, Trace


class TestHistoryStoreInit:
    """HistoryStore 初始化测试"""

    def test_init_creates_base_path(self, tmp_path: Path):
        """初始化时应自动创建基础目录"""
        from ai_agent.session.store import HistoryStore

        base_path = tmp_path / "history"
        assert not base_path.exists()

        store = HistoryStore(base_path)

        assert base_path.exists()
        assert store.base_path == base_path

    def test_init_with_existing_path(self, tmp_path: Path):
        """使用已存在的目录初始化"""
        from ai_agent.session.store import HistoryStore

        base_path = tmp_path / "existing_history"
        base_path.mkdir()

        store = HistoryStore(base_path)

        assert store.base_path == base_path


class TestHistoryStoreMessages:
    """HistoryStore 消息操作测试"""

    @pytest.fixture
    def store(self, tmp_path: Path) -> "HistoryStore":
        """创建 HistoryStore 实例"""
        from ai_agent.session.store import HistoryStore

        return HistoryStore(tmp_path / "history")

    @pytest.fixture
    def sample_message(self) -> Message:
        """创建示例消息"""
        return Message(
            role="user",
            content="帮我分析这个项目",
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )

    def test_append_message_creates_directory(
        self, store: "HistoryStore", sample_message: Message
    ):
        """追加消息应创建会话目录"""
        store.append_message("my-agent", "20260320-001", sample_message)

        session_dir = store.base_path / "my-agent" / "20260320-001"
        assert session_dir.exists()

    def test_append_message_creates_file(
        self, store: "HistoryStore", sample_message: Message
    ):
        """追加消息应创建 messages.jsonl 文件"""
        store.append_message("my-agent", "20260320-001", sample_message)

        messages_file = store.base_path / "my-agent" / "20260320-001" / "messages.jsonl"
        assert messages_file.exists()

    def test_append_message_writes_jsonl(
        self, store: "HistoryStore", sample_message: Message
    ):
        """消息应以 JSONL 格式写入"""
        store.append_message("my-agent", "20260320-001", sample_message)

        messages_file = store.base_path / "my-agent" / "20260320-001" / "messages.jsonl"
        content = messages_file.read_text(encoding="utf-8")

        # JSONL 每行是一个 JSON 对象
        lines = content.strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["role"] == "user"
        assert data["content"] == "帮我分析这个项目"

    def test_append_multiple_messages(
        self, store: "HistoryStore", sample_message: Message
    ):
        """追加多条消息应分行写入"""
        msg1 = sample_message
        msg2 = Message(
            role="assistant",
            content="好的，让我先看看项目结构...",
            timestamp=datetime(2026, 3, 20, 10, 5, 3),
        )

        store.append_message("my-agent", "20260320-001", msg1)
        store.append_message("my-agent", "20260320-001", msg2)

        messages_file = store.base_path / "my-agent" / "20260320-001" / "messages.jsonl"
        content = messages_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        assert len(lines) == 2

        data1 = json.loads(lines[0])
        data2 = json.loads(lines[1])
        assert data1["role"] == "user"
        assert data2["role"] == "assistant"

    def test_load_messages_empty(self, store: "HistoryStore"):
        """加载空会话应返回空列表"""
        messages = store.load_messages("my-agent", "20260320-001")

        assert messages == []

    def test_load_messages_returns_list(self, store: "HistoryStore", sample_message: Message):
        """加载消息应返回 Message 列表"""
        store.append_message("my-agent", "20260320-001", sample_message)

        messages = store.load_messages("my-agent", "20260320-001")

        assert len(messages) == 1
        assert isinstance(messages[0], Message)
        assert messages[0].role == "user"
        assert messages[0].content == "帮我分析这个项目"

    def test_load_messages_multiple(self, store: "HistoryStore"):
        """加载多条消息"""
        msg1 = Message(role="user", content="问题1", timestamp=datetime(2026, 3, 20, 10, 5, 1))
        msg2 = Message(role="assistant", content="回答1", timestamp=datetime(2026, 3, 20, 10, 5, 3))
        msg3 = Message(role="user", content="问题2", timestamp=datetime(2026, 3, 20, 10, 6, 0))

        store.append_message("my-agent", "20260320-001", msg1)
        store.append_message("my-agent", "20260320-001", msg2)
        store.append_message("my-agent", "20260320-001", msg3)

        messages = store.load_messages("my-agent", "20260320-001")

        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"

    def test_load_messages_with_name_field(self, store: "HistoryStore"):
        """加载带有 name 字段的消息 (tool 角色)"""
        msg = Message(
            role="tool",
            content="文件内容...",
            timestamp=datetime(2026, 3, 20, 10, 5, 4),
            name="read",
        )

        store.append_message("my-agent", "20260320-001", msg)

        messages = store.load_messages("my-agent", "20260320-001")

        assert len(messages) == 1
        assert messages[0].role == "tool"
        assert messages[0].name == "read"


class TestHistoryStoreTraces:
    """HistoryStore 调用记录操作测试"""

    @pytest.fixture
    def store(self, tmp_path: Path) -> "HistoryStore":
        """创建 HistoryStore 实例"""
        from ai_agent.session.store import HistoryStore

        return HistoryStore(tmp_path / "history")

    @pytest.fixture
    def sample_trace(self) -> Trace:
        """创建示例调用记录"""
        return Trace(
            id="trace-001",
            tool="read",
            params={"path": "./src/main.py"},
            result_status="success",
            duration_ms=45,
            timestamp=datetime(2026, 3, 20, 10, 5, 4),
        )

    def test_append_trace_creates_file(
        self, store: "HistoryStore", sample_trace: Trace
    ):
        """追加调用记录应创建 traces.jsonl 文件"""
        store.append_trace("my-agent", "20260320-001", sample_trace)

        traces_file = store.base_path / "my-agent" / "20260320-001" / "traces.jsonl"
        assert traces_file.exists()

    def test_append_trace_writes_jsonl(
        self, store: "HistoryStore", sample_trace: Trace
    ):
        """调用记录应以 JSONL 格式写入"""
        store.append_trace("my-agent", "20260320-001", sample_trace)

        traces_file = store.base_path / "my-agent" / "20260320-001" / "traces.jsonl"
        content = traces_file.read_text(encoding="utf-8")

        lines = content.strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["id"] == "trace-001"
        assert data["tool"] == "read"
        assert data["params"] == {"path": "./src/main.py"}
        assert data["result_status"] == "success"
        assert data["duration_ms"] == 45

    def test_append_multiple_traces(self, store: "HistoryStore", sample_trace: Trace):
        """追加多条调用记录应分行写入"""
        trace1 = sample_trace
        trace2 = Trace(
            id="trace-002",
            tool="web_search",
            params={"query": "Python async"},
            result_status="success",
            result_preview="Found 10 results...",
            duration_ms=1234,
            timestamp=datetime(2026, 3, 20, 10, 6, 0),
        )

        store.append_trace("my-agent", "20260320-001", trace1)
        store.append_trace("my-agent", "20260320-001", trace2)

        traces_file = store.base_path / "my-agent" / "20260320-001" / "traces.jsonl"
        content = traces_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        assert len(lines) == 2

        data2 = json.loads(lines[1])
        assert data2["id"] == "trace-002"
        assert data2["result_preview"] == "Found 10 results..."

    def test_load_traces_empty(self, store: "HistoryStore"):
        """加载空会话应返回空列表"""
        traces = store.load_traces("my-agent", "20260320-001")

        assert traces == []

    def test_load_traces_returns_list(self, store: "HistoryStore", sample_trace: Trace):
        """加载调用记录应返回 Trace 列表"""
        store.append_trace("my-agent", "20260320-001", sample_trace)

        traces = store.load_traces("my-agent", "20260320-001")

        assert len(traces) == 1
        assert isinstance(traces[0], Trace)
        assert traces[0].id == "trace-001"
        assert traces[0].tool == "read"
        assert traces[0].duration_ms == 45

    def test_load_traces_multiple(self, store: "HistoryStore"):
        """加载多条调用记录"""
        trace1 = Trace(
            id="trace-001",
            tool="read",
            params={},
            result_status="success",
            duration_ms=10,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        trace2 = Trace(
            id="trace-002",
            tool="write",
            params={},
            result_status="error",
            duration_ms=20,
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )

        store.append_trace("my-agent", "20260320-001", trace1)
        store.append_trace("my-agent", "20260320-001", trace2)

        traces = store.load_traces("my-agent", "20260320-001")

        assert len(traces) == 2
        assert traces[0].tool == "read"
        assert traces[1].tool == "write"


class TestHistoryStoreMetadata:
    """HistoryStore 元数据操作测试"""

    @pytest.fixture
    def store(self, tmp_path: Path) -> "HistoryStore":
        """创建 HistoryStore 实例"""
        from ai_agent.session.store import HistoryStore

        return HistoryStore(tmp_path / "history")

    @pytest.fixture
    def sample_session(self) -> Session:
        """创建示例会话"""
        return Session(
            id="20260320-001",
            project_slug="my-agent",
            title="调试 Skills 系统",
            created_at=datetime(2026, 3, 20, 10, 5, 0),
            message_count=42,
            trace_count=15,
        )

    def test_save_session_metadata_creates_file(
        self, store: "HistoryStore", sample_session: Session
    ):
        """保存会话元数据应创建 metadata.json 文件"""
        store.save_session_metadata("my-agent", sample_session)

        metadata_file = store.base_path / "my-agent" / "20260320-001" / "metadata.json"
        assert metadata_file.exists()

    def test_save_session_metadata_writes_json(
        self, store: "HistoryStore", sample_session: Session
    ):
        """元数据应以 JSON 格式写入"""
        store.save_session_metadata("my-agent", sample_session)

        metadata_file = store.base_path / "my-agent" / "20260320-001" / "metadata.json"
        content = metadata_file.read_text(encoding="utf-8")

        data = json.loads(content)
        assert data["id"] == "20260320-001"
        assert data["project_slug"] == "my-agent"
        assert data["title"] == "调试 Skills 系统"
        assert data["message_count"] == 42
        assert data["trace_count"] == 15

    def test_load_session_metadata_not_found(self, store: "HistoryStore"):
        """加载不存在的元数据应返回 None"""
        result = store.load_session_metadata("my-agent", "20260320-001")

        assert result is None

    def test_load_session_metadata_returns_session(
        self, store: "HistoryStore", sample_session: Session
    ):
        """加载元数据应返回 Session 对象"""
        store.save_session_metadata("my-agent", sample_session)

        result = store.load_session_metadata("my-agent", "20260320-001")

        assert result is not None
        assert isinstance(result, Session)
        assert result.id == "20260320-001"
        assert result.title == "调试 Skills 系统"
        assert result.message_count == 42

    def test_load_session_metadata_with_updated_at(self, store: "HistoryStore"):
        """加载带有 updated_at 的元数据"""
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="测试会话",
            created_at=datetime(2026, 3, 20, 10, 5, 0),
            updated_at=datetime(2026, 3, 20, 15, 30, 0),
        )

        store.save_session_metadata("my-agent", session)
        result = store.load_session_metadata("my-agent", "20260320-001")

        assert result is not None
        assert result.updated_at is not None
        assert result.updated_at == datetime(2026, 3, 20, 15, 30, 0)

    def test_save_session_metadata_overwrites(
        self, store: "HistoryStore", sample_session: Session
    ):
        """保存元数据应覆盖已存在的文件"""
        # 第一次保存
        store.save_session_metadata("my-agent", sample_session)

        # 更新并再次保存
        updated_session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="更新后的标题",
            created_at=sample_session.created_at,
            message_count=100,
        )
        store.save_session_metadata("my-agent", updated_session)

        result = store.load_session_metadata("my-agent", "20260320-001")

        assert result is not None
        assert result.title == "更新后的标题"
        assert result.message_count == 100


class TestHistoryStoreListSessions:
    """HistoryStore 会话列表测试"""

    @pytest.fixture
    def store(self, tmp_path: Path) -> "HistoryStore":
        """创建 HistoryStore 实例"""
        from ai_agent.session.store import HistoryStore

        return HistoryStore(tmp_path / "history")

    def test_list_sessions_empty(self, store: "HistoryStore"):
        """列出空项目的会话应返回空列表"""
        sessions = store.list_sessions("my-agent")

        assert sessions == []

    def test_list_sessions_single(self, store: "HistoryStore"):
        """列出单个会话"""
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="测试会话",
            created_at=datetime(2026, 3, 20, 10, 5, 0),
        )
        store.save_session_metadata("my-agent", session)

        sessions = store.list_sessions("my-agent")

        assert len(sessions) == 1
        assert sessions[0].id == "20260320-001"
        assert sessions[0].title == "测试会话"

    def test_list_sessions_multiple_ordered_by_updated_at(self, store: "HistoryStore"):
        """多个会话应按更新时间倒序排列"""
        # 创建三个会话，不同更新时间
        session1 = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="会话1",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
            updated_at=datetime(2026, 3, 20, 11, 0, 0),  # 最早
        )
        session2 = Session(
            id="20260320-002",
            project_slug="my-agent",
            title="会话2",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
            updated_at=datetime(2026, 3, 20, 15, 0, 0),  # 最新
        )
        session3 = Session(
            id="20260320-003",
            project_slug="my-agent",
            title="会话3",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
            updated_at=datetime(2026, 3, 20, 13, 0, 0),  # 中间
        )

        store.save_session_metadata("my-agent", session1)
        store.save_session_metadata("my-agent", session2)
        store.save_session_metadata("my-agent", session3)

        sessions = store.list_sessions("my-agent")

        assert len(sessions) == 3
        # 应按更新时间倒序：session2 -> session3 -> session1
        assert sessions[0].id == "20260320-002"
        assert sessions[1].id == "20260320-003"
        assert sessions[2].id == "20260320-001"

    def test_list_sessions_without_updated_at_uses_created_at(self, store: "HistoryStore"):
        """没有更新时间的会话应使用创建时间排序"""
        session1 = Session(
            id="20260319-001",
            project_slug="my-agent",
            title="旧会话",
            created_at=datetime(2026, 3, 19, 10, 0, 0),
        )
        session2 = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="新会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )

        store.save_session_metadata("my-agent", session1)
        store.save_session_metadata("my-agent", session2)

        sessions = store.list_sessions("my-agent")

        assert len(sessions) == 2
        # 新会话在前
        assert sessions[0].id == "20260320-001"
        assert sessions[1].id == "20260319-001"

    def test_list_sessions_different_projects(self, store: "HistoryStore"):
        """不同项目的会话应隔离"""
        session1 = Session(
            id="20260320-001",
            project_slug="project-a",
            title="项目A会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        session2 = Session(
            id="20260320-002",
            project_slug="project-b",
            title="项目B会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )

        store.save_session_metadata("project-a", session1)
        store.save_session_metadata("project-b", session2)

        sessions_a = store.list_sessions("project-a")
        sessions_b = store.list_sessions("project-b")

        assert len(sessions_a) == 1
        assert len(sessions_b) == 1
        assert sessions_a[0].project_slug == "project-a"
        assert sessions_b[0].project_slug == "project-b"

    def test_list_sessions_ignores_invalid_metadata(self, store: "HistoryStore"):
        """列出会话时应忽略无效的元数据文件"""
        # 创建有效会话
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="有效会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        store.save_session_metadata("my-agent", session)

        # 创建无效的元数据文件
        invalid_dir = store.base_path / "my-agent" / "20260320-999"
        invalid_dir.mkdir(parents=True)
        (invalid_dir / "metadata.json").write_text("invalid json", encoding="utf-8")

        sessions = store.list_sessions("my-agent")

        # 应只返回有效会话
        assert len(sessions) == 1
        assert sessions[0].id == "20260320-001"

    def test_list_sessions_ignores_directories_without_metadata(self, store: "HistoryStore"):
        """列出会话时应忽略没有元数据的目录"""
        # 创建有效会话
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="有效会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        store.save_session_metadata("my-agent", session)

        # 创建没有元数据的目录
        empty_dir = store.base_path / "my-agent" / "20260320-002"
        empty_dir.mkdir(parents=True)

        sessions = store.list_sessions("my-agent")

        assert len(sessions) == 1
        assert sessions[0].id == "20260320-001"


class TestHistoryStoreIntegration:
    """HistoryStore 集成测试"""

    @pytest.fixture
    def store(self, tmp_path: Path) -> "HistoryStore":
        """创建 HistoryStore 实例"""
        from ai_agent.session.store import HistoryStore

        return HistoryStore(tmp_path / "history")

    def test_full_session_workflow(self, store: "HistoryStore"):
        """完整会话工作流测试"""
        # 1. 创建会话
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="完整测试",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        store.save_session_metadata("my-agent", session)

        # 2. 追加消息
        msg1 = Message(
            role="user",
            content="帮我分析项目",
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )
        msg2 = Message(
            role="assistant",
            content="好的，开始分析...",
            timestamp=datetime(2026, 3, 20, 10, 5, 3),
        )
        store.append_message("my-agent", "20260320-001", msg1)
        store.append_message("my-agent", "20260320-001", msg2)

        # 3. 追加调用记录
        trace = Trace(
            id="trace-001",
            tool="read",
            params={"path": "main.py"},
            result_status="success",
            duration_ms=50,
            timestamp=datetime(2026, 3, 20, 10, 5, 2),
        )
        store.append_trace("my-agent", "20260320-001", trace)

        # 4. 验证数据
        loaded_session = store.load_session_metadata("my-agent", "20260320-001")
        loaded_messages = store.load_messages("my-agent", "20260320-001")
        loaded_traces = store.load_traces("my-agent", "20260320-001")

        assert loaded_session is not None
        assert loaded_session.title == "完整测试"
        assert len(loaded_messages) == 2
        assert len(loaded_traces) == 1

        # 5. 列出会话
        sessions = store.list_sessions("my-agent")
        assert len(sessions) == 1

    def test_file_structure_matches_design(self, store: "HistoryStore"):
        """验证文件结构符合设计"""
        # 创建会话和数据
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="测试",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        store.save_session_metadata("my-agent", session)

        msg = Message(
            role="user",
            content="test",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        store.append_message("my-agent", "20260320-001", msg)

        trace = Trace(
            id="trace-001",
            tool="test",
            params={},
            result_status="success",
            duration_ms=1,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        store.append_trace("my-agent", "20260320-001", trace)

        # 验证目录结构
        session_dir = store.base_path / "my-agent" / "20260320-001"
        assert session_dir.exists()
        assert (session_dir / "metadata.json").exists()
        assert (session_dir / "messages.jsonl").exists()
        assert (session_dir / "traces.jsonl").exists()
