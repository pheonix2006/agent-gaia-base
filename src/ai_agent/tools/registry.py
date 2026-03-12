"""工具注册中心模块"""


class ToolRegistry:
    """工具注册中心（单例模式）"""

    _instance = None
    _tools: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, tool) -> None:
        """注册工具"""
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str):
        """获取工具"""
        return cls._tools.get(name)

    @classmethod
    def get_all(cls) -> list:
        """获取所有工具"""
        return list(cls._tools.values())

    @classmethod
    def get_langchain_tools(cls) -> list:
        """获取 LangChain 格式的所有工具"""
        return [t.to_langchain_tool() for t in cls._tools.values()]

    @classmethod
    def clear(cls) -> None:
        """清空注册中心（仅用于测试）"""
        cls._tools = {}
