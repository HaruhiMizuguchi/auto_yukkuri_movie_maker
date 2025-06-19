"""
TTS処理モジュール 実API単体テスト

AIVIS Speech APIとの実際の連携とデータベース保存をテスト
"""

import asyncio
import json
import os
import tempfile
import pytest
import pytest_asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.modules.tts_processor import TTSProcessor
from src.dao.tts_generation_dao import TTSGenerationDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.config_manager import ConfigManager
from src.api.tts_client import AivisSpeechClient, TTSRequest, TTSResponse, TimestampData


@pytest_asyncio.fixture
async def real_tts_client():
    """実際のAIVIS Speech API クライアント"""
    client = AivisSpeechClient(base_url="http://127.0.0.1:10101")
    yield client
    await client.close()


@pytest.fixture
def mock_db_manager():
    """モックデータベースマネージャー"""
    mock = MagicMock(spec=DatabaseManager)
    
    # スクリプトデータをモック
    mock_script_data = {
        "segments": [
            {
                "segment_id": 1,
                "speaker": "reimu",
                "text": "こんにちは、今日はAIについて話しましょう。",
                "estimated_duration": 3.5,
                "emotion": "neutral"
            },
            {
                "segment_id": 2,
                "speaker": "marisa",
                "text": "面白そうだね！AIってどんなことができるの？",
                "estimated_duration": 3.2,
                "emotion": "happy"
            }
        ]
    }
    
    mock.fetch_one.return_value = (json.dumps(mock_script_data),)
    mock.execute_query.return_value = None
    
    return mock


@pytest.fixture
def mock_file_manager():
    """モックファイルシステムマネージャー"""
    mock = MagicMock(spec=FileSystemManager)
    
    # 一時ディレクトリパス
    temp_dir = tempfile.mkdtemp()
    mock.get_project_directory.return_value = temp_dir
    mock.create_project_directory.return_value = True
    mock.get_project_directory_path.return_value = Path(temp_dir)
    mock.create_file.return_value = True
    
    return mock


@pytest.fixture
def mock_config():
    """モック設定"""
    return {
        "voice_mapping": {
            "reimu": {"speaker_id": 0, "style": "normal"},
            "marisa": {"speaker_id": 1, "style": "cheerful"}
        },
        "audio_settings": {
            "sample_rate": 24000,
            "speed": 1.0,
            "pitch": 0.0,
            "volume": 1.0
        },
        "output_format": "wav"
    }


@pytest.fixture
def tts_processor(mock_db_manager, mock_file_manager, mock_config):
    """TTS処理モジュール"""
    dao = TTSGenerationDAO(mock_db_manager)
    config_manager = MagicMock(spec=ConfigManager)
    
    processor = TTSProcessor(
        dao=dao,
        file_manager=mock_file_manager,
        config_manager=config_manager
    )
    processor.config = mock_config
    
    return processor


class TestTTSProcessorRealAPI:
    """TTS処理モジュール実API統合テスト"""
    
    @pytest.mark.asyncio
    async def test_process_script_to_audio_real_api(self, tts_processor, real_tts_client):
        """スクリプトから音声生成（実API）"""
        project_id = "test_project_123"
        
        # 実際のAIVIS Speech クライアントをセット
        tts_processor.tts_client = real_tts_client
        
        try:
            # サーバーの動作確認
            speakers = await real_tts_client.get_speakers()
            assert len(speakers) > 0, "AIVIS Speech サーバーに話者が見つかりません"
            
            # TTS処理実行
            result = await tts_processor.process_script_to_audio(project_id)
            
            # 結果検証
            assert result is not None
            assert "audio_segments" in result
            assert "combined_audio_path" in result
            assert "audio_metadata" in result
            
            # オーディオセグメント検証
            segments = result["audio_segments"]
            assert len(segments) == 2  # reimu + marisa
            
            for segment in segments:
                assert "segment_id" in segment
                assert "speaker" in segment
                assert "audio_path" in segment
                assert "duration" in segment
                assert segment["duration"] > 0
            
            # メタデータ検証
            metadata = result["audio_metadata"]
            assert "total_duration" in metadata
            assert "sample_rate" in metadata
            assert "segments_info" in metadata
            assert metadata["total_duration"] > 0
            
        except Exception as e:
            # AIVIS Speech サーバーが動作していない場合はスキップ
            if "Connection" in str(e) or "ConnectTimeout" in str(e):
                pytest.skip(f"AIVIS Speech server not available: {e}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_generate_segment_audio_real_api(self, tts_processor, real_tts_client):
        """個別セグメント音声生成（実API）"""
        tts_processor.tts_client = real_tts_client
        
        try:
            # サーバー動作確認
            speakers = await real_tts_client.get_speakers()
            speaker_id = speakers[0]["styles"][0]["id"]
            
            # セグメント音声生成
            segment_data = {
                "segment_id": 1,
                "speaker": "reimu", 
                "text": "こんにちは、テストです。",
                "emotion": "neutral"
            }
            
            result = await tts_processor._generate_segment_audio(
                segment_data, 
                speaker_id, 
                "/tmp/test_audio.wav"
            )
            
            # 結果検証
            assert result is not None
            assert "duration" in result
            assert "timestamps" in result
            assert result["duration"] > 0
            
            # タイムスタンプ検証
            timestamps = result["timestamps"]
            assert len(timestamps) > 0
            for ts in timestamps:
                assert "start_time" in ts
                assert "end_time" in ts
                assert "text" in ts
                assert ts["start_time"] >= 0
                assert ts["end_time"] > ts["start_time"]
                
        except Exception as e:
            if "Connection" in str(e) or "ConnectTimeout" in str(e):
                pytest.skip(f"AIVIS Speech server not available: {e}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_combine_audio_segments(self, tts_processor):
        """音声セグメント結合テスト"""
        # モック音声ファイルパス
        segment_paths = [
            "/tmp/segment_1.wav",
            "/tmp/segment_2.wav"
        ]
        
        output_path = "/tmp/combined.wav"
        
        # 音声結合（実装に依存、モック可能）
        with patch.object(tts_processor, '_combine_audio_files') as mock_combine:
            mock_combine.return_value = {
                "duration": 6.7,
                "sample_rate": 24000,
                "file_size": 1024 * 1024
            }
            
            result = await tts_processor._combine_audio_segments(
                segment_paths, 
                output_path
            )
            
            # 結果検証
            assert result is not None
            assert "duration" in result
            assert result["duration"] > 0
            mock_combine.assert_called_once_with(segment_paths, output_path)
    
    @pytest.mark.asyncio
    async def test_database_integration(self, tts_processor):
        """データベース統合テスト"""
        project_id = "test_project_456"
        
        # TTS結果データ
        tts_result = {
            "audio_segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "audio_path": "/tmp/seg1.wav",
                    "duration": 3.5,
                    "timestamps": [
                        {"start_time": 0.0, "end_time": 1.2, "text": "こんにちは"}
                    ]
                }
            ],
            "combined_audio_path": "/tmp/combined.wav",
            "audio_metadata": {
                "total_duration": 6.7,
                "sample_rate": 24000,
                "segments_count": 2
            }
        }
        
        # データベース保存
        tts_processor.dao.save_tts_result(project_id, tts_result)
        
        # 保存が呼ばれたことを確認
        tts_processor.dao.db_manager.execute_query.assert_called()
        
        # 保存されたデータの検証
        call_args_list = tts_processor.dao.db_manager.execute_query.call_args_list
        call_args_str = str(call_args_list)
        assert project_id in call_args_str
        assert "tts_generation" in call_args_str 