"""ReAct Agent 实现"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START, END
from langgraph.pregel import Pregel
from langsmith import traceable
from pydantic import BaseModel, ConfigDict, Field

from ..base import BaseAgent
from ...prompts import ReActPrompt
from ...skills import SkillCatalog
from ...trace import TraceRecorder, TraceSpanCtx
from ...types import AnyDict
from .events import AgentEvent, AgentEventType

if TYPE_CHECKING:
    from ...memory import CompressedMemory
    from ...tools.filesystem.permissions import PermissionManager

logger = logging.getLogger(__name__)

# JSON Schema definition for finish action
FINISH_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "result": {
            "type": "string",
            "description": "The final answer or result to report",
        },
        "status": {
            "type": "string",
            "enum": ["done", "partial", "blocked"],
            "description": "Execution status: done=completed successfully, partial=incomplete progress, blocked=cannot proceed",
        },
        "summary": {
            "type": "string",
            "description": "Brief summary of key findings and observations",
        },
    },
    "required": ["result", "status"],
}

FINISH_ACTION_DESCRIPTION: str = "Report your final answer when the task is complete or cannot proceed."


class ReActAction(BaseModel):
    """LLM 返回的结构化动作"""

    action: str = Field(description="工具名称或 'finish'")
    params: dict[str, Any] = Field(default_factory=dict, description="工具参数")
    memory: str = Field(default="", description="本轮观察/思考")


class AgentState(BaseModel):
    """ReAct Agent 状态"""

    question: str = Field(description="用户原始问题")
    current_obs: str = Field(default="", description="当前观察")
    steps_taken: int = Field(default=0, description="已执行步数")
    actions_history: list[ReActAction] = Field(
        default_factory=list, description="动作历史"
    )
    final_answer: str | None = Field(default=None, description="最终答案")
    error: str | None = Field(default=None, description="错误信息")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ReActAgent(BaseAgent):
    """
    ReAct Agent 实现
    - 结构化 JSON 输出（action + params + memory）
    - 自动终止 + 最大步数兜底
    - 工具调用重试机制
    - 流式事件输出（stream 方法）
    - Skills 渐进式披露支持
    """

    MAX_STEPS = 20
    MAX_RETRIES = 3
    _memory: "CompressedMemory | None"

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool] | None = None,
        prompt: ReActPrompt | None = None,
        max_steps: int = MAX_STEPS,
        max_retries: int = MAX_RETRIES,
        memory: "CompressedMemory | None" = None,
        create_memory: bool = False,
        skill_catalog: SkillCatalog | None = None,
        permission_manager: "PermissionManager | None" = None,
    ):
        super().__init__(llm, tools)
        self.prompt = prompt or ReActPrompt()
        self.max_steps = max_steps
        self.max_retries = max_retries
        self._skill_catalog = skill_catalog
        self.permission_manager = permission_manager

        # Memory 集成
        if memory is not None:
            self._memory = memory
        elif create_memory:
            from ...memory import CompressedMemory
            self._memory = CompressedMemory(llm=llm, max_memory=10, keep_recent=3)
        else:
            self._memory = None

        self._graph = self._build_graph()

    def update_tools(self, new_tools: list[BaseTool]) -> None:
        """更新工具列表（支持运行时热重载）。

        Args:
            new_tools: 新的 LangChain 工具列表
        """
        self.tools = new_tools
        logger.info(f"工具列表已更新: {len(new_tools)} 个工具")

    def _build_graph(self) -> Pregel:
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

    async def _think_node(self, state: AgentState) -> AnyDict:
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
        content = str(response.content)
        action = self._parse_action(content)

        if action is None:
            return {"error": "Failed to parse LLM response as JSON"}

        # 更新状态
        updates: AnyDict = {
            "actions_history": state.actions_history + [action],
        }

        # 如果是 finish，设置最终答案（支持新旧两种格式）
        if action.action == "finish":
            # 优先使用 result，兼容 answer
            final_answer = action.params.get("result") or action.params.get("answer", action.memory)
            # 记录调试信息
            if "result" in action.params:
                result_value = action.params["result"]
                logger.info(
                    f"[ReActAgent] finish action的result长度={len(result_value) if isinstance(result_value, str) else 'N/A'}, "
                    f"result前100字符: {str(result_value)[:100] if result_value else 'N/A'}"
                )
            updates["final_answer"] = final_answer

        return updates

    async def _act_node(self, state: AgentState) -> AnyDict:
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

    async def _observe_node(self, state: AgentState) -> AnyDict:
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
        """构建工具描述供 LLM 选择

        当使用 Skills 模式时，采用轻量级描述，模型需要使用 Read 工具读取 SKILL.md 获取详细参数说明。
        当不使用 Skills 时，保留完整的 JSON Schema（向后兼容）。
        """
        import json

        lines = ["Available actions:\n"]

        # 判断是否使用 Skills 轻量模式
        use_skills_mode = self._skill_catalog is not None and len(self._skill_catalog.skills) > 0

        if use_skills_mode and self._skill_catalog is not None:
            # Skills 轻量模式：只显示 name + description
            # 模型需要使用 Read 工具读取 SKILL.md 获取详细参数说明
            lines.append("Each skill has a SKILL.md file with parameter details.")
            lines.append("Workflow: Read SKILL.md ONCE -> Extract parameters -> Call tool immediately.")
            lines.append("DO NOT read SKILL.md again after calling the tool.\n")

            for skill in self._skill_catalog.skills:
                # 将 skill-name 转换为 tool_name 格式（连字符转下划线）
                tool_name = skill.name.replace("-", "_")
                lines.append(f"### {tool_name}")
                lines.append(f"Description: {skill.description}")
                lines.append(f"Instructions: Use 'read' tool with path: {skill.location}")
                lines.append("")  # Skill 之间空行
        else:
            # 传统模式：显示完整 JSON Schema（向后兼容）
            for tool in self.tools:
                lines.append(f"### {tool.name}")
                lines.append(f"Description: {tool.description}")

                # 获取参数 schema
                try:
                    schema = tool.get_input_jsonschema()
                    if schema:
                        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
                        lines.append(f"Parameters: {schema_json}")
                    else:
                        lines.append("Parameters: {}")
                except Exception:
                    lines.append("Parameters: {}")

                lines.append("")  # 工具之间空行

        # 添加 finish action（始终显示完整 schema，因为没有对应的 Skill）
        lines.append("### finish")
        lines.append(f"Description: {FINISH_ACTION_DESCRIPTION}")
        finish_schema_json = json.dumps(FINISH_ACTION_SCHEMA, indent=2, ensure_ascii=False)
        lines.append(f"Parameters: {finish_schema_json}")

        return "\n".join(lines)

    def _parse_action(self, response: str) -> ReActAction | None:
        """从 LLM 响应中解析 JSON 动作

        支持多种 LLM 输出格式，包括：
        - 标准 JSON 块 (```json ... ```)
        - 纯 JSON 字符串
        - 包含未转义控制字符的 JSON（部分国产模型的问题）
        """
        try:
            # 尝试提取 JSON 块
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()

            # 尝试标准解析
            try:
                data = json.loads(json_str)
                return ReActAction(**data)
            except json.JSONDecodeError:
                pass

            # 尝试修复：清理控制字符后重试
            # 某些 LLM（如 GLM）可能在字符串中输出实际换行符而非 \n
            cleaned = self._repair_json_string(json_str)
            try:
                data = json.loads(cleaned)
                return ReActAction(**data)
            except json.JSONDecodeError:
                pass

            # 尝试修复：添加外层大括号（如果响应是部分 JSON）
            try:
                fixed = "{" + json_str + "}"
                data = json.loads(fixed)
                return ReActAction(**data)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

            # 最终尝试：使用 regex 提取关键字段（使用修复后的字符串）
            return self._extract_action_with_regex(cleaned)

        except Exception as e:
            logger.debug(f"[ReActAgent] JSON 解析完全失败: {e}")
            return None

    def _repair_json_string(self, json_str: str) -> str:
        """修复 JSON 字符串中的常见问题

        主要处理某些 LLM 在字符串值中直接输出控制字符的问题。
        以及其他常见的 JSON 格式问题。
        """
        import re

        # 方法：使用状态机逐字符处理，修复字符串内的控制字符
        result = []
        in_string = False
        i = 0

        while i < len(json_str):
            char = json_str[i]

            if char == '\\' and in_string and i + 1 < len(json_str):
                # 遇到转义符，检查下一个字符
                next_char = json_str[i + 1]
                # 如果是合法的转义序列，直接复制
                if next_char in '"\\bfnrt/':
                    result.append(char)
                    result.append(next_char)
                    i += 2
                    continue
                elif next_char == 'u' and i + 5 < len(json_str):
                    # Unicode 转义
                    unicode_chars = json_str[i+2:i+6]
                    if all(c in '0123456789abcdefABCDEF' for c in unicode_chars):
                        result.append(char)
                        result.append(next_char)
                        result.append(unicode_chars)
                        i += 6
                        continue
                # 非法转义序列，保留反斜杠
                result.append(char)
                i += 1
                continue

            if char == '"':
                in_string = not in_string
                result.append(char)
                i += 1
                continue

            # 在字符串内部，转义控制字符
            if in_string and char in '\n\r\t':
                # 实际的控制字符需要转义
                escape_map = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}
                result.append(escape_map[char])
                i += 1
                continue

            # 处理其他控制字符（仅在字符串内）
            if in_string and ord(char) < 32 and char not in '\n\r\t':
                # 其他控制字符转为 Unicode 转义
                result.append(f'\\u{ord(char):04x}')
                i += 1
                continue

            result.append(char)
            i += 1

        repaired = ''.join(result)
        
        # 额外的修复步骤
        
        # 1. 移除多余的尾部逗号（在 } 或 ] 之前的逗号）
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)
        
        # 2. 如果字符串未闭合，尝试闭合
        # 计算引号数量（非转义的）
        quote_count = 0
        in_str = False
        escape = False
        for c in repaired:
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_str = not in_str
                quote_count += 1
        
        # 如果引号数量为奇数，添加闭合引号
        if quote_count % 2 == 1:
            repaired += '"'
        
        # 3. 如果括号不匹配，尝试添加缺失的括号
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')
        
        if open_braces > 0:
            repaired += '}' * open_braces
        if open_brackets > 0:
            repaired += ']' * open_brackets
        
        return repaired

    def _extract_action_with_regex(self, text: str) -> ReActAction | None:
        """使用正则表达式从文本中提取 action 信息（最后的兜底方案）
        
        支持提取：
        - action: 字符串
        - params: 完整的对象（包括嵌套结构）
        - memory: 字符串
        """
        try:
            # 提取 action 字段
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', text)
            if not action_match:
                return None

            action_name = action_match.group(1)
            
            # 提取 params 对象
            params: dict[str, Any] = {}
            
            # 尝试匹配完整的 params 对象
            # 策略：找到 "params" 字段后，使用括号匹配提取完整对象
            params_match = re.search(r'"params"\s*:\s*\{', text)
            if params_match:
                # 找到 params 开始位置
                start_idx = params_match.start()
                brace_start = params_match.end() - 1  # 第一个 { 的位置
                
                # 使用栈匹配找到对应的 }
                brace_count = 0
                i = brace_start
                in_string = False
                escape_next = False
                
                while i < len(text):
                    char = text[i]
                    
                    if escape_next:
                        escape_next = False
                        i += 1
                        continue
                    
                    if char == '\\' and in_string:
                        escape_next = True
                        i += 1
                        continue
                    
                    if char == '"':
                        in_string = not in_string
                        i += 1
                        continue
                    
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                # 找到匹配的闭合括号
                                params_json = text[brace_start:i+1]
                                try:
                                    params = json.loads(params_json)
                                    break
                                except json.JSONDecodeError:
                                    # 如果解析失败，尝试修复
                                    repaired = self._repair_json_string(params_json)
                                    try:
                                        params = json.loads(repaired)
                                        break
                                    except json.JSONDecodeError:
                                        logger.debug(f"[ReActAgent] 无法解析 params: {params_json[:100]}")
                                        break
                    i += 1
            
            # 对于 finish action，尝试提取 result（向后兼容）
            if action_name == "finish" and not params:
                result_str = self._extract_json_string_value(text, "result")
                if result_str is not None:
                    params["result"] = result_str

            # 尝试提取 memory
            memory = self._extract_json_string_value(text, "memory") or ""

            return ReActAction(action=action_name, params=params, memory=memory)
        except Exception as e:
            logger.debug(f"[ReActAgent] regex 提取失败: {e}")
            return None

    def _extract_json_string_value(self, text: str, field_name: str) -> str | None:
        """从JSON文本中提取指定字段的字符串值

        使用括号匹配而非正则表达式，正确处理字符串内的转义引号和嵌套结构。

        Args:
            text: JSON文本
            field_name: 字段名称（如 "result", "memory"）

        Returns:
            提取的字符串值（已反转义），如果未找到则返回 None
        """
        import json

        # 查找字段位置: "field_name":
        field_pattern = f'"{field_name}"\\s*:\\s*"'
        field_match = re.search(field_pattern, text)
        if not field_match:
            return None

        # 字符串值的起始位置（跳过开头的引号）
        value_start = field_match.end() - 1
        quote_pos = field_match.end() - 1

        # 使用状态机提取完整字符串
        i = quote_pos + 1  # 跳过开头的引号
        result_chars = []
        escape_next = False

        while i < len(text):
            char = text[i]

            if escape_next:
                # 处理转义字符
                escape_map = {
                    '"': '"',
                    '\\': '\\',
                    '/': '/',
                    'b': '\b',
                    'f': '\f',
                    'n': '\n',
                    'r': '\r',
                    't': '\t',
                }
                result_chars.append(escape_map.get(char, char))
                escape_next = False
                i += 1
                continue

            if char == '\\':
                escape_next = True
                i += 1
                continue

            if char == '"':
                # 找到字符串结束
                return ''.join(result_chars)

            result_chars.append(char)
            i += 1

        # 未找到闭合引号
        return None

    def _find_tool(self, name: str) -> BaseTool | None:
        """根据名称查找工具"""
        for tool in self.tools:
            if tool.name == name:
                return tool  # type: ignore[no-any-return]
        return None

    async def _execute_with_retry(
        self,
        tool: BaseTool,
        params: AnyDict,
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
        recorder = TraceRecorder("agent_run")
        recorder.start_span("run")
        try:
            result = await self._run_impl(message)
            recorder.finish_span(input={"message": message}, output=result)
            return result
        except BaseException:
            recorder.finish_span(input={"message": message}, error=_format_trace_exc())
            raise
        finally:
            recorder.finish_run()

    async def _run_impl(self, message: str) -> str:
        """LangGraph ainvoke 实现（被 run() 的 trace wrapper 包裹）"""
        initial_state = AgentState(
            question=message,
            current_obs="",
            steps_taken=0,
            actions_history=[],
        )

        result = await self._graph.ainvoke(initial_state)  # type: ignore[arg-type]

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

        当存在活跃的 TraceRecorder 时，会自动记录各阶段的 trace span。

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

            # 获取 memory 文本
            memory_text = self._memory.as_text() if self._memory else "None"

            # 格式化 Prompt
            formatted_prompt = self.prompt.format(
                original_question=state.question,
                action_space=action_space,
                memory=memory_text,
                obs=state.current_obs or "No observation yet.",
            )

            # 调用 LLM（带 trace span）
            try:
                async with TraceSpanCtx(
                    "llm_call",
                    input={"prompt": formatted_prompt[:500]},
                    metadata={"step": step},
                ) as span:
                    response = await self.llm.ainvoke([HumanMessage(formatted_prompt)])
                    raw_output = response.content
                    span.set_output(str(raw_output)[:1000])
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
            action = self._parse_action(str(raw_output))

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

            # Yield THINK 事件（带 trace span）
            logger.info(f"[ReActAgent] step={step} THINK 完成，action={action.action}, memory={action.memory[:50] if action.memory else 'N/A'}...")
            async with TraceSpanCtx(
                "think",
                input={"action": action.action, "memory": action.memory[:200] if action.memory else ""},
                metadata={"step": step},
            ) as span:
                span.set_output({"action": action.action, "params": action.params})
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
                # 优先使用 result，兼容 answer
                state.final_answer = action.params.get("result") or action.params.get("answer", action.memory)
                logger.info(f"[ReActAgent] step={step} 任务完成，最终答案: {state.final_answer[:50] if state.final_answer else 'N/A'}...")
                # 记录最终答案的长度（用于调试）
                logger.info(
                    f"[ReActAgent] step={step} 生成FINISH事件, "
                    f"answer长度={len(state.final_answer) if state.final_answer else 0}, "
                    f"answer前100字符: {state.final_answer[:100] if state.final_answer else 'N/A'}"
                )
                yield AgentEvent(
                    event=AgentEventType.FINISH,
                    data={"answer": state.final_answer},
                    step=step,
                )
                break

            # ========== ACT 阶段 ==========
            logger.info(f"[ReActAgent] step={step} 开始 ACT 阶段，工具: {action.action}")

            # Yield ACT 事件（执行前，带 trace span）
            async with TraceSpanCtx(
                f"act:{action.action}",
                input={"tool_name": action.action, "params": action.params},
                metadata={"step": step},
            ) as span:
                span.set_output({"tool_name": action.action, "params": action.params})
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

                # Yield OBSERVE 事件（错误，带 trace span）
                async with TraceSpanCtx(
                    "observe",
                    input={"tool_name": action.action, "error": error_msg},
                    metadata={"step": step, "success": False},
                ) as span:
                    span.set_output(error_msg)
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

            # 执行工具（带 trace span）
            try:
                async with TraceSpanCtx(
                    "tool_execution",
                    input={"tool_name": action.action, "params": action.params},
                    metadata={"step": step},
                ) as span:
                    result = await self._execute_with_retry(tool, action.params)
                    span.set_output(result[:1000] if result else result)
                state.current_obs = result
                state.steps_taken += 1
                logger.info(f"[ReActAgent] step={step} 工具执行成功: {action.action}, 结果: {result[:100] if result else 'N/A'}...")

                # Yield OBSERVE 事件（带 trace span）
                async with TraceSpanCtx(
                    "observe",
                    input={"tool_name": action.action, "result_preview": result[:200] if result else ""},
                    metadata={"step": step, "success": True},
                ) as span:
                    span.set_output(result[:1000] if result else result)
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

                # 记录到 Memory
                if self._memory:
                    from ...memory import MemoryRecord
                    await self._memory.add(MemoryRecord(
                        observation={"result": result},
                        action={"name": action.action, "params": action.params},
                        thinking=action.memory,
                    ))
            except Exception as e:
                error_msg = f"Error executing tool '{action.action}': {e}"
                state.current_obs = error_msg
                state.steps_taken += 1
                logger.error(f"[ReActAgent] step={step} 工具执行失败: {action.action}, 错误: {e}")

                # Yield OBSERVE 事件（错误，带 trace span）
                async with TraceSpanCtx(
                    "observe",
                    input={"tool_name": action.action, "error": error_msg},
                    metadata={"step": step, "success": False},
                ) as span:
                    span.set_output(error_msg)
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

    def get_graph(self) -> Pregel:
        """获取编译后的图（用于调试/可视化）"""
        return self._graph


def _format_trace_exc() -> str:
    """Return a short string representation of the currently handled exception."""
    import traceback

    return traceback.format_exc()
