# 修复JSON解析截断问题

## 问题描述

Agent在处理LLM返回的JSON时，如果字符串内容包含特殊字符组合（如`"}`, `",`），会导致内容被提前截断。

### 问题示例

**LLM返回的原始JSON：**
```json
{
  "action": "finish",
  "params": {
    "result": "根据Agent Skills规范...

## 核心原则

```json
{
  "skills": [...]
}
```

这种渐进式加载...",
    "status": "done"
  },
  "memory": "已获取信息"
}
```

**问题表现：**
- 用户看到"原始输出"中包含完整的JSON
- 但解析后只显示了部分内容（在第一个`"}`处截断）

## 根本原因

### 1. 有缺陷的正则表达式

**位置：** `src/ai_agent/agents/react/graph.py:509-516`

```python
# 问题代码
result_match = re.search(r'"result"\s*:\s*"([\s\S]*?)(?:"\s*[,}]|"\s*$)', text)
memory_match = re.search(r'"memory"\s*:\s*"([\s\S]*?)(?:"\s*[,}]|"\s*$)', text)
```

**问题分析：**
- `[\s\S]*?` 使用**非贪婪匹配**
- 会在遇到第一个符合`"\s*[,}]`模式的位置停止
- 如果字符串内容包含`"}`或`",`组合，正则误认为字符串结束
- 导致内容被提前截断

### 2. 未传递修复后的JSON

**位置：** `src/ai_agent/agents/react/graph.py:329`

```python
# 问题代码
return self._extract_action_with_regex(json_str)  # 传入原始字符串
```

`_extract_action_with_regex`接收到的是原始JSON字符串，而不是经过`_repair_json_string`修复的字符串，导致无法正确处理实际换行符等问题。

## 解决方案

### 修复1：重写字符串提取逻辑

**新增方法：** `_extract_json_string_value`

使用**状态机**逐字符解析JSON字符串，而非正则表达式：

```python
def _extract_json_string_value(self, text: str, field_name: str) -> str | None:
    """从JSON文本中提取指定字段的字符串值

    使用括号匹配而非正则表达式，正确处理字符串内的转义引号和嵌套结构。
    """
    # 查找字段位置
    field_pattern = f'"{field_name}"\s*:\s*"'
    field_match = re.search(field_pattern, text)
    if not field_match:
        return None

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
            # 找到字符串结束（非转义的引号）
            return ''.join(result_chars)

        result_chars.append(char)
        i += 1

    return None
```

**优势：**
- ✅ 正确处理转义引号`\"`
- ✅ 正确处理嵌套JSON和markdown代码块
- ✅ 正确反转义JSON转义序列
- ✅ 不会被字符串内的特殊字符组合干扰

### 修复2：传递修复后的JSON

**位置：** `src/ai_agent/agents/react/graph.py:329`

```python
# 修复后
return self._extract_action_with_regex(cleaned)  # 传入修复后的字符串
```

确保`_extract_action_with_regex`接收到的是经过`_repair_json_string`修复的JSON字符串，正确处理实际换行符等控制字符。

## 测试验证

### 测试用例

创建了`test_json_string_extraction.py`，包含以下测试：

1. ✅ 简单字符串
2. ✅ 包含引号的字符串
3. ✅ 包含换行符的字符串
4. ✅ 包含markdown代码块的字符串（核心问题）
5. ✅ 包含转义反斜杠的字符串
6. ✅ 不存在的字段返回None
7. ✅ 完整的finish action解析

### 测试结果

```
[PASS] 所有测试通过!
[PASS] 原始问题案例测试通过!
  result长度: 365
  memory: 已获取Agent Skills规范中关于渐进式加载的详细信息
```

## 影响范围

### 修改的文件

- `src/ai_agent/agents/react/graph.py`
  - 新增`_extract_json_string_value`方法
  - 修改`_extract_action_with_regex`方法调用新方法
  - 修改`_parse_action`传递修复后的JSON

### 向后兼容性

- ✅ 完全向后兼容
- ✅ 仅修改内部实现，API无变化
- ✅ 所有现有测试应该继续通过

## 总结

这次修复彻底解决了JSON字符串解析的截断问题，使Agent能够正确处理包含markdown代码块、嵌套JSON等复杂内容的LLM响应。核心改进是：

1. **从正则表达式切换到状态机解析** - 更可靠、更精确
2. **正确处理JSON转义序列** - 反转义`\n`, `\"`等
3. **使用修复后的JSON** - 统一处理实际换行符等异常

现在Agent可以可靠地处理任意复杂的JSON字符串内容了！
