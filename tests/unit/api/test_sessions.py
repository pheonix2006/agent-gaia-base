"""会话管理 API 测试"""

from fastapi.testclient import TestClient
from pathlib import Path


def test_list_sessions(client: TestClient) -> None:
    """测试获取会话列表"""
    # 先创建一个项目
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test Project 2", "path": str(Path.cwd())},
    )
    assert response.status_code == 201
    project_slug = response.json()["slug"]

    # 创建会话
    response = client.post(
        "/api/v1/sessions",
        json={"project_slug": project_slug, "title": "Test Session"},
    )
    assert response.status_code == 201

    # 获取会话列表
    response = client.get(f"/api/v1/sessions?project={project_slug}")
    assert response.status_code == 200
    data = response.json()

    assert "sessions" in data
    assert "total" in data
    assert "page" in data
    assert data["total"] >= 1


def test_create_session(client: TestClient) -> None:
    """测试创建会话"""
    # 先创建项目
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test Project 3", "path": str(Path.cwd())},
    )
    assert response.status_code == 201
    project_slug = response.json()["slug"]

    # 创建会话
    response = client.post(
        "/api/v1/sessions",
        json={"project_slug": project_slug, "title": "My Session"},
    )
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["title"] == "My Session"
    assert data["project_slug"] == project_slug
    assert "created_at" in data


def test_create_session_auto_title(client: TestClient) -> None:
    """测试创建会话时自动生成标题"""
    # 先创建项目
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test Project 4", "path": str(Path.cwd())},
    )
    assert response.status_code == 201
    project_slug = response.json()["slug"]

    # 创建会话（不提供 title）
    response = client.post(
        "/api/v1/sessions",
        json={"project_slug": project_slug},
    )
    assert response.status_code == 201
    data = response.json()

    # 验证自动生成了时间戳格式的标题（如 "2026-03-20 15:30"）
    assert "title" in data
    assert data["title"] != "新会话"  # 不应该是默认标题
    # 验证标题格式（YYYY-MM-DD HH:MM）
    import re
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", data["title"])


def test_update_session_rename(client: TestClient) -> None:
    """测试重命名会话"""
    # 先创建项目和会话
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test Project 5", "path": str(Path.cwd())},
    )
    assert response.status_code == 201
    project_slug = response.json()["slug"]

    response = client.post(
        "/api/v1/sessions",
        json={"project_slug": project_slug, "title": "Old Title"},
    )
    assert response.status_code == 201
    session_id = response.json()["id"]

    # 重命名会话
    response = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"title": "New Title"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == session_id
    assert data["title"] == "New Title"


def test_delete_session(client: TestClient) -> None:
    """测试删除会话"""
    # 先创建项目和会话
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test Project 6", "path": str(Path.cwd())},
    )
    assert response.status_code == 201
    project_slug = response.json()["slug"]

    response = client.post(
        "/api/v1/sessions",
        json={"project_slug": project_slug, "title": "To Delete"},
    )
    assert response.status_code == 201
    session_id = response.json()["id"]

    # 删除会话
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "deleted"
    assert data["id"] == session_id

    # 验证会话已被删除（再次获取列表不应包含该会话）
    response = client.get(f"/api/v1/sessions?project={project_slug}")
    assert response.status_code == 200
    sessions = response.json()["sessions"]
    session_ids = [s["id"] for s in sessions]
    assert session_id not in session_ids


def test_list_sessions_pagination(client: TestClient) -> None:
    """测试会话列表分页"""
    # 先创建项目
    response = client.post(
        "/api/v1/projects",
        json={"name": "Test Project 7", "path": str(Path.cwd())},
    )
    assert response.status_code == 201
    project_slug = response.json()["slug"]

    # 创建 15 个会话
    for i in range(15):
        response = client.post(
            "/api/v1/sessions",
            json={"project_slug": project_slug, "title": f"Session {i}"},
        )
        assert response.status_code == 201

    # 测试第一页（每页 10 个）
    response = client.get(f"/api/v1/sessions?project={project_slug}&page=1&limit=10")
    assert response.status_code == 200
    data = response.json()

    assert len(data["sessions"]) == 10
    assert data["total"] == 15
    assert data["page"] == 1

    # 测试第二页（剩余 5 个）
    response = client.get(f"/api/v1/sessions?project={project_slug}&page=2&limit=10")
    assert response.status_code == 200
    data = response.json()

    assert len(data["sessions"]) == 5
    assert data["total"] == 15
    assert data["page"] == 2


def test_update_nonexistent_session(client: TestClient) -> None:
    """测试重命名不存在的会话"""
    response = client.patch(
        "/api/v1/sessions/nonexistent-session-id",
        json={"title": "New Title"}
    )
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


def test_delete_nonexistent_session(client: TestClient) -> None:
    """测试删除不存在的会话"""
    response = client.delete("/api/v1/sessions/nonexistent-session-id")
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


def test_list_sessions_nonexistent_project(client: TestClient) -> None:
    """测试获取不存在项目的会话列表"""
    response = client.get("/api/v1/sessions?project=nonexistent-project")
    # 项目不存在时应返回空列表或 404
    assert response.status_code in [200, 404]
