"""多项目会话管理模块

此模块提供多项目、多会话的完整管理功能。

核心组件:
- types: 核心数据类型定义
- config: 全局配置管理
- store: 历史记录存储
- project: 项目注册与管理
- session_manager: 会话创建与恢复
"""

from ai_agent.session.config import ConfigManager
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
    # 核心类型
    "Message",
    "Permission",
    "Project",
    "Session",
    "Trace",
    # 管理器
    "ConfigManager",
    "ProjectManager",
    "HistoryStore",
]
