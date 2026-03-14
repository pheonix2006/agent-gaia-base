# -*- coding: utf-8 -*-
"""
AudioParseTool 真实 API 验证脚本

运行前确保 .env 中配置了:
- OPENAI_API_KEY
- OPENAI_BASE_URL
- OPENAI_MODEL (GLM-4.6V 或其他支持音频的模型)

运行方式:
    cd "E:/Project/ai agent"
    python scripts/test_audio_parse.py <audio_file_path>

注意: 需要提供真实的音频文件进行测试
支持的格式: mp3, wav, m4a, ogg, flac, aac
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

from ai_agent.tools.media.audio_parse import AudioParseTool


async def test_audio_parse(audio_path: str):
    print("=" * 60)
    print("AudioParseTool 真实 API 测试")
    print("=" * 60)

    tool = AudioParseTool()

    # 检查文件是否存在
    audio_file = Path(audio_path)
    if not audio_file.exists():
        print(f"[ERROR] 错误: 音频文件不存在: {audio_path}")
        print(f"\n使用方法:")
        print(f"  python scripts/test_audio_parse.py <audio_file_path>")
        print(f"\n示例:")
        print(f"  python scripts/test_audio_parse.py test.mp3")
        print(f"  python scripts/test_audio_parse.py /path/to/recording.wav")
        return

    print(f"\n音频文件: {audio_path}")
    print(f"文件大小: {audio_file.stat().st_size / 1024:.2f} KB")
    print(f"文件格式: {audio_file.suffix.lstrip('.')}")
    print()

    # 测试用例
    test_cases = [
        {
            "query": "请转录这段音频的内容",
            "description": "音频转录"
        },
        {
            "query": "这段音频讲了什么？用简短的话总结",
            "description": "音频总结"
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"--- 测试 {i}: {case['description']} ---")
        print(f"Query: {case['query']}")
        print()

        try:
            result = await tool.run(
                audio_path=audio_path,
                query=case["query"]
            )

            if result.success:
                print(f"[PASS] 成功!")
                print(f"   耗时: {result.metrics.get('elapsed_time', 0):.2f}s")
                print(f"   音频格式: {result.metrics.get('audio_format', 'N/A')}")
                print(f"   音频大小: {result.metrics.get('audio_size', 0) / 1024:.2f} KB")
                print(f"\n   结果:")
                print(f"   {result.data}")
            else:
                print(f"[FAIL] 失败: {result.error}")

        except Exception as e:
            print(f"[ERROR] 异常: {e}")

        print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print("=" * 60)
        print("AudioParseTool 真实 API 测试")
        print("=" * 60)
        print(f"\n使用方法:")
        print(f"  python scripts/test_audio_parse.py <audio_file_path>")
        print(f"\n支持的音频格式: mp3, wav, m4a, ogg, flac, aac")
        print(f"\n示例:")
        print(f"  python scripts/test_audio_parse.py test.mp3")
        print(f"  python scripts/test_audio_parse.py /path/to/recording.wav")
        print()
        print("提示: 你可以下载一些测试音频文件到 scripts/ 目录进行测试")
        sys.exit(1)

    audio_path = sys.argv[1]
    asyncio.run(test_audio_parse(audio_path))


if __name__ == "__main__":
    main()
