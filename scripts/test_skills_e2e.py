# -*- coding: utf-8 -*-
"""
Skills 系统端到端测试脚本

通过真实 API 测试 ReAct Agent 使用 Skills 的完整流程：
1. 验证 Skills Catalog 加载
2. 验证 Agent 能正确读取 SKILL.md
3. 针对每个 Skill 设计测试问题，验证真实调用

运行前确保 .env 中配置了所有必需的 API Key:
- OPENAI_API_KEY 或 ZHIPU_API_KEY
- ZHIPU_API_KEY (用于 web_search)
- JINA_API_KEY (用于 web_content)

运行方式:
    cd "E:/Project/ai agent"
    uv run python scripts/test_skills_e2e.py
"""

import asyncio
import sys
import io
from pathlib import Path

# 设置 UTF-8 编码输出
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_agent.agents.react import ReActAgent, AgentEventType
from ai_agent.llm.client import create_llm_client
from ai_agent.llm.config import LLMSettings
from ai_agent.prompts import ReActPrompt
from ai_agent.skills.catalog import build_catalog_from_directory, get_catalog_prompt
from ai_agent.tools import (
    GoogleSearchTool,
    ZhipuWebSearchTool,
    WebContentTool,
    ImageAnalysisTool,
    AudioParseTool,
    ReadTool,
)


# 测试用例配置
# 每个 Skill 对应一个针对性的测试问题
SKILL_TEST_CASES = [
    {
        "skill": "web-search",
        "question": "搜索一下今天北京的天气情况",
        "expected_tool": "web_search",
        "description": "测试 web-search Skill - 需要搜索实时天气信息",
    },
    {
        "skill": "web-content",
        "question": "访问 https://www.anthropic.com 并用一句话告诉我这家公司是做什么的",
        "expected_tool": "web_content",
        "description": "测试 web-content Skill - 需要读取网页内容",
    },
    {
        "skill": "image-analysis",
        "question": "分析这张图片 https://www.python.org/static/img/python-logo.png 用一句话描述这个 logo",
        "expected_tool": "image_analysis",
        "description": "测试 image-analysis Skill - 需要分析图片",
    },
    # audio-parse 仅支持本地文件，跳过 URL 测试
    # 如需测试，请提供本地音频文件路径
    # {
    #     "skill": "audio-parse",
    #     "question": "转录本地音频文件 /path/to/audio.mp3",
    #     "expected_tool": "audio_parse",
    #     "description": "测试 audio-parse Skill - 需要转录本地音频",
    # },
]


def print_header(title: str) -> None:
    """打印标题"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_subheader(title: str) -> None:
    """打印子标题"""
    print("\n" + "-" * 70)
    print(f" {title}")
    print("-" * 70)


async def test_skills_catalog() -> bool:
    """测试 Skills Catalog 加载"""
    print_header("测试 1: Skills Catalog 加载")

    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"

    print(f"Skills 目录: {skills_dir}")
    print(f"目录存在: {skills_dir.exists()}")

    catalog = build_catalog_from_directory(skills_dir)
    print(f"\n发现 {len(catalog.skills)} 个 Skills:")

    for skill in catalog.skills:
        print(f"  - {skill.name}: {skill.description[:40]}...")

    # 验证 Catalog Prompt 生成
    catalog_prompt = get_catalog_prompt(catalog)
    print(f"\nCatalog Prompt 长度: {len(catalog_prompt)} 字符")

    if len(catalog.skills) >= 4:
        print("\n[PASS] Skills Catalog 加载成功!")
        return True
    else:
        print("\n[FAIL] Skills Catalog 加载失败，期望至少 4 个 Skills")
        return False


async def test_read_skill_md() -> bool:
    """测试 Read 工具读取 SKILL.md"""
    print_header("测试 2: Read 工具读取 SKILL.md")

    read_tool = ReadTool()
    skill_md_path = Path(__file__).parent.parent / "skills" / "web-search" / "SKILL.md"

    print(f"读取文件: {skill_md_path}")

    from ai_agent.tools.filesystem.read import ReadParams
    params = ReadParams(path=str(skill_md_path))
    result = read_tool.run_sync(params)

    if result.success:
        print(f"\n[PASS] 成功读取 SKILL.md")
        print(f"内容预览:\n{result.data[:500]}...")
        return True
    else:
        print(f"\n[FAIL] 读取失败: {result.error}")
        return False


async def test_skill_e2e(test_case: dict, llm, tools: list, prompt: ReActPrompt, catalog) -> dict:
    """测试单个 Skill 的端到端流程"""
    skill = test_case["skill"]
    question = test_case["question"]
    expected_tool = test_case["expected_tool"]

    print_subheader(f"测试 Skill: {skill}")
    print(f"问题描述: {test_case['description']}")
    print(f"问题: {question}")
    print(f"期望工具: {expected_tool}")

    # 创建 Agent
    agent = ReActAgent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        skill_catalog=catalog,
        max_steps=8,  # 增加 max_steps 以适应 Skills 模式
    )

    # 执行并收集事件
    events = []
    tools_used = []
    final_answer = None
    error = None

    try:
        async for event in agent.stream(question):
            events.append(event)

            if event.event == AgentEventType.ACT:
                tool_name = event.data.get("tool_name")
                if tool_name:
                    tools_used.append(tool_name)
                    print(f"  [ACT] 调用工具: {tool_name}")

            elif event.event == AgentEventType.OBSERVE:
                success = event.data.get("success", False)
                summary = event.data.get("result_summary", "")[:100]
                print(f"  [OBSERVE] 成功: {success}, 结果: {summary}...")

            elif event.event == AgentEventType.FINISH:
                final_answer = event.data.get("answer", "")
                print(f"  [FINISH] 最终答案: {final_answer[:200]}...")

            elif event.event == AgentEventType.ERROR:
                error = event.data.get("message", "Unknown error")
                print(f"  [ERROR] {error}")

    except Exception as e:
        error = str(e)
        print(f"  [EXCEPTION] {error}")

    # 验证结果
    success = (
        expected_tool in tools_used
        and final_answer is not None
        and error is None
    )

    return {
        "skill": skill,
        "success": success,
        "tools_used": tools_used,
        "expected_tool_used": expected_tool in tools_used,
        "final_answer": final_answer,
        "error": error,
    }


async def run_all_skill_tests() -> dict[str, bool]:
    """运行所有 Skill 测试"""
    print_header("Skills 系统端到端测试")

    # 初始化 LLM
    print("正在初始化 LLM 客户端...")
    llm = create_llm_client()
    print("LLM 客户端初始化完成")

    # 构建 Skills Catalog
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    catalog = build_catalog_from_directory(skills_dir)
    catalog_prompt = get_catalog_prompt(catalog)

    # 初始化工具
    settings = LLMSettings()
    search_tool = ZhipuWebSearchTool() if settings.web_search_provider == "zhipu" else GoogleSearchTool()

    tools = [
        search_tool,
        WebContentTool(),
        ImageAnalysisTool(),
        AudioParseTool(),
        ReadTool(),  # 必须包含 Read 工具
    ]

    # 转换为 LangChain 格式
    langchain_tools = [tool.to_langchain_tool() for tool in tools]

    # 创建 Prompt
    prompt = ReActPrompt().with_context(catalog_prompt) if catalog_prompt else ReActPrompt()

    # 运行测试
    results = {}

    for test_case in SKILL_TEST_CASES:
        result = await test_skill_e2e(
            test_case, llm, langchain_tools, prompt, catalog
        )
        results[result["skill"]] = result["success"]

    return results


async def main():
    """主函数"""
    print("=" * 70)
    print(" Skills 系统端到端测试")
    print(" 测试 ReAct Agent 通过 Skills 调用真实工具")
    print("=" * 70)

    all_results = {}

    # 测试 1: Skills Catalog 加载
    all_results["catalog"] = await test_skills_catalog()

    # 测试 2: Read 工具
    all_results["read_tool"] = await test_read_skill_md()

    # 测试 3-6: 各 Skill 端到端测试
    skill_results = await run_all_skill_tests()
    all_results.update(skill_results)

    # 汇总结果
    print_header("测试结果汇总")

    passed = 0
    total = len(all_results)

    for name, success in all_results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")
        if success:
            passed += 1

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n>>> 所有测试通过! Skills 系统工作正常")
    else:
        print("\n<<< 部分测试失败，请检查日志")

    print("=" * 70)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
