"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_agent.llm.client import create_llm_client
from ai_agent.agents.simple.graph import SimpleChatAgent
from .routes.chat import router as chat_router

# 获取静态文件目录
static_dir = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化 LLM 和 Agent
    llm = create_llm_client()
    app.state.agent = SimpleChatAgent(llm)
    yield
    # 关闭时清理（如有需要）


app = FastAPI(
    title="AI Agent API",
    description="基于 LangGraph 的 AI Agent 服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


@app.get("/")
async def chat_page():
    """聊天页面"""
    chat_html = static_dir / "chat.html"
    if chat_html.exists():
        return FileResponse(chat_html)
    return FileResponse(static_dir / "index.html")


# 挂载静态文件
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
