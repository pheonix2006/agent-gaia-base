"""LLM 客户端工厂模块"""

from langchain_openai import ChatOpenAI

from .config import LLMSettings


def create_llm_client(settings: LLMSettings | None = None) -> ChatOpenAI:
    """创建 LLM 客户端

    Args:
        settings: LLM 配置，不传则自动从 .env 加载

    Returns:
        ChatOpenAI 客户端实例
    """
    if settings is None:
        settings = LLMSettings()  # type: ignore[call-arg]

    return ChatOpenAI(
        api_key=settings.openai_api_key,  # type: ignore[arg-type]
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.temperature,
    )
