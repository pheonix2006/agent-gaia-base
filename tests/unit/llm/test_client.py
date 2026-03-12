# tests/unit/llm/test_client.py
"""LLM 客户端工厂测试"""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_create_llm_client_with_settings():
    """测试使用配置创建 LLM 客户端"""
    os.environ["OPENAI_API_KEY"] = "test-key"

    from ai_agent.llm.config import LLMSettings
    from ai_agent.llm.client import create_llm_client

    settings = LLMSettings()
    client = create_llm_client(settings)

    assert client is not None
    assert client.model_name == settings.openai_model


def test_create_llm_client_without_settings():
    """测试不传配置时自动加载"""
    os.environ["OPENAI_API_KEY"] = "auto-key"

    from ai_agent.llm.client import create_llm_client

    client = create_llm_client()

    assert client is not None


def test_llm_client_configuration():
    """测试客户端配置正确性"""
    os.environ["OPENAI_API_KEY"] = "config-test-key"
    os.environ["OPENAI_BASE_URL"] = "https://test.api.com/v1"
    os.environ["OPENAI_MODEL"] = "test-model"
    os.environ["TEMPERATURE"] = "0.3"

    from ai_agent.llm.config import LLMSettings
    from ai_agent.llm.client import create_llm_client

    settings = LLMSettings()
    client = create_llm_client(settings)

    assert client.model_name == "test-model"
    assert client.temperature == 0.3
