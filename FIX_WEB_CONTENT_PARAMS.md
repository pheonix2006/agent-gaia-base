# WebContentTool 参数验证修复

## 问题描述

**原始错误：**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for WebContentParams
query
  Field required [type=missing, input_value={'url': 'https://www.basketball-reference.com/players/b/banchpa01.html'}, input_type=dict]
```

**根本原因：**
- `WebContentParams` 需要两个必需参数：`url` 和 `query`
- 但 LLM 调用时只传入了 `url`，缺少 `query` 参数
- 工具的 `description` 不够清晰，没有明确说明需要**两个**参数

## 修复方案

### 1. 改进工具描述 ✅

**文件：** `src/ai_agent/tools/web/web_content.py`

**修改前：**
```python
@property
def description(self) -> str:
    return "提取网页内容并回答问题。支持 http/https URL。返回基于网页内容的答案。"
```

**修改后：**
```python
@property
def description(self) -> str:
    return (
        "提取网页内容并回答问题。"
        "需要提供两个参数："
        "1. url: 要提取内容的网页 URL（仅支持 http/https）"
        "2. query: 针对网页内容的具体问题或指令"
        "示例：{'url': 'https://example.com', 'query': '这篇文章的要点是什么？'}"
    )
```

**改进点：**
- ✅ 明确说明需要**两个**参数
- ✅ 详细说明每个参数的作用
- ✅ 提供具体的调用示例

### 2. 添加参数验证测试 ✅

**文件：** `tests/unit/tools/web/test_web_content.py`

**新增测试用例：**
```python
def test_params_validation_missing_query(self):
    """测试缺少必需参数 query 时抛出验证错误"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        WebContentParams(url="https://example.com")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("query",)
    assert errors[0]["type"] == "missing"
```

**测试覆盖：**
- ✅ 缺少 `query` 参数
- ✅ 缺少 `url` 参数
- ✅ 两个参数都缺少

### 3. 改进 ReAct Prompt ✅

**文件：** `src/ai_agent/prompts/react.py`

**新增指导：**
```python
==== Guidelines ====
...
8. ⚠️ Always provide ALL required parameters for each tool (check tool descriptions)
9. If unsure about parameters, check the tool's parameter schema first
```

**改进点：**
- ✅ 明确提醒 LLM 提供所有必需参数
- ✅ 引导 LLM 在不确定时查看工具描述

## 验证结果

### 单元测试 ✅

```bash
$ uv run pytest tests/unit/tools/web/test_web_content.py -v

tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_tool_properties PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_params_schema PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_web_content_params PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_params_validation_missing_query PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_params_validation_missing_url PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_params_validation_missing_both PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_run_success PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_run_fetch_failure PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_run_empty_content PASSED
tests/unit/tools/web/test_web_content.py::TestWebContentTool::test_run_long_content_chunking PASSED

============================= 10 passed in 0.60s ==============================
```

### 类型检查 ✅

```bash
$ uv run mypy src/ai_agent/tools/web/web_content.py
Success: no issues found in 1 source file

$ uv run mypy src/ai_agent/prompts/react.py
Success: no issues found in 1 source file
```

### 参数 Schema 验证 ✅

```json
{
  "description": "网页内容提取参数",
  "properties": {
    "url": {
      "description": "要提取内容的网页 URL（仅支持 http/https）",
      "type": "string"
    },
    "query": {
      "description": "针对网页内容的问题或指令",
      "type": "string"
    }
  },
  "required": ["url", "query"],
  "type": "object"
}
```

## 影响

### 正面影响 ✅
- ✅ LLM 现在能清楚地知道 `web_content` 工具需要两个参数
- ✅ 减少参数验证错误的发生
- ✅ 提高工具调用的成功率
- ✅ 更好的开发者体验（错误信息更清晰）

### 潜在风险 ⚠️
- ⚠️ 描述变长可能占用更多 token（影响很小，可忽略）
- ✅ 向后兼容（不影响现有代码，只是改进描述）

## 最佳实践

### 工具描述规范

根据这次修复，总结出以下工具描述最佳实践：

```python
@property
def description(self) -> str:
    return (
        "简要描述工具功能。"
        "需要提供 N 个参数："
        "1. param1: 参数说明"
        "2. param2: 参数说明"
        "示例：{'param1': 'value1', 'param2': 'value2'}"
    )
```

**关键要素：**
1. ✅ 第一句话说明核心功能
2. ✅ 明确列出所有必需参数
3. ✅ 每个参数有清晰的作用说明
4. ✅ 提供一个具体的调用示例

## 相关文件

- `src/ai_agent/tools/web/web_content.py` - WebContentTool 实现
- `tests/unit/tools/web/test_web_content.py` - 单元测试
- `src/ai_agent/prompts/react.py` - ReAct Prompt 模板
- `verify_web_content_fix.py` - 验证脚本

## 总结

这次修复通过以下三个层面解决问题：

1. **工具层面：** 改进工具描述，明确说明参数要求
2. **测试层面：** 添加参数验证测试，防止回归
3. **Prompt 层面：** 改进 ReAct prompt，引导 LLM 正确调用

现在 LLM 在调用 `web_content` 工具时会清楚地知道需要提供 `url` 和 `query` 两个参数！
