"""Skills 模块

提供 Skills 系统，支持渐进式披露模式：
1. SkillCatalog - 展示可用 Skills 摘要
2. Skill - 完整的 Skill 内容

基于 agentskills.io 规范实现。
"""

from .types import Skill, SkillCatalog, SkillMeta

__all__ = ["Skill", "SkillCatalog", "SkillMeta"]
