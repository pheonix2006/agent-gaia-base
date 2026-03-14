"""LangSmith 追踪配置模块"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class LangSmithSettings(BaseSettings):
    """LangSmith 追踪配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project_name: str = "ai-agent"

    def setup(self) -> None:
        """配置 LangSmith 环境变量"""
        os.environ["LANGSMITH_TRACING"] = str(self.langsmith_tracing).lower()
        os.environ["LANGSMITH_ENDPOINT"] = self.langsmith_endpoint
        os.environ["LANGSMITH_API_KEY"] = self.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = self.langsmith_project_name
        # 启用 LangChain v2 tracing（与 LangSmith 兼容）
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
