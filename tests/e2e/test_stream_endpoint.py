# tests/e2e/test_stream_endpoint.py
"""SSE 流式端点 E2E 测试

测试 /chat/stream 端点的 SSE 功能。
使用真实 API 进行测试，需要设置 OPENAI_API_KEY 环境变量。

运行命令:
    pytest tests/e2e/test_stream_endpoint.py -m integration -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ai_agent.agents.react.events import AgentEventType


class TestSSEConnection:
    """测试 SSE 连接成功"""

    def test_stream_endpoint_exists(self):
        """测试流式端点存在"""
        from fastapi.testclient import TestClient
        from ai_agent.agents.simple.graph import SimpleChatAgent

        with patch("ai_agent.api.main.create_llm_client") as mock_create:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="test"))
            mock_create.return_value = mock_llm

            from ai_agent.api.main import app
            app.state.agent = SimpleChatAgent(mock_llm)

            with TestClient(app) as client:
                # 验证端点可访问（即使返回 422 也说明端点存在）
                response = client.post("/api/v1/chat/stream", json={})
                # 不是 404 说明端点存在
                assert response.status_code != 404

    def test_stream_endpoint_accepts_post(self):
        """测试流式端点接受 POST 请求"""
        from fastapi.testclient import TestClient

        with patch("ai_agent.api.main.create_llm_client"):
            from ai_agent.api.main import app

            # 使用 mock agent
            mock_agent = MagicMock()
            mock_agent.stream = AsyncMock()

            async def mock_stream(message):
                from ai_agent.agents.react.events import AgentEvent
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "test"},
                    step=1,
                )

            mock_agent.stream = mock_stream
            app.state.agent = mock_agent

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/chat/stream",
                    json={"message": "Hello"},
                    headers={"Accept": "text/event-stream"},
                )

                # 应该返回 200 或者 SSE 响应
                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")


class TestSSEEventFormat:
    """测试 SSE 事件格式正确性"""

    def test_event_format_has_data_prefix(self):
        """测试事件格式包含 data: 前缀"""
        from fastapi.testclient import TestClient
        from ai_agent.agents.react.events import AgentEvent

        with patch("ai_agent.api.main.create_llm_client"):
            from ai_agent.api.main import app

            async def mock_stream(message):
                yield AgentEvent(
                    event=AgentEventType.THINK,
                    data={"reasoning": "思考中..."},
                    step=1,
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "完成"},
                    step=2,
                )

            mock_agent = MagicMock()
            mock_agent.stream = mock_stream
            app.state.agent = mock_agent

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/chat/stream",
                    json={"message": "测试"},
                )

                content = response.text
                # 检查 SSE 格式
                assert "data: " in content

    def test_event_format_has_double_newline(self):
        """测试事件格式包含双换行符"""
        from fastapi.testclient import TestClient
        from ai_agent.agents.react.events import AgentEvent

        with patch("ai_agent.api.main.create_llm_client"):
            from ai_agent.api.main import app

            async def mock_stream(message):
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "完成"},
                    step=1,
                )

            mock_agent = MagicMock()
            mock_agent.stream = mock_stream
            app.state.agent = mock_agent

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/chat/stream",
                    json={"message": "测试"},
                )

                content = response.text
                # SSE 事件以 \n\n 结尾
                assert "\n\n" in content

    def test_event_format_json_parseable(self):
        """测试事件数据可以解析为 JSON"""
        from fastapi.testclient import TestClient
        from ai_agent.agents.react.events import AgentEvent

        with patch("ai_agent.api.main.create_llm_client"):
            from ai_agent.api.main import app

            async def mock_stream(message):
                yield AgentEvent(
                    event=AgentEventType.THINK,
                    data={"reasoning": "测试推理"},
                    step=1,
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "最终答案"},
                    step=2,
                )

            mock_agent = MagicMock()
            mock_agent.stream = mock_stream
            app.state.agent = mock_agent

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/chat/stream",
                    json={"message": "测试"},
                )

                content = response.text
                events = []

                # 解析 SSE 事件
                for line in content.split("\n"):
                    if line.startswith("data: "):
                        json_str = line[6:]  # 移除 "data: " 前缀
                        if json_str:
                            event_data = json.loads(json_str)
                            events.append(event_data)

                # 验证能正确解析
                assert len(events) >= 1
                assert "event" in events[0]
                assert "data" in events[0]
                assert "step" in events[0]
                assert "timestamp" in events[0]


class TestSSEEventOrder:
    """测试 SSE 事件顺序正确性"""

    def test_events_have_correct_structure(self):
        """测试事件包含正确的结构"""
        from fastapi.testclient import TestClient
        from ai_agent.agents.react.events import AgentEvent

        with patch("ai_agent.api.main.create_llm_client"):
            from ai_agent.api.main import app

            async def mock_stream(message):
                yield AgentEvent(
                    event=AgentEventType.THINK,
                    data={"reasoning": "分析问题", "action": "finish"},
                    step=0,
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "最终答案"},
                    step=1,
                )

            mock_agent = MagicMock()
            mock_agent.stream = mock_stream
            app.state.agent = mock_agent

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/chat/stream",
                    json={"message": "测试"},
                )

                content = response.text
                events = []

                for line in content.split("\n"):
                    if line.startswith("data: "):
                        json_str = line[6:]
                        if json_str:
                            events.append(json.loads(json_str))

                # 验证事件结构
                for event in events:
                    assert "event" in event
                    assert "data" in event
                    assert "timestamp" in event
                    assert "step" in event

    def test_last_event_is_finish(self):
        """测试最后一个事件是 finish 类型"""
        from fastapi.testclient import TestClient
        from ai_agent.agents.react.events import AgentEvent

        with patch("ai_agent.api.main.create_llm_client"):
            from ai_agent.api.main import app

            async def mock_stream(message):
                yield AgentEvent(
                    event=AgentEventType.THINK,
                    data={"reasoning": "分析问题"},
                    step=0,
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "最终答案"},
                    step=1,
                )

            mock_agent = MagicMock()
            mock_agent.stream = mock_stream
            app.state.agent = mock_agent

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/chat/stream",
                    json={"message": "测试"},
                )

                content = response.text
                events = []

                for line in content.split("\n"):
                    if line.startswith("data: "):
                        json_str = line[6:]
                        if json_str:
                            events.append(json.loads(json_str))

                # 最后一个事件应该是 finish
                assert events[-1]["event"] == "finish"

    def test_steps_increment_correctly(self):
        """测试步骤号递增正确"""
        from fastapi.testclient import TestClient
        from ai_agent.agents.react.events import AgentEvent

        with patch("ai_agent.api.main.create_llm_client"):
            from ai_agent.api.main import app

            async def mock_stream(message):
                yield AgentEvent(
                    event=AgentEventType.THINK,
                    data={"reasoning": "分析"},
                    step=0,
                )
                yield AgentEvent(
                    event=AgentEventType.ACT,
                    data={"tool_name": "search"},
                    step=1,
                )
                yield AgentEvent(
                    event=AgentEventType.OBSERVE,
                    data={"result_summary": "结果"},
                    step=2,
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "完成"},
                    step=3,
                )

            mock_agent = MagicMock()
            mock_agent.stream = mock_stream
            app.state.agent = mock_agent

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/chat/stream",
                    json={"message": "测试"},
                )

                content = response.text
                events = []

                for line in content.split("\n"):
                    if line.startswith("data: "):
                        json_str = line[6:]
                        if json_str:
                            events.append(json.loads(json_str))

                # 验证步骤递增
                steps = [e["step"] for e in events]
                assert steps == sorted(steps)  # 步骤应该是递增的


@pytest.mark.integration
class TestStreamEndpointWithRealAPI:
    """使用真实 API 的集成测试

    运行前确保设置 OPENAI_API_KEY 环境变量
    """

    @pytest.mark.integration
    def test_real_api_simple_question(self):
        """测试真实 API：简单问题"""
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("未设置 OPENAI_API_KEY")

        from fastapi.testclient import TestClient
        from ai_agent.api.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/stream",
                json={"message": "1+1等于几？"},
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            content = response.text
            assert "data: " in content

            # 解析并验证事件
            events = []
            for line in content.split("\n"):
                if line.startswith("data: "):
                    json_str = line[6:]
                    if json_str:
                        events.append(json.loads(json_str))

            # 应该至少有 think 和 finish 事件
            assert len(events) >= 2
            event_types = [e["event"] for e in events]
            assert "finish" in event_types
