"""SimpleChatAgent 模块"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.pregel import Pregel

from ..base import BaseAgent


class SimpleChatAgent(BaseAgent):
    """简单对话 Agent，无工具调用"""

    def __init__(self, llm: BaseChatModel) -> None:
        super().__init__(llm)
        self._graph = self._build_graph()

    def _build_graph(self) -> Pregel:
        """构建 LangGraph 图"""

        async def chat_node(state: MessagesState) -> dict[str, list[Any]]:
            response = await self.llm.ainvoke(state["messages"])
            return {"messages": [response]}

        graph = StateGraph(MessagesState)
        graph.add_node("chat", chat_node)
        graph.add_edge(START, "chat")
        graph.add_edge("chat", END)
        return graph.compile()

    async def run(self, message: str) -> str:
        """运行 Agent"""
        result = await self._graph.ainvoke({"messages": [HumanMessage(message)]})  # type: ignore[call-overload]
        content = result["messages"][-1].content
        return str(content) if content else ""

    def get_graph(self) -> Pregel:
        """获取编译后的图"""
        return self._graph
