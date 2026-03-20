"""项目管理 API 单元测试"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


class TestProjectAPI:
    """项目管理 API 测试"""

    def test_list_projects(self, client: TestClient) -> None:
        """测试获取项目列表"""
        response = client.get("/api/v1/projects")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # 至少有一个测试项目

        # 验证数据结构
        project = data[0]
        assert "slug" in project
        assert "name" in project
        assert "path" in project

    def test_create_project(self, client: TestClient, tmp_path: Path) -> None:
        """测试创建项目"""
        project_path = tmp_path / "new-project"
        project_path.mkdir()

        response = client.post(
            "/api/v1/projects",
            json={"name": "New Project", "path": str(project_path)},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "New Project"
        assert data["slug"] == "new-project"
        assert data["path"] == str(project_path)

    def test_create_project_duplicate_name(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """测试创建重名项目（应该失败）"""
        project_path1 = tmp_path / "project1"
        project_path2 = tmp_path / "project2"
        project_path1.mkdir()
        project_path2.mkdir()

        # 第一次创建
        response1 = client.post(
            "/api/v1/projects",
            json={"name": "Test Duplicate", "path": str(project_path1)},
        )
        assert response1.status_code == 200

        # 第二次创建同名项目
        response2 = client.post(
            "/api/v1/projects",
            json={"name": "Test Duplicate", "path": str(project_path2)},
        )
        # 应该成功，但 slug 会自动添加后缀
        assert response2.status_code == 200
        data = response2.json()
        assert data["slug"].startswith("test-duplicate")
        assert data["slug"] != "test-duplicate"

    def test_update_project_rename(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """测试重命名项目"""
        project_path = tmp_path / "rename-project"
        project_path.mkdir()

        # 先创建项目
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Old Name", "path": str(project_path)},
        )
        assert create_response.status_code == 200
        slug = create_response.json()["slug"]

        # 重命名项目
        response = client.patch(
            f"/api/v1/projects/{slug}",
            json={"name": "New Name"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "New Name"
        # slug 应该改变
        assert data["slug"] == "new-name"

    def test_delete_project(self, client: TestClient, tmp_path: Path) -> None:
        """测试删除项目"""
        project_path = tmp_path / "delete-project"
        project_path.mkdir()

        # 先创建项目
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Delete Me", "path": str(project_path)},
        )
        assert create_response.status_code == 200
        slug = create_response.json()["slug"]

        # 删除项目
        response = client.delete(f"/api/v1/projects/{slug}")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "deleted"
        assert data["slug"] == slug

        # 验证项目确实被删除
        list_response = client.get("/api/v1/projects")
        projects = list_response.json()
        slugs = [p["slug"] for p in projects]
        assert slug not in slugs
