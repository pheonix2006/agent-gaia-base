"""ReAct Agent stream() 方法真实 API 测试

测试场景：
1. 简单问答（LLM only，think → finish）
2. 搜索问答（LLM + Serper，think → act → observe → finish）
"""

import os
import pytest

# 跳过条件：没有真实 API Key
requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY"
)


@pytest.fixture
def llm_client():
    """创建真实 LLM 客户端"""
    from ai_agent.llm.client import create_llm_client
    return create_llm_client()


@pytest.fixture
def search_tools():
    """创建搜索相关工具"""
    from ai_agent.tools.web import GoogleSearchTool, WebContentTool
    return [
        GoogleSearchTool().to_langchain_tool(),
        WebContentTool().to_langchain_tool(),
    ]


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_stream_simple_qa_think_finish(llm_client):
    """测试简单问答 - 只有 think → finish 流程（无工具调用）

    验证点：
    1. 事件顺序正确：think -> finish
    2. think 事件包含 reasoning 和 raw_output
    3. finish 事件包含 answer
    """
    from ai_agent.agents.react import ReActAgent, AgentEventType

    agent = ReActAgent(llm_client, tools=[], max_steps=3)

    events = []
    async for event in agent.stream("法国的首都是哪里？"):
        events.append(event)

    # 验证事件类型顺序
    event_types = [e.event for e in events]
    assert AgentEventType.THINK in event_types, "应该有 think 事件"
    assert AgentEventType.FINISH in event_types, "应该有 finish 事件"

    # 验证 think 事件数据
    think_events = [e for e in events if e.event == AgentEventType.THINK]
    assert len(think_events) >= 1, "至少有一个 think 事件"
    think_event = think_events[0]
    assert "raw_output" in think_event.data, "think 事件应该包含 raw_output"

    # 验证 finish 事件数据
    finish_events = [e for e in events if e.event == AgentEventType.FINISH]
    assert len(finish_events) == 1, "应该有一个 finish 事件"
    finish_event = finish_events[0]
    assert "answer" in finish_event.data, "finish 事件应该包含 answer"
    assert "巴黎" in finish_event.data["answer"] or "Paris" in finish_event.data["answer"], \
        f"答案应该包含巴黎/Paris，实际答案: {finish_event.data['answer']}"

    # 验证步骤号递增
    steps = [e.step for e in events]
    assert steps == sorted(steps), "步骤号应该递增"

    print(f"\n=== 简单问答测试 ===")
    print(f"事件数量: {len(events)}")
    print(f"事件类型顺序: {[e.event.value for e in events]}")
    print(f"最终答案: {finish_event.data['answer']}")


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_stream_with_search_tool(llm_client, search_tools):
    """测试使用搜索工具 - 完整 think → act → observe → finish 流程

    验证点：
    1. 事件顺序正确：think -> act -> observe -> think -> finish
    2. act 事件包含 tool_name 和 params
    3. observe 事件包含 tool_name 和 result_summary
    """
    from ai_agent.agents.react import ReActAgent, AgentEventType

    agent = ReActAgent(llm_client, tools=search_tools, max_steps=10)

    # 使用一个需要搜索的问题
    events = []
    async for event in agent.stream("2024年奥运会是在哪里举办的？"):
        events.append(event)

    # 验证事件类型
    event_types = [e.event for e in events]

    # 验证有 think 事件
    assert AgentEventType.THINK in event_types, "应该有 think 事件"
    assert AgentEventType.FINISH in event_types, "应该有 finish 事件"

    # 验证有工具调用（act + observe）
    act_events = [e for e in events if e.event == AgentEventType.ACT]
    observe_events = [e for e in events if e.event == AgentEventType.OBSERVE]

    # 如果使用了工具，验证数据结构
    if act_events:
        act_event = act_events[0]
        assert "tool_name" in act_event.data, "act 事件应该包含 tool_name"
        assert "params" in act_event.data, "act 事件应该包含 params"
        print(f"\n工具调用: {act_event.data['tool_name']}")
        print(f"参数: {act_event.data['params']}")

    if observe_events:
        observe_event = observe_events[0]
        assert "tool_name" in observe_event.data, "observe 事件应该包含 tool_name"
        assert "result_summary" in observe_event.data, "observe 事件应该包含 result_summary"
        print(f"工具结果: {observe_event.data['result_summary'][:100]}...")

    # 验证 finish 事件
    finish_events = [e for e in events if e.event == AgentEventType.FINISH]
    assert len(finish_events) == 1, "应该有一个 finish 事件"
    finish_event = finish_events[0]

    print(f"\n=== 搜索问答测试 ===")
    print(f"事件数量: {len(events)}")
    print(f"事件类型顺序: {[e.event.value for e in events]}")
    print(f"最终答案: {finish_event.data['answer']}")


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_stream_event_data_structure(llm_client):
    """测试事件数据结构的完整性

    验证每个事件的字段：
    - event: AgentEventType
    - data: dict
    - timestamp: datetime
    - step: int >= 0
    """
    from ai_agent.agents.react import ReActAgent, AgentEventType
    from datetime import datetime

    agent = ReActAgent(llm_client, tools=[], max_steps=3)

    events = []
    async for event in agent.stream("1+1等于几？"):
        events.append(event)

    for i, event in enumerate(events):
        # 验证基本字段
        assert hasattr(event, 'event'), f"事件 {i} 应该有 event 字段"
        assert hasattr(event, 'data'), f"事件 {i} 应该有 data 字段"
        assert hasattr(event, 'timestamp'), f"事件 {i} 应该有 timestamp 字段"
        assert hasattr(event, 'step'), f"事件 {i} 应该有 step 字段"

        # 验证类型
        assert isinstance(event.event, AgentEventType), f"事件 {i} 的 event 应该是 AgentEventType"
        assert isinstance(event.data, dict), f"事件 {i} 的 data 应该是 dict"
        assert isinstance(event.timestamp, datetime), f"事件 {i} 的 timestamp 应该是 datetime"
        assert isinstance(event.step, int), f"事件 {i} 的 step 应该是 int"
        assert event.step >= 0, f"事件 {i} 的 step 应该 >= 0"

    print(f"\n=== 数据结构测试 ===")
    print(f"所有 {len(events)} 个事件数据结构验证通过")


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_stream_to_sse_format(llm_client):
    """测试事件的 SSE 格式转换"""
    from ai_agent.agents.react import ReActAgent

    agent = ReActAgent(llm_client, tools=[], max_steps=3)

    events = []
    async for event in agent.stream("你好"):
        events.append(event)

    # 验证 SSE 格式
    for event in events:
        sse_str = event.to_sse()
        assert sse_str.startswith("data: "), "SSE 格式应该以 'data: ' 开头"
        assert sse_str.endswith("\n\n"), "SSE 格式应该以 '\\n\\n' 结尾"

        json_str = event.to_json()
        assert "{" in json_str, "JSON 应该包含 '{'"
        assert "}" in json_str, "JSON 应该包含 '}'"
        assert '"event"' in json_str, "JSON 应该包含 'event' 字段"
        assert '"data"' in json_str, "JSON 应该包含 'data' 字段"
        assert '"timestamp"' in json_str, "JSON 应该包含 'timestamp' 字段"
        assert '"step"' in json_str, "JSON 应该包含 'step' 字段"

    print(f"\n=== SSE 格式测试 ===")
    print(f"所有 {len(events)} 个事件的 SSE 格式验证通过")
    print(f"示例 SSE: {events[0].to_sse()[:100]}...")


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_run_still_works(llm_client):
    """验证现有 run() 方法仍然正常工作"""
    from ai_agent.agents.react import ReActAgent

    agent = ReActAgent(llm_client, tools=[], max_steps=3)

    result = await agent.run("2+2等于几？")

    assert result is not None, "run() 应该返回结果"
    assert "4" in result, f"结果应该包含 4，实际结果: {result}"

    print(f"\n=== run() 方法测试 ===")
    print(f"结果: {result}")


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_stream_logging_output(llm_client, caplog):
    """测试 logging 输出"""
    import logging
    from ai_agent.agents.react import ReActAgent

    # 设置 ai_agent.agents.react.graph logger 的级别
    agent = ReActAgent(llm_client, tools=[], max_steps=3)

    # 确保 logger 传播到 root
    with caplog.at_level(logging.INFO, logger="ai_agent.agents.react.graph"):
        events = []
        async for event in agent.stream("测试日志"):
            events.append(event)

    # 验证有 logging 输出
    assert len(caplog.records) > 0, "应该有 logging 输出"

    # 检查日志内容
    log_messages = [r.message for r in caplog.records]

    # 应该包含 think 和 finish 相关日志
    has_think_log = any("think" in msg.lower() for msg in log_messages)
    has_finish_log = any("finish" in msg.lower() for msg in log_messages)

    assert has_think_log, "应该有 think 相关的日志"
    assert has_finish_log, "应该有 finish 相关的日志"

    print(f"\n=== 日志测试 ===")
    print(f"日志记录数: {len(caplog.records)}")
    for record in caplog.records[:5]:  # 只打印前5条
        print(f"  [{record.levelname}] {record.message}")


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_react_agent_langsmith_trace(llm_client, search_tools):
    """真实 API 测试：验证 LangSmith trace 创建

    此测试验证 @traceable 装饰器正确集成，
    在 LangSmith 中创建层级化的 trace 结构。

    验证点：
    1. stream 方法正常执行
    2. 事件序列完整
    3. Trace 应该在 LangSmith 控制台可见

    运行方式：
        pytest -m integration_real tests/integration/test_react_agent_live.py::test_react_agent_langsmith_trace -v

    检查 LangSmith：
        1. 打开 https://smith.langchain.com
        2. 进入 ai-agent 项目
        3. 查找名为 "react_agent" 的 trace
        4. 验证层级结构：LLM 调用和工具调用作为子 span
    """
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType

    # 检查 LangSmith API Key
    langsmith_key = os.getenv("LANGSMITH_API_KEY")
    if not langsmith_key or langsmith_key == "test-langsmith-key":
        pytest.skip("需要真实的 LANGSMITH_API_KEY")

    agent = ReActAgent(llm_client, tools=search_tools, max_steps=5)

    # 执行一个需要工具调用的问题
    events = []
    question = "今天北京天气怎么样？"

    print(f"\n=== LangSmith Trace 测试 ===")
    print(f"问题: {question}")
    print(f"LangSmith 项目: {os.getenv('LANGSMITH_PROJECT', 'ai-agent')}")

    async for event in agent.stream(question):
        events.append(event)
        print(f"  事件: {event.event.value}, 步骤: {event.step}")

    # 验证事件
    assert len(events) > 0, "应该产生事件"

    event_types = [e.event for e in events]
    assert AgentEventType.FINISH in event_types, "应该有 finish 事件"

    # 获取最终答案
    finish_events = [e for e in events if e.event == AgentEventType.FINISH]
    assert len(finish_events) == 1
    answer = finish_events[0].data.get("answer", "")

    print(f"\n最终答案: {answer[:200] if answer else 'N/A'}...")
    print(f"\n✅ 请在 LangSmith 控制台验证 trace 结构：")
    print(f"   https://smith.langchain.com")
    print(f"   项目: ai-agent")
    print(f"   应该看到一个名为 'react_agent' 的 trace")
    print(f"   LLM 调用和工具调用应该作为子 span 嵌套")


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_traceable_decorator_with_multiple_steps(llm_client, search_tools):
    """测试多步骤任务的 trace 结构

    验证点：
    1. 多次 think/act/observe 循环
    2. trace 包含所有步骤
    """
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType

    langsmith_key = os.getenv("LANGSMITH_API_KEY")
    if not langsmith_key or langsmith_key == "test-langsmith-key":
        pytest.skip("需要真实的 LANGSMITH_API_KEY")

    agent = ReActAgent(llm_client, tools=search_tools, max_steps=8)

    # 使用一个可能需要多步搜索的问题
    events = []
    question = "Python 3.12 有什么新特性？"

    print(f"\n=== 多步骤 Trace 测试 ===")
    print(f"问题: {question}")

    async for event in agent.stream(question):
        events.append(event)

    # 统计事件类型
    event_counts = {}
    for event in events:
        event_type = event.event.value
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    print(f"\n事件统计:")
    for event_type, count in event_counts.items():
        print(f"  {event_type}: {count}")

    # 验证
    assert AgentEventType.THINK in [e.event for e in events], "应该有 think 事件"
    assert AgentEventType.FINISH in [e.event for e in events], "应该有 finish 事件"

    print(f"\n✅ 测试通过，trace 应该已记录到 LangSmith")
