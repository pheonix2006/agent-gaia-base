"""ReAct Agent 调试脚本

用于调试 ReAct Agent 的执行过程，观察每轮的 think/act/observe，
检查工具调用是否正常，检测死循环等问题。

使用方式:
    python scripts/test_react_debug.py
"""

# 加载通用配置（编码、路径等）
import _common  # noqa: F401

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 初始化 LangSmith 追踪
try:
    from ai_agent.trace.langsmith import LangSmithSettings
    LangSmithSettings().setup()
    print("LangSmith 追踪已启用")
except Exception as e:
    print(f"LangSmith 配置失败（可选功能）: {e}")

from ai_agent.llm.client import create_llm_client
from ai_agent.agents.react import ReActAgent, AgentEventType
from ai_agent.tools.web import GoogleSearchTool, WebContentTool


# 测试问题列表
TEST_QUESTIONS = [
    {
        "name": "NBA 阿德巴约得分查询",
        "question": "搜索关于nba热火阿德巴约前几天取得的得分，对阵奇才",
        "expected_tools": ["google_search"],
        "max_steps": 30,
    },
    {
        "name": "简单问答（无需工具）",
        "question": "法国的首都是哪里？",
        "expected_tools": [],
        "max_steps": 15,
    },
    {
        "name": "最新信息查询",
        "question": "2024年美国总统大选的最新民调结果如何？",
        "expected_tools": ["google_search"],
        "max_steps": 30,
    },
]


async def test_agent_stream(
    agent: ReActAgent,
    question: str,
    max_steps: int = 20,
    verbose: bool = True,
) -> dict:
    """测试 Agent 的流式执行

    Args:
        agent: ReActAgent 实例
        question: 测试问题
        max_steps: 最大步数限制
        verbose: 是否打印详细日志

    Returns:
        包含执行结果的字典
    """
    result = {
        "question": question,
        "events": [],
        "event_types": [],
        "tool_calls": [],
        "errors": [],
        "steps": 0,
        "success": False,
        "final_answer": None,
    }

    print(f"\n{'='*60}")
    print(f"📝 问题: {question}")
    print(f"{'='*60}")

    step = 0
    async for event in agent.stream(question):
        step += 1
        result["steps"] = step
        result["events"].append(event)
        result["event_types"].append(event.event.value)

        # 打印事件详情
        if verbose:
            print(f"\n--- 步骤 {step}: {event.event.value.upper()} ---")
            print(f"⏰ 时间: {event.timestamp}")

            if event.event == AgentEventType.THINK:
                reasoning = event.data.get("reasoning", "")
                action = event.data.get("action", "")
                print(f"🤔 推理: {reasoning[:100]}...")
                if action:
                    print(f"🎯 决策行动: {action}")

            elif event.event == AgentEventType.ACT:
                tool_name = event.data.get("tool_name", "")
                params = event.data.get("params", {})
                print(f"🔧 调用工具: {tool_name}")
                print(f"📋 参数: {params}")
                result["tool_calls"].append({"tool": tool_name, "params": params})

            elif event.event == AgentEventType.OBSERVE:
                tool_name = event.data.get("tool_name", "")
                result_summary = event.data.get("result_summary", "")
                success = event.data.get("success", True)
                print(f"📥 工具结果: {tool_name}")
                print(f"{'✅' if success else '❌'} 摘要: {result_summary[:150]}...")
                if not success:
                    result["errors"].append(f"工具 {tool_name} 调用失败")

            elif event.event == AgentEventType.ERROR:
                message = event.data.get("message", "")
                details = event.data.get("details", "")
                print(f"❌ 错误: {message}")
                print(f"📄 详情: {details}")
                result["errors"].append(f"{message}: {details}")

            elif event.event == AgentEventType.FINISH:
                answer = event.data.get("answer", "")
                print(f"✅ 完成!")
                print(f"💡 最终答案: {answer[:200]}...")
                result["success"] = True
                result["final_answer"] = answer

        # 检查是否超过最大步数（死循环检测）
        if step >= max_steps:
            print(f"\n⚠️  警告: 达到最大步数 {max_steps}，可能存在死循环!")
            result["errors"].append(f"超过最大步数限制 ({max_steps})")
            break

    # 打印摘要
    print(f"\n{'='*60}")
    print(f"📊 执行摘要")
    print(f"{'='*60}")
    print(f"总步骤数: {result['steps']}")
    print(f"事件序列: {' → '.join(result['event_types'])}")
    print(f"工具调用: {[c['tool'] for c in result['tool_calls']]}")
    if result["errors"]:
        print(f"❌ 错误: {result['errors']}")
    else:
        print(f"✅ 无错误")

    return result


async def main():
    """主函数"""
    # 检查 API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("[ERROR] OPENAI_API_KEY not set")
        return

    # 创建 LLM 客户端
    print("🔧 初始化 LLM 客户端...")
    llm = create_llm_client()

    # 创建工具
    print("🔧 初始化工具...")
    tools = [
        GoogleSearchTool().to_langchain_tool(),
        WebContentTool().to_langchain_tool(),
    ]
    print(f"   已加载工具: {[t.name for t in tools]}")

    # 创建 Agent
    print("🔧 创建 ReActAgent...")
    agent = ReActAgent(llm, tools=tools, max_steps=20)

    # 运行测试
    all_results = []
    for test_case in TEST_QUESTIONS:
        result = await test_agent_stream(
            agent,
            test_case["question"],
            max_steps=test_case["max_steps"],
        )
        all_results.append(result)

        # 验证结果
        expected_tools = test_case["expected_tools"]
        if expected_tools:
            called_tools = [c["tool"] for c in result["tool_calls"]]
            for tool in expected_tools:
                if tool in called_tools:
                    print(f"✅ 预期工具 {tool} 被调用")
                else:
                    print(f"⚠️  预期工具 {tool} 未被调用")

    # 打印总体报告
    print(f"\n\n{'='*60}")
    print(f"📋 总体测试报告")
    print(f"{'='*60}")

    success_count = sum(1 for r in all_results if r["success"])
    error_count = sum(len(r["errors"]) for r in all_results)

    print(f"测试用例数: {len(all_results)}")
    print(f"成功完成: {success_count}")
    print(f"错误总数: {error_count}")

    if error_count == 0:
        print(f"\n🎉 所有测试通过!")
    else:
        print(f"\n⚠️  存在需要修复的问题:")
        for i, result in enumerate(all_results):
            if result["errors"]:
                print(f"\n  测试 {i+1} ({result['question'][:30]}...):")
                for error in result["errors"]:
                    print(f"    - {error}")


if __name__ == "__main__":
    asyncio.run(main())
