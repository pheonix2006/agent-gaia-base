"""API 测试配置"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pathlib import Path

from ai_agent.api.routes.projects import router as projects_router
from ai_agent.api.routes.sessions import router as sessions_router
from ai_agent.session import HistoryStore, ProjectManager
from ai_agent.session.manager import SessionManager


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """创建测试客户端

    每次创建独立的 FastAPI 应用实例，避免测试间状态共享。

    Args:
        tmp_path: pytest 提供的临时目录

    Returns:
        TestClient: FastAPI 测试客户端
    """
    # 创建独立的 FastAPI 应用
    app = FastAPI()
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(sessions_router, prefix="/api/v1")

    # 创建独立的 ProjectManager 和 SessionManager
    config_dir = tmp_path / ".agents"
    history_dir = config_dir / "history"

    project_manager = ProjectManager(config_dir=config_dir)
    history_store = HistoryStore(base_path=history_dir)
    session_manager = SessionManager(store=history_store, project_manager=project_manager)

    # 注册一个测试项目
    test_project_path = tmp_path / "test-project"
    test_project_path.mkdir()
    project_manager.register_project(test_project_path, "Test Project")

    # 将 managers 注入到 app.state
    app.state.project_manager = project_manager
    app.state.session_manager = session_manager

    return TestClient(app)
