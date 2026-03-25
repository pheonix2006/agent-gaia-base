---
name: web_search_prime
description: Search web information, returns results including web page title, web page URL, web page summary, website name, website icon, etc.
---

# web_search_prime

来源: MCP 服务器 `web-search-prime`

Search web information, returns results including web page title, web page URL, web page summary, website name, website icon, etc.

## 参数说明

### 必填参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| search_query | string | 是 | - | Content to be searched, it is recommended that the search query not exceed 70 characters |

### 可选参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| search_domain_filter | string | 否 | - | Used to limit the scope of search results, only return content from specified whitelist domains, such as: www.example.com. |
| search_recency_filter | string | 否 | `noLimit` | Search for web pages within a specified time range. |
| content_size | string | 否 | `medium` | Control the number of words in the web page summary; |
| location | string | 否 | `cn` | Guess which region the user is from based on user input. |

**search_recency_filter 可选值：** `oneDay`, `oneWeek`, `oneMonth`, `oneYear`, `noLimit`
**location 可选值：** `cn`, `us`

## 使用示例

```json
{
    "action": web_search_prime,
    "params": {
        "search_query": "<search_query>",
        "search_domain_filter": "<search_domain_filter>",
        "search_recency_filter": "noLimit",
        "content_size": "medium",
        "location": "cn"
    }
}
```
