"""全局配置管理模块

提供全局配置的创建、读取、更新和合并功能。

核心功能:
- 初始化创建默认配置
- get_llm_config() - 获取 LLM 配置
- set_api_key(provider, key) - 设置 API Key
- get_merged_config(project_dir) - 合并项目级覆盖配置
"""

import json
import os
from pathlib import Path
from typing import Any


class ConfigManager:
    """全局配置管理器

    管理全局配置文件，支持项目级配置覆盖。

    Attributes:
        config_path: 配置文件路径
        _config: 内存中的配置缓存
    """

    # 默认配置结构
    DEFAULT_CONFIG: dict[str, Any] = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "temperature": 0.7,
        },
        "api_keys": {},
    }

    # 环境变量映射
    ENV_KEY_MAPPING: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "jina": "JINA_API_KEY",
        "serper": "SERPER_API_KEY",
        "zhipu": "ZHIPU_API_KEY",
    }

    def __init__(self, config_path: Path):
        """初始化配置管理器

        如果配置文件不存在，将创建默认配置。

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._load_or_create()

    def _load_or_create(self) -> None:
        """加载或创建配置文件"""
        if self.config_path.exists():
            try:
                content = self.config_path.read_text(encoding="utf-8")
                self._config = json.loads(content)
            except (json.JSONDecodeError, OSError):
                # 无效 JSON，使用默认配置
                self._config = self._get_default_config()
                self._save()
        else:
            self._config = self._get_default_config()
            self._ensure_parent_dir()
            self._save()

    def _get_default_config(self) -> dict[str, Any]:
        """获取默认配置的深拷贝"""
        result: dict[str, Any] = json.loads(json.dumps(self.DEFAULT_CONFIG))
        return result

    def _ensure_parent_dir(self) -> None:
        """确保父目录存在"""
        parent = self.config_path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    def _save(self) -> None:
        """保存配置到文件"""
        self._ensure_parent_dir()
        content = json.dumps(self._config, indent=2, ensure_ascii=False)
        self.config_path.write_text(content, encoding="utf-8")

    def get_llm_config(self) -> dict[str, Any]:
        """获取 LLM 配置

        返回 LLM 配置，包含 provider、model、api_key 等字段。

        Returns:
            LLM 配置字典
        """
        llm_config: dict[str, Any] = self._config.get("llm", {}).copy()

        # 确保 API Key 从 api_keys 或环境变量获取
        provider = llm_config.get("provider", "openai")
        if not isinstance(provider, str):
            provider = "openai"
        api_key = self.get_api_key(provider)
        llm_config["api_key"] = api_key or ""

        return llm_config

    def set_api_key(self, provider: str, key: str) -> None:
        """设置 API Key

        将 API Key 保存到配置文件中。

        Args:
            provider: 提供者名称（如 openai, anthropic）
            key: API Key
        """
        if "api_keys" not in self._config:
            self._config["api_keys"] = {}

        self._config["api_keys"][provider] = key
        self._save()

    def get_api_key(self, provider: str) -> str | None:
        """获取 API Key

        优先从配置文件获取，其次从环境变量获取。

        Args:
            provider: 提供者名称

        Returns:
            API Key 或 None
        """
        # 1. 从 api_keys 节点获取
        api_keys = self._config.get("api_keys", {})
        if provider in api_keys and api_keys[provider]:
            key: str | None = str(api_keys[provider])
            return key

        # 2. 从 llm.api_key 获取（仅当 provider 匹配时）
        llm_config = self._config.get("llm", {})
        if llm_config.get("provider") == provider and llm_config.get("api_key"):
            result: str | None = str(llm_config["api_key"])
            return result

        # 3. 从环境变量获取
        env_key = self.ENV_KEY_MAPPING.get(provider)
        if env_key:
            return os.environ.get(env_key)

        return None

    def get_merged_config(self, project_dir: Path | None = None) -> dict[str, Any]:
        """获取合并后的配置

        合并全局配置和项目级配置（如果存在）。

        Args:
            project_dir: 项目目录路径

        Returns:
            合并后的配置字典
        """
        # 从全局配置深拷贝
        merged = self._deep_merge({}, self._config)

        # 如果提供了项目目录，合并项目配置
        if project_dir is not None:
            project_config_path = Path(project_dir) / ".aiagent.json"
            if project_config_path.exists():
                try:
                    content = project_config_path.read_text(encoding="utf-8")
                    project_config = json.loads(content)
                    merged = self._deep_merge(merged, project_config)
                except (json.JSONDecodeError, OSError):
                    # 无效的项目配置，忽略
                    pass

        # 确保 LLM 配置中的 API Key 正确
        if "llm" in merged:
            provider = merged["llm"].get("provider", "openai")
            api_key = self.get_api_key(provider)
            merged["llm"]["api_key"] = api_key or ""

        return merged

    def _deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """深度合并两个字典

        Args:
            base: 基础字典
            override: 覆盖字典

        Returns:
            合并后的新字典
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result
