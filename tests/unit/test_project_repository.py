"""
ProjectRepository tests - プロジェクトデータアクセス機能のテスト

プロジェクト作成・取得・更新、ワークフローステップ管理、
ファイル参照の登録・取得のテストケース
"""

import os
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.core.project_repository import ProjectRepository, ProjectDataAccessError
from src.core.database_manager import DatabaseManager


class TestProjectRepository:
    """ProjectRepository テストクラス"""
    
    @pytest.fixture
    def temp_db_path(self):
        """テスト用一時データベースパス"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_repository.db")
        yield db_path
        # クリーンアップ
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def db_manager(self, temp_db_path):
        """テスト用DatabaseManager"""
        manager = DatabaseManager(temp_db_path)
        manager.initialize()
        yield manager
        manager.close()
    
    @pytest.fixture
    def repository(self, db_manager):
        """テスト用ProjectRepository"""
        return ProjectRepository(db_manager)
    
    # テスト 1-4-2-1: プロジェクト基本操作テスト
    def test_create_project_success(self, repository):
        """プロジェクト作成の成功テスト"""
        project_data = {
            "project_id": "test_project_001",
            "theme": "テスト動画のテーマ",
            "target_length_minutes": 7.5,
            "config": {
                "genre": "programming",
                "tone": "casual"
            }
        }
        
        result = repository.create_project(**project_data)
        
        assert result is True
        
        # 作成されたプロジェクトを確認
        project = repository.get_project("test_project_001")
        assert project is not None
        assert project["id"] == "test_project_001"
        assert project["theme"] == "テスト動画のテーマ"
        assert project["target_length_minutes"] == 7.5
        assert project["status"] == "created"
    
    def test_create_project_duplicate_error(self, repository):
        """重複プロジェクト作成時のエラーテスト"""
        project_data = {
            "project_id": "duplicate_test",
            "theme": "重複テスト",
            "target_length_minutes": 5.0
        }
        
        # 最初の作成は成功
        assert repository.create_project(**project_data) is True
        
        # 同じIDで再作成はエラー
        with pytest.raises(ProjectDataAccessError) as exc_info:
            repository.create_project(**project_data)
        assert "already exists" in str(exc_info.value)
    
    def test_get_project_not_found(self, repository):
        """存在しないプロジェクト取得時のNone返却テスト"""
        result = repository.get_project("non_existent_project")
        assert result is None
    
    def test_update_project_success(self, repository):
        """プロジェクト更新の成功テスト"""
        # プロジェクト作成
        repository.create_project(
            "update_test",
            "更新テスト",
            5.0
        )
        
        # 更新実行
        updates = {
            "theme": "更新されたテーマ",
            "target_length_minutes": 8.0,
            "status": "in_progress"
        }
        
        result = repository.update_project("update_test", **updates)
        assert result is True
        
        # 更新確認
        project = repository.get_project("update_test")
        assert project["theme"] == "更新されたテーマ"
        assert project["target_length_minutes"] == 8.0
        assert project["status"] == "in_progress"
    
    def test_update_project_not_found(self, repository):
        """存在しないプロジェクト更新時のエラーテスト"""
        with pytest.raises(ProjectDataAccessError) as exc_info:
            repository.update_project("non_existent", theme="新テーマ")
        assert "not found" in str(exc_info.value)
    
    # テスト 1-4-2-2: ワークフローステップ管理テスト
    def test_create_workflow_step_success(self, repository):
        """ワークフローステップ作成の成功テスト"""
        # プロジェクト作成
        repository.create_project("workflow_test", "ワークフローテスト", 5.0)
        
        # ステップ作成
        step_data = {
            "step_number": 1,
            "step_name": "theme_selection",
            "input_data": {"user_preferences": {"genre": "tech"}},
            "status": "pending"
        }
        
        result = repository.create_workflow_step("workflow_test", **step_data)
        assert result is True
        
        # 作成確認
        step = repository.get_workflow_step("workflow_test", "theme_selection")
        assert step is not None
        assert step["step_number"] == 1
        assert step["step_name"] == "theme_selection"
        assert step["status"] == "pending"
    
    def test_update_workflow_step_status(self, repository):
        """ワークフローステップステータス更新テスト"""
        # プロジェクトとステップ作成
        repository.create_project("status_test", "ステータステスト", 5.0)
        repository.create_workflow_step(
            "status_test",
            step_number=1,
            step_name="script_generation",
            status="pending"
        )
        
        # ステータス更新
        result = repository.update_workflow_step_status(
            "status_test",
            "script_generation", 
            "running"
        )
        assert result is True
        
        # 更新確認
        step = repository.get_workflow_step("status_test", "script_generation")
        assert step["status"] == "running"
        assert step["started_at"] is not None
    
    def test_save_step_result(self, repository):
        """ステップ実行結果保存テスト"""
        # プロジェクトとステップ作成
        repository.create_project("result_test", "結果テスト", 5.0)
        repository.create_workflow_step(
            "result_test",
            step_number=2,
            step_name="tts_generation",
            status="running"
        )
        
        # 結果保存
        output_data = {
            "generated_files": ["audio_01.wav", "audio_02.wav"],
            "total_duration": 45.5,
            "quality_score": 0.95
        }
        
        result = repository.save_step_result(
            "result_test",
            "tts_generation",
            output_data,
            status="completed"
        )
        assert result is True
        
        # 結果確認
        step = repository.get_workflow_step("result_test", "tts_generation")
        assert step["status"] == "completed"
        assert step["completed_at"] is not None
        
        output = json.loads(step["output_data"])
        assert output["total_duration"] == 45.5
        assert len(output["generated_files"]) == 2
    
    def test_get_step_input_from_previous(self, repository):
        """前ステップ出力の取得テスト"""
        # プロジェクト・ステップ作成
        repository.create_project("input_test", "入力テスト", 5.0)
        repository.create_workflow_step(
            "input_test",
            step_number=1,
            step_name="theme_selection",
            status="completed"
        )
        
        # 前ステップ結果保存
        previous_output = {
            "selected_theme": "プログラミング解説",
            "target_duration": 300
        }
        repository.save_step_result(
            "input_test",
            "theme_selection",
            previous_output,
            status="completed"
        )
        
        # 次ステップで前ステップ出力を取得
        input_data = repository.get_step_input("input_test", "script_generation")
        
        assert input_data is not None
        assert input_data["selected_theme"] == "プログラミング解説"
        assert input_data["target_duration"] == 300
    
    # テスト 1-4-2-3: ファイル参照管理テスト
    def test_register_file_reference_success(self, repository):
        """ファイル参照登録の成功テスト"""
        # プロジェクト作成
        repository.create_project("file_test", "ファイルテスト", 5.0)
        
        # ファイル参照登録
        file_data = {
            "file_type": "script",
            "file_category": "output",
            "file_path": "files/scripts/script.json",
            "file_name": "script.json",
            "file_size": 2048,
            "mime_type": "application/json",
            "metadata": {"version": "1.0", "encoding": "utf-8"}
        }
        
        file_id = repository.register_file_reference("file_test", **file_data)
        
        assert file_id is not None
        assert isinstance(file_id, int)
        
        # 登録確認
        file_info = repository.get_file_reference(file_id)
        assert file_info is not None
        assert file_info["file_type"] == "script"
        assert file_info["file_path"] == "files/scripts/script.json"
        assert file_info["file_size"] == 2048
    
    def test_get_files_by_query(self, repository):
        """ファイルクエリ検索テスト"""
        # プロジェクト作成
        repository.create_project("query_test", "クエリテスト", 5.0)
        
        # 複数ファイル登録
        files_data = [
            {
                "file_type": "audio",
                "file_category": "intermediate",
                "file_path": "files/audio/segment_01.wav",
                "file_name": "segment_01.wav",
                "file_size": 1024000
            },
            {
                "file_type": "audio", 
                "file_category": "output",
                "file_path": "files/audio/combined.wav",
                "file_name": "combined.wav",
                "file_size": 5120000
            },
            {
                "file_type": "script",
                "file_category": "output",
                "file_path": "files/scripts/final_script.json",
                "file_name": "final_script.json",
                "file_size": 4096
            }
        ]
        
        for file_data in files_data:
            repository.register_file_reference("query_test", **file_data)
        
        # 音声ファイルのみ検索
        audio_files = repository.get_files_by_query(
            "query_test",
            file_type="audio"
        )
        assert len(audio_files) == 2
        assert all(f["file_type"] == "audio" for f in audio_files)
        
        # 出力ファイルのみ検索
        output_files = repository.get_files_by_query(
            "query_test",
            file_category="output"
        )
        assert len(output_files) == 2
        assert all(f["file_category"] == "output" for f in output_files)
    
    def test_update_file_metadata(self, repository):
        """ファイルメタデータ更新テスト"""
        # プロジェクト・ファイル作成
        repository.create_project("metadata_test", "メタデータテスト", 5.0)
        file_id = repository.register_file_reference(
            "metadata_test",
            file_type="video",
            file_category="intermediate",
            file_path="files/video/test.mp4",
            file_name="test.mp4",
            file_size=10240000,
            metadata={"duration": 120.0, "fps": 30}
        )
        
        # メタデータ更新
        new_metadata = {
            "duration": 125.5,
            "fps": 30,
            "resolution": "1920x1080",
            "bitrate": 5000
        }
        
        result = repository.update_file_metadata(file_id, new_metadata)
        assert result is True
        
        # 更新確認
        file_info = repository.get_file_reference(file_id)
        metadata = json.loads(file_info["metadata"])
        assert metadata["duration"] == 125.5
        assert metadata["resolution"] == "1920x1080"
        assert metadata["bitrate"] == 5000
    
    # テスト 1-4-2-4: プロジェクト状態管理テスト
    def test_get_project_status(self, repository):
        """プロジェクト全体状況取得テスト"""
        # プロジェクト・複数ステップ作成
        repository.create_project("status_overview_test", "状況テスト", 5.0)
        
        steps_data = [
            {"step_number": 1, "step_name": "theme_selection", "status": "completed"},
            {"step_number": 2, "step_name": "script_generation", "status": "running"},
            {"step_number": 3, "step_name": "tts_generation", "status": "pending"}
        ]
        
        for step_data in steps_data:
            repository.create_workflow_step("status_overview_test", **step_data)
        
        # ファイル登録
        repository.register_file_reference(
            "status_overview_test",
            file_type="script",
            file_category="output",
            file_path="files/scripts/script.json",
            file_name="script.json",
            file_size=2048
        )
        
        # 状況取得
        status = repository.get_project_status("status_overview_test")
        
        assert status is not None
        assert status["project"]["id"] == "status_overview_test"
        assert len(status["workflow_steps"]) == 3
        assert len(status["files"]) == 1
        
        # ステップ状況確認
        completed_steps = [s for s in status["workflow_steps"] if s["status"] == "completed"]
        running_steps = [s for s in status["workflow_steps"] if s["status"] == "running"]
        pending_steps = [s for s in status["workflow_steps"] if s["status"] == "pending"]
        
        assert len(completed_steps) == 1
        assert len(running_steps) == 1  
        assert len(pending_steps) == 1
    
    def test_delete_project_cascade(self, repository):
        """プロジェクト削除のカスケードテスト"""
        # プロジェクト・ステップ・ファイル作成
        repository.create_project("delete_test", "削除テスト", 5.0)
        repository.create_workflow_step(
            "delete_test",
            step_number=1,
            step_name="theme_selection",
            status="completed"
        )
        repository.register_file_reference(
            "delete_test",
            file_type="script",
            file_category="output", 
            file_path="files/scripts/script.json",
            file_name="script.json",
            file_size=1024
        )
        
        # 削除前確認
        assert repository.get_project("delete_test") is not None
        assert repository.get_workflow_step("delete_test", "theme_selection") is not None
        
        # プロジェクト削除
        result = repository.delete_project("delete_test")
        assert result is True
        
        # 削除確認
        assert repository.get_project("delete_test") is None
        assert repository.get_workflow_step("delete_test", "theme_selection") is None
    
    # テスト 1-4-2-5: エラーハンドリングテスト  
    def test_database_error_handling(self, repository):
        """データベースエラーハンドリングテスト"""
        # データベース接続をモック化してエラーを発生させる
        with patch.object(repository.db_manager, 'get_connection') as mock_conn:
            mock_conn.side_effect = Exception("Database connection failed")
            
            with pytest.raises(ProjectDataAccessError) as exc_info:
                repository.get_project("any_project")
            
            assert "Database error" in str(exc_info.value)
    
    def test_invalid_json_data_handling(self, repository):
        """不正JSON データハンドリングテスト"""
        repository.create_project("json_test", "JSONテスト", 5.0)
        
        # 不正なJSONデータでステップ作成を試行
        with pytest.raises(ProjectDataAccessError) as exc_info:
            repository.create_workflow_step(
                "json_test",
                step_number=1,
                step_name="test_step",
                input_data="invalid json string"  # 辞書ではなく文字列
            )
        
        assert "Invalid data format" in str(exc_info.value) 