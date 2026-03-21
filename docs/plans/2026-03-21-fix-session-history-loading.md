# 修复会话历史加载功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 修复会话历史无法加载的问题，实现切换会话时自动加载完整的对话历史和工具调用记录

**架构：** 后端提供 `GET /api/v1/sessions/{session_id}` API，前端 `switchSession()` 调用 API 并渲染历史消息

**技术栈：** FastAPI, Pydantic, SQLite (HistoryStore), 纯 HTML/CSS/JavaScript

**根本原因分析：**
1. ✅ API 端点已实现但返回空数据
2. ✅ 会话数据实际存储在 `C:\Users\MR\.agents\history\ai-agent\20260321-001`
3. ❌ API 返回的 project_slug 是 "ai-agent-2" 而不是 "ai-agent"
4. ❌ `load_session_data()` 遍历所有项目查找会话，但使用了错误的 slug

---

## Task 1: 添加调试日志定位问题

**目的：** 确认 `load_session_data()` 查找会话的过程

**文件：**
- Modify: `src/ai_agent/api/routes/sessions.py:313-343`

**Step 1: 添加调试日志**

```python
# src/ai_agent/api/routes/sessions.py
# 在 get_session_data 函数中添加日志

@router.get("/sessions/{session_id}", response_model=SessionDataResponse)
async def get_session_data(request: Request, session_id: str) -> SessionDataResponse:
    """获取会话完整数据（包括消息历史和工具调用记录）"""
    session_manager: SessionManager = request.app.state.session_manager

    # 需要确定 session 所属的项目
    projects = session_manager.project_manager.list_projects()

    for project in projects:
        logger.info(f"Searching in project: {project.slug} (path: {project.path})")  # 新增
        session_data = session_manager.load_session_data(project.slug, session_id)
        if session_data is not None:
            logger.info(f"Found session {session_id} in project {project.slug}")  # 新增
            logger.info(f"Messages: {len(session_data['messages'])}, Traces: {len(session_data['traces'])}")  # 新增
            # ... 其余代码
```

**Step 2: 重启服务并测试**

运行：
```bash
cd "E:/Project/ai agent"
uv run python main.py
```

访问：`http://localhost:8000/api/v1/sessions/20260321-001`

查看控制台日志输出。

**Step 3: 根据日志分析问题**

根据日志确定：
- 遍历了哪些项目
- 在哪个项目中找到了会话
- messages 和 traces 是否被正确加载

---

## Task 2: 修复 HistoryStore.load_messages 和 load_traces

**目的：** 确保 HistoryStore 正确加载消息和调用记录

**文件：**
- Modify: `src/ai_agent/session/store.py` (load_messages 和 load_traces 方法)
- Test: `tests/unit/session/test_store.py`

**Step 1: 检查文件是否存在**

```python
# src/ai_agent/session/store.py
# 在 load_messages 方法开始处添加

def load_messages(self, project_slug: str, session_id: str) -> list[Message]:
    """加载会话的所有消息"""
    file_path = self.base_path / project_slug / session_id / "messages.jsonl"

    # 添加文件存在性检查
    if not file_path.exists():
        logger.warning(f"Messages file not found: {file_path}")
        return []

    logger.info(f"Loading messages from: {file_path}")  # 新增
    # ... 其余代码
```

**Step 2: 对 load_traces 做同样修改**

```python
def load_traces(self, project_slug: str, session_id: str) -> list[Trace]:
    """加载会话的所有调用记录"""
    file_path = self.base_path / project_slug / session_id / "traces.jsonl"

    if not file_path.exists():
        logger.warning(f"Traces file not found: {file_path}")
        return []

    logger.info(f"Loading traces from: {file_path}")  # 新增
    # ... 其余代码
```

**Step 3: 测试加载功能**

创建测试脚本：
```python
# tests/manual/test_session_loading.py
from pathlib import Path
from ai_agent.session.store import HistoryStore
from ai_agent.session.project import ProjectManager
from ai_agent.session.manager import SessionManager

# 初始化
config_dir = Path.home() / ".agents"
history_dir = config_dir / "history"

project_manager = ProjectManager(config_dir=config_dir)
history_store = HistoryStore(base_path=history_dir)
session_manager = SessionManager(store=history_store, project_manager=project_manager)

# 测试加载会话
session_id = "20260321-001"
projects = project_manager.list_projects()

for project in projects:
    print(f"\nProject: {project.slug} (path: {project.path})")
    session_data = session_manager.load_session_data(project.slug, session_id)
    if session_data:
        print(f"  Found session: {session_data['session'].title}")
        print(f"  Messages: {len(session_data['messages'])}")
        print(f"  Traces: {len(session_data['traces'])}")
    else:
        print(f"  Session not found")
```

运行：
```bash
cd "E:/Project/ai agent"
uv run python tests/manual/test_session_loading.py
```

---

## Task 3: 优化项目查找逻辑

**目的：** 改进 get_session_data 的项目查找效率

**文件：**
- Modify: `src/ai_agent/api/routes/sessions.py:295-354`

**Step 1: 添加会话索引或缓存**

当前问题：每次获取会话都要遍历所有项目。

**方案 A：在 SessionManager 中添加会话到项目的映射缓存**
```python
# src/ai_agent/session/manager.py

class SessionManager:
    def __init__(self, store: HistoryStore, project_manager: ProjectManager) -> None:
        self.store = store
        self.project_manager = project_manager
        self._session_project_map: dict[str, str] = {}  # session_id -> project_slug

    def find_session_project(self, session_id: str) -> str | None:
        """查找会话所属的项目 slug"""
        # 检查缓存
        if session_id in self._session_project_map:
            return self._session_project_map[session_id]

        # 遍历所有项目查找
        for project in self.project_manager.list_projects():
            session = self.get_session(project.slug, session_id)
            if session:
                self._session_project_map[session_id] = project.slug
                return project.slug

        return None
```

**Step 2: 在 get_session_data 中使用新方法**

```python
@router.get("/sessions/{session_id}", response_model=SessionDataResponse)
async def get_session_data(request: Request, session_id: str) -> SessionDataResponse:
    session_manager: SessionManager = request.app.state.session_manager

    # 查找会话所属项目
    project_slug = session_manager.find_session_project(session_id)
    if not project_slug:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 加载会话数据
    session_data = session_manager.load_session_data(project_slug, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话数据加载失败")

    # ... 转换为响应格式
```

**Step 3: 编写单元测试**

```python
# tests/unit/session/test_manager.py

def test_find_session_project(session_manager):
    """测试查找会话所属项目"""
    # 创建测试会话
    project_slug = "test-project"
    session = session_manager.create_session(project_slug, "Test Session")

    # 查找项目
    found_slug = session_manager.find_session_project(session.id)
    assert found_slug == project_slug

def test_find_nonexistent_session(session_manager):
    """测试查找不存在的会话"""
    found_slug = session_manager.find_session_project("nonexistent-id")
    assert found_slug is None
```

---

## Task 4: 验证前端加载逻辑

**目的：** 确认前端正确调用 API 并渲染历史

**文件：**
- Modify: `src/ai_agent/api/static/chat.html:915-990`

**Step 1: 添加前端调试日志**

```javascript
// src/ai_agent/api/static/chat.html
// 在 switchSession 函数中添加 console.log

async function switchSession(sessionId) {
    console.log('[DEBUG] Switching to session:', sessionId);  // 新增

    appState.currentSession = appState.currentProject?.sessions?.find(s => s.id === sessionId);
    if (!appState.currentSession) {
        appState.currentSession = { id: sessionId };
    }

    localStorage.setItem('last_session_id', sessionId);

    chatContainer.innerHTML = '';

    // 加载会话历史
    try {
        console.log('[DEBUG] Fetching session data from API...');  // 新增
        const sessionData = await apiCall('GET', `/api/v1/sessions/${sessionId}`);
        console.log('[DEBUG] Session data received:', sessionData);  // 新增

        if (sessionData && sessionData.messages && sessionData.messages.length > 0) {
            console.log('[DEBUG] Rendering history:', sessionData.messages.length, 'messages');  // 新增
            renderSessionHistory(sessionData);
        } else {
            console.log('[DEBUG] Empty session, showing welcome');  // 新增
            showWelcome();
        }
    } catch (error) {
        console.error('[DEBUG] Failed to load session history:', error);  // 新增
        showWelcome();
    }

    renderProjectList();
}
```

**Step 2: 在浏览器中测试**

1. 打开 `http://localhost:8000/chat.html`
2. 打开浏览器开发者工具 (F12)
3. 切换到 Console 标签
4. 点击侧边栏的会话 "20260321-001"
5. 查看控制台输出的调试信息

**预期输出：**
```
[DEBUG] Switching to session: 20260321-001
[DEBUG] Fetching session data from API...
[DEBUG] Session data received: {session: {...}, messages: [...], traces: [...]}
[DEBUG] Rendering history: 5 messages
```

---

## Task 5: 修复项目注册问题（根本原因）

**目的：** 解决 main.py 启动时注册了错误项目的问题

**文件：**
- Modify: `src/ai_agent/api/main.py:83-86`
- Test: 手动测试

**问题：** 当前有两个项目注册：
- `ai-agent` (E:\Project\ai agent) - 正确路径，有历史数据
- `ai-agent-2` (E:\Project) - 错误路径，空数据

**Step 1: 清理错误的项目注册**

手动编辑配置文件：
```bash
# 备份
cp "C:/Users/MR/.agents/projects.json" "C:/Users/MR/.agents/projects.json.backup"

# 编辑文件，删除 ai-agent-2 项目
```

或者运行清理脚本：
```python
# scripts/cleanup_projects.py
import json
from pathlib import Path

config_file = Path.home() / ".agents" / "projects.json"

with open(config_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 只保留 ai-agent 项目
data['projects'] = [p for p in data['projects'] if p['slug'] == 'ai-agent']

with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Cleaned up projects.json")
```

**Step 2: 验证 main.py 的项目注册逻辑**

```python
# src/ai_agent/api/main.py

# 当前代码（正确）：
project_root = Path(__file__).parent.parent.parent.parent  # E:\Project\ai agent
project = project_manager.register_project(project_root, "AI Agent")
```

这段代码是正确的，但可能在之前运行时路径解析有问题。

**Step 3: 添加路径验证日志**

```python
# src/ai_agent/api/main.py

project_root = Path(__file__).parent.parent.parent.parent
logger.info(f"Registering project with root: {project_root.resolve()}")  # 新增
project = project_manager.register_project(project_root, "AI Agent")
logger.info(f"Project registered: slug={project.slug}, path={project.path}")  # 新增
```

**Step 4: 重启服务验证**

```bash
cd "E:/Project/ai agent"
uv run python main.py
```

检查日志输出：
```
Registering project with root: E:\Project\ai agent
Project registered: slug=ai-agent, path=E:\Project\ai agent
```

---

## Task 6: 端到端测试

**目的：** 完整测试会话历史加载流程

**文件：**
- 无需修改代码，仅测试

**Step 1: 启动服务**

```bash
cd "E:/Project/ai agent"
uv run python main.py
```

**Step 2: 访问界面**

打开：`http://localhost:8000/chat.html`

**Step 3: 测试场景**

**场景 A：新建会话并发送消息**
1. 点击"新建会话"
2. 发送消息："测试消息 1"
3. 等待 Assistant 回复
4. 确认消息显示正常

**场景 B：切换到历史会话**
1. 点击侧边栏的会话 "20260321-001"（新会话）
2. 查看是否显示完整对话历史
3. 确认工具调用步骤卡片正确渲染
4. 确认用户和 Assistant 消息都显示

**场景 C：刷新页面**
1. 刷新浏览器 (F5)
2. 检查是否自动恢复上次会话
3. 检查历史消息是否完整加载

**Step 4: 检查浏览器控制台**

确认没有错误信息，所有 API 调用成功。

**预期结果：**
- ✅ 会话历史完整加载
- ✅ 消息和工具调用步骤正确渲染
- ✅ 切换会话流畅无延迟
- ✅ 刷新页面后历史保持

---

## Task 7: 性能优化（可选）

**目的：** 如果加载大量历史消息时性能较差，进行优化

**文件：**
- Modify: `src/ai_agent/api/routes/sessions.py` (添加分页支持)
- Modify: `src/ai_agent/api/static/chat.html` (懒加载)

**仅在 Task 6 测试发现性能问题时执行此任务。**

**Step 1: 添加消息分页参数**

```python
@router.get("/sessions/{session_id}", response_model=SessionDataResponse)
async def get_session_data(
    request: Request,
    session_id: str,
    message_limit: int = Query(default=100, ge=1, le=1000, description="消息数量限制"),
    trace_limit: int = Query(default=200, ge=1, le=1000, description="调用记录数量限制"),
) -> SessionDataResponse:
    # ... 加载会话数据
    messages = messages[-message_limit:]  # 只返回最后 N 条
    traces = traces[-trace_limit:]  # 只返回最后 N 条
    # ...
```

**Step 2: 前端实现懒加载**

如果消息超过 100 条，显示"加载更多"按钮。

---

## 验收标准

完成所有任务后，确认：

- [ ] API 端点 `GET /api/v1/sessions/{session_id}` 返回正确的消息和 traces
- [ ] 前端 `switchSession()` 成功加载并渲染历史
- [ ] 切换会话时显示完整的对话历史
- [ ] 工具调用步骤卡片正确显示
- [ ] 刷新页面后会话历史保持
- [ ] 浏览器控制台无错误
- [ ] 单元测试全部通过

---

## 相关文档

- 设计文档：`docs/design/2026-03-20-multi-project-session-ui-design.md`
- 实施计划：`docs/plans/2026-03-20-multi-project-session-ui-implementation.md`
- SessionManager 源码：`src/ai_agent/session/manager.py`
- HistoryStore 源码：`src/ai_agent/session/store.py`

---

## 提交信息模板

```bash
git add src/ai_agent/api/routes/sessions.py src/ai_agent/session/manager.py src/ai_agent/api/static/chat.html
git commit -m "fix: 修复会话历史加载功能

- 添加调试日志定位会话查找问题
- 修复 HistoryStore 文件加载逻辑
- 优化 get_session_data 项目查找效率
- 前端添加会话历史渲染功能
- 清理错误的项目注册

Fixes #[issue-number]
"
```
