"""ReAct Agent 实现"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START, END
from langsmith import traceable
from pydantic import BaseModel, ConfigDict, Field

from ..base import BaseAgent
from ...prompts import ReActPrompt
from .events import AgentEvent, AgentEventType

logger = logging.getLogger(__name__)


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
    - 流式事件输出（stream 方法）
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
        memory: Optional["CompressedMemory"] = None,
        create_memory: bool = False,
    ):
        super().__init__(llm, tools)
        self.prompt = prompt or ReActPrompt()
        self.max_steps = max_steps
        self.max_retries = max_retries

        # Memory 集成
        if memory is not None:
            self._memory = memory
        elif create_memory:
            from ...memory import CompressedMemory
            self._memory = CompressedMemory(llm=llm, max_memory=10, keep_recent=3)
        else:
            self._memory = None

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
            memory=self._memory.as_text() if self._memory else "None",
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
        # 记录到 Memory（如果有）
        if self._memory and state.actions_history:
            from ...memory import MemoryRecord

            last_action = state.actions_history[-1]

            await self._memory.add(MemoryRecord(
                observation={"result": state.current_obs},
                action={
                    "name": last_action.action,
                    "params": last_action.params,
                },
                thinking=last_action.memory,
            ))

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
            except (json.JSONDecodeError, ValueError, TypeError):
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
        """运行 ReAct Agent

        Args:
            message: 用户输入消息

        Returns:
            最终答案字符串
        """
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

    @traceable(
        name="react_agent",
        run_type="chain",
        tags=["react", "agent"],
    )
    async def stream(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        """流式执行 ReAct Agent，yield 每个事件

        这是一个独立的流式执行方法，不依赖 LangGraph 的 ainvoke。
        它手动实现 think -> act -> observe 循环，在每个关键点 yield AgentEvent。

        Args:
            message: 用户输入消息

        Yields:
            AgentEvent: 表示执行过程中的各类事件
        """
        # 初始化状态
        state = AgentState(
            question=message,
            current_obs="",
            steps_taken=0,
            actions_history=[],
        )
        step = 0

        logger.info(f"[ReActAgent] 开始执行，问题: {message[:50]}...")

        while True:
            # 检查最大步数
            if state.steps_taken >= self.max_steps:
                logger.info(f"[ReActAgent] step={step} 达到最大步数 {self.max_steps}，结束执行")
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": state.final_answer or "达到最大步数限制"},
                    step=step,
                )
                break

            # ========== THINK 阶段 ==========
            logger.info(f"[ReActAgent] step={step} 开始 THINK 阶段")

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
            try:
                response = await self.llm.ainvoke([HumanMessage(formatted_prompt)])
                raw_output = response.content
            except Exception as e:
                logger.error(f"[ReActAgent] step={step} LLM 调用失败: {e}")
                yield AgentEvent(
                    event=AgentEventType.ERROR,
                    data={"message": "LLM 调用失败", "details": str(e)},
                    step=step,
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": f"Agent error: LLM 调用失败 - {e}"},
                    step=step + 1,
                )
                break

            # 解析 JSON 响应
            action = self._parse_action(raw_output)

            if action is None:
                logger.error(f"[ReActAgent] step={step} 无法解析 LLM 响应为 JSON")
                yield AgentEvent(
                    event=AgentEventType.ERROR,
                    data={
                        "message": "无法解析 LLM 响应",
                        "details": f"raw_output: {raw_output[:200]}..."
                    },
                    step=step,
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": "Agent error: 无法解析 LLM 响应"},
                    step=step + 1,
                )
                break

            # 更新状态
            state.actions_history = state.actions_history + [action]

            # Yield THINK 事件
            logger.info(f"[ReActAgent] step={step} THINK 完成，action={action.action}, memory={action.memory[:50] if action.memory else 'N/A'}...")
            yield AgentEvent(
                event=AgentEventType.THINK,
                data={
                    "reasoning": action.memory,
                    "raw_output": raw_output,
                    "action": action.action,
                },
                step=step,
            )
            step += 1

            # 检查是否应该结束
            if action.action == "finish":
                state.final_answer = action.params.get("answer", action.memory)
                logger.info(f"[ReActAgent] step={step} 任务完成，最终答案: {state.final_answer[:50] if state.final_answer else 'N/A'}...")
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": state.final_answer},
                    step=step,
                )
                break

            # ========== ACT 阶段 ==========
            logger.info(f"[ReActAgent] step={step} 开始 ACT 阶段，工具: {action.action}")

            # Yield ACT 事件（执行前）
            yield AgentEvent(
                event=AgentEventType.ACT,
                data={
                    "tool_name": action.action,
                    "params": action.params,
                },
                step=step,
            )
            step += 1

            # 查找工具
            tool = self._find_tool(action.action)
            if tool is None:
                error_msg = f"Error: Tool '{action.action}' not found."
                state.current_obs = error_msg
                state.steps_taken += 1
                logger.warning(f"[ReActAgent] step={step} 工具未找到: {action.action}")

                # Yield OBSERVE 事件（错误）
                yield AgentEvent(
                    event=AgentEventType.OBSERVE,
                    data={
                        "tool_name": action.action,
                        "result_summary": error_msg,
                        "success": False,
                    },
                    step=step,
                )
                step += 1
                continue

            # 执行工具
            try:
                result = await self._execute_with_retry(tool, action.params)
                state.current_obs = result
                state.steps_taken += 1
                logger.info(f"[ReActAgent] step={step} 工具执行成功: {action.action}, 结果: {result[:100] if result else 'N/A'}...")

                # Yield OBSERVE 事件
                yield AgentEvent(
                    event=AgentEventType.OBSERVE,
                    data={
                        "tool_name": action.action,
                        "result_summary": result[:2000] if len(result) > 2000 else result,
                        "result": result,  # 完整结果
                        "success": True,
                    },
                    step=step,
                )
            except Exception as e:
                error_msg = f"Error executing tool '{action.action}': {e}"
                state.current_obs = error_msg
                state.steps_taken += 1
                logger.error(f"[ReActAgent] step={step} 工具执行失败: {action.action}, 错误: {e}")

                # Yield OBSERVE 事件（错误）
                yield AgentEvent(
                    event=AgentEventType.OBSERVE,
                    data={
                        "tool_name": action.action,
                        "result_summary": error_msg,
                        "success": False,
                    },
                    step=step,
                )

            step += 1

            # 继续下一轮循环（observe 后回到 think）

    def get_graph(self):
        """获取编译后的图（用于调试/可视化）"""
        return self._graph
