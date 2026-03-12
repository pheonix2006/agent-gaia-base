# ReAct Agent 设计文档

> **设计日期:** 2026-03-11
> **状态:** 已确认，待实现

---

## 1. 需求概述

### 1.1 使用场景
通用工具调用 Agent - 支持注册多种工具，LLM 自动选择和调用。

### 1.2 核心特性
| 特性 | 决策 |
|------|------|
| **终止条件** | 自动终止 + 最大步数兜底（默认 20 步） |
| **状态管理** | 单轮对话（当前），后续可扩展多轮 |
| **错误处理** | 工具失败时自动重试 N 次（默认 3 次） |
| **输出格式** | 结构化 JSON（action + params + memory） |
| **Prompt 模板** | 可自定义，独立 prompts/ 目录 |
| **Memory** | 独立模块，完整实现（含 LLM 压缩） |

---

## 2. 目录结构

```
src/ai_agent/
├── agents/           # 现有
│   ├── base.py
│   ├── simple/
│   └── react/        # 【新增】ReAct Agent
│       ├── __init__.py
│       └── graph.py
├── prompts/          # 【新增】Prompt 模板层
│   ├── __init__.py
│   ├── base.py       # Prompt 基类
│   └── react.py      # ReAct Prompt
├── memory/           # 【新增】Memory 模块
│   ├── __init__.py
│   └── base.py       # Memory 类（含压缩）
├── tools/            # 现有
├── llm/              # 现有
├── api/              # 现有
└── trace/            # 现有
```

---

## 3. Memory 模块设计

### 3.1 文件位置
`src/ai_agent/memory/base.py`

### 3.2 核心类

```python
class MemoryRecord(BaseModel):
    """单条记忆记录"""
    observation: Dict[str, Any]
    action: Dict[str, Any]
    thinking: Optional[str] = None
    reward: Optional[float] = None
    raw_response: Optional[str] = None


class BaseMemory(ABC):
    """Memory 基类"""

    @abstractmethod
    async def add(self, record: MemoryRecord) -> None: ...

    @abstractmethod
    def as_text(self) -> str: ...

    @abstractmethod
    def clear(self) -> None: ...


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
        keep_recent: int = 3
    ): ...
```

### 3.3 核心特性
- `add()` / `add_raw()`: 两种添加方式
- `as_text()`: 生成 Prompt 注入文本，最近记录在前
- `_compress()`: 达到 `max_memory` 时自动触发压缩
- `_summarize_records()`: 使用 LLM 提取关键信息

---

## 4. Prompt 模块设计

### 4.1 文件位置
- `src/ai_agent/prompts/base.py` - 基类
- `src/ai_agent/prompts/react.py` - ReAct 专用

### 4.2 ReAct Prompt 模板

```
==== Your Task ====
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
{obs}
```

### 4.3 使用方式

```python
prompt = ReActPrompt().with_task("Solve the math problem")
formatted = prompt.format(
    original_question="What is 2+2?",
    action_space="tools: add, subtract, multiply",
    memory="None",
    obs="No observation yet"
)
```

---

## 5. ReAct Agent 设计

### 5.1 文件位置
`src/ai_agent/agents/react/graph.py`

### 5.2 状态模型

```python
class ReActAction(BaseModel):
    """LLM 返回的结构化动作"""
    action: str          # 工具名称或 'finish'
    params: Dict[str, Any]
    memory: str          # 本轮观察/思考


class AgentState(BaseModel):
    """ReAct Agent 状态"""
    question: str
    current_obs: str = ""
    steps_taken: int = 0
    actions_history: List[ReActAction] = []
    final_answer: Optional[str] = None
    error: Optional[str] = None
```

### 5.3 图结构

```
START → think → [should_finish?] → act → observe → think → ...
                     ↓
                   END (finish 或达到上限)
```

### 5.4 核心节点

| 节点 | 职责 |
|------|------|
| `_think_node` | 构建 Prompt → 调用 LLM → 解析 JSON → 判断是否 finish |
| `_act_node` | 查找工具 → 执行（带重试）→ 返回观察 |
| `_observe_node` | 后处理（预留扩展点）|

### 5.5 辅助方法

| 方法 | 职责 |
|------|------|
| `_build_action_space` | 生成工具列表描述 |
| `_parse_action` | 从 LLM 响应提取 JSON，支持容错 |
| `_find_tool` | 按名称查找注册的工具 |
| `_execute_with_retry` | 执行工具，失败时指数退避重试 |

### 5.6 配置参数

```python
class ReActAgent(BaseAgent):
    MAX_STEPS = 20      # 最大执行步数
    MAX_RETRIES = 3     # 工具调用最大重试次数

    def __init__(
        self,
        llm,
        tools: List[BaseTool] | None = None,
        prompt: ReActPrompt | None = None,
        max_steps: int = MAX_STEPS,
        max_retries: int = MAX_RETRIES,
    ): ...
```

---

## 6. 使用示例

```python
from ai_agent.llm.client import create_llm_client
from ai_agent.agents.react import ReActAgent
from ai_agent.tools.registry import ToolRegistry

# 创建 LLM
llm = create_llm_client()

# 获取注册的工具
tools = ToolRegistry.get_langchain_tools()

# 创建 Agent
agent = ReActAgent(llm, tools=tools, max_steps=15)

# 运行
answer = await agent.run("What is the weather in Beijing?")
print(answer)
```

---

## 7. 实现文件清单

| 文件 | 说明 |
|------|------|
| `src/ai_agent/memory/__init__.py` | Memory 模块入口 |
| `src/ai_agent/memory/base.py` | Memory 基类 + CompressedMemory |
| `src/ai_agent/prompts/__init__.py` | Prompt 模块入口 |
| `src/ai_agent/prompts/base.py` | Prompt 基类 |
| `src/ai_agent/prompts/react.py` | ReAct Prompt 模板 |
| `src/ai_agent/agents/react/__init__.py` | ReAct Agent 入口 |
| `src/ai_agent/agents/react/graph.py` | ReAct Agent 核心实现 |
| `tests/unit/memory/test_base.py` | Memory 单元测试 |
| `tests/unit/prompts/test_react.py` | Prompt 单元测试 |
| `tests/unit/agents/test_react_agent.py` | ReAct Agent 单元测试 |

---

## 8. 设计原则遵循

| 原则 | 应用 |
|------|------|
| **KISS** | 状态机结构简单，三个节点循环 |
| **YAGNI** | 当前单轮对话，Memory 压缩预留但可用 |
| **DRY** | Prompt 模板、Memory 模块可复用 |
| **SRP** | Memory/Prompt/Agent 各司其职 |
| **OCP** | BaseMemory/BasePrompt 便于扩展 |
| **DIP** | Agent 依赖抽象（BaseTool），非具体实现 |
