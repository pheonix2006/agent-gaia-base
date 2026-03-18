"""Read 工具实现"""

import time
from typing import Optional

from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult
from ai_agent.tools.filesystem.permissions import PermissionManager


class ReadParams(BaseModel):
    """Read 工具参数"""

    path: str = Field(description="要读取的文件路径")
    offset: int = Field(default=0, ge=0, description="从第几行开始读取（0 表示从头开始）")
    limit: int = Field(default=2000, ge=1, le=10000, description="最多读取多少行")


class ReadTool(BaseAgentTool[ReadParams, str]):
    """文件读取工具

    支持读取文本文件，可选行偏移和限制。
    """

    def __init__(
        self,
        permission_manager: Optional[PermissionManager] = None,
        default_encoding: str = "utf-8",
    ) -> None:
        self._permission_manager = permission_manager
        self._default_encoding = default_encoding

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return """读取文件内容。

参数：
- path: 文件路径（绝对路径或相对路径）
- offset: 从第几行开始读取，默认 0
- limit: 最多读取多少行，默认 2000

返回文件内容，带行号前缀。"""

    @property
    def params_schema(self) -> type[ReadParams]:
        return ReadParams

    async def run(self, params: ReadParams) -> ToolResult[str]:
        """执行文件读取"""
        return self.run_sync(params)

    def run_sync(self, params: ReadParams) -> ToolResult[str]:
        """同步执行文件读取"""
        start_time = time.time()

        try:
            from pathlib import Path

            file_path = Path(params.path).expanduser().resolve()

            # 检查文件是否存在
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    data="",
                    error=f"文件不存在: {params.path}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 检查是否为文件
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    data="",
                    error=f"路径不是文件: {params.path}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 权限检查
            if self._permission_manager and not self._permission_manager.is_allowed(file_path):
                return ToolResult(
                    success=False,
                    data="",
                    error=f"权限不足：无法访问 {params.path}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 读取文件
            content = file_path.read_text(encoding=self._default_encoding)
            lines = content.splitlines()

            # 应用偏移和限制
            start = params.offset
            end = start + params.limit
            selected_lines = lines[start:end]

            # 添加行号前缀
            numbered_lines = []
            for i, line in enumerate(selected_lines, start=start + 1):
                numbered_lines.append(f"{i:6}\t{line}")

            result_content = "\n".join(numbered_lines)

            return ToolResult(
                success=True,
                data=result_content,
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "total_lines": len(lines),
                    "returned_lines": len(selected_lines),
                },
            )

        except UnicodeDecodeError as e:
            return ToolResult(
                success=False,
                data="",
                error=f"文件编码错误: {e}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except PermissionError as e:
            return ToolResult(
                success=False,
                data="",
                error=f"权限错误: {e}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data="",
                error=f"读取失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
