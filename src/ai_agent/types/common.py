"""通用类型别名定义

这些类型别名用于简化类型注解，提高代码可读性。
"""

from typing import Any, TypeAlias

# 基础 JSON 类型
JSON: TypeAlias = str | int | float | bool | None | dict[str, "JSON"] | list["JSON"]

# 通用字典类型
AnyDict: TypeAlias = dict[str, Any]

# JSON 兼容字典
JSONDict: TypeAlias = dict[str, JSON]
