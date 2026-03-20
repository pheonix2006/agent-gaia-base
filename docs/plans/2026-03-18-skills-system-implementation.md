# Skills 系统实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现渐进式披露的 Skills 系统，替换现有 Tools 的完整描述注入方式

**Architecture:**
- Skills 作为 Tools 的"使用说明书"，初始只加载 Catalog（name + description），按需加载完整 SKILL.md
- Read 工具作为前置依赖，支持读取 skills 目录
- 遵循 agentskills.io 规范，确保社区兼容性

**Tech Stack:** Python 3.11, Pydantic, pytest, asyncio

---

## 概述

### 核心流程变化

```
传统方式（臃肿）:
系统提示 → 所有 Tools 的完整 description + parameters schema → 模型选择 → 执行

Skills 方式（渐进式）:
系统提示 → Skills Catalog（轻量）→ 模型选择 Skill → Read SKILL.md → 根据说明调用 Tool
```

### 文件结构

```
src/ai_agent/
├── skills/                          # 新增模块
│   ├── __init__.py
│   ├── discovery.py                 # Skill 发现
│   ├── parser.py                    # SKILL.md 解析
│   ├── catalog.py                   # Catalog 构建
│   └── types.py                     # 类型定义
│
├── tools/
│   └── filesystem/                  # 新增：文件系统工具
│       ├── __init__.py
│       ├── read.py                  # Read 工具
│       └── permissions.py           # 权限控制
│
└── ...

skills/                              # Skills 目录（项目根目录）
├── web-search/
│   └── SKILL.md
├── web-content/
│   └── SKILL.md
├── image-analysis/
│   └── SKILL.md
└── audio-parse/
    └── SKILL.md

tests/
├── unit/
│   ├── skills/
│   │   ├── test_discovery.py
│   │   ├── test_parser.py
│   │   └── test_catalog.py
│   └── tools/
│       └── filesystem/
│           └── test_read.py
└── integration/
    └── skills/
        └── test_skills_integration.py
```

---

## Task 1: Skills 类型定义

**Files:**
- Create: `src/ai_agent/skills/__init__.py`
- Create: `src/ai_agent/skills/types.py`
- Create: `tests/unit/skills/__init__.py`
- Create: `tests/unit/skills/test_types.py`

**Step 1: Write the failing test**

```python
# tests/unit/skills/test_types.py
"""Skills 类型定义测试"""

import pytest
from pydantic import ValidationError


class TestSkillMeta:
    """SkillMeta 模型测试"""

    def test_skill_meta_creation(self):
        """测试创建有效的 SkillMeta"""
        from ai_agent.skills.types import SkillMeta

        meta = SkillMeta(
            name="web-search",
            description="搜索互联网获取实时信息",
            location="/path/to/skills/web-search/SKILL.md",
        )

        assert meta.name == "web-search"
        assert meta.description == "搜索互联网获取实时信息"
        assert str(meta.location) == "/path/to/skills/web-search/SKILL.md"

    def test_skill_meta_name_required(self):
        """测试 name 是必填字段"""
        from ai_agent.skills.types import SkillMeta

        with pytest.raises(ValidationError):
            SkillMeta(
                description="描述",
                location="/path/to/SKILL.md",
            )

    def test_skill_meta_description_required(self):
        """测试 description 是必填字段"""
        from ai_agent.skills.types import SkillMeta

        with pytest.raises(ValidationError):
            SkillMeta(
                name="skill-name",
                location="/path/to/SKILL.md",
            )


class TestSkill:
    """Skill 模型测试"""

    def test_skill_creation(self):
        """测试创建完整的 Skill"""
        from ai_agent.skills.types import Skill, SkillMeta

        meta = SkillMeta(
            name="web-search",
            description="搜索互联网",
            location="/skills/web-search/SKILL.md",
        )

        skill = Skill(
            meta=meta,
            body="## 使用说明\n\n这是一个搜索工具...",
        )

        assert skill.meta == meta
        assert "使用说明" in skill.body

    def test_skill_body_can_be_empty(self):
        """测试 body 可以为空"""
        from ai_agent.skills.types import Skill, SkillMeta

        meta = SkillMeta(
            name="minimal-skill",
            description="最小 Skill",
            location="/skills/minimal/SKILL.md",
        )

        skill = Skill(meta=meta, body="")

        assert skill.body == ""


class TestSkillCatalog:
    """SkillCatalog 测试"""

    def test_catalog_creation(self):
        """测试创建 Catalog"""
        from ai_agent.skills.types import SkillCatalog, SkillMeta

        skills = [
            SkillMeta(name="web-search", description="搜索", location="/a/SKILL.md"),
            SkillMeta(name="image-analysis", description="图片分析", location="/b/SKILL.md"),
        ]

        catalog = SkillCatalog(skills=skills)

        assert len(catalog.skills) == 2
        assert catalog.skills[0].name == "web-search"

    def test_catalog_to_xml(self):
        """测试 Catalog 转 XML 格式"""
        from ai_agent.skills.types import SkillCatalog, SkillMeta

        skills = [
            SkillMeta(name="web-search", description="搜索互联网", location="/skills/web-search/SKILL.md"),
        ]

        catalog = SkillCatalog(skills=skills)
        xml = catalog.to_xml()

        assert "<skills_catalog>" in xml
        assert "<skill>" in xml
        assert "<name>web-search</name>" in xml
        assert "<description>搜索互联网</description>" in xml
        assert "<location>" in xml
        assert "</skills_catalog>" in xml

    def test_empty_catalog(self):
        """测试空 Catalog"""
        from ai_agent.skills.types import SkillCatalog

        catalog = SkillCatalog(skills=[])
        xml = catalog.to_xml()

        assert xml == ""
```

**Step 2: Run test to verify it fails**

```bash
cd "E:/Project/ai agent"
uv run pytest tests/unit/skills/test_types.py -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/skills/__init__.py
"""Skills 模块"""

from .types import Skill, SkillCatalog, SkillMeta

__all__ = ["Skill", "SkillCatalog", "SkillMeta"]
```

```python
# src/ai_agent/skills/types.py
"""Skills 类型定义"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    """Skill 元数据（Catalog 中使用）"""

    name: str = Field(description="Skill 名称，必须唯一")
    description: str = Field(description="Skill 简短描述，用于判断何时使用")
    location: Path = Field(description="SKILL.md 文件的绝对路径")

    model_config = {"frozen": True}


class Skill(BaseModel):
    """完整的 Skill（包含 body 内容）"""

    meta: SkillMeta = Field(description="Skill 元数据")
    body: str = Field(description="SKILL.md 的 Markdown 正文（去除 frontmatter 后）")


class SkillCatalog(BaseModel):
    """Skill 目录（注入系统提示用）"""

    skills: list[SkillMeta] = Field(default_factory=list, description="所有可用 Skills")

    def to_xml(self) -> str:
        """转换为 XML 格式，用于注入系统提示"""
        if not self.skills:
            return ""

        lines = ["<skills_catalog>"]
        for skill in self.skills:
            lines.extend([
                "<skill>",
                f"<name>{skill.name}</name>",
                f"<description>{skill.description}</description>",
                f"<location>{skill.location}</location>",
                "</skill>",
            ])
        lines.append("</skills_catalog>")
        return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/skills/test_types.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/skills/__init__.py src/ai_agent/skills/types.py tests/unit/skills/
git commit -m "feat(skills): add Skill types and catalog XML generation"
```

---

## Task 2: SKILL.md 解析器

**Files:**
- Create: `src/ai_agent/skills/parser.py`
- Create: `tests/unit/skills/test_parser.py`

**Step 1: Write the failing test**

```python
# tests/unit/skills/test_parser.py
"""SKILL.md 解析器测试"""

import pytest


class TestSkillParser:
    """SkillParser 测试"""

    def test_parse_valid_skill_md(self):
        """测试解析有效的 SKILL.md"""
        from ai_agent.skills.parser import parse_skill_md
        from ai_agent.skills.types import SkillMeta

        content = """---
name: web-search
description: 搜索互联网获取实时信息
---

# Web Search

## 何时使用
当用户需要搜索最新信息时使用。

## 参数说明
- query: 搜索关键词
"""

        meta, body = parse_skill_md(content, location="/skills/web-search/SKILL.md")

        assert isinstance(meta, SkillMeta)
        assert meta.name == "web-search"
        assert meta.description == "搜索互联网获取实时信息"
        assert "# Web Search" in body

    def test_parse_missing_frontmatter(self):
        """测试缺少 frontmatter 的情况"""
        from ai_agent.skills.parser import parse_skill_md, SkillParseError

        content = """# Web Search
没有 frontmatter
"""

        with pytest.raises(SkillParseError):
            parse_skill_md(content, location="/skills/web-search/SKILL.md")

    def test_parse_missing_name(self):
        """测试缺少 name 字段"""
        from ai_agent.skills.parser import parse_skill_md, SkillParseError

        content = """---
description: 只有描述
---
Body content
"""

        with pytest.raises(SkillParseError):
            parse_skill_md(content, location="/skills/test/SKILL.md")

    def test_parse_missing_description(self):
        """测试缺少 description 字段"""
        from ai_agent.skills.parser import parse_skill_md, SkillParseError

        content = """---
name: test-skill
---
Body content
"""

        with pytest.raises(SkillParseError):
            parse_skill_md(content, location="/skills/test/SKILL.md")

    def test_parse_malformed_yaml_with_colon(self):
        """测试处理包含冒号的无效 YAML（容错处理）"""
        from ai_agent.skills.parser import parse_skill_md

        # 这种格式在技术上可能是无效 YAML，但我们要尽量处理
        content = '''---
name: test-skill
description: |
  这是一个描述：包含冒号
---
Body
'''

        meta, body = parse_skill_md(content, location="/skills/test/SKILL.md")

        assert meta.name == "test-skill"
        assert "冒号" in meta.description

    def test_parse_empty_body(self):
        """测试 body 为空的情况"""
        from ai_agent.skills.parser import parse_skill_md

        content = """---
name: minimal
description: 最小 skill
---
"""

        meta, body = parse_skill_md(content, location="/skills/minimal/SKILL.md")

        assert meta.name == "minimal"
        assert body == ""

    def test_parse_with_extra_frontmatter_fields(self):
        """测试解析包含额外字段的 frontmatter"""
        from ai_agent.skills.parser import parse_skill_md

        content = """---
name: advanced-skill
description: 高级 skill
version: "1.0"
author: test
compatibility:
  requires:
    - Python 3
---

## 使用说明
"""

        meta, body = parse_skill_md(content, location="/skills/advanced/SKILL.md")

        assert meta.name == "advanced-skill"
        assert "使用说明" in body
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/skills/test_parser.py -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/skills/parser.py
"""SKILL.md 解析器"""

import re
from pathlib import Path

import yaml

from ai_agent.skills.types import SkillMeta


class SkillParseError(Exception):
    """SKILL.md 解析错误"""
    pass


def parse_skill_md(content: str, location: str | Path) -> tuple[SkillMeta, str]:
    """解析 SKILL.md 文件内容

    Args:
        content: SKILL.md 文件的完整内容
        location: SKILL.md 文件的路径（用于错误提示）

    Returns:
        tuple[SkillMeta, str]: (元数据, Markdown 正文)

    Raises:
        SkillParseError: 解析失败时抛出
    """
    location = Path(location)

    # 匹配 YAML frontmatter
    pattern = r"^---\s*\n(.*?)\n---\s*\n?(.*)$"
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        raise SkillParseError(
            f"SKILL.md 格式错误：缺少 YAML frontmatter (--- delimiters)\n"
            f"文件位置: {location}"
        )

    yaml_content = match.group(1)
    body = match.group(2).strip()

    try:
        frontmatter = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise SkillParseError(
            f"SKILL.md YAML 解析错误: {e}\n"
            f"文件位置: {location}"
        )

    if not isinstance(frontmatter, dict):
        raise SkillParseError(
            f"SKILL.md frontmatter 必须是 YAML 对象\n"
            f"文件位置: {location}"
        )

    # 验证必填字段
    name = frontmatter.get("name")
    description = frontmatter.get("description")

    if not name:
        raise SkillParseError(
            f"SKILL.md 缺少必填字段 'name'\n"
            f"文件位置: {location}"
        )

    if not description:
        raise SkillParseError(
            f"SKILL.md 缺少必填字段 'description'\n"
            f"文件位置: {location}"
        )

    meta = SkillMeta(
        name=str(name),
        description=str(description),
        location=location,
    )

    return meta, body
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/skills/test_parser.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/skills/parser.py tests/unit/skills/test_parser.py
git commit -m "feat(skills): add SKILL.md parser with YAML frontmatter support"
```

---

## Task 3: Skill 发现器

**Files:**
- Create: `src/ai_agent/skills/discovery.py`
- Create: `tests/unit/skills/test_discovery.py`
- Create: `skills/.gitkeep` (确保目录存在)

**Step 1: Write the failing test**

```python
# tests/unit/skills/test_discovery.py
"""Skill 发现器测试"""

import tempfile
from pathlib import Path

import pytest


class TestSkillDiscovery:
    """SkillDiscovery 测试"""

    def test_discover_skills_from_directory(self):
        """测试从目录发现 Skills"""
        from ai_agent.skills.discovery import discover_skills

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # 创建有效的 skill
            skill_dir = skills_dir / "web-search"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("""---
name: web-search
description: 搜索互联网
---
Body content
""")

            skills = discover_skills(skills_dir)

            assert len(skills) == 1
            assert skills[0].name == "web-search"

    def test_discover_multiple_skills(self):
        """测试发现多个 Skills"""
        from ai_agent.skills.discovery import discover_skills

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # 创建多个 skills
            for name in ["web-search", "image-analysis", "audio-parse"]:
                skill_dir = skills_dir / name
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
description: {name} 描述
---
Body
""")

            skills = discover_skills(skills_dir)

            assert len(skills) == 3
            names = [s.name for s in skills]
            assert "web-search" in names
            assert "image-analysis" in names

    def test_skip_directories_without_skill_md(self):
        """测试跳过没有 SKILL.md 的目录"""
        from ai_agent.skills.discovery import discover_skills

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # 有效 skill
            valid_dir = skills_dir / "valid-skill"
            valid_dir.mkdir()
            (valid_dir / "SKILL.md").write_text("""---
name: valid-skill
description: 有效
---
Body
""")

            # 无效目录（无 SKILL.md）
            invalid_dir = skills_dir / "invalid-dir"
            invalid_dir.mkdir()
            (invalid_dir / "README.md").write_text("No skill here")

            # 普通文件（不是目录）
            (skills_dir / "some-file.txt").write_text("Not a directory")

            skills = discover_skills(skills_dir)

            assert len(skills) == 1
            assert skills[0].name == "valid-skill"

    def test_nonexistent_directory_returns_empty(self):
        """测试目录不存在时返回空列表"""
        from ai_agent.skills.discovery import discover_skills

        skills = discover_skills(Path("/nonexistent/path/12345"))
        assert skills == []

    def test_skip_ignored_directories(self):
        """测试跳过被忽略的目录"""
        from ai_agent.skills.discovery import discover_skills

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # 创建 .git 目录（应该被跳过）
            git_dir = skills_dir / ".git"
            git_dir.mkdir()
            (git_dir / "SKILL.md").write_text("""---
name: git-skill
description: 不应该被发现
---
""")

            # 创建 __pycache__ 目录（应该被跳过）
            pycache_dir = skills_dir / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "SKILL.md").write_text("""---
name: pycache-skill
description: 不应该被发现
---
""")

            # 有效 skill
            valid_dir = skills_dir / "valid-skill"
            valid_dir.mkdir()
            (valid_dir / "SKILL.md").write_text("""---
name: valid-skill
description: 有效
---
""")

            skills = discover_skills(skills_dir)

            assert len(skills) == 1
            assert skills[0].name == "valid-skill"


class TestSkillLoading:
    """Skill 加载测试"""

    def test_load_skill_from_path(self):
        """测试从路径加载完整 Skill"""
        from ai_agent.skills.discovery import load_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: test-skill
description: 测试技能
---
# 使用说明
这是正文内容。
""")

            skill = load_skill(skill_md)

            assert skill.meta.name == "test-skill"
            assert "使用说明" in skill.body

    def test_load_skill_with_scripts(self):
        """测试加载包含脚本的 Skill"""
        from ai_agent.skills.discovery import load_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "scripted-skill"
            skill_dir.mkdir()

            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: scripted-skill
description: 带脚本的技能
---
# 说明
使用 scripts/run.py 执行。
""")

            # 创建脚本文件
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "run.py").write_text("print('hello')")

            skill = load_skill(skill_md)

            assert skill.meta.name == "scripted-skill"
            # skill_dir 属性应该指向 Skill 目录
            assert skill.meta.location.parent.name == "scripted-skill"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/skills/test_discovery.py -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/skills/discovery.py
"""Skill 发现器"""

import logging
from pathlib import Path

from ai_agent.skills.parser import parse_skill_md, SkillParseError
from ai_agent.skills.types import Skill, SkillMeta

logger = logging.getLogger(__name__)

# 要跳过的目录名
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}


def discover_skills(skills_dir: Path) -> list[SkillMeta]:
    """从目录发现所有 Skills

    扫描 skills_dir 下的子目录，查找包含 SKILL.md 的目录。

    Args:
        skills_dir: Skills 根目录

    Returns:
        list[SkillMeta]: 发现的 Skill 元数据列表
    """
    skills_dir = Path(skills_dir)

    if not skills_dir.exists():
        logger.debug(f"Skills 目录不存在: {skills_dir}")
        return []

    if not skills_dir.is_dir():
        logger.warning(f"Skills 路径不是目录: {skills_dir}")
        return []

    discovered: list[SkillMeta] = []

    for item in skills_dir.iterdir():
        # 跳过非目录
        if not item.is_dir():
            continue

        # 跳过忽略的目录
        if item.name in IGNORED_DIRS:
            continue

        # 查找 SKILL.md
        skill_md = item / "SKILL.md"
        if not skill_md.exists():
            logger.debug(f"跳过目录（无 SKILL.md）: {item}")
            continue

        # 解析 SKILL.md
        try:
            content = skill_md.read_text(encoding="utf-8")
            meta, _ = parse_skill_md(content, location=skill_md)
            discovered.append(meta)
            logger.info(f"发现 Skill: {meta.name}")
        except SkillParseError as e:
            logger.warning(f"Skill 解析失败，跳过: {e}")
        except Exception as e:
            logger.error(f"读取 SKILL.md 失败: {skill_md}, 错误: {e}")

    return discovered


def load_skill(skill_md_path: Path) -> Skill:
    """加载完整的 Skill

    Args:
        skill_md_path: SKILL.md 文件的路径

    Returns:
        Skill: 完整的 Skill 对象

    Raises:
        SkillParseError: 解析失败时抛出
    """
    skill_md_path = Path(skill_md_path)

    if not skill_md_path.exists():
        raise SkillParseError(f"SKILL.md 文件不存在: {skill_md_path}")

    content = skill_md_path.read_text(encoding="utf-8")
    meta, body = parse_skill_md(content, location=skill_md_path)

    return Skill(meta=meta, body=body)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/skills/test_discovery.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/skills/discovery.py tests/unit/skills/test_discovery.py skills/.gitkeep
git commit -m "feat(skills): add skill discovery with directory scanning"
```

---

## Task 4: Skill Catalog 构建器

**Files:**
- Create: `src/ai_agent/skills/catalog.py`
- Create: `tests/unit/skills/test_catalog.py`

**Step 1: Write the failing test**

```python
# tests/unit/skills/test_catalog.py
"""Skill Catalog 构建器测试"""

import tempfile
from pathlib import Path

import pytest


class TestCatalogBuilder:
    """CatalogBuilder 测试"""

    def test_build_catalog_from_skills(self):
        """测试从 Skills 构建 Catalog"""
        from ai_agent.skills.catalog import build_catalog
        from ai_agent.skills.types import SkillMeta

        skills = [
            SkillMeta(
                name="web-search",
                description="搜索互联网",
                location=Path("/skills/web-search/SKILL.md"),
            ),
            SkillMeta(
                name="image-analysis",
                description="分析图片",
                location=Path("/skills/image-analysis/SKILL.md"),
            ),
        ]

        catalog = build_catalog(skills)

        assert len(catalog.skills) == 2
        xml = catalog.to_xml()
        assert "<skills_catalog>" in xml
        assert "web-search" in xml
        assert "image-analysis" in xml

    def test_build_catalog_empty(self):
        """测试空 Catalog"""
        from ai_agent.skills.catalog import build_catalog

        catalog = build_catalog([])

        assert len(catalog.skills) == 0
        assert catalog.to_xml() == ""

    def test_get_catalog_with_instructions(self):
        """测试获取带行为指令的 Catalog"""
        from ai_agent.skills.catalog import get_catalog_prompt
        from ai_agent.skills.types import SkillCatalog, SkillMeta

        catalog = SkillCatalog(skills=[
            SkillMeta(
                name="test-skill",
                description="测试",
                location=Path("/skills/test/SKILL.md"),
            ),
        ])

        prompt = get_catalog_prompt(catalog)

        assert "<skills_catalog>" in prompt
        assert "test-skill" in prompt
        assert "Read" in prompt or "read" in prompt
        assert "SKILL.md" in prompt

    def test_build_catalog_from_directory(self):
        """测试从目录直接构建 Catalog"""
        from ai_agent.skills.catalog import build_catalog_from_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # 创建测试 Skills
            for name in ["skill-a", "skill-b"]:
                skill_dir = skills_dir / name
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
description: {name} 描述
---
Body
""")

            catalog = build_catalog_from_directory(skills_dir)

            assert len(catalog.skills) == 2
            names = [s.name for s in catalog.skills]
            assert "skill-a" in names
            assert "skill-b" in names


class TestCatalogInjection:
    """Catalog 注入测试"""

    def test_catalog_injection_format(self):
        """测试 Catalog 注入格式符合规范"""
        from ai_agent.skills.catalog import get_catalog_prompt
        from ai_agent.skills.types import SkillCatalog, SkillMeta

        catalog = SkillCatalog(skills=[
            SkillMeta(
                name="web-search",
                description="搜索互联网获取实时信息",
                location=Path("/path/to/skills/web-search/SKILL.md"),
            ),
        ])

        prompt = get_catalog_prompt(catalog)

        # 验证 XML 结构
        assert "<skills_catalog>" in prompt
        assert "</skills_catalog>" in prompt
        assert "<skill>" in prompt
        assert "</skill>" in prompt
        assert "<name>web-search</name>" in prompt
        assert "<description>搜索互联网获取实时信息</description>" in prompt
        assert "<location>" in prompt

        # 验证行为指令
        assert "skill" in prompt.lower()

    def test_catalog_xml_escaping(self):
        """测试 XML 特殊字符转义"""
        from ai_agent.skills.types import SkillCatalog, SkillMeta

        catalog = SkillCatalog(skills=[
            SkillMeta(
                name="test-skill",
                description="描述包含 <特殊> & 字符",
                location=Path("/skills/test/SKILL.md"),
            ),
        ])

        xml = catalog.to_xml()

        # XML 特殊字符应该被正确处理（或者不引起解析错误）
        assert "test-skill" in xml
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/skills/test_catalog.py -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/skills/catalog.py
"""Skill Catalog 构建器"""

from pathlib import Path

from ai_agent.skills.discovery import discover_skills
from ai_agent.skills.types import SkillCatalog, SkillMeta


# Catalog 行为指令模板
CATALOG_INSTRUCTIONS = """以下 Skills 提供了特定任务的专用指令。

当任务匹配某个 Skill 的描述时，使用 Read 工具加载对应 location 的 SKILL.md 文件。
Skill 中引用的相对路径应基于 Skill 目录（SKILL.md 的父目录）解析。

{catalog_xml}"""


def build_catalog(skills: list[SkillMeta]) -> SkillCatalog:
    """从 Skill 列表构建 Catalog

    Args:
        skills: Skill 元数据列表

    Returns:
        SkillCatalog: 构建好的 Catalog
    """
    return SkillCatalog(skills=skills)


def build_catalog_from_directory(skills_dir: Path) -> SkillCatalog:
    """从目录直接构建 Catalog

    Args:
        skills_dir: Skills 根目录

    Returns:
        SkillCatalog: 构建好的 Catalog
    """
    skills = discover_skills(Path(skills_dir))
    return build_catalog(skills)


def get_catalog_prompt(catalog: SkillCatalog) -> str:
    """获取带行为指令的 Catalog 提示词

    Args:
        catalog: Skill Catalog

    Returns:
        str: 完整的 Catalog 提示词（包含行为指令）
    """
    catalog_xml = catalog.to_xml()

    if not catalog_xml:
        return ""

    return CATALOG_INSTRUCTIONS.format(catalog_xml=catalog_xml)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/skills/test_catalog.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/skills/catalog.py tests/unit/skills/test_catalog.py
git commit -m "feat(skills): add catalog builder with XML generation"
```

---

## Task 5: Read 工具（最小实现）

**Files:**
- Create: `src/ai_agent/tools/filesystem/__init__.py`
- Create: `src/ai_agent/tools/filesystem/read.py`
- Create: `src/ai_agent/tools/filesystem/permissions.py`
- Create: `tests/unit/tools/filesystem/__init__.py`
- Create: `tests/unit/tools/filesystem/test_read.py`

**Step 1: Write the failing test**

```python
# tests/unit/tools/filesystem/test_read.py
"""Read 工具测试"""

import tempfile
from pathlib import Path

import pytest


class TestReadTool:
    """Read 工具测试"""

    def test_read_file_success(self):
        """测试成功读取文件"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Content\n\nHello World")
            f.flush()

            tool = ReadTool()
            result = tool.run(ReadParams(path=f.name))

            assert result.success is True
            assert "# Test Content" in result.data

    def test_read_file_not_found(self):
        """测试文件不存在"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        tool = ReadTool()
        result = tool.run(ReadParams(path="/nonexistent/file/12345.md"))

        assert result.success is False
        assert "不存在" in result.error or "not found" in result.error.lower()

    def test_read_with_line_limit(self):
        """测试限制读取行数"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for i in range(100):
                f.write(f"Line {i}\n")
            f.flush()

            tool = ReadTool()
            result = tool.run(ReadParams(path=f.name, limit=10))

            assert result.success is True
            lines = result.data.split("\n")
            # 去掉可能的空行
            non_empty_lines = [l for l in lines if l.strip()]
            assert len(non_empty_lines) <= 10

    def test_read_with_offset(self):
        """测试从指定偏移读取"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for i in range(10):
                f.write(f"Line {i}\n")
            f.flush()

            tool = ReadTool()
            result = tool.run(ReadParams(path=f.name, offset=5))

            assert result.success is True
            assert "Line 5" in result.data
            assert "Line 0" not in result.data

    def test_read_skill_md_file(self):
        """测试读取 SKILL.md 文件（核心场景）"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: test-skill
description: 测试技能
---
# 使用说明
这是正文内容。
""")

            tool = ReadTool()
            result = tool.run(ReadParams(path=str(skill_md)))

            assert result.success is True
            assert "name: test-skill" in result.data
            assert "使用说明" in result.data


class TestReadToolPermissions:
    """Read 工具权限测试"""

    def test_read_allowed_path(self):
        """测试读取允许的路径"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams
        from ai_agent.tools.filesystem.permissions import PermissionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_dir = Path(tmpdir)
            test_file = allowed_dir / "test.md"
            test_file.write_text("content")

            # 设置权限：允许读取该目录
            pm = PermissionManager()
            pm.allow_path(allowed_dir)

            tool = ReadTool(permission_manager=pm)
            result = tool.run(ReadParams(path=str(test_file)))

            assert result.success is True

    def test_read_denied_path(self):
        """测试读取禁止的路径"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams
        from ai_agent.tools.filesystem.permissions import PermissionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            denied_dir = Path(tmpdir) / "secret"
            denied_dir.mkdir()
            secret_file = denied_dir / "secret.md"
            secret_file.write_text("secret content")

            # 设置权限：禁止读取该目录
            pm = PermissionManager()
            pm.deny_path(denied_dir)

            tool = ReadTool(permission_manager=pm)
            result = tool.run(ReadParams(path=str(secret_file)))

            assert result.success is False
            assert "权限" in result.error or "denied" in result.error.lower()


class TestReadToolIntegration:
    """Read 工具与 LangChain 集成测试"""

    def test_to_langchain_tool(self):
        """测试转换为 LangChain 工具"""
        from ai_agent.tools.filesystem.read import ReadTool
        from langchain_core.tools import StructuredTool

        tool = ReadTool()
        langchain_tool = tool.to_langchain_tool()

        assert isinstance(langchain_tool, StructuredTool)
        assert langchain_tool.name == "read"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/tools/filesystem/test_read.py -v
```
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/tools/filesystem/__init__.py
"""文件系统工具模块"""

from .read import ReadTool, ReadParams
from .permissions import PermissionManager

__all__ = ["ReadTool", "ReadParams", "PermissionManager"]
```

```python
# src/ai_agent/tools/filesystem/permissions.py
"""文件系统权限管理"""

from pathlib import Path
from typing import Any


class PermissionManager:
    """权限管理器

    管理文件系统访问权限，支持 allow/deny 列表。
    """

    def __init__(self) -> None:
        self._allowed_paths: list[Path] = []
        self._denied_paths: list[Path] = []

    def allow_path(self, path: Path | str) -> None:
        """添加允许访问的路径"""
        path = Path(path).resolve()
        if path not in self._allowed_paths:
            self._allowed_paths.append(path)

    def deny_path(self, path: Path | str) -> None:
        """添加禁止访问的路径"""
        path = Path(path).resolve()
        if path not in self._denied_paths:
            self._denied_paths.append(path)

    def is_allowed(self, path: Path | str) -> bool:
        """检查路径是否允许访问

        优先级：deny > allow

        Args:
            path: 要检查的路径

        Returns:
            bool: 是否允许访问
        """
        path = Path(path).resolve()

        # 检查是否在 deny 列表中
        for denied in self._denied_paths:
            try:
                path.relative_to(denied)
                return False
            except ValueError:
                pass

        # 如果没有设置 allow 列表，默认允许
        if not self._allowed_paths:
            return True

        # 检查是否在 allow 列表中
        for allowed in self._allowed_paths:
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                pass

        return False
```

```python
# src/ai_agent/tools/filesystem/read.py
"""Read 工具实现"""

import time
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult, AnyDict
from ai_agent.tools.filesystem.permissions import PermissionManager


class ReadParams(BaseModel):
    """Read 工具参数"""

    path: str = Field(description="要读取的文件路径")
    offset: int = Field(default=0, ge=0, description="从第几行开始读取（0 表示从头开始）")
    limit: int = Field(default=2000, ge=1, le=10000, description="最多读取多少行")


class ReadTool(BaseAgentTool[ReadParams, str]):
    """文件读取工具

    支持读取文本文件，可选行偏移和限制。
    """

    def __init__(
        self,
        permission_manager: Optional[PermissionManager] = None,
        default_encoding: str = "utf-8",
    ) -> None:
        self._permission_manager = permission_manager
        self._default_encoding = default_encoding

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return """读取文件内容。

参数：
- path: 文件路径（绝对路径或相对路径）
- offset: 从第几行开始读取，默认 0
- limit: 最多读取多少行，默认 2000

返回文件内容，带行号前缀。"""

    @property
    def params_schema(self) -> type[ReadParams]:
        return ReadParams

    def run(self, params: ReadParams) -> ToolResult[str]:
        """执行文件读取"""
        start_time = time.time()

        try:
            file_path = Path(params.path).expanduser().resolve()

            # 检查文件是否存在
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    data="",
                    error=f"文件不存在: {params.path}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 检查是否为文件
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    data="",
                    error=f"路径不是文件: {params.path}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 权限检查
            if self._permission_manager and not self._permission_manager.is_allowed(file_path):
                return ToolResult(
                    success=False,
                    data="",
                    error=f"权限不足：无法访问 {params.path}",
                    metrics={"elapsed_time": start_time - start_time},
                )

            # 读取文件
            content = file_path.read_text(encoding=self._default_encoding)
            lines = content.splitlines()

            # 应用偏移和限制
            start = params.offset
            end = start + params.limit
            selected_lines = lines[start:end]

            # 添加行号前缀
            numbered_lines = []
            for i, line in enumerate(selected_lines, start=start + 1):
                numbered_lines.append(f"{i:6}\t{line}")

            result_content = "\n".join(numbered_lines)

            return ToolResult(
                success=True,
                data=result_content,
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "total_lines": len(lines),
                    "returned_lines": len(selected_lines),
                },
            )

        except UnicodeDecodeError as e:
            return ToolResult(
                success=False,
                data="",
                error=f"文件编码错误: {e}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except PermissionError as e:
            return ToolResult(
                success=False,
                data="",
                error=f"权限错误: {e}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data="",
                error=f"读取失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/tools/filesystem/test_read.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/tools/filesystem/ tests/unit/tools/filesystem/
git commit -m "feat(tools): add Read tool with permission management"
```

---

## Task 6: 为现有 Tools 创建 Skills

**Files:**
- Create: `skills/web-search/SKILL.md`
- Create: `skills/web-content/SKILL.md`
- Create: `skills/image-analysis/SKILL.md`
- Create: `skills/audio-parse/SKILL.md`

**Step 1: 创建 web-search Skill**

```markdown
# skills/web-search/SKILL.md
---
name: web-search
description: 搜索互联网获取实时信息、新闻、技术文档等。支持中英文搜索。
---

# Web Search

使用 Web Search 工具搜索互联网获取信息。

## 何时使用

- 用户询问最新新闻、事件、动态
- 需要获取实时数据、统计信息
- 查找技术文档、教程、解决方案
- 验证事实性信息

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ✅ | - | 搜索关键词，不超过 70 字符 |
| count | int | ❌ | 10 | 返回结果数量，1-50 |
| search_recency_filter | string | ❌ | noLimit | 时间范围过滤 |

**search_recency_filter 可选值：**
- `oneDay` - 最近一天
- `oneWeek` - 最近一周
- `oneMonth` - 最近一个月
- `oneYear` - 最近一年
- `noLimit` - 不限制

## 使用示例

```json
{
  "action": "web_search",
  "params": {
    "query": "Claude 3.5 最新功能",
    "count": 5,
    "search_recency_filter": "oneWeek"
  }
}
```

## 返回结果

返回搜索结果列表，每项包含：
- `title`: 页面标题
- `content`: 摘要内容
- `link`: 页面链接

## 注意事项

- 中文搜索效果更佳
- 复杂查询建议拆分为多个简单搜索
- 如需获取完整网页内容，配合 web-content Skill 使用
```

**Step 2: 创建 web-content Skill**

```markdown
# skills/web-content/SKILL.md
---
name: web-content
description: 提取网页内容并回答问题。支持任意 http/https URL。
---

# Web Content

抓取网页内容并基于内容回答问题。

## 何时使用

- 需要获取某个网页的完整内容
- 基于特定网页回答问题
- 提取网页中的特定信息

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✅ | 网页 URL（仅支持 http/https） |
| query | string | ✅ | 针对网页内容的问题或指令 |

## 使用示例

```json
{
  "action": "web_content",
  "params": {
    "url": "https://docs.anthropic.com/claude/docs",
    "query": "Claude 支持哪些模型？各自的特点是什么？"
  }
}
```

## 返回结果

返回包含以下字段的对象：
- `url`: 请求的 URL
- `answer`: 基于网页内容的回答
- `source_preview`: 网页内容预览（前 2000 字符）

## 注意事项

- 仅支持 http/https 协议
- 部分网站可能无法访问
- 长文本会自动分块处理
```

**Step 3: 创建 image-analysis Skill**

```markdown
# skills/image-analysis/SKILL.md
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
| image_path | string | ✅ | 图片路径（本地文件或 URL） |
| query | string | ✅ | 关于图像的问题或分析指令 |

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

## 注意事项

- 本地文件需要存在且可读
- URL 需要可公开访问
- 大图片可能需要较长处理时间
```

**Step 4: 创建 audio-parse Skill**

```markdown
# skills/audio-parse/SKILL.md
---
name: audio-parse
description: 解析音频文件，转录为文字。支持多种音频格式。
---

# Audio Parse

将音频文件转录为文字。

## 何时使用

- 转录录音、会议记录
- 提取音频中的对话内容
- 处理语音消息

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| audio_path | string | ✅ | 音频文件路径（本地文件） |

## 支持的音频格式

- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- FLAC (.flac)
- OGG (.ogg)

## 使用示例

```json
{
  "action": "audio_parse",
  "params": {
    "audio_path": "/path/to/recording.mp3"
  }
}
```

## 返回结果

返回转录的文字内容。

## 注意事项

- 仅支持本地文件
- 音频质量影响转录准确度
- 长音频可能需要较长处理时间
```

**Step 5: Commit**

```bash
git add skills/
git commit -m "feat(skills): add SKILL.md for existing tools"
```

---

## Task 7: 集成测试

**Files:**
- Create: `tests/integration/skills/__init__.py`
- Create: `tests/integration/skills/test_skills_integration.py`

**Step 1: Write the failing test**

```python
# tests/integration/skills/test_skills_integration.py
"""Skills 系统集成测试"""

import tempfile
from pathlib import Path

import pytest


class TestSkillsIntegration:
    """Skills 系统集成测试"""

    def test_full_skills_workflow(self):
        """测试完整的 Skills 工作流"""
        from ai_agent.skills.catalog import build_catalog_from_directory, get_catalog_prompt

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # 创建测试 Skills
            for name, desc in [("web-search", "搜索互联网"), ("image-analysis", "分析图片")]:
                skill_dir = skills_dir / name
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
description: {desc}
---
# {name}

使用说明...
""")

            # 1. 构建 Catalog
            catalog = build_catalog_from_directory(skills_dir)
            assert len(catalog.skills) == 2

            # 2. 获取提示词
            prompt = get_catalog_prompt(catalog)
            assert "web-search" in prompt
            assert "image-analysis" in prompt
            assert "<skills_catalog>" in prompt

    def test_skill_loading_and_parsing(self):
        """测试 Skill 加载和解析"""
        from ai_agent.skills.discovery import load_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: test-skill
description: 测试技能
compatibility:
  requires:
    - Python 3
---

# 使用说明

这是一个测试技能。

## 参数

- param1: 参数1
- param2: 参数2
""")

            skill = load_skill(skill_md)

            assert skill.meta.name == "test-skill"
            assert skill.meta.description == "测试技能"
            assert "使用说明" in skill.body
            assert "参数" in skill.body

    def test_read_tool_with_skill_file(self):
        """测试 Read 工具读取 SKILL.md"""
        from ai_agent.tools.filesystem.read import ReadTool, ReadParams

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "web-search"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: web-search
description: 搜索互联网
---
# Web Search
使用说明...
""")

            tool = ReadTool()
            result = tool.run(ReadParams(path=str(skill_md)))

            assert result.success is True
            assert "name: web-search" in result.data
            assert "Web Search" in result.data


class TestCatalogWithRealSkills:
    """使用真实 Skills 目录的测试"""

    def test_load_project_skills(self):
        """测试加载项目 Skills 目录"""
        from ai_agent.skills.catalog import build_catalog_from_directory

        # 使用项目根目录下的 skills 目录
        project_root = Path(__file__).parent.parent.parent.parent
        skills_dir = project_root / "skills"

        if not skills_dir.exists():
            pytest.skip("项目 skills 目录不存在")

        catalog = build_catalog_from_directory(skills_dir)

        # 应该至少有我们创建的 4 个 Skills
        assert len(catalog.skills) >= 4

        names = [s.name for s in catalog.skills]
        assert "web-search" in names
        assert "web-content" in names
        assert "image-analysis" in names
        assert "audio-parse" in names
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/skills/test_skills_integration.py -v
```
Expected: Some tests may fail if skills don't exist yet

**Step 3: Run all tests**

```bash
uv run pytest tests/ -v
```

**Step 4: Commit**

```bash
git add tests/integration/skills/
git commit -m "test(skills): add integration tests for skills system"
```

---

## Task 8: 更新模块导出和文档

**Files:**
- Modify: `src/ai_agent/tools/__init__.py`
- Modify: `src/ai_agent/__init__.py`

**Step 1: 更新 tools 模块导出**

```python
# src/ai_agent/tools/__init__.py
"""工具模块"""

from .base import BaseAgentTool, ToolResult
from .registry import ToolRegistry
from .web import GoogleSearchTool, WebContentTool, ZhipuWebSearchTool
from .media import ImageAnalysisTool, AudioParseTool
from .filesystem import ReadTool, ReadParams, PermissionManager

__all__ = [
    "BaseAgentTool",
    "ToolResult",
    "ToolRegistry",
    "WebContentTool",
    "GoogleSearchTool",
    "ZhipuWebSearchTool",
    "ImageAnalysisTool",
    "AudioParseTool",
    "ReadTool",
    "ReadParams",
    "PermissionManager",
]
```

**Step 2: 更新主模块导出**

```python
# src/ai_agent/__init__.py
"""AI Agent 包"""

from ai_agent.skills import Skill, SkillCatalog, SkillMeta
from ai_agent.skills.catalog import build_catalog_from_directory, get_catalog_prompt

__all__ = [
    "Skill",
    "SkillCatalog",
    "SkillMeta",
    "build_catalog_from_directory",
    "get_catalog_prompt",
]
```

**Step 3: Commit**

```bash
git add src/ai_agent/__init__.py src/ai_agent/tools/__init__.py
git commit -m "feat: export skills and filesystem modules"
```

---

## 验证

### 单元测试

```bash
# 运行所有单元测试
uv run pytest tests/unit/skills/ tests/unit/tools/filesystem/ -v

# 预期：全部通过
```

### 集成测试

```bash
# 运行集成测试
uv run pytest tests/integration/skills/ -v

# 预期：全部通过
```

### 类型检查

```bash
# 运行 mypy 类型检查
uv run mypy src/ai_agent/skills/ src/ai_agent/tools/filesystem/

# 预期：无错误
```

### 手动验证

```python
# Python REPL 验证
from pathlib import Path
from ai_agent.skills.catalog import build_catalog_from_directory, get_catalog_prompt

# 构建 Catalog
catalog = build_catalog_from_directory(Path("./skills"))
print(f"发现 {len(catalog.skills)} 个 Skills")

# 获取提示词
prompt = get_catalog_prompt(catalog)
print(prompt)
```

---

## 后续任务（不在本阶段）

1. **将 Catalog 注入 ReActAgent 系统提示** - 需要修改 ReActPrompt
2. **实现 Write/Edit 工具** - 完善文件系统工具
3. **实现会话隔离** - 创建会话管理模块
4. **创建 workspace 目录** - 实现权限控制
