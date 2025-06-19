"""
TTS処理モジュール 統合テスト

実際のデータベース操作とファイルシステムとの統合をテスト
"""

import asyncio
import json
import os
import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.modules.tts_processor import TTSProcessor, TTSResult
from src.dao.tts_generation_dao import TTSGenerationDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.config_manager import ConfigManager
from src.api.tts_client import AivisSpeechClient


@pytest.fixture
def db_manager():
    """実際のデータベースマネージャー（テスト用）"""
    db_path = ":memory:"  # インメモリデータベース
    manager = DatabaseManager(db_path)
    
    # テーブル初期化
    manager.initialize()
    
    return manager


@pytest.fixture
def file_manager():
    """実際のファイルシステムマネージャー（テスト用）"""
    temp_base_dir = tempfile.mkdtemp()
    manager = FileSystemManager(temp_base_dir)
    return manager


@pytest.fixture
def config_manager():
    """設定マネージャー"""
    return MagicMock(spec=ConfigManager)


@pytest.fixture
def mock_tts_client():
    """モックTTSクライアント"""
    mock_client = AsyncMock(spec=AivisSpeechClient)
    
    # モック音声レスポンス
    mock_response = MagicMock()
    mock_response.duration_seconds = 3.5
    mock_response.sample_rate = 24000
    mock_response.audio_length = 3.5
    mock_response.timestamps = [
        MagicMock(start_time=0.0, end_time=1.2, text="こんにちは", phoneme=None, confidence=0.95),
        MagicMock(start_time=1.2, end_time=2.8, text="テストです", phoneme=None, confidence=0.92)
    ]
    mock_response.save_audio = MagicMock()
    
    mock_client.generate_audio.return_value = mock_response
    mock_client.get_speakers.return_value = [
        {"styles": [{"id": 0}, {"id": 1}]}
    ]
    
    return mock_client


@pytest.fixture
def tts_processor(db_manager, file_manager, config_manager, mock_tts_client):
    """TTS処理モジュール（統合テスト用）"""
    dao = TTSGenerationDAO(db_manager)
    
    processor = TTSProcessor(
        dao=dao,
        file_manager=file_manager,
        config_manager=config_manager,
        tts_client=mock_tts_client
    )
    
    return processor


class TestTTSGenerationIntegration:
    """TTS処理統合テスト"""
    
    @pytest.mark.asyncio
    async def test_full_tts_workflow(self, tts_processor, db_manager, file_manager):
        """完全なTTSワークフローテスト"""
        project_id = "integration_test_project"
        
        # 1. プロジェクト作成
        db_manager.execute_query(
            "INSERT INTO projects (id, theme, target_length_minutes, config_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, "AIとテクノロジー", 5, json.dumps({
                "voice_config": {
                    "voice_mapping": {
                        "reimu": {"speaker_id": 0, "style": "normal"},
                        "marisa": {"speaker_id": 1, "style": "cheerful"}
                    }
                }
            }), datetime.now().isoformat())
        )
        
        # 2. スクリプト生成結果を事前に保存
        script_data = {
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
                    "text": "面白そうだね！AIの可能性は無限大だよ！",
                    "estimated_duration": 3.2,
                    "emotion": "happy"
                }
            ],
            "total_estimated_duration": 6.7
        }
        
        db_manager.execute_query(
            "INSERT INTO workflow_steps (project_id, step_number, step_name, status, output_data, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, 2, "script_generation", "completed", json.dumps(script_data), datetime.now().isoformat())
        )
        
        # 3. プロジェクトディレクトリを作成
        project_dir = file_manager.create_project_directory(project_id)
        
        # 4. TTS処理実行
        with patch.object(tts_processor, '_combine_audio_files') as mock_combine:
            mock_combine.return_value = {
                "duration": 6.7,
                "sample_rate": 24000,
                "file_size": 2048000
            }
            
            result = await tts_processor.process_script_to_audio(project_id)
        
        # 5. 結果検証
        assert result is not None
        assert "audio_segments" in result
        assert "combined_audio_path" in result
        assert "audio_metadata" in result
        
        # セグメント検証
        segments = result["audio_segments"]
        assert len(segments) == 2
        
        for i, segment in enumerate(segments):
            assert segment["segment_id"] == i + 1
            assert segment["speaker"] in ["reimu", "marisa"]
            assert segment["duration"] > 0
            assert len(segment["timestamps"]) > 0
            
            # 音声ファイルパス検証
            assert segment["audio_path"].endswith(".wav")
            assert project_id in segment["audio_path"]
        
        # メタデータ検証
        metadata = result["audio_metadata"]
        assert metadata["total_duration"] > 0
        assert metadata["segments_count"] == 2
        assert metadata["sample_rate"] == 24000
        assert len(metadata["segments_info"]) == 2
    
    @pytest.mark.asyncio
    async def test_database_persistence(self, tts_processor, db_manager):
        """データベース永続化テスト"""
        project_id = "persistence_test"
        
        # プロジェクトとスクリプト準備
        await self._setup_test_project_and_script(db_manager, project_id)
        
        # TTS処理実行
        with patch.object(tts_processor, '_combine_audio_files') as mock_combine:
            mock_combine.return_value = {"duration": 5.5, "sample_rate": 24000, "file_size": 1024000}
            
            result = await tts_processor.process_script_to_audio(project_id)
        
        # データベースから結果を取得
        saved_result = tts_processor.dao.get_tts_result(project_id)
        
        assert saved_result is not None
        assert saved_result["status"] == "completed"
        
        output_data = saved_result["output_data"]
        assert "audio_segments" in output_data
        assert "audio_metadata" in output_data
        assert output_data["audio_metadata"]["total_duration"] > 0
        
        # workflow_stepsテーブル確認
        workflow_result = db_manager.fetch_one(
            "SELECT step_name, status FROM workflow_steps WHERE project_id = ? AND step_name = 'tts_generation'",
            (project_id,)
        )
        assert workflow_result is not None
        assert workflow_result[1] == "completed"  # status
    
    @pytest.mark.asyncio
    async def test_file_registration(self, tts_processor, db_manager, file_manager):
        """ファイル登録テスト"""
        project_id = "file_registration_test"
        
        # プロジェクトとスクリプト準備
        await self._setup_test_project_and_script(db_manager, project_id)
        
        # プロジェクトディレクトリ作成
        file_manager.create_project_directory(project_id)
        
        # TTS処理実行
        with patch.object(tts_processor, '_combine_audio_files') as mock_combine:
            mock_combine.return_value = {"duration": 4.2, "sample_rate": 24000, "file_size": 896000}
            
            result = await tts_processor.process_script_to_audio(project_id)
        
        # データベースから登録ファイルを確認
        registered_files = tts_processor.dao.get_audio_files(project_id)
        
        assert len(registered_files) >= 3  # 2セグメント + 1結合ファイル
        
        # ファイルタイプ確認
        file_types = [f["file_type"] for f in registered_files]
        assert "audio" in file_types
        
        # ファイルカテゴリ確認
        categories = [f["file_category"] for f in registered_files]
        assert "intermediate" in categories  # セグメントファイル
        assert "output" in categories        # 結合ファイル
        
        # ファイルパス確認
        for file_info in registered_files:
            assert project_id in file_info["file_path"]
            assert file_info["file_name"].endswith(".wav")
    
    async def _setup_test_project_and_script(self, db_manager: DatabaseManager, project_id: str):
        """テスト用プロジェクトとスクリプトをセットアップ"""
        # プロジェクト作成
        db_manager.execute_query(
            "INSERT INTO projects (id, theme, target_length_minutes, config_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, "テストテーマ", 5, json.dumps({
                "voice_config": {
                    "voice_mapping": {
                        "reimu": {"speaker_id": 0},
                        "marisa": {"speaker_id": 1}
                    }
                }
            }), datetime.now().isoformat())
        )
        
        # スクリプト生成結果を保存
        script_data = {
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu", 
                    "text": "テストテキストです。",
                    "estimated_duration": 2.5,
                    "emotion": "neutral"
                },
                {
                    "segment_id": 2,
                    "speaker": "marisa",
                    "text": "これもテストです！",
                    "estimated_duration": 2.0,
                    "emotion": "happy"
                }
            ]
        }
        
        db_manager.execute_query(
            "INSERT INTO workflow_steps (project_id, step_number, step_name, status, output_data, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, 2, "script_generation", "completed", json.dumps(script_data), datetime.now().isoformat())
        ) 