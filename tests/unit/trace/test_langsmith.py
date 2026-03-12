# tests/unit/trace/test_langsmith.py
"""LangSmith 追踪配置测试"""
import os
import pytest


def test_langsmith_settings_from_env():
    """测试从环境变量加载 LangSmith 配置"""
    # 使用测试值
    os.environ["LANGSMITH_API_KEY"] = "test-langsmith-key"
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT_NAME"] = "test-project"

    from ai_agent.trace.langsmith import LangSmithSettings

    settings = LangSmithSettings()

    assert settings.langsmith_tracing is True
    assert settings.langsmith_project_name == "test-project"
    assert settings.langsmith_api_key == "test-langsmith-key"


def test_langsmith_setup_sets_environment():
    """测试 setup 方法设置环境变量"""
    os.environ["LANGSMITH_API_KEY"] = "setup-test-key"
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT_NAME"] = "setup-project"

    from ai_agent.trace.langsmith import LangSmithSettings

    settings = LangSmithSettings()
    settings.setup()

    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_PROJECT") == "setup-project"
    assert os.environ.get("LANGSMITH_API_KEY") == "setup-test-key"


def test_langsmith_can_be_disabled():
    """测试可以禁用追踪"""
    os.environ["LANGSMITH_API_KEY"] = "disable-test-key"
    os.environ["LANGSMITH_TRACING"] = "false"

    from ai_agent.trace.langsmith import LangSmithSettings

    settings = LangSmithSettings()

    assert settings.langsmith_tracing is False
