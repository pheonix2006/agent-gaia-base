"""聊天路由模块"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    """处理聊天请求"""
    agent = request.app.state.agent
    response = await agent.run(body.message)
    return ChatResponse(response=response)
