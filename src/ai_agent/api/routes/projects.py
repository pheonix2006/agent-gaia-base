"""项目管理路由模块

提供项目的 CRUD API 端点。
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_agent.session import ProjectManager
from ai_agent.session.types import Project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    """创建项目请求

    Attributes:
        name: 项目名称
        path: 项目路径
    """

    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    path: str = Field(..., description="项目路径")


class UpdateProjectRequest(BaseModel):
    """更新项目请求

    Attributes:
        name: 新的项目名称
    """

    name: str = Field(..., min_length=1, max_length=100, description="新的项目名称")


class ProjectResponse(BaseModel):
    """项目响应

    Attributes:
        slug: 项目唯一标识
        name: 项目名称
        path: 项目路径
    """

    slug: str = Field(..., description="项目唯一标识")
    name: str = Field(..., description="项目名称")
    path: str = Field(..., description="项目路径")


class DeleteProjectResponse(BaseModel):
    """删除项目响应

    Attributes:
        status: 状态消息
        slug: 被删除的项目 slug
    """

    status: str = Field(..., description="状态消息")
    slug: str = Field(..., description="被删除的项目 slug")


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(request: Request) -> list[ProjectResponse]:
    """获取项目列表

    Args:
        request: FastAPI 请求对象

    Returns:
        list[ProjectResponse]: 项目列表
    """
    project_manager: ProjectManager = request.app.state.project_manager
    projects = project_manager.list_projects()

    return [
        ProjectResponse(slug=p.slug, name=p.name, path=str(p.path)) for p in projects
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: Request, body: CreateProjectRequest
) -> ProjectResponse:
    """创建项目

    Args:
        request: FastAPI 请求对象
        body: 创建项目请求体

    Returns:
        ProjectResponse: 创建的项目

    Raises:
        HTTPException: 400 - 路径不存在或无效
    """
    project_manager: ProjectManager = request.app.state.project_manager

    # 验证路径是否为有效目录（解析绝对路径，防止路径遍历）
    project_path = Path(body.path).resolve()
    if not project_path.is_dir():
        raise HTTPException(status_code=400, detail="路径不是有效的目录")

    # 注册项目
    project = project_manager.register_project(project_path, body.name)

    return ProjectResponse(slug=project.slug, name=project.name, path=str(project.path))


@router.patch("/projects/{slug}", response_model=ProjectResponse)
async def update_project(
    request: Request, slug: str, body: UpdateProjectRequest
) -> ProjectResponse:
    """更新项目（重命名）

    Args:
        request: FastAPI 请求对象
        slug: 项目 slug
        body: 更新项目请求体

    Returns:
        ProjectResponse: 更新后的项目

    Raises:
        HTTPException: 404 - 项目不存在
        HTTPException: 400 - 名称冲突
    """
    project_manager: ProjectManager = request.app.state.project_manager

    try:
        updated_project = project_manager.rename_project(slug, body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if updated_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return ProjectResponse(
        slug=updated_project.slug,
        name=updated_project.name,
        path=str(updated_project.path),
    )


@router.delete("/projects/{slug}", response_model=DeleteProjectResponse)
async def delete_project(request: Request, slug: str) -> DeleteProjectResponse:
    """删除项目

    Args:
        request: FastAPI 请求对象
        slug: 项目 slug

    Returns:
        DeleteProjectResponse: 删除确认

    Raises:
        HTTPException: 404 - 项目不存在
    """
    project_manager: ProjectManager = request.app.state.project_manager

    success = project_manager.delete_project(slug)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")

    return DeleteProjectResponse(status="deleted", slug=slug)
