"""ReAct Prompt 模板

重构后：工具描述通过 bind_tools() 传递，不再嵌入 prompt。
ReActPrompt 类保留用于 system_prompt 定制（task_instruction + context）。
"""

from typing import Any
from .base import BasePrompt


DEFAULT_SYSTEM_PROMPT = """你是一个 AI 助手。使用提供的工具来回答用户的问题。

## 行为准则

1. 在回答之前，请充分思考并使用可用的工具来收集信息
2. 当你有足够的信息时，直接回复用户
3. 如果工具调用失败，基于已有信息给出最佳回答
4. 保持回答准确、简洁、有帮助"""


class ReActPrompt(BasePrompt):
    """ReAct Prompt 模板类（简化版）

    重构后不再构建 action_space。
    format() 只需要 original_question，生成 system prompt 格式的文本。
    """

    def __init__(
        self,
        task_instruction: str = "Answer the user's question accurately.",
        context: str = "No additional context provided.",
    ) -> None:
        self._task_instruction = task_instruction
        self._context = context
        self._template = DEFAULT_SYSTEM_PROMPT

    @property
    def template(self) -> str:
        return self._template

    def format(  # type: ignore[override]
        self,
        original_question: str,
        **kwargs: Any,
    ) -> str:
        """格式化 ReAct Prompt

        简化版：不再接受 action_space、memory、obs 参数。
        只注入 task_instruction、context 和 original_question。

        Args:
            original_question: 用户原始问题
            **kwargs: 忽略额外的关键字参数（向后兼容）

        Returns:
            格式化后的 prompt 字符串
        """
        sections = []

        sections.append(f"## 任务\n{self._task_instruction}")

        if self._context and self._context != "No additional context provided.":
            sections.append(f"## 上下文\n{self._context}")

        sections.append(f"## 用户问题\n{original_question}")

        return "\n\n".join(sections)

    def with_task(self, task: str) -> "ReActPrompt":
        """链式调用：设置任务指令"""
        self._task_instruction = task
        return self

    def with_context(self, context: str) -> "ReActPrompt":
        """链式调用：设置上下文"""
        self._context = context
        return self
