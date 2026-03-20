"""多项目会话管理模块

此模块提供多项目、多会话的完整管理功能。

核心组件:
- types: 核心数据类型定义
- project_manager: 项目注册与管理
- session_manager: 会话创建与恢复
- history_store: 历史记录存储
"""

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
