"""Agent 上下文管理路由"""

import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai_agent.agents.react import ReActAgent
from ai_agent.tools.filesystem.permissions import PermissionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class SwitchContextRequest(BaseModel):
    """切换上下文请求"""

    project_slug: str


class ContextResponse(BaseModel):
    """上下文响应"""

    project_slug: str
    session_id: str


@router.patch("/context", response_model=ContextResponse)
async def switch_context(request: Request, body: SwitchContextRequest) -> ContextResponse:
    """切换 Agent 上下文（硬切换）

    硬切换逻辑：
    1. 获取目标项目
    2. 重建 PermissionManager（只允许新项目路径）
    3. 重新创建 Agent（使用新的 permission_manager）
    4. 更新 app.state（agent, permission_manager, project_slug, session_id）
    5. 获取或创建活跃会话

    Args:
        request: FastAPI Request 对象
        body: 切换上下文请求体

    Returns:
        ContextResponse: 包含新项目 slug 和会话 ID

    Raises:
        HTTPException: 项目不存在时返回 404
    """
    # 1. 获取目标项目
    project_manager = request.app.state.project_manager
    target_project = project_manager.get_project(body.project_slug)

    if target_project is None:
        raise HTTPException(
            status_code=404,
            detail=f"项目 '{body.project_slug}' 不存在",
        )

    # 2. 重建 PermissionManager（只允许新项目路径）
    new_permission_manager = PermissionManager()
    new_permission_manager.allow_path(target_project.path, operations=None)
    logger.info(f"已为项目 {target_project.slug} 创建新的 PermissionManager")

    # 3. 重新创建 Agent
    old_agent: ReActAgent = request.app.state.agent

    # 从旧 Agent 获取属性
    llm = old_agent.llm
    tools = old_agent.tools
    system_prompt = old_agent.system_prompt

    # 创建新 Agent
    new_agent = ReActAgent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
    )
    logger.info(f"已为项目 {target_project.slug} 重建 ReActAgent")

    # 4. 更新 app.state
    request.app.state.agent = new_agent
    request.app.state.permission_manager = new_permission_manager
    request.app.state.project_slug = target_project.slug

    # 5. 获取或创建活跃会话
    session_manager = request.app.state.session_manager
    active_session = session_manager.get_or_create_active_session(target_project.slug)
    request.app.state.session_id = active_session.id

    logger.info(
        f"上下文已切换到项目 {target_project.slug}，会话 {active_session.id}"
    )

    return ContextResponse(
        project_slug=target_project.slug,
        session_id=active_session.id,
    )
