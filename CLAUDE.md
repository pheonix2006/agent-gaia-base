# AI Agent 开发规范

> 基于 SOLID、KISS、DRY、YAGNI 原则的专业开发指南

## 目录

- [代码导航策略](#代码导航策略)
- [测试驱动开发 (TDD)](#测试驱动开发-tdd)
- [类型检查规范](#类型检查规范)
- [代码质量标准](#代码质量标准)
- [项目结构约定](#项目结构约定)

---

## 代码导航策略

### 优先使用 LSP 精准定位

**核心原则：减少全文件读取，使用符号导航**

```bash
# 1. 符号定义查找
serena definitions "<symbol_name>"           # 查找符号定义位置
serena references "<symbol_name>"            # 查找所有引用

# 2. 模块结构浏览
serena symbols "<module_path>"               # 列出模块内所有符号
serena document_symbols                      # 当前文件符号列表

# 3. 类型推断与签名
serena hover "<symbol_name>"                 # 获取类型信息和文档
serena signature "<function_name>"           # 函数签名详情

# 4. 调用层次分析
serena call_hierarchy "<function_name>"      # 调用关系图
serena type_hierarchy "<class_name>"         # 类型继承关系
```

### 读取策略

| 场景 | 推荐方法 |
|------|----------|
| 了解符号定义 | `serena definitions` > Read 局部 |
| 查找函数调用 | `serena references` |
| 理解模块结构 | `serena symbols` + 按需读取 |
| 修改代码 | `serena definitions` 定位 → Edit |
| 新功能开发 | Read 接口文件 → 按需深入 |

### 禁止行为

- ❌ 频繁 `Read` 整个文件"了解结构"
- ❌ 盲目搜索后逐个读取
- ❌ 不使用 LSP 直接猜测位置

---

## 测试驱动开发 (TDD)

### 三层测试架构

```
tests/
├── unit/           # 单元测试：隔离、快速、Mock 外部依赖
├── integration/    # 集成测试：组件交互、Mock LLM API
└── e2e/            # 端到端：真实 API、完整流程
```

### TDD 工作流

```
┌─────────────────────────────────────────────────────────┐
│  1. 🔴 RED    → 编写失败测试（描述期望行为）              │
│  2. 🟢 GREEN  → 最小实现使测试通过                       │
│  3. 🔵 REFACTOR → 优化代码，保持测试通过                  │
│  4. 🔁 REPEAT → 下一功能点                               │
└─────────────────────────────────────────────────────────┘
```

### 测试分类与标记

```python
# pytest markers (pyproject.toml 已配置)
# integration_real: 需要真实 API Key 的测试

# 单元测试示例 - 纯逻辑，无外部依赖
class TestToolRegistry:
    def test_register_tool_success(self):
        """测试工具注册成功场景"""
        registry = ToolRegistry()
        tool = MockTool(name="test")
        registry.register(tool)
        assert registry.get("test") == tool

# 集成测试示例 - Mock LLM 调用
@pytest.mark.asyncio
class TestReactAgentIntegration:
    async def test_agent_processes_query(self, mock_llm_client):
        """测试 Agent 处理查询的集成流程"""
        agent = ReactAgent(llm=mock_llm_client)
        result = await agent.run("test query")
        assert result.status == "completed"

# 真实 API 测试 - 需要环境变量
@pytest.mark.integration_real
@pytest.mark.asyncio
class TestRealAPI:
    async def test_openai_completion(self):
        """真实 OpenAI API 调用验证"""
        client = LLMClient()
        response = await client.chat("Hello")
        assert response.content
```

### 测试命名约定

```python
# 格式: test_<被测方法>_<场景>_<预期结果>
def test_parse_tool_call_valid_json_returns_tool():
    ...

def test_execute_tool_timeout_raises_error():
    ...

# 参数化测试
@pytest.mark.parametrize("input,expected", [
    ("valid input", "expected output"),
    ("edge case", "edge result"),
    pytest.param("invalid", None, marks=pytest.mark.xfail),
])
def test_transform_various_inputs(input, expected):
    ...
```

### 测试覆盖率要求

| 层级 | 覆盖率目标 | 说明 |
|------|-----------|------|
| 单元测试 | ≥ 90% | 核心业务逻辑 |
| 集成测试 | ≥ 70% | 组件交互路径 |
| E2E 测试 | 关键路径 | 用户核心流程 |

### 运行测试

```bash
# 单元测试（快速反馈）
uv run pytest tests/unit -v

# 集成测试（Mock API）
uv run pytest tests/integration -v

# 真实 API 测试（需要 API Key）
uv run pytest -m integration_real -v

# 全量测试 + 覆盖率
uv run pytest --cov=src/ai_agent --cov-report=term-missing

# 类型检查
uv run mypy src/ai_agent
```

---

## 类型检查规范

### Mypy 配置 (已配置严格模式)

```toml
[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true          # 强制类型注解
disallow_incomplete_defs = true       # 禁止部分注解
strict_optional = true                 # 严格 Optional 处理
warn_return_any = true                # 返回值类型警告
```

### 类型注解规范

```python
from typing import TypeAlias, TypeVar, Generic, Callable
from collections.abc import Awaitable

# 类型别名 - 清晰语义
JsonDict: TypeAlias = dict[str, Any]
ToolResult: TypeAlias = str | dict[str, Any]

# 泛型 - 可复用组件
T = TypeVar("T")

class Cache(Generic[T]):
    def get(self, key: str) -> T | None: ...
    def set(self, key: str, value: T) -> None: ...

# 函数签名 - 完整注解
async def process_query(
    query: str,
    *,
    timeout: float = 30.0,
    callbacks: list[Callable[[str], None]] | None = None,
) -> QueryResult:
    """处理用户查询

    Args:
        query: 用户输入的查询字符串
        timeout: 超时时间（秒）
        callbacks: 可选的回调函数列表

    Returns:
        查询结果对象

    Raises:
        TimeoutError: 处理超时时抛出
    """
    ...

# Protocol - 鸭子类型约束
from typing import Protocol

class LLMClientProtocol(Protocol):
    async def chat(self, messages: list[Message]) -> str: ...
    async def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...
```

### 类型检查工作流

```bash
# 开发时持续检查
uv run mypy src/ai_agent --watch

# CI 完整检查
uv run mypy src/ai_agent --strict
```

---

## 代码质量标准

### SOLID 原则应用

```python
# S - 单一职责：一个类只做一件事
class ToolRegistry:
    """仅负责工具注册与查找"""
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool | None: ...

class ToolExecutor:
    """仅负责工具执行"""
    async def execute(self, tool: Tool, params: dict) -> ToolResult: ...

# O - 开闭原则：扩展开放，修改关闭
class BaseAgent(ABC):
    @abstractmethod
    async def run(self, query: str) -> Result: ...

class ReactAgent(BaseAgent):
    async def run(self, query: str) -> Result: ...
    # 扩展行为，不修改基类

# L - 里氏替换：子类可完全替代父类
class MemoryBackend(ABC):
    @abstractmethod
    async def save(self, key: str, value: Any) -> None: ...

class InMemoryBackend(MemoryBackend): ...  # 可替换
class RedisBackend(MemoryBackend): ...      # 可替换

# I - 接口隔离：接口专一
class Readable(Protocol):
    async def read(self, key: str) -> Any: ...

class Writable(Protocol):
    async def write(self, key: str, value: Any) -> None: ...

# 客户端按需实现，不强制实现不需要的方法

# D - 依赖倒置：依赖抽象
class Agent:
    def __init__(
        self,
        llm: LLMClientProtocol,      # 依赖抽象
        memory: MemoryBackend,        # 依赖抽象
    ): ...
```

### KISS / DRY / YAGNI

```python
# KISS - 简洁直观
# ❌ 过度设计
class ToolExecutionStrategyFactory:
    def create_strategy(self, tool_type: str) -> ExecutionStrategy: ...

# ✅ 简单直接
async def execute_tool(tool: Tool, params: dict) -> Result:
    return await tool.run(**params)

# DRY - 消除重复
# ❌ 重复代码
async def handle_user_query(query: str) -> Result:
    validated = validate(query)
    logger.info(f"Processing: {validated}")
    return await agent.run(validated)

async def handle_system_query(query: str) -> Result:
    validated = validate(query)  # 重复
    logger.info(f"Processing: {validated}")  # 重复
    return await agent.run(validated)

# ✅ 抽取公共逻辑
async def process_query(query: str, source: str = "user") -> Result:
    validated = validate(query)
    logger.info(f"Processing [{source}]: {validated}")
    return await agent.run(validated)

# YAGNI - 只做需要的
# ❌ 预留未来功能
class Agent:
    def __init__(self, enable_cache: bool = False, enable_metrics: bool = False,
                 enable_tracing: bool = False, future_feature: bool = False): ...

# ✅ 当前需要什么就做什么
class Agent:
    def __init__(self, llm: LLMClientProtocol): ...
```

### 代码格式与可读性

```python
# 导入顺序：标准库 → 第三方 → 本地
import asyncio
from typing import Any

from langchain_core.messages import BaseMessage

from ai_agent.types import QueryResult
from ai_agent.tools.base import Tool

# 函数长度：≤ 50 行（复杂逻辑抽取子函数）
# 类长度：≤ 300 行（考虑拆分）
# 参数数量：≤ 5 个（超过使用配置对象）

# 配置对象模式
@dataclass
class AgentConfig:
    max_iterations: int = 10
    timeout: float = 30.0
    enable_memory: bool = True

class Agent:
    def __init__(self, config: AgentConfig): ...
```

---

## 项目结构约定

```
src/ai_agent/
├── __init__.py
├── agents/           # Agent 实现
│   ├── base.py       # 抽象基类
│   ├── simple/       # 简单 Agent
│   └── react/        # ReAct Agent
├── api/              # FastAPI 路由
│   ├── main.py       # 应用入口
│   └── routes/       # 路由模块
├── config/           # 配置管理
├── llm/              # LLM 客户端封装
├── memory/           # 记忆/状态管理
├── prompts/          # Prompt 模板
├── tools/            # 工具实现
│   ├── base.py       # 工具基类
│   ├── registry.py   # 工具注册表
│   ├── web/          # Web 相关工具
│   └── media/        # 媒体处理工具
├── trace/            # 追踪/监控
└── types/            # 类型定义
```

### 模块职责

| 模块 | 职责 | 依赖方向 |
|------|------|----------|
| `types/` | 纯数据结构，无业务逻辑 | 无依赖 |
| `config/` | 配置加载与验证 | → types |
| `tools/` | 工具定义与执行 | → types, config |
| `llm/` | LLM 调用封装 | → types, config |
| `memory/` | 状态持久化 | → types |
| `agents/` | Agent 核心逻辑 | → llm, tools, memory, types |
| `api/` | HTTP 接口 | → agents |

### 依赖规则

```
              ┌─────────┐
              │  api/   │
              └────┬────┘
                   │
              ┌────▼────┐
              │ agents/ │
              └────┬────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼───┐    ┌─────▼─────┐   ┌────▼────┐
│  llm  │    │   tools   │   │ memory  │
└───┬───┘    └─────┬─────┘   └────┬────┘
    │              │              │
    └──────────────┼──────────────┘
                   │
              ┌────▼────┐
              │ types/  │
              └─────────┘
```

---

## 快速命令参考

```bash
# 开发流程
uv run pytest tests/unit -v          # 快速单元测试
uv run mypy src/ai_agent             # 类型检查

# 完整验证
uv run pytest --cov=src/ai_agent     # 测试 + 覆盖率
uv run mypy src/ai_agent --strict    # 严格类型检查

# 真实 API 测试
OPENAI_API_KEY=xxx uv run pytest -m integration_real -v

# 运行服务
uv run python main.py
```

---

## 检查清单

### 提交前必检

- [ ] `uv run mypy src/ai_agent` 无错误
- [ ] `uv run pytest tests/unit` 全部通过
- [ ] 新代码有对应测试
- [ ] 遵循 SOLID/KISS/DRY/YAGNI
- [ ] 无重复代码
- [ ] 函数/类有清晰文档

### Code Review 标准

- [ ] 类型注解完整
- [ ] 测试覆盖核心逻辑
- [ ] 无过度设计
- [ ] 依赖方向正确
- [ ] 命名清晰语义化
