# src/ai_agent/tools/media/audio_parse.py

"""音频解析工具"""

import base64
import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


logger = logging.getLogger(__name__)


class AudioParseParams(BaseModel):
    audio_path: str = Field(description="音频文件路径（仅支持本地文件）")
    query: str = Field(description="关于音频的问题或转录指令")


class AudioParseTool(BaseAgentTool[AudioParseParams, str]):
    """使用多模态模型解析音频内容"""

    name = "audio_parse"
    description = "转录音频内容或回答关于音频的问题。支持 mp3、wav、m4a 等格式。"

    # 支持的音频格式
    SUPPORTED_FORMATS = {"mp3", "wav", "m4a", "ogg", "flac", "aac"}

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
    def params_schema(self) -> type[AudioParseParams]:
        """参数模型"""
        return AudioParseParams

    async def _get_openai_client(self) -> Any:
        """获取或创建 OpenAI 客户端"""
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url
            )
        return self._openai_client

    def _validate_audio_file(self, audio_path: str) -> Path:
        """验证音频文件"""
        path = Path(audio_path).expanduser()

        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        ext = path.suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的音频格式: {ext}。支持: {', '.join(self.SUPPORTED_FORMATS)}")

        return path

    async def run(self, params: AudioParseParams) -> ToolResult[str]:
        """执行音频解析"""
        import time
        start_time = time.time()

        audio_path = params.audio_path
        query = params.query

        # 参数校验
        if not audio_path or not query:
            return ToolResult(
                success=False,
                data="",
                error="audio_path 和 query 都是必需参数",
                metrics={"elapsed_time": time.time() - start_time},
            )

        # 验证并读取音频文件（先处理文件，再检查 API key）
        try:
            audio_file = self._validate_audio_file(audio_path)
            audio_data = audio_file.read_bytes()
            encoded_audio = base64.b64encode(audio_data).decode("utf-8")
            audio_format = audio_file.suffix.lower().lstrip(".")
        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                data="",
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
            )
        except ValueError as e:
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
                error=f"音频文件读取失败: {str(e)}",
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

            # 使用 input_audio 格式（OpenAI API 标准）
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": encoded_audio,
                                "format": audio_format,
                            },
                        },
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
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "audio_format": audio_format,
                    "audio_size": len(audio_data),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data="",
                error=f"音频解析失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
