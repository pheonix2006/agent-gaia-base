---
name: webReader
description: Fetch and Convert URL to Large Model Friendly Input.
---

# webReader

来源: MCP 服务器 `web-reader`

Fetch and Convert URL to Large Model Friendly Input.

## 参数说明

### 必填参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| url | string | 是 | - | The URL of the website to fetch and read |

### 可选参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| timeout | integer | 否 | `20` | Request timeout(unit is second), |
| no_cache | boolean | 否 | `false` | Disable cache(true/false), |
| return_format | string | 否 | `markdown` | Reader response content type (markdown or text), |
| retain_images | boolean | 否 | `true` | Retain images (true/false), |
| no_gfm | boolean | 否 | `false` | Disable GitHub Flavored Markdown (true/false), |
| keep_img_data_url | boolean | 否 | `false` | Keep image data URL (true/false), |
| with_images_summary | boolean | 否 | `false` | Include images summary (true/false), |
| with_links_summary | boolean | 否 | `false` | Include links summary (true/false), |

## 使用示例

```json
{
    "action": webReader,
    "params": {
        "url": "<url>",
        "timeout": "20",
        "no_cache": "false",
        "return_format": "markdown",
        "retain_images": "true",
        "no_gfm": "false",
        "keep_img_data_url": "false",
        "with_images_summary": "false",
        "with_links_summary": "false"
    }
}
```
