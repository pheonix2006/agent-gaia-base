"""LLM 配置模块"""

from pydantic import Field, field_validator
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
    openai_api_key: str = Field(default="", repr=False)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Jina API 配置（网页内容提取）
    jina_api_key: str = Field(default="", repr=False)
    jina_use_free_mode: bool = False

    # Serper API 配置（Google 搜索）
    serper_api_key: str = Field(default="", repr=False)
    serper_base_url: str = "https://google.serper.dev/search"

    # 智谱 Web Search API 配置
    zhipu_api_key: str = Field(default="", repr=False)
    zhipu_web_search_url: str = "https://open.bigmodel.cn/api/paas/v4/web_search"

    # 搜索引擎选择：zhipu | google
    web_search_provider: str = Field(default="zhipu", description="搜索引擎提供者")

    @field_validator("openai_base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """验证 URL 格式"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str:
        """验证 API Key 不为空"""
        if not v:
            raise ValueError("OPENAI_API_KEY is required")
        return v
