"""ReAct Agent 实现"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, ConfigDict, Field

from ..base import BaseAgent
from ...prompts import ReActPrompt


class ReActAction(BaseModel):
    """LLM 返回的结构化动作"""

    action: str = Field(description="工具名称或 'finish'")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    memory: str = Field(default="", description="本轮观察/思考")


class AgentState(BaseModel):
    """ReAct Agent 状态"""

    question: str = Field(description="用户原始问题")
    current_obs: str = Field(default="", description="当前观察")
    steps_taken: int = Field(default=0, description="已执行步数")
    actions_history: List[ReActAction] = Field(
        default_factory=list, description="动作历史"
    )
    final_answer: Optional[str] = Field(default=None, description="最终答案")
    error: Optional[str] = Field(default=None, description="错误信息")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ReActAgent(BaseAgent):
    """
    ReAct Agent 实现
    - 结构化 JSON 输出（action + params + memory）
    - 自动终止 + 最大步数兜底
    - 工具调用重试机制
    """

    MAX_STEPS = 20
    MAX_RETRIES = 3

    def __init__(
        self,
        llm,
        tools: List[BaseTool] | None = None,
        prompt: ReActPrompt | None = None,
        max_steps: int = MAX_STEPS,
        max_retries: int = MAX_RETRIES,
    ):
        super().__init__(llm, tools)
        self.prompt = prompt or ReActPrompt()
        self.max_steps = max_steps
        self.max_retries = max_retries
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 状态图"""
        graph = StateGraph(AgentState)

        # 节点
        graph.add_node("think", self._think_node)
        graph.add_node("act", self._act_node)
        graph.add_node("observe", self._observe_node)

        # 边
        graph.add_edge(START, "think")
        graph.add_conditional_edges(
            "think",
            self._should_finish,
            {"finish": END, "continue": "act"},
        )
        graph.add_edge("act", "observe")
        graph.add_edge("observe", "think")

        return graph.compile()

    def _should_finish(self, state: AgentState) -> str:
        """判断是否应该结束"""
        if state.final_answer is not None:
            return "finish"
        if state.error and "max_retries_exceeded" in state.error:
            return "finish"
        if state.steps_taken >= self.max_steps:
            return "finish"
        return "continue"

    async def _think_node(self, state: AgentState) -> Dict[str, Any]:
        """Think 节点：调用 LLM 决定下一步行动"""
        # 构建工具描述
        action_space = self._build_action_space()

        # 格式化 Prompt
        formatted_prompt = self.prompt.format(
            original_question=state.question,
            action_space=action_space,
            memory="None",
            obs=state.current_obs or "No observation yet.",
        )

        # 调用 LLM
        response = await self.llm.ainvoke([HumanMessage(formatted_prompt)])

        # 解析 JSON 响应
        action = self._parse_action(response.content)

        if action is None:
            return {"error": "Failed to parse LLM response as JSON"}

        # 更新状态
        updates: Dict[str, Any] = {
            "actions_history": state.actions_history + [action],
        }

        # 如果是 finish，设置最终答案
        if action.action == "finish":
            updates["final_answer"] = action.params.get("answer", action.memory)

        return updates

    async def _act_node(self, state: AgentState) -> Dict[str, Any]:
        """Act 节点：执行工具调用（带重试）"""
        if not state.actions_history:
            return {"error": "No action to execute"}

        current_action = state.actions_history[-1]

        # finish 不需要执行工具
        if current_action.action == "finish":
            return {"current_obs": "Task completed."}

        # 查找工具
        tool = self._find_tool(current_action.action)
        if tool is None:
            return {
                "current_obs": f"Error: Tool '{current_action.action}' not found.",
                "steps_taken": state.steps_taken + 1,
            }

        # 执行工具（带重试）
        result = await self._execute_with_retry(tool, current_action.params)

        return {
            "current_obs": result,
            "steps_taken": state.steps_taken + 1,
        }

    async def _observe_node(self, state: AgentState) -> Dict[str, Any]:
        """Observe 节点：处理观察结果，准备下一轮"""
        return {}

    def _build_action_space(self) -> str:
        """构建工具描述供 LLM 选择"""
        if not self.tools:
            return "No tools available. Use 'finish' to provide your answer."

        lines = ["Available tools:"]
        for tool in self.tools:
            lines.append(f"- {tool.name}: {tool.description}")
        lines.append("- finish: Use this when you have the final answer.")

        return "\n".join(lines)

    def _parse_action(self, response: str) -> ReActAction | None:
        """从 LLM 响应中解析 JSON 动作"""
        try:
            # 尝试提取 JSON 块
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()

            data = json.loads(json_str)
            return ReActAction(**data)
        except (json.JSONDecodeError, ValueError):
            # 尝试修复常见问题
            try:
                fixed = "{" + json_str + "}"
                data = json.loads(fixed)
                return ReActAction(**data)
            except:
                return None

    def _find_tool(self, name: str) -> BaseTool | None:
        """根据名称查找工具"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def _execute_with_retry(
        self,
        tool: BaseTool,
        params: Dict[str, Any],
    ) -> str:
        """执行工具调用，带重试机制"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = await tool.ainvoke(params)
                return str(result)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    # 指数退避
                    await asyncio.sleep(0.5 * (attempt + 1))

        return f"Error after {self.max_retries} retries: {last_error}"

    async def run(self, message: str) -> str:
        """运行 ReAct Agent"""
        initial_state = AgentState(
            question=message,
            current_obs="",
            steps_taken=0,
            actions_history=[],
        )

        result = await self._graph.ainvoke(initial_state)

        # 返回最终答案或错误信息
        final_state = AgentState(**result)

        if final_state.final_answer:
            return final_state.final_answer
        elif final_state.error:
            return f"Agent error: {final_state.error}"
        else:
            return "Agent completed without a clear answer."

    def get_graph(self):
        """获取编译后的图（用于调试/可视化）"""
        return self._graph
