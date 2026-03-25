# tests/conftest.py
"""Pytest 配置"""
import os
import pytest
import asyncio
from dotenv import load_dotenv

# 在测试开始前加载 .env 文件
load_dotenv()


def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require real API keys)"
    )


@pytest.fixture(autouse=True)
def setup_env():
    """设置测试环境变量"""
    # 如果环境变量不存在，设置测试默认值
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "test-api-key"
    if "LANGSMITH_API_KEY" not in os.environ:
        os.environ["LANGSMITH_API_KEY"] = "test-langsmith-key"

    yield


@pytest.fixture
def trace_recorder(tmp_path):
    """Create TraceRecorder for current test, auto-flush on test end.

    Usage:
        def test_something(trace_recorder):
            # ... code that uses trace decorators ...
            assert trace_recorder.has_span("think").with_output(action="search")
    """
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.recorder import TraceRecorder

    config = TraceConfig(trace_dir=str(tmp_path))
    recorder = TraceRecorder(name="test", config=config)
    recorder.start_span("test")
    yield recorder
    recorder.finish_span()
    recorder.finish_run()


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
