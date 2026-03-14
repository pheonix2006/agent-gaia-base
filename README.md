# AI Agent

基于 LangGraph 的 AI Agent 服务，支持工具调用、流式输出和记忆功能。

## 特性

- **ReAct Agent** - 思考-行动-观察循环，自动选择工具完成任务
- **流式输出** - SSE 实时返回执行过程，支持前端展示
- **多种工具** - Google 搜索、网页抓取、图像分析、音频解析
- **记忆功能** - 自动压缩历史对话，保持长对话上下文
- **LangSmith 追踪** - 可选的链路追踪和调试支持

## 快速开始

### 前置要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd ai-agent

# 安装依赖
uv sync
```

### 配置

创建 `.env` 文件：

```env
# LLM 配置（必需，兼容 OpenAI API 格式）
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# 工具 API（可选，按需配置）
SERPER_API_KEY=your_serper_key      # Google 搜索
JINA_API_KEY=your_jina_key          # 网页内容提取
```

### 运行

```bash
uv run uvicorn ai_agent.api.main:app --reload
```

服务启动后访问：
- API 文档：http://localhost:8000/docs
- 聊天页面：http://localhost:8000

## API 示例

### 同步调用

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "今天北京天气怎么样？"}'
```

响应：
```json
{"response": "今天北京天气晴朗，气温 15-25°C..."}
```

### 流式调用

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "搜索一下 LangGraph 是什么"}'
```

响应（SSE 格式）：
```
data: {"event": "think", "data": {"action": "google_search", ...}, "step": 1}

data: {"event": "act", "data": {"tool_name": "google_search", ...}, "step": 2}

data: {"event": "observe", "data": {"result_summary": "...", ...}, "step": 3}

data: {"event": "finish", "data": {"answer": "LangGraph 是 ..."}, "step": 4}
```

## 许可证

MIT
