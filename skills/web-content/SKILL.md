---
name: web-content
description: 提取网页内容并回答问题。需要提供 url 和 query 两个参数。支持任意 http/https URL。
---

# Web Content

抓取网页内容并基于内容回答问题。

## ⚠️ 重要提示

**必须同时提供两个参数，缺一不可：**
1. `url`: 网页地址
2. `query`: 针对网页内容的具体问题或指令

❌ **错误示例：** 只提供 url
```json
{
  "action": "web_content",
  "params": {
    "url": "https://example.com"
  }
}
```

✅ **正确示例：** 同时提供 url 和 query
```json
{
  "action": "web_content",
  "params": {
    "url": "https://example.com",
    "query": "这篇文章的主要观点是什么？"
  }
}
```

## 何时使用

- 需要获取某个网页的完整内容
- 基于特定网页回答问题
- 提取网页中的特定信息
- 总结网页内容
- 从网页中提取特定数据

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✅ 是 | 网页 URL（仅支持 http/https） |
| query | string | ✅ 是 | 针对网页内容的问题或指令 |

## 使用示例

### 示例 1：获取文档信息
```json
{
  "action": "web_content",
  "params": {
    "url": "https://docs.anthropic.com/claude/docs",
    "query": "Claude 支持哪些模型？各自的特点是什么？"
  }
}
```

### 示例 2：提取文章要点
```json
{
  "action": "web_content",
  "params": {
    "url": "https://www.basketball-reference.com/players/b/banchpa01.html",
    "query": "这个球员的基本信息、职业生涯数据和成就有哪些？"
  }
}
```

### 示例 3：总结博客文章
```json
{
  "action": "web_content",
  "params": {
    "url": "https://example.com/blog/ai-trends-2024",
    "query": "总结这篇文章的 3 个主要观点"
  }
}
```

### 示例 4：提取特定数据
```json
{
  "action": "web_content",
  "params": {
    "url": "https://github.com/langchain-ai/langchain",
    "query": "这个项目有多少 star？最近一次更新是什么时候？主要功能是什么？"
  }
}
```

### 示例 5：对比分析
```json
{
  "action": "web_content",
  "params": {
    "url": "https://python.org/downloads",
    "query": "当前最新的 Python 版本是什么？有哪些主要新特性？"
  }
}
```

## 返回结果

返回包含以下字段的对象：
- `url`: 请求的 URL
- `answer`: 基于网页内容的回答
- `source_preview`: 网页内容预览（前 2000 字符）

```json
{
  "url": "https://docs.anthropic.com/claude/docs",
  "answer": "Claude 支持以下模型：Claude 3 Opus、Claude 3.5 Sonnet...",
  "source_preview": "# Claude Documentation\n\nClaude is..."
}
```

## 常见错误

### ❌ 错误 1：缺少 query 参数
```json
{
  "action": "web_content",
  "params": {
    "url": "https://example.com"
  }
}
```
**错误信息：** `ValidationError: Field required [type=missing, input_value={'url': '...'}]`

**解决方法：** 添加 query 参数
```json
{
  "action": "web_content",
  "params": {
    "url": "https://example.com",
    "query": "请总结这个页面的内容"
  }
}
```

### ❌ 错误 2：query 过于模糊
```json
{
  "action": "web_content",
  "params": {
    "url": "https://example.com",
    "query": "信息"  // 太模糊
  }
}
```
**问题：** 可能得到不够精确的答案

**解决方法：** 使用具体的问题
```json
{
  "action": "web_content",
  "params": {
    "url": "https://example.com",
    "query": "这家公司的主营业务是什么？成立时间？"
  }
}
```

## 最佳实践

1. **明确的问题**
   - ✅ 好：`"这个产品的价格是多少？有哪些功能？"`
   - ❌ 差：`"告诉我一些信息"`

2. **结构化查询**
   - ✅ 好：`"总结以下 3 点：1) 主要功能 2) 适用场景 3) 价格"`
   - ❌ 差：`"介绍这个产品"`

3. **具体化需求**
   - ✅ 好：`"列出前 5 个特性，每个用一句话说明"`
   - ❌ 差：`"列出所有特性"`

4. **合理使用**
   - 适用于：需要从特定网页提取信息的场景
   - 不适用于：通用搜索（请使用 web-search 工具）

## 注意事项

- 仅支持 http/https 协议
- 部分网站可能无法访问（如需要登录的页面）
- 长文本会自动分块处理（超过 95000 tokens）
- 需要 OPENAI_API_KEY 环境变量配置
- 通过 Jina Reader API 获取网页内容（支持免费和付费模式）

## 工作原理

1. 使用 Jina Reader API 获取网页的纯文本内容
2. 如果内容过长（>95000 tokens），自动分块处理
3. 使用 LLM 根据你的 query 分析网页内容
4. 返回精准的答案

## 与 web-search 的区别

| 工具 | 用途 | 输入 | 输出 |
|------|------|------|------|
| **web-search** | 搜索互联网信息 | 搜索关键词 | 多个搜索结果列表 |
| **web-content** | 提取特定网页内容 | URL + 问题 | 针对该网页的精准答案 |

**使用流程：**
1. 使用 `web-search` 搜索相关信息
2. 从搜索结果中选择相关 URL
3. 使用 `web-content` 深度分析该 URL 的内容
