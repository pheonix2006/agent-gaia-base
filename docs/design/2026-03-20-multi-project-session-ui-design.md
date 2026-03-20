# 多项目/会话管理 UI 设计文档

> **文档状态**：设计完成，待实施
> **创建时间**：2026-03-20
> **最后更新**：2026-03-20

---

## 1. 背景与目标

### 当前状态

**已完成部分：**
- ✅ SessionManager/ProjectManager 已集成到后端
- ✅ 会话持久化逻辑已实现（消息和 traces 保存）
- ✅ 后端已注册项目并创建活跃会话

**存在问题：**
- ❌ 前端 chat.html 完全没有显示 project/session 信息
- ❌ 用户无法切换项目或查看历史会话
- ❌ 权限检查不一致（ReadTool 使用旧接口）
- ❌ 缺少项目/会话管理界面

### 目标

设计并实现**完整的多项目/多会话管理界面**，提供：
1. 项目级工作空间切换（硬切换）
2. 会话历史管理和快速切换
3. 动态权限授权机制
4. 端到端可验证的实现路径

---

## 2. 核心设计决策

### 决策 1：项目切换行为 → **硬切换（IDE Workspace 模式）**

**定义：**
- 切换项目 = 切换完整工作目录上下文
- Agent 的 Read/Write/Edit 工具权限自动更新到新项目
- Skill Catalog 重新加载（不同项目可能有不同的 skills）
- PermissionManager 重置为只允许新项目路径

**理由：**
- 与 SessionManager/PermissionManager 的设计理念一致
- 避免用户困惑（当前项目 ≠ 可访问的文件）
- 更安全（项目间完全隔离）

**替代方案（未采纳）：**
- B. 软切换（仅历史隔离）
- C. 混合模式（带权限提示）

---

### 决策 2：会话标题命名 → **自动时间戳 + 可编辑**

**定义：**
- 默认标题：`"2026-03-20 14:30"`（创建时间）
- 用户可以后续手动重命名
- 重命名通过侧边栏右键菜单或编辑按钮

**理由：**
- 零摩擦创建（无需额外交互）
- 时间戳提供基本的时间顺序信息
- 保留了手动编辑的灵活性

**替代方案（未采纳）：**
- A. 用户手动输入（额外步骤）
- C. LLM 自动总结（额外成本，可能不准确）
- D. 首条消息前 50 字符（可能过长）

---

### 决策 3：UI 布局结构 → **侧边栏主导（类似 ChatGPT）**

**布局示意：**
```
┌─────────────┬──────────────────────┐
│ 项目列表     │                       │
│  ├ 项目1    │   当前会话聊天区       │
│  └ 项目2    │                       │
│             │                       │
│ 会话列表     │                       │
│  ├ 会话1    │                       │
│  └ 会话2    │                       │
│             │                       │
│ [+新建会话]  │   [输入框]            │
└─────────────┴──────────────────────┘
```

**理由：**
- 符合 AI Chat 产品的常见心智模型
- 适合桌面端使用场景
- 空间充足，层次清晰

**替代方案（未采纳）：**
- B. 顶部导航栏（节省垂直空间，但需要点击展开）
- C. 三栏布局（信息密度高，但小屏幕拥挤）

---

### 决策 4：权限管理 UI → **对话内动态授权**

**定义：**
- 默认只能访问当前项目目录
- 当用户请求访问其他路径时，前端弹出权限确认对话框
- 用户选择："允许一次"、"总是允许"、"拒绝"
- 权限决策保存到 PermissionManager（会话级）

**理由：**
- 符合用户心智（用到才问）
- 不会过度复杂化界面
- 与现有 PermissionManager 的 ASK 机制完美匹配

**替代方案（未采纳）：**
- A. 系统自动管理（无法精细控制）
- B. 设置页面手动配置（交互复杂）
- D. 混合模式（最大开发量）

---

### 决策 5：项目管理能力 → **完整 CRUD**

**定义：**
- ✅ 创建：侧边栏提供"新建项目"按钮，弹窗输入名称和路径
- ✅ 读取：项目列表自动显示
- ✅ 更新：可重命名项目
- ✅ 删除：右键菜单或删除按钮

**理由：**
- 提供最大灵活性
- 用户无需手动编辑配置文件
- 实现完整的自服务能力

**替代方案（未采纳）：**
- A. 仅查看（不够灵活）
- C. 仅创建（不对称）
- D. 桌面端拖拽（浏览器安全限制）

---

### 决策 6：会话历史加载策略 → **分页懒加载 + 缓存**

**定义：**
- 初始加载最近 20 条会话
- 滚动到底部时加载下一页
- 已访问的会话缓存到内存（下次切换无延迟）

**理由：**
- 首屏快速（只加载最近 20 条）
- 热门会话切换无延迟（缓存命中）
- 实现复杂度适中

**替代方案（未采纳）：**
- A. 一次性全量加载（启动慢）
- B. 仅分页无缓存（滚动有延迟）
- C. 按需加载（点击切换有延迟）

---

## 3. 架构设计

### 3.1 技术栈选择

**前端：**
- 框架：纯 HTML/CSS/JavaScript（无框架依赖）
- 状态管理：内存 JavaScript 对象 + LocalStorage 缓存
- 样式：扩展现有 CSS，保持暗色主题一致性

**后端 API 扩展：**
```
新增路由 /api/v1/projects
  GET    /                   → 获取项目列表
  POST   /                   → 创建项目
  PATCH  /{slug}             → 更新项目（重命名）
  DELETE /{slug}             → 删除项目

新增路由 /api/v1/sessions
  GET    /                   → 分页获取会话列表（?page=1&limit=20）
  POST   /                   → 创建新会话
  PATCH  /{id}               → 重命名会话
  DELETE /{id}               → 删除会话

新增路由 /api/v1/permissions
  POST   /request            → 权限请求确认（用户决策）
  GET    /                   → 获取当前权限列表

新增路由 /api/v1/agent
  PATCH  /context            → 切换项目上下文（重建 Agent）
```

### 3.2 数据流

**启动流程：**
```
1. 前端加载 → GET /api/v1/projects
2. 渲染项目列表 → 从 LocalStorage 读取 last_project_slug
3. GET /api/v1/sessions?project={slug}&page=1
4. 渲染会话列表 → 从 LocalStorage 读取 last_session_id
5. 加载会话详情 → 渲染聊天历史
```

**切换项目：**
```
1. 用户点击项目 → PATCH /api/v1/agent/context
2. 后端：
   - 清空 PermissionManager
   - 设置新项目路径为允许
   - 重建 Agent（加载新 Skill Catalog）
3. 前端：
   - 更新侧边栏高亮
   - 加载该项目的会话列表
   - 切换到最近活跃会话
```

**权限动态授权：**
```
1. Agent 调用工具 → PermissionManager.check() → Permission.ASK
2. 工具返回：{"success": false, "error": "PERMISSION_REQUIRED", ...}
3. 前端检测错误码 → 弹出对话框
4. 用户决策 → POST /api/v1/permissions/request
5. 后端更新 PermissionManager → 允许路径
6. 前端自动重试消息
```

---

## 4. 验证策略

### 验证点 1：权限检查一致性

**问题：** ReadTool 使用旧的 `is_allowed()` 接口，与 WriteTool/EditTool 不一致

**修复方案：**
- ✅ 统一使用 `check(path, OperationType.READ/WRITE/EDIT)`
- ✅ 移除 `is_allowed()` 旧接口
- ✅ 添加单元测试覆盖三种工具的权限拒绝场景

**验证命令：**
```bash
uv run pytest tests/unit/tools/filesystem/test_permissions.py -v
```

---

### 验证点 2：项目切换时的权限重置

**场景：** 切换项目 A → B 时，PermissionManager 应该只允许项目 B 的路径

**验证方法：**
```python
def test_switch_project_resets_permissions():
    # 1. 创建两个项目
    # 2. 在项目 A 中授权访问外部路径
    # 3. 切换到项目 B
    # 4. 验证：外部路径不再被允许
```

---

### 验证点 3：端到端贯通

**测试场景：**
```
1. 前端：点击"新建项目" → 输入名称 → POST /api/v1/projects
2. 后端：ProjectManager.register_project() → 保存到 ~/.agents/config.json
3. 前端：项目列表自动刷新 → 显示新项目
4. 前端：点击项目 → 自动创建会话 → POST /api/v1/sessions
5. 前端：发送消息 "读取 package.json"
6. 后端：Agent 调用 ReadTool → 成功返回内容
7. 前端：显示工具调用结果
```

**验证命令：**
```bash
# 手动 E2E 测试
uv run python main.py
# 打开浏览器 → 执行上述场景
```

---

### 验证点 4：权限动态授权

**测试场景：**
```
1. 当前项目：ai-agent
2. 发送消息："读取 E:/other-project/test.txt"
3. 后端：PermissionManager.check() → Permission.ASK
4. 工具返回：{"success": false, "error": "PERMISSION_REQUIRED", ...}
5. 前端：弹出对话框 "是否允许访问 E:/other-project/test.txt？"
6. 用户点击"允许一次"
7. 前端：POST /api/v1/permissions/request
8. 后端：PermissionManager.allow_path()
9. 前端：自动重试 → 成功读取文件
```

---

## 5. 实现路径

### 阶段 1：后端 API 补全（优先级：高）

**目标：** 提供完整的项目/会话管理 API

**任务：**
- [ ] 实现 `/api/v1/projects` 的 CRUD 接口
- [ ] 实现 `/api/v1/sessions` 的 CRUD 接口
- [ ] 实现 `/api/v1/agent/context` 切换接口
- [ ] 统一 ReadTool/WriteTool/EditTool 的权限检查
- [ ] 添加单元测试

**验证：**
```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "path": "/tmp/test"}'
# 预期：返回 {"slug": "test", "name": "Test", "path": "/tmp/test"}
```

---

### 阶段 2：前端侧边栏（优先级：高）

**目标：** 实现侧边栏静态 UI 和基础交互

**任务：**
- [ ] 添加侧边栏 HTML 结构（项目列表 + 会话列表）
- [ ] 调整布局（Flexbox：左侧 280px，右侧自适应）
- [ ] 实现项目/会话的展开/折叠交互
- [ ] 实现新建项目/会话的弹窗表单
- [ ] 响应式布局（可选）

**验证：**
- 打开 http://localhost:8000/
- 检查侧边栏可见，宽度 280px
- 聊天区域正确缩放

---

### 阶段 3：前后端集成（优先级：高）

**目标：** 实现端到端的数据流和交互

**任务：**
- [ ] 启动时加载项目/会话列表
- [ ] 实现切换项目的 API 调用
- [ ] 实现创建/删除/重命名项目的交互
- [ ] 实现创建/删除/重命名会话的交互
- [ ] 实现 LocalStorage 缓存（last_project_slug, last_session_id）

**验证：**
- 创建项目 → 创建会话 → 发送消息 → 验证响应

---

### 阶段 4：权限动态授权（优先级：中）

**目标：** 实现对话内动态授权流程

**任务：**
- [ ] 后端返回 PERMISSION_REQUIRED 错误码
- [ ] 前端检测错误并弹出对话框
- [ ] 实现 `/api/v1/permissions/request` 接口
- [ ] 实现重试消息机制
- [ ] 添加集成测试

**验证：**
- 跨项目访问 → 弹出对话框 → 允许 → 成功读取

---

### 阶段 5：优化与测试（优先级：中）

**目标：** 提升性能和稳定性

**任务：**
- [ ] 实现会话列表的分页懒加载
- [ ] 实现已访问会话的缓存
- [ ] 添加 E2E 集成测试
- [ ] 修复 mypy 类型检查错误
- [ ] 性能优化（大量会话时的渲染性能）

**验证：**
```bash
uv run pytest tests/integration/ -v
uv run mypy src/ai_agent
```

---

## 6. 测试策略

### 单元测试（后端）

```python
# tests/unit/api/test_projects.py
def test_create_project_api(client):
    response = client.post("/api/v1/projects", json={
        "name": "Test",
        "path": "/tmp/test"
    })
    assert response.status_code == 200
    assert response.json()["slug"] == "test"

# tests/unit/tools/filesystem/test_permissions.py
def test_read_tool_permission_unified():
    # 验证 ReadTool 使用 check(path, OperationType.READ)
    ...

# tests/unit/session/test_switch_project.py
def test_switch_project_resets_permissions():
    # 验证切换项目后权限被重置
    ...
```

### 集成测试（E2E）

```python
# tests/integration/test_full_workflow.py
@pytest.mark.integration
async def test_create_project_and_chat():
    # 1. 创建项目
    # 2. 创建会话
    # 3. 发送消息
    # 4. 验证响应
    ...
```

### 手动测试检查清单

- [ ] 创建项目 → 项目列表显示
- [ ] 切换项目 → 侧边栏更新 → Agent 上下文切换
- [ ] 创建会话 → 聊天界面清空
- [ ] 切换会话 → 历史消息加载
- [ ] 跨项目访问 → 权限对话框弹出
- [ ] 允许权限 → 重试成功
- [ ] 重命名项目/会话 → 标题更新
- [ ] 删除项目/会话 → 从列表移除
- [ ] 刷新页面 → 恢复上次的项目/会话

---

## 7. 风险与缓解

### 风险 1：权限检查不一致导致安全漏洞

**缓解措施：**
- 统一使用 `check(path, OperationType)` 接口
- 添加完整的单元测试覆盖
- 代码审查重点检查权限调用

---

### 风险 2：项目切换时状态不一致

**缓解措施：**
- 切换时清空所有旧状态（PermissionManager, Agent）
- 使用原子操作（先准备新状态，再切换）
- 添加状态一致性断言

---

### 风险 3：大量会话时性能下降

**缓解措施：**
- 分页加载（每页 20 条）
- 虚拟滚动（仅渲染可见项）
- 缓存已访问会话

---

### 风险 4：跨浏览器兼容性

**缓解措施：**
- 使用标准 DOM API（避免实验性特性）
- 测试 Chrome/Firefox/Edge
- 渐进增强（基础功能保证可用）

---

## 8. 未来迭代方向

**短期（1-2 周）：**
- [ ] 会话搜索功能
- [ ] 会话导出（Markdown/JSON）
- [ ] 项目图标/颜色标记

**中期（1-2 月）：**
- [ ] 会话标签分类
- [ ] 多标签页会话（同时打开多个会话）
- [ ] 移动端响应式优化

**长期（3+ 月）：**
- [ ] 团队协作（多用户共享项目）
- [ ] 云同步（跨设备访问）
- [ ] 插件系统（自定义工具集成）

---

## 9. 参考资料

### 相关代码文件

- `src/ai_agent/session/manager.py` - SessionManager 实现
- `src/ai_agent/session/project_manager.py` - ProjectManager 实现
- `src/ai_agent/tools/filesystem/permissions.py` - PermissionManager 实现
- `src/ai_agent/api/main.py` - FastAPI 应用入口
- `src/ai_agent/api/routes/chat.py` - 聊天路由
- `src/ai_agent/api/static/chat.html` - 当前前端页面

### 相关文档

- `CLAUDE.md` - 项目开发规范
- `docs/plans/2026-03-20-multi-project-session-management.md` - SessionManager 设计文档

---

## 附录：关键术语

| 术语 | 定义 |
|------|------|
| **项目（Project）** | 一个工作目录上下文，包含代码、配置、Skills 等 |
| **会话（Session）** | 一次完整的对话流程，包含多条消息和工具调用记录 |
| **硬切换** | 切换项目时完全重建 Agent 上下文和权限配置 |
| **PermissionManager** | 管理文件访问权限的组件，支持 allow/deny/ask 三种级别 |
| **OperationType** | 文件操作类型枚举：READ, WRITE, EDIT, LIST, DELETE |
| **ASK 权限** | 需要用户动态确认的权限级别 |

---

**文档结束**
