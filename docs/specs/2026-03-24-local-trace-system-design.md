# Local Trace System Design

> 本地结构化追踪系统，用于 TDD 开发中记录 Agent/Tool/LLM 调用的完整执行轨迹

## 1. 背景与动机

现有追踪机制的不足：
- **LangSmith** — 云端观测，对本地 TDD 开发调试不友好，无法离线查看
- **标准 logging** — 散落的文本日志，无结构化聚合，无法回溯完整链路
- **session Trace** — 仅记录工具调用，不覆盖 LLM 调用和 JSON 解析等节点

目标：提供一个**装饰器驱动的本地追踪系统**，零侵入静默记录每次执行的完整轨迹，输出为可读性强的 JSON 文件。

## 2. 设计决策

| 维度 | 选择 | 理由 |
|------|------|------|
| 实现方案 | 轻量自定义 Tracer | KISS/YAGNI，不需要 OTel 的分布式能力 |
| 记录方式 | 装饰器 + 上下文管理器 | AOP 横切关注点，零侵入业务代码 |
| 输出格式 | 单个嵌套 JSON 文件 | 可读性好，信息完整 |
| 数据模型 | 扁平 spans + parent_id | JSON 序列化简单，查询方便 |
| 传播机制 | ContextVar | async 安全，零参数传递 |
| 任务粒度 | 层级模型 | 适配全链路 ReAct 和单个工具测试 |
| 数据大小 | 完整记录 | 不截断，保留完整调试信息 |
| LangSmith 关系 | 完全独立 | 避免复杂度，未来按需桥接 |
| 外部依赖 | 零新增 | 仅使用标准库 |

## 3. 核心数据模型

```python
# src/ai_agent/trace/types.py

@dataclass
class SpanData:
    """单个追踪节点"""
    name: str                    # "think", "act:web_search", "llm_call"
    span_id: str                 # 8位短ID
    parent_id: str | None        # 父节点ID，顶层为 None
    started_at: float            # unix timestamp
    finished_at: float | None    # None = 未完成（异常中断）
    status: str                  # "success" | "error"
    input: Any = None            # 序列化后的输入
    output: Any = None           # 序列化后的输出
    error: str | None = None     # 异常信息
    metadata: dict = field(default_factory=dict)

@dataclass
class TraceRun:
    """一次完整的运行记录"""
    run_id: str                  # "20260324_143022_a3f2"
    name: str                    # 运行名称
    started_at: float
    finished_at: float | None
    spans: list[SpanData]        # 扁平列表，通过 parent_id 构成树
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
```

**设计要点：**
- spans 用扁平列表 + parent_id 构成树，JSON 序列化简单
- input/output 用 Any，运行时做 JSON 序列化处理
- run_id 格式：`{YYYYMMDD}_{HHMMSS}_{random_4chars}`

## 4. 装饰器 API

```python
# --- 顶层装饰器：创建完整 run ---
@trace_run("react_agent")
async def run(self, query: str) -> str: ...

@trace_run("react_agent.stream")
async def stream(self, query: str) -> AsyncGenerator: ...

# --- 子节点装饰器：挂载到当前活跃 run ---
@trace_span("think")
def _think_node(self, state: AgentState) -> dict: ...

@trace_span("act")
def _act_node(self, state: AgentState) -> dict: ...

# --- 上下文管理器：代码块级追踪 ---
async with trace_span("llm_call") as span:
    span.set_tag("model", "gpt-4")
    result = await self.llm.chat(messages)

# --- pytest 集成 ---
@pytest.fixture
def trace_recorder():
    with trace_run(pytest.current_test_name) as recorder:
        yield recorder
    # fixture 结束时自动 flush 到 logs/traces/
```

**关键行为：**
- `@trace_run` — 创建新 run，结束时 flush JSON 文件
- `@trace_span` — 如果没有活跃 run，静默跳过（不报错）
- 异常自动捕获 — status 标记 "error"，记录 error 信息，然后 re-raise
- `ContextVar` 传播 — 不需要手动传参，任何深度嵌套都能自动找到所属 run

## 5. ContextVar 传播机制

```python
# src/ai_agent/trace/context.py

_active_run: ContextVar[TraceRun | None] = ContextVar("active_run", default=None)
_span_stack: ContextVar[list[str]] = ContextVar("span_stack", default_factory=list)
```

- `_active_run` — 当前活跃的 TraceRun
- `_span_stack` — 当前 span 嵌套栈，用于确定 parent_id
- asyncio 天然支持 ContextVar 隔离，并发安全

## 6. 文件存储

```
logs/traces/
├── 20260324/                          # 按日期分目录
│   ├── 143022_a3f2_react_agent.json
│   ├── 143055_b7c1_tool_search.json
│   └── ...
├── .gitignore
└── ...
```

- 按日期分目录避免单目录文件过多
- 文件名格式：`{HHMMSS}_{short_id}_{name}.json`
- `.traces/` 放项目根目录，gitignore 排除

## 7. pytest 断言 API

```python
# src/ai_agent/trace/assertions.py

def test_react_agent_calls_search_tool(trace_recorder):
    agent = ReActAgent(llm=mock_llm, tools=[search_tool])
    await agent.run("search python tutorial")

    assert trace_recorder.success()
    assert trace_recorder.has_span("think")
    assert trace_recorder.has_span("act:web_search").with_input(query="python tutorial")
    assert trace_recorder.span_count() >= 2
    assert trace_recorder.duration_ms() < 5000
```

**断言 API：**
- `trace_recorder.success()` — run 整体是否成功
- `trace_recorder.has_span(name)` — 是否存在指定 span，返回 SpanAssertion 对象
- `SpanAssertion.with_input(**kwargs)` — 断言 span 输入包含指定字段
- `SpanAssertion.with_output(**kwargs)` — 断言 span 输出包含指定字段
- `trace_recorder.span_count()` — span 总数
- `trace_recorder.duration_ms()` — run 总耗时
- 失败时输出有意义的上下文信息

## 8. 模块结构

```
src/ai_agent/trace/
├── __init__.py           # 公开 API: trace_run, trace_span, TraceRecorder
├── types.py              # SpanData, TraceRun 数据模型
├── context.py            # ContextVar 传播
├── recorder.py           # TraceRecorder: span 树构建 + JSON 序列化 + 文件写入
├── decorators.py         # @trace_run, @trace_span 装饰器实现
├── assertions.py         # pytest 断言 API
├── config.py             # 存储路径、启用开关
└── langsmith.py          # 现有 LangSmith 集成（保持不动）
```

**依赖关系：**
```
decorators.py  ──→  context.py  ──→  types.py
                     │
recorder.py    ──→  context.py  ──→  types.py
     │
assertions.py ──→  recorder.py
```

## 9. 接入现有代码

仅在关键方法上加装饰器，核心业务代码零修改：

```python
# src/ai_agent/agents/react/graph.py
@trace_run("react_agent")         # run 方法
@trace_run("react_agent.stream")  # stream 方法
@trace_span("think")              # _think_node
@trace_span("act")                # _act_node
@trace_span("observe")            # _observe_node
@trace_span("llm_call")           # LLM 调用处（可选，用上下文管理器）
@trace_span("parse_action")       # JSON 解析（可选）
```

预计 ~7 个装饰器注入点。

## 10. JSON 输出示例

```json
{
  "run_id": "20260324_143022_a3f2",
  "name": "react_agent",
  "status": "success",
  "started_at": 1742807422.123,
  "finished_at": 1742807425.456,
  "total_duration_ms": 3333,
  "tags": ["react", "agent"],
  "spans": [
    {
      "name": "think",
      "span_id": "b1c2d3e4",
      "parent_id": null,
      "started_at": 1742807422.123,
      "finished_at": 1742807424.423,
      "duration_ms": 2300,
      "status": "success",
      "input": {
        "question": "search python tutorial",
        "action_space": "..."
      },
      "output": {
        "action": "web_search",
        "params": {"query": "python tutorial"}
      },
      "metadata": {
        "step": 1,
        "model": "gpt-4"
      }
    },
    {
      "name": "act:web_search",
      "span_id": "e5f6a7b8",
      "parent_id": "b1c2d3e4",
      "started_at": 1742807424.423,
      "finished_at": 1742807425.223,
      "duration_ms": 800,
      "status": "success",
      "input": {"query": "python tutorial"},
      "output": {"results": "..."},
      "metadata": {
        "step": 1,
        "tool": "web_search"
      }
    }
  ]
}
```

## 11. 与现有系统的关系

| 现有模块 | 关系 |
|----------|------|
| `trace/langsmith.py` | 保持不动，完全独立。两套装饰器可共存 |
| `session/types.py` Trace | 保持不动。session 层记录和本地 trace 是不同职责 |
| 标准 `logging` | 保持不动。两者互补，logging 用于实时输出，trace 用于结构化回溯 |

## 12. 验收标准

### 12.1 单元测试

| 测试场景 | 验证内容 |
|----------|----------|
| SpanData 序列化 | input/output 含特殊字符、None、嵌套对象时 JSON 正确 |
| ContextVar 传播 | 嵌套 span 的 parent_id 正确关联 |
| 装饰器异常处理 | 函数抛异常时 span status="error"，异常正常 re-raise |
| 无活跃 run 时 | `@trace_span` 静默跳过，不报错 |
| 文件写入 | JSON 文件格式正确，目录自动创建 |
| 断言 API | `has_span`/`with_input`/`success` 各场景正确断言 |

### 12.2 集成测试（真实 API）

| 测试场景 | 验证内容 |
|----------|----------|
| 单次 LLM 调用 | `@trace_span("llm_call")` 记录完整的 prompt 和 response |
| 单个工具执行 | `@trace_span("act:web_search")` 记录输入参数和真实搜索结果 |
| 完整 ReAct 流程 | `@trace_run("react_agent")` 记录多轮 think/act/observe 全链路 |
| 异常中断 | 工具调用失败时，trace 记录错误信息和中断位置 |
| pytest fixture | 测试自动生成 trace JSON，断言 API 验证通过 |
| API 端到端 | `POST /api/v1/chat/stream` 调用后，本地生成 trace JSON 且结构正确 |

### 12.3 稳定性要求

- 真实 API 调用测试必须稳定通过（不依赖 mock）
- 不同颗粒度（单 LLM / 单工具 / 完整流程）均可独立追踪
- trace 系统不影响现有功能（装饰器可随时移除，系统正常工作）
- 并发场景下 ContextVar 隔离正确
