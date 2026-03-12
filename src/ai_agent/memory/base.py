"""Memory 模块 - 支持 ReAct 及其他 Agent 类型的记忆管理"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel


class MemoryRecord(BaseModel):
    """单条记忆记录

    用于存储 Agent 执行过程中的观察、动作和思考过程。
    """

    observation: Dict[str, Any]  # 从环境获取的观察结果
    action: Dict[str, Any]  # Agent 执行的动作及其参数
    thinking: Optional[str] = None  # 推理过程 (可选)
    reward: Optional[float] = None  # 奖励信号 (可选)
    raw_response: Optional[str] = None  # LLM 原始响应 (可选)


class BaseMemory(ABC):
    """Memory 基类，定义统一接口"""

    @abstractmethod
    async def add(self, record: MemoryRecord) -> None:
        """添加记忆"""

    @abstractmethod
    def as_text(self) -> str:
        """转换为可注入 Prompt 的文本"""

    @abstractmethod
    def clear(self) -> None:
        """清空记忆"""


class CompressedMemory(BaseMemory):
    """
    带压缩功能的 Memory 实现
    - 保留最近 keep_recent 条完整记录
    - 早期记录通过 LLM 压缩为摘要
    """

    def __init__(
        self,
        llm: BaseChatModel,
        max_memory: int = 10,
        keep_recent: int = 3,
    ):
        if max_memory < 1:
            raise ValueError("max_memory must be at least 1")
        if keep_recent < 0:
            raise ValueError("keep_recent must be non-negative")
        if keep_recent > max_memory:
            raise ValueError("keep_recent cannot exceed max_memory")

        self.llm = llm
        self.max_memory = max_memory
        self.keep_recent = keep_recent
        self._records: List[MemoryRecord] = []
        self._summary: Optional[str] = None

    async def add(self, record: MemoryRecord) -> None:
        """添加记忆并触发压缩检查"""
        self._records.append(record)
        await self._compress()

    async def add_raw(
        self,
        observation: Dict[str, Any],
        action: Dict[str, Any],
        thinking: Optional[str] = None,
        reward: Optional[float] = None,
        raw_response: Optional[str] = None,
    ) -> None:
        """便捷方法：直接添加原始数据"""
        record = MemoryRecord(
            observation=observation,
            action=action,
            thinking=thinking,
            reward=reward,
            raw_response=raw_response,
        )
        await self.add(record)

    def as_text(self) -> str:
        """生成可注入 Prompt 的文本"""
        if not self._summary and not self._records:
            return "None"

        parts: List[str] = []

        if self._records:
            parts.append("[Recent steps (latest first)]")
            for idx, r in enumerate(reversed(self._records), 1):
                parts.append(
                    f"{idx}. action={json.dumps(r.action, ensure_ascii=False)}, "
                    f"observation={json.dumps(r.observation, ensure_ascii=False)}, "
                    f"thinking={r.thinking}, reward={r.reward}"
                )

        if self._summary:
            parts.append("")
            parts.append("[Summary of earlier steps]")
            parts.append(self._summary)

        return "\n".join(parts)

    def clear(self) -> None:
        """清空所有记忆"""
        self._records.clear()
        self._summary = None

    async def _compress(self) -> None:
        """达到上限时压缩旧记录"""
        if len(self._records) < self.max_memory:
            return

        if self.keep_recent > 0:
            head = self._records[:-self.keep_recent]
            tail = self._records[-self.keep_recent:]
        else:
            head = self._records[:]
            tail = []

        if head:
            head_summary = await self._summarize_records(head)
            if self._summary:
                self._summary += "\n\n" + head_summary
            else:
                self._summary = head_summary

        self._records = tail

    async def _summarize_records(self, records: List[MemoryRecord]) -> str:
        """使用 LLM 压缩记录"""
        record_lines: List[str] = []
        for idx, r in enumerate(records, 1):
            record_lines.append(
                f"{idx}. action={json.dumps(r.action, ensure_ascii=False)}, "
                f"observation={json.dumps(r.observation, ensure_ascii=False)}, "
                f"thinking={json.dumps(r.thinking, ensure_ascii=False)}, "
                f"reward={r.reward}"
            )
        records_text = "\n".join(record_lines)

        summary_prompt = f"""You are the memory compression module of a language-model-based agent.

You are given several past interaction steps in chronological order (oldest first).
Each step includes:
- the agent's action,
- the environment observation,
- the reward signal,
- the agent's thinking.

Your task is to write a compact, **persistent memory** block that lets the agent
continue its work without seeing the full history.

Please:
- Focus on:
  1) stable facts and rules about the environment/world,
  2) useful strategies / plans / tools the agent tried,
  3) important mistakes or failure patterns to avoid later,
  4) partial progress and remaining goals / TODOs.
- Use at most 8–10 lines.
- Use a neutral, factual tone.
- Do NOT repeat low-level JSON details unless they are crucial.
- Do NOT include meta text like "here is the summary" or any explanation.
- Output ONLY the memory lines, one per line.

===== PAST STEPS =====
{records_text}
===== SUMMARY (start here) ====="""

        response = await self.llm.ainvoke([HumanMessage(summary_prompt)])
        return response.content

    @property
    def record_count(self) -> int:
        """当前完整记录数"""
        return len(self._records)

    @property
    def has_summary(self) -> bool:
        """是否有压缩摘要"""
        return self._summary is not None
