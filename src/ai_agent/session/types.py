"""多项目会话管理系统的核心类型定义

此模块定义了所有核心数据结构，包括：
- Permission: 权限枚举
- Project: 项目模型
- Session: 会话模型
- Message: 消息模型
- Trace: 工具调用记录模型
"""

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Permission(str, Enum):
    """三级权限枚举

    Attributes:
        ALLOW: 直接允许执行
        DENY: 直接拒绝执行
        ASK: 需要用户确认
    """

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Project(BaseModel):
    """项目模型

    表示一个注册到系统中的工程项目。

    Attributes:
        slug: 项目唯一标识，小写连字符格式
        name: 项目友好名称
        path: 项目绝对路径
        added_at: 添加时间
        last_opened: 最后打开时间（可选）
        active_session: 当前活跃会话 ID（可选）
    """

    slug: str = Field(..., description="项目唯一标识，小写连字符格式")
    name: str = Field(..., description="项目友好名称")
    path: Path = Field(..., description="项目绝对路径")
    added_at: datetime = Field(..., description="添加时间")
    last_opened: datetime | None = Field(default=None, description="最后打开时间")
    active_session: str | None = Field(default=None, description="当前活跃会话 ID")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """验证 slug 格式：小写字母、数字，用连字符分隔"""
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", v):
            raise ValueError(
                "slug 必须是小写字母、数字，用连字符分隔（如: my-agent, project123）"
            )
        return v


class Session(BaseModel):
    """会话模型

    表示一个对话会话。

    Attributes:
        id: 会话 ID，格式 YYYYMMDD-NNN
        project_slug: 所属项目 slug
        title: 会话标题
        created_at: 创建时间
        updated_at: 更新时间（可选）
        message_count: 消息数量
        trace_count: 调用记录数量
    """

    id: str = Field(..., description="会话 ID，格式 YYYYMMDD-NNN")
    project_slug: str = Field(..., description="所属项目 slug")
    title: str = Field(default="新会话", description="会话标题")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")
    message_count: int = Field(default=0, ge=0, description="消息数量")
    trace_count: int = Field(default=0, ge=0, description="调用记录数量")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """验证 Session ID 格式：YYYYMMDD-NNN"""
        if not re.match(r"^\d{8}-\d{3}$", v):
            raise ValueError("会话 ID 格式必须是 YYYYMMDD-NNN（如: 20260320-001）")
        return v


class Message(BaseModel):
    """消息模型

    表示一条对话消息。

    Attributes:
        role: 角色（user/assistant/system/tool）
        content: 消息内容
        timestamp: 时间戳
        name: 工具名称（role=tool 时使用）
    """

    role: str = Field(..., description="角色: user/assistant/system/tool")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(..., description="时间戳")
    name: str | None = Field(default=None, description="工具名称（role=tool 时）")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """验证 role 值必须是有效角色"""
        valid_roles = {"user", "assistant", "system", "tool"}
        if v not in valid_roles:
            raise ValueError(f"role 必须是: {', '.join(sorted(valid_roles))}")
        return v


class Trace(BaseModel):
    """工具调用记录模型

    表示一次工具调用的完整记录。

    Attributes:
        id: 调用唯一标识
        tool: 工具名称
        params: 调用参数
        result_status: 结果状态（success/error/timeout）
        result_preview: 结果预览（可选）
        duration_ms: 执行耗时（毫秒）
        timestamp: 时间戳
    """

    id: str = Field(..., description="调用唯一标识")
    tool: str = Field(..., description="工具名称")
    params: dict[str, Any] = Field(default_factory=dict, description="调用参数")
    result_status: str = Field(..., description="结果状态: success/error/timeout")
    result_preview: str | None = Field(default=None, description="结果预览")
    duration_ms: int = Field(..., ge=0, description="执行耗时（毫秒）")
    timestamp: datetime = Field(..., description="时间戳")

    @field_validator("result_status")
    @classmethod
    def validate_result_status(cls, v: str) -> str:
        """验证 result_status 值必须是有效状态"""
        valid_statuses = {"success", "error", "timeout"}
        if v not in valid_statuses:
            raise ValueError(
                f"result_status 必须是: {', '.join(sorted(valid_statuses))}"
            )
        return v
