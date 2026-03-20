"""核心类型定义的单元测试

测试对象: src/ai_agent/session/types.py

TDD 流程: 先写失败测试，再实现最小代码使测试通过
"""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError


class TestPermission:
    """Permission 枚举测试"""

    def test_permission_has_allow(self):
        """Permission 应包含 ALLOW 值"""
        from ai_agent.session.types import Permission

        assert Permission.ALLOW.value == "allow"

    def test_permission_has_deny(self):
        """Permission 应包含 DENY 值"""
        from ai_agent.session.types import Permission

        assert Permission.DENY.value == "deny"

    def test_permission_has_ask(self):
        """Permission 应包含 ASK 值"""
        from ai_agent.session.types import Permission

        assert Permission.ASK.value == "ask"

    def test_permission_count(self):
        """Permission 应恰好有 3 个值"""
        from ai_agent.session.types import Permission

        assert len(Permission) == 3


class TestProject:
    """Project 模型测试"""

    def test_create_project_with_required_fields(self):
        """使用必填字段创建 Project"""
        from ai_agent.session.types import Project

        now = datetime.now()
        project = Project(
            slug="my-agent",
            name="My Agent Project",
            path=Path("E:/Project/ai agent"),
            added_at=now,
        )

        assert project.slug == "my-agent"
        assert project.name == "My Agent Project"
        assert project.path == Path("E:/Project/ai agent")
        assert project.added_at == now
        assert project.last_opened is None
        assert project.active_session is None

    def test_create_project_with_all_fields(self):
        """使用所有字段创建 Project"""
        from ai_agent.session.types import Project

        now = datetime.now()
        later = datetime.now()
        project = Project(
            slug="web-scraper",
            name="Web Scraper",
            path=Path("/home/user/projects/web-scraper"),
            added_at=now,
            last_opened=later,
            active_session="20260320-001",
        )

        assert project.slug == "web-scraper"
        assert project.last_opened == later
        assert project.active_session == "20260320-001"

    def test_project_slug_validation_valid(self):
        """有效的 slug 格式应通过验证"""
        from ai_agent.session.types import Project

        valid_slugs = [
            "my-agent",
            "web-scraper",
            "project123",
            "a",
            "test-project-1",
            "123",
            "abc-def-ghi",
        ]

        for slug in valid_slugs:
            project = Project(
                slug=slug,
                name="Test",
                path=Path("/tmp"),
                added_at=datetime.now(),
            )
            assert project.slug == slug

    def test_project_slug_validation_invalid(self):
        """无效的 slug 格式应抛出 ValidationError"""
        from ai_agent.session.types import Project

        invalid_slugs = [
            "My-Agent",      # 大写字母
            "my_agent",      # 下划线
            "my agent",      # 空格
            "my-agent-",     # 以连字符结尾
            "-my-agent",     # 以连字符开头
            "my--agent",     # 连续连字符
            "",              # 空字符串
        ]

        for slug in invalid_slugs:
            with pytest.raises(ValidationError):
                Project(
                    slug=slug,
                    name="Test",
                    path=Path("/tmp"),
                    added_at=datetime.now(),
                )

    def test_project_missing_required_field(self):
        """缺少必填字段应抛出 ValidationError"""
        from ai_agent.session.types import Project

        with pytest.raises(ValidationError):
            Project(
                name="Test",
                path=Path("/tmp"),
                added_at=datetime.now(),
            )


class TestSession:
    """Session 模型测试"""

    def test_create_session_with_required_fields(self):
        """使用必填字段创建 Session"""
        from ai_agent.session.types import Session

        now = datetime.now()
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            created_at=now,
        )

        assert session.id == "20260320-001"
        assert session.project_slug == "my-agent"
        assert session.title == "新会话"
        assert session.created_at == now
        assert session.updated_at is None
        assert session.message_count == 0
        assert session.trace_count == 0

    def test_create_session_with_all_fields(self):
        """使用所有字段创建 Session"""
        from ai_agent.session.types import Session

        now = datetime.now()
        later = datetime.now()
        session = Session(
            id="20260320-002",
            project_slug="web-scraper",
            title="调试 Skills 系统",
            created_at=now,
            updated_at=later,
            message_count=42,
            trace_count=15,
        )

        assert session.title == "调试 Skills 系统"
        assert session.message_count == 42
        assert session.trace_count == 15

    def test_session_id_validation_valid(self):
        """有效的 Session ID 格式应通过验证"""
        from ai_agent.session.types import Session

        valid_ids = [
            "20260320-001",
            "20260101-999",
            "19991231-000",
            "20301231-123",
        ]

        for session_id in valid_ids:
            session = Session(
                id=session_id,
                project_slug="test",
                created_at=datetime.now(),
            )
            assert session.id == session_id

    def test_session_id_validation_invalid(self):
        """无效的 Session ID 格式应抛出 ValidationError"""
        from ai_agent.session.types import Session

        invalid_ids = [
            "2026-03-20-001",    # 错误的日期格式
            "20260320",          # 缺少序号
            "20260320-1",        # 序号位数不足
            "20260320-0001",     # 序号位数过多
            "26-03-20-001",      # 年份位数不足
            "2026320-001",       # 日期格式错误
            "20260320-abc",      # 序号非数字
            "",                  # 空字符串
        ]

        for session_id in invalid_ids:
            with pytest.raises(ValidationError):
                Session(
                    id=session_id,
                    project_slug="test",
                    created_at=datetime.now(),
                )

    def test_session_missing_required_field(self):
        """缺少必填字段应抛出 ValidationError"""
        from ai_agent.session.types import Session

        with pytest.raises(ValidationError):
            Session(
                project_slug="test",
                created_at=datetime.now(),
            )


class TestMessage:
    """Message 模型测试"""

    def test_create_message_with_required_fields(self):
        """使用必填字段创建 Message"""
        from ai_agent.session.types import Message

        now = datetime.now()
        message = Message(
            role="user",
            content="帮我分析这个项目",
            timestamp=now,
        )

        assert message.role == "user"
        assert message.content == "帮我分析这个项目"
        assert message.timestamp == now
        assert message.name is None

    def test_create_message_with_name(self):
        """创建带有 name 字段的 Message (role=tool)"""
        from ai_agent.session.types import Message

        now = datetime.now()
        message = Message(
            role="tool",
            content="文件内容...",
            timestamp=now,
            name="read",
        )

        assert message.role == "tool"
        assert message.name == "read"

    def test_message_role_validation_valid(self):
        """有效的 role 值应通过验证"""
        from ai_agent.session.types import Message

        valid_roles = ["user", "assistant", "system", "tool"]

        for role in valid_roles:
            message = Message(
                role=role,
                content="test",
                timestamp=datetime.now(),
            )
            assert message.role == role

    def test_message_role_validation_invalid(self):
        """无效的 role 值应抛出 ValidationError"""
        from ai_agent.session.types import Message

        invalid_roles = ["User", "ASSISTANT", "admin", "bot", "", "unknown"]

        for role in invalid_roles:
            with pytest.raises(ValidationError):
                Message(
                    role=role,
                    content="test",
                    timestamp=datetime.now(),
                )

    def test_message_missing_required_field(self):
        """缺少必填字段应抛出 ValidationError"""
        from ai_agent.session.types import Message

        with pytest.raises(ValidationError):
            Message(
                content="test",
                timestamp=datetime.now(),
            )


class TestTrace:
    """Trace 模型测试"""

    def test_create_trace_with_required_fields(self):
        """使用必填字段创建 Trace"""
        from ai_agent.session.types import Trace

        now = datetime.now()
        trace = Trace(
            id="trace-001",
            tool="read",
            params={"path": "./src/main.py"},
            result_status="success",
            duration_ms=45,
            timestamp=now,
        )

        assert trace.id == "trace-001"
        assert trace.tool == "read"
        assert trace.params == {"path": "./src/main.py"}
        assert trace.result_status == "success"
        assert trace.result_preview is None
        assert trace.duration_ms == 45
        assert trace.timestamp == now

    def test_create_trace_with_result_preview(self):
        """创建带有 result_preview 的 Trace"""
        from ai_agent.session.types import Trace

        now = datetime.now()
        trace = Trace(
            id="trace-002",
            tool="web_search",
            params={"query": "Python async"},
            result_status="success",
            result_preview="Found 10 results...",
            duration_ms=1234,
            timestamp=now,
        )

        assert trace.result_preview == "Found 10 results..."

    def test_trace_result_status_validation_valid(self):
        """有效的 result_status 值应通过验证"""
        from ai_agent.session.types import Trace

        valid_statuses = ["success", "error", "timeout"]

        for status in valid_statuses:
            trace = Trace(
                id="trace-001",
                tool="test",
                params={},
                result_status=status,
                duration_ms=100,
                timestamp=datetime.now(),
            )
            assert trace.result_status == status

    def test_trace_result_status_validation_invalid(self):
        """无效的 result_status 值应抛出 ValidationError"""
        from ai_agent.session.types import Trace

        invalid_statuses = ["Success", "ERROR", "failed", "pending", "", "unknown"]

        for status in invalid_statuses:
            with pytest.raises(ValidationError):
                Trace(
                    id="trace-001",
                    tool="test",
                    params={},
                    result_status=status,
                    duration_ms=100,
                    timestamp=datetime.now(),
                )

    def test_trace_duration_ms_must_be_non_negative(self):
        """duration_ms 必须是非负整数"""
        from ai_agent.session.types import Trace

        # 有效: 0
        trace = Trace(
            id="trace-001",
            tool="test",
            params={},
            result_status="success",
            duration_ms=0,
            timestamp=datetime.now(),
        )
        assert trace.duration_ms == 0

        # 有效: 正整数
        trace = Trace(
            id="trace-002",
            tool="test",
            params={},
            result_status="success",
            duration_ms=1000,
            timestamp=datetime.now(),
        )
        assert trace.duration_ms == 1000

        # 无效: 负数
        with pytest.raises(ValidationError):
            Trace(
                id="trace-003",
                tool="test",
                params={},
                result_status="success",
                duration_ms=-1,
                timestamp=datetime.now(),
            )

    def test_trace_missing_required_field(self):
        """缺少必填字段应抛出 ValidationError"""
        from ai_agent.session.types import Trace

        with pytest.raises(ValidationError):
            Trace(
                tool="test",
                params={},
                result_status="success",
                duration_ms=100,
                timestamp=datetime.now(),
            )


class TestModelSerialization:
    """模型序列化测试"""

    def test_project_model_dump(self):
        """Project 可以序列化为 dict"""
        from ai_agent.session.types import Project

        now = datetime(2026, 3, 20, 10, 0, 0)
        project = Project(
            slug="my-agent",
            name="My Agent",
            path=Path("/tmp/test"),
            added_at=now,
        )

        data = project.model_dump()
        assert data["slug"] == "my-agent"
        assert data["name"] == "My Agent"
        assert isinstance(data["path"], Path)
        assert data["added_at"] == now

    def test_session_model_dump(self):
        """Session 可以序列化为 dict"""
        from ai_agent.session.types import Session

        now = datetime(2026, 3, 20, 10, 5, 0)
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="测试会话",
            created_at=now,
            message_count=10,
            trace_count=3,
        )

        data = session.model_dump()
        assert data["id"] == "20260320-001"
        assert data["title"] == "测试会话"
        assert data["message_count"] == 10

    def test_message_model_dump(self):
        """Message 可以序列化为 dict"""
        from ai_agent.session.types import Message

        now = datetime(2026, 3, 20, 10, 5, 1)
        message = Message(
            role="user",
            content="你好",
            timestamp=now,
        )

        data = message.model_dump()
        assert data["role"] == "user"
        assert data["content"] == "你好"

    def test_trace_model_dump(self):
        """Trace 可以序列化为 dict"""
        from ai_agent.session.types import Trace

        now = datetime(2026, 3, 20, 10, 5, 4)
        trace = Trace(
            id="trace-001",
            tool="read",
            params={"path": "./main.py"},
            result_status="success",
            duration_ms=45,
            timestamp=now,
        )

        data = trace.model_dump()
        assert data["id"] == "trace-001"
        assert data["tool"] == "read"
        assert data["params"] == {"path": "./main.py"}


class TestModelJSONSerialization:
    """JSON 序列化测试"""

    def test_project_model_json(self):
        """Project 可以序列化为 JSON"""
        from ai_agent.session.types import Project

        now = datetime(2026, 3, 20, 10, 0, 0)
        project = Project(
            slug="my-agent",
            name="My Agent",
            path=Path("/tmp/test"),
            added_at=now,
        )

        json_str = project.model_dump_json()
        assert "my-agent" in json_str
        assert "My Agent" in json_str

    def test_session_model_json(self):
        """Session 可以序列化为 JSON"""
        from ai_agent.session.types import Session

        now = datetime(2026, 3, 20, 10, 5, 0)
        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            created_at=now,
        )

        json_str = session.model_dump_json()
        assert "20260320-001" in json_str
        assert "新会话" in json_str

    def test_models_json_roundtrip(self):
        """所有模型可以 JSON 反序列化"""
        import json

        from ai_agent.session.types import Message, Project, Session, Trace

        now = datetime(2026, 3, 20, 10, 0, 0)

        # Project
        project = Project(
            slug="test",
            name="Test",
            path=Path("/tmp"),
            added_at=now,
        )
        project_data = json.loads(project.model_dump_json())
        project_restored = Project.model_validate(project_data)
        assert project_restored.slug == project.slug

        # Session
        session = Session(
            id="20260320-001",
            project_slug="test",
            created_at=now,
        )
        session_data = json.loads(session.model_dump_json())
        session_restored = Session.model_validate(session_data)
        assert session_restored.id == session.id

        # Message
        message = Message(
            role="user",
            content="test",
            timestamp=now,
        )
        message_data = json.loads(message.model_dump_json())
        message_restored = Message.model_validate(message_data)
        assert message_restored.content == message.content

        # Trace
        trace = Trace(
            id="trace-001",
            tool="test",
            params={"key": "value"},
            result_status="success",
            duration_ms=100,
            timestamp=now,
        )
        trace_data = json.loads(trace.model_dump_json())
        trace_restored = Trace.model_validate(trace_data)
        assert trace_restored.id == trace.id
