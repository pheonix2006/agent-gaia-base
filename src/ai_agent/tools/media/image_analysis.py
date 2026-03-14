# src/ai_agent/tools/media/image_analysis.py

"""图像分析工具"""

import base64
import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


logger = logging.getLogger(__name__)


class ImageAnalysisParams(BaseModel):
    image_path: str = Field(description="图像路径（本地文件或 URL）")
    query: str = Field(description="关于图像的问题或分析指令")


class ImageAnalysisTool(BaseAgentTool[ImageAnalysisParams, str]):
    """使用多模态模型分析图像内容"""

    name = "image_analysis"
    description = "分析图像内容，回答关于图像的问题。支持本地图片路径和 URL。"

    def __init__(self) -> None:
        self._settings: LLMSettings | None = None
        self._openai_client: Any = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            # 从环境变量加载或使用默认值
            import os
            api_key = os.getenv("OPENAI_API_KEY", "test_key")
            self._settings = LLMSettings(openai_api_key=api_key)
        return self._settings

    @property
    def params_schema(self) -> type[ImageAnalysisParams]:
        """参数模型"""
        return ImageAnalysisParams

    async def _get_openai_client(self) -> Any:
        """获取或创建 OpenAI 客户端"""
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url
            )
        return self._openai_client

    def _encode_image(self, image_path: str) -> str:
        """将本地图片编码为 base64"""
        path = Path(image_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8")

    def _get_image_url(self, image_path: str) -> str:
        """获取图片 URL（本地文件转 base64 data URL）"""
        if image_path.startswith(("http://", "https://")):
            return image_path
        encoded = self._encode_image(image_path)
        # 根据文件扩展名确定 MIME 类型
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")
        return f"data:{mime_type};base64,{encoded}"

    async def run(self, params: ImageAnalysisParams) -> ToolResult[str]:
        """执行图像分析"""
        import time
        start_time = time.time()

        image_path = params.image_path
        query = params.query

        # 参数校验
        if not image_path or not query:
            return ToolResult(
                success=False,
                data="",
                error="image_path 和 query 都是必需参数",
                metrics={"elapsed_time": time.time() - start_time},
            )

        # 处理图片（先处理文件，再检查 API key）
        try:
            image_url = self._get_image_url(image_path)
        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                data="",
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data="",
                error=f"图片处理失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )

        # 检查 API key（在调用 API 前）
        api_key = self.settings.openai_api_key
        if not api_key:
            return ToolResult(
                success=False,
                data="",
                error="OPENAI_API_KEY 未配置",
                metrics={"elapsed_time": time.time() - start_time},
            )

        # 调用多模态模型
        try:
            client = await self._get_openai_client()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": query},
                    ],
                }
            ]

            completion = await client.chat.completions.create(
                model=self.settings.openai_model,
                messages=messages,
            )

            content = None
            if completion and completion.choices:
                content = completion.choices[0].message.content

            if not content:
                return ToolResult(
                    success=False,
                    data="",
                    error="模型返回空响应",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            return ToolResult(
                success=True,
                data=content.strip(),
                error=None,
                metrics={"elapsed_time": time.time() - start_time},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data="",
                error=f"图像分析失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
