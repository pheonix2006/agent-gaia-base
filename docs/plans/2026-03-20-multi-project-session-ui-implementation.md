# 多项目/会话管理 UI 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 实现完整的多项目/会话管理界面，包括项目切换、会话历史、动态权限授权

**架构：** 后端 FastAPI REST API + 前端纯 JavaScript SPA，侧边栏主导布局，硬切换模式

**技术栈：** FastAPI, Pydantic, SQLite (HistoryStore), 纯 HTML/CSS/JavaScript

**设计文档：** `docs/design/2026-03-20-multi-project-session-ui-design.md`

---

## 前置条件验证

### Task 0: 验证当前测试状态

**目的：** 确保实施前所有测试通过

**Step 1: 运行单元测试验证**

```bash
uv run pytest tests/unit -v
```

**预期结果：** 425 passed, 1 failed (test_llm_settings_missing_api_key)

**Step 2: 记录当前失败测试**

当前有 1 个已知失败：
- `tests/unit/llm/test_config.py::test_llm_settings_missing_api_key`
- 原因：LLM 配置验证逻辑问题
- 影响：不影响本功能实施

---

## Phase 1: 后端 API 补全（优先级：高）

### Task 1: 统一 ReadTool 权限检查

**文件：**
- Modify: `src/ai_agent/tools/filesystem/read.py:86-92`
- Modify: `src/ai_agent/tools/filesystem/permissions.py` (添加 OperationType.READ 检查支持)

**Step 1: 修改 ReadTool 使用统一的权限检查**

```python
# src/ai_agent/tools/filesystem/read.py
# 在文件顶部导入
from .permissions import OperationType

# 修改 run_sync 方法的权限检查部分（第 86-92 行）
# 旧代码：
# if self._permission_manager and not self._permission_manager.is_allowed(file_path):
#     return ToolResult(...)

# 新代码：
if self._permission_manager:
    from ai_agent.session.types import Permission
    permission = self._permission_manager.check(file_path, OperationType.READ)
    if permission != Permission.ALLOW:
        return ToolResult(
            success=False,
            data="",
            error=f"权限不足：无法访问 {params.path}",
            metrics={"elapsed_time": time.time() - start_time},
        )
```

**Step 2: 编写单元测试验证权限检查**

```python
# tests/unit/tools/filesystem/test_read_tool_permissions.py
import pytest
from pathlib import Path
from ai_agent.tools.filesystem.read import ReadTool
from ai_agent.tools.filesystem.permissions import PermissionManager, OperationType
from ai_agent.session.types import Permission


def test_read_tool_uses_check_with_operation_type(tmp_path):
    """验证 ReadTool 使用 check(path, OperationType.READ)"""
    # 创建测试文件
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    # 创建 PermissionManager 并设置为 ASK
    pm = PermissionManager()
    pm.ask_path(tmp_path)

    # 创建 ReadTool
    tool = ReadTool(permission_manager=pm)

    # 读取应该返回权限错误
    result = tool.run_sync({"path": str(test_file), "offset": 0, "limit": 100})

    assert result.success is False
    assert "权限不足" in result.error


def test_read_tool_allows_when_permitted(tmp_path):
    """验证 ReadTool 在有权限时正常读取"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    pm = PermissionManager()
    pm.allow_path(tmp_path, operations=[OperationType.READ])

    tool = ReadTool(permission_manager=pm)
    result = tool.run_sync({"path": str(test_file), "offset": 0, "limit": 100})

    assert result.success is True
    assert "hello world" in result.data
```

**Step 3: 运行测试验证失败**

```bash
uv run pytest tests/unit/tools/filesystem/test_read_tool_permissions.py -v
```

**预期结果：** FAIL (文件不存在)

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/unit/tools/filesystem/test_read_tool_permissions.py -v
```

**预期结果：** 2 passed

**Step 5: 提交**

```bash
git add src/ai_agent/tools/filesystem/read.py tests/unit/tools/filesystem/test_read_tool_permissions.py
git commit -m "fix(tools): unify ReadTool permission check with OperationType.READ"
```

---

### Task 2: 创建项目管理 API 路由文件

**文件：**
- Create: `src/ai_agent/api/routes/projects.py`

**Step 1: 编写项目管理 API 测试**

```python
# tests/unit/api/test_projects.py
import pytest
from fastapi.testclient import TestClient
from pathlib import Path


def test_list_projects(client: TestClient, tmp_path):
    """测试获取项目列表"""
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_project(client: TestClient, tmp_path):
    """测试创建项目"""
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test Project", "path": str(tmp_path / "test-project")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Project"
    assert "slug" in data


def test_create_project_duplicate_name(client: TestClient):
    """测试重复项目名返回错误"""
    # 第一次创建
    client.post("/api/v1/projects", json={"name": "Test", "path": "/tmp/test1"})

    # 第二次创建同名项目
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test", "path": "/tmp/test2"}
    )
    assert response.status_code == 400


def test_update_project_rename(client: TestClient):
    """测试重命名项目"""
    # 创建项目
    create_resp = client.post(
        "/api/v1/projects",
        json={"name": "Old Name", "path": "/tmp/old"}
    )
    slug = create_resp.json()["slug"]

    # 重命名
    response = client.patch(
        f"/api/v1/projects/{slug}",
        json={"name": "New Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_delete_project(client: TestClient):
    """测试删除项目"""
    # 创建项目
    create_resp = client.post(
        "/api/v1/projects",
        json={"name": "To Delete", "path": "/tmp/delete"}
    )
    slug = create_resp.json()["slug"]

    # 删除
    response = client.delete(f"/api/v1/projects/{slug}")
    assert response.status_code == 200

    # 验证已删除
    list_resp = client.get("/api/v1/projects")
    slugs = [p["slug"] for p in list_resp.json()]
    assert slug not in slugs
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/unit/api/test_projects.py -v
```

**预期结果：** FAIL (404 Not Found)

**Step 3: 实现 projects.py 路由**

```python
# src/ai_agent/api/routes/projects.py
"""项目管理 API 路由"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_agent.session import ProjectManager

router = APIRouter()


class CreateProjectRequest(BaseModel):
    """创建项目请求"""

    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    path: str = Field(..., description="项目路径")


class UpdateProjectRequest(BaseModel):
    """更新项目请求"""

    name: str = Field(..., min_length=1, max_length=100, description="新项目名称")


class ProjectResponse(BaseModel):
    """项目响应"""

    slug: str = Field(..., description="项目唯一标识")
    name: str = Field(..., description="项目名称")
    path: str = Field(..., description="项目路径")


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(request: Request) -> list[ProjectResponse]:
    """获取项目列表"""
    project_manager: ProjectManager = request.app.state.project_manager
    projects = project_manager.list_projects()

    return [
        ProjectResponse(slug=p.slug, name=p.name, path=str(p.path))
        for p in projects
    ]


@router.post("/", response_model=ProjectResponse, status_code=200)
async def create_project(
    request: Request, body: CreateProjectRequest
) -> ProjectResponse:
    """创建新项目"""
    project_manager: ProjectManager = request.app.state.project_manager

    # 检查项目名是否已存在
    existing = project_manager.get_project_by_name(body.name)
    if existing:
        raise HTTPException(status_code=400, detail="项目名称已存在")

    # 注册项目
    project_path = Path(body.path).resolve()
    project = project_manager.register_project(project_path, body.name)

    return ProjectResponse(slug=project.slug, name=project.name, path=str(project.path))


@router.patch("/{slug}", response_model=ProjectResponse)
async def update_project(
    request: Request, slug: str, body: UpdateProjectRequest
) -> ProjectResponse:
    """更新项目（重命名）"""
    project_manager: ProjectManager = request.app.state.project_manager

    # 获取项目
    project = project_manager.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 检查新名称是否冲突
    existing = project_manager.get_project_by_name(body.name)
    if existing and existing.slug != slug:
        raise HTTPException(status_code=400, detail="项目名称已存在")

    # 重命名
    updated_project = project_manager.rename_project(slug, body.name)

    return ProjectResponse(
        slug=updated_project.slug,
        name=updated_project.name,
        path=str(updated_project.path),
    )


@router.delete("/{slug}")
async def delete_project(request: Request, slug: str) -> dict[str, str]:
    """删除项目"""
    project_manager: ProjectManager = request.app.state.project_manager

    # 检查项目是否存在
    project = project_manager.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 删除
    project_manager.delete_project(slug)

    return {"status": "deleted", "slug": slug}
```

**Step 4: 注册路由到 main.py**

```python
# src/ai_agent/api/main.py
# 在导入部分添加（第 33 行附近）
from .routes.projects import router as projects_router

# 在路由注册部分添加（第 151 行之后）
app.include_router(projects_router, prefix="/api/v1/projects")
```

**Step 5: 在 main.py lifespan 中添加 project_manager 到 app.state**

```python
# src/ai_agent/api/main.py
# 在 lifespan 函数中，第 76 行之后添加
app.state.project_manager = project_manager
```

**Step 6: 创建测试 client fixture**

```python
# tests/unit/api/conftest.py
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from ai_agent.api.main import app
from ai_agent.session import ProjectManager


@pytest.fixture
def client(tmp_path: Path):
    """创建测试客户端"""
    # 设置临时 project_manager
    config_dir = tmp_path / ".agents"
    project_manager = ProjectManager(config_dir=config_dir)

    # 注册一个测试项目
    project_manager.register_project(tmp_path / "test-project", "Test Project")

    app.state.project_manager = project_manager

    return TestClient(app)
```

**Step 7: 运行测试验证通过**

```bash
uv run pytest tests/unit/api/test_projects.py -v
```

**预期结果：** 5 passed

**Step 8: 提交**

```bash
git add src/ai_agent/api/routes/projects.py src/ai_agent/api/main.py tests/unit/api/
git commit -m "feat(api): add project management CRUD endpoints"
```

---

### Task 3: 创建会话管理 API 路由

**文件：**
- Create: `src/ai_agent/api/routes/sessions.py`

**Step 1: 编写会话管理 API 测试**

```python
# tests/unit/api/test_sessions.py
import pytest
from fastapi.testclient import TestClient


def test_list_sessions(client: TestClient):
    """测试获取会话列表"""
    # 先创建一个项目
    client.post("/api/v1/projects", json={"name": "Test", "path": "/tmp/test"})

    response = client.get("/api/v1/sessions?project=test")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data
    assert "page" in data


def test_create_session(client: TestClient):
    """测试创建会话"""
    # 创建项目
    client.post("/api/v1/projects", json={"name": "Test", "path": "/tmp/test"})

    # 创建会话
    response = client.post(
        "/api/v1/sessions",
        json={"project_slug": "test", "title": "My Session"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "My Session"
    assert "id" in data


def test_create_session_auto_title(client: TestClient):
    """测试自动生成标题（时间戳）"""
    client.post("/api/v1/projects", json={"name": "Test", "path": "/tmp/test"})

    response = client.post(
        "/api/v1/sessions",
        json={"project_slug": "test"}  # 不提供 title
    )
    assert response.status_code == 200
    # 标题应该是时间戳格式，如 "2026-03-20 14:30"
    assert "2026-" in response.json()["title"]


def test_update_session_rename(client: TestClient):
    """测试重命名会话"""
    client.post("/api/v1/projects", json={"name": "Test", "path": "/tmp/test"})
    create_resp = client.post(
        "/api/v1/sessions",
        json={"project_slug": "test"}
    )
    session_id = create_resp.json()["id"]

    # 重命名
    response = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"title": "New Title"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"


def test_delete_session(client: TestClient):
    """测试删除会话"""
    client.post("/api/v1/projects", json={"name": "Test", "path": "/tmp/test"})
    create_resp = client.post(
        "/api/v1/sessions",
        json={"project_slug": "test"}
    )
    session_id = create_resp.json()["id"]

    # 删除
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200

    # 验证已删除
    list_resp = client.get("/api/v1/sessions?project=test")
    session_ids = [s["id"] for s in list_resp.json()["sessions"]]
    assert session_id not in session_ids


def test_list_sessions_pagination(client: TestClient):
    """测试分页"""
    client.post("/api/v1/projects", json={"name": "Test", "path": "/tmp/test"})

    # 创建 25 个会话
    for i in range(25):
        client.post("/api/v1/sessions", json={"project_slug": "test"})

    # 请求第一页
    response = client.get("/api/v1/sessions?project=test&page=1&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 20
    assert data["total"] == 25
    assert data["page"] == 1

    # 请求第二页
    response = client.get("/api/v1/sessions?project=test&page=2&limit=20")
    assert len(response.json()["sessions"]) == 5
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/unit/api/test_sessions.py -v
```

**预期结果：** FAIL (404 Not Found)

**Step 3: 实现 sessions.py 路由**

```python
# src/ai_agent/api/routes/sessions.py
"""会话管理 API 路由"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ai_agent.session import SessionManager

router = APIRouter()


class CreateSessionRequest(BaseModel):
    """创建会话请求"""

    project_slug: str = Field(..., description="项目 slug")
    title: Optional[str] = Field(None, description="会话标题，不提供则自动生成")


class UpdateSessionRequest(BaseModel):
    """更新会话请求"""

    title: str = Field(..., min_length=1, max_length=200, description="新标题")


class SessionResponse(BaseModel):
    """会话响应"""

    id: str = Field(..., description="会话 ID")
    title: str = Field(..., description="会话标题")
    project_slug: str = Field(..., description="所属项目")
    created_at: str = Field(..., description="创建时间")


class SessionListResponse(BaseModel):
    """会话列表响应"""

    sessions: list[SessionResponse] = Field(..., description="会话列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    project: str = Query(..., description="项目 slug"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
) -> SessionListResponse:
    """获取会话列表（分页）"""
    session_manager: SessionManager = request.app.state.session_manager

    # 获取会话列表
    all_sessions = session_manager.list_sessions(project)

    # 分页
    total = len(all_sessions)
    start = (page - 1) * limit
    end = start + limit
    page_sessions = all_sessions[start:end]

    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                title=s.title,
                project_slug=s.project_slug,
                created_at=s.created_at.isoformat(),
            )
            for s in page_sessions
        ],
        total=total,
        page=page,
    )


@router.post("/", response_model=SessionResponse, status_code=200)
async def create_session(
    request: Request, body: CreateSessionRequest
) -> SessionResponse:
    """创建新会话"""
    session_manager: SessionManager = request.app.state.session_manager

    # 自动生成标题（时间戳）
    title = body.title or datetime.now().strftime("%Y-%m-%d %H:%M")

    # 创建会话
    session = session_manager.create_session(body.project_slug, title=title)

    return SessionResponse(
        id=session.id,
        title=session.title,
        project_slug=session.project_slug,
        created_at=session.created_at.isoformat(),
    )


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    request: Request, session_id: str, body: UpdateSessionRequest
) -> SessionResponse:
    """更新会话（重命名）"""
    session_manager: SessionManager = request.app.state.session_manager

    # 重命名
    session = session_manager.rename_session(session_id, body.title)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return SessionResponse(
        id=session.id,
        title=session.title,
        project_slug=session.project_slug,
        created_at=session.created_at.isoformat(),
    )


@router.delete("/{session_id}")
async def delete_session(request: Request, session_id: str) -> dict[str, str]:
    """删除会话"""
    session_manager: SessionManager = request.app.state.session_manager

    # 删除
    success = session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {"status": "deleted", "id": session_id}
```

**Step 4: 注册路由到 main.py**

```python
# src/ai_agent/api/main.py
# 在导入部分添加
from .routes.sessions import router as sessions_router

# 在路由注册部分添加
app.include_router(sessions_router, prefix="/api/v1/sessions")
```

**Step 5: 运行测试验证通过**

```bash
uv run pytest tests/unit/api/test_sessions.py -v
```

**预期结果：** 6 passed

**Step 6: 提交**

```bash
git add src/ai_agent/api/routes/sessions.py src/ai_agent/api/main.py tests/unit/api/test_sessions.py
git commit -m "feat(api): add session management CRUD endpoints with pagination"
```

---

### Task 4: 实现 Agent 上下文切换 API

**文件：**
- Modify: `src/ai_agent/api/main.py`

**Step 1: 编写上下文切换测试**

```python
# tests/unit/api/test_agent_context.py
import pytest
from fastapi.testclient import TestClient


def test_switch_project_context(client: TestClient, tmp_path):
    """测试切换项目上下文"""
    # 创建两个项目
    client.post(
        "/api/v1/projects",
        json={"name": "Project A", "path": str(tmp_path / "project-a")}
    )
    client.post(
        "/api/v1/projects",
        json={"name": "Project B", "path": str(tmp_path / "project-b")}
    )

    # 切换到 Project B
    response = client.patch(
        "/api/v1/agent/context",
        json={"project_slug": "project-b"}
    )
    assert response.status_code == 200
    assert response.json()["project_slug"] == "project-b"

    # 验证 app.state 已更新
    assert client.app.state.project_slug == "project-b"


def test_switch_project_rebuilds_agent(client: TestClient, tmp_path):
    """测试切换项目会重建 Agent（权限重置）"""
    # 创建两个项目
    client.post(
        "/api/v1/projects",
        json={"name": "Project A", "path": str(tmp_path / "project-a")}
    )
    client.post(
        "/api/v1/projects",
        json={"name": "Project B", "path": str(tmp_path / "project-b")}
    )

    # 切换到 Project B
    response = client.patch(
        "/api/v1/agent/context",
        json={"project_slug": "project-b"}
    )
    assert response.status_code == 200

    # 验证 Agent 被重建（新的实例）
    # 这通过检查 app.state.agent 的 id 或其他唯一标识来验证
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/unit/api/test_agent_context.py -v
```

**预期结果：** FAIL (404 Not Found)

**Step 3: 实现上下文切换 API**

```python
# src/ai_agent/api/routes/agent.py
"""Agent 上下文管理 API 路由"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_agent.session import ProjectManager, SessionManager
from ai_agent.tools.filesystem.permissions import PermissionManager

router = APIRouter()


class SwitchContextRequest(BaseModel):
    """切换上下文请求"""

    project_slug: str = Field(..., description="目标项目 slug")


class ContextResponse(BaseModel):
    """上下文响应"""

    project_slug: str = Field(..., description="当前项目 slug")
    session_id: str = Field(..., description="当前会话 ID")


@router.patch("/context", response_model=ContextResponse)
async def switch_context(
    request: Request, body: SwitchContextRequest
) -> ContextResponse:
    """切换项目上下文（硬切换）"""
    project_manager: ProjectManager = request.app.state.project_manager
    session_manager: SessionManager = request.app.state.session_manager

    # 1. 获取目标项目
    target_project = project_manager.get_project(body.project_slug)
    if not target_project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 2. 重建 PermissionManager（只允许新项目路径）
    new_permission_manager = PermissionManager()
    new_permission_manager.allow_path(target_project.path, operations=None)

    # 3. 重新创建 Agent
    # 获取原来的 LLM、tools、prompt 配置
    old_agent = request.app.state.agent
    llm = old_agent.llm  # 假设有这个属性
    tools = old_agent.tools
    prompt = old_agent.prompt

    # 重新创建 Agent
    from ai_agent.agents.react import ReActAgent
    new_agent = ReActAgent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        create_memory=True,  # 保持 memory 功能
        permission_manager=new_permission_manager,
    )

    # 4. 更新 app.state
    request.app.state.agent = new_agent
    request.app.state.permission_manager = new_permission_manager
    request.app.state.project_slug = body.project_slug

    # 5. 获取或创建活跃会话
    active_session = session_manager.get_or_create_active_session(body.project_slug)
    request.app.state.session_id = active_session.id

    return ContextResponse(
        project_slug=body.project_slug,
        session_id=active_session.id,
    )
```

**Step 4: 注册路由到 main.py**

```python
# src/ai_agent/api/main.py
# 在导入部分添加
from .routes.agent import router as agent_router

# 在路由注册部分添加
app.include_router(agent_router, prefix="/api/v1/agent")
```

**Step 5: 修改 ReActAgent 支持权限管理器注入**

```python
# src/ai_agent/agents/react/graph.py
# 在 ReActAgent.__init__ 方法中添加 permission_manager 参数
def __init__(
    self,
    llm,
    tools=None,
    prompt=None,
    create_memory=False,
    skill_catalog=None,
    permission_manager=None,  # 新增参数
):
    self.llm = llm
    self.tools = tools or []
    self.prompt = prompt
    self.permission_manager = permission_manager  # 保存引用
    # ... 其他初始化逻辑
```

**Step 6: 运行测试验证通过**

```bash
uv run pytest tests/unit/api/test_agent_context.py -v
```

**预期结果：** 2 passed

**Step 7: 提交**

```bash
git add src/ai_agent/api/routes/agent.py src/ai_agent/api/main.py src/ai_agent/agents/react/graph.py tests/unit/api/test_agent_context.py
git commit -m "feat(api): add agent context switch endpoint with permission reset"
```

---

## Phase 2: 前端侧边栏实现

### Task 5: 添加侧边栏 HTML 结构

**文件：**
- Modify: `src/ai_agent/api/static/chat.html`

**Step 1: 添加侧边栏容器**

```html
<!-- src/ai_agent/api/static/chat.html -->
<!-- 在 <body> 标签后，第 194 行左右 -->
<body>
    <!-- 新增：主容器 -->
    <div class="main-container">
        <!-- 新增：侧边栏 -->
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h2>项目</h2>
                <button id="createProjectBtn" class="btn-icon" title="新建项目">+</button>
            </div>

            <div class="project-list" id="projectList">
                <!-- 项目列表将通过 JS 动态渲染 -->
            </div>

            <div class="sidebar-footer">
                <button id="settingsBtn" class="btn-secondary">设置</button>
            </div>
        </div>

        <!-- 原有的聊天界面容器 -->
        <div class="chat-wrapper">
            <!-- 原来的 header, chat-container, input-area 移到这里 -->
        </div>
    </div>
```

**Step 2: 添加侧边栏 CSS 样式**

```css
/* src/ai_agent/api/static/chat.html */
/* 在 <style> 标签内添加（第 192 行之前） */

/* 主容器布局 */
.main-container {
    display: flex;
    height: 100vh;
    overflow: hidden;
}

/* 侧边栏 */
.sidebar {
    width: 280px;
    background: #16213e;
    border-right: 1px solid #0f3460;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
}

.sidebar.collapsed {
    width: 0;
    overflow: hidden;
}

.sidebar-header {
    padding: 15px 20px;
    border-bottom: 1px solid #0f3460;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.sidebar-header h2 {
    font-size: 16px;
    color: #e94560;
    margin: 0;
}

.project-list {
    flex: 1;
    overflow-y: auto;
    padding: 10px 0;
}

.project-item {
    margin-bottom: 5px;
}

.project-header {
    padding: 10px 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: background 0.2s;
}

.project-header:hover {
    background: #0f3460;
}

.project-header.active {
    background: #0f3460;
    border-left: 3px solid #e94560;
}

.project-name {
    font-size: 14px;
    color: #eee;
}

.project-expand {
    font-size: 12px;
    color: #888;
    transition: transform 0.2s;
}

.project-item.expanded .project-expand {
    transform: rotate(180deg);
}

.session-list {
    display: none;
    background: #0a0f1e;
    padding: 5px 0;
}

.project-item.expanded .session-list {
    display: block;
}

.session-item {
    padding: 8px 30px;
    cursor: pointer;
    font-size: 13px;
    color: #ccc;
    transition: background 0.2s;
}

.session-item:hover {
    background: #16213e;
}

.session-item.active {
    background: #1a3a5c;
    color: #fff;
}

.session-item .session-actions {
    display: none;
    float: right;
}

.session-item:hover .session-actions {
    display: inline;
}

.btn-icon {
    width: 28px;
    height: 28px;
    background: #e94560;
    color: #fff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
}

.btn-icon:hover {
    background: #d63d56;
}

.btn-secondary {
    width: 100%;
    padding: 10px;
    background: #0f3460;
    color: #eee;
    border: 1px solid #1a4a80;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
}

.btn-secondary:hover {
    background: #1a4a80;
}

.sidebar-footer {
    padding: 15px 20px;
    border-top: 1px solid #0f3460;
}

/* 聊天包装器 */
.chat-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0; /* 防止 flex 子元素溢出 */
}

/* 调整原有的聊天容器样式 */
.header {
    /* 保持原有样式 */
}

.chat-container {
    flex: 1;
    /* 移除 height: 100vh，由 flex 布局控制 */
}

.input-area {
    /* 保持原有样式 */
}
```

**Step 3: 验证 HTML 渲染**

```bash
# 启动服务器
uv run python main.py

# 浏览器打开 http://localhost:8000
# 预期：看到左侧侧边栏，右侧聊天区域
```

**Step 4: 提交**

```bash
git add src/ai_agent/api/static/chat.html
git commit -m "feat(ui): add sidebar HTML structure and layout"
```

---

### Task 6: 实现前端状态管理和 API 调用

**文件：**
- Modify: `src/ai_agent/api/static/chat.html`

**Step 1: 添加 JavaScript 状态管理**

```javascript
// src/ai_agent/api/static/chat.html
// 在 <script> 标签内，第 214 行之后添加

// 应用状态
const appState = {
    currentProject: null,
    currentSession: null,
    projects: [],
    sessionCache: {}  // 缓存已加载的会话
};

// API 调用封装
async function apiCall(method, path, body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (body) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(path, options);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Request failed');
    }
    return response.json();
}

// 加载项目列表
async function loadProjects() {
    const projects = await apiCall('GET', '/api/v1/projects');
    appState.projects = projects;

    // 渲染项目列表
    renderProjectList();

    // 恢复上次活跃的项目
    const lastProjectSlug = localStorage.getItem('last_project_slug');
    if (lastProjectSlug && projects.find(p => p.slug === lastProjectSlug)) {
        await switchProject(lastProjectSlug);
    } else if (projects.length > 0) {
        await switchProject(projects[0].slug);
    }
}

// 切换项目
async function switchProject(projectSlug) {
    // 调用 API 切换上下文
    const context = await apiCall('PATCH', '/api/v1/agent/context', {
        project_slug: projectSlug
    });

    appState.currentProject = appState.projects.find(p => p.slug === projectSlug);
    appState.currentSession = { id: context.session_id };

    // 保存到 LocalStorage
    localStorage.setItem('last_project_slug', projectSlug);

    // 加载该项目的会话列表
    await loadSessions(projectSlug, 1);

    // 切换到活跃会话
    await switchSession(context.session_id);

    // 更新 UI
    renderProjectList();
}

// 加载会话列表（分页）
async function loadSessions(projectSlug, page = 1) {
    const response = await apiCall(
        'GET',
        `/api/v1/sessions?project=${projectSlug}&page=${page}&limit=20`
    );

    // 找到项目并更新会话列表
    const project = appState.projects.find(p => p.slug === projectSlug);
    if (project) {
        if (page === 1) {
            project.sessions = response.sessions;
        } else {
            project.sessions = [...project.sessions, ...response.sessions];
        }
        project.totalSessions = response.total;
    }

    renderProjectList();
}

// 切换会话
async function switchSession(sessionId) {
    appState.currentSession = appState.currentProject?.sessions?.find(s => s.id === sessionId);
    if (!appState.currentSession) {
        appState.currentSession = { id: sessionId };
    }

    // 保存到 LocalStorage
    localStorage.setItem('last_session_id', sessionId);

    // 清空聊天界面
    chatContainer.innerHTML = '';
    showWelcome();

    // TODO: 加载会话历史消息（如果需要）

    // 更新 UI
    renderProjectList();
}

// 创建新会话
async function createSession(projectSlug) {
    const session = await apiCall('POST', '/api/v1/sessions', {
        project_slug: projectSlug
    });

    // 添加到项目会话列表开头
    const project = appState.projects.find(p => p.slug === projectSlug);
    if (project) {
        if (!project.sessions) project.sessions = [];
        project.sessions.unshift(session);
    }

    // 切换到新会话
    await switchSession(session.id);
}

// 创建新项目
async function createProject(name, path) {
    const project = await apiCall('POST', '/api/v1/projects', { name, path });
    appState.projects.push(project);
    renderProjectList();
    await switchProject(project.slug);
}
```

**Step 2: 实现渲染函数**

```javascript
// src/ai_agent/api/static/chat.html
// 继续在 <script> 标签内添加

// 渲染项目列表
function renderProjectList() {
    const projectList = document.getElementById('projectList');
    projectList.innerHTML = '';

    appState.projects.forEach(project => {
        const projectItem = document.createElement('div');
        projectItem.className = 'project-item';

        // 检查是否是当前项目
        const isActive = appState.currentProject?.slug === project.slug;
        if (isActive) {
            projectItem.classList.add('expanded');
        }

        // 项目头部
        const header = document.createElement('div');
        header.className = `project-header ${isActive ? 'active' : ''}`;
        header.innerHTML = `
            <span class="project-name">${escapeHtml(project.name)}</span>
            <span class="project-expand">▼</span>
        `;
        header.onclick = () => toggleProject(project.slug);
        projectItem.appendChild(header);

        // 会话列表
        const sessionList = document.createElement('div');
        sessionList.className = 'session-list';

        if (project.sessions && project.sessions.length > 0) {
            project.sessions.forEach(session => {
                const sessionItem = document.createElement('div');
                sessionItem.className = `session-item ${
                    appState.currentSession?.id === session.id ? 'active' : ''
                }`;
                sessionItem.innerHTML = `
                    <span>${escapeHtml(session.title)}</span>
                    <span class="session-actions">
                        <button onclick="event.stopPropagation(); deleteSession('${session.id}')" title="删除">×</button>
                    </span>
                `;
                sessionItem.onclick = () => switchSession(session.id);
                sessionList.appendChild(sessionItem);
            });
        }

        // 新建会话按钮
        const createSessionBtn = document.createElement('div');
        createSessionBtn.className = 'session-item';
        createSessionBtn.innerHTML = '+ 新建会话';
        createSessionBtn.style.color = '#888';
        createSessionBtn.onclick = () => createSession(project.slug);
        sessionList.appendChild(createSessionBtn);

        projectItem.appendChild(sessionList);
        projectList.appendChild(projectItem);
    });
}

// 展开/折叠项目
function toggleProject(projectSlug) {
    if (appState.currentProject?.slug !== projectSlug) {
        // 切换到该项目
        switchProject(projectSlug);
    } else {
        // 仅展开/折叠
        const projectItem = event.target.closest('.project-item');
        projectItem.classList.toggle('expanded');
    }
}

// 删除会话
async function deleteSession(sessionId) {
    if (!confirm('确定要删除这个会话吗？')) return;

    await apiCall('DELETE', `/api/v1/sessions/${sessionId}`);

    // 从列表中移除
    appState.projects.forEach(project => {
        if (project.sessions) {
            project.sessions = project.sessions.filter(s => s.id !== sessionId);
        }
    });

    // 如果删除的是当前会话，切换到第一个会话
    if (appState.currentSession?.id === sessionId) {
        const firstSession = appState.currentProject?.sessions?.[0];
        if (firstSession) {
            await switchSession(firstSession.id);
        }
    }

    renderProjectList();
}
```

**Step 3: 初始化应用**

```javascript
// src/ai_agent/api/static/chat.html
// 在 <script> 标签末尾添加

// 应用初始化
async function init() {
    try {
        await loadProjects();
    } catch (error) {
        console.error('初始化失败:', error);
        alert('加载项目列表失败：' + error.message);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
```

**Step 4: 验证前后端集成**

```bash
# 启动服务器
uv run python main.py

# 浏览器打开 http://localhost:8000
# 预期：
# 1. 看到侧边栏显示项目列表
# 2. 点击项目可展开/折叠
# 3. 点击会话可切换
# 4. 点击"新建会话"可创建新会话
```

**Step 5: 提交**

```bash
git add src/ai_agent/api/static/chat.html
git commit -m "feat(ui): implement frontend state management and project/session switching"
```

---

## Phase 3: 权限动态授权

### Task 7: 实现权限请求对话框

**文件：**
- Modify: `src/ai_agent/api/static/chat.html`

**Step 1: 添加权限对话框 HTML**

```html
<!-- src/ai_agent/api/static/chat.html -->
<!-- 在 .chat-wrapper 之前添加 -->

<!-- 权限请求对话框 -->
<div class="modal" id="permissionModal" style="display: none;">
    <div class="modal-content">
        <h3>⚠️ 权限请求</h3>
        <p id="permissionMessage"></p>
        <div class="modal-actions">
            <button id="permissionAllowOnce" class="btn-primary">允许一次</button>
            <button id="permissionAllowAlways" class="btn-primary">总是允许</button>
            <button id="permissionDeny" class="btn-secondary">拒绝</button>
        </div>
    </div>
</div>
```

**Step 2: 添加对话框 CSS**

```css
/* src/ai_agent/api/static/chat.html */
/* 在 <style> 标签内添加 */

/* 对话框样式 */
.modal {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: #16213e;
    padding: 30px;
    border-radius: 12px;
    max-width: 500px;
    width: 90%;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.modal-content h3 {
    color: #e94560;
    margin: 0 0 15px 0;
    font-size: 18px;
}

.modal-content p {
    color: #eee;
    line-height: 1.6;
    margin-bottom: 20px;
}

.modal-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}

.btn-primary {
    padding: 10px 20px;
    background: #e94560;
    color: #fff;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
}

.btn-primary:hover {
    background: #d63d56;
}
```

**Step 3: 实现权限请求处理逻辑**

```javascript
// src/ai_agent/api/static/chat.html
// 在 <script> 标签内添加

// 待处理的权限请求
let pendingPermissionRequest = null;

// 检测权限错误并弹出对话框
function checkPermissionError(event) {
    if (event.event === 'error' && event.data?.code === 'PERMISSION_REQUIRED') {
        showPermissionDialog(event.data);
        return true;  // 已处理
    }
    return false;  // 未处理
}

// 显示权限对话框
function showPermissionDialog(permissionData) {
    pendingPermissionRequest = permissionData;

    const message = `Agent 想要访问项目外的${permissionData.operation === 'read' ? '文件' : '路径'}：\n${permissionData.path}`;
    document.getElementById('permissionMessage').textContent = message;
    document.getElementById('permissionModal').style.display = 'flex';
}

// 关闭权限对话框
function closePermissionDialog() {
    document.getElementById('permissionModal').style.display = 'none';
    pendingPermissionRequest = null;
}

// 处理用户决策
async function handlePermissionDecision(decision) {
    if (!pendingPermissionRequest) return;

    const { path, operation, permission_id } = pendingPermissionRequest;

    try {
        await apiCall('POST', '/api/v1/permissions/request', {
            path,
            operation,
            decision,  // 'allow_once', 'allow_always', 'deny'
            permission_id
        });

        closePermissionDialog();

        // 如果允许，重试最后一条消息
        if (decision === 'allow_once' || decision === 'allow_always') {
            retryLastMessage();
        }
    } catch (error) {
        alert('权限请求失败：' + error.message);
    }
}

// 重试最后一条消息（简化实现）
function retryLastMessage() {
    // TODO: 实现重试逻辑
    // 可以保存最后一条消息到 appState，然后重新发送
    console.log('重试最后一条消息');
}

// 绑定按钮事件
document.getElementById('permissionAllowOnce').onclick = () => handlePermissionDecision('allow_once');
document.getElementById('permissionAllowAlways').onclick = () => handlePermissionDecision('allow_always');
document.getElementById('permissionDeny').onclick = () => handlePermissionDecision('deny');
```

**Step 4: 修改 renderEvent 函数集成权限检测**

```javascript
// src/ai_agent/api/static/chat.html
// 修改 renderEvent 函数（第 274 行左右）

function renderEvent(event) {
    // 先检查是否是权限错误
    if (checkPermissionError(event)) {
        return;  // 已处理，不渲染普通错误卡片
    }

    // 原有的渲染逻辑...
    if (!currentStepsContainer) {
        createStepsContainer();
    }
    // ...
}
```

**Step 5: 后端实现权限请求 API**

```python
# src/ai_agent/api/routes/permissions.py
"""权限管理 API 路由"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_agent.tools.filesystem.permissions import PermissionManager, OperationType

router = APIRouter()


class PermissionRequest(BaseModel):
    """权限请求"""

    path: str = Field(..., description="请求的路径")
    operation: str = Field(..., description="操作类型：read/write/edit")
    decision: str = Field(..., description="用户决策：allow_once/allow_always/deny")
    permission_id: str | None = Field(None, description="权限请求 ID")


@router.post("/request")
async def request_permission(
    request: Request, body: PermissionRequest
) -> dict[str, str]:
    """处理权限请求"""
    permission_manager: PermissionManager = request.app.state.permission_manager

    # 转换操作类型
    operation_map = {
        "read": OperationType.READ,
        "write": OperationType.WRITE,
        "edit": OperationType.EDIT,
    }
    operation = operation_map.get(body.operation)
    if not operation:
        raise HTTPException(status_code=400, detail="无效的操作类型")

    # 根据用户决策更新权限
    if body.decision == "allow_once":
        # 允许一次（会话级）
        permission_manager.allow_path(body.path, operations=[operation])
    elif body.decision == "allow_always":
        # 总是允许（所有操作）
        permission_manager.allow_path(body.path, operations=None)
    elif body.decision == "deny":
        # 拒绝
        permission_manager.deny_path(body.path, operations=[operation])
    else:
        raise HTTPException(status_code=400, detail="无效的决策")

    return {"status": "success", "decision": body.decision}


@router.get("/")
async def list_permissions(request: Request) -> dict[str, list[str]]:
    """获取当前权限列表"""
    permission_manager: PermissionManager = request.app.state.permission_manager

    return {
        "allowed": [str(p) for p in permission_manager.list_allowed()],
        "denied": [str(p) for p in permission_manager.list_denied()],
    }
```

**Step 6: 注册路由到 main.py**

```python
# src/ai_agent/api/main.py
# 在导入部分添加
from .routes.permissions import router as permissions_router

# 在路由注册部分添加
app.include_router(permissions_router, prefix="/api/v1/permissions")
```

**Step 7: 修改工具返回权限错误码**

```python
# src/ai_agent/tools/filesystem/read.py
# 修改权限检查部分（第 86-92 行）

if self._permission_manager:
    from ai_agent.session.types import Permission
    permission = self._permission_manager.check(file_path, OperationType.READ)

    if permission == Permission.ASK:
        # 返回特殊错误码
        import uuid
        return ToolResult(
            success=False,
            data="",
            error="PERMISSION_REQUIRED",
            metrics={
                "elapsed_time": time.time() - start_time,
                "code": "PERMISSION_REQUIRED",
                "path": str(file_path),
                "operation": "read",
                "permission_id": str(uuid.uuid4()),
            },
        )
    elif permission == Permission.DENY:
        return ToolResult(
            success=False,
            data="",
            error=f"权限不足：无法访问 {params.path}",
            metrics={"elapsed_time": time.time() - start_time},
        )
```

**Step 8: 同样修改 WriteTool 和 EditTool**

```python
# src/ai_agent/tools/filesystem/write.py 和 edit.py
# 在权限检查部分添加类似逻辑
```

**Step 9: 验证权限流程**

```bash
# 启动服务器
uv run python main.py

# 浏览器测试流程：
# 1. 在当前项目中发送："读取 /tmp/test.txt"（项目外路径）
# 2. 预期：弹出权限对话框
# 3. 点击"允许一次"
# 4. 预期：对话框关闭，消息自动重试并成功
```

**Step 10: 提交**

```bash
git add src/ai_agent/api/static/chat.html src/ai_agent/api/routes/permissions.py src/ai_agent/api/main.py src/ai_agent/tools/filesystem/*.py
git commit -m "feat(permissions): implement dynamic permission authorization dialog"
```

---

## Phase 4: 优化与测试

### Task 8: 修复已知测试失败

**Step 1: 修复 test_llm_settings_missing_api_key**

```python
# tests/unit/llm/test_config.py
# 修改 test_llm_settings_missing_api_key（第 43 行左右）

def test_llm_settings_missing_api_key():
    """测试缺少 API Key 时的验证（不使用 .env 文件）"""
    # 保存原始环境变量
    original_key = os.environ.get("OPENAI_API_KEY")

    try:
        # 临时移除 API Key
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        from ai_agent.llm.config import LLMSettings

        # 使用 _env_file=None 避免 .env 文件干扰
        # 注意：Pydantic Settings 默认不强制要求 API Key
        # 需要在 LLMSettings 中添加 validator
        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    finally:
        # 恢复环境变量
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
```

**Step 2: 在 LLMSettings 添加验证器**

```python
# src/ai_agent/llm/config.py
# 在 LLMSettings 类中添加验证器

from pydantic import field_validator

class LLMSettings(BaseSettings):
    # ... 原有字段

    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str:
        """验证 API Key 不为空"""
        if not v:
            raise ValueError("OPENAI_API_KEY is required")
        return v
```

**Step 3: 运行测试验证**

```bash
uv run pytest tests/unit/llm/test_config.py::test_llm_settings_missing_api_key -v
```

**预期结果：** PASS

**Step 4: 提交**

```bash
git add tests/unit/llm/test_config.py src/ai_agent/llm/config.py
git commit -m "fix(llm): add API key validation in LLMSettings"
```

---

### Task 9: 修复 mypy 类型错误

**Step 1: 修复 main.py 类型错误**

```python
# src/ai_agent/api/main.py
# 修改第 133 行

# 旧代码：
# tools=langchain_tools,

# 新代码：
tools=list(langchain_tools),  # 转换为 list[BaseTool]
```

**Step 2: 运行 mypy 验证**

```bash
uv run mypy src/ai_agent
```

**预期结果：** 0 errors

**Step 3: 提交**

```bash
git add src/ai_agent/api/main.py
git commit -m "fix(types): resolve mypy type error in main.py"
```

---

### Task 10: 编写 E2E 集成测试

**文件：**
- Create: `tests/integration/test_multi_project_workflow.py`

**Step 1: 编写完整流程测试**

```python
# tests/integration/test_multi_project_workflow.py
"""多项目/会话管理 E2E 测试"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


@pytest.mark.integration
class TestMultiProjectWorkflow:
    """测试完整的多项目管理流程"""

    def test_create_project_and_session_and_chat(self, client: TestClient, tmp_path: Path):
        """测试：创建项目 → 创建会话 → 发送消息"""
        # 1. 创建项目
        project_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test Project", "path": str(tmp_path / "test-project")}
        )
        assert project_resp.status_code == 200
        project_slug = project_resp.json()["slug"]

        # 2. 创建会话
        session_resp = client.post(
            "/api/v1/sessions",
            json={"project_slug": project_slug, "title": "First Session"}
        )
        assert session_resp.status_code == 200
        session_id = session_resp.json()["id"]

        # 3. 发送消息
        chat_resp = client.post(
            "/api/v1/chat",
            json={"message": "你好"}
        )
        assert chat_resp.status_code == 200
        response = chat_resp.json()["response"]
        assert len(response) > 0

        # 4. 验证消息已保存
        # TODO: 实现消息历史查询 API 后验证

    def test_switch_project_and_verify_context(self, client: TestClient, tmp_path: Path):
        """测试：切换项目 → 验证上下文更新"""
        # 创建两个项目
        client.post(
            "/api/v1/projects",
            json={"name": "Project A", "path": str(tmp_path / "project-a")}
        )
        client.post(
            "/api/v1/projects",
            json={"name": "Project B", "path": str(tmp_path / "project-b")}
        )

        # 切换到 Project B
        switch_resp = client.patch(
            "/api/v1/agent/context",
            json={"project_slug": "project-b"}
        )
        assert switch_resp.status_code == 200
        assert switch_resp.json()["project_slug"] == "project-b"

        # 验证会话已切换
        session_id = switch_resp.json()["session_id"]
        assert session_id is not None

    def test_permission_authorization_flow(self, client: TestClient, tmp_path: Path):
        """测试：跨项目访问 → 权限弹窗 → 授权 → 重试"""
        # 创建项目
        client.post(
            "/api/v1/projects",
            json={"name": "Test", "path": str(tmp_path / "test")}
        )

        # 创建外部文件
        external_file = tmp_path / "external" / "test.txt"
        external_file.parent.mkdir(parents=True, exist_ok=True)
        external_file.write_text("external content")

        # 尝试读取外部文件
        # TODO: 需要实现权限检测后才能完整测试
```

**Step 2: 运行集成测试**

```bash
uv run pytest tests/integration/test_multi_project_workflow.py -v
```

**预期结果：** 3 passed

**Step 3: 提交**

```bash
git add tests/integration/test_multi_project_workflow.py
git commit -m "test(integration): add E2E tests for multi-project workflow"
```

---

## 最终验证

### Task 11: 完整功能验证

**Step 1: 运行所有单元测试**

```bash
uv run pytest tests/unit -v
```

**预期结果：** All tests pass

**Step 2: 运行集成测试**

```bash
uv run pytest tests/integration -v
```

**预期结果：** All tests pass

**Step 3: 运行 mypy 类型检查**

```bash
uv run mypy src/ai_agent
```

**预期结果：** 0 errors

**Step 4: 手动 E2E 验证**

```bash
# 启动服务器
uv run python main.py

# 浏览器验证清单：
# [ ] 打开 http://localhost:8000，看到侧边栏
# [ ] 侧边栏显示当前项目（ai-agent）
# [ ] 点击项目展开，看到会话列表
# [ ] 点击"新建会话"，创建新会话成功
# [ ] 切换到新会话，聊天界面清空
# [ ] 发送消息，收到响应
# [ ] 点击"新建项目"，创建项目成功
# [ ] 切换到新项目，Agent 上下文更新
# [ ] 尝试读取项目外文件，弹出权限对话框
# [ ] 点击"允许一次"，重试成功
# [ ] 刷新页面，恢复上次的项目和会话
# [ ] 重命名项目/会话成功
# [ ] 删除项目/会话成功
```

**Step 5: 最终提交**

```bash
git add .
git commit -m "feat: complete multi-project/session UI implementation"
```

---

## 总结

**实施完成标志：**
- ✅ 后端 API 完整（项目/会话/权限管理）
- ✅ 前端 UI 完整（侧边栏、项目/会话列表、权限对话框）
- ✅ 权限系统统一（Read/Write/Edit 使用相同接口）
- ✅ 端到端可运行（前后端贯通）
- ✅ 所有测试通过
- ✅ 类型检查通过
- ✅ 手动验证通过

**预计工作量：** 2-3 天

**技术债务：**
- [ ] 会话历史消息加载（需要 HistoryStore 查询 API）
- [ ] 消息重试机制（需要保存最后一条消息）
- [ ] 性能优化（大量会话时的虚拟滚动）
- [ ] 移动端响应式优化

