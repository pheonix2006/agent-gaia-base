# -*- coding: utf-8 -*-
"""
WebContentTool 真实 API 验证脚本

运行前确保 .env 中配置了:
- JINA_API_KEY
- OPENAI_API_KEY
- OPENAI_BASE_URL
- OPENAI_MODEL

运行方式:
    cd "E:/Project/ai agent"
    python scripts/test_web_content.py
"""

import asyncio
import sys
import os
from pathlib import Path

# 设置 UTF-8 编码输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_agent.tools.web.web_content import WebContentTool


async def test_web_content():
    print("=" * 60)
    print("WebContentTool 真实 API 测试")
    print("=" * 60)

    tool = WebContentTool()

    # 测试用例
    test_cases = [
        {
            "url": "https://www.python.org",
            "query": "What is Python? Answer in 2-3 sentences.",
            "description": "Python 官网内容提取"
        },
        {
            "url": "https://github.com/langchain-ai/langchain",
            "query": "What is LangChain? Brief summary in Chinese.",
            "description": "GitHub README 提取"
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}: {case['description']} ---")
        print(f"URL: {case['url']}")
        print(f"Query: {case['query']}")
        print()

        try:
            result = await tool.run(
                url=case["url"],
                query=case["query"]
            )

            if result.success:
                print(f"[PASS] 成功!")
                print(f"   耗时: {result.metrics.get('elapsed_time', 0):.2f}s")
                print(f"   Token 数: {result.metrics.get('token_count', 'N/A')}")
                print(f"   是否分块: {result.metrics.get('chunked', False)}")
                print(f"\n   答案:")
                answer = result.data['answer']
                # 截断长答案
                if len(answer) > 500:
                    print(f"   {answer[:500]}...")
                else:
                    print(f"   {answer}")
            else:
                print(f"[FAIL] 失败: {result.error}")

        except Exception as e:
            print(f"[ERROR] 异常: {e}")

        print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_web_content())
