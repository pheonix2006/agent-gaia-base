# tests/integration/test_api_chat.py
"""API 聊天端点集成测试"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage


@pytest.fixture
def mock_llm():
    """创建模拟 LLM - 返回 ReAct 格式的 finish 响应"""
    llm = MagicMock()
    # 返回 JSON 格式的 finish action，让 ReActAgent 直接结束
    finish_response = AIMessage(
        content='```json\n{"action": "finish", "params": {"answer": "Test response"}, "memory": "Direct answer"}\n```'
    )
    llm.ainvoke = AsyncMock(return_value=finish_response)
    return llm


def test_health_check():
    """测试健康检查端点"""
    from fastapi.testclient import TestClient

    with patch("ai_agent.api.main.create_llm_client"):
        from ai_agent.api.main import app

        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_chat_endpoint_validates_input():
    """测试聊天端点验证输入"""
    from fastapi.testclient import TestClient

    with patch("ai_agent.api.main.create_llm_client"):
        from ai_agent.api.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat",
                json={}
            )

    assert response.status_code == 422  # Validation error


def test_chat_endpoint_returns_response(mock_llm):
    """测试聊天端点返回响应"""
    from fastapi.testclient import TestClient
    from ai_agent.agents.react import ReActAgent

    def mock_create_llm():
        return mock_llm

    with patch("ai_agent.api.main.create_llm_client", side_effect=mock_create_llm):
        from ai_agent.api.main import app

        # 使用 ReActAgent（与 main.py 一致），无工具，减少步数
        app.state.agent = ReActAgent(mock_llm, tools=[], max_steps=3)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat",
                json={"message": "Hello"}
            )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Test response" in data["response"]
