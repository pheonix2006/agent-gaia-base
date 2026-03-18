"""Skills 类型定义测试"""

from pathlib import Path

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
        assert meta.location == Path("/path/to/skills/web-search/SKILL.md")

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
