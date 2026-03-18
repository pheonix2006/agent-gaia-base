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
description: Search the internet
---
Body content
""", encoding="utf-8")

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
description: {name} description
---
Body
""", encoding="utf-8")

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
description: Valid skill
---
Body
""", encoding="utf-8")

            # 无效目录（无 SKILL.md）
            invalid_dir = skills_dir / "invalid-dir"
            invalid_dir.mkdir()
            (invalid_dir / "README.md").write_text("No skill here", encoding="utf-8")

            # 普通文件（不是目录）
            (skills_dir / "some-file.txt").write_text("Not a directory", encoding="utf-8")

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
description: Should not be discovered
---
""", encoding="utf-8")

            # 创建 __pycache__ 目录（应该被跳过）
            pycache_dir = skills_dir / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "SKILL.md").write_text("""---
name: pycache-skill
description: Should not be discovered
---
""", encoding="utf-8")

            # 有效 skill
            valid_dir = skills_dir / "valid-skill"
            valid_dir.mkdir()
            (valid_dir / "SKILL.md").write_text("""---
name: valid-skill
description: Valid skill
---
""", encoding="utf-8")

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
description: Test skill description
---
# Usage Instructions
This is the body content.
""", encoding="utf-8")

            skill = load_skill(skill_md)

            assert skill.meta.name == "test-skill"
            assert "Usage Instructions" in skill.body

    def test_load_skill_with_scripts(self):
        """测试加载包含脚本的 Skill"""
        from ai_agent.skills.discovery import load_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "scripted-skill"
            skill_dir.mkdir()

            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: scripted-skill
description: Skill with scripts
---
# Instructions
Use scripts/run.py to execute.
""", encoding="utf-8")

            # 创建脚本文件
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "run.py").write_text("print('hello')", encoding="utf-8")

            skill = load_skill(skill_md)

            assert skill.meta.name == "scripted-skill"
            # skill_dir 属性应该指向 Skill 目录
            assert skill.meta.location.parent.name == "scripted-skill"
