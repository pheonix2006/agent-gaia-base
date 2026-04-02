"""ReAct Prompt 简化后的单元测试"""

import pytest


def test_default_system_prompt_exists():
    """DEFAULT_SYSTEM_PROMPT 常量存在且是非空字符串"""
    from ai_agent.prompts.react import DEFAULT_SYSTEM_PROMPT

    assert isinstance(DEFAULT_SYSTEM_PROMPT, str)
    assert len(DEFAULT_SYSTEM_PROMPT) > 0


def test_default_system_prompt_contains_key_instructions():
    """DEFAULT_SYSTEM_PROMPT 包含关键指令关键词"""
    from ai_agent.prompts.react import DEFAULT_SYSTEM_PROMPT

    assert "工具" in DEFAULT_SYSTEM_PROMPT or "tool" in DEFAULT_SYSTEM_PROMPT.lower()
    assert "思考" in DEFAULT_SYSTEM_PROMPT or "think" in DEFAULT_SYSTEM_PROMPT.lower()


def test_react_prompt_no_action_space_parameter():
    """ReActPrompt.format() 不再接受 action_space 参数"""
    from ai_agent.prompts.react import ReActPrompt

    prompt = ReActPrompt()
    formatted = prompt.format(original_question="What is 2+2?")
    assert isinstance(formatted, str)
    assert "What is 2+2?" in formatted


def test_react_prompt_with_task():
    """with_task 链式调用仍然有效"""
    from ai_agent.prompts.react import ReActPrompt

    prompt = ReActPrompt().with_task("Solve math problems")
    formatted = prompt.format(original_question="test")

    assert "Solve math problems" in formatted


def test_react_prompt_with_context():
    """with_context 链式调用仍然有效"""
    from ai_agent.prompts.react import ReActPrompt

    prompt = ReActPrompt().with_context("You are a math assistant")
    formatted = prompt.format(original_question="test")

    assert "You are a math assistant" in formatted


def test_react_prompt_template_property():
    """template 属性返回非空字符串"""
    from ai_agent.prompts.react import ReActPrompt

    prompt = ReActPrompt()
    assert prompt.template is not None
    assert isinstance(prompt.template, str)
    assert len(prompt.template) > 0


def test_react_prompt_default_values():
    """默认 task_instruction 和 context 有合理值"""
    from ai_agent.prompts.react import ReActPrompt

    prompt = ReActPrompt()
    formatted = prompt.format(original_question="hello")

    assert len(formatted) > 0
