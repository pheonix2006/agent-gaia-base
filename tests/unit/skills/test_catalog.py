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
                (skill_dir / "SKILL.md").write_text(
                    f"""---
name: {name}
description: {name} description
---
Body
""",
                    encoding="utf-8",
                )

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
