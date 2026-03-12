# src/ai_agent/tools/web/web_content.py

"""网页内容提取工具（Jina API）"""

import asyncio
import time
from typing import Any, Optional, List

import httpx
import tiktoken

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


class WebContentTool(BaseAgentTool):
    """使用 Jina API 提取网页内容并进行智能问答"""

    name = "web_content"
    description = "提取网页内容并回答问题。支持 http/https URL。返回基于网页内容的答案。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要提取内容的网页 URL（仅支持 http/https）",
            },
            "query": {
                "type": "string",
                "description": "针对网页内容的问题或指令",
            },
        },
        "required": ["url", "query"],
        "additionalProperties": False,
    }

    # 内容分块的 token 限制
    CHUNK_TOKEN_LIMIT = 95000

    def __init__(self):
        self._settings: Optional[LLMSettings] = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

    async def _fetch_jina(self, url: str, max_retry: int = 3) -> Optional[str]:
        """通过 Jina API 获取网页内容"""
        jina_api_key = self.settings.jina_api_key
        if not jina_api_key:
            raise ValueError("JINA_API_KEY 未配置")

        headers = {"Authorization": f"Bearer {jina_api_key}"}
        jina_url = f"https://r.jina.ai/{url}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(max_retry):
                try:
                    response = await client.get(jina_url, headers=headers)
                    if response.status_code == 200:
                        return response.text
                    else:
                        print(f"Jina API error (attempt {attempt + 1}): {response.text[:200]}")
                except httpx.RequestError as e:
                    print(f"Jina request error (attempt {attempt + 1}): {e}")

        return None

    async def _call_llm(self, query: str) -> str:
        """调用 LLM 处理查询"""
        from openai import AsyncOpenAI

        api_key = self.settings.openai_api_key
        base_url = self.settings.openai_base_url
        model = self.settings.openai_model

        if not api_key:
            raise ValueError("OPENAI_API_KEY 未配置")

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        messages = [{"role": "user", "content": query}]

        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.settings.temperature,
        )

        content = completion.choices[0].message.content if completion and completion.choices else None
        if not content:
            raise RuntimeError("LLM 返回空响应")

        return content.strip()

    async def run(self, url: str, query: str) -> ToolResult:
        """执行网页内容提取和问答"""
        start_time = time.time()

        try:
            # 1. 获取网页内容
            source_text = await self._fetch_jina(url)
            if not source_text or not source_text.strip():
                return ToolResult(
                    success=False,
                    data=None,
                    error="获取网页内容失败或内容为空",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 2. 构建查询 prompt
            def build_prompt(content: str, q: str) -> str:
                return (
                    f"请阅读以下网页内容并回答问题：\n"
                    f"--- 网页内容开始 ---\n{content}\n--- 网页内容结束 ---\n\n"
                    f"如果没有相关信息，请明确说明。现在请回答问题：{q}"
                )

            # 3. 检查是否需要分块
            encoding = tiktoken.get_encoding("cl100k_base")
            tokens = encoding.encode(source_text)
            token_count = len(tokens)

            if token_count > self.CHUNK_TOKEN_LIMIT:
                # 分块处理
                output_parts: List[str] = []
                num_chunks = max(2, token_count // self.CHUNK_TOKEN_LIMIT + 1)
                chunk_size = token_count // num_chunks

                tasks: List[asyncio.Task[str]] = []
                for i in range(num_chunks):
                    start_idx = i * chunk_size
                    end_idx = min(start_idx + chunk_size + 1024, token_count)
                    chunk_text = encoding.decode(tokens[start_idx:end_idx])
                    chunk_prompt = build_prompt(chunk_text, query)
                    tasks.append(asyncio.create_task(self._call_llm(chunk_prompt)))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                output = f"内容较长，分 {num_chunks} 部分处理。请综合以下结果：\n\n"
                for idx, result in enumerate(results):
                    if isinstance(result, Exception):
                        return ToolResult(
                            success=False,
                            data=None,
                            error=f"第 {idx + 1} 部分处理失败: {result}",
                            metrics={"elapsed_time": time.time() - start_time},
                        )
                    output += f"--- 第 {idx + 1} 部分答案 ---\n{result}\n\n"
            else:
                # 直接处理
                prompt = build_prompt(source_text, query)
                output = await self._call_llm(prompt)

            # 4. 返回结果
            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "answer": output,
                    "source_preview": source_text[:2000] if source_text else "",
                },
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "token_count": token_count,
                    "chunked": token_count > self.CHUNK_TOKEN_LIMIT,
                },
            )

        except ValueError as e:
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
                error=f"处理失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
