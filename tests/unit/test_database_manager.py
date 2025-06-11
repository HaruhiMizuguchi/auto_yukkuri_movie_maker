"""
データベース管理システムのテスト

テスト対象:
- DatabaseManager クラス
- データベース初期化
- テーブル作成
- マイグレーション
- 接続管理
"""

import os
import pytest
import tempfile
from pathlib import Path
from typing import Any, Dict

# テスト対象のインポート（まだ実装していない）
from src.core.database_manager import DatabaseManager, DatabaseError


class TestDatabaseManager:
    """データベース管理システムのテストクラス"""

    @pytest.fixture
    def temp_db_path(self) -> str:
        """テスト用の一時データベースファイルパス"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        # クリーンアップ - Windowsでのファイルロック問題を回避
        try:
            if os.path.exists(path):
                # 少し待ってからファイル削除を試行
                import time
                time.sleep(0.1)
                os.unlink(path)
        except (PermissionError, OSError):
            # ファイルが使用中の場合は無視（テスト環境では問題なし）
            pass

    @pytest.fixture
    def db_manager(self, temp_db_path: str) -> DatabaseManager:
        """テスト用のDatabaseManagerインスタンス"""
        manager = DatabaseManager(db_path=temp_db_path)
        yield manager
        # テスト後のクリーンアップ
        manager.close_connection()

    def test_database_initialization(self, db_manager: DatabaseManager):
        """データベース初期化のテスト"""
        # データベースが初期化されることを確認
        db_manager.initialize()
        
        # データベースファイルが作成されることを確認
        assert os.path.exists(db_manager.db_path)
        
        # 接続が可能であることを確認
        assert db_manager.get_connection() is not None

    def test_tables_creation(self, db_manager: DatabaseManager):
        """テーブル作成のテスト"""
        db_manager.initialize()
        
        # 必要なテーブルが作成されることを確認
        expected_tables = [
            'projects',
            'workflow_steps', 
            'project_files',
            'project_statistics',
            'api_usage',
            'system_config'
        ]
        
        actual_tables = db_manager.get_table_names()
        for table in expected_tables:
            assert table in actual_tables

    def test_table_schema_validation(self, db_manager: DatabaseManager):
        """テーブルスキーマの検証"""
        db_manager.initialize()
        
        # projectsテーブルのスキーマを確認
        projects_schema = db_manager.get_table_schema('projects')
        expected_columns = [
            'id', 'theme', 'target_length_minutes', 'status', 
            'config_json', 'output_summary_json', 'created_at', 'updated_at'
        ]
        
        actual_columns = [col['name'] for col in projects_schema]
        for column in expected_columns:
            assert column in actual_columns

    def test_connection_management(self, db_manager: DatabaseManager):
        """接続管理のテスト"""
        db_manager.initialize()
        
        # 接続取得（コンテキストマネージャーとして）
        with db_manager.get_connection() as conn1:
            assert conn1 is not None
            
            # 同じ接続が返されることを確認（接続プール機能）
            with db_manager.get_connection() as conn2:
                assert conn1 is conn2
        
        # 接続を閉じる
        db_manager.close_connection()
        
        # 新しい接続が取得できることを確認
        with db_manager.get_connection() as conn3:
            assert conn3 is not None

    def test_transaction_management(self, db_manager: DatabaseManager):
        """トランザクション管理のテスト"""
        db_manager.initialize()
        
        # トランザクション開始
        with db_manager.transaction() as conn:
            # テストデータ挿入（themeフィールドを含む）
            conn.execute(
                "INSERT INTO projects (id, theme, status) VALUES (?, ?, ?)",
                ("test_001", "test_theme", "created")
            )
            
            # トランザクション内でデータが見えることを確認
            result = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?", 
                ("test_001",)
            ).fetchone()
            assert result[0] == 1
        
        # トランザクション完了後もデータが残っていることを確認
        with db_manager.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?", 
                ("test_001",)
            ).fetchone()
            assert result[0] == 1

    def test_transaction_rollback(self, db_manager: DatabaseManager):
        """トランザクションロールバックのテスト"""
        db_manager.initialize()
        
        # 例外でロールバックされることを確認
        try:
            with db_manager.transaction() as conn:
                conn.execute(
                    "INSERT INTO projects (id, theme, status) VALUES (?, ?, ?)",
                    ("test_002", "test_theme", "created")
                )
                # 意図的に例外を発生させる
                raise ValueError("Test exception")
        except (ValueError, DatabaseError):
            # ValueErrorまたはDatabaseErrorのどちらでも良い
            pass
        
        # ロールバックされてデータが残っていないことを確認
        with db_manager.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?", 
                ("test_002",)
            ).fetchone()
            assert result[0] == 0

    def test_migration_system(self, db_manager: DatabaseManager):
        """マイグレーションシステムのテスト"""
        db_manager.initialize()
        
        # 現在のマイグレーションバージョンを確認
        current_version = db_manager.get_migration_version()
        assert isinstance(current_version, int)
        assert current_version >= 1
        
        # マイグレーションが適用済みであることを確認
        assert db_manager.is_migration_applied(current_version)

    def test_database_backup_restore(self, db_manager: DatabaseManager, temp_db_path: str):
        """データベースバックアップ・復元のテスト"""
        db_manager.initialize()
        
        # テストデータを挿入
        with db_manager.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, theme, status) VALUES (?, ?, ?)",
                ("backup_test", "test_theme", "completed")
            )
        
        # バックアップ作成
        backup_path = temp_db_path + ".backup"
        db_manager.create_backup(backup_path)
        assert os.path.exists(backup_path)
        
        # 元のデータを削除
        with db_manager.transaction() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", ("backup_test",))
        
        # データが削除されたことを確認
        with db_manager.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?", 
                ("backup_test",)
            ).fetchone()
            assert result[0] == 0
        
        # バックアップから復元
        db_manager.restore_from_backup(backup_path)
        
        # データが復元されたことを確認
        with db_manager.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?", 
                ("backup_test",)
            ).fetchone()
            assert result[0] == 1
        
        # クリーンアップ
        if os.path.exists(backup_path):
            os.unlink(backup_path)

    def test_health_check(self, db_manager: DatabaseManager):
        """データベースヘルスチェックのテスト"""
        db_manager.initialize()
        
        # ヘルスチェックが正常に完了することを確認
        health_status = db_manager.health_check()
        assert health_status['status'] == 'healthy'
        assert 'db_path' in health_status
        assert 'db_size_bytes' in health_status
        assert 'table_count' in health_status
        assert health_status['table_count'] >= 6  # 基本的なテーブル数

    def test_cleanup_temporary_files(self, db_manager: DatabaseManager):
        """一時ファイルクリーンアップのテスト"""
        db_manager.initialize()
        
        # テスト用プロジェクトを作成
        with db_manager.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, theme, status) VALUES (?, ?, ?)",
                ("temp_test", "test_theme", "created")
            )
        
        # 一時ファイル情報を登録
        with db_manager.transaction() as conn:
            conn.execute("""
                INSERT INTO project_files 
                (project_id, file_type, file_category, file_path, file_name, is_temporary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("temp_test", "metadata", "intermediate", "temp/test.json", "test.json", True))
        
        # クリーンアップ実行前に一時ファイルが存在することを確認
        with db_manager.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM project_files WHERE is_temporary = 1"
            ).fetchone()
            assert result[0] >= 1
        
        # クリーンアップ実行
        db_manager.cleanup_temporary_files()
        
        # クリーンアップ後に一時ファイルが削除されていることを確認
        with db_manager.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM project_files WHERE is_temporary = 1"
            ).fetchone()
            assert result[0] == 0 