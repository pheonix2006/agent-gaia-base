# tests/integration/test_real_api.py
"""真实 API 集成测试（需要真实 API Key）"""
import os
import pytest


@pytest.fixture(autouse=True)
def setup_langsmith():
    """设置 LangSmith 追踪"""
    from ai_agent.trace.langsmith import LangSmithSettings

    try:
        settings = LangSmithSettings()
        settings.setup()
    except Exception:
        pass  # LangSmith 配置可选


@pytest.mark.integration_real
@pytest.mark.asyncio
async def test_real_llm_response():
    """测试真实 LLM API 调用"""
    from ai_agent.llm.client import create_llm_client
    from langchain_core.messages import HumanMessage

    llm = create_llm_client()
    response = await llm.ainvoke([HumanMessage("Say 'Hello World' and nothing else")])

    assert response is not None
    assert response.content
    assert len(response.content) > 0


@pytest.mark.integration_real
@pytest.mark.asyncio
async def test_real_simple_chat_agent():
    """测试真实 SimpleChatAgent"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.simple.graph import SimpleChatAgent

    llm = create_llm_client()
    agent = SimpleChatAgent(llm)

    response = await agent.run("What is 2+2? Answer with just the number.")

    assert response is not None
    assert "4" in response


@pytest.mark.integration_real
@pytest.mark.asyncio
async def test_langsmith_tracing_enabled():
    """测试 LangSmith 追踪已启用"""
    from ai_agent.trace.langsmith import LangSmithSettings

    settings = LangSmithSettings()

    assert settings.langsmith_tracing is True
    assert settings.langsmith_api_key is not None

    # 验证环境变量已设置
    settings.setup()
    assert os.environ.get("LANGSMITH_TRACING") == "true"


@pytest.mark.integration_real
def test_real_api_end_to_end():
    """端到端测试：真实 API 通过 FastAPI"""
    from fastapi.testclient import TestClient
    from ai_agent.api.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Say 'pong' and nothing else"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 0
