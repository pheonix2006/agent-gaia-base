---
name: search_doc
description: Search documentation, issues, and commits of a GitHub repository.
---

# search_doc

来源: MCP 服务器 `zread`

Search documentation, issues, and commits of a GitHub repository.

## 参数说明

### 必填参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| repo_name | string | 是 | - | GitHub repository: owner/repo (e.g. "vitejs/vite") |
| query | string | 是 | - | The search keywords or question about the repository. |

### 可选参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| language | string | 否 | - | 'zh' or 'en' (choose according to context language). |

## 使用示例

```json
{
    "action": search_doc,
    "params": {
        "repo_name": "<repo_name>",
        "query": "<query>",
        "language": "<language>"
    }
}
```
