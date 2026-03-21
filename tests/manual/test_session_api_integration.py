#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会话 API 集成测试脚本

测试 GET /api/v1/sessions/{session_id} 是否正确返回会话历史数据
"""

import json
import sys
from pathlib import Path

# Windows 控制台编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ai_agent.session.manager import SessionManager
from ai_agent.session.store import HistoryStore
from ai_agent.session.project import ProjectManager


def test_session_loading():
    """测试会话加载功能"""
    print("=" * 60)
    print("会话加载功能集成测试")
    print("=" * 60)

    # 1. 初始化组件
    print("\n[Step 1] 初始化组件...")
    config_dir = Path.home() / ".agents"
    history_dir = config_dir / "history"

    project_manager = ProjectManager(config_dir=config_dir)
    history_store = HistoryStore(base_path=history_dir)
    session_manager = SessionManager(store=history_store, project_manager=project_manager)

    print(f"[OK] 配置目录: {config_dir}")
    print(f"[OK] 历史目录: {history_dir}")

    # 2. 列出所有注册的项目
    print("\n[Step 2] 列出所有注册的项目...")
    projects = project_manager.list_projects()
    print(f"找到 {len(projects)} 个项目:")
    for i, project in enumerate(projects, 1):
        print(f"  {i}. {project.slug}")
        print(f"     名称: {project.name}")
        print(f"     路径: {project.path}")
        print(f"     活跃会话: {project.active_session}")

    # 3. 测试目标会话
    target_session_id = "20260321-001"
    print(f"\n[Step 3] 查找会话: {target_session_id}")

    found_project_slug = None
    session_data = None

    for project in projects:
        print(f"\n尝试在项目 '{project.slug}' 中查找...")
        data = session_manager.load_session_data(project.slug, target_session_id)

        if data:
            found_project_slug = project.slug
            session_data = data
            print(f"[OK] 找到会话！")
            print(f"  会话ID: {data['session'].id}")
            print(f"  标题: {data['session'].title}")
            print(f"  消息数: {len(data['messages'])}")
            print(f"  调用记录数: {len(data['traces'])}")
            break
        else:
            print(f"  [X] 未找到")

    # 4. 验证数据
    print("\n[Step 4] 验证会话数据...")

    if not session_data:
        print(f"[ERROR] 错误：在所有项目中都未找到会话 {target_session_id}")
        print("\n可能的原因：")
        print("1. 会话不存在")
        print("2. 会话文件损坏")
        print("3. 项目 slug 不匹配")

        # 检查文件是否存在
        print("\n检查文件系统...")
        for project in projects:
            session_dir = history_dir / project.slug / target_session_id
            if session_dir.exists():
                print(f"[OK] 找到目录: {session_dir}")
                files = list(session_dir.iterdir())
                print(f"  文件: {[f.name for f in files]}")
            else:
                print(f"[X] 目录不存在: {session_dir}")

        return False

    # 5. 详细检查消息
    print("\n[Step 5] 检查消息内容...")
    messages = session_data['messages']
    if messages:
        print(f"共 {len(messages)} 条消息:")
        for i, msg in enumerate(messages[:3], 1):  # 只显示前3条
            print(f"  {i}. [{msg.role}] {msg.content[:50]}...")
    else:
        print("[ERROR] 错误：消息列表为空")
        return False

    # 6. 详细检查调用记录
    print("\n[Step 6] 检查调用记录...")
    traces = session_data['traces']
    if traces:
        print(f"共 {len(traces)} 条调用记录:")
        for i, trace in enumerate(traces[:3], 1):  # 只显示前3条
            print(f"  {i}. [{trace.tool}] {trace.result_status}")
    else:
        print("[WARN]  警告：调用记录为空（可能是纯对话，无工具调用）")

    print("\n" + "=" * 60)
    print("[OK] 测试通过！会话数据加载正常")
    print("=" * 60)
    return True


def test_api_endpoint():
    """测试 API 端点"""
    import requests

    print("\n" + "=" * 60)
    print("API 端点集成测试")
    print("=" * 60)

    base_url = "http://localhost:8000"
    session_id = "20260321-001"

    try:
        print(f"\n[Step 1] 调用 API: GET {base_url}/api/v1/sessions/{session_id}")
        response = requests.get(f"{base_url}/api/v1/sessions/{session_id}", timeout=5)

        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n[Step 2] 解析响应数据...")

            session = data.get('session', {})
            messages = data.get('messages', [])
            traces = data.get('traces', [])

            print(f"[OK] 会话ID: {session.get('id')}")
            print(f"[OK] 标题: {session.get('title')}")
            print(f"[OK] 项目: {session.get('project_slug')}")
            print(f"[OK] 消息数: {len(messages)}")
            print(f"[OK] 调用记录数: {len(traces)}")

            if messages:
                print("\n[Step 3] 检查消息内容...")
                for i, msg in enumerate(messages[:3], 1):
                    role = msg.get('role')
                    content = msg.get('content', '')[:50]
                    print(f"  {i}. [{role}] {content}...")

                print("\n" + "=" * 60)
                print("[OK] API 测试通过！返回数据正常")
                print("=" * 60)
                return True
            else:
                print("\n[ERROR] 错误：API 返回的消息列表为空")
                print("响应数据:", json.dumps(data, indent=2, ensure_ascii=False))
                return False
        else:
            print(f"\n[ERROR] 错误：API 返回错误状态码 {response.status_code}")
            print("响应:", response.text)
            return False

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] 错误：无法连接到服务器")
        print("请确保服务正在运行：uv run python main.py")
        return False
    except Exception as e:
        print(f"\n[ERROR] 错误：{type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("开始集成测试...\n")

    # 测试 1: 直接测试 SessionManager
    success1 = test_session_loading()

    # 测试 2: 测试 API 端点
    print("\n" + "=" * 60)
    print("等待 2 秒后测试 API 端点...")
    print("=" * 60)
    import time
    time.sleep(2)

    success2 = test_api_endpoint()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"SessionManager 测试: {'[OK] 通过' if success1 else '[X] 失败'}")
    print(f"API 端点测试: {'[OK] 通过' if success2 else '[X] 失败'}")

    if success1 and success2:
        print("\n[SUCCESS] 所有测试通过！后端正常工作")
        sys.exit(0)
    else:
        print("\n[ERROR] 部分测试失败，请检查后端实现")
        sys.exit(1)
