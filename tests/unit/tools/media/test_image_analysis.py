# tests/unit/tools/media/test_image_analysis.py

"""ImageAnalysisTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_agent.tools.media.image_analysis import ImageAnalysisTool, ImageAnalysisParams


class TestImageAnalysisTool:
    """ImageAnalysisTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = ImageAnalysisTool()
        assert tool.name == "image_analysis"
        assert "图像" in tool.description or "图片" in tool.description or "image" in tool.description.lower()
        assert "image_path" in tool.parameters.get("properties", {})
        assert "query" in tool.parameters.get("properties", {})

    @pytest.mark.asyncio
    async def test_run_success_with_local_file(self, tmp_path, monkeypatch):
        """测试本地图片分析成功"""
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        tool = ImageAnalysisTool()

        # 创建临时图片文件
        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"fake image data")

        with patch.object(tool, '_get_openai_client', new_callable=AsyncMock) as mock_client:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "这是一张测试图片"
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

            params = ImageAnalysisParams(image_path=str(image_file), query="描述这张图片")
            result = await tool.run(params)

            assert result.success is True
            assert result.data == "这是一张测试图片"

    @pytest.mark.asyncio
    async def test_run_success_with_url(self, monkeypatch):
        """测试 URL 图片分析成功"""
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        tool = ImageAnalysisTool()

        with patch.object(tool, '_get_openai_client', new_callable=AsyncMock) as mock_client:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "URL 图片描述"
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

            params = ImageAnalysisParams(
                image_path="https://example.com/image.jpg",
                query="描述这张图片"
            )
            result = await tool.run(params)

            assert result.success is True
            assert result.data == "URL 图片描述"

    @pytest.mark.asyncio
    async def test_run_missing_params(self):
        """测试缺少参数"""
        tool = ImageAnalysisTool()

        params = ImageAnalysisParams(image_path="test.jpg", query="")
        result = await tool.run(params)
        assert result.success is False
        assert "必需" in result.error or "required" in result.error.lower()

        params = ImageAnalysisParams(image_path="", query="描述")
        result = await tool.run(params)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_run_file_not_found(self):
        """测试文件不存在"""
        tool = ImageAnalysisTool()

        params = ImageAnalysisParams(image_path="/nonexistent/image.jpg", query="描述")
        result = await tool.run(params)

        assert result.success is False
        assert "不存在" in result.error or "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_api_error(self, tmp_path, monkeypatch):
        """测试 API 错误"""
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        tool = ImageAnalysisTool()

        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"fake image data")

        with patch.object(tool, '_get_openai_client', new_callable=AsyncMock) as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            params = ImageAnalysisParams(image_path=str(image_file), query="描述")
            result = await tool.run(params)

            assert result.success is False
            assert "API Error" in result.error
