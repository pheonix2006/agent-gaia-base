---
name: get_repo_structure
description: Get the directory structure and file list of a GitHub repository.
---

# get_repo_structure

来源: MCP 服务器 `zread`

Get the directory structure and file list of a GitHub repository.

## 参数说明

### 必填参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| repo_name | string | 是 | - | GitHub repository: owner/repo (e.g. "vitejs/vite") |

### 可选参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| dir_path | string | 否 | - | The directory path to inspect (default: root "/") |

## 使用示例

```json
{
    "action": get_repo_structure,
    "params": {
        "repo_name": "<repo_name>",
        "dir_path": "<dir_path>"
    }
}
```
