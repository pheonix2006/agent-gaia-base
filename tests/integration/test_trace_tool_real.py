"""Trace 集成测试 -- 单个工具执行（真实 API）

验证 @trace_span + @trace_run 装饰器在真实 ZhipuWebSearchTool
调用场景下正确记录 span、写入 JSON 文件，并正确处理错误。

所有测试标记为 integration_real，需要有效的 OPENAI_API_KEY。
"""

import json
import os
from pathlib import Path

import pytest

requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY",
)


def _find_trace_json(trace_dir: str) -> Path:
    """在 trace_dir 下递归查找唯一一个 .json 文件并返回其路径。"""
    files = list(Path(trace_dir).rglob("*.json"))
    assert len(files) == 1, f"期望找到 1 个 trace JSON 文件，实际找到 {len(files)}: {files}"
    return files[0]


def _load_trace_json(trace_dir: str) -> dict:
    """读取 trace JSON 文件并返回解析后的字典。"""
    path = _find_trace_json(trace_dir)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_single_tool_execution(tmp_path: Path) -> None:
    """验证 trace_run + trace_span 在真实搜索工具调用时正确记录 span 并输出非空结果。"""
    from ai_agent.tools.web.zhipu_web_search import (
        ZhipuWebSearchParams,
        ZhipuWebSearchTool,
    )
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    trace_cfg = TraceConfig(trace_dir=str(tmp_path))
    tool = ZhipuWebSearchTool()

    @trace_run("tool_test", config=trace_cfg)
    async def execute_search(query: str) -> dict:
        @trace_span("act:web_search")
        async def _call_tool() -> dict:
            params = ZhipuWebSearchParams(query=query)
            result = await tool.run(params)
            return result.model_dump()

        return await _call_tool()

    result = await execute_search("Python programming language")

    # 验证工具返回了成功结果
    assert result["success"] is True
    assert isinstance(result["data"], list)
    assert len(result["data"]) > 0

    # 验证 trace JSON 文件已写入
    trace_data = _load_trace_json(str(tmp_path))
    assert trace_data["name"] == "tool_test"
    assert trace_data["status"] == "success"

    # 验证 span 结构
    spans = trace_data["spans"]
    assert len(spans) >= 2  # execute_search + _call_tool 至少两个 span

    # 查找 act:web_search span
    web_search_spans = [s for s in spans if s["name"] == "act:web_search"]
    assert len(web_search_spans) == 1, "应有且仅有 1 个 act:web_search span"

    span = web_search_spans[0]
    assert span["status"] == "success"
    assert span["output"] is not None
    # output 是 ToolResult 的 dict dump，应包含 success=True 和非空 data
    assert span["output"]["success"] is True
    assert len(span["output"]["data"]) > 0
    assert span["duration_ms"] is not None
    assert span["duration_ms"] > 0


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_tool_error(tmp_path: Path) -> None:
    """验证工具执行出错时 trace 正确记录 error 信息。

    通过构造一个会抛出异常的 span 来模拟工具错误场景，
    确保 trace_run 仍然能完成写入，并且 error span 的
    status 和 error 字段被正确填充。
    """
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    trace_cfg = TraceConfig(trace_dir=str(tmp_path))

    class FakeSearchError(Exception):
        """模拟工具内部错误。"""

        pass

    @trace_run("tool_error_test", config=trace_cfg)
    async def execute_failing_tool() -> dict:
        @trace_span("act:web_search")
        async def _call_failing_tool() -> dict:
            raise FakeSearchError("API rate limit exceeded")

        try:
            return await _call_failing_tool()
        except FakeSearchError:
            # 将异常包装为失败结果，模拟真实工具的 error 处理
            return {"success": False, "error": "API rate limit exceeded"}

    result = await execute_failing_tool()

    # 验证外层正确捕获了错误
    assert result["success"] is False
    assert "rate limit" in result["error"].lower()

    # 验证 trace JSON 文件已写入
    trace_data = _load_trace_json(str(tmp_path))
    assert trace_data["name"] == "tool_error_test"

    # act:web_search span 内部抛出了异常，会被 trace_span 捕获记录为 error
    spans = trace_data["spans"]
    web_search_spans = [s for s in spans if s["name"] == "act:web_search"]
    assert len(web_search_spans) == 1

    span = web_search_spans[0]
    # 因为异常在 trace_span 内部被抛出（虽然外层 catch 了），
    # trace_span 的 __exit__ 会先记录 error，然后异常传播
    assert span["status"] == "error"
    assert span["error"] is not None
    assert "FakeSearchError" in span["error"] or "rate limit" in span["error"]
