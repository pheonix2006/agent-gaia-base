# tests/integration/tools/test_media_tools.py

"""Media 工具集成测试（真实 API）"""

import pytest
from ai_agent.tools.media import ImageAnalysisTool, AudioParseTool


pytestmark = pytest.mark.integration


class TestImageAnalysisToolIntegration:
    """ImageAnalysisTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return ImageAnalysisTool()

    @pytest.mark.asyncio
    async def test_analyze_url_image(self, tool):
        """测试分析 URL 图片"""
        # 使用公开的测试图片
        result = await tool.run(
            image_path="https://www.python.org/static/img/python-logo.png",
            query="Describe this image. What do you see?"
        )

        assert result.success is True
        assert result.data is not None
        assert len(result.data) > 10
        print(f"\n图像描述: {result.data[:300]}...")

    @pytest.mark.asyncio
    async def test_analyze_photo(self, tool):
        """测试分析照片 - 使用真实的 PNG 格式图片"""
        # 使用 Python 官网的 PNG 图片（真正的 PNG 格式，不是 SVG）
        result = await tool.run(
            image_path="https://www.python.org/static/img/python-logo.png",
            query="What colors are used in this logo?"
        )

        assert result.success is True
        print(f"\n颜色描述: {result.data}")


class TestAudioParseToolIntegration:
    """AudioParseTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return AudioParseTool()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要真实音频文件")
    async def test_transcribe_audio(self, tool, tmp_path):
        """测试音频转录"""
        # 注意：需要真实的音频文件才能测试
        audio_file = tmp_path / "test.mp3"
        # 这里需要写入真实的音频数据
        # audio_file.write_bytes(real_audio_data)

        if not audio_file.exists() or audio_file.stat().st_size == 0:
            pytest.skip("需要真实音频文件")

        result = await tool.run(
            audio_path=str(audio_file),
            query="Transcribe this audio"
        )

        assert result.success is True
        print(f"\n转录结果: {result.data}")
