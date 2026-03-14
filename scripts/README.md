# 工具验证脚本

这个目录包含用于验证多模态工具的测试脚本。

## 前置要求

确保 `.env` 文件中配置了以下 API Key：

```env
# LLM 配置 (GLM-4.6V 多模态模型)
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4.6v

# Jina API (网页内容提取)
JINA_API_KEY=your_jina_key

# Serper API (Google 搜索)
SERPER_API_KEY=your_serper_key
SERPER_BASE_URL=https://google.serper.dev/search
```

## 运行方式

### 1. 测试所有工具（推荐）

```bash
cd "E:/Project/ai agent"
python scripts/test_all.py
```

### 2. 单独测试每个工具

```bash
# 测试网页内容提取 (Jina API)
python scripts/test_web_content.py

# 测试 Google 搜索 (Serper API)
python scripts/test_google_search.py

# 测试图像分析 (GLM-4.6V)
python scripts/test_image_analysis.py

# 测试音频解析 (GLM-4.6V) - 需要提供音频文件
python scripts/test_audio_parse.py /path/to/audio.mp3
```

## 测试说明

| 脚本 | 工具 | API | 测试内容 |
|------|------|-----|----------|
| `test_web_content.py` | WebContentTool | Jina | 提取 Python 官网和 GitHub README |
| `test_google_search.py` | GoogleSearchTool | Serper | 搜索 Python、AI、问答 |
| `test_image_analysis.py` | ImageAnalysisTool | GLM-4.6V | 分析 Python Logo 等图片 |
| `test_audio_parse.py` | AudioParseTool | GLM-4.6V | 转录用户提供的音频文件 |

## 预期输出

成功的测试会显示：
```
✅ 成功!
   耗时: 1.23s
   结果: ...
```

失败的测试会显示：
```
❌ 失败: API Key 未配置
```
