"""编码配置模块

统一处理 UTF-8 编码问题，解决 Windows 控制台中文乱码。

使用方式：
    from ai_agent.config.encoding import setup_utf8_encoding
    setup_utf8_encoding()
"""

import io
import sys


def setup_utf8_encoding() -> None:
    """设置 UTF-8 编码输出（Windows 兼容）

    在 Windows 系统上，控制台默认使用 GBK 编码，
    导致输出中文时出现乱码。此函数将标准输出和标准错误
    统一设置为 UTF-8 编码。
    """
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


# 自动执行（当此模块被导入时）
setup_utf8_encoding()
