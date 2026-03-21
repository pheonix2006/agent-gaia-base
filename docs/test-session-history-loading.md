# 会话历史加载功能测试说明

## 已完成的修复

### 1. 后端修复
- ✅ 清理了错误的项目注册（ai-agent-2）
- ✅ 添加 `GET /api/v1/sessions/{session_id}` API 端点
- ✅ 修改 chat.py，将思考事件也保存到 traces.jsonl
- ✅ 使用特殊标记 `tool="_think_"` 标识思考事件

### 2. 前端修复
- ✅ 修改 `switchSession()` 函数，切换会话时加载历史
- ✅ 添加 `renderSessionHistory()` 函数，渲染历史消息和工具调用
- ✅ 识别思考事件 (`_think_`) 并渲染为思考卡片

---

## 测试步骤

### 1. 启动服务

```bash
cd "E:/Project/ai agent"
uv run python main.py
```

### 2. 运行后端集成测试

```bash
uv run python tests/manual/test_session_api_integration.py
```

**预期结果：**
- SessionManager 测试：✅ 通过
- API 端点测试：✅ 通过
- 消息数：5
- 调用记录数：35

### 3. 前端测试

#### 3.1 测试旧历史加载（没有思考事件）

1. 打开 `http://localhost:8000/chat.html`
2. 点击侧边栏的会话 "20260321-001"（旧数据）
3. **预期：** 显示工具调用步骤（read, web_search），**但没有思考卡片**

#### 3.2 测试新对话（包含思考事件）

1. 点击"新建会话"
2. 发送消息："今天的日期是什么？"
3. 观察 Assistant 回复过程中的事件（应该有思考卡片）
4. 点击侧边栏的其他会话
5. 再点击回刚创建的会话
6. **预期：** 完整加载历史，**包括思考卡片**

---

## 关于旧数据的说明

### 问题
旧的历史数据（如 20260321-001）是在修改前创建的，**traces.jsonl 中没有保存思考事件**。

### 数据对比

**旧数据（修改前）：**
```json
{"tool":"read","params":{...},"result_status":"success",...}
{"tool":"web_search","params":{...},"result_status":"success",...}
```

**新数据（修改后）：**
```json
{"tool":"_think_","params":{"reasoning":"...","raw_output":"..."},"result_status":"success",...}
{"tool":"read","params":{...},"result_status":"success",...}
{"tool":"web_search","params":{...},"result_status":"success",...}
```

### 解决方案

**方案 A：创建新对话测试**
- 直接创建新对话，思考事件会自动保存
- 最简单，推荐用于验证功能

**方案 B：为旧数据补充思考事件**
- 需要重新运行 Agent 生成思考内容
- 复杂，不推荐

---

## 验收标准

- [ ] 后端集成测试全部通过
- [ ] 旧历史会话能正常加载（即使缺少思考卡片）
- [ ] 新对话的思考事件被正确保存
- [ ] 新对话的历史加载时显示思考卡片
- [ ] 工具调用步骤卡片正确显示
- [ ] 用户和 Assistant 消息都正确渲染
- [ ] 切换会话流畅无延迟

---

## 调试技巧

### 查看会话数据

```bash
# 查看会话列表
ls "C:/Users/MR/.agents/history/ai-agent/"

# 查看消息历史
cat "C:/Users/MR/.agents/history/ai-agent/<session-id>/messages.jsonl"

# 查看调用记录（包括思考事件）
cat "C:/Users/MR/.agents/history/ai-agent/<session-id>/traces.jsonl"
```

### 浏览器控制台调试

1. 打开浏览器开发者工具 (F12)
2. 切换到 Console 标签
3. 点击会话，查看调试输出：
   ```
   [DEBUG] Switching to session: xxx
   [DEBUG] Fetching session data from API...
   [DEBUG] Session data received: {...}
   [DEBUG] Rendering history: 5 messages
   ```

### 检查 API 响应

```bash
curl http://localhost:8000/api/v1/sessions/<session-id> | python -m json.tool
```

---

## 文件修改清单

### 后端
- `src/ai_agent/api/routes/sessions.py` - 添加获取会话历史的 API 端点
- `src/ai_agent/api/routes/chat.py` - 保存思考事件到 traces
- `scripts/cleanup_duplicate_projects.py` - 清理重复项目注册

### 前端
- `src/ai_agent/api/static/chat.html` - 加载并渲染会话历史

### 测试
- `tests/manual/test_session_api_integration.py` - 后端集成测试脚本

---

## 已知问题

1. **旧数据缺少思考事件** - 修改前创建的会话没有思考卡片
2. **性能未优化** - 大量历史消息时未实现分页（可后续优化）

---

## 下一步优化（可选）

1. **消息分页** - 超过 100 条消息时实现懒加载
2. **思考事件索引** - 为思考事件创建单独的存储
3. **会话搜索** - 支持按标题或内容搜索会话
4. **会话导出** - 支持导出会话为 Markdown 或 JSON
