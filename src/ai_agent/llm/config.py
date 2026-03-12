"""LLM 配置模块"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM 配置

    从 .env 文件加载配置，支持所有兼容 OpenAI API 的服务。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI 兼容 API 配置
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"
    temperature: float = 0.7

    # Jina API 配置（网页内容提取）
    jina_api_key: str = ""

    # Serper API 配置（Google 搜索）
    serper_api_key: str = ""
    serper_base_url: str = "https://google.serper.dev/search"
