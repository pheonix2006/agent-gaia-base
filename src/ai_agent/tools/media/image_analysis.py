# src/ai_agent/tools/media/image_analysis.py

"""图像分析工具"""

import base64
import logging
from pathlib import Path
from typing import Any, Optional

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


logger = logging.getLogger(__name__)


class ImageAnalysisTool(BaseAgentTool):
    """使用多模态模型分析图像内容"""

    name = "image_analysis"
    description = "分析图像内容，回答关于图像的问题。支持本地图片路径和 URL。"
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "图像路径（本地文件或 URL）",
            },
            "query": {
                "type": "string",
                "description": "关于图像的问题或分析指令",
            },
        },
        "required": ["image_path", "query"],
        "additionalProperties": False,
    }

    def __init__(self):
        self._settings: Optional[LLMSettings] = None
        self._openai_client: Optional[Any] = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

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

    async def run(self, image_path: str, query: str) -> ToolResult:
        """执行图像分析"""
        import time
        start_time = time.time()

        # 参数校验
        if not image_path or not query:
            return ToolResult(
                success=False,
                data=None,
                error="image_path 和 query 都是必需参数",
                metrics={"elapsed_time": time.time() - start_time},
            )

        api_key = self.settings.openai_api_key
        if not api_key:
            return ToolResult(
                success=False,
                data=None,
                error="OPENAI_API_KEY 未配置",
                metrics={"elapsed_time": time.time() - start_time},
            )

        # 处理图片
        try:
            image_url = self._get_image_url(image_path)
        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"图片处理失败: {str(e)}",
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
                    data=None,
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
                data=None,
                error=f"图像分析失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
