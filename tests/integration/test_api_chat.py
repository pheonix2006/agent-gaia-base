# tests/integration/test_api_chat.py
"""API 聊天端点集成测试"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage


@pytest.fixture
def mock_llm():
    """创建模拟 LLM"""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Test response"))
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
    from ai_agent.agents.simple.graph import SimpleChatAgent

    def mock_create_llm():
        return mock_llm

    with patch("ai_agent.api.main.create_llm_client", side_effect=mock_create_llm):
        from ai_agent.api.main import app

        # 重新初始化应用状态
        app.state.agent = SimpleChatAgent(mock_llm)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat",
                json={"message": "Hello"}
            )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert data["response"] == "Test response"
