# Action Space 格式重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构 `_build_action_space` 方法，使其生成 benchmark 格式的工具描述，并为 finish 方法添加完整的 JSON Schema 参数定义。

**Architecture:**
1. 定义 `FINISH_ACTION_SCHEMA` 常量，包含 result/status/memory 字段
2. 重构 `_build_action_space` 输出格式：`### Name\nDescription:\nParameters: {json}`
3. 更新所有 finish 处理逻辑，将 `answer` 字段映射为 `result`

**Tech Stack:** Python 3.12+, Pydantic 2.0+, asyncio

---

## 目标格式对比

### 当前格式
```
Available tools:
- calculator: Performs calculations
    - param1 (required): description
- finish: Use this when you have the final answer.
```

### 目标格式
```
Available actions:

### GoogleSearchTool
Description: Search the web using Serper API...
Parameters: {
  "type": "object",
  "properties": {
    "query": {"type": "string", "description": "Search query"},
    "k": {"type": "integer", "default": 5}
  },
  "required": ["query"]
}

### finish
Description: Report your final answer when the task is complete or cannot proceed.
Parameters: {
  "type": "object",
  "properties": {
    "result": {"type": "string", "description": "The final answer or result"},
    "status": {"type": "string", "enum": ["done", "partial", "blocked"]},
    "memory": {"type": "string", "description": "Brief summary of key findings"}
  },
  "required": ["result", "status"]
}
```

---

## Task 1: 定义 FINISH_ACTION_SCHEMA 常量

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py` (在文件顶部添加常量)

**Step 1: 添加常量定义**

在 `graph.py` 文件中，`logger` 定义之后、`ReActAction` 类之前添加：

```python
# finish action 的 JSON Schema 定义
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
        "memory": {
            "type": "string",
            "description": "Brief summary of key findings and observations",
        },
    },
    "required": ["result", "status"],
}

FINISH_ACTION_DESCRIPTION = "Report your final answer when the task is complete or cannot proceed."
```

**Step 2: 添加 Any 类型导入（如果需要）**

确保文件顶部有 `from typing import Any` 的导入。

**Step 3: 验证语法**

Run: `python -c "from ai_agent.agents.react.graph import FINISH_ACTION_SCHEMA; print(FINISH_ACTION_SCHEMA)"`
Expected: 打印 schema 字典

---

## Task 2: 重构 _build_action_space 方法

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py:193-227`

**Step 1: 编写测试（先写失败测试）**

在 `tests/unit/agents/test_react_agent.py` 中更新 `test_build_action_space` 测试：

```python
def test_build_action_space():
    """测试构建工具描述 - 新格式"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "calculator"
    mock_tool.description = "Performs calculations"
    mock_tool.parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression"}
        },
        "required": ["expression"]
    }
    mock_tool.get_input_jsonschema.return_value = mock_tool.parameters

    agent = ReActAgent(mock_llm, tools=[mock_tool])
    action_space = agent._build_action_space()

    # 验证新格式
    assert "Available actions:" in action_space
    assert "### calculator" in action_space
    assert "Description: Performs calculations" in action_space
    assert "Parameters:" in action_space
    assert '"expression"' in action_space

    # 验证 finish 部分
    assert "### finish" in action_space
    assert '"result"' in action_space
    assert '"status"' in action_space
    assert '"done"' in action_space
    assert '"partial"' in action_space
    assert '"blocked"' in action_space
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_react_agent.py::test_build_action_space -v`
Expected: FAIL (旧格式不包含新格式的元素)

**Step 3: 重写 _build_action_space 方法**

将 `graph.py:193-227` 的 `_build_action_space` 方法替换为：

```python
def _build_action_space(self) -> str:
    """构建工具描述供 LLM 选择（benchmark 格式，包含完整 JSON Schema）"""
    import json

    lines = ["Available actions:\n"]

    # 遍历所有工具
    for tool in self.tools:
        lines.append(f"### {tool.name}")
        lines.append(f"Description: {tool.description}")

        # 获取参数 schema
        try:
            schema = tool.get_input_jsonschema()
            if schema:
                # 格式化 JSON Schema 为缩进格式
                schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
                lines.append(f"Parameters: {schema_json}")
            else:
                lines.append("Parameters: {}")
        except Exception:
            lines.append("Parameters: {}")

        lines.append("")  # 工具之间空行

    # 添加 finish action
    lines.append("### finish")
    lines.append(f"Description: {FINISH_ACTION_DESCRIPTION}")
    finish_schema_json = json.dumps(FINISH_ACTION_SCHEMA, indent=2, ensure_ascii=False)
    lines.append(f"Parameters: {finish_schema_json}")

    return "\n".join(lines)
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_react_agent.py::test_build_action_space -v`
Expected: PASS

**Step 5: 更新空工具测试**

更新 `test_build_action_space_empty` 测试：

```python
def test_build_action_space_empty():
    """测试无工具时的描述 - 新格式"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm, tools=[])

    action_space = agent._build_action_space()

    # 即使无工具，也应该包含 finish
    assert "Available actions:" in action_space
    assert "### finish" in action_space
    assert '"result"' in action_space
```

**Step 6: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_react_agent.py::test_build_action_space_empty -v`
Expected: PASS

---

## Task 3: 更新 finish 处理逻辑 - _think_node 路径

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py:142` (graph 模式)
- Modify: `src/ai_agent/agents/react/graph.py:417-418` (stream 模式)

**Step 1: 编写测试**

```python
def test_finish_action_with_new_params():
    """测试 finish 使用新参数格式"""
    from ai_agent.agents.react import ReActAgent, AgentState, ReActAction

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm, tools=[])

    # 创建 action 使用新格式参数
    action = ReActAction(
        action="finish",
        params={"result": "The answer is 42", "status": "done", "memory": "Found the answer"},
        memory="Found the answer"
    )

    state = AgentState(question="What is the answer?")
    updates = agent._update_state_node(state, action)

    # 验证 final_answer 从 result 字段获取
    assert updates["final_answer"] == "The answer is 42"
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_react_agent.py::test_finish_action_with_new_params -v`
Expected: FAIL (旧逻辑使用 "answer" 字段)

**Step 3: 更新 _update_state_node 方法**

修改 `graph.py:142-143`：

```python
# 如果是 finish，设置最终答案
if action.action == "finish":
    # 支持新旧两种格式：优先使用 result，兼容 answer
    final_answer = action.params.get("result") or action.params.get("answer", action.memory)
    updates["final_answer"] = final_answer
```

**Step 4: 更新 stream 方法中的 finish 处理**

修改 `graph.py:417-418`：

```python
if action.action == "finish":
    # 支持新旧两种格式：优先使用 result，兼容 answer
    state.final_answer = action.params.get("result") or action.params.get("answer", action.memory)
```

**Step 5: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_react_agent.py::test_finish_action_with_new_params -v`
Expected: PASS

**Step 6: 验证兼容性（旧格式仍然工作）**

```python
def test_finish_action_backward_compatible():
    """测试 finish 旧格式仍然兼容"""
    from ai_agent.agents.react import ReActAgent, AgentState, ReActAction

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm, tools=[])

    # 使用旧格式参数
    action = ReActAction(
        action="finish",
        params={"answer": "Old format answer"},
        memory="Some memory"
    )

    state = AgentState(question="Test question")
    updates = agent._update_state_node(state, action)

    # 旧格式仍然有效
    assert updates["final_answer"] == "Old format answer"
```

Run: `pytest tests/unit/agents/test_react_agent.py::test_finish_action_backward_compatible -v`
Expected: PASS

---

## Task 4: 运行完整测试套件

**Files:**
- All test files

**Step 1: 运行所有 react 相关测试**

Run: `pytest tests/unit/agents/test_react_agent.py -v`
Expected: All PASS

**Step 2: 运行工具相关测试**

Run: `pytest tests/unit/tools/ -v`
Expected: All PASS

**Step 3: 运行 prompt 测试**

Run: `pytest tests/unit/prompts/ -v`
Expected: All PASS

---

## Task 5: 提交变更

**Step 1: 检查变更**

Run: `git status`
Run: `git diff src/ai_agent/agents/react/graph.py`

**Step 2: 提交**

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent.py
git commit -m "refactor(react): improve _build_action_space format with JSON Schema

- Add FINISH_ACTION_SCHEMA constant with result/status/memory fields
- Refactor _build_action_space to benchmark format:
  - Use '### Name' section headers
  - Add explicit 'Description:' prefix
  - Output full JSON Schema for Parameters
- Update finish handling to support both 'result' and 'answer' params
- Add comprehensive tests for new format and backward compatibility"
```

---

## 变更文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/ai_agent/agents/react/graph.py` | 修改 | 添加常量、重构方法、更新 finish 处理 |
| `tests/unit/agents/test_react_agent.py` | 修改 | 更新测试、添加新测试 |

---

## 风险评估

1. **LLM 兼容性**：新格式可能导致现有 prompt 行为变化
   - 缓解：完整测试，监控 LLM 响应

2. **向后兼容**：旧代码可能依赖旧格式
   - 缓解：finish 处理同时支持 `answer` 和 `result` 字段
