"""
DataIntegrationManager tests - データ統合管理機能のテスト

メタデータ←→ファイル同期、整合性チェック、
バックアップ・復元のテストケース
"""

import os
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.core.data_integration_manager import DataIntegrationManager, DataIntegrationError
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.file_system_manager import FileSystemManager


class TestDataIntegrationManager:
    """DataIntegrationManager テストクラス"""
    
    @pytest.fixture
    def temp_dirs(self):
        """テスト用一時ディレクトリ"""
        temp_db_dir = tempfile.mkdtemp()
        temp_fs_dir = tempfile.mkdtemp()
        yield temp_db_dir, temp_fs_dir
        # クリーンアップ
        for temp_dir in [temp_db_dir, temp_fs_dir]:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def db_manager(self, temp_dirs):
        """テスト用DatabaseManager"""
        temp_db_dir, _ = temp_dirs
        db_path = os.path.join(temp_db_dir, "test_integration.db")
        manager = DatabaseManager(db_path)
        manager.initialize()
        yield manager
        manager.close()
    
    @pytest.fixture
    def repository(self, db_manager):
        """テスト用ProjectRepository"""
        return ProjectRepository(db_manager)
    
    @pytest.fixture
    def fs_manager(self, temp_dirs):
        """テスト用FileSystemManager"""
        _, temp_fs_dir = temp_dirs
        return FileSystemManager(base_directory=temp_fs_dir)
    
    @pytest.fixture
    def integration_manager(self, repository, fs_manager):
        """テスト用DataIntegrationManager"""
        return DataIntegrationManager(repository, fs_manager)
    
    # テスト 1-4-4-1: メタデータ←→ファイル同期テスト
    def test_sync_metadata_to_files_success(self, integration_manager, repository, fs_manager):
        """メタデータからファイルへの同期成功テスト"""
        # プロジェクト・ファイル参照作成
        project_id = "sync_test_001"
        repository.create_project(project_id, "同期テスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # ファイル参照をDBに登録
        file_id = repository.register_file_reference(
            project_id,
            file_type="script",
            file_category="output",
            file_path="files/scripts/test_script.json",
            file_name="test_script.json",
            file_size=1024,
            metadata={"version": "1.0", "encoding": "utf-8"}
        )
        
        # 同期実行
        result = integration_manager.sync_metadata_to_files(project_id)
        
        assert result is True
        
        # 同期結果の確認
        sync_report = integration_manager.get_last_sync_report()
        assert sync_report is not None
        assert sync_report["project_id"] == project_id
        assert sync_report["direction"] == "metadata_to_files"
        assert sync_report["status"] == "success"
    
    def test_sync_files_to_metadata_success(self, integration_manager, repository, fs_manager):
        """ファイルからメタデータへの同期成功テスト"""
        # プロジェクト作成
        project_id = "sync_test_002"
        repository.create_project(project_id, "逆同期テスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 実際のファイル作成
        test_content = {"message": "Hello World", "timestamp": "2024-01-01T00:00:00"}
        fs_manager.create_file(
            project_id,
            "files/scripts/real_script.json",
            json.dumps(test_content)
        )
        
        # 同期実行（ファイル→メタデータ）
        result = integration_manager.sync_files_to_metadata(project_id)
        
        assert result is True
        
        # DBにファイル情報が登録されたことを確認
        files = repository.get_files_by_query(project_id, file_type="script")
        assert len(files) >= 1
        
        # 同期レポート確認
        sync_report = integration_manager.get_last_sync_report()
        assert sync_report["direction"] == "files_to_metadata"
        assert sync_report["status"] == "success"
    
    def test_bidirectional_sync_success(self, integration_manager, repository, fs_manager):
        """双方向同期の成功テスト"""
        # プロジェクト作成
        project_id = "bidirectional_test"
        repository.create_project(project_id, "双方向同期テスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 初期データ設定
        # DB側にファイル参照追加
        repository.register_file_reference(
            project_id,
            file_type="audio",
            file_category="output",
            file_path="files/audio/test_audio.wav",
            file_name="test_audio.wav",
            file_size=2048000
        )
        
        # FS側にファイル追加
        fs_manager.create_file(
            project_id,
            "files/video/test_video.mp4",
            b"\x00\x01\x02\x03"  # ダミーバイナリ
        )
        
        # 双方向同期実行
        result = integration_manager.sync_bidirectional(project_id)
        
        assert result is True
        
        # 同期後の状態確認
        # DBにビデオファイル情報が追加されている
        video_files = repository.get_files_by_query(project_id, file_type="video")
        assert len(video_files) >= 1
        
        # レポート確認
        sync_report = integration_manager.get_last_sync_report()
        assert sync_report["direction"] == "bidirectional"
        assert sync_report["status"] == "success"
    
    def test_sync_conflict_detection(self, integration_manager, repository, fs_manager):
        """同期コンフリクト検出テスト"""
        # プロジェクト作成
        project_id = "conflict_test"
        repository.create_project(project_id, "コンフリクトテスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 同じパスに異なるファイルサイズで登録
        file_path = "files/scripts/conflict_file.json"
        
        # DB登録（小さいサイズ）
        repository.register_file_reference(
            project_id,
            file_type="script",
            file_category="output",
            file_path=file_path,
            file_name="conflict_file.json",
            file_size=100
        )
        
        # FS作成（大きいサイズ）
        large_content = "x" * 500
        fs_manager.create_file(project_id, file_path, large_content)
        
        # 同期実行（コンフリクト発生）
        result = integration_manager.sync_bidirectional(project_id)
        
        # 同期は成功するが、コンフリクトが検出される
        assert result is True
        
        # コンフリクトレポート確認
        sync_report = integration_manager.get_last_sync_report()
        assert len(sync_report.get("conflicts", [])) > 0
        
        conflict = sync_report["conflicts"][0]
        assert conflict["file_path"] == file_path
        assert conflict["type"] == "size_mismatch"
    
    # テスト 1-4-4-2: 整合性チェックテスト
    def test_integrity_check_success(self, integration_manager, repository, fs_manager):
        """整合性チェック成功テスト"""
        # プロジェクト・データ作成
        project_id = "integrity_test"
        repository.create_project(project_id, "整合性テスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 整合性のあるデータ作成
        test_content = "test content for integrity"
        file_path = "files/metadata/integrity_test.txt"
        
        # ファイル作成
        fs_manager.create_file(project_id, file_path, test_content)
        
        # DB登録（正確なサイズで）
        repository.register_file_reference(
            project_id,
            file_type="metadata",
            file_category="output",
            file_path=file_path,
            file_name="integrity_test.txt",
            file_size=len(test_content.encode('utf-8'))
        )
        
        # 整合性チェック実行
        integrity_report = integration_manager.check_integrity(project_id)
        
        assert integrity_report is not None
        assert integrity_report["status"] == "success"
        assert integrity_report["total_files"] == 1
        assert integrity_report["consistent_files"] == 1
        assert len(integrity_report["inconsistencies"]) == 0
    
    def test_integrity_check_missing_files(self, integration_manager, repository, fs_manager):
        """ファイル不整合検出テスト"""
        # プロジェクト作成
        project_id = "missing_files_test"
        repository.create_project(project_id, "不整合テスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # DBにのみファイル参照を登録（実ファイルなし）
        repository.register_file_reference(
            project_id,
            file_type="audio",
            file_category="output",
            file_path="files/audio/missing_audio.wav",
            file_name="missing_audio.wav",
            file_size=1024000
        )
        
        # 整合性チェック実行
        integrity_report = integration_manager.check_integrity(project_id)
        
        assert integrity_report["status"] == "inconsistent"
        assert integrity_report["total_files"] == 1
        assert integrity_report["consistent_files"] == 0
        assert len(integrity_report["inconsistencies"]) == 1
        
        inconsistency = integrity_report["inconsistencies"][0]
        assert inconsistency["type"] == "missing_file"
        assert inconsistency["file_path"] == "files/audio/missing_audio.wav"
    
    def test_integrity_check_orphaned_files(self, integration_manager, repository, fs_manager):
        """孤立ファイル検出テスト"""
        # プロジェクト作成
        project_id = "orphaned_files_test"
        repository.create_project(project_id, "孤立ファイルテスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # ファイルのみ作成（DB登録なし）
        fs_manager.create_file(
            project_id,
            "files/video/orphaned_video.mp4",
            b"\x00\x01\x02\x03\x04"
        )
        
        # 整合性チェック実行
        integrity_report = integration_manager.check_integrity(project_id)
        
        assert integrity_report["status"] == "inconsistent"
        assert len(integrity_report["orphaned_files"]) == 1
        
        orphaned = integrity_report["orphaned_files"][0]
        assert "orphaned_video.mp4" in orphaned["file_path"]
    
    def test_auto_repair_integrity(self, integration_manager, repository, fs_manager):
        """自動修復機能テスト"""
        # プロジェクト作成
        project_id = "auto_repair_test"
        repository.create_project(project_id, "自動修復テスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 不整合データ作成
        # 1. 孤立ファイル（FS only）
        fs_manager.create_file(
            project_id,
            "files/scripts/orphaned.json",
            '{"orphaned": true}'
        )
        
        # 2. DB only ファイル（missing file）
        repository.register_file_reference(
            project_id,
            file_type="audio",
            file_category="output",
            file_path="files/audio/phantom.wav",
            file_name="phantom.wav",
            file_size=1000
        )
        
        # 自動修復実行
        repair_result = integration_manager.auto_repair_integrity(project_id)
        
        assert repair_result is True
        
        # 修復後の状態確認
        post_repair_report = integration_manager.check_integrity(project_id)
        
        # 孤立ファイルがDBに登録されている
        orphaned_files = repository.get_files_by_query(project_id, file_type="script")
        assert len(orphaned_files) >= 1
        
        # 修復レポート確認
        repair_report = integration_manager.get_last_repair_report()
        assert repair_report is not None
        assert repair_report["project_id"] == project_id
        assert repair_report["repaired_items"] > 0
    
    # テスト 1-4-4-3: バックアップ・復元テスト
    def test_create_project_backup_success(self, integration_manager, repository, fs_manager, temp_dirs):
        """プロジェクトバックアップ作成成功テスト"""
        _, temp_fs_dir = temp_dirs
        
        # プロジェクト・データ作成
        project_id = "backup_test"
        repository.create_project(project_id, "バックアップテスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # テストファイル作成
        test_files = [
            ("files/scripts/script1.json", '{"version": "1.0"}'),
            ("files/audio/audio1.wav", b"\x00\x01\x02\x03"),
            ("files/metadata/meta1.json", '{"meta": "data"}')
        ]
        
        for file_path, content in test_files:
            if isinstance(content, str):
                fs_manager.create_file(project_id, file_path, content)
                file_size = len(content.encode('utf-8'))
            else:
                fs_manager.create_file(project_id, file_path, content)
                file_size = len(content)
            
            # DB登録
            repository.register_file_reference(
                project_id,
                file_type=file_path.split('/')[1].rstrip('s'),  # audio, script, metadata
                file_category="output",
                file_path=file_path,
                file_name=Path(file_path).name,
                file_size=file_size
            )
        
        # バックアップ作成
        backup_path = os.path.join(temp_fs_dir, f"{project_id}_backup.zip")
        result = integration_manager.create_project_backup(project_id, backup_path)
        
        assert result is True
        assert os.path.exists(backup_path)
        
        # バックアップファイルサイズ確認
        backup_size = os.path.getsize(backup_path)
        assert backup_size > 0
    
    def test_restore_project_from_backup(self, integration_manager, repository, fs_manager, temp_dirs):
        """バックアップからの復元テスト"""
        _, temp_fs_dir = temp_dirs
        
        # 元プロジェクト作成・バックアップ
        original_project_id = "restore_source"
        repository.create_project(original_project_id, "復元元プロジェクト", 7.0)
        fs_manager.create_project_directory(original_project_id)
        
        # データ作成
        original_content = '{"original": "data", "timestamp": "2024-01-01T00:00:00"}'
        fs_manager.create_file(
            original_project_id,
            "files/scripts/original.json",
            original_content
        )
        
        repository.register_file_reference(
            original_project_id,
            file_type="script",
            file_category="output",
            file_path="files/scripts/original.json",
            file_name="original.json",
            file_size=len(original_content.encode('utf-8'))
        )
        
        # バックアップ作成
        backup_path = os.path.join(temp_fs_dir, "restore_test_backup.zip")
        integration_manager.create_project_backup(original_project_id, backup_path)
        
        # 新プロジェクトとして復元
        restored_project_id = "restore_target"
        result = integration_manager.restore_project_from_backup(
            backup_path,
            restored_project_id
        )
        
        assert result is True
        
        # 復元後の確認
        restored_project = repository.get_project(restored_project_id)
        assert restored_project is not None
        assert restored_project["theme"] == "復元元プロジェクト"
        
        # ファイル復元確認
        restored_content = fs_manager.read_file(
            restored_project_id,
            "files/scripts/original.json"
        )
        assert restored_content == original_content
        
        # DB情報復元確認
        restored_files = repository.get_files_by_query(restored_project_id)
        assert len(restored_files) >= 1
    
    def test_incremental_backup(self, integration_manager, repository, fs_manager, temp_dirs):
        """増分バックアップテスト"""
        _, temp_fs_dir = temp_dirs
        
        # プロジェクト作成
        project_id = "incremental_test"
        repository.create_project(project_id, "増分バックアップテスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 初期ファイル
        fs_manager.create_file(
            project_id,
            "files/scripts/initial.json",
            '{"initial": true}'
        )
        
        # フルバックアップ作成
        full_backup_path = os.path.join(temp_fs_dir, "full_backup.zip")
        integration_manager.create_project_backup(project_id, full_backup_path)
        
        # 追加ファイル
        fs_manager.create_file(
            project_id,
            "files/scripts/additional.json",
            '{"additional": true}'
        )
        
        # 増分バックアップ作成
        incremental_backup_path = os.path.join(temp_fs_dir, "incremental_backup.zip")
        result = integration_manager.create_incremental_backup(
            project_id,
            incremental_backup_path,
            full_backup_path
        )
        
        assert result is True
        assert os.path.exists(incremental_backup_path)
        
        # 増分バックアップサイズがフルバックアップより小さいことを確認
        full_size = os.path.getsize(full_backup_path)
        incremental_size = os.path.getsize(incremental_backup_path)
        assert incremental_size < full_size
    
    # テスト 1-4-4-4: エラーハンドリングテスト
    def test_sync_with_missing_project(self, integration_manager):
        """存在しないプロジェクトの同期エラーテスト"""
        with pytest.raises(DataIntegrationError) as exc_info:
            integration_manager.sync_metadata_to_files("non_existent_project")
        
        assert "Project not found" in str(exc_info.value)
    
    def test_backup_with_invalid_path(self, integration_manager, repository, fs_manager):
        """不正パスでのバックアップエラーテスト"""
        # プロジェクト作成
        project_id = "backup_error_test"
        repository.create_project(project_id, "バックアップエラーテスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 不正なバックアップパス
        invalid_backup_path = "/invalid/path/backup.zip"
        
        with pytest.raises(DataIntegrationError) as exc_info:
            integration_manager.create_project_backup(project_id, invalid_backup_path)
        
        assert "Failed to create backup" in str(exc_info.value)
    
    def test_restore_with_corrupted_backup(self, integration_manager):
        """破損バックアップからの復元エラーテスト"""
        # 破損したバックアップファイル作成
        corrupted_backup_path = tempfile.mktemp(suffix=".zip")
        with open(corrupted_backup_path, 'w') as f:
            f.write("This is not a valid zip file")
        
        try:
            with pytest.raises(DataIntegrationError) as exc_info:
                integration_manager.restore_project_from_backup(
                    corrupted_backup_path,
                    "corrupted_restore_test"
                )
            
            assert "Failed to restore from backup" in str(exc_info.value)
            
        finally:
            # クリーンアップ
            if os.path.exists(corrupted_backup_path):
                os.unlink(corrupted_backup_path)
    
    def test_concurrent_operation_handling(self, integration_manager, repository, fs_manager):
        """並行操作処理テスト"""
        # プロジェクト作成
        project_id = "concurrent_test"
        repository.create_project(project_id, "並行操作テスト", 5.0)
        fs_manager.create_project_directory(project_id)
        
        # 操作ロック取得のテスト
        lock_acquired = integration_manager.acquire_operation_lock(project_id)
        assert lock_acquired is True
        
        # 同じプロジェクトでの重複ロック試行
        duplicate_lock = integration_manager.acquire_operation_lock(project_id)
        assert duplicate_lock is False
        
        # ロック解放
        integration_manager.release_operation_lock(project_id)
        
        # 解放後の再取得
        new_lock = integration_manager.acquire_operation_lock(project_id)
        assert new_lock is True
        
        # 最終クリーンアップ
        integration_manager.release_operation_lock(project_id) 