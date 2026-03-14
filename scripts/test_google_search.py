# -*- coding: utf-8 -*-
"""
GoogleSearchTool 真实 API 验证脚本

运行前确保 .env 中配置了:
- SERPER_API_KEY
- SERPER_BASE_URL

运行方式:
    cd "E:/Project/ai agent"
    python scripts/test_google_search.py
"""

import asyncio
import sys
import io
from pathlib import Path

# 设置 UTF-8 编码输出
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_agent.tools.web.google_search import GoogleSearchTool


async def test_google_search():
    print("=" * 60)
    print("GoogleSearchTool 真实 API 测试")
    print("=" * 60)

    tool = GoogleSearchTool()

    # 测试用例
    test_cases = [
        {
            "query": "Python programming language",
            "k": 3,
            "description": "英文搜索 - Python"
        },
        {
            "query": "人工智能最新进展",
            "k": 5,
            "gl": "cn",
            "hl": "zh",
            "description": "中文搜索 - AI"
        },
        {
            "query": "What is the capital of France?",
            "k": 1,
            "description": "问答式搜索"
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}: {case['description']} ---")
        print(f"Query: {case['query']}")
        print(f"参数: k={case.get('k', 5)}, gl={case.get('gl', 'us')}, hl={case.get('hl', 'en')}")
        print()

        try:
            result = await tool.run(
                query=case["query"],
                k=case.get("k", 5),
                gl=case.get("gl", "us"),
                hl=case.get("hl", "en")
            )

            if result.success:
                print(f"[PASS] 成功!")
                print(f"   耗时: {result.metrics.get('elapsed_time', 0):.2f}s")
                print(f"   结果数量: {result.metrics.get('result_count', 0)}")
                print(f"\n   搜索结果:")
                for j, item in enumerate(result.data[:3], 1):
                    content = item['content'][:150] + "..." if len(item['content']) > 150 else item['content']
                    print(f"   {j}. {content}")
                    print(f"      来源: {item['source']}")
            else:
                print(f"[FAIL] 失败: {result.error}")

        except Exception as e:
            print(f"[ERROR] 异常: {e}")

        print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_google_search())
