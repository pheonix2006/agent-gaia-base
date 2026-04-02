"""ReAct Agent - 基于原生 tool_calling 的 2 节点 LangGraph 实现"""

import json
from typing import AsyncIterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
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

    # --- 以下方法在 Task 5 中实现 ---

    async def run(
        self, message: str, *, context: AgentContext | None = None
    ) -> str:
        raise NotImplementedError("Task 5")

    async def stream(  # type: ignore[override]
        self, message: str, *, context: AgentContext | None = None
    ) -> AsyncIterator[AgentEvent]:
        raise NotImplementedError("Task 5")
        yield  # type: ignore  # noqa: unreachable

    def get_graph(self) -> CompiledStateGraph:
        return self._graph
