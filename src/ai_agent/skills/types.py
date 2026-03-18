"""Skills 类型定义"""

from html import escape
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def _escape_xml(value: str) -> str:
    """转义 XML 特殊字符

    Args:
        value: 需要转义的字符串

    Returns:
        转义后的安全字符串
    """
    return escape(value)


class SkillMeta(BaseModel):
    """Skill 元数据（Catalog 中使用）

    用于在 SkillCatalog 中展示 Skill 的基本信息，采用渐进式披露模式。
    """

    name: str = Field(description="Skill 名称，必须唯一")
    description: str = Field(description="Skill 简短描述，用于判断何时使用")
    location: Path = Field(description="SKILL.md 文件的绝对路径")

    model_config = ConfigDict(frozen=True)


class Skill(BaseModel):
    """完整的 Skill（包含 body 内容）

    表示完整的 Skill，包含元数据和 Markdown 正文内容。
    """

    meta: SkillMeta = Field(description="Skill 元数据")
    body: str = Field(description="SKILL.md 的 Markdown 正文（去除 frontmatter 后）")


class SkillCatalog(BaseModel):
    """Skill 目录（注入系统提示用）

    管理所有可用 Skills 的元数据，支持转换为 XML 格式注入系统提示。
    采用渐进式披露模式：先展示 Catalog，按需读取完整 Skill。
    """

    skills: list[SkillMeta] = Field(default_factory=list, description="所有可用 Skills")

    def to_xml(self) -> str:
        """转换为 XML 格式，用于注入系统提示

        Returns:
            XML 格式的字符串，空 Catalog 返回空字符串
        """
        if not self.skills:
            return ""

        lines = ["<skills_catalog>"]
        for skill in self.skills:
            lines.extend([
                "<skill>",
                f"<name>{_escape_xml(skill.name)}</name>",
                f"<description>{_escape_xml(skill.description)}</description>",
                f"<location>{_escape_xml(str(skill.location))}</location>",
                "</skill>",
            ])
        lines.append("</skills_catalog>")
        return "\n".join(lines)
