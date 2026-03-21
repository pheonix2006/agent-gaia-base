"""会话管理路由模块

提供会话的 CRUD API 端点。
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ai_agent.session.manager import SessionManager

router = APIRouter()


class CreateSessionRequest(BaseModel):
    """创建会话请求

    Attributes:
        project_slug: 项目 slug
        title: 会话标题（可选，不提供则自动生成）
    """

    project_slug: str = Field(..., description="项目 slug")
    title: str | None = Field(default=None, description="会话标题（可选）")


class UpdateSessionRequest(BaseModel):
    """更新会话请求

    Attributes:
        title: 新的会话标题
    """

    title: str = Field(..., min_length=1, max_length=200, description="新的会话标题")


class SessionResponse(BaseModel):
    """会话响应

    Attributes:
        id: 会话 ID
        title: 会话标题
        project_slug: 项目 slug
        created_at: 创建时间（ISO 格式）
    """

    id: str = Field(..., description="会话 ID")
    title: str = Field(..., description="会话标题")
    project_slug: str = Field(..., description="项目 slug")
    created_at: str = Field(..., description="创建时间（ISO 格式）")


class SessionListResponse(BaseModel):
    """会话列表响应

    Attributes:
        sessions: 会话列表
        total: 总数
        page: 当前页码
    """

    sessions: list[SessionResponse] = Field(..., description="会话列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")


class DeleteSessionResponse(BaseModel):
    """删除会话响应

    Attributes:
        status: 状态消息
        id: 被删除的会话 ID
    """

    status: str = Field(..., description="状态消息")
    id: str = Field(..., description="被删除的会话 ID")


class MessageResponse(BaseModel):
    """消息响应

    Attributes:
        role: 角色（user/assistant/system/tool）
        content: 消息内容
        timestamp: 时间戳（ISO 格式）
    """

    role: str = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳（ISO 格式）")


class TraceResponse(BaseModel):
    """工具调用记录响应

    Attributes:
        tool: 工具名称
        params: 工具输入参数
        result_status: 结果状态
        result_preview: 工具输出结果预览
        timestamp: 时间戳（ISO 格式）
    """

    tool: str = Field(..., description="工具名称")
    params: dict = Field(..., description="工具输入参数")
    result_status: str = Field(..., description="结果状态")
    result_preview: str | None = Field(default=None, description="工具输出结果预览")
    timestamp: str = Field(..., description="时间戳（ISO 格式）")


class SessionDataResponse(BaseModel):
    """会话完整数据响应

    Attributes:
        session: 会话元数据
        messages: 消息列表
        traces: 工具调用记录列表
    """

    session: SessionResponse = Field(..., description="会话元数据")
    messages: list[MessageResponse] = Field(..., description="消息列表")
    traces: list[TraceResponse] = Field(..., description="工具调用记录列表")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    project: str = Query(..., description="项目 slug"),
    page: int = Query(default=1, ge=1, description="页码"),
    limit: int = Query(default=10, ge=1, le=100, description="每页数量"),
) -> SessionListResponse:
    """获取会话列表（分页）

    Args:
        request: FastAPI 请求对象
        project: 项目 slug
        page: 页码（从 1 开始）
        limit: 每页数量

    Returns:
        SessionListResponse: 会话列表响应

    Raises:
        HTTPException: 404 - 项目不存在
    """
    session_manager: SessionManager = request.app.state.session_manager

    # 验证项目存在
    project_obj = session_manager.project_manager.get_project(project)
    if project_obj is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 获取所有会话
    all_sessions = session_manager.list_sessions(project)
    total = len(all_sessions)

    # 分页
    start = (page - 1) * limit
    end = start + limit
    page_sessions = all_sessions[start:end]

    # 转换为响应格式
    sessions = [
        SessionResponse(
            id=s.id,
            title=s.title,
            project_slug=s.project_slug,
            created_at=s.created_at.isoformat(),
        )
        for s in page_sessions
    ]

    return SessionListResponse(sessions=sessions, total=total, page=page)


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    request: Request, body: CreateSessionRequest
) -> SessionResponse:
    """创建会话

    如果不提供 title，自动生成时间戳标题（如 "2026-03-20 15:30"）。

    Args:
        request: FastAPI 请求对象
        body: 创建会话请求体

    Returns:
        SessionResponse: 创建的会话

    Raises:
        HTTPException: 404 - 项目不存在
    """
    session_manager: SessionManager = request.app.state.session_manager

    # 自动生成标题（如果未提供）
    title = body.title
    if title is None:
        title = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 创建会话
    try:
        session = session_manager.create_session(body.project_slug, title)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return SessionResponse(
        id=session.id,
        title=session.title,
        project_slug=session.project_slug,
        created_at=session.created_at.isoformat(),
    )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    request: Request, session_id: str, body: UpdateSessionRequest
) -> SessionResponse:
    """更新会话（重命名）

    Args:
        request: FastAPI 请求对象
        session_id: 会话 ID
        body: 更新会话请求体

    Returns:
        SessionResponse: 更新后的会话

    Raises:
        HTTPException: 404 - 会话不存在
    """
    session_manager: SessionManager = request.app.state.session_manager

    # 需要确定 session 所属的项目
    # 由于我们不知道 project_slug，需要遍历所有项目查找会话
    # 这是一个性能问题，但在当前架构下是必需的
    # 更好的做法是在 URL 中包含 project_slug（如 /projects/{slug}/sessions/{id}）
    projects = session_manager.project_manager.list_projects()

    for project in projects:
        session = session_manager.get_session(project.slug, session_id)
        if session is not None:
            # 找到会话，执行重命名
            updated_session = session_manager.rename_session(
                project.slug, session_id, body.title
            )
            if updated_session is None:
                raise HTTPException(status_code=500, detail="重命名失败")

            return SessionResponse(
                id=updated_session.id,
                title=updated_session.title,
                project_slug=updated_session.project_slug,
                created_at=updated_session.created_at.isoformat(),
            )

    # 未找到会话
    raise HTTPException(status_code=404, detail="会话不存在")


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    request: Request, session_id: str
) -> DeleteSessionResponse:
    """删除会话

    Args:
        request: FastAPI 请求对象
        session_id: 会话 ID

    Returns:
        DeleteSessionResponse: 删除确认

    Raises:
        HTTPException: 404 - 会话不存在
    """
    session_manager: SessionManager = request.app.state.session_manager

    # 需要确定 session 所属的项目
    projects = session_manager.project_manager.list_projects()

    for project in projects:
        session = session_manager.get_session(project.slug, session_id)
        if session is not None:
            # 找到会话，执行删除
            success = session_manager.delete_session(project.slug, session_id)
            if not success:
                raise HTTPException(status_code=500, detail="删除失败")

            return DeleteSessionResponse(status="deleted", id=session_id)

    # 未找到会话
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/sessions/{session_id}", response_model=SessionDataResponse)
async def get_session_data(request: Request, session_id: str) -> SessionDataResponse:
    """获取会话完整数据（包括消息历史和工具调用记录）

    Args:
        request: FastAPI 请求对象
        session_id: 会话 ID

    Returns:
        SessionDataResponse: 会话完整数据

    Raises:
        HTTPException: 404 - 会话不存在
    """
    session_manager: SessionManager = request.app.state.session_manager

    # 需要确定 session 所属的项目
    projects = session_manager.project_manager.list_projects()

    for project in projects:
        session_data = session_manager.load_session_data(project.slug, session_id)
        if session_data is not None:
            # 找到会话，返回完整数据
            session = session_data["session"]
            messages = session_data["messages"]
            traces = session_data["traces"]

            return SessionDataResponse(
                session=SessionResponse(
                    id=session.id,
                    title=session.title,
                    project_slug=session.project_slug,
                    created_at=session.created_at.isoformat(),
                ),
                messages=[
                    MessageResponse(
                        role=msg.role,
                        content=msg.content,
                        timestamp=msg.timestamp.isoformat(),
                    )
                    for msg in messages
                ],
                traces=[
                    TraceResponse(
                        tool=trace.tool,
                        params=trace.params,
                        result_status=trace.result_status,
                        result_preview=trace.result_preview,
                        timestamp=trace.timestamp.isoformat(),
                    )
                    for trace in traces
                ],
            )

    # 未找到会话
    raise HTTPException(status_code=404, detail="会话不存在")
