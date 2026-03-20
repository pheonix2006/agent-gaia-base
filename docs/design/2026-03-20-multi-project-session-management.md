# 多项目会话管理系统设计

> 创建日期: 2026-03-20
> 状态: 已确认

## 一、设计目标

### 1.1 核心需求

| 需求 | 描述 |
|------|------|
| 多项目支持 | 支持管理多个独立工程项目，每个项目有独立的路径和配置 |
| 项目级 Skills | 每个项目可以有自己的专属 Skills |
| 全局共享 | 全局 Skills 和配置在所有项目间共享 |
| 会话持久化 | 每个项目支持多个会话，会话可恢复 |
| 历史记录 | 完整保存对话记录和工具调用详情，支持 UI 展示 |
| 权限管理 | 三级权限 (allow/deny/ask)，支持回调确认 |

### 1.2 设计原则

- **非侵入式**: 不在项目目录强制创建 workspace 结构
- **集中管理**: 历史记录和配置集中在全局目录
- **渐进式披露**: Skills 按需加载，优化 Token 消耗
- **可扩展**: 支持后续添加更多功能

---

## 二、目录结构设计

### 2.1 全局目录 (`~/.agents/`)

```
~/.agents/                              # 全局 Agent 根目录
├── config.json                         # 全局配置（LLM、API Key）
├── projects.json                       # 项目注册表
├── skills/                             # 全局共享 Skills
│   ├── code-review/
│   │   └── SKILL.md
│   └── documentation/
│       └── SKILL.md
└── history/                            # 历史记录集中存储
    ├── <project-slug>/                 # 项目标识
    │   ├── <session-id>/               # 会话标识 (YYYYMMDD-NNN)
    │   │   ├── metadata.json           # 会话元信息
    │   │   ├── messages.jsonl          # 对话记录
    │   │   └── traces.jsonl            # 工具调用记录
    │   └── ...
    └── ...
```

### 2.2 项目目录（用户工作区）

```
<path-to-project>/                      # 用户的任意项目目录
├── skills/                             # 项目专属 Skills（可选）
│   └── my-custom-skill/
│       └── SKILL.md
├── .agent/                             # 项目级覆盖配置（可选）
│   └── config.override.json
└── (用户原有项目文件...)
```

### 2.3 设计说明

| 目录 | 权限 | 共享范围 | 用途 |
|------|------|----------|------|
| `~/.agents/skills/` | 只读 | 所有项目 | 全局共享 Skills |
| `~/.agents/config.json` | 读写 | 所有项目 | 全局配置 |
| `~/.agents/history/` | 读写 | 按项目隔离 | 历史记录存储 |
| `<project>/skills/` | 只读 | 仅该项目 | 项目专属 Skills |
| `<project>/.agent/` | 读写 | 仅该项目 | 项目级配置覆盖 |

---

## 三、项目注册表设计

### 3.1 数据结构

```json
// ~/.agents/projects.json
{
  "my-agent": {
    "name": "My Agent Project",
    "path": "E:/Project/ai agent",
    "added_at": "2026-03-20T10:00:00Z",
    "last_opened": "2026-03-20T15:30:00Z",
    "active_session": "20260320-001"
  },
  "web-scraper": {
    "name": "Web Scraper",
    "path": "E:/Project/web-scraper",
    "added_at": "2026-03-18T09:00:00Z",
    "last_opened": "2026-03-19T14:00:00Z",
    "active_session": "20260319-001"
  }
}
```

### 3.2 Project Slug 生成规则

- 用户注册项目时提供友好名称
- 自动生成 slug：小写 + 连字符（如 `My Agent` → `my-agent`）
- slug 作为历史记录目录名，确保可读性
- 路径与 slug 建立双向映射

---

## 四、会话管理设计

### 4.1 会话 ID 格式

```
YYYYMMDD-NNN

示例:
- 20260320-001  (2026年3月20日第1个会话)
- 20260320-002  (2026年3月20日第2个会话)
```

### 4.2 会话元数据

```json
// ~/.agents/history/<project>/<session>/metadata.json
{
  "id": "20260320-001",
  "title": "调试 Skills 系统",
  "created_at": "2026-03-20T10:05:00Z",
  "updated_at": "2026-03-20T15:30:00Z",
  "project_slug": "my-agent",
  "message_count": 42,
  "trace_count": 15
}
```

### 4.3 会话生命周期

```
┌─────────────────────────────────────────────────────┐
│  打开项目                                            │
│     │                                                │
│     ▼                                                │
│  检查 active_session                                │
│     │                                                │
│     ├── 存在 → 加载历史会话                          │
│     │                                                │
│     └── 不存在 → 创建新会话                          │
│               │                                      │
│               ▼                                      │
│         生成 Session ID (YYYYMMDD-NNN)              │
│               │                                      │
│               ▼                                      │
│         创建会话目录和 metadata.json                 │
│               │                                      │
│               ▼                                      │
│         更新 projects.json 的 active_session        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 4.4 会话操作

| 操作 | 描述 |
|------|------|
| 创建会话 | 生成新 Session ID，初始化目录和元数据 |
| 恢复会话 | 加载历史会话的消息和状态 |
| 切换会话 | 保存当前会话，加载目标会话 |
| 追加消息 | 流式写入 messages.jsonl |
| 追加调用记录 | 流式写入 traces.jsonl |

---

## 五、历史记录格式设计

### 5.1 消息记录 (messages.jsonl)

```jsonl
{"role": "user", "content": "帮我分析这个项目", "timestamp": "2026-03-20T10:05:01Z"}
{"role": "assistant", "content": "好的，让我先看看项目结构...", "timestamp": "2026-03-20T10:05:03Z"}
{"role": "tool", "name": "read", "content": "文件内容...", "timestamp": "2026-03-20T10:05:04Z"}
```

### 5.2 工具调用记录 (traces.jsonl)

```jsonl
{"id": "trace-001", "tool": "read", "params": {"path": "./src/main.py"}, "result_status": "success", "duration_ms": 45, "timestamp": "2026-03-20T10:05:04Z"}
{"id": "trace-002", "tool": "web_search", "params": {"query": "Python async"}, "result_status": "success", "duration_ms": 1234, "timestamp": "2026-03-20T10:06:00Z"}
```

### 5.3 字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| id | string | 调用唯一标识 |
| tool | string | 工具名称 |
| params | object | 调用参数 |
| result_status | string | 结果状态 (success/error/timeout) |
| result_preview | string | 结果预览（可选，大结果截断） |
| duration_ms | int | 执行耗时（毫秒） |
| timestamp | string | ISO 8601 时间戳 |

---

## 六、权限系统设计

### 6.1 三级权限模型

| 权限 | 行为 | 适用场景 |
|------|------|----------|
| `allow` | 直接执行，无需确认 | Skills 目录、已信任路径 |
| `deny` | 拒绝执行 | 敏感路径、其他会话目录 |
| `ask` | 请求用户确认 | 项目源码、不确定的操作 |

### 6.2 权限矩阵

| 路径 | Read | Write | Edit | List |
|------|------|-------|------|------|
| `~/.agents/skills/` | allow | deny | deny | allow |
| `~/.agents/history/<自己项目>/` | allow | allow | allow | allow |
| `~/.agents/history/<其他项目>/` | deny | deny | deny | deny |
| `<project>/skills/` | allow | ask | ask | allow |
| `<project>/` (其他) | ask | ask | ask | allow |

### 6.3 权限回调机制

```python
class PermissionCallback(Protocol):
    """权限确认回调协议"""
    async def __call__(
        self,
        path: Path,
        operation: str,  # "read" | "write" | "edit" | "list"
        context: dict    # 额外上下文信息
    ) -> bool:           # True=允许, False=拒绝
        ...
```

**设计说明**：
- `ask` 权限触发回调
- 由上层 UI 决定交互方式（CLI 确认 / Web 弹窗 / 配置预设）
- 回调返回布尔值决定是否执行

---

## 七、Skills 层级设计

### 7.1 加载优先级

```
1. 全局 Skills (~/.agents/skills/)
2. 项目 Skills (<project>/skills/)
3. 合并去重（项目 Skills 可覆盖全局同名 Skills）
```

### 7.2 Catalog 构建

- 会话启动时扫描全局 + 项目 Skills
- 生成合并后的 Catalog 注入 Agent
- 记录已激活 Skills，避免重复加载

---

## 八、配置层级设计

### 8.1 配置优先级

```
1. 默认配置（代码内置）
2. 全局配置 (~/.agents/config.json)
3. 项目配置 (<project>/.agent/config.override.json)
```

### 8.2 全局配置结构

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-..."
  },
  "permissions": {
    "default": "ask",
    "trusted_paths": []
  },
  "ui": {
    "theme": "dark"
  }
}
```

---

## 九、UI 数据接口需求

### 9.1 项目列表

```
GET /api/projects
Response: [
  {
    "slug": "my-agent",
    "name": "My Agent Project",
    "path": "E:/Project/ai agent",
    "last_opened": "2026-03-20T15:30:00Z",
    "session_count": 5
  }
]
```

### 9.2 会话列表

```
GET /api/projects/<slug>/sessions
Response: [
  {
    "id": "20260320-001",
    "title": "调试 Skills 系统",
    "created_at": "2026-03-20T10:05:00Z",
    "message_count": 42
  }
]
```

### 9.3 会话详情

```
GET /api/projects/<slug>/sessions/<session_id>
Response: {
  "metadata": {...},
  "messages": [...],
  "traces": [...]
}
```

---

## 十、待实现模块清单

| 模块 | 职责 | 优先级 |
|------|------|--------|
| `ProjectManager` | 项目注册、查询、路径映射 | P0 |
| `SessionManager` | 会话创建、恢复、切换 | P0 |
| `HistoryStore` | JSONL 格式读写、追加 | P0 |
| `PermissionManager` | 三级权限 + 回调 | P1 |
| `ConfigManager` | 多层配置合并 | P1 |
| `SkillLoader` | 全局 + 项目 Skills 合并 | P1 |

---

## 十一、决策记录

| 决策项 | 选择 | 原因 |
|--------|------|------|
| 历史存储位置 | 全局集中 | 统一管理，UI 加载快 |
| 存储格式 | JSONL | 追加高效，无额外依赖 |
| Project ID | 用户命名 + slug | 友好可读 |
| Session ID | 时间戳+序号 | 有序，日期直观 |
| 会话管理 | 持久+自动恢复 | 符合连续工作习惯 |
| ask 权限交互 | 事件回调 | 灵活支持多种 UI |
