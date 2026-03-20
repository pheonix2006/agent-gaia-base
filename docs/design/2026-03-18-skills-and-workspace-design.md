# Skills 与 Workspace 系统设计文档

> 版本：1.0
> 日期：2026-03-18
> 状态：设计阶段

## 一、背景与动机

### 1.1 当前痛点

现有 Tools 系统存在以下问题：

| 问题 | 影响 |
|------|------|
| **Token 负担大** | 每个 Tool 需要完整的 description + parameter schema，所有 Tools 在会话开始时全部加载 |
| **扩展成本高** | 新增 Tool 需要编写代码、注册、维护，流程繁琐 |
| **缺乏生态** | 无法复用社区已有能力，需要重复造轮子 |

### 1.2 Skills 方案优势

Skills 是一种**渐进式披露**的指令注入机制：

| 特性 | 说明 |
|------|------|
| **渐进式加载** | 三层加载策略，按需加载，减少 base context 消耗 |
| **社区生态** | 遵循 [agentskills.io](https://agentskills.io) 规范，可直接使用社区 Skills |
| **灵活扩展** | 可为纯 Markdown 指令，也可包含可执行脚本 |
| **无需改代码** | 放入 skills 目录即可生效 |

---

## 二、核心设计原则

### 2.1 渐进式披露（Progressive Disclosure）

遵循 Agent Skills 规范的三层加载策略：

| Tier | 加载内容 | 加载时机 | Token 消耗 |
|------|----------|----------|------------|
| 1. Catalog | name + description | 会话启动时 | ~50-100 tokens/skill |
| 2. Instructions | 完整 SKILL.md 内容 | Skill 被激活时 | <5000 tokens |
| 3. Resources | 脚本、引用文件、资源 | 按需加载 | 视情况而定 |

### 2.2 会话隔离

每个会话应有独立的文件操作空间，同时支持协作场景下的共享需求。

### 2.3 权限分层

不同目录具有不同的访问权限，确保安全性。

### 2.4 兼容社区规范

严格遵循 [agentskills.io](https://agentskills.io/client-implementation/adding-skills-support) 的实现规范，确保与社区 Skills 的兼容性。

---

## 三、目录结构设计

### 3.1 整体结构

```
E:/Project/ai agent/
│
├── skills/                              # Skills 目录（只读，所有会话共享）
│   ├── web-search/
│   │   └── SKILL.md
│   ├── pdf-processing/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── extract.py
│   └── autoglm-websearch/
│       ├── SKILL.md
│       └── websearch.py
│
├── workspace/                           # 共享工作区（可读写，所有会话共享）
│   ├── src/                             # 项目代码
│   ├── docs/                            # 项目文档
│   └── shared_data/                     # 共享数据
│
└── .agent/                              # Agent 运行时数据
    └── sessions/
        ├── session-001/
        │   ├── context.json             # 对话上下文
        │   ├── state.json               # 会话状态
        │   └── workspace/               # 会话私有工作区
        │       ├── temp/                # 临时文件
        │       ├── generated/           # 生成的代码
        │       ├── outputs/             # 输出结果（表格、报告）
        │       └── cache/               # 缓存
        │
        └── session-002/
            └── workspace/
                └── ...
```

### 3.2 目录职责说明

| 目录 | 权限 | 共享范围 | 用途 |
|------|------|----------|------|
| `./skills/` | 只读 | 所有会话 | 存放 Skills 指令与脚本 |
| `./workspace/` | 可读写 | 所有会话 | 项目协作、共享代码/文档 |
| `./.agent/sessions/<id>/workspace/` | 可读写 | 仅该会话 | 会话私有的临时文件、生成代码、输出结果 |

### 3.3 会话 Agent 的访问边界

```
┌──────────────────────────────────────────────────────┐
│               Session-001 的 Agent                    │
├──────────────────────────────────────────────────────┤
│  ✅ ./skills/                      ← 只读，共享       │
│  ✅ ./workspace/                   ← 可读写，共享     │
│  ✅ ./.agent/sessions/session-001/ ← 可读写，私有     │
│  ❌ ./.agent/sessions/session-002/ ← 不可见          │
└──────────────────────────────────────────────────────┘
```

---

## 四、Skills 系统设计

### 4.1 Skill 文件格式

遵循 [SKILL.md 规范](https://agentskills.io/specification)：

```markdown
---
name: skill-name
description: 简短描述，用于 Catalog 显示
compatibility:
  requires:
    - Python 3
---

# Skill 标题

## When to use
描述何时应该使用此 Skill

## Instructions
具体的使用指令...

## Resources
引用的资源文件...
```

### 4.2 Skill 发现机制

**扫描范围**：
- 项目级：`./skills/` 目录

**发现规则**：
- 查找子目录中包含 `SKILL.md` 文件的目录
- 跳过 `.git/`、`node_modules/`、`__pycache__/` 等
- 设置合理的扫描深度限制（如 4-6 层）

**命名冲突处理**：
- 项目级 Skills 优先级最高

### 4.3 Skill 解析机制

解析 SKILL.md 文件的步骤：

1. 识别开头的 `---` 和结尾的 `---` 作为 YAML frontmatter 边界
2. 解析 YAML 提取 `name`（必填）和 `description`（必填）
3. 提取 frontmatter 之后的 Markdown 内容作为 body

**容错处理**：
- YAML 解析失败时尝试修复（如处理未加引号的冒号）
- name 超过 64 字符时警告但仍加载
- description 为空时跳过该 Skill 并记录错误

### 4.4 Skill 目录构建（Tier 1）

会话启动时，构建 Skill Catalog 注入系统提示：

```xml
<skills_catalog>
<skill>
<name>web-search</name>
<description>使用网络搜索获取实时信息</description>
<location>E:/Project/ai agent/skills/web-search/SKILL.md</location>
</skill>
<skill>
<name>pdf-processing</name>
<description>处理 PDF 文件，提取文本和表格</description>
<location>E:/Project/ai agent/skills/pdf-processing/SKILL.md</location>
</skill>
</skills_catalog>
```

**行为指令**：

```
以下 Skills 提供了特定任务的专用指令。
当任务匹配某个 Skill 的描述时，使用 Read 工具加载对应 location 的 SKILL.md 文件。
Skill 中引用的相对路径应基于 Skill 目录（SKILL.md 的父目录）解析。
```

### 4.5 Skill 激活机制（Tier 2）

**激活方式**：

| 方式 | 描述 | 适用场景 |
|------|------|----------|
| 文件读取激活 | 模型使用 Read 工具直接读取 SKILL.md | 简单实现，模型有文件读取能力 |
| 专用工具激活 | 提供 `activate_skill` 工具返回内容 | 需要包装、去重、追踪时 |

**激活后内容**：

可选择：
- 返回完整 SKILL.md（含 frontmatter）
- 仅返回 body（去除 frontmatter）

**结构化包装（可选）**：

```
# [Skill Name]
[SKILL.md body]

---
Skill directory: /path/to/skill
Relative paths in this skill are relative to the skill directory.

Bundled resources:
- scripts/extract.py
- references/spec.md
```

### 4.6 上下文管理（Tier 5）

**保护 Skill 内容**：
- Skill 激活后的内容应标记为受保护
- 上下文压缩时跳过 Skill 内容

**去重激活**：
- 跟踪已激活的 Skills
- 重复激活时跳过重新注入

---

## 五、文件系统工具设计

### 5.1 工具列表

| 工具 | 描述 | 参数 |
|------|------|------|
| `Read` | 读取文件内容 | `path`: 文件路径 |
| `Write` | 创建/覆盖文件 | `path`, `content` |
| `Edit` | 编辑文件（字符串替换） | `path`, `old_string`, `new_string` |
| `List` | 列出目录内容 | `path`: 目录路径 |
| `Glob` | 模式匹配查找文件 | `pattern`: glob 模式 |
| `Grep` | 内容搜索 | `pattern`: 正则表达式 |

### 5.2 权限控制

**三级权限**：

| 权限 | 行为 |
|------|------|
| `allow` | 直接执行，无需确认 |
| `deny` | 拒绝执行 |
| `ask` | 请求用户确认 |

**目录权限矩阵**：

| 目录 | Read | Write | Edit | List |
|------|------|-------|------|------|
| `./skills/` | ✅ allow | ❌ deny | ❌ deny | ✅ allow |
| `./workspace/` | ✅ allow | ✅ allow | ✅ allow | ✅ allow |
| `./.agent/sessions/<自己的>/` | ✅ allow | ✅ allow | ✅ allow | ✅ allow |
| `./.agent/sessions/<其他>/` | ❌ deny | ❌ deny | ❌ deny | ❌ deny |
| `./src/` | ❌ deny | ❌ deny | ❌ deny | ❌ deny |

### 5.3 路径解析

**相对路径解析**：

- 相对路径基于会话私有 workspace 解析
- `./workspace/` 作为共享区域可显式访问
- Skill 中的相对路径基于 Skill 目录解析

**路径规范化**：

- 统一使用正斜杠 `/`
- 防止路径穿越攻击（如 `../../../etc/passwd`）

---

## 六、会话管理设计

### 6.1 会话生命周期

```
创建会话 → 加载 Skills Catalog → 初始化私有 workspace → 运行 → 清理（可选）
```

### 6.2 会话 ID 生成

- 使用时间戳 + 随机后缀：`session-20260318-001a3f`
- 或使用 UUID：`session-550e8400-e29b-41d4-a716-446655440000`

### 6.3 会话数据

| 数据 | 存储位置 | 说明 |
|------|----------|------|
| 对话上下文 | `./.agent/sessions/<id>/context.json` | 对话历史、摘要 |
| 会话状态 | `./.agent/sessions/<id>/state.json` | 已激活的 Skills、变量 |
| 私有文件 | `./.agent/sessions/<id>/workspace/` | 会话产生的所有文件 |

### 6.4 会话清理策略

| 策略 | 触发条件 | 行为 |
|------|----------|------|
| 手动清理 | 用户请求 | 删除整个会话目录 |
| 自动清理 | 会话超过 N 天 | 提示用户或自动删除 |
| 不清理 | - | 保留所有会话数据 |

---

## 七、分阶段实施计划

### 阶段一：Skills 系统基础

**目标**：实现 Skills 的发现、解析、目录构建

**交付物**：
- Skill 发现模块（扫描 `./skills/` 目录）
- SKILL.md 解析器（YAML frontmatter + Markdown body）
- Skill Catalog 构建（注入系统提示）
- 基础测试用例

**不包括**：
- 文件系统工具
- 会话隔离

### 阶段二：文件系统工具

**目标**：实现带权限控制的文件操作工具

**交付物**：
- Read/Write/Edit/List 工具实现
- 权限控制系统（allow/deny/ask）
- 路径解析与安全检查
- 与现有 Tool 系统集成
- 文件工具测试用例

**不包括**：
- 会话隔离
- Skill 激活与文件工具的联动

### 阶段三：会话隔离与集成

**目标**：实现完整的会话隔离，整合 Skills 与文件工具

**交付物**：
- 会话管理模块（创建、销毁、状态持久化）
- 会话私有 workspace
- 权限矩阵完整实现
- Skill 激活机制（文件读取或专用工具）
- 上下文保护与去重
- 端到端测试

**最终效果**：
- 会话启动时自动扫描 Skills 并构建 Catalog
- Agent 可按需激活 Skills 获取指令
- Agent 在私有 workspace 中进行文件操作
- 权限系统保障安全性

---

## 八、参考资料

### 官方规范
- [Agent Skills Specification](https://agentskills.io/specification)
- [Adding Skills Support Guide](https://agentskills.io/client-implementation/adding-skills-support)

### 业界设计参考

| 项目 | 借鉴点 |
|------|--------|
| **Claude Code** | 权限控制语法（allow/deny/ask）、配置优先级、双安全层设计 |
| **Cursor / Windsurf** | Multi-Root Workspaces、会话数据隔离 |
| **OpenAI Code Interpreter** | gVisor 沙箱隔离、会话独立文件空间 |
| **Continue.dev** | Context Providers、工作区配置结构 |

### 相关调研报告
- [How to Sandbox AI Agents - Northflank](https://northflank.com/blog/how-to-sandbox-ai-agents)
- [How to Sandbox LLMs & AI Shell Tools - CodeAnt](https://www.codeant.ai/blogs/agentic-rag-shell-sandboxing)

---

## 九、待讨论事项

- [ ] Skill 激活方式：文件读取 vs 专用工具？
- [ ] 会话 ID 格式：时间戳+随机 vs UUID？
- [ ] 是否支持用户级全局 Skills（`~/.agents/skills/`）？
- [ ] 会话清理策略：自动清理时间阈值？
- [ ] 是否需要 Skill 安装/卸载命令？
