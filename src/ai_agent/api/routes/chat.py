"""聊天路由模块

提供同步和流式聊天 API 端点。
"""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai_agent.agents.react import ReActAgent
from ai_agent.agents.react.events import AgentEvent, AgentEventType

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

    Args:
        request: FastAPI 请求对象，用于访问应用状态中的 Agent
        body: 聊天请求体，包含用户消息

    Returns:
        ChatResponse: 包含 Agent 响应的对象
    """
    agent: ReActAgent = request.app.state.agent
    response: str = await agent.run(body.message)
    return ChatResponse(response=response)


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """流式聊天端点

    返回 SSE (Server-Sent Events) 格式的流式响应。
    每个事件包含 Agent 执行过程中的状态更新。

    SSE 事件格式:
        data: {"event": "think", "data": {...}, "timestamp": "...", "step": 1}

        data: {"event": "act", "data": {...}, "timestamp": "...", "step": 2}

        ...

    事件类型:
        - think: 思考阶段，包含推理过程
        - act: 行动阶段，调用工具
        - observe: 观察阶段，获取工具结果
        - error: 错误事件
        - finish: 完成事件，包含最终答案

    Args:
        request: FastAPI 请求对象，用于访问应用状态中的 Agent
        body: 聊天请求体，包含用户消息

    Returns:
        StreamingResponse: SSE 格式的流式响应
    """
    agent: ReActAgent = request.app.state.agent

    async def event_generator() -> AsyncGenerator[str, None]:
        """生成 SSE 事件流

        Yields:
            str: SSE 格式的事件字符串
        """
        try:
            async for event in agent.stream(body.message):
                yield event.to_sse()
        except Exception as e:
            # 生成错误事件
            error_event = AgentEvent(
                event=AgentEventType.ERROR,
                data={"message": str(e), "details": type(e).__name__},
                step=-1,
            )
            yield error_event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
