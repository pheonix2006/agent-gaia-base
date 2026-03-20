"""ConfigManager 类的单元测试

测试对象: src/ai_agent/session/config.py

TDD 流程: 先写失败测试，再实现最小代码使测试通过
"""

import json
from pathlib import Path
from typing import Generator

import pytest


class TestConfigManagerInit:
    """ConfigManager 初始化测试"""

    def test_init_creates_config_file(self, tmp_path: Path):
        """初始化时应自动创建默认配置文件"""
        from ai_agent.session.config import ConfigManager

        config_path = tmp_path / "config.json"
        assert not config_path.exists()

        manager = ConfigManager(config_path)

        assert config_path.exists()

    def test_init_with_existing_config(self, tmp_path: Path):
        """使用已存在的配置文件初始化"""
        from ai_agent.session.config import ConfigManager

        config_path = tmp_path / "config.json"
        existing_config = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "existing-key"
            }
        }
        config_path.write_text(json.dumps(existing_config), encoding="utf-8")

        manager = ConfigManager(config_path)

        assert manager.get_llm_config()["provider"] == "openai"
        assert manager.get_llm_config()["model"] == "gpt-4"

    def test_init_creates_default_config(self, tmp_path: Path):
        """初始化应创建默认配置结构"""
        from ai_agent.session.config import ConfigManager

        config_path = tmp_path / "config.json"
        ConfigManager(config_path)

        content = config_path.read_text(encoding="utf-8")
        config = json.loads(content)

        assert "llm" in config
        assert "provider" in config["llm"]
        assert "model" in config["llm"]


class TestConfigManagerGetLLMConfig:
    """ConfigManager get_llm_config 测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path, monkeypatch) -> "ConfigManager":
        """创建 ConfigManager 实例（隔离环境变量）"""
        from ai_agent.session.config import ConfigManager

        # 清除可能影响测试的环境变量
        for var in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "JINA_API_KEY"]:
            monkeypatch.delenv(var, raising=False)

        return ConfigManager(tmp_path / "config.json")

    def test_get_llm_config_returns_dict(self, manager: "ConfigManager"):
        """获取 LLM 配置应返回字典"""
        from ai_agent.session.config import ConfigManager

        config = manager.get_llm_config()

        assert isinstance(config, dict)

    def test_get_llm_config_has_required_fields(self, manager: "ConfigManager"):
        """LLM 配置应包含必需字段"""
        config = manager.get_llm_config()

        assert "provider" in config
        assert "model" in config
        assert "api_key" in config

    def test_get_llm_config_default_provider(self, manager: "ConfigManager"):
        """默认 LLM 提供者应为 openai"""
        config = manager.get_llm_config()

        assert config["provider"] == "openai"

    def test_get_llm_config_default_model(self, manager: "ConfigManager"):
        """默认模型应为 gpt-4"""
        config = manager.get_llm_config()

        assert config["model"] == "gpt-4"

    def test_get_llm_config_empty_api_key_by_default(self, manager: "ConfigManager"):
        """默认 API Key 应为空字符串"""
        config = manager.get_llm_config()

        assert config["api_key"] == ""

    def test_get_llm_config_with_api_key(self, tmp_path: Path, monkeypatch):
        """获取带有 API Key 的 LLM 配置"""
        from ai_agent.session.config import ConfigManager

        # 清除环境变量以确保测试隔离
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config_path = tmp_path / "config.json"
        config_data = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "sk-test-key-123"
            }
        }
        config_path.write_text(json.dumps(config_data), encoding="utf-8")

        manager = ConfigManager(config_path)
        config = manager.get_llm_config()

        assert config["api_key"] == "sk-test-key-123"


class TestConfigManagerSetAPIKey:
    """ConfigManager set_api_key 测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "ConfigManager":
        """创建 ConfigManager 实例"""
        from ai_agent.session.config import ConfigManager

        return ConfigManager(tmp_path / "config.json")

    def test_set_api_key_updates_config(self, manager: "ConfigManager"):
        """设置 API Key 应更新配置"""
        manager.set_api_key("openai", "sk-new-key")

        config = manager.get_llm_config()
        assert config["api_key"] == "sk-new-key"

    def test_set_api_key_persists_to_file(self, manager: "ConfigManager"):
        """设置 API Key 应持久化到文件"""
        manager.set_api_key("openai", "sk-persisted-key")

        # 重新加载配置
        from ai_agent.session.config import ConfigManager

        new_manager = ConfigManager(manager.config_path)
        config = new_manager.get_llm_config()

        assert config["api_key"] == "sk-persisted-key"

    def test_set_api_key_overwrites_existing(self, manager: "ConfigManager"):
        """设置 API Key 应覆盖已有的 Key"""
        manager.set_api_key("openai", "sk-first")
        manager.set_api_key("openai", "sk-second")

        config = manager.get_llm_config()
        assert config["api_key"] == "sk-second"

    def test_set_api_key_for_different_providers(self, tmp_path: Path):
        """为不同提供者设置 API Key"""
        from ai_agent.session.config import ConfigManager

        manager = ConfigManager(tmp_path / "config.json")

        manager.set_api_key("openai", "sk-openai-key")
        manager.set_api_key("anthropic", "sk-ant-key")

        # 验证配置文件包含两个 key
        content = manager.config_path.read_text(encoding="utf-8")
        config = json.loads(content)

        assert config["api_keys"]["openai"] == "sk-openai-key"
        assert config["api_keys"]["anthropic"] == "sk-ant-key"


class TestConfigManagerGetMergedConfig:
    """ConfigManager get_merged_config 测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "ConfigManager":
        """创建 ConfigManager 实例"""
        from ai_agent.session.config import ConfigManager

        return ConfigManager(tmp_path / "config.json")

    def test_get_merged_config_returns_dict(self, manager: "ConfigManager"):
        """获取合并配置应返回字典"""
        config = manager.get_merged_config()

        assert isinstance(config, dict)

    def test_get_merged_config_includes_llm(self, manager: "ConfigManager"):
        """合并配置应包含 LLM 配置"""
        config = manager.get_merged_config()

        assert "llm" in config

    def test_get_merged_config_with_project_override(self, manager: "ConfigManager", tmp_path: Path):
        """项目级配置应覆盖全局配置"""
        # 设置全局配置
        manager.set_api_key("openai", "sk-global-key")

        # 创建项目级配置
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        project_config = {
            "llm": {
                "model": "gpt-4-turbo"
            }
        }
        (project_dir / ".aiagent.json").write_text(
            json.dumps(project_config), encoding="utf-8"
        )

        merged = manager.get_merged_config(project_dir)

        # API Key 来自全局
        assert merged["llm"]["api_key"] == "sk-global-key"
        # model 来自项目覆盖
        assert merged["llm"]["model"] == "gpt-4-turbo"

    def test_get_merged_config_without_project_dir(self, manager: "ConfigManager"):
        """无项目目录时返回全局配置"""
        config = manager.get_merged_config()

        assert "llm" in config
        assert config["llm"]["provider"] == "openai"

    def test_get_merged_config_no_project_config_file(self, manager: "ConfigManager", tmp_path: Path):
        """项目目录无配置文件时返回全局配置"""
        project_dir = tmp_path / "no-config-project"
        project_dir.mkdir()

        manager.set_api_key("openai", "sk-test")
        merged = manager.get_merged_config(project_dir)

        assert merged["llm"]["api_key"] == "sk-test"
        assert merged["llm"]["model"] == "gpt-4"

    def test_get_merged_config_deep_merge(self, manager: "ConfigManager", tmp_path: Path):
        """深层合并配置（不完全覆盖）"""
        # 设置全局配置
        manager.set_api_key("openai", "sk-global")

        # 项目级配置只覆盖部分字段
        project_dir = tmp_path / "deep-merge-project"
        project_dir.mkdir()
        project_config = {
            "llm": {
                "temperature": 0.5
            },
            "tools": {
                "web_search": {
                    "enabled": True
                }
            }
        }
        (project_dir / ".aiagent.json").write_text(
            json.dumps(project_config), encoding="utf-8"
        )

        merged = manager.get_merged_config(project_dir)

        # 全局配置保留
        assert merged["llm"]["api_key"] == "sk-global"
        assert merged["llm"]["provider"] == "openai"
        # 项目覆盖生效
        assert merged["llm"]["temperature"] == 0.5
        # 新增的项目配置
        assert merged["tools"]["web_search"]["enabled"] is True


class TestConfigManagerAdditionalAPIs:
    """ConfigManager 其他 API 测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> "ConfigManager":
        """创建 ConfigManager 实例"""
        from ai_agent.session.config import ConfigManager

        return ConfigManager(tmp_path / "config.json")

    def test_get_api_key_existing(self, manager: "ConfigManager"):
        """获取已存在的 API Key"""
        manager.set_api_key("openai", "sk-test")

        key = manager.get_api_key("openai")

        assert key == "sk-test"

    def test_get_api_key_not_found(self, manager: "ConfigManager"):
        """获取不存在的 API Key 应返回 None"""
        key = manager.get_api_key("unknown-provider")

        assert key is None

    def test_get_api_key_from_env_fallback(self, tmp_path: Path, monkeypatch):
        """API Key 应从环境变量回退获取"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

        from ai_agent.session.config import ConfigManager

        manager = ConfigManager(tmp_path / "config.json")
        key = manager.get_api_key("openai")

        assert key == "sk-from-env"

    def test_config_file_pretty_formatted(self, tmp_path: Path):
        """配置文件应以易读格式保存"""
        from ai_agent.session.config import ConfigManager

        config_path = tmp_path / "config.json"
        ConfigManager(config_path)

        content = config_path.read_text(encoding="utf-8")

        # 应包含缩进
        assert "  " in content
        # 应包含换行
        assert "\n" in content


class TestConfigManagerErrorHandling:
    """ConfigManager 错误处理测试"""

    def test_invalid_json_falls_back_to_default(self, tmp_path: Path):
        """无效 JSON 应回退到默认配置"""
        from ai_agent.session.config import ConfigManager

        config_path = tmp_path / "config.json"
        config_path.write_text("invalid json {{{", encoding="utf-8")

        manager = ConfigManager(config_path)

        # 应使用默认配置
        config = manager.get_llm_config()
        assert config["provider"] == "openai"

    def test_project_config_invalid_json_ignored(self, tmp_path: Path):
        """项目配置无效 JSON 应被忽略"""
        from ai_agent.session.config import ConfigManager

        manager = ConfigManager(tmp_path / "config.json")
        manager.set_api_key("openai", "sk-test")

        # 创建无效的项目配置
        project_dir = tmp_path / "invalid-project"
        project_dir.mkdir()
        (project_dir / ".aiagent.json").write_text(
            "invalid json {{{", encoding="utf-8"
        )

        # 应返回全局配置，不抛出异常
        merged = manager.get_merged_config(project_dir)
        assert merged["llm"]["api_key"] == "sk-test"
