"""ReAct Prompt 模板"""

from typing import Any
from .base import BasePrompt


REACT_TEMPLATE = """==== Your Task ====
{task_instruction}

==== Context ====
{context}

==== Original Question (for reference) ====
{original_question}

==== Available Tools ====
{action_space}

==== Guidelines ====
1. Focus on completing YOUR TASK above
2. Think step by step before outputting an action
3. Write key observations to the "memory" field
4. Use tools to gather information or take actions
5. Once done, use 'finish' IMMEDIATELY
6. ⚠️ Always check tool parameter limits (e.g., web_search query ≤ 70 chars)
7. If a query is too long, split into multiple tool calls
8. ⚠️ Always provide ALL required parameters for each tool (check tool descriptions)
9. If unsure about parameters, check the tool's parameter schema first

⚠️ BUDGET: When remaining_steps <= 5, use 'finish' NOW!

==== Output Format ====
```json
{{
    "action": "<tool_name>",
    "params": {{}},
    "memory": "<observations>"
}}
```

==== Memory ====
{memory}

==== Current Observation ====
{obs}"""


class ReActPrompt(BasePrompt):
    """ReAct Prompt 模板类"""

    def __init__(
        self,
        task_instruction: str = "Answer the user's question accurately.",
        context: str = "No additional context provided.",
    ):
        self._task_instruction = task_instruction
        self._context = context
        self._template = REACT_TEMPLATE

    @property
    def template(self) -> str:
        return self._template

    def format(  # type: ignore[override]
        self,
        original_question: str,
        action_space: str,
        memory: str = "None",
        obs: str = "None",
        **kwargs: Any,
    ) -> str:
        """格式化 ReAct Prompt"""
        return self._template.format(
            task_instruction=self._task_instruction,
            context=self._context,
            original_question=original_question,
            action_space=action_space,
            memory=memory,
            obs=obs,
        )

    def with_task(self, task: str) -> "ReActPrompt":
        """链式调用：设置任务指令"""
        self._task_instruction = task
        return self

    def with_context(self, context: str) -> "ReActPrompt":
        """链式调用：设置上下文"""
        self._context = context
        return self
