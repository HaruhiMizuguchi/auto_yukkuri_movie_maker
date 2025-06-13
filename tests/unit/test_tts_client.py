"""
AIVIS Speech TTS クライアントのテスト
"""

import pytest
import json
import tempfile
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List
from pathlib import Path

from src.api.tts_client import (
    AivisSpeechClient,
    TTSRequest,
    TTSResponse,
    AudioSettings,
    TimestampData,
    TTSAPIError,
    InvalidSpeakerError,
    AudioGenerationError,
    SpeakerStyle
)
from src.core.api_client import APIResponse, NetworkError


class TestAudioSettings:
    """AudioSettings のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        settings = AudioSettings()
        
        assert settings.speaker_id == 0
        assert settings.speed == 1.0
        assert settings.pitch == 0.0
        assert settings.intonation == 1.0
        assert settings.volume == 1.0
        assert settings.pre_phoneme_length == 0.1
        assert settings.post_phoneme_length == 0.1
    
    def test_custom_values(self):
        """カスタム値設定テスト"""
        settings = AudioSettings(
            speaker_id=1,
            speed=1.2,
            pitch=0.1,
            intonation=1.1,
            volume=0.9,
            pre_phoneme_length=0.05,
            post_phoneme_length=0.15
        )
        
        assert settings.speaker_id == 1
        assert settings.speed == 1.2
        assert settings.pitch == 0.1
        assert settings.intonation == 1.1
        assert settings.volume == 0.9
        assert settings.pre_phoneme_length == 0.05
        assert settings.post_phoneme_length == 0.15


class TestTimestampData:
    """TimestampData のテスト"""
    
    def test_basic_data(self):
        """基本データテスト"""
        timestamp = TimestampData(
            start_time=0.0,
            end_time=0.5,
            text="こ",
            phoneme="k"
        )
        
        assert timestamp.start_time == 0.0
        assert timestamp.end_time == 0.5
        assert timestamp.text == "こ"
        assert timestamp.phoneme == "k"
        assert timestamp.confidence is None
    
    def test_with_confidence(self):
        """信頼度付きデータテスト"""
        timestamp = TimestampData(
            start_time=0.0,
            end_time=0.5,
            text="ん",
            phoneme="n",
            confidence=0.95
        )
        
        assert timestamp.confidence == 0.95


class TestTTSRequest:
    """TTSRequest のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        request = TTSRequest(text="テストです")
        
        assert request.text == "テストです"
        assert request.speaker_id == 0
        assert request.audio_settings is None
        assert request.enable_timestamps is True
        assert request.output_format == "wav"
    
    def test_custom_values(self):
        """カスタム値設定テスト"""
        settings = AudioSettings(speed=1.2)
        request = TTSRequest(
            text="カスタムテスト",
            speaker_id=1,
            audio_settings=settings,
            enable_timestamps=False,
            output_format="mp3"
        )
        
        assert request.text == "カスタムテスト"
        assert request.speaker_id == 1
        assert request.audio_settings == settings
        assert request.enable_timestamps is False
        assert request.output_format == "mp3"


class TestTTSResponse:
    """TTSResponse のテスト"""
    
    def test_basic_response(self):
        """基本レスポンステスト"""
        audio_data = b"fake_audio_data"
        timestamps = [
            TimestampData(0.0, 0.5, "て", "t"),
            TimestampData(0.5, 1.0, "す", "s")
        ]
        speaker_info = {"speaker_name": "テスト話者", "speaker_id": 0}
        
        response = TTSResponse(
            audio_data=audio_data,
            audio_length=2.5,
            sample_rate=24000,
            timestamps=timestamps,
            speaker_info=speaker_info
        )
        
        assert response.audio_data == audio_data
        assert response.audio_length == 2.5
        assert response.duration_seconds == 2.5
        assert response.sample_rate == 24000
        assert len(response.timestamps) == 2
        assert response.speaker_info == speaker_info
    
    def test_save_audio(self):
        """音声保存テスト"""
        audio_data = b"test_audio_content"
        response = TTSResponse(
            audio_data=audio_data,
            audio_length=1.0,
            sample_rate=24000,
            timestamps=[],
            speaker_info={}
        )
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
        
        try:
            response.save_audio(tmp_file_path)
            
            with open(tmp_file_path, 'rb') as f:
                saved_data = f.read()
            
            assert saved_data == audio_data
        finally:
            # クリーンアップ
            import os
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)


class TestTTSAPIErrors:
    """TTS API エラーのテスト"""
    
    def test_tts_api_error(self):
        """TTSAPIError テスト"""
        error = TTSAPIError("Test error", speaker_id=1)
        
        assert error.message == "Test error"
        assert error.speaker_id == 1
        assert error.context["speaker_id"] == 1
    
    def test_invalid_speaker_error(self):
        """InvalidSpeakerError テスト"""
        error = InvalidSpeakerError(999)
        
        assert "Invalid speaker ID: 999" in error.message
        assert error.error_code == "INVALID_SPEAKER"
        assert error.speaker_id == 999
        assert error.retry_recommended is False
    
    def test_audio_generation_error(self):
        """AudioGenerationError テスト"""
        error = AudioGenerationError("Generation failed", speaker_id=2)
        
        assert error.message == "Generation failed"
        assert error.error_code == "AUDIO_GENERATION_FAILED"
        assert error.speaker_id == 2
        assert error.retry_recommended is True


class TestAivisSpeechClient:
    """AivisSpeechClient のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        client = AivisSpeechClient()
        
        assert client.base_url == "http://127.0.0.1:10101"
        assert client.api_key is None
        assert client.rate_limit_config.requests_per_minute == 120
        assert client.rate_limit_config.requests_per_hour == 7200
    
    def test_initialization_custom_url(self):
        """カスタムURL初期化テスト"""
        custom_url = "http://localhost:8080"
        client = AivisSpeechClient(base_url=custom_url)
        
        assert client.base_url == custom_url
    
    @pytest.mark.asyncio
    async def test_get_speakers_success(self):
        """話者一覧取得成功テスト"""
        mock_speakers = [
            {
                "name": "テスト話者",
                "speaker_uuid": "test-uuid",
                "styles": [
                    {"id": 0, "name": "ノーマル"},
                    {"id": 1, "name": "喜び"}
                ]
            }
        ]
        
        mock_response = APIResponse(
            status_code=200,
            headers={},
            data=mock_speakers
        )
        
        client = AivisSpeechClient()
        
        with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            speakers = await client.get_speakers()
            
            assert speakers == mock_speakers
            assert client._available_speakers == mock_speakers
            
            # 2回目の呼び出しでキャッシュされることを確認
            speakers2 = await client.get_speakers()
            assert speakers2 == mock_speakers
            assert mock_send.call_count == 1  # キャッシュされるので1回のみ
    
    @pytest.mark.asyncio
    async def test_get_speakers_error(self):
        """話者一覧取得エラーテスト"""
        mock_response = APIResponse(
            status_code=500,
            headers={},
            data={"error": "Internal server error"}
        )
        
        client = AivisSpeechClient()
        
        with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            with pytest.raises(TTSAPIError) as exc_info:
                await client.get_speakers()
            
            assert exc_info.value.error_code == "GET_SPEAKERS_FAILED"
    
    @pytest.mark.asyncio
    async def test_validate_speaker_valid(self):
        """有効話者ID検証テスト"""
        mock_speakers = [
            {
                "name": "テスト話者",
                "styles": [
                    {"id": 0, "name": "ノーマル"},
                    {"id": 1, "name": "喜び"}
                ]
            }
        ]
        
        client = AivisSpeechClient()
        client._available_speakers = mock_speakers
        
        assert await client.validate_speaker(0) is True
        assert await client.validate_speaker(1) is True
        assert await client.validate_speaker(999) is False
    
    @pytest.mark.asyncio
    async def test_get_audio_query_success(self):
        """音声クエリ取得成功テスト"""
        mock_query_data = {
            "accent_phrases": [
                {
                    "moras": [
                        {"consonant": "k", "consonant_length": 0.1, "vowel": "o", "vowel_length": 0.2},
                        {"consonant": "n", "consonant_length": 0.1, "vowel": "n", "vowel_length": 0.15}
                    ]
                }
            ],
            "speedScale": 1.0,
            "pitchScale": 0.0,
            "intonationScale": 1.0,
            "volumeScale": 1.0,
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1
        }
        
        mock_response = APIResponse(
            status_code=200,
            headers={},
            data=mock_query_data
        )
        
        client = AivisSpeechClient()
        
        with patch.object(client, 'validate_speaker', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True
            
            with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = mock_response
                
                audio_settings = AudioSettings(speed=1.2, pitch=0.1)
                query_data = await client.get_audio_query(
                    text="こんにちは",
                    speaker_id=0,
                    audio_settings=audio_settings
                )
                
                assert query_data["speedScale"] == 1.2
                assert query_data["pitchScale"] == 0.1
                
                # リクエストパラメータの確認
                call_args = mock_send.call_args
                api_request = call_args[0][0]
                assert api_request.endpoint == "/audio_query"
                assert api_request.params["speaker"] == 0
                assert api_request.params["text"] == "こんにちは"
    
    @pytest.mark.asyncio
    async def test_get_audio_query_invalid_speaker(self):
        """音声クエリ取得無効話者テスト"""
        client = AivisSpeechClient()
        
        with patch.object(client, 'validate_speaker', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = False
            
            with pytest.raises(InvalidSpeakerError):
                await client.get_audio_query("テスト", 999)
    
    @pytest.mark.asyncio
    async def test_synthesize_audio_success(self):
        """音声合成成功テスト"""
        fake_audio_data = b"fake_wav_data"
        mock_response = APIResponse(
            status_code=200,
            headers={"content-type": "audio/wav"},
            data=None,
            raw_content=fake_audio_data
        )
        
        client = AivisSpeechClient()
        query_data = {"test": "data"}
        
        with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            audio_data = await client.synthesize_audio(query_data, 0)
            
            assert audio_data == fake_audio_data
            
            # リクエストパラメータの確認
            call_args = mock_send.call_args
            api_request = call_args[0][0]
            assert api_request.endpoint == "/synthesis"
            assert api_request.params["speaker"] == 0
            assert api_request.data == query_data
    
    @pytest.mark.asyncio
    async def test_synthesize_audio_error(self):
        """音声合成エラーテスト"""
        mock_response = APIResponse(
            status_code=400,
            headers={},
            data={"error": "Invalid query"}
        )
        
        client = AivisSpeechClient()
        
        with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            with pytest.raises(AudioGenerationError):
                await client.synthesize_audio({}, 0)
    
    @pytest.mark.asyncio
    async def test_generate_audio_success(self):
        """音声生成統合テスト成功"""
        # モックデータ
        mock_speakers = [{"name": "Test", "styles": [{"id": 0, "name": "Normal"}]}]
        mock_query_data = {
            "accent_phrases": [
                {
                    "moras": [
                        {"consonant": "k", "consonant_length": 0.1, "vowel": "o", "vowel_length": 0.2}
                    ]
                }
            ],
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1
        }
        fake_audio_data = b"generated_audio"
        
        client = AivisSpeechClient()
        client._available_speakers = mock_speakers
        
        with patch.object(client, 'get_audio_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_query_data
            
            with patch.object(client, 'synthesize_audio', new_callable=AsyncMock) as mock_synth:
                mock_synth.return_value = fake_audio_data
                
                request = TTSRequest(text="こんにちは", speaker_id=0)
                response = await client.generate_audio(request)
                
                assert response.audio_data == fake_audio_data
                assert response.audio_length > 0
                assert response.sample_rate == 24000
                assert len(response.timestamps) > 0
                assert response.speaker_info["speaker_id"] == 0
    
    def test_calculate_audio_length(self):
        """音声長さ計算テスト"""
        client = AivisSpeechClient()
        query_data = {
            "accent_phrases": [
                {
                    "moras": [
                        {"consonant_length": 0.1, "vowel_length": 0.2},
                        {"consonant_length": 0.05, "vowel_length": 0.15}
                    ]
                }
            ],
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1
        }
        
        length = client._calculate_audio_length(query_data)
        expected = 0.7
        assert abs(length - expected) < 1e-10
    
    def test_find_speaker_info(self):
        """話者情報検索テスト"""
        client = AivisSpeechClient()
        speakers = [
            {
                "name": "話者1",
                "speaker_uuid": "uuid1",
                "styles": [
                    {"id": 0, "name": "ノーマル"},
                    {"id": 1, "name": "喜び"}
                ]
            },
            {
                "name": "話者2",
                "speaker_uuid": "uuid2",
                "styles": [
                    {"id": 2, "name": "ノーマル"}
                ]
            }
        ]
        
        # 存在する話者
        info = client._find_speaker_info(speakers, 1)
        assert info["speaker_name"] == "話者1"
        assert info["style_name"] == "喜び"
        assert info["speaker_id"] == 1
        assert info["speaker_uuid"] == "uuid1"
        
        # 存在しない話者
        info = client._find_speaker_info(speakers, 999)
        assert info == {"speaker_id": 999}
    
    @pytest.mark.asyncio
    async def test_generate_timestamps(self):
        """タイムスタンプ生成テスト"""
        client = AivisSpeechClient()
        query_data = {
            "accent_phrases": [
                {
                    "moras": [
                        {
                            "consonant": "k",
                            "consonant_length": 0.1,
                            "vowel": "o",
                            "vowel_length": 0.2
                        },
                        {
                            "consonant": "n",
                            "consonant_length": 0.05,
                            "vowel": "n",
                            "vowel_length": 0.15
                        }
                    ]
                }
            ],
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1
        }
        
        timestamps = await client._generate_timestamps(query_data, "こん")
        
        # 4つのタイムスタンプ（k, o, n, n）が生成されることを確認
        assert len(timestamps) == 4
        
        # 最初のタイムスタンプ（k）
        assert timestamps[0].start_time == 0.1  # prePhonemeLength
        assert timestamps[0].end_time == 0.2
        assert timestamps[0].text == "k"
        assert timestamps[0].phoneme == "k"
        
        # 2番目のタイムスタンプ（o）
        assert timestamps[1].start_time == 0.2
        assert timestamps[1].end_time == 0.4
        assert timestamps[1].text == "o"
        assert timestamps[1].phoneme == "o"
    
    @pytest.mark.asyncio
    async def test_batch_generate_audio_success(self):
        """バッチ音声生成成功テスト"""
        client = AivisSpeechClient()
        
        mock_response = TTSResponse(
            audio_data=b"audio",
            audio_length=1.0,
            sample_rate=24000,
            timestamps=[],
            speaker_info={}
        )
        
        with patch.object(client, 'generate_audio', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response
            
            requests = [
                TTSRequest(text="テスト1", speaker_id=0),
                TTSRequest(text="テスト2", speaker_id=1)
            ]
            
            responses = await client.batch_generate_audio(requests)
            
            assert len(responses) == 2
            assert all(resp.audio_data == b"audio" for resp in responses)
            assert mock_generate.call_count == 2
    
    @pytest.mark.asyncio
    async def test_batch_generate_audio_with_error(self):
        """バッチ音声生成エラー処理テスト"""
        client = AivisSpeechClient()
        
        def mock_generate_side_effect(request):
            if request.text == "エラー":
                raise AudioGenerationError("Test error")
            return TTSResponse(
                audio_data=b"audio",
                audio_length=1.0,
                sample_rate=24000,
                timestamps=[],
                speaker_info={}
            )
        
        with patch.object(client, 'generate_audio', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = mock_generate_side_effect
            
            requests = [
                TTSRequest(text="成功", speaker_id=0),
                TTSRequest(text="エラー", speaker_id=1)
            ]
            
            responses = await client.batch_generate_audio(requests)
            
            assert len(responses) == 2
            assert responses[0].audio_data == b"audio"  # 成功
            assert responses[1].audio_data == b""  # エラー時は空
            assert responses[1].audio_length == 0.0
    
    @pytest.mark.asyncio
    async def test_close(self):
        """リソースクリーンアップテスト"""
        client = AivisSpeechClient()
        
        # セッションが None の場合
        await client.close()
        
        # セッションがある場合
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session
        
        await client.close()
        
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """コンテキストマネージャーテスト"""
        async with AivisSpeechClient() as client:
            assert isinstance(client, AivisSpeechClient)
        
        # __aexit__ で close が呼ばれることを確認
        with patch.object(client, 'close', new_callable=AsyncMock) as mock_close:
            async with client:
                pass
            mock_close.assert_called_once()


# パフォーマンステスト
class TestPerformance:
    """パフォーマンステスト"""
    
    def test_timestamp_generation_performance(self):
        """タイムスタンプ生成パフォーマンステスト"""
        client = AivisSpeechClient()
        
        # 大きなクエリデータ
        large_query_data = {
            "accent_phrases": [
                {
                    "moras": [
                        {"consonant": "k", "consonant_length": 0.1, "vowel": "o", "vowel_length": 0.2}
                        for _ in range(100)
                    ]
                }
                for _ in range(10)
            ],
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1
        }
        
        import time
        import asyncio
        
        async def test_performance():
            start_time = time.time()
            
            for _ in range(10):
                await client._generate_timestamps(large_query_data, "テスト" * 100)
            
            end_time = time.time()
            
            # 10回の処理が2秒以内で完了することを確認
            assert end_time - start_time < 2.0
        
        asyncio.run(test_performance())
    
    def test_audio_length_calculation_performance(self):
        """音声長さ計算パフォーマンステスト"""
        client = AivisSpeechClient()
        
        # 大きなクエリデータ
        large_query_data = {
            "accent_phrases": [
                {
                    "moras": [
                        {"consonant_length": 0.1, "vowel_length": 0.2}
                        for _ in range(1000)
                    ]
                }
                for _ in range(10)
            ],
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1
        }
        
        import time
        start_time = time.time()
        
        for _ in range(100):
            client._calculate_audio_length(large_query_data)
        
        end_time = time.time()
        
        # 100回の処理が1秒以内で完了することを確認
        assert end_time - start_time < 1.0 