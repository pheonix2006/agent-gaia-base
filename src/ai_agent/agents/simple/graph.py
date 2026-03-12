"""SimpleChatAgent 模块"""

from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.messages import HumanMessage

from ..base import BaseAgent


class SimpleChatAgent(BaseAgent):
    """简单对话 Agent，无工具调用"""

    def __init__(self, llm):
        super().__init__(llm)
        self._graph = self._build_graph()

    def _build_graph(self):
        """构建 LangGraph 图"""

        async def chat_node(state: MessagesState):
            response = await self.llm.ainvoke(state["messages"])
            return {"messages": [response]}

        graph = StateGraph(MessagesState)
        graph.add_node("chat", chat_node)
        graph.add_edge(START, "chat")
        graph.add_edge("chat", END)
        return graph.compile()

    async def run(self, message: str) -> str:
        """运行 Agent"""
        result = await self._graph.ainvoke({"messages": [HumanMessage(message)]})
        return result["messages"][-1].content

    def get_graph(self):
        """获取编译后的图"""
        return self._graph
