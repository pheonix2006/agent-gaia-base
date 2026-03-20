"""Edit 工具实现"""

import time
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult
from ai_agent.tools.filesystem.permissions import PermissionManager, OperationType


class EditParams(BaseModel):
    """Edit 工具参数"""

    path: str = Field(description="要编辑的文件路径")
    old_text: str = Field(description="要替换的文本（精确匹配）")
    new_text: str = Field(description="替换后的新文本")

    @field_validator("old_text")
    @classmethod
    def validate_old_text(cls, v: str) -> str:
        """验证 old_text 不为空"""
        if not v:
            raise ValueError("old_text 不能为空")
        return v


class EditTool(BaseAgentTool[EditParams, dict[str, Any]]):
    """文件编辑工具

    支持精确文本替换，返回替换次数。
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
        return "edit"

    @property
    def description(self) -> str:
        return """编辑文件内容，执行精确文本替换。

参数：
- path: 文件路径（绝对路径或相对路径）
- old_text: 要替换的文本（必须精确匹配）
- new_text: 替换后的新文本

返回替换次数，如果未找到匹配则返回错误。"""

    @property
    def params_schema(self) -> type[EditParams]:
        return EditParams

    async def run(self, params: EditParams) -> ToolResult[dict[str, Any]]:
        """执行文件编辑"""
        return self.run_sync(params)

    def run_sync(self, params: EditParams) -> ToolResult[dict[str, Any]]:
        """同步执行文件编辑"""
        start_time = time.time()

        try:
            file_path = Path(params.path).expanduser().resolve()

            # 检查文件是否存在
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    data={},
                    error=f"文件不存在: {params.path}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 检查是否为文件
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    data={},
                    error=f"路径不是文件: {params.path}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 权限检查 - 使用 EDIT 操作类型
            if self._permission_manager:
                permission = self._permission_manager.check(
                    file_path, OperationType.EDIT
                )
                from ai_agent.session.types import Permission

                if permission != Permission.ALLOW:
                    return ToolResult(
                        success=False,
                        data={},
                        error=f"权限不足：无法编辑 {params.path}",
                        metrics={"elapsed_time": time.time() - start_time},
                    )

            # 读取文件内容
            content = file_path.read_text(encoding=self._default_encoding)

            # 检查 old_text 是否存在
            if params.old_text not in content:
                return ToolResult(
                    success=False,
                    data={"replacements": 0},
                    error=f"未找到要替换的文本: {params.old_text[:50]}{'...' if len(params.old_text) > 50 else ''}",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 执行替换 - 统计替换次数
            old_count = content.count(params.old_text)
            new_content = content.replace(params.old_text, params.new_text)

            # 写回文件
            file_path.write_text(new_content, encoding=self._default_encoding)

            return ToolResult(
                success=True,
                data={
                    "replacements": old_count,
                    "path": str(file_path),
                },
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "old_text_length": len(params.old_text),
                    "new_text_length": len(params.new_text),
                },
            )

        except ValueError as e:
            # Pydantic 验证错误
            return ToolResult(
                success=False,
                data={},
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
            )
        except UnicodeDecodeError as e:
            return ToolResult(
                success=False,
                data={},
                error=f"文件编码错误: {e}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except PermissionError as e:
            return ToolResult(
                success=False,
                data={},
                error=f"权限错误: {e}",
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"编辑失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
