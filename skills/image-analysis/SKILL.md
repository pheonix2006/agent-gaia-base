---
name: image-analysis
description: 分析图像内容，回答关于图像的问题。支持本地图片和 URL。
---

# Image Analysis

使用多模态模型分析图像内容。

## 何时使用

- 识别图片中的物体、场景、文字
- 分析图表、截图、设计稿
- 描述图片内容
- 回答关于图片的问题

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| image_path | string | 是 | 图片路径（本地文件或 URL） |
| query | string | 是 | 关于图像的问题或分析指令 |

## 支持的图片格式

- PNG (.png)
- JPEG (.jpg, .jpeg)
- GIF (.gif)
- WebP (.webp)

## 使用示例

```json
{
  "action": "image_analysis",
  "params": {
    "image_path": "/path/to/screenshot.png",
    "query": "这个界面有哪些主要功能？请列出所有按钮和它们的作用。"
  }
}
```

## 返回结果

返回对图像的分析结果文本。

```json
{
  "success": true,
  "data": "这个界面是一个文本编辑器，包含以下主要功能：\n1. 文件操作区...",
  "error": null,
  "metrics": {
    "elapsed_time": 2.5
  }
}
```

## 注意事项

- 本地文件需要存在且可读
- URL 需要可公开访问
- 大图片可能需要较长处理时间
- 需要 OPENAI_API_KEY 环境变量
