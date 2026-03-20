"""测试 Agent 上下文切换 API"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import Mock

from ai_agent.api.main import app
from ai_agent.session import Project
from ai_agent.agents.react import ReActAgent
from ai_agent.tools.filesystem.permissions import PermissionManager


@pytest.fixture
def client():
    """创建测试客户端并初始化 app.state"""
    # 创建模拟的依赖项
    from ai_agent.llm.client import create_llm_client
    from ai_agent.prompts import ReActPrompt
    from ai_agent.session import HistoryStore, ProjectManager
    from ai_agent.session.manager import SessionManager

    # 初始化 LLM 和其他组件
    llm = create_llm_client()
    tools = []
    prompt = ReActPrompt()

    # 初始化 Agent
    agent = ReActAgent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        create_memory=True,
    )

    # 初始化 SessionManager
    config_dir = Path.home() / ".agents"
    project_manager = ProjectManager(config_dir=config_dir)
    history_store = HistoryStore(base_path=config_dir / "history")
    session_manager = SessionManager(store=history_store, project_manager=project_manager)

    # 注册测试项目
    project_root = Path(__file__).parent.parent.parent.parent.parent
    project = project_manager.register_project(project_root, "AI Agent")

    # 获取或创建活跃会话
    active_session = session_manager.get_or_create_active_session(project.slug)

    # 设置 app.state
    app.state.agent = agent
    app.state.session_manager = session_manager
    app.state.project_manager = project_manager
    app.state.project_slug = project.slug
    app.state.session_id = active_session.id
    app.state.permission_manager = PermissionManager()

    return TestClient(app)


class TestAgentContextSwitch:
    """测试 Agent 上下文切换"""

    def test_switch_project_context(self, client: TestClient):
        """测试成功切换项目上下文"""
        # 准备测试数据
        project_slug = "ai-agent"  # 默认注册的项目

        # 发送切换请求
        response = client.patch(
            "/api/v1/agent/context", json={"project_slug": project_slug}
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["project_slug"] == project_slug
        assert "session_id" in data
        assert isinstance(data["session_id"], str)

    def test_switch_project_rebuilds_agent(self, client: TestClient):
        """测试切换项目会重建 Agent 和 PermissionManager"""
        project_slug = "ai-agent"

        # 获取切换前的状态
        response1 = client.patch(
            "/api/v1/agent/context", json={"project_slug": project_slug}
        )
        assert response1.status_code == 200
        session_id_1 = response1.json()["session_id"]

        # 再次切换到同一项目，应该返回相同的 session
        response2 = client.patch(
            "/api/v1/agent/context", json={"project_slug": project_slug}
        )
        assert response2.status_code == 200
        session_id_2 = response2.json()["session_id"]

        # 相同项目的活跃会话应该是一致的
        assert session_id_1 == session_id_2

    def test_switch_nonexistent_project(self, client: TestClient):
        """测试切换到不存在的项目应该返回 404"""
        response = client.patch(
            "/api/v1/agent/context", json={"project_slug": "nonexistent-project"}
        )

        # 验证返回 404
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "不存在" in data["detail"] or "not found" in data["detail"].lower()
