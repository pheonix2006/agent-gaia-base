import pytest


def test_react_prompt_template_constant():
    """测试 REACT_TEMPLATE 常量存在"""
    from ai_agent.prompts.react import REACT_TEMPLATE

    assert "{task_instruction}" in REACT_TEMPLATE
    assert "{original_question}" in REACT_TEMPLATE
    assert "{action_space}" in REACT_TEMPLATE
    assert "{memory}" in REACT_TEMPLATE
    assert "{obs}" in REACT_TEMPLATE


def test_react_prompt_initialization():
    """测试 ReActPrompt 初始化"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt()
    assert prompt.template is not None


def test_react_prompt_format():
    """测试 ReActPrompt 格式化"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt()

    formatted = prompt.format(
        original_question="What is 2+2?",
        action_space="tools: calculator",
        memory="None",
        obs="No observation",
    )

    assert "What is 2+2?" in formatted
    assert "calculator" in formatted


def test_react_prompt_with_task():
    """测试 with_task 链式调用"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt().with_task("Solve math problems")
    formatted = prompt.format(
        original_question="test",
        action_space="none",
    )

    assert "Solve math problems" in formatted


def test_react_prompt_with_context():
    """测试 with_context 链式调用"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt().with_context("You are a math assistant")
    formatted = prompt.format(
        original_question="test",
        action_space="none",
    )

    assert "You are a math assistant" in formatted
