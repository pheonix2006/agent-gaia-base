---
name: read_file
description: Read the full code content of a specific file in a GitHub repository.
---

# read_file

来源: MCP 服务器 `zread`

Read the full code content of a specific file in a GitHub repository.

## 参数说明

### 必填参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| repo_name | string | 是 | - | GitHub repository: owner/repo (e.g. "vitejs/vite") |
| file_path | string | 是 | - | The relative path to the file (e.g. "src/index.ts"). |

## 使用示例

```json
{
    "action": read_file,
    "params": {
        "repo_name": "<repo_name>",
        "file_path": "<file_path>"
    }
}
```
