"""会话管理系统端到端集成测试

测试完整的会话管理工作流，包括:
1. 注册项目
2. 创建会话
3. 追加消息
4. 追加调用记录
5. 加载并验证数据
6. 列出会话

此测试验证 ProjectManager、HistoryStore、ConfigManager 组件之间的协作。
"""

from datetime import datetime
from pathlib import Path

import pytest

from ai_agent.session.config import ConfigManager
from ai_agent.session.project import ProjectManager
from ai_agent.session.store import HistoryStore
from ai_agent.session.types import Message, Session, Trace


@pytest.fixture
def test_env(tmp_path: Path) -> dict[str, Path]:
    """创建隔离的测试环境

    Args:
        tmp_path: pytest 提供的临时目录

    Returns:
        包含测试环境路径的字典
    """
    config_dir = tmp_path / ".agents"
    history_dir = config_dir / "history"
    project_dir = tmp_path / "projects" / "my-ai-agent"

    # 创建测试项目目录
    project_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_dir": config_dir,
        "history_dir": history_dir,
        "project_dir": project_dir,
    }


class TestE2ESessionWorkflow:
    """端到端会话工作流测试

    验证从项目注册到会话数据加载的完整流程。
    """

    def test_full_workflow(
        self, test_env: dict[str, Path]
    ) -> None:
        """完整的端到端工作流测试

        流程:
        1. 注册项目
        2. 创建会话
        3. 追加消息
        4. 追加调用记录
        5. 加载并验证数据
        6. 列出会话
        """
        config_dir = test_env["config_dir"]
        history_dir = test_env["history_dir"]
        project_dir = test_env["project_dir"]

        # ========== 1. 注册项目 ==========
        project_manager = ProjectManager(config_dir=config_dir)
        project = project_manager.register_project(
            path=project_dir,
            name="AI Agent Project"
        )

        # 验证项目注册成功
        assert project.slug == "ai-agent-project"
        assert project.name == "AI Agent Project"
        assert project.path == project_dir.resolve()

        # ========== 2. 创建会话 ==========
        store = HistoryStore(base_path=history_dir)
        session_id = "20260320-001"

        session = Session(
            id=session_id,
            project_slug=project.slug,
            title="测试会话 - 分析项目结构",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
            message_count=0,
            trace_count=0,
        )
        store.save_session_metadata(project.slug, session)

        # 设置活跃会话
        project_manager.set_active_session(project.slug, session_id)

        # 验证会话创建成功
        loaded_session = store.load_session_metadata(project.slug, session_id)
        assert loaded_session is not None
        assert loaded_session.title == "测试会话 - 分析项目结构"

        # ========== 3. 追加消息 ==========
        messages = [
            Message(
                role="user",
                content="请帮我分析这个项目的结构",
                timestamp=datetime(2026, 3, 20, 10, 5, 1),
            ),
            Message(
                role="assistant",
                content="好的，让我先查看项目的目录结构...",
                timestamp=datetime(2026, 3, 20, 10, 5, 3),
            ),
            Message(
                role="tool",
                content="列出目录: src/ai_agent/",
                name="bash",
                timestamp=datetime(2026, 3, 20, 10, 5, 4),
            ),
            Message(
                role="assistant",
                content="项目结构如下:\n- src/ai_agent/agents/\n- src/ai_agent/tools/\n- src/ai_agent/session/",
                timestamp=datetime(2026, 3, 20, 10, 5, 10),
            ),
        ]

        for msg in messages:
            store.append_message(project.slug, session_id, msg)

        # 验证消息追加成功
        loaded_messages = store.load_messages(project.slug, session_id)
        assert len(loaded_messages) == 4
        assert loaded_messages[0].role == "user"
        assert loaded_messages[0].content == "请帮我分析这个项目的结构"
        assert loaded_messages[2].role == "tool"
        assert loaded_messages[2].name == "bash"

        # ========== 4. 追加调用记录 ==========
        traces = [
            Trace(
                id="trace-001",
                tool="bash",
                params={"command": "ls -la src/ai_agent/"},
                result_status="success",
                result_preview="agents/ tools/ session/ prompts/",
                duration_ms=45,
                timestamp=datetime(2026, 3, 20, 10, 5, 4),
            ),
            Trace(
                id="trace-002",
                tool="read",
                params={"file_path": "src/ai_agent/session/__init__.py"},
                result_status="success",
                result_preview=""""多项目会话管理模块...""",
                duration_ms=23,
                timestamp=datetime(2026, 3, 20, 10, 5, 6),
            ),
        ]

        for trace in traces:
            store.append_trace(project.slug, session_id, trace)

        # 验证调用记录追加成功
        loaded_traces = store.load_traces(project.slug, session_id)
        assert len(loaded_traces) == 2
        assert loaded_traces[0].tool == "bash"
        assert loaded_traces[0].duration_ms == 45
        assert loaded_traces[1].tool == "read"
        assert loaded_traces[1].result_status == "success"

        # ========== 5. 加载并验证数据 ==========
        # 更新会话元数据（模拟消息/调用计数更新）
        updated_session = Session(
            id=session_id,
            project_slug=project.slug,
            title="测试会话 - 分析项目结构",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
            updated_at=datetime(2026, 3, 20, 10, 5, 10),
            message_count=len(messages),
            trace_count=len(traces),
        )
        store.save_session_metadata(project.slug, updated_session)

        # 重新加载并验证完整性
        final_session = store.load_session_metadata(project.slug, session_id)
        assert final_session is not None
        assert final_session.message_count == 4
        assert final_session.trace_count == 2
        assert final_session.updated_at == datetime(2026, 3, 20, 10, 5, 10)

        # 验证项目活跃会话设置
        project_check = project_manager.get_project(project.slug)
        assert project_check is not None
        assert project_check.active_session == session_id

        # ========== 6. 列出会话 ==========
        # 添加第二个会话
        session2 = Session(
            id="20260320-002",
            project_slug=project.slug,
            title="第二个测试会话",
            created_at=datetime(2026, 3, 20, 14, 0, 0),
        )
        store.save_session_metadata(project.slug, session2)

        sessions = store.list_sessions(project.slug)
        assert len(sessions) == 2

        # 验证会话按更新时间倒序（无 updated_at 的用 created_at）
        session_ids = [s.id for s in sessions]
        assert "20260320-001" in session_ids
        assert "20260320-002" in session_ids

    def test_multiple_projects_isolation(
        self, test_env: dict[str, Path]
    ) -> None:
        """多项目数据隔离测试

        验证不同项目的会话数据完全隔离。
        """
        config_dir = test_env["config_dir"]
        history_dir = test_env["history_dir"]

        project_manager = ProjectManager(config_dir=config_dir)
        store = HistoryStore(base_path=history_dir)

        # 创建两个项目
        project1_dir = test_env["project_dir"] / "project1"
        project2_dir = test_env["project_dir"] / "project2"
        project1_dir.mkdir(parents=True)
        project2_dir.mkdir(parents=True)

        p1 = project_manager.register_project(project1_dir, "Project One")
        p2 = project_manager.register_project(project2_dir, "Project Two")

        # 为每个项目创建会话
        session1 = Session(
            id="20260320-001",
            project_slug=p1.slug,
            title="项目一会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        session2 = Session(
            id="20260320-002",
            project_slug=p2.slug,
            title="项目二会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )

        store.save_session_metadata(p1.slug, session1)
        store.save_session_metadata(p2.slug, session2)

        # 为每个会话添加消息
        msg1 = Message(
            role="user",
            content="项目一的消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        msg2 = Message(
            role="user",
            content="项目二的消息",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )

        store.append_message(p1.slug, session1.id, msg1)
        store.append_message(p2.slug, session2.id, msg2)

        # 验证隔离
        p1_messages = store.load_messages(p1.slug, session1.id)
        p2_messages = store.load_messages(p2.slug, session2.id)

        assert len(p1_messages) == 1
        assert len(p2_messages) == 1
        assert p1_messages[0].content == "项目一的消息"
        assert p2_messages[0].content == "项目二的消息"

        # 验证列出会话时隔离
        p1_sessions = store.list_sessions(p1.slug)
        p2_sessions = store.list_sessions(p2.slug)

        assert len(p1_sessions) == 1
        assert len(p2_sessions) == 1
        assert p1_sessions[0].project_slug == p1.slug
        assert p2_sessions[0].project_slug == p2.slug

    def test_persistence_across_manager_recreation(
        self, test_env: dict[str, Path]
    ) -> None:
        """持久化测试 - 模拟应用重启

        验证数据在管理器重新创建后保持完整。
        """
        config_dir = test_env["config_dir"]
        history_dir = test_env["history_dir"]
        project_dir = test_env["project_dir"]

        # 第一次: 创建数据
        project_manager1 = ProjectManager(config_dir=config_dir)
        store1 = HistoryStore(base_path=history_dir)

        project = project_manager1.register_project(
            project_dir, "Persistent Project"
        )

        session = Session(
            id="20260320-001",
            project_slug=project.slug,
            title="持久化测试会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        store1.save_session_metadata(project.slug, session)

        msg = Message(
            role="user",
            content="这条消息需要持久化",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        store1.append_message(project.slug, session.id, msg)

        trace = Trace(
            id="trace-001",
            tool="test",
            params={},
            result_status="success",
            duration_ms=10,
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )
        store1.append_trace(project.slug, session.id, trace)

        project_manager1.set_active_session(project.slug, session.id)
        project_manager1.update_last_opened(project.slug)

        # 第二次: 重新创建管理器（模拟重启）
        project_manager2 = ProjectManager(config_dir=config_dir)
        store2 = HistoryStore(base_path=history_dir)

        # 验证项目持久化
        restored_project = project_manager2.get_project(project.slug)
        assert restored_project is not None
        assert restored_project.name == "Persistent Project"
        assert restored_project.active_session == session.id
        assert restored_project.last_opened is not None

        # 验证会话持久化
        restored_session = store2.load_session_metadata(project.slug, session.id)
        assert restored_session is not None
        assert restored_session.title == "持久化测试会话"

        # 验证消息持久化
        restored_messages = store2.load_messages(project.slug, session.id)
        assert len(restored_messages) == 1
        assert restored_messages[0].content == "这条消息需要持久化"

        # 验证调用记录持久化
        restored_traces = store2.load_traces(project.slug, session.id)
        assert len(restored_traces) == 1
        assert restored_traces[0].tool == "test"

    def test_file_structure_compliance(
        self, test_env: dict[str, Path]
    ) -> None:
        """文件结构合规性测试

        验证数据文件按设计规范存储。
        """
        history_dir = test_env["history_dir"]
        project_dir = test_env["project_dir"]

        project_manager = ProjectManager(config_dir=test_env["config_dir"])
        store = HistoryStore(base_path=history_dir)

        project = project_manager.register_project(project_dir, "Structure Test")
        session_id = "20260320-001"

        # 创建完整数据
        session = Session(
            id=session_id,
            project_slug=project.slug,
            title="结构测试",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        store.save_session_metadata(project.slug, session)

        msg = Message(
            role="user",
            content="test",
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
        )
        store.append_message(project.slug, session_id, msg)

        trace = Trace(
            id="trace-001",
            tool="test",
            params={},
            result_status="success",
            duration_ms=1,
            timestamp=datetime(2026, 3, 20, 10, 5, 1),
        )
        store.append_trace(project.slug, session_id, trace)

        # 验证文件结构
        session_dir = history_dir / project.slug / session_id
        assert session_dir.exists(), "会话目录应存在"
        assert session_dir.is_dir(), "会话目录应为目录"

        # 验证文件存在
        metadata_file = session_dir / "metadata.json"
        messages_file = session_dir / "messages.jsonl"
        traces_file = session_dir / "traces.jsonl"

        assert metadata_file.exists(), "metadata.json 应存在"
        assert messages_file.exists(), "messages.jsonl 应存在"
        assert traces_file.exists(), "traces.jsonl 应存在"

        # 验证文件格式
        import json

        # metadata.json 应为 JSON 格式
        metadata_content = metadata_file.read_text(encoding="utf-8")
        metadata = json.loads(metadata_content)
        assert metadata["id"] == session_id

        # messages.jsonl 应为 JSONL 格式
        messages_content = messages_file.read_text(encoding="utf-8")
        for line in messages_content.strip().split("\n"):
            msg_data = json.loads(line)
            assert "role" in msg_data
            assert "content" in msg_data

        # traces.jsonl 应为 JSONL 格式
        traces_content = traces_file.read_text(encoding="utf-8")
        for line in traces_content.strip().split("\n"):
            trace_data = json.loads(line)
            assert "id" in trace_data
            assert "tool" in trace_data


class TestE2EWithConfigManager:
    """包含 ConfigManager 的端到端测试

    验证全局配置与项目配置的协作。
    """

    def test_config_integration(
        self, test_env: dict[str, Path]
    ) -> None:
        """配置管理器集成测试"""
        config_dir = test_env["config_dir"]
        config_file = config_dir / "config.json"

        # 创建配置管理器
        config_manager = ConfigManager(config_path=config_file)

        # 设置 API Key
        config_manager.set_api_key("openai", "test-key-12345")

        # 获取 LLM 配置
        llm_config = config_manager.get_llm_config()
        assert llm_config["api_key"] == "test-key-12345"

        # 验证配置持久化
        config_manager2 = ConfigManager(config_path=config_file)
        llm_config2 = config_manager2.get_llm_config()
        assert llm_config2["api_key"] == "test-key-12345"

    def test_project_config_override(
        self, test_env: dict[str, Path]
    ) -> None:
        """项目级配置覆盖测试"""
        import json

        config_dir = test_env["config_dir"]
        project_dir = test_env["project_dir"]
        config_file = config_dir / "config.json"

        # 创建全局配置
        config_manager = ConfigManager(config_path=config_file)
        config_manager.set_api_key("openai", "global-key")

        # 创建项目级配置
        project_config = {
            "llm": {
                "model": "gpt-4-turbo",
                "temperature": 0.5,
            }
        }
        project_config_file = project_dir / ".aiagent.json"
        project_config_file.write_text(
            json.dumps(project_config), encoding="utf-8"
        )

        # 获取合并配置
        merged = config_manager.get_merged_config(project_dir)

        # 验证合并结果
        assert merged["llm"]["model"] == "gpt-4-turbo"  # 项目覆盖
        assert merged["llm"]["temperature"] == 0.5  # 项目覆盖
        assert merged["llm"]["provider"] == "openai"  # 全局默认
        assert merged["llm"]["api_key"] == "global-key"  # 全局值


class TestE2EErrorHandling:
    """端到端错误处理测试"""

    def test_concurrent_access_simulation(
        self, test_env: dict[str, Path]
    ) -> None:
        """并发访问模拟测试

        验证多实例场景下的乐观并发机制。
        """
        config_dir = test_env["config_dir"]
        project_dir = test_env["project_dir"]

        # 两个独立的管理器实例
        manager1 = ProjectManager(config_dir=config_dir)
        manager2 = ProjectManager(config_dir=config_dir)

        # manager1 注册项目
        p1 = manager1.register_project(
            project_dir / "project1", "First Project"
        )

        # manager2 注册另一个项目（模拟并发）
        p2 = manager2.register_project(
            project_dir / "project2", "Second Project"
        )

        # 重新加载验证两个项目都存在
        manager3 = ProjectManager(config_dir=config_dir)
        projects = manager3.list_projects()

        assert len(projects) == 2
        slugs = [p.slug for p in projects]
        assert "first-project" in slugs
        assert "second-project" in slugs

    def test_corrupted_metadata_handling(
        self, test_env: dict[str, Path]
    ) -> None:
        """损坏元数据处理测试"""
        history_dir = test_env["history_dir"]
        project_dir = test_env["project_dir"]

        project_manager = ProjectManager(config_dir=test_env["config_dir"])
        store = HistoryStore(base_path=history_dir)

        project = project_manager.register_project(project_dir, "Test")

        # 创建有效会话
        valid_session = Session(
            id="20260320-001",
            project_slug=project.slug,
            title="有效会话",
            created_at=datetime(2026, 3, 20, 10, 0, 0),
        )
        store.save_session_metadata(project.slug, valid_session)

        # 创建损坏的元数据
        invalid_dir = history_dir / project.slug / "20260320-999"
        invalid_dir.mkdir(parents=True)
        (invalid_dir / "metadata.json").write_text(
            "not valid json {{{", encoding="utf-8"
        )

        # 列出会话时应忽略损坏的
        sessions = store.list_sessions(project.slug)
        assert len(sessions) == 1
        assert sessions[0].id == "20260320-001"
