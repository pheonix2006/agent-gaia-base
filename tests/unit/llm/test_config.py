# tests/unit/llm/test_config.py
"""LLM 配置测试"""
import os
import pytest
from pydantic import ValidationError


def test_llm_settings_from_env():
    """测试从环境变量加载 LLM 配置"""
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["OPENAI_BASE_URL"] = "https://api.test.com/v1"
    os.environ["OPENAI_MODEL"] = "test-model"
    os.environ["TEMPERATURE"] = "0.5"

    from ai_agent.llm.config import LLMSettings

    settings = LLMSettings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_base_url == "https://api.test.com/v1"
    assert settings.openai_model == "test-model"
    assert settings.temperature == 0.5


def test_llm_settings_defaults():
    """测试 LLM 配置默认值"""
    os.environ["OPENAI_API_KEY"] = "default-key"
    # 清除其他环境变量以测试默认值
    for key in ["OPENAI_BASE_URL", "OPENAI_MODEL", "TEMPERATURE"]:
        if key in os.environ:
            del os.environ[key]

    from ai_agent.llm.config import LLMSettings

    settings = LLMSettings()

    assert settings.openai_api_key == "default-key"
    # 默认值应该从类定义中获取
    assert settings.temperature == 0.7


def test_llm_settings_missing_api_key():
    """测试缺少 API Key 时抛出错误（不使用 .env 文件）"""
    # 清除环境变量
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

    from ai_agent.llm.config import LLMSettings

    # 使用 _env_file=None 来忽略 .env 文件
    with pytest.raises(ValidationError):
        LLMSettings(_env_file=None)


def test_llm_settings_temperature_validation():
    """测试温度参数验证"""
    os.environ["OPENAI_API_KEY"] = "temp-key"
    os.environ["TEMPERATURE"] = "1.5"  # 有效范围

    from ai_agent.llm.config import LLMSettings

    settings = LLMSettings()
    assert settings.temperature == 1.5
