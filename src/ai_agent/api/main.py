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
from ai_agent.session import HistoryStore, ProjectManager
from ai_agent.session.manager import SessionManager
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
from .routes.agent import router as agent_router
from .routes.chat import router as chat_router
from .routes.projects import router as projects_router
from .routes.sessions import router as sessions_router

logger = logging.getLogger(__name__)

# 获取静态文件目录
static_dir: Path = Path(__file__).parent / "static"
# 项目根目录
project_root: Path = Path(__file__).resolve().parent.parent.parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理

    初始化 Agent 及其依赖组件：
    - LangSmith 追踪（可选）
    - LLM 客户端
    - SessionManager（会话管理）
    - Skills Catalog（渐进式披露）
    - 工具集合（含 Read 工具 + MCP 工具）
    - ReActAgent（直接接收 BaseAgentTool 列表）

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

    # 初始化工具（内置 + MCP）
    from ai_agent.tools.base import BaseAgentTool

    # === MCP 工具集成 ===
    from ai_agent.mcp.config import load_mcp_config
    from ai_agent.mcp.manager import McpManager

    mcp_config_path = project_root / "mcp_servers.json"
    mcp_manager: McpManager | None = None
    mcp_tools: list[BaseAgentTool] = []

    if mcp_config_path.exists():
        try:
            mcp_config = load_mcp_config(mcp_config_path)
            mcp_manager = McpManager(
                config=mcp_config,
                skills_dir=project_root / "skills",
                config_path=mcp_config_path,
            )
            mcp_tools = await mcp_manager.start()
            logger.info(f"MCP 已加载 {len(mcp_tools)} 个远程工具")
        except Exception as e:
            logger.warning(f"MCP 初始化失败（可选功能）: {e}")
            mcp_manager = None

    app.state.mcp_manager = mcp_manager

    # === Skills 系统集成 ===
    # MCP 启动后再构建 Catalog（确保 skills/mcp/ 下的 SKILL.md 已生成）
    skills_dir = project_root / "skills"

    catalog = build_catalog_from_directory(skills_dir)
    catalog_prompt = get_catalog_prompt(catalog)
    logger.info(f"已加载 {len(catalog.skills)} 个 Skills: {[s.name for s in catalog.skills]}")

    settings = LLMSettings()

    # 根据配置选择搜索引擎
    search_tool: BaseAgentTool
    if settings.web_search_provider == "zhipu":
        search_tool = ZhipuWebSearchTool()
        logger.info("使用智谱 Web Search")
    else:
        search_tool = GoogleSearchTool()
        logger.info("使用 Google Search (Serper)")

    # 工具列表：内置 + MCP
    tools: list[BaseAgentTool] = [
        search_tool,
        WebContentTool(),
        ImageAnalysisTool(),
        AudioParseTool(),
        ReadTool(),
    ] + mcp_tools
    logger.info(f"已加载 {len(tools)} 个工具: {[t.name for t in tools]}")

    # 构建 system_prompt（注入 Skills Catalog 到 system prompt）
    from ai_agent.prompts.react import DEFAULT_SYSTEM_PROMPT

    system_prompt = DEFAULT_SYSTEM_PROMPT
    if catalog_prompt:
        system_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n## 可用技能\n{catalog_prompt}"

    # 创建 ReActAgent（直接传递 BaseAgentTool，Agent 内部处理 to_langchain_tool 转换）
    app.state.agent = ReActAgent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
    )
    logger.info("ReActAgent 已初始化")

    yield
    # MCP 清理
    if mcp_manager:
        await mcp_manager.stop()


app: FastAPI = FastAPI(
    title="AI Agent API",
    description="基于 LangGraph 的 AI Agent 服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(agent_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")


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
