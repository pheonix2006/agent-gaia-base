"""FastAPI 应用入口

提供 AI Agent 服务的主应用模块。
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_agent.agents.react import ReActAgent
from ai_agent.llm.client import create_llm_client
from ai_agent.tools import (
    GoogleSearchTool,
    WebContentTool,
    ImageAnalysisTool,
    AudioParseTool,
)
from ai_agent.trace.langsmith import LangSmithSettings
from .routes.chat import router as chat_router

logger = logging.getLogger(__name__)

# 获取静态文件目录
static_dir: Path = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理

    初始化 Agent 及其依赖组件：
    - LangSmith 追踪（可选）
    - LLM 客户端
    - 工具集合
    - ReActAgent（带 Memory 支持）

    Args:
        app: FastAPI 应用实例

    Yields:
        None: 应用运行期间
    """
    # 初始化 LangSmith（可选，失败不报错）
    try:
        # 不传入 api_key 参数，让 pydantic-settings 从 .env 文件自动加载
        LangSmithSettings().setup()  # type: ignore[call-arg]
        logger.info("LangSmith 追踪已启用")
    except Exception as e:
        logger.warning(f"LangSmith 配置失败（可选功能）: {e}")

    # 初始化 LLM
    llm = create_llm_client()
    logger.info("LLM 客户端已初始化")

    # 初始化所有工具并转换为 LangChain 格式
    from ai_agent.tools.base import BaseAgentTool

    tools: list[BaseAgentTool] = [
        GoogleSearchTool(),
        WebContentTool(),
        ImageAnalysisTool(),
        AudioParseTool(),
    ]
    langchain_tools = [tool.to_langchain_tool() for tool in tools]
    logger.info(f"已加载 {len(langchain_tools)} 个工具: {[t.name for t in langchain_tools]}")

    # 创建 ReActAgent（启用 Memory 支持）
    app.state.agent = ReActAgent(llm, tools=langchain_tools, create_memory=True)  # type: ignore[arg-type]
    logger.info("ReActAgent 已初始化（Memory 功能已启用）")

    yield
    # 关闭时清理（如有需要）


app: FastAPI = FastAPI(
    title="AI Agent API",
    description="基于 LangGraph 的 AI Agent 服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查端点

    Returns:
        dict: 包含服务状态信息的字典
    """
    return {"status": "healthy"}


@app.get("/")
async def chat_page() -> FileResponse:
    """聊天页面

    Returns:
        FileResponse: 聊天页面 HTML 文件
    """
    chat_html: Path = static_dir / "chat.html"
    if chat_html.exists():
        return FileResponse(chat_html)
    return FileResponse(static_dir / "index.html")


# 挂载静态文件
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
