# ReAct Agent 流式集成设计文档

## 概述

将 ReActAgent 集成到 API，支持流式响应（SSE），让用户能看到完整的 agent 执行过程：思考 → 工具调用 → 结果 → 最终答案。

## 设计决策

### 1. 流式输出粒度
- **选择**：步骤级流式（每完成一个 think/act/observe 推送事件）
- **前端交互**：折叠卡片式，默认简略显示，可展开查看详情

### 2. 详情展示
- **选择**：参数 + 结果摘要（信息量适中）

### 3. 事件类型

| 事件类型 | 简略显示 | 展开详情内容 |
|---------|---------|------------|
| `think` | 🤔 思考中... | LLM reasoning content、原始 JSON 输出 |
| `act` | 🔧 调用 xxx... | 工具名、调用参数 |
| `observe` | 📥 获取结果 | 工具名、结果摘要 |
| `error` | ❌ 出错了 | 错误信息、详情 |
| `finish` | ✅ 完成 | 最终答案 |

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (chat.html)                      │
│  EventSource 连接 /api/v1/chat/stream                       │
│  接收 SSE 事件，渲染折叠卡片                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓ SSE
┌─────────────────────────────────────────────────────────────┐
│                    API (routes/chat.py)                      │
│  /chat/stream - SSE 流式端点                                 │
│  调用 ReActAgent.stream() 并 yield 事件                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   ReActAgent (agents/react/graph.py)         │
│  新增 stream() 方法：                                        │
│  - 每个 think/act/observe 节点 yield 事件                    │
│  - logging.info 记录日志                                     │
│  - LangSmith 自动追踪 (环境变量已配置)                        │
└─────────────────────────────────────────────────────────────┘
```

## SSE 事件数据结构

```json
{
    "event": "think" | "act" | "observe" | "error" | "finish",
    "data": {
        "reasoning": "用户想知道天气，我需要先搜索...",
        "raw_output": "```json\n{\"action\": \"google_search\", ...}\n```",
        "tool_name": "google_search",
        "params": {"query": "今天北京天气"},
        "result_summary": "找到 3 个结果：1. 北京天气预报...",
        "message": "错误信息",
        "details": "详细错误",
        "answer": "最终答案"
    },
    "timestamp": "2026-03-12T10:30:00Z",
    "step": 1
}
```

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|-----|---------|------|
| `src/ai_agent/agents/react/events.py` | **新增** | 定义 `AgentEvent` Pydantic 模型 |
| `src/ai_agent/agents/react/graph.py` | **修改** | 新增 `stream()` 方法，添加 logging |
| `src/ai_agent/api/main.py` | **修改** | 初始化 LangSmith + ReActAgent + Tools |
| `src/ai_agent/api/routes/chat.py` | **修改** | 新增 `/chat/stream` SSE 端点 |
| `src/ai_agent/api/schemas/events.py` | **新增** | SSE 事件的响应模型 |
| `src/ai_agent/api/static/chat.html` | **修改** | 支持 EventSource + 折叠卡片 UI |
| `tests/integration/test_react_agent_live.py` | **新增** | 真实 API 集成测试 |
| `tests/e2e/test_stream_endpoint.py` | **新增** | SSE 端到端测试 |

## 测试策略

### 真实 API 测试场景

| 场景 | 涉及 API | 验证点 |
|-----|---------|-------|
| **简单问答** | LLM only | think → finish 流程 |
| **搜索问答** | LLM + Serper | think → act(google_search) → observe → finish |
| **网页分析** | LLM + Serper + Jina | 多步工具链调用 |
| **错误处理** | LLM + 无效工具参数 | error 事件、重试机制 |
| **流式输出** | 全栈 | SSE 事件格式、顺序正确 |

### 测试文件结构

```
tests/
├── integration/
│   ├── test_real_api.py          # 已有，需扩展
│   └── test_react_agent_live.py  # 新增：完整 ReAct 真实 API 测试
├── e2e/
│   └── test_stream_endpoint.py   # 新增：SSE 端点端到端测试
```

## 实现顺序

1. 定义事件模型 (`events.py`)
2. 修改 Agent 支持 stream + logging
3. 修改 API 集成 ReActAgent + Tools
4. 新增 SSE 端点 (`/chat/stream`)
5. 更新前端 UI (折叠卡片)
6. 编写真实 API 测试

## 关键原则

- **TDD**：每个任务先写测试，再写实现
- **真实 API 测试**：必须使用真实 LLM + 真实工具 API 进行验证
- **Logging + LangSmith**：每个关键操作都有日志和追踪
