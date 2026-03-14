# -*- coding: utf-8 -*-
"""
多模态工具完整验证脚本

运行前确保 .env 中配置了所有必需的 API Key:
- OPENAI_API_KEY
- OPENAI_BASE_URL
- OPENAI_MODEL
- JINA_API_KEY
- SERPER_API_KEY
- SERPER_BASE_URL

运行方式:
    cd "E:/Project/ai agent"
    python scripts/test_all.py
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

from ai_agent.tools.web.web_content import WebContentTool
from ai_agent.tools.web.google_search import GoogleSearchTool
from ai_agent.tools.media.image_analysis import ImageAnalysisTool


async def test_web_content():
    """测试 WebContentTool"""
    print("\n" + "=" * 60)
    print("1. WebContentTool 测试 (Jina API)")
    print("=" * 60)

    tool = WebContentTool()

    try:
        result = await tool.run(
            url="https://www.python.org",
            query="What is Python? Answer in 2 sentences."
        )

        if result.success:
            print(f"[PASS] 成功! 耗时: {result.metrics.get('elapsed_time', 0):.2f}s")
            print(f"   答案: {result.data['answer'][:300]}...")
            return True
        else:
            print(f"[FAIL] 失败: {result.error}")
            return False
    except Exception as e:
        print(f"[ERROR] 异常: {e}")
        return False


async def test_google_search():
    """测试 GoogleSearchTool"""
    print("\n" + "=" * 60)
    print("2. GoogleSearchTool 测试 (Serper API)")
    print("=" * 60)

    tool = GoogleSearchTool()

    try:
        result = await tool.run(query="Python programming", k=3)

        if result.success:
            print(f"[PASS] 成功! 耗时: {result.metrics.get('elapsed_time', 0):.2f}s")
            print(f"   结果数: {len(result.data)}")
            for i, item in enumerate(result.data[:2], 1):
                print(f"   {i}. {item['content'][:100]}...")
            return True
        else:
            print(f"[FAIL] 失败: {result.error}")
            return False
    except Exception as e:
        print(f"[ERROR] 异常: {e}")
        return False


async def test_image_analysis():
    """测试 ImageAnalysisTool"""
    print("\n" + "=" * 60)
    print("3. ImageAnalysisTool 测试 (GLM-4.6V)")
    print("=" * 60)

    tool = ImageAnalysisTool()

    try:
        result = await tool.run(
            image_path="https://www.python.org/static/img/python-logo.png",
            query="Describe this logo in 2 sentences."
        )

        if result.success:
            print(f"[PASS] 成功! 耗时: {result.metrics.get('elapsed_time', 0):.2f}s")
            print(f"   描述: {result.data}")
            return True
        else:
            print(f"[FAIL] 失败: {result.error}")
            return False
    except Exception as e:
        print(f"[ERROR] 异常: {e}")
        return False


async def main():
    print("=" * 60)
    print("多模态工具完整验证")
    print("=" * 60)
    print("\n正在测试所有工具...")

    results = {
        "WebContentTool": await test_web_content(),
        "GoogleSearchTool": await test_google_search(),
        "ImageAnalysisTool": await test_image_analysis(),
    }

    # 总结
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, success in results.items():
        status = "[PASS] 通过" if success else "[FAIL] 失败"
        print(f"  {name}: {status}")

    passed = sum(results.values())
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n>>> 所有工具测试通过!")
    else:
        print("\n<<< 部分工具测试失败，请检查 API 配置")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
