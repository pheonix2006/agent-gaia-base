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
