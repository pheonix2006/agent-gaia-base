---
name: audio-parse
description: 解析音频文件，转录为文字或回答关于音频的问题。支持多种音频格式。
---

# Audio Parse

将音频文件转录为文字或回答关于音频的问题。

## 何时使用

- 转录录音、会议记录
- 提取音频中的对话内容
- 处理语音消息
- 回答关于音频内容的问题

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| audio_path | string | 是 | 音频文件路径（仅支持本地文件） |
| query | string | 是 | 关于音频的问题或转录指令 |

## 支持的音频格式

- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- FLAC (.flac)
- OGG (.ogg)
- AAC (.aac)

## 使用示例

```json
{
  "action": "audio_parse",
  "params": {
    "audio_path": "/path/to/recording.mp3",
    "query": "请将这段录音转录为文字"
  }
}
```

## 返回结果

返回转录的文字内容或问题回答。

```json
{
  "success": true,
  "data": "转录结果：大家好，今天我们来讨论项目的进展情况...",
  "error": null,
  "metrics": {
    "elapsed_time": 5.2,
    "audio_format": "mp3",
    "audio_size": 1024000
  }
}
```

## 注意事项

- 仅支持本地文件
- 音频质量影响转录准确度
- 长音频可能需要较长处理时间
- 需要 OPENAI_API_KEY 环境变量
