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
