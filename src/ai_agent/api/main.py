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
from ai_agent.llm.config import LLMSettings
from ai_agent.prompts import ReActPrompt
from ai_agent.session import HistoryStore, ProjectManager
from ai_agent.session.manager import SessionManager
from ai_agent.skills import SkillCatalog
from ai_agent.skills.catalog import build_catalog_from_directory, get_catalog_prompt
from ai_agent.tools import (
    GoogleSearchTool,
    ZhipuWebSearchTool,
    WebContentTool,
    ImageAnalysisTool,
    AudioParseTool,
    ReadTool,
)
from ai_agent.trace.langsmith import LangSmithSettings
from .routes.chat import router as chat_router
from .routes.projects import router as projects_router

logger = logging.getLogger(__name__)

# 获取静态文件目录
static_dir: Path = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理

    初始化 Agent 及其依赖组件：
    - LangSmith 追踪（可选）
    - LLM 客户端
    - SessionManager（会话管理）
    - Skills Catalog（渐进式披露）
    - 工具集合（含 Read 工具）
    - ReActAgent（带 Memory 支持）

    Args:
        app: FastAPI 应用实例

    Yields:
        None: 应用运行期间
    """
    # 初始化 LangSmith（可选，失败不报错）
    try:
        # 不传入 api_key 参数，让 pydantic-settings 从 .env 文件自动加载
        LangSmithSettings().setup()
        logger.info("LangSmith 追踪已启用")
    except Exception as e:
        logger.warning(f"LangSmith 配置失败（可选功能）: {e}")

    # 初始化 LLM
    llm = create_llm_client()
    logger.info("LLM 客户端已初始化")

    # === SessionManager 初始化 ===
    config_dir = Path.home() / ".agents"
    history_dir = config_dir / "history"

    # 初始化组件
    project_manager = ProjectManager(config_dir=config_dir)
    history_store = HistoryStore(base_path=history_dir)
    session_manager = SessionManager(store=history_store, project_manager=project_manager)

    # 自动注册当前项目
    project_root = Path(__file__).parent.parent.parent.parent  # 项目根目录
    project = project_manager.register_project(project_root, "AI Agent")
    logger.info(f"项目已注册: {project.name} (slug: {project.slug})")

    # 获取或创建活跃会话
    active_session = session_manager.get_or_create_active_session(project.slug)
    logger.info(f"活跃会话: {active_session.id} - {active_session.title}")

    # 保存到 app.state
    app.state.session_manager = session_manager
    app.state.project_manager = project_manager
    app.state.project_slug = project.slug
    app.state.session_id = active_session.id

    # === Skills 系统集成 ===
    # 发现 Skills 并构建 Catalog
    skills_dir = project_root / "skills"

    catalog = build_catalog_from_directory(skills_dir)
    catalog_prompt = get_catalog_prompt(catalog)
    logger.info(f"已加载 {len(catalog.skills)} 个 Skills: {[s.name for s in catalog.skills]}")

    # 初始化所有工具并转换为 LangChain 格式
    from ai_agent.tools.base import BaseAgentTool

    settings = LLMSettings()

    # 根据配置选择搜索引擎
    search_tool: BaseAgentTool
    if settings.web_search_provider == "zhipu":
        search_tool = ZhipuWebSearchTool()
        logger.info("使用智谱 Web Search")
    else:
        search_tool = GoogleSearchTool()
        logger.info("使用 Google Search (Serper)")

    # 工具列表（含 Read 工具支持 Skills 系统）
    tools: list[BaseAgentTool] = [
        search_tool,
        WebContentTool(),
        ImageAnalysisTool(),
        AudioParseTool(),
        ReadTool(),  # 添加 Read 工具，支持 Agent 读取 SKILL.md
    ]
    langchain_tools = [tool.to_langchain_tool() for tool in tools]
    logger.info(f"已加载 {len(langchain_tools)} 个工具: {[t.name for t in langchain_tools]}")

    # 创建 ReActPrompt（注入 Skills Catalog 到 context）
    prompt = ReActPrompt().with_context(catalog_prompt) if catalog_prompt else ReActPrompt()

    # 创建 ReActAgent（启用 Memory 支持，传递 Skill Catalog 实现轻量模式）
    app.state.agent = ReActAgent(
        llm,
        tools=langchain_tools,
        prompt=prompt,
        create_memory=True,
        skill_catalog=catalog,  # 传递 Skill Catalog 启用轻量模式
    )
    logger.info("ReActAgent 已初始化（Memory 功能已启用，Skills 轻量模式已启用）")

    yield
    # 关闭时清理（如有需要）


app: FastAPI = FastAPI(
    title="AI Agent API",
    description="基于 LangGraph 的 AI Agent 服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")


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
