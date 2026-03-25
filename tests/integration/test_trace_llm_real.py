"""Trace + LLM 集成测试 — 真实 API

验证 trace 装饰器与真实 LLM 客户端的集成，
确保 trace JSON 文件正确记录 span 信息。

标记: @pytest.mark.integration_real
跳过: 无 OPENAI_API_KEY 或 key 为 test-api-key 时自动跳过
"""

import json
import os
from pathlib import Path

import pytest

requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY",
)


def _find_trace_json(trace_dir: str) -> dict:
    """在 trace_dir 下递归查找唯一的 .json trace 文件并返回解析后的 dict。"""
    trace_path = Path(trace_dir)
    json_files = list(trace_path.rglob("*.json"))
    assert len(json_files) == 1, f"Expected 1 trace JSON file, found {len(json_files)}: {json_files}"
    with open(json_files[0], encoding="utf-8") as f:
        return json.load(f)


def _find_all_trace_jsons(trace_dir: str) -> list[dict]:
    """在 trace_dir 下递归查找所有 .json trace 文件并返回解析后的 dict 列表。"""
    trace_path = Path(trace_dir)
    json_files = sorted(trace_path.rglob("*.json"))
    results: list[dict] = []
    for jf in json_files:
        with open(jf, encoding="utf-8") as f:
            results.append(json.load(f))
    return results


# ---------------------------------------------------------------------------
# Test 1: 单次 LLM 调用 + trace_span + trace_run
# ---------------------------------------------------------------------------


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_single_llm_call(tmp_path: Path) -> None:
    """验证单次 LLM 调用被 trace_span 和 trace_run 正确记录。

    使用 create_llm_client() 创建真实 LLM，
    用 @trace_span("llm_call") + @trace_run("single_llm_test") 包装，
    验证 JSON 文件包含正确记录的 span 数据。
    """
    from ai_agent.llm.client import create_llm_client
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    config = TraceConfig(trace_dir=str(tmp_path))
    llm = create_llm_client()

    prompt = "What is 2+2? Answer with just the number."

    @trace_run("single_llm_test", config=config)
    async def do_llm_call() -> str:
        @trace_span("llm_call")
        async def call_llm(question: str) -> str:
            response = await llm.ainvoke(question)
            return response.content

        result = await call_llm(prompt)
        return result

    answer = await do_llm_call()

    # 验证 LLM 返回了合理的内容
    assert answer is not None
    assert len(str(answer).strip()) > 0

    # 验证 JSON trace 文件
    trace_data = _find_trace_json(str(tmp_path))

    assert trace_data["name"] == "single_llm_test"
    assert trace_data["status"] == "success"
    assert trace_data["finished_at"] is not None

    # 应该有 2 个 span: 外层 do_llm_call + 内层 llm_call
    spans = trace_data["spans"]
    assert len(spans) >= 2

    # 找到 llm_call span
    llm_spans = [s for s in spans if s["name"] == "llm_call"]
    assert len(llm_spans) == 1

    llm_span = llm_spans[0]
    assert llm_span["status"] == "success"
    assert llm_span["finished_at"] is not None
    assert llm_span["duration_ms"] is not None and llm_span["duration_ms"] > 0

    # 验证 output 非空（包含 LLM 返回内容）
    assert llm_span["output"] is not None
    output_value = llm_span["output"]
    # output 可能是 {"value": ...} 或 dict 形式
    output_str = json.dumps(output_value, ensure_ascii=False)
    assert len(output_str.strip()) > 0


# ---------------------------------------------------------------------------
# Test 2: trace 记录错误场景
# ---------------------------------------------------------------------------


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_llm_error_handling(tmp_path: Path) -> None:
    """验证 trace 正确记录错误场景。

    @trace_span 装饰的函数抛出 ConnectionError，
    验证 error span 被记录且包含正确的错误信息。
    """
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    config = TraceConfig(trace_dir=str(tmp_path))

    @trace_run("error_test", config=config)
    async def failing_workflow() -> None:
        @trace_span("failing_call")
        async def call_that_fails() -> None:
            raise ConnectionError("API connection failed")

        await call_that_fails()

    # 预期会抛出 ConnectionError
    with pytest.raises(ConnectionError, match="API connection failed"):
        await failing_workflow()

    # 验证 JSON trace 文件仍然被写入
    trace_data = _find_trace_json(str(tmp_path))

    assert trace_data["name"] == "error_test"
    # 整个 run 的 status 应该是 error（因为有失败的 span）
    assert trace_data["status"] == "error"

    # 找到 failing_call span
    spans = trace_data["spans"]
    failing_spans = [s for s in spans if s["name"] == "failing_call"]
    assert len(failing_spans) == 1

    failing_span = failing_spans[0]
    assert failing_span["status"] == "error"
    assert failing_span["error"] is not None
    assert "API connection failed" in failing_span["error"]
    assert failing_span["finished_at"] is not None


# ---------------------------------------------------------------------------
# Test 3: 多次顺序 LLM 调用
# ---------------------------------------------------------------------------


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_multiple_sequential_llm_calls(tmp_path: Path) -> None:
    """验证多次顺序 LLM 调用都在同一个 trace run 中正确记录。

    在一个 @trace_run 内执行多个 @trace_span 调用，
    验证所有 span 都被记录到同一个 JSON 文件中。
    """
    from ai_agent.llm.client import create_llm_client
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    config = TraceConfig(trace_dir=str(tmp_path))
    llm = create_llm_client()

    @trace_run("multi_call_test", config=config)
    async def multi_call_workflow() -> list[str]:
        @trace_span("call_1")
        async def first_call() -> str:
            response = await llm.ainvoke("What is 1+1? Answer with just the number.")
            return response.content

        @trace_span("call_2")
        async def second_call() -> str:
            response = await llm.ainvoke("What is 3+3? Answer with just the number.")
            return response.content

        @trace_span("call_3")
        async def third_call() -> str:
            response = await llm.ainvoke("What is 5+5? Answer with just the number.")
            return response.content

        results: list[str] = []
        results.append(await first_call())
        results.append(await second_call())
        results.append(await third_call())
        return results

    answers = await multi_call_workflow()

    # 验证得到了 3 个回答
    assert len(answers) == 3
    for answer in answers:
        assert answer is not None
        assert len(str(answer).strip()) > 0

    # 验证 JSON trace 文件
    trace_data = _find_trace_json(str(tmp_path))

    assert trace_data["name"] == "multi_call_test"
    assert trace_data["status"] == "success"
    assert trace_data["finished_at"] is not None

    spans = trace_data["spans"]

    # 应该有外层 span + 3 个调用 span = 至少 4 个 span
    assert len(spans) >= 4

    # 验证每个调用 span 都被正确记录
    for call_name in ["call_1", "call_2", "call_3"]:
        call_spans = [s for s in spans if s["name"] == call_name]
        assert len(call_spans) == 1, f"Expected exactly 1 span named '{call_name}', found {len(call_spans)}"

        span = call_spans[0]
        assert span["status"] == "success"
        assert span["finished_at"] is not None
        assert span["duration_ms"] is not None and span["duration_ms"] > 0
        assert span["output"] is not None
