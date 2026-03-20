"""文件写入工具"""

import time
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult

from .permissions import OperationType, PermissionManager


class WriteParams(BaseModel):
    """Write 工具参数

    Attributes:
        path: 文件路径（绝对路径或相对路径）
        content: 要写入的内容
        mode: 写入模式，"w" 为覆盖写入，"a" 为追加
    """

    path: str = Field(description="文件路径（绝对路径或相对路径）")
    content: str = Field(description="要写入的文件内容")
    mode: Literal["w", "a"] = Field(
        default="w",
        description="写入模式：'w' 覆盖写入，'a' 追加写入",
    )


class WriteTool(BaseAgentTool[WriteParams, dict[str, Any]]):
    """文件写入工具

    支持写入文本文件，可自动创建父目录。
    与 PermissionManager 集成进行权限检查。
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
        return "write"

    @property
    def description(self) -> str:
        return """写入文件内容。

参数：
- path: 文件路径（绝对路径或相对路径）
- content: 要写入的内容
- mode: 写入模式，"w" 覆盖写入（默认），"a" 追加

自动创建父目录。返回写入的字节数。
"""

    @property
    def params_schema(self) -> type[WriteParams]:
        return WriteParams

    async def run(self, params: WriteParams) -> ToolResult[dict[str, Any]]:
        """执行文件写入（异步）"""
        return self.run_sync(params)

    def run_sync(self, params: WriteParams) -> ToolResult[dict[str, Any]]:
        """同步执行文件写入"""
        start_time = time.time()

        try:
            file_path = Path(params.path).expanduser().resolve()

            # 权限检查
            if self._permission_manager:
                from ai_agent.session.types import Permission

                permission = self._permission_manager.check(
                    file_path, OperationType.WRITE
                )
                if permission != Permission.ALLOW:
                    return ToolResult(
                        success=False,
                        data={},
                        error=f"权限不足：无法写入 {params.path}",
                        metrics={"elapsed_time": time.time() - start_time},
                    )

            # 自动创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(file_path, mode=params.mode, encoding=self._default_encoding) as f:
                f.write(params.content)

            # 计算实际写入的字节数
            bytes_written = len(params.content.encode(self._default_encoding))

            return ToolResult(
                success=True,
                data={
                    "bytes_written": bytes_written,
                    "path": str(file_path),
                },
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "mode": params.mode,
                },
            )

        except PermissionError as e:
            return ToolResult(
                success=False,
                data={},
                error=f"权限错误: {e}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except OSError as e:
            return ToolResult(
                success=False,
                data={},
                error=f"写入失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"写入失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
