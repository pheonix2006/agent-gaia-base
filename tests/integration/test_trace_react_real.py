"""Trace + ReAct Agent 真实 API 集成测试

验证 @trace_run 装饰器与完整 ReAct Agent 流程的集成。
需要真实的 OPENAI_API_KEY 才能运行。
"""

import json
import os
from pathlib import Path

import pytest

requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY"
)


@pytest.fixture
def trace_tools():
    """创建真实可用的测试工具（CalculatorTool + EchoTool）。"""
    from pydantic import BaseModel, Field

    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class CalculatorParams(BaseModel):
        expression: str = Field(description="Math expression to evaluate")

    class EchoParams(BaseModel):
        text: str = Field(description="Text to echo back")

    class CalculatorTool(BaseAgentTool[CalculatorParams, str]):
        @property
        def name(self) -> str:
            return "calculator"

        @property
        def description(self) -> str:
            return "Perform basic arithmetic. Input should be a math expression like '2+2'."

        @property
        def params_schema(self) -> type[CalculatorParams]:
            return CalculatorParams

        async def run(self, params: CalculatorParams) -> ToolResult[str]:
            expression = params.expression
            try:
                allowed = set("0123456789+-*/(). ")
                if not all(c in allowed for c in expression):
                    return ToolResult(success=False, data="", error="Invalid characters")
                result = eval(expression)
                return ToolResult(success=True, data=str(result))
            except Exception as e:
                return ToolResult(success=False, data="", error=str(e))

    class EchoTool(BaseAgentTool[EchoParams, str]):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Echo back the input text."

        @property
        def params_schema(self) -> type[EchoParams]:
            return EchoParams

        async def run(self, params: EchoParams) -> ToolResult[str]:
            return ToolResult(success=True, data=f"Echo: {params.text}")

    return [CalculatorTool().to_langchain_tool(), EchoTool().to_langchain_tool()]


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _find_trace_json(trace_dir: str, expected_name: str) -> dict:
    """在 trace_dir 中查找包含 expected_name 的 JSON 文件并返回解析后的数据。"""
    dir_path = Path(trace_dir)
    json_files: list[Path] = []
    for p in dir_path.rglob("*.json"):
        if expected_name in p.name:
            json_files.append(p)

    assert len(json_files) >= 1, f"未找到包含 '{expected_name}' 的 trace JSON 文件，目录内容: {list(dir_path.rglob('*.json'))}"

    with open(json_files[-1], encoding="utf-8") as f:
        return json.load(f)


def _assert_trace_structure(data: dict, expected_name: str, expected_status: str = "success") -> None:
    """验证 trace JSON 文件的基本结构。"""
    assert data["name"] == expected_name, f"期望 name='{expected_name}', 实际: {data['name']}"
    assert data["status"] == expected_status, f"期望 status='{expected_status}', 实际: {data['status']}"
    assert data["total_duration_ms"] > 0, f"total_duration_ms 应 > 0, 实际: {data['total_duration_ms']}"
    assert "run_id" in data, "缺少 run_id"
    assert "started_at" in data, "缺少 started_at"
    assert "finished_at" in data, "缺少 finished_at"
    assert "spans" in data, "缺少 spans"
    assert data["finished_at"] is not None, "finished_at 不应为 None"


def _assert_span_fields(span: dict) -> None:
    """验证每个 span 包含必需字段。"""
    for field_name in ("name", "span_id", "started_at", "finished_at", "duration_ms", "status"):
        assert field_name in span, f"span 缺少字段: {field_name}"
    assert span["started_at"] is not None, "span started_at 不应为 None"
    assert span["finished_at"] is not None, "span finished_at 不应为 None"
    assert span["duration_ms"] is not None, "span duration_ms 不应为 None"


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_full_react_run(trace_tools, tmp_path):
    """验证 @trace_run 装饰器包裹完整 ReActAgent.run() 后生成正确的 trace JSON。"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.llm.client import create_llm_client
    from ai_agent.trace import TraceConfig, trace_run

    trace_config = TraceConfig(trace_dir=str(tmp_path))

    llm = create_llm_client()

    @trace_run("react_full_test", config=trace_config)
    async def traced_run() -> str:
        agent = ReActAgent(llm, tools=trace_tools, max_steps=10)
        result = await agent.run("What is 15 + 27? Use the calculator tool.")
        return result

    result = await traced_run()

    # 验证 Agent 返回结果
    assert result is not None
    assert len(result) > 0

    # 验证 trace JSON 文件
    data = _find_trace_json(str(tmp_path), "react_full_test")
    _assert_trace_structure(data, "react_full_test")

    # 验证至少有一个 span（顶层 span）
    assert len(data["spans"]) >= 1, f"至少应有 1 个 span, 实际: {len(data['spans'])}"

    # 验证每个 span 的必需字段
    for span in data["spans"]:
        _assert_span_fields(span)


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_react_stream(trace_tools, tmp_path):
    """验证 @trace_run 装饰器包裹 ReActAgent.stream() 后生成正确的 trace JSON。"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType
    from ai_agent.llm.client import create_llm_client
    from ai_agent.trace import TraceConfig, trace_run

    trace_config = TraceConfig(trace_dir=str(tmp_path))

    llm = create_llm_client()

    @trace_run("react_stream_test", config=trace_config)
    async def traced_stream() -> dict:
        agent = ReActAgent(llm, tools=trace_tools, max_steps=10)
        events: list[dict] = []
        async for event in agent.stream("What is 15 + 27? Use the calculator tool."):
            # 将 AgentEvent 转换为可序列化的 dict
            events.append({
                "event": str(event.event.value) if hasattr(event, "event") else str(event),
                "step": event.step if hasattr(event, "step") else None,
            })
        return {"event_count": len(events), "events": events}

    trace_result = await traced_stream()

    # 验证收集到事件
    assert trace_result["event_count"] > 0, "应至少产生一个事件"

    # 验证存在 FINISH 事件
    finish_events = [e for e in trace_result["events"] if e.get("event") == "finish"]
    assert len(finish_events) >= 1, f"应至少有一个 FINISH 事件, 实际: {len(finish_events)}"

    # 验证 trace JSON 文件
    data = _find_trace_json(str(tmp_path), "react_stream_test")
    _assert_trace_structure(data, "react_stream_test")

    # 验证每个 span 的必需字段
    for span in data["spans"]:
        _assert_span_fields(span)


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_react_no_tools(tmp_path):
    """验证无工具场景下 @trace_run + ReActAgent 仍然正确记录 trace。"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.llm.client import create_llm_client
    from ai_agent.trace import TraceConfig, trace_run

    trace_config = TraceConfig(trace_dir=str(tmp_path))

    llm = create_llm_client()

    @trace_run("react_no_tools_test", config=trace_config)
    async def traced_no_tools() -> str:
        agent = ReActAgent(llm, tools=[], max_steps=3)
        result = await agent.run("What is the capital of France?")
        return result

    result = await traced_no_tools()

    # 验证 Agent 返回结果
    assert result is not None
    assert len(result) > 0

    # 验证 trace JSON 文件
    data = _find_trace_json(str(tmp_path), "react_no_tools_test")
    _assert_trace_structure(data, "react_no_tools_test")

    # 验证至少有一个 span
    assert len(data["spans"]) >= 1, f"至少应有 1 个 span, 实际: {len(data['spans'])}"

    # 验证每个 span 的必需字段
    for span in data["spans"]:
        _assert_span_fields(span)


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_react_error_handling(trace_tools, tmp_path):
    """验证 Agent 遇到错误（工具未找到）时 trace 仍能正确记录。"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.llm.client import create_llm_client
    from ai_agent.trace import TraceConfig, trace_run

    trace_config = TraceConfig(trace_dir=str(tmp_path))

    llm = create_llm_client()

    @trace_run("react_error_test", config=trace_config)
    async def traced_error_run() -> str:
        # 不给 Agent 任何工具，但提示它使用一个不存在的工具
        agent = ReActAgent(llm, tools=[], max_steps=5)
        result = await agent.run("Use the calculator tool to compute 1 + 1. You must use a tool.")
        return result

    result = await traced_error_run()

    # 验证 Agent 返回结果（即使有错误也会返回结果）
    assert result is not None

    # 验证 trace JSON 文件
    data = _find_trace_json(str(tmp_path), "react_error_test")
    _assert_trace_structure(data, "react_error_test")

    # 验证至少有一个 span
    assert len(data["spans"]) >= 1, f"至少应有 1 个 span, 实际: {len(data['spans'])}"

    # 验证每个 span 的必需字段
    for span in data["spans"]:
        _assert_span_fields(span)
