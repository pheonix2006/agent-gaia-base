"""历史记录存储模块

此模块提供 JSONL 格式的历史记录存储功能。

核心功能:
- 消息记录的追加和加载
- 调用记录的追加和加载
- 会话元数据的保存和加载
- 会话列表查询

文件结构:
~/.agents/history/<project-slug>/<session-id>/
├── metadata.json    # 会话元数据
├── messages.jsonl   # 对话记录（每行一个 JSON）
└── traces.jsonl     # 工具调用记录（每行一个 JSON）
"""

import json
import logging
from pathlib import Path
from typing import Any

from ai_agent.session.types import Message, Session, Trace

logger = logging.getLogger(__name__)


class HistoryStore:
    """历史记录存储类

    负责管理会话的持久化存储，包括消息、调用记录和元数据。

    Attributes:
        base_path: 存储根目录

    Example:
        >>> store = HistoryStore(Path.home() / ".agents" / "history")
        >>> store.append_message("my-agent", "20260320-001", message)
        >>> messages = store.load_messages("my-agent", "20260320-001")
    """

    def __init__(self, base_path: Path) -> None:
        """初始化 HistoryStore

        自动创建存储根目录。

        Args:
            base_path: 存储根目录
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"HistoryStore initialized with base_path: {base_path}")

    def _get_session_dir(self, project_slug: str, session_id: str) -> Path:
        """获取会话目录路径

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            会话目录路径
        """
        return self.base_path / project_slug / session_id

    def _get_messages_file(self, project_slug: str, session_id: str) -> Path:
        """获取消息文件路径

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            messages.jsonl 文件路径
        """
        return self._get_session_dir(project_slug, session_id) / "messages.jsonl"

    def _get_traces_file(self, project_slug: str, session_id: str) -> Path:
        """获取调用记录文件路径

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            traces.jsonl 文件路径
        """
        return self._get_session_dir(project_slug, session_id) / "traces.jsonl"

    def _get_metadata_file(self, project_slug: str, session_id: str) -> Path:
        """获取元数据文件路径

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            metadata.json 文件路径
        """
        return self._get_session_dir(project_slug, session_id) / "metadata.json"

    def append_message(
        self, project_slug: str, session_id: str, message: Message
    ) -> None:
        """追加消息到 messages.jsonl

        以 JSONL 格式追加消息，每条消息占一行。

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            message: 要追加的消息
        """
        session_dir = self._get_session_dir(project_slug, session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        messages_file = self._get_messages_file(project_slug, session_id)
        message_json = message.model_dump_json()

        with open(messages_file, "a", encoding="utf-8") as f:
            f.write(message_json + "\n")

        logger.debug(f"Appended message to {messages_file}")

    def load_messages(self, project_slug: str, session_id: str) -> list[Message]:
        """加载会话的所有消息

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            消息列表，按追加顺序排列。如果文件不存在则返回空列表。
        """
        messages_file = self._get_messages_file(project_slug, session_id)

        if not messages_file.exists():
            return []

        messages: list[Message] = []
        with open(messages_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    messages.append(Message.model_validate(data))

        return messages

    def append_trace(self, project_slug: str, session_id: str, trace: Trace) -> None:
        """追加调用记录到 traces.jsonl

        以 JSONL 格式追加调用记录，每条记录占一行。

        Args:
            project_slug: 项目标识
            session_id: 会话 ID
            trace: 要追加的调用记录
        """
        session_dir = self._get_session_dir(project_slug, session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        traces_file = self._get_traces_file(project_slug, session_id)
        trace_json = trace.model_dump_json()

        with open(traces_file, "a", encoding="utf-8") as f:
            f.write(trace_json + "\n")

        logger.debug(f"Appended trace to {traces_file}")

    def load_traces(self, project_slug: str, session_id: str) -> list[Trace]:
        """加载会话的所有调用记录

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            调用记录列表，按追加顺序排列。如果文件不存在则返回空列表。
        """
        traces_file = self._get_traces_file(project_slug, session_id)

        if not traces_file.exists():
            return []

        traces: list[Trace] = []
        with open(traces_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    traces.append(Trace.model_validate(data))

        return traces

    def save_session_metadata(
        self, project_slug: str, session: Session
    ) -> None:
        """保存会话元数据

        以 JSON 格式保存会话元数据到 metadata.json。

        Args:
            project_slug: 项目标识
            session: 要保存的会话对象
        """
        session_dir = self._get_session_dir(project_slug, session.id)
        session_dir.mkdir(parents=True, exist_ok=True)

        metadata_file = self._get_metadata_file(project_slug, session.id)
        metadata_json = session.model_dump_json(indent=2)

        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write(metadata_json)

        logger.debug(f"Saved session metadata to {metadata_file}")

    def load_session_metadata(
        self, project_slug: str, session_id: str
    ) -> Session | None:
        """加载会话元数据

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            会话对象，如果文件不存在则返回 None。
        """
        metadata_file = self._get_metadata_file(project_slug, session_id)

        if not metadata_file.exists():
            return None

        with open(metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Session.model_validate(data)

    def list_sessions(self, project_slug: str) -> list[Session]:
        """列出项目的所有会话

        按更新时间倒序排列（最新的在前）。
        如果没有更新时间则使用创建时间。

        Args:
            project_slug: 项目标识

        Returns:
            会话列表，按更新时间倒序排列。
        """
        project_dir = self.base_path / project_slug

        if not project_dir.exists():
            return []

        sessions: list[Session] = []

        for session_dir in project_dir.iterdir():
            if not session_dir.is_dir():
                continue

            metadata_file = session_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = Session.model_validate(data)
                sessions.append(session)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to load metadata from {metadata_file}: {e}")
                continue

        # 按更新时间倒序排列，没有更新时间则使用创建时间
        def get_sort_time(session: Session) -> Any:
            return session.updated_at or session.created_at

        sessions.sort(key=get_sort_time, reverse=True)

        return sessions

    def delete_session(self, project_slug: str, session_id: str) -> bool:
        """删除会话

        删除会话目录及其所有文件（metadata.json, messages.jsonl, traces.jsonl）。

        Args:
            project_slug: 项目标识
            session_id: 会话 ID

        Returns:
            bool: 删除成功返回 True，会话不存在返回 False
        """
        import shutil

        session_dir = self._get_session_dir(project_slug, session_id)

        if not session_dir.exists():
            logger.debug(f"Session directory does not exist: {session_dir}")
            return False

        try:
            shutil.rmtree(session_dir)
            logger.info(f"Deleted session directory: {session_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session directory {session_dir}: {e}")
            return False
