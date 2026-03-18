---
name: web-content
description: 提取网页内容并回答问题。支持任意 http/https URL。
---

# Web Content

抓取网页内容并基于内容回答问题。

## 何时使用

- 需要获取某个网页的完整内容
- 基于特定网页回答问题
- 提取网页中的特定信息

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | 是 | 网页 URL（仅支持 http/https） |
| query | string | 是 | 针对网页内容的问题或指令 |

## 使用示例

```json
{
  "action": "web_content",
  "params": {
    "url": "https://docs.anthropic.com/claude/docs",
    "query": "Claude 支持哪些模型？各自的特点是什么？"
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

## 注意事项

- 仅支持 http/https 协议
- 部分网站可能无法访问
- 长文本会自动分块处理
- 需要 OPENAI_API_KEY 环境变量
