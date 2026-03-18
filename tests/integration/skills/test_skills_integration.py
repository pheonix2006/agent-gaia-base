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
                (skill_dir / "SKILL.md").write_text(
                    f"""---
name: {name}
description: {desc}
---
# {name}

使用说明...
""",
                    encoding="utf-8",
                )

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
            skill_md.write_text(
                """---
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
""",
                encoding="utf-8",
            )

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
            skill_md.write_text(
                """---
name: web-search
description: 搜索互联网
---
# Web Search
使用说明...
""",
                encoding="utf-8",
            )

            tool = ReadTool()
            result = tool.run_sync(ReadParams(path=str(skill_md)))

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
