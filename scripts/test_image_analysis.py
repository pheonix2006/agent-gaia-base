# -*- coding: utf-8 -*-
"""
ImageAnalysisTool 真实 API 验证脚本

运行前确保 .env 中配置了:
- OPENAI_API_KEY
- OPENAI_BASE_URL
- OPENAI_MODEL (GLM-4.6V 或其他支持视觉的模型)

运行方式:
    cd "E:/Project/ai agent"
    python scripts/test_image_analysis.py
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

from ai_agent.tools.media.image_analysis import ImageAnalysisTool


async def test_image_analysis():
    print("=" * 60)
    print("ImageAnalysisTool 真实 API 测试")
    print("=" * 60)

    tool = ImageAnalysisTool()

    # 测试用例 - 使用公开的图片 URL
    test_cases = [
        {
            "image_path": "https://www.python.org/static/img/python-logo.png",
            "query": "Describe this image. What do you see?",
            "description": "Python 官网 Logo"
        },
        {
            "image_path": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/800px-Python-logo-notext.svg.png",
            "query": "这个 Logo 使用了哪些颜色？用中文回答。",
            "description": "Wikipedia Python Logo - 中文问答"
        },
        {
            "image_path": "https://picsum.photos/400/300",
            "query": "What is shown in this random image?",
            "description": "随机图片测试"
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}: {case['description']} ---")
        print(f"Image: {case['image_path']}")
        print(f"Query: {case['query']}")
        print()

        try:
            result = await tool.run(
                image_path=case["image_path"],
                query=case["query"]
            )

            if result.success:
                print(f"[PASS] 成功!")
                print(f"   耗时: {result.metrics.get('elapsed_time', 0):.2f}s")
                print(f"\n   分析结果:")
                print(f"   {result.data}")
            else:
                print(f"[FAIL] 失败: {result.error}")

        except Exception as e:
            print(f"[ERROR] 异常: {e}")

        print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_image_analysis())
