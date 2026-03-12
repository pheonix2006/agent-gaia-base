# tests/conftest.py
"""Pytest 配置"""
import os
import pytest
from dotenv import load_dotenv

# 在测试开始前加载 .env 文件
load_dotenv()


@pytest.fixture(autouse=True)
def setup_env():
    """设置测试环境变量"""
    # 如果环境变量不存在，设置测试默认值
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "test-api-key"
    if "LANGSMITH_API_KEY" not in os.environ:
        os.environ["LANGSMITH_API_KEY"] = "test-langsmith-key"

    yield
