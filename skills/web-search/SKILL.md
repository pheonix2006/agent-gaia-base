---
name: web-search
description: 搜索互联网获取实时信息、新闻、技术文档等。支持中英文搜索，中文效果更佳。
---

# Web Search

使用 Web Search 工具搜索互联网获取信息。

## 何时使用

- 用户询问最新新闻、事件、动态
- 需要获取实时数据、统计信息
- 查找技术文档、教程、解决方案
- 验证事实性信息

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 搜索关键词，不超过 70 字符 |
| count | int | 否 | 10 | 返回结果数量，1-50 |
| search_recency_filter | string | 否 | noLimit | 时间范围过滤 |

**search_recency_filter 可选值：**
- `oneDay` - 最近一天
- `oneWeek` - 最近一周
- `oneMonth` - 最近一个月
- `oneYear` - 最近一年
- `noLimit` - 不限制

## 使用示例

```json
{
  "action": "web_search",
  "params": {
    "query": "Claude 3.5 最新功能",
    "count": 5,
    "search_recency_filter": "oneWeek"
  }
}
```

## 返回结果

返回搜索结果列表，每项包含：
- `title`: 页面标题
- `content`: 摘要内容
- `link`: 页面链接

```json
[
  {
    "title": "Claude 3.5 发布新功能",
    "content": "Anthropic 发布 Claude 3.5 Sonnet...",
    "link": "https://example.com/article"
  }
]
```

## 注意事项

- 中文搜索效果更佳
- 复杂查询建议拆分为多个简单搜索
- 如需获取完整网页内容，配合 web-content Skill 使用
- 需要 ZHIPU_API_KEY 环境变量
