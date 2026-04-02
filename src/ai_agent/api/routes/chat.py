"""聊天路由模块

提供同步和流式聊天 API 端点。
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai_agent.agents.react import ReActAgent
from ai_agent.types import AgentEvent, AgentEventType
from ai_agent.session.manager import SessionManager
from ai_agent.session.types import Message, Trace
from ai_agent.trace import TraceRecorder

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求

    Attributes:
        message: 用户发送的消息内容
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户消息内容",
        examples=["今天北京天气怎么样？"],
    )


class ChatResponse(BaseModel):
    """聊天响应

    Attributes:
        response: Agent 返回的响应内容
    """

    response: str = Field(
        ...,
        min_length=1,
        description="Agent 响应内容",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """处理聊天请求

    保存用户消息和 Assistant 回复到会话。

    Args:
        request: FastAPI 请求对象，用于访问应用状态中的 Agent
        body: 聊天请求体，包含用户消息

    Returns:
        ChatResponse: 包含 Agent 响应的对象
    """
    agent: ReActAgent = request.app.state.agent
    session_manager: SessionManager = request.app.state.session_manager
    project_slug: str = request.app.state.project_slug
    session_id: str = request.app.state.session_id

    now = datetime.now()

    # 保存用户消息
    user_message = Message(
        role="user",
        content=body.message,
        timestamp=now,
    )
    session_manager.append_message(project_slug, session_id, user_message)

    # 运行 Agent
    response: str = await agent.run(body.message)

    # 保存 Assistant 回复
    assistant_message = Message(
        role="assistant",
        content=response,
        timestamp=datetime.now(),
    )
    session_manager.append_message(project_slug, session_id, assistant_message)

    return ChatResponse(response=response)


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """流式聊天端点

    返回 SSE (Server-Sent Events) 格式的流式响应。
    每个事件包含 Agent 执行过程中的状态更新。
    同时保存用户消息、Assistant 回复和工具调用记录到会话。

    SSE 事件格式:
        data: {"type": "text", "data": {...}, "timestamp": "...", "step": 1}

        data: {"type": "tool_call", "data": {...}, "timestamp": "...", "step": 2}

        ...

    === 事件类型映射 ===
    旧事件 → 新事件：
      think   → text        (LLM 文本输出)
      act     → tool_call   (工具调用开始)
      observe → tool_result (工具执行结果)
      finish  → done        (完成)

    事件类型:
        - text: LLM 文本输出
        - tool_call: 工具调用请求
        - tool_result: 工具执行结果
        - error: 错误事件
        - done: 完成事件，包含最终答案

    Args:
        request: FastAPI 请求对象，用于访问应用状态中的 Agent
        body: 聊天请求体，包含用户消息

    Returns:
        StreamingResponse: SSE 格式的流式响应
    """
    agent: ReActAgent = request.app.state.agent
    session_manager: SessionManager = request.app.state.session_manager
    project_slug: str = request.app.state.project_slug
    session_id: str = request.app.state.session_id

    now = datetime.now()

    # 保存用户消息
    user_message = Message(
        role="user",
        content=body.message,
        timestamp=now,
    )
    session_manager.append_message(project_slug, session_id, user_message)

    async def event_generator() -> Any:
        """生成 SSE 事件流

        在此创建 TraceRecorder，确保整个流式执行过程都被追踪。
        agent.stream() 中的 TraceSpanCtx 会自动关联到此 recorder。

        Yields:
            str: SSE 格式的事件字符串
        """
        recorder = TraceRecorder("chat_stream")
        recorder.start_span("stream")

        final_response: str = ""
        traces: list[Trace] = []
        status = "completed"

        try:
            async for event in agent.stream(body.message):
                # 收集文本输出记录（text 事件）
                if event.type == AgentEventType.TEXT:
                    content = event.data.get("content", "")
                    trace = Trace(
                        id=str(uuid4()),
                        tool="_text_",
                        params={"content": content[:200]},
                        result_status="success",
                        duration_ms=0,
                        timestamp=event.timestamp,
                    )
                    traces.append(trace)

                # 收集工具调用记录（tool_call 事件）
                if event.type == AgentEventType.TOOL_CALL:
                    tool_name = event.data.get("name", "unknown")
                    args = event.data.get("args", {})
                    trace = Trace(
                        id=str(uuid4()),
                        tool=tool_name,
                        params=args if isinstance(args, dict) else {"args": str(args)},
                        result_status="success",
                        duration_ms=0,
                        timestamp=event.timestamp,
                    )
                    traces.append(trace)

                # 收集最终回复
                if event.type == AgentEventType.DONE:
                    final_response = event.data.get("answer", "")

                yield event.to_sse()

            recorder.finish_span(input={"message": body.message}, output={"status": status, "final_response": final_response[:500] if final_response else None})
        except Exception as e:
            status = "error"
            # 更新最后一个 trace 为错误状态
            if traces:
                traces[-1] = Trace(
                    id=traces[-1].id,
                    tool=traces[-1].tool,
                    params=traces[-1].params,
                    result_status="error",
                    result_preview=str(e),
                    duration_ms=0,
                    timestamp=traces[-1].timestamp,
                )

            # 生成错误事件
            error_event = AgentEvent(
                type=AgentEventType.ERROR,
                data={"message": str(e), "details": type(e).__name__},
                step=0,
            )
            yield error_event.to_sse()

            recorder.finish_span(input={"message": body.message}, error=str(e))
        finally:
            # 刷新 trace 到文件
            recorder.finish_run()

            # 保存所有工具调用记录
            for trace in traces:
                session_manager.append_trace(project_slug, session_id, trace)

            # 保存 Assistant 回复
            if final_response:
                assistant_message = Message(
                    role="assistant",
                    content=final_response,
                    timestamp=datetime.now(),
                )
                session_manager.append_message(project_slug, session_id, assistant_message)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
