"""ReAct Agent - 基于原生 tool_calling 的 2 节点 LangGraph 实现"""

import json
from typing import Any, AsyncIterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_agent.agents.base import BaseAgent
from ai_agent.memory.base import BaseMemory
from ai_agent.tools.base import BaseAgentTool
from ai_agent.types.agents import AgentContext, AgentEvent, AgentEventType, AgentState
from ai_agent.types.common import AnyDict

DEFAULT_SYSTEM_PROMPT = (
    "你是一个 AI 助手。使用提供的工具来回答用户的问题。"
    "在回答之前，请充分思考并使用可用的工具来收集信息。"
    "当你有足够的信息时，直接回复用户。"
)


class ReActAgent(BaseAgent):
    """ReAct Agent：使用 LLM 原生 tool_calling 的 2 节点状态图。

    图结构：
        START -> agent -> (conditional) -> tools -> agent -> ... -> END
                                   \\-> END

    - agent 节点：调用 LLM（已 bind_tools），LLM 决定调用工具或直接回复
    - tools 节点：执行工具调用，将结果作为 ToolMessage 返回
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseAgentTool],
        *,
        max_steps: int = 20,
        system_prompt: str | None = None,
        memory: BaseMemory | None = None,
    ) -> None:
        super().__init__(llm, tools)
        self.max_steps = max_steps
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.memory = memory
        self._graph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        """构建 2 节点 LangGraph 状态图"""
        self._lc_tools = [t.to_langchain_tool() for t in self.tools]
        self._llm_with_tools = self.llm.bind_tools(self._lc_tools)

        graph = StateGraph(AgentState)
        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tool_node)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", self._should_continue)
        graph.add_edge("tools", "agent")
        return graph.compile()

    async def _agent_node(self, state: AgentState) -> dict:
        """agent 节点：调用 LLM（已绑定工具）"""
        response = await self._llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    async def _tool_node(self, state: AgentState) -> dict:
        """tools 节点：执行工具调用"""
        last_message = state["messages"][-1]
        assert isinstance(last_message, AIMessage), (
            f"Expected AIMessage, got {type(last_message).__name__}"
        )
        tool_messages: list[ToolMessage] = []
        for tool_call in last_message.tool_calls:
            tool = self._tool_map.get(tool_call["name"])
            if tool is None:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: unknown tool '{tool_call['name']}'",
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                )
                continue
            try:
                params_model = tool.params_schema(**tool_call["args"])
                result = await tool.run(params_model)
                content = (
                    result.data
                    if isinstance(result.data, str)
                    else json.dumps(result.data, ensure_ascii=False)
                )
                tool_messages.append(
                    ToolMessage(content=content, tool_call_id=tool_call["id"])
                )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing tool '{tool_call['name']}': {e}",
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                )
        return {
            "messages": tool_messages,
            "step_count": state.get("step_count", 0) + 1,
        }

    def _should_continue(self, state: AgentState) -> str:
        """条件边：判断是否继续调用工具"""
        if state.get("step_count", 0) >= self.max_steps:
            return END
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    def update_tools(self, tools: list[BaseAgentTool]) -> None:
        """运行时更新工具列表"""
        self.tools = tools
        self._tool_map = {t.name: t for t in tools}
        self._lc_tools = [t.to_langchain_tool() for t in tools]
        self._llm_with_tools = self.llm.bind_tools(self._lc_tools)

    def _build_messages(
        self, message: str, context: AgentContext | None
    ) -> list:
        """构建输入消息列表"""
        messages: list = []
        system_content = self.system_prompt
        if context:
            if context.system_prompt_override:
                system_content = context.system_prompt_override
            if context.memory_text:
                system_content += f"\n\n## 历史记忆\n{context.memory_text}"
        messages.append(SystemMessage(content=system_content))
        messages.append(HumanMessage(content=message))
        return messages

    async def run(
        self, message: str, *, context: AgentContext | None = None
    ) -> str:
        """运行 Agent，返回最终文本回复。

        Args:
            message: 用户输入消息
            context: 可选的 Agent 上下文（系统提示覆盖、记忆、步数覆盖）

        Returns:
            Agent 的最终文本回复
        """
        messages = self._build_messages(message, context)

        result = await self._graph.ainvoke(
            {"messages": messages, "step_count": 0}
        )
        return str(result["messages"][-1].content)

    def _translate_event(
        self, raw_event: Any, current_step: int
    ) -> AgentEvent | None:
        """将 LangGraph astream_events 原始事件转换为 AgentEvent。

        Args:
            raw_event: LangGraph astream_events 的原始事件字典
            current_step: 当前步骤编号

        Returns:
            转换后的 AgentEvent，或 None（如果事件不需要对外暴露）
        """
        from datetime import datetime

        kind = raw_event["event"]

        if kind == "on_chat_model_stream":
            chunk = raw_event["data"]["chunk"]
            if chunk.content:
                return AgentEvent(
                    type=AgentEventType.TEXT,
                    data={"content": chunk.content},
                    step=current_step,
                    timestamp=datetime.now(),
                )
            if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                tc_chunk = chunk.tool_call_chunks[0]
                return AgentEvent(
                    type=AgentEventType.TOOL_CALL,
                    data={
                        "name": tc_chunk.get("name", ""),
                        "args": tc_chunk.get("args", ""),
                    },
                    step=current_step,
                    timestamp=datetime.now(),
                )
            return None

        if kind == "on_tool_start":
            return AgentEvent(
                type=AgentEventType.TOOL_CALL,
                data={
                    "name": raw_event["data"].get("name", ""),
                    "args": raw_event["data"].get("input", {}),
                },
                step=current_step,
                timestamp=datetime.now(),
            )

        if kind == "on_tool_end":
            return AgentEvent(
                type=AgentEventType.TOOL_RESULT,
                data={"content": str(raw_event["data"].get("output", ""))},
                step=current_step,
                timestamp=datetime.now(),
            )

        return None

    async def stream(  # type: ignore[override]
        self, message: str, *, context: AgentContext | None = None
    ) -> AsyncIterator[AgentEvent]:
        """流式运行 Agent，yield AgentEvent 事件序列。

        使用 LangGraph 的 astream_events API 获取细粒度事件流，
        并通过 _translate_event 转换为统一的 AgentEvent 格式。

        Args:
            message: 用户输入消息
            context: 可选的 Agent 上下文

        Yields:
            AgentEvent: 执行过程中的事件
        """
        from datetime import datetime

        messages = self._build_messages(message, context)
        step = 0
        last_text = ""
        async for event in self._graph.astream_events(
            {"messages": messages, "step_count": 0}, version="v2"
        ):
            translated = self._translate_event(event, step)
            if translated is not None:
                step = max(step, translated.step + 1)
                if translated.type == AgentEventType.TEXT:
                    last_text += translated.data.get("content", "")
                yield translated
        # 循环结束后 yield DONE 事件
        yield AgentEvent(
            type=AgentEventType.DONE,
            data={"answer": last_text},
            step=step,
            timestamp=datetime.now(),
        )

    def get_graph(self) -> CompiledStateGraph:
        return self._graph
