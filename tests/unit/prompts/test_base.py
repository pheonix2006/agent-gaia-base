import pytest


def test_base_prompt_is_abstract():
    """测试 BasePrompt 是抽象类"""
    from ai_agent.prompts.base import BasePrompt

    with pytest.raises(TypeError):
        BasePrompt()


def test_base_prompt_concrete_implementation():
    """测试具体实现"""
    from ai_agent.prompts.base import BasePrompt

    class SimplePrompt(BasePrompt):
        @property
        def template(self) -> str:
            return "Hello {name}!"

        def format(self, **kwargs) -> str:
            return self.template.format(**kwargs)

    prompt = SimplePrompt()
    assert prompt.template == "Hello {name}!"
    assert prompt.format(name="World") == "Hello World!"
