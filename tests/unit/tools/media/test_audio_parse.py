# tests/unit/tools/media/test_audio_parse.py

"""AudioParseTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_agent.tools.media.audio_parse import AudioParseTool, AudioParseParams


class TestAudioParseTool:
    """AudioParseTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = AudioParseTool()
        assert tool.name == "audio_parse"
        assert "音频" in tool.description or "audio" in tool.description.lower()
        assert "audio_path" in tool.parameters.get("properties", {})
        assert "query" in tool.parameters.get("properties", {})

    @pytest.mark.asyncio
    async def test_run_success(self, tmp_path, monkeypatch):
        """测试音频解析成功"""
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        tool = AudioParseTool()

        # 创建临时音频文件
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        with patch.object(tool, '_get_openai_client', new_callable=AsyncMock) as mock_client:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "这是转录的文本内容"
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

            params = AudioParseParams(audio_path=str(audio_file), query="转录这段音频")
            result = await tool.run(params)

            assert result.success is True
            assert result.data == "这是转录的文本内容"

    @pytest.mark.asyncio
    async def test_run_missing_params(self):
        """测试缺少参数"""
        tool = AudioParseTool()

        params = AudioParseParams(audio_path="test.mp3", query="")
        result = await tool.run(params)
        assert result.success is False

        params = AudioParseParams(audio_path="", query="转录")
        result = await tool.run(params)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_run_file_not_found(self):
        """测试文件不存在"""
        tool = AudioParseTool()

        params = AudioParseParams(audio_path="/nonexistent/audio.mp3", query="转录")
        result = await tool.run(params)

        assert result.success is False
        assert "不存在" in result.error or "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_unsupported_format(self, tmp_path):
        """测试不支持的格式"""
        tool = AudioParseTool()

        audio_file = tmp_path / "test.xyz"
        audio_file.write_bytes(b"fake audio data")

        params = AudioParseParams(audio_path=str(audio_file), query="转录")
        result = await tool.run(params)

        assert result.success is False
        assert "不支持" in result.error or "unsupported" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_api_error(self, tmp_path, monkeypatch):
        """测试 API 错误"""
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        tool = AudioParseTool()

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        with patch.object(tool, '_get_openai_client', new_callable=AsyncMock) as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            params = AudioParseParams(audio_path=str(audio_file), query="转录")
            result = await tool.run(params)

            assert result.success is False
            assert "API Error" in result.error
