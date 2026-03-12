"""Prompt 基类模块"""

from abc import ABC, abstractmethod
from typing import Any


class BasePrompt(ABC):
    """Prompt 基类，定义统一接口"""

    @property
    @abstractmethod
    def template(self) -> str:
        """获取原始模板字符串"""
        pass

    @abstractmethod
    def format(self, **kwargs: Any) -> str:
        """格式化模板，注入变量"""
        pass
