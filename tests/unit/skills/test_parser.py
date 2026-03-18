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
