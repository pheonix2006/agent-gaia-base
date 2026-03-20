"""会话管理器模块

提供会话生命周期管理，包括创建、获取、更新和加载会话数据。

核心功能:
- create_session(project_slug, title) - 创建新会话
- get_session(project_slug, session_id) - 获取会话
- get_or_create_active_session(project_slug) - 获取或创建活跃会话
- list_sessions(project_slug) - 列出会话
- append_message(project_slug, session_id, message) - 追加消息
- append_trace(project_slug, session_id, trace) - 追加调用记录
- load_session_data(project_slug, session_id) - 加载完整数据
"""

import logging
from datetime import datetime
from typing import Any, TypedDict

from ai_agent.session.project import ProjectManager
from ai_agent.session.store import HistoryStore
from ai_agent.session.types import Message, Session, Trace

logger = logging.getLogger(__name__)


class SessionData(TypedDict):
    """会话完整数据的类型定义

    Attributes:
        session: 会话元数据
        messages: 消息列表
        traces: 调用记录列表
    """

    session: Session
    messages: list[Message]
    traces: list[Trace]


class SessionManager:
    """会话管理器

    负责会话的创建、获取、更新和完整数据加载。
    管理会话 ID 的生成和项目的活跃会话状态。

    Attributes:
        store: 历史记录存储实例
        project_manager: 项目管理器实例

    Example:
        >>> store = HistoryStore(Path.home() / ".agents" / "history")
        >>> pm = ProjectManager()
        >>> manager = SessionManager(store=store, project_manager=pm)
        >>> session = manager.create_session("my-project", "新会话")
        >>> print(session.id)  # "20260320-001"
    """

    def __init__(
        self,
        store: HistoryStore,
        project_manager: ProjectManager,
    ) -> None:
        """初始化会话管理器

        Args:
            store: 历史记录存储实例
            project_manager: 项目管理器实例
        """
        self.store = store
        self.project_manager = project_manager
        logger.debug("SessionManager initialized")

    def _generate_session_id(self, project_slug: str) -> str:
        """生成会话 ID

        格式为 YYYYMMDD-NNN，其中 NNN 是当天该项目的序号。

        Args:
            project_slug: 项目标识

        Returns:
            新的会话 ID
        """
        today = datetime.now()
        date_prefix = today.strftime("%Y%m%d")

        # 获取现有会话，找出当天最大序号
        existing_sessions = self.store.list_sessions(project_slug)
        max_seq = 0

        for session in existing_sessions:
            if session.id.startswith(date_prefix):
                try:
                    seq = int(session.id.split("-")[1])
                    if seq > max_seq:
                        max_seq = seq
                except (IndexError, ValueError):
                    continue

        # 生成新序号
        new_seq = max_seq + 1
        return f"{date_prefix}-{new_seq:03d}"

    def create_session(
        self,
        project_slug: str,
        title: str = "新会话",
    ) -> Session:
        """创建新会话

        生成新的会话 ID，创建会话元数据，并设置为项目的活跃会话。

        Args:
            project_slug: 项目标识
            title: 会话标题，默认为 "新会话"

        Returns:
            新创建的会话对象

        Raises:
            ValueError: 项目不存在时抛出
        """
        # 验证项目存在
        project = self.project_manager.get_project(project_slug)
        if project is None:
            raise ValueError(f"项目不存在: {project_slug}")

        # 生成会话 ID
        session_id = self._generate_session_id(project_slug)
        now = datetime.now()

        # 创建会话对象
        session = Session(
            id=session_id,
            project_slug=project_slug,
            title=title,
            created_at=now,
            message_count=0,
            trace_count=0,
        )

        # 持久化元数据
        self.store.save_session_metadata(project_slug, session)

        # 设置为活跃会话
        self.project_manager.set_active_session(project_slug, session_id)

        logger.info(f"Created session {session_id} for project {project_slug}")
        return session

    def get_session(
        self,
        project_slug: str,
        session_id: str,
    ) -> Session | None:
        """获取会话

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            会话对象，不存在则返回 None
        """
        return self.store.load_session_metadata(project_slug, session_id)

    def get_or_create_active_session(
        self,
        project_slug: str,
    ) -> Session:
        """获取或创建活跃会话

        如果项目有活跃会话，返回该会话；否则创建新会话。

        Args:
            project_slug: 项目标识

        Returns:
            活跃会话对象

        Raises:
            ValueError: 项目不存在时抛出
        """
        # 验证项目存在
        project = self.project_manager.get_project(project_slug)
        if project is None:
            raise ValueError(f"项目不存在: {project_slug}")

        # 检查是否有活跃会话
        if project.active_session:
            session = self.get_session(project_slug, project.active_session)
            if session is not None:
                return session

        # 创建新会话
        return self.create_session(project_slug)

    def list_sessions(self, project_slug: str) -> list[Session]:
        """列出项目的所有会话

        按更新时间倒序排列（最新的在前）。

        Args:
            project_slug: 项目标识

        Returns:
            会话列表
        """
        return self.store.list_sessions(project_slug)

    def append_message(
        self,
        project_slug: str,
        session_id: str,
        message: Message,
    ) -> None:
        """追加消息到会话

        同时更新会话的消息计数和更新时间。

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            message: 要追加的消息

        Raises:
            ValueError: 会话不存在时抛出
        """
        # 验证会话存在
        session = self.get_session(project_slug, session_id)
        if session is None:
            raise ValueError(f"会话不存在: {session_id}")

        # 追加消息
        self.store.append_message(project_slug, session_id, message)

        # 更新元数据
        updated_session = Session(
            id=session.id,
            project_slug=session.project_slug,
            title=session.title,
            created_at=session.created_at,
            updated_at=datetime.now(),
            message_count=session.message_count + 1,
            trace_count=session.trace_count,
        )
        self.store.save_session_metadata(project_slug, updated_session)

        logger.debug(f"Appended message to session {session_id}")

    def append_trace(
        self,
        project_slug: str,
        session_id: str,
        trace: Trace,
    ) -> None:
        """追加调用记录到会话

        同时更新会话的调用记录计数和更新时间。

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            trace: 要追加的调用记录

        Raises:
            ValueError: 会话不存在时抛出
        """
        # 验证会话存在
        session = self.get_session(project_slug, session_id)
        if session is None:
            raise ValueError(f"会话不存在: {session_id}")

        # 追加调用记录
        self.store.append_trace(project_slug, session_id, trace)

        # 更新元数据
        updated_session = Session(
            id=session.id,
            project_slug=session.project_slug,
            title=session.title,
            created_at=session.created_at,
            updated_at=datetime.now(),
            message_count=session.message_count,
            trace_count=session.trace_count + 1,
        )
        self.store.save_session_metadata(project_slug, updated_session)

        logger.debug(f"Appended trace to session {session_id}")

    def load_session_data(
        self,
        project_slug: str,
        session_id: str,
    ) -> SessionData | None:
        """加载完整会话数据

        包括会话元数据、所有消息和调用记录。

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            包含 session, messages, traces 的字典，
            会话不存在时返回 None
        """
        # 加载元数据
        session = self.get_session(project_slug, session_id)
        if session is None:
            return None

        # 加载消息和调用记录
        messages = self.store.load_messages(project_slug, session_id)
        traces = self.store.load_traces(project_slug, session_id)

        return {
            "session": session,
            "messages": messages,
            "traces": traces,
        }
