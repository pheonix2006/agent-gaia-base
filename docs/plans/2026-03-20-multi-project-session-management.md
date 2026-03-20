# 多项目会话管理系统实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现支持多项目、多会话、历史记录和权限管理的完整系统

**Architecture:** 采用分层架构 - ProjectManager 管理项目注册，SessionManager 管理会话生命周期，HistoryStore 处理 JSONL 持久化，PermissionManager 实现三级权限回调。所有数据集中在 `~/.agents/` 目录。

**Tech Stack:** Python 3.11+, Pydantic v2, asyncio, JSONL, pathlib

---

## 模块依赖关系

```
┌─────────────────────────────────────────────────────────┐
│                      API Layer                          │
│  (FastAPI routes 调用 ProjectManager/SessionManager)    │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  SessionManager                         │
│  (会话创建、恢复、切换、消息追加)                         │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  ProjectManager                          │
│  (项目注册、查询、slug 映射)                             │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  HistoryStore                           │
│  (JSONL 读写、消息/调用记录追加)                         │
└─────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  PermissionManager                      │
│  (三级权限检查、回调确认)                                │
└─────────────────────────────────────────────────────────┘
```

---

## Task 1: 核心类型定义

**Files:**
- Create: `src/ai_agent/session/types.py`
- Test: `tests/unit/session/test_types.py`

**Step 1: Write the failing test**

```python
# tests/unit/session/test_types.py
"""会话管理类型定义测试"""

import pytest
from datetime import datetime
from pathlib import Path


class TestProject:
    """Project 模型测试"""

    def test_project_creation(self):
        """测试创建有效的 Project"""
        from ai_agent.session.types import Project

        project = Project(
            slug="my-agent",
            name="My Agent Project",
            path=Path("E:/Project/ai agent"),
            added_at=datetime(2026, 3, 20, 10, 0, 0),
        )

        assert project.slug == "my-agent"
        assert project.name == "My Agent Project"
        assert project.active_session is None

    def test_project_slug_validation(self):
        """测试 slug 格式验证"""
        from ai_agent.session.types import Project

        # 有效 slug
        Project(slug="my-agent", name="Test", path=Path("/test"))
        Project(slug="a", name="Test", path=Path("/test"))

        # 无效 slug
        with pytest.raises(ValueError):
            Project(slug="My Agent", name="Test", path=Path("/test"))


class TestSession:
    """Session 模型测试"""

    def test_session_creation(self):
        """测试创建有效的 Session"""
        from ai_agent.session.types import Session

        session = Session(
            id="20260320-001",
            project_slug="my-agent",
            title="调试会话",
            created_at=datetime(2026, 3, 20, 10, 5, 0),
        )

        assert session.id == "20260320-001"
        assert session.project_slug == "my-agent"
        assert session.message_count == 0

    def test_session_id_format(self):
        """测试 session ID 格式验证"""
        from ai_agent.session.types import Session

        # 有效 ID
        Session(id="20260320-001", project_slug="test")
        Session(id="20260101-999", project_slug="test")

        # 无效 ID
        with pytest.raises(ValueError):
            Session(id="2026-03-20-001", project_slug="test")  # 多了连字符


class TestMessage:
    """Message 模型测试"""

    def test_message_creation(self):
        """测试创建有效的 Message"""
        from ai_agent.session.types import Message

        msg = Message(
            role="user",
            content="你好",
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )

        assert msg.role == "user"
        assert msg.content == "你好"

    def test_message_role_validation(self):
        """测试 role 验证"""
        from ai_agent.session.types import Message

        # 有效 role
        for role in ["user", "assistant", "system", "tool"]:
            Message(role=role, content="test")

        # 无效 role
        with pytest.raises(ValueError):
            Message(role="invalid", content="test")


class TestTrace:
    """Trace 模型测试"""

    def test_trace_creation(self):
        """测试创建有效的 Trace"""
        from ai_agent.session.types import Trace

        trace = Trace(
            id="trace-001",
            tool="read",
            params={"path": "./test.py"},
            result_status="success",
            duration_ms=45,
            timestamp=datetime(2026, 3, 20, 10, 5, 4),
        )

        assert trace.tool == "read"
        assert trace.result_status == "success"
        assert trace.duration_ms == 45


class TestPermission:
    """Permission 枚举测试"""

    def test_permission_values(self):
        """测试权限值"""
        from ai_agent.session.types import Permission

        assert Permission.ALLOW == "allow"
        assert Permission.DENY == "deny"
        assert Permission.ASK == "ask"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/session/test_types.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'ai_agent.session'"

**Step 3: Write minimal implementation**

```python
# src/ai_agent/session/__init__.py
"""会话管理模块"""

from ai_agent.session.types import (
    Message,
    Permission,
    Project,
    Session,
    Trace,
)

__all__ = [
    "Message",
    "Permission",
    "Project",
    "Session",
    "Trace",
]
```

```python
# src/ai_agent/session/types.py
"""会话管理核心类型定义"""

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Permission(str, Enum):
    """权限级别"""

    ALLOW = "allow"  # 直接允许
    DENY = "deny"  # 直接拒绝
    ASK = "ask"  # 需要确认


class Project(BaseModel):
    """项目信息"""

    slug: str = Field(..., description="项目唯一标识，小写连字符格式")
    name: str = Field(..., description="项目友好名称")
    path: Path = Field(..., description="项目绝对路径")
    added_at: datetime = Field(..., description="添加时间")
    last_opened: datetime | None = Field(default=None, description="最后打开时间")
    active_session: str | None = Field(default=None, description="当前活跃会话 ID")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", v):
            raise ValueError("slug must be lowercase with hyphens, e.g. 'my-project'")
        return v


class Session(BaseModel):
    """会话信息"""

    id: str = Field(..., description="会话 ID，格式 YYYYMMDD-NNN")
    project_slug: str = Field(..., description="所属项目 slug")
    title: str = Field(default="新会话", description="会话标题")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")
    message_count: int = Field(default=0, description="消息数量")
    trace_count: int = Field(default=0, description="调用记录数量")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^\d{8}-\d{3}$", v):
            raise ValueError("session id must be format YYYYMMDD-NNN")
        return v


class Message(BaseModel):
    """对话消息"""

    role: str = Field(..., description="角色: user/assistant/system/tool")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(..., description="时间戳")
    name: str | None = Field(default=None, description="工具名称（role=tool 时）")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = {"user", "assistant", "system", "tool"}
        if v not in valid_roles:
            raise ValueError(f"role must be one of {valid_roles}")
        return v


class Trace(BaseModel):
    """工具调用记录"""

    id: str = Field(..., description="调用唯一标识")
    tool: str = Field(..., description="工具名称")
    params: dict[str, Any] = Field(default_factory=dict, description="调用参数")
    result_status: str = Field(
        default="success", description="结果状态: success/error/timeout"
    )
    result_preview: str | None = Field(default=None, description="结果预览")
    duration_ms: int = Field(..., ge=0, description="执行耗时（毫秒）")
    timestamp: datetime = Field(..., description="时间戳")

    @field_validator("result_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {"success", "error", "timeout"}
        if v not in valid_statuses:
            raise ValueError(f"result_status must be one of {valid_statuses}")
        return v
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/session/test_types.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/session/__init__.py src/ai_agent/session/types.py tests/unit/session/test_types.py
git commit -m "feat(session): add core type definitions (Project, Session, Message, Trace)"
```

---

## Task 2: 历史记录存储 (HistoryStore)

**Files:**
- Create: `src/ai_agent/session/store.py`
- Test: `tests/unit/session/test_store.py`

**Step 1: Write the failing test**

```python
# tests/unit/session/test_store.py
"""历史记录存储测试"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


class TestHistoryStore:
    """HistoryStore 测试"""

    def test_store_init(self):
        """测试初始化存储目录"""
        from ai_agent.session.store import HistoryStore

        with TemporaryDirectory() as tmpdir:
            store = HistoryStore(Path(tmpdir))
            assert store.base_path == Path(tmpdir)
            assert store.base_path.exists()

    def test_append_message(self):
        """测试追加消息"""
        from ai_agent.session.store import HistoryStore
        from ai_agent.session.types import Message

        with TemporaryDirectory() as tmpdir:
            store = HistoryStore(Path(tmpdir))

            msg = Message(
                role="user",
                content="你好",
                timestamp=datetime(2026, 3, 20, 10, 5, 1),
            )
            store.append_message("my-project", "20260320-001", msg)

            # 验证文件存在
            msg_file = (
                store.base_path / "my-project" / "20260320-001" / "messages.jsonl"
            )
            assert msg_file.exists()

            # 验证内容
            lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["role"] == "user"
            assert data["content"] == "你好"

    def test_append_trace(self):
        """测试追加调用记录"""
        from ai_agent.session.store import HistoryStore
        from ai_agent.session.types import Trace

        with TemporaryDirectory() as tmpdir:
            store = HistoryStore(Path(tmpdir))

            trace = Trace(
                id="trace-001",
                tool="read",
                params={"path": "./test.py"},
                result_status="success",
                duration_ms=45,
                timestamp=datetime(2026, 3, 20, 10, 5, 4),
            )
            store.append_trace("my-project", "20260320-001", trace)

            trace_file = (
                store.base_path / "my-project" / "20260320-001" / "traces.jsonl"
            )
            assert trace_file.exists()

            lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
            data = json.loads(lines[0])
            assert data["tool"] == "read"
            assert data["duration_ms"] == 45

    def test_load_messages(self):
        """测试加载消息"""
        from ai_agent.session.store import HistoryStore
        from ai_agent.session.types import Message

        with TemporaryDirectory() as tmpdir:
            store = HistoryStore(Path(tmpdir))

            # 写入多条消息
            for i in range(3):
                msg = Message(
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"消息 {i}",
                    timestamp=datetime(2026, 3, 20, 10, 5, i),
                )
                store.append_message("test-project", "20260320-001", msg)

            # 加载并验证
            messages = store.load_messages("test-project", "20260320-001")
            assert len(messages) == 3
            assert messages[0].content == "消息 0"
            assert messages[1].role == "assistant"

    def test_load_traces(self):
        """测试加载调用记录"""
        from ai_agent.session.store import HistoryStore
        from ai_agent.session.types import Trace

        with TemporaryDirectory() as tmpdir:
            store = HistoryStore(Path(tmpdir))

            # 写入多条记录
            for i in range(2):
                trace = Trace(
                    id=f"trace-{i:03d}",
                    tool="read" if i == 0 else "write",
                    params={},
                    duration_ms=10 * (i + 1),
                    timestamp=datetime(2026, 3, 20, 10, 5, i),
                )
                store.append_trace("test-project", "20260320-001", trace)

            traces = store.load_traces("test-project", "20260320-001")
            assert len(traces) == 2
            assert traces[0].tool == "read"
            assert traces[1].duration_ms == 20

    def test_save_and_load_session_metadata(self):
        """测试保存和加载会话元数据"""
        from ai_agent.session.store import HistoryStore
        from ai_agent.session.types import Session

        with TemporaryDirectory() as tmpdir:
            store = HistoryStore(Path(tmpdir))

            session = Session(
                id="20260320-001",
                project_slug="test-project",
                title="测试会话",
                created_at=datetime(2026, 3, 20, 10, 5, 0),
                message_count=3,
            )
            store.save_session_metadata("test-project", session)

            loaded = store.load_session_metadata("test-project", "20260320-001")
            assert loaded is not None
            assert loaded.title == "测试会话"
            assert loaded.message_count == 3

    def test_list_sessions(self):
        """测试列出会话"""
        from ai_agent.session.store import HistoryStore
        from ai_agent.session.types import Session

        with TemporaryDirectory() as tmpdir:
            store = HistoryStore(Path(tmpdir))

            # 创建多个会话
            for i in range(3):
                session = Session(
                    id=f"20260320-{i:03d}",
                    project_slug="test-project",
                    title=f"会话 {i}",
                    created_at=datetime(2026, 3, 20, 10, 5 + i, 0),
                )
                store.save_session_metadata("test-project", session)

            sessions = store.list_sessions("test-project")
            assert len(sessions) == 3
            # 应该按时间倒序排列
            assert sessions[0].id == "20260320-002"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/session/test_store.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'ai_agent.session.store'"

**Step 3: Write minimal implementation**

```python
# src/ai_agent/session/store.py
"""历史记录存储 - JSONL 格式"""

import json
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from ai_agent.session.types import Message, Session, Trace

T = TypeVar("T", Message, Trace)


class HistoryStore:
    """JSONL 格式历史记录存储"""

    def __init__(self, base_path: Path):
        """
        初始化存储

        Args:
            base_path: 存储根目录，如 ~/.agents/history/
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_session_dir(self, project_slug: str, session_id: str) -> Path:
        """获取会话目录路径"""
        return self.base_path / project_slug / session_id

    def _ensure_session_dir(self, project_slug: str, session_id: str) -> Path:
        """确保会话目录存在"""
        session_dir = self._get_session_dir(project_slug, session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def append_message(self, project_slug: str, session_id: str, message: Message) -> None:
        """
        追加消息到 messages.jsonl

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            message: 消息对象
        """
        session_dir = self._ensure_session_dir(project_slug, session_id)
        msg_file = session_dir / "messages.jsonl"

        with open(msg_file, "a", encoding="utf-8") as f:
            f.write(message.model_dump_json() + "\n")

    def append_trace(self, project_slug: str, session_id: str, trace: Trace) -> None:
        """
        追加调用记录到 traces.jsonl

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            trace: 调用记录对象
        """
        session_dir = self._ensure_session_dir(project_slug, session_id)
        trace_file = session_dir / "traces.jsonl"

        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(trace.model_dump_json() + "\n")

    def load_messages(self, project_slug: str, session_id: str) -> list[Message]:
        """
        加载会话的所有消息

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            消息列表
        """
        msg_file = self._get_session_dir(project_slug, session_id) / "messages.jsonl"
        if not msg_file.exists():
            return []

        messages = []
        with open(msg_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    messages.append(Message(**data))
        return messages

    def load_traces(self, project_slug: str, session_id: str) -> list[Trace]:
        """
        加载会话的所有调用记录

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            调用记录列表
        """
        trace_file = self._get_session_dir(project_slug, session_id) / "traces.jsonl"
        if not trace_file.exists():
            return []

        traces = []
        with open(trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    traces.append(Trace(**data))
        return traces

    def save_session_metadata(self, project_slug: str, session: Session) -> None:
        """
        保存会话元数据

        Args:
            project_slug: 项目标识
            session: 会话对象
        """
        session_dir = self._ensure_session_dir(project_slug, session.id)
        meta_file = session_dir / "metadata.json"

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(session.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    def load_session_metadata(
        self, project_slug: str, session_id: str
    ) -> Session | None:
        """
        加载会话元数据

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            会话对象，不存在则返回 None
        """
        meta_file = self._get_session_dir(project_slug, session_id) / "metadata.json"
        if not meta_file.exists():
            return None

        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Session(**data)

    def list_sessions(self, project_slug: str) -> list[Session]:
        """
        列出项目的所有会话

        Args:
            project_slug: 项目标识

        Returns:
            会话列表，按更新时间倒序排列
        """
        project_dir = self.base_path / project_slug
        if not project_dir.exists():
            return []

        sessions = []
        for session_dir in project_dir.iterdir():
            if session_dir.is_dir():
                session = self.load_session_metadata(project_slug, session_dir.name)
                if session:
                    sessions.append(session)

        # 按更新时间倒序排列
        sessions.sort(key=lambda s: s.updated_at or s.created_at, reverse=True)
        return sessions
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/session/test_store.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/session/store.py tests/unit/session/test_store.py
git commit -m "feat(session): add HistoryStore with JSONL persistence"
```

---

## Task 3: 项目管理器 (ProjectManager)

**Files:**
- Create: `src/ai_agent/session/project.py`
- Test: `tests/unit/session/test_project.py`

**Step 1: Write the failing test**

```python
# tests/unit/session/test_project.py
"""项目管理器测试"""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


class TestProjectManager:
    """ProjectManager 测试"""

    def test_init(self):
        """测试初始化"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))
            assert manager.config_file.exists()

    def test_register_project(self):
        """测试注册项目"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))

            project = manager.register_project(
                path=Path("E:/Project/ai agent"),
                name="My Agent Project",
            )

            assert project.slug == "my-agent-project"
            assert project.name == "My Agent Project"
            assert project.added_at is not None

    def test_register_duplicate_path(self):
        """测试注册重复路径"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))

            manager.register_project(Path("/test/path"), "Project A")
            # 相同路径应返回已有项目
            project = manager.register_project(Path("/test/path"), "Different Name")
            assert project.slug == "project-a"

    def test_slug_generation(self):
        """测试 slug 生成"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))

            # 中文名称
            p1 = manager.register_project(Path("/test/1"), "我的项目")
            assert p1.slug == "wo-de-xiang-mu"  # 拼音转换

            # 特殊字符
            p2 = manager.register_project(Path("/test/2"), "Test@Project!")
            assert p2.slug == "test-project"

    def test_get_project(self):
        """测试获取项目"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))

            manager.register_project(Path("/test/path"), "Test Project")

            # 通过 slug 获取
            project = manager.get_project("test-project")
            assert project is not None
            assert project.name == "Test Project"

            # 通过路径获取
            project = manager.get_by_path(Path("/test/path"))
            assert project is not None

    def test_list_projects(self):
        """测试列出项目"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))

            manager.register_project(Path("/test/a"), "Project A")
            manager.register_project(Path("/test/b"), "Project B")

            projects = manager.list_projects()
            assert len(projects) == 2

    def test_update_last_opened(self):
        """测试更新最后打开时间"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))

            project = manager.register_project(Path("/test/path"), "Test")
            assert project.last_opened is None

            manager.update_last_opened("test")
            updated = manager.get_project("test")
            assert updated is not None
            assert updated.last_opened is not None

    def test_set_active_session(self):
        """测试设置活跃会话"""
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            manager = ProjectManager(Path(tmpdir))

            manager.register_project(Path("/test"), "Test")
            manager.set_active_session("test", "20260320-001")

            project = manager.get_project("test")
            assert project is not None
            assert project.active_session == "20260320-001"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/session/test_project.py -v
```

Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/ai_agent/session/project.py
"""项目管理器"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_agent.session.types import Project


def _generate_slug(name: str) -> str:
    """
    从项目名生成 slug

    - 转小写
    - 非字母数字转连字符
    - 连续连字符合并
    - 去除首尾连字符
    """
    # 简单处理：只保留字母数字，其他转连字符
    slug = ""
    for char in name.lower():
        if char.isalnum():
            slug += char
        else:
            slug += "-"

    # 合并连续连字符
    slug = re.sub(r"-+", "-", slug)
    # 去除首尾
    slug = slug.strip("-")

    return slug or "project"


def _slugify_chinese(name: str) -> str:
    """
    处理中文名称，转换为拼音 slug

    如果没有 pypinyin 包，则使用哈希作为备用
    """
    try:
        from pypinyin import lazy_pinyin

        pinyin_parts = lazy_pinyin(name)
        pinyin_str = "-".join(pinyin_parts)
        return _generate_slug(pinyin_str)
    except ImportError:
        # 备用方案：使用 hash
        return f"project-{abs(hash(name)) % 10000:04d}"


class ProjectManager:
    """项目注册与管理"""

    def __init__(self, config_dir: Path):
        """
        初始化项目管理器

        Args:
            config_dir: 配置目录，如 ~/.agents/
        """
        self.config_dir = config_dir
        self.config_file = config_dir / "projects.json"
        self._ensure_config()

    def _ensure_config(self) -> None:
        """确保配置文件存在"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            self._save_projects({})

    def _load_projects(self) -> dict[str, dict[str, Any]]:
        """加载项目配置"""
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_projects(self, projects: dict[str, dict[str, Any]]) -> None:
        """保存项目配置"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)

    def _project_to_dict(self, project: Project) -> dict[str, Any]:
        """Project 对象转字典"""
        return {
            "name": project.name,
            "path": str(project.path),
            "added_at": project.added_at.isoformat(),
            "last_opened": project.last_opened.isoformat()
            if project.last_opened
            else None,
            "active_session": project.active_session,
        }

    def _dict_to_project(self, slug: str, data: dict[str, Any]) -> Project:
        """字典转 Project 对象"""
        return Project(
            slug=slug,
            name=data["name"],
            path=Path(data["path"]),
            added_at=datetime.fromisoformat(data["added_at"]),
            last_opened=datetime.fromisoformat(data["last_opened"])
            if data.get("last_opened")
            else None,
            active_session=data.get("active_session"),
        )

    def register_project(self, path: Path, name: str) -> Project:
        """
        注册新项目

        如果路径已存在，返回已有项目

        Args:
            path: 项目绝对路径
            name: 项目友好名称

        Returns:
            Project 对象
        """
        path = path.resolve()
        projects = self._load_projects()

        # 检查路径是否已存在
        for slug, data in projects.items():
            if Path(data["path"]).resolve() == path:
                return self._dict_to_project(slug, data)

        # 生成 slug
        base_slug = _slugify_chinese(name) if any(
            "\u4e00" <= c <= "\u9fff" for c in name
        ) else _generate_slug(name)

        # 确保 slug 唯一
        slug = base_slug
        counter = 1
        while slug in projects:
            slug = f"{base_slug}-{counter}"
            counter += 1

        # 创建项目
        project = Project(
            slug=slug,
            name=name,
            path=path,
            added_at=datetime.now(timezone.utc),
        )

        projects[slug] = self._project_to_dict(project)
        self._save_projects(projects)

        return project

    def get_project(self, slug: str) -> Project | None:
        """通过 slug 获取项目"""
        projects = self._load_projects()
        if slug in projects:
            return self._dict_to_project(slug, projects[slug])
        return None

    def get_by_path(self, path: Path) -> Project | None:
        """通过路径获取项目"""
        path = path.resolve()
        projects = self._load_projects()

        for slug, data in projects.items():
            if Path(data["path"]).resolve() == path:
                return self._dict_to_project(slug, data)
        return None

    def list_projects(self) -> list[Project]:
        """列出所有项目"""
        projects = self._load_projects()
        result = [self._dict_to_project(slug, data) for slug, data in projects.items()]
        # 按最后打开时间排序
        result.sort(key=lambda p: p.last_opened or p.added_at, reverse=True)
        return result

    def update_last_opened(self, slug: str) -> None:
        """更新最后打开时间"""
        projects = self._load_projects()
        if slug in projects:
            projects[slug]["last_opened"] = datetime.now(timezone.utc).isoformat()
            self._save_projects(projects)

    def set_active_session(self, slug: str, session_id: str) -> None:
        """设置活跃会话"""
        projects = self._load_projects()
        if slug in projects:
            projects[slug]["active_session"] = session_id
            self._save_projects(projects)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/session/test_project.py -v
```

Expected: PASS（可能需要安装 pypinyin）

**Step 5: Commit**

```bash
git add src/ai_agent/session/project.py tests/unit/session/test_project.py
git commit -m "feat(session): add ProjectManager with registration and lookup"
```

---

## Task 4: 会话管理器 (SessionManager)

**Files:**
- Create: `src/ai_agent/session/manager.py`
- Test: `tests/unit/session/test_manager.py`

**Step 1: Write the failing test**

```python
# tests/unit/session/test_manager.py
"""会话管理器测试"""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


class TestSessionManager:
    """SessionManager 测试"""

    def test_create_session(self):
        """测试创建会话"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            pm = ProjectManager(Path(tmpdir))
            sm = SessionManager(Path(tmpdir))

            project = pm.register_project(Path("/test"), "Test Project")
            session = sm.create_session(project.slug)

            assert session.id.startswith(datetime.now().strftime("%Y%m%d"))
            assert session.project_slug == project.slug
            assert "Test Project" in session.title or session.title == "新会话"

    def test_session_id_sequence(self):
        """测试会话 ID 序号递增"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            pm = ProjectManager(Path(tmpdir))
            sm = SessionManager(Path(tmpdir))

            project = pm.register_project(Path("/test"), "Test")

            s1 = sm.create_session(project.slug)
            s2 = sm.create_session(project.slug)

            assert s1.id.endswith("-001")
            assert s2.id.endswith("-002")

    def test_get_or_create_active_session(self):
        """测试获取或创建活跃会话"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            pm = ProjectManager(Path(tmpdir))
            sm = SessionManager(Path(tmpdir))

            project = pm.register_project(Path("/test"), "Test")

            # 首次调用，创建新会话
            session1 = sm.get_or_create_active_session(project.slug)
            assert session1 is not None

            # 再次调用，返回同一会话
            session2 = sm.get_or_create_active_session(project.slug)
            assert session2.id == session1.id

    def test_append_message_updates_count(self):
        """测试追加消息更新计数"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager
        from ai_agent.session.types import Message

        with TemporaryDirectory() as tmpdir:
            pm = ProjectManager(Path(tmpdir))
            sm = SessionManager(Path(tmpdir))

            project = pm.register_project(Path("/test"), "Test")
            session = sm.create_session(project.slug)

            msg = Message(
                role="user",
                content="测试",
                timestamp=datetime.now(),
            )
            sm.append_message(project.slug, session.id, msg)

            updated = sm.get_session(project.slug, session.id)
            assert updated is not None
            assert updated.message_count == 1

    def test_list_sessions(self):
        """测试列出会话"""
        from ai_agent.session.manager import SessionManager
        from ai_agent.session.project import ProjectManager

        with TemporaryDirectory() as tmpdir:
            pm = ProjectManager(Path(tmpdir))
            sm = SessionManager(Path(tmpdir))

            project = pm.register_project(Path("/test"), "Test")

            sm.create_session(project.slug)
            sm.create_session(project.slug)

            sessions = sm.list_sessions(project.slug)
            assert len(sessions) == 2
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/session/test_manager.py -v
```

Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/ai_agent/session/manager.py
"""会话管理器"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_agent.session.project import ProjectManager
from ai_agent.session.store import HistoryStore
from ai_agent.session.types import Message, Session, Trace


class SessionManager:
    """会话生命周期管理"""

    def __init__(self, config_dir: Path):
        """
        初始化会话管理器

        Args:
            config_dir: 配置目录，如 ~/.agents/
        """
        self.config_dir = config_dir
        self.store = HistoryStore(config_dir / "history")
        self.project_manager = ProjectManager(config_dir)

    def _generate_session_id(self, project_slug: str) -> str:
        """
        生成会话 ID

        格式: YYYYMMDD-NNN
        """
        today = datetime.now().strftime("%Y%m%d")
        sessions = self.store.list_sessions(project_slug)

        # 找今天最大的序号
        max_seq = 0
        for session in sessions:
            if session.id.startswith(today):
                try:
                    seq = int(session.id.split("-")[1])
                    max_seq = max(max_seq, seq)
                except (IndexError, ValueError):
                    pass

        return f"{today}-{max_seq + 1:03d}"

    def create_session(
        self, project_slug: str, title: str | None = None
    ) -> Session:
        """
        创建新会话

        Args:
            project_slug: 项目标识
            title: 会话标题（可选）

        Returns:
            新创建的 Session
        """
        project = self.project_manager.get_project(project_slug)
        if not project:
            raise ValueError(f"Project not found: {project_slug}")

        session_id = self._generate_session_id(project_slug)
        session_title = title or f"新会话"

        session = Session(
            id=session_id,
            project_slug=project_slug,
            title=session_title,
            created_at=datetime.now(timezone.utc),
        )

        self.store.save_session_metadata(project_slug, session)
        self.project_manager.set_active_session(project_slug, session_id)

        return session

    def get_session(self, project_slug: str, session_id: str) -> Session | None:
        """获取会话"""
        return self.store.load_session_metadata(project_slug, session_id)

    def get_or_create_active_session(self, project_slug: str) -> Session:
        """
        获取活跃会话，不存在则创建

        Args:
            project_slug: 项目标识

        Returns:
            Session 对象
        """
        project = self.project_manager.get_project(project_slug)
        if not project:
            raise ValueError(f"Project not found: {project_slug}")

        if project.active_session:
            session = self.get_session(project_slug, project.active_session)
            if session:
                return session

        # 没有活跃会话，创建新的
        return self.create_session(project_slug)

    def list_sessions(self, project_slug: str) -> list[Session]:
        """列出项目的所有会话"""
        return self.store.list_sessions(project_slug)

    def append_message(
        self, project_slug: str, session_id: str, message: Message
    ) -> None:
        """
        追加消息到会话

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            message: 消息对象
        """
        self.store.append_message(project_slug, session_id, message)

        # 更新会话计数
        session = self.get_session(project_slug, session_id)
        if session:
            session.message_count += 1
            session.updated_at = datetime.now(timezone.utc)
            self.store.save_session_metadata(project_slug, session)

    def append_trace(
        self, project_slug: str, session_id: str, trace: Trace
    ) -> None:
        """
        追加调用记录到会话

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            trace: 调用记录对象
        """
        self.store.append_trace(project_slug, session_id, trace)

        # 更新会话计数
        session = self.get_session(project_slug, session_id)
        if session:
            session.trace_count += 1
            session.updated_at = datetime.now(timezone.utc)
            self.store.save_session_metadata(project_slug, session)

    def load_session_data(
        self, project_slug: str, session_id: str
    ) -> dict[str, Any]:
        """
        加载会话完整数据

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            包含 metadata, messages, traces 的字典
        """
        session = self.get_session(project_slug, session_id)
        if not session:
            raise ValueError(f"Session not found: {project_slug}/{session_id}")

        return {
            "metadata": session,
            "messages": self.store.load_messages(project_slug, session_id),
            "traces": self.store.load_traces(project_slug, session_id),
        }
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/session/test_manager.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/session/manager.py tests/unit/session/test_manager.py
git commit -m "feat(session): add SessionManager with lifecycle management"
```

---

## Task 5: 权限管理器增强

**Files:**
- Modify: `src/ai_agent/tools/filesystem/permissions.py`
- Test: `tests/unit/tools/filesystem/test_permissions.py`

**Step 1: Write the failing test**

```python
# tests/unit/tools/filesystem/test_permissions.py
"""权限管理器测试"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

import pytest


class TestPermissionLevel:
    """权限级别测试"""

    def test_permission_values(self):
        """测试权限枚举值"""
        from ai_agent.session.types import Permission

        assert Permission.ALLOW.value == "allow"
        assert Permission.DENY.value == "deny"
        assert Permission.ASK.value == "ask"


class TestPermissionManagerV2:
    """增强版权限管理器测试"""

    def test_check_allow_path(self):
        """测试允许路径"""
        from ai_agent.tools.filesystem.permissions import PermissionManager

        with TemporaryDirectory() as tmpdir:
            pm = PermissionManager()
            pm.allow_path(Path(tmpdir))

            result = pm.check(Path(tmpdir) / "test.txt", "read")
            assert result == "allow"

    def test_check_deny_path(self):
        """测试拒绝路径"""
        from ai_agent.tools.filesystem.permissions import PermissionManager

        with TemporaryDirectory() as tmpdir:
            pm = PermissionManager()
            pm.deny_path(Path(tmpdir))

            result = pm.check(Path(tmpdir) / "secret.txt", "read")
            assert result == "deny"

    def test_check_ask_default(self):
        """测试默认询问"""
        from ai_agent.tools.filesystem.permissions import PermissionManager

        pm = PermissionManager(default="ask")

        result = pm.check(Path("/unknown/path"), "write")
        assert result == "ask"

    def test_check_by_operation(self):
        """测试按操作类型检查"""
        from ai_agent.tools.filesystem.permissions import PermissionManager

        with TemporaryDirectory() as tmpdir:
            pm = PermissionManager()
            pm.allow_path(Path(tmpdir), operations=["read"])  # 只允许读
            pm.deny_path(Path(tmpdir), operations=["write"])  # 拒绝写

            assert pm.check(Path(tmpdir) / "test.txt", "read") == "allow"
            assert pm.check(Path(tmpdir) / "test.txt", "write") == "deny"

    @pytest.mark.asyncio
    async def test_request_with_callback(self):
        """测试带回调的请求"""
        from ai_agent.tools.filesystem.permissions import PermissionManager

        callback = AsyncMock(return_value=True)
        pm = PermissionManager(default="ask", callback=callback)

        result = await pm.request(Path("/test"), "read")
        assert result is True
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_allow_without_callback(self):
        """测试 allow 不触发回调"""
        from ai_agent.tools.filesystem.permissions import PermissionManager

        callback = AsyncMock(return_value=True)
        pm = PermissionManager(callback=callback)

        with TemporaryDirectory() as tmpdir:
            pm.allow_path(Path(tmpdir))
            result = await pm.request(Path(tmpdir) / "test.txt", "read")

            assert result is True
            callback.assert_not_called()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/tools/filesystem/test_permissions.py -v
```

Expected: FAIL (部分方法不存在)

**Step 3: Read existing implementation and modify**

先读取现有实现，然后增强它。

**Step 4: Modify implementation**

修改 `src/ai_agent/tools/filesystem/permissions.py`，添加：
- 三级权限 (allow/deny/ask)
- 按操作类型区分
- 异步回调支持

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/unit/tools/filesystem/test_permissions.py -v
```

**Step 6: Commit**

```bash
git add src/ai_agent/tools/filesystem/permissions.py tests/unit/tools/filesystem/test_permissions.py
git commit -m "feat(permissions): add three-level permission with callback support"
```

---

## Task 6: 全局配置管理

**Files:**
- Create: `src/ai_agent/session/config.py`
- Test: `tests/unit/session/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/session/test_config.py
"""全局配置管理测试"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


class TestConfigManager:
    """ConfigManager 测试"""

    def test_init_creates_default(self):
        """测试初始化创建默认配置"""
        from ai_agent.session.config import ConfigManager

        with TemporaryDirectory() as tmpdir:
            cm = ConfigManager(Path(tmpdir))
            assert cm.config_file.exists()

            config = cm.load()
            assert "llm" in config

    def test_get_llm_config(self):
        """测试获取 LLM 配置"""
        from ai_agent.session.config import ConfigManager

        with TemporaryDirectory() as tmpdir:
            cm = ConfigManager(Path(tmpdir))

            llm_config = cm.get_llm_config()
            assert "provider" in llm_config

    def test_set_api_key(self):
        """测试设置 API Key"""
        from ai_agent.session.config import ConfigManager

        with TemporaryDirectory() as tmpdir:
            cm = ConfigManager(Path(tmpdir))

            cm.set_api_key("openai", "sk-test-123")

            config = cm.load()
            assert config["llm"]["api_key"] == "sk-test-123"

    def test_project_override(self):
        """测试项目级配置覆盖"""
        from ai_agent.session.config import ConfigManager

        with TemporaryDirectory() as tmpdir:
            cm = ConfigManager(Path(tmpdir))
            cm.set_api_key("openai", "sk-global")

            # 创建项目覆盖配置
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            override_file = project_dir / ".agent" / "config.override.json"
            override_file.parent.mkdir(parents=True, exist_ok=True)
            override_file.write_text('{"llm": {"model": "gpt-4-turbo"}}')

            merged = cm.get_merged_config(project_dir)
            assert merged["llm"]["model"] == "gpt-4-turbo"
            assert merged["llm"]["api_key"] == "sk-global"  # 保留全局
```

**Step 2-5: Implement and test**

实现 `src/ai_agent/session/config.py`

**Step 6: Commit**

```bash
git add src/ai_agent/session/config.py tests/unit/session/test_config.py
git commit -m "feat(session): add ConfigManager with project override"
```

---

## Task 7: 更新模块导出

**Files:**
- Modify: `src/ai_agent/session/__init__.py`
- Modify: `src/ai_agent/__init__.py`

**Step 1: Update exports**

```python
# src/ai_agent/session/__init__.py
"""会话管理模块"""

from ai_agent.session.config import ConfigManager
from ai_agent.session.manager import SessionManager
from ai_agent.session.project import ProjectManager
from ai_agent.session.store import HistoryStore
from ai_agent.session.types import (
    Message,
    Permission,
    Project,
    Session,
    Trace,
)

__all__ = [
    "ConfigManager",
    "HistoryStore",
    "Message",
    "Permission",
    "Project",
    "ProjectManager",
    "Session",
    "SessionManager",
    "Trace",
]
```

**Step 2: Commit**

```bash
git add src/ai_agent/session/__init__.py src/ai_agent/__init__.py
git commit -m "feat(session): export session module"
```

---

## Task 8: 集成测试

**Files:**
- Create: `tests/integration/session/test_e2e.py`

**Step 1: Write integration test**

```python
# tests/integration/session/test_e2e.py
"""会话系统端到端测试"""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


class TestSessionE2E:
    """端到端测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        from ai_agent.session import (
            ConfigManager,
            Message,
            ProjectManager,
            SessionManager,
            Trace,
        )

        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            # 1. 初始化
            pm = ProjectManager(config_dir)
            sm = SessionManager(config_dir)

            # 2. 注册项目
            project = pm.register_project(
                Path("/home/user/my-project"),
                "我的项目",
            )
            assert project.slug == "wo-de-xiang-mu"

            # 3. 创建会话
            session = sm.create_session(project.slug, "第一次调试")
            assert session.id.startswith(datetime.now().strftime("%Y%m%d"))

            # 4. 追加消息
            msg1 = Message(
                role="user",
                content="帮我分析这个项目",
                timestamp=datetime.now(),
            )
            sm.append_message(project.slug, session.id, msg1)

            msg2 = Message(
                role="assistant",
                content="好的，让我看看...",
                timestamp=datetime.now(),
            )
            sm.append_message(project.slug, session.id, msg2)

            # 5. 追加调用记录
            trace = Trace(
                id="trace-001",
                tool="read",
                params={"path": "./main.py"},
                duration_ms=50,
                timestamp=datetime.now(),
            )
            sm.append_trace(project.slug, session.id, trace)

            # 6. 加载并验证
            data = sm.load_session_data(project.slug, session.id)
            assert len(data["messages"]) == 2
            assert len(data["traces"]) == 1
            assert data["metadata"].message_count == 2
            assert data["metadata"].trace_count == 1

            # 7. 列出会话
            sessions = sm.list_sessions(project.slug)
            assert len(sessions) == 1
```

**Step 2: Run test**

```bash
uv run pytest tests/integration/session/test_e2e.py -v
```

**Step 3: Commit**

```bash
git add tests/integration/session/test_e2e.py
git commit -m "test(session): add end-to-end integration test"
```

---

## 执行顺序总结

| Task | 模块 | 依赖 | 预计时间 |
|------|------|------|----------|
| 1 | types.py | 无 | 15 min |
| 2 | store.py | Task 1 | 20 min |
| 3 | project.py | Task 1 | 20 min |
| 4 | manager.py | Task 1-3 | 25 min |
| 5 | permissions.py | Task 1 | 15 min |
| 6 | config.py | 无 | 15 min |
| 7 | exports | Task 1-6 | 5 min |
| 8 | e2e test | Task 1-7 | 15 min |

**总计: ~2 小时**

---

## 子代理开发验证流程

**每个 Task 必须经过以下 4 个阶段验证：**

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: 开发 Agent (Developer)                            │
│  - 编写失败测试                                               │
│  - 实现最小代码                                               │
│  - 运行测试确认通过                                           │
│  - 输出: 代码 + 测试                                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  Phase 2: 质量验证 Agent (QA)                                │
│  - 类型检查: mypy --strict                                   │
│  - 代码风格: ruff check                                       │
│  - 测试覆盖率: pytest --cov                                   │
│  - 输出: 质量报告 + 问题列表                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │ 有问题则返回 Phase 1
┌─────────────────────▼───────────────────────────────────────┐
│  Phase 3: Code Review Agent                                  │
│  - 检查 SOLID/KISS/DRY/YAGNI                                 │
│  - 检查代码可读性和注释                                        │
│  - 检查测试覆盖边界情况                                        │
│  - 输出: Review 通过/需要修改                                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ 需要修改则返回 Phase 1
┌─────────────────────▼───────────────────────────────────────┐
│  Phase 4: 功能验证 Agent (Verifier)                          │
│  - 运行完整测试套件                                            │
│  - 验证功能符合设计文档                                        │
│  - 验证与其他模块的集成                                        │
│  - 输出: 功能验证通过/失败                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ 失败则返回 Phase 1 修复
                      ▼
              ✅ Task 完成，Commit
```

### Phase 验证命令

```bash
# Phase 2: 质量验证
uv run mypy src/ai_agent/session/ --strict
uv run ruff check src/ai_agent/session/
uv run pytest tests/unit/session/ --cov=src/ai_agent/session/ --cov-report=term-missing

# Phase 4: 功能验证
uv run pytest tests/unit/session/ tests/integration/session/ -v
```

### 迭代修复规则

1. **任何 Phase 失败** → 返回 Phase 1 修复
2. **修复次数上限** → 3 次，超过则暂停请求人工介入
3. **每次修复后** → 重新走完所有 Phase
4. **只有全部通过** → 才能 Commit 并进入下一个 Task

---

## 后续任务（不在本阶段）

- [ ] API routes 集成
- [ ] ReActAgent 集成 SessionManager
- [ ] Write/Edit 工具实现
- [ ] UI 接口对接
