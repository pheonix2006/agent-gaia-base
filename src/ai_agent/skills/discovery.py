"""Skill 发现器"""

import logging
from pathlib import Path

from ai_agent.skills.parser import SkillParseError, parse_skill_md
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

    递归扫描 skills_dir 下所有层级，查找包含 SKILL.md 的目录。

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

    for skill_md in skills_dir.rglob("SKILL.md"):
        # 跳过被忽略的目录中的 SKILL.md
        rel_parts = skill_md.relative_to(skills_dir).parts
        if any(part in IGNORED_DIRS for part in rel_parts):
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
