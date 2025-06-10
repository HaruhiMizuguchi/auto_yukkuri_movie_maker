#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# DatabaseManager implementation
db_manager_code = '''"""
データベース管理システム

SQLiteデータベースの初期化、接続管理、トランザクション制御、
マイグレーション、バックアップ・復元機能を提供する。
"""

import os
import sqlite3
import shutil
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Any, Optional, Generator, Tuple
from datetime import datetime


class DatabaseError(Exception):
    """データベース関連のエラー"""
    pass


class MigrationError(DatabaseError):
    """マイグレーション関連のエラー"""
    pass


class DatabaseManager:
    """データベース管理クラス"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None
        self.logger = logging.getLogger(__name__)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
    def initialize(self) -> None:
        try:
            self.logger.info(f"データベース初期化開始: {self.db_path}")
            self.get_connection()
            self._run_migrations()
            self.logger.info("データベース初期化完了")
        except Exception as e:
            self.logger.error(f"データベース初期化エラー: {e}")
            raise DatabaseError(f"データベース初期化に失敗しました: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            try:
                self._connection = sqlite3.connect(
                    self.db_path,
                    timeout=30.0,
                    check_same_thread=False
                )
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA journal_mode = WAL")
                self._connection.row_factory = sqlite3.Row
                self.logger.debug("データベース接続を確立")
            except sqlite3.Error as e:
                self.logger.error(f"データベース接続エラー: {e}")
                raise DatabaseError(f"データベース接続に失敗しました: {e}")
        return self._connection
    
    def close_connection(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
                self.logger.debug("データベース接続を閉じました")
            except sqlite3.Error as e:
                self.logger.warning(f"接続クローズ時にエラー: {e}")
            finally:
                self._connection = None
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.get_connection()
        try:
            conn.execute("BEGIN")
            self.logger.debug("トランザクション開始")
            yield conn
            conn.commit()
            self.logger.debug("トランザクションコミット")
        except Exception as e:
            conn.rollback()
            self.logger.warning(f"トランザクションロールバック: {e}")
            raise
    
    def get_table_names(self) -> List[str]:
        try:
            conn = self.get_connection()
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"テーブル名取得エラー: {e}")
            raise DatabaseError(f"テーブル名の取得に失敗しました: {e}")
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            schema = []
            for row in cursor.fetchall():
                schema.append({
                    'cid': row[0],
                    'name': row[1],
                    'type': row[2],
                    'notnull': bool(row[3]),
                    'default_value': row[4],
                    'primary_key': bool(row[5])
                })
            return schema
        except sqlite3.Error as e:
            self.logger.error(f"テーブルスキーマ取得エラー: {e}")
            raise DatabaseError(f"テーブルスキーマの取得に失敗しました: {e}")
    
    def get_migration_version(self) -> int:
        try:
            conn = self.get_connection()
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_migrations'
            """)
            if not cursor.fetchone():
                return 0
            cursor = conn.execute("""
                SELECT MAX(version) FROM schema_migrations 
                WHERE applied = 1
            """)
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
        except sqlite3.Error as e:
            self.logger.error(f"マイグレーションバージョン取得エラー: {e}")
            return 0
    
    def is_migration_applied(self, version: int) -> bool:
        try:
            conn = self.get_connection()
            cursor = conn.execute("""
                SELECT applied FROM schema_migrations 
                WHERE version = ?
            """, (version,))
            result = cursor.fetchone()
            return bool(result[0]) if result else False
        except sqlite3.Error as e:
            self.logger.error(f"マイグレーション状態確認エラー: {e}")
            return False
    
    def create_backup(self, backup_path: str) -> None:
        try:
            self.logger.info(f"データベースバックアップ開始: {backup_path}")
            self.close_connection()
            shutil.copy2(self.db_path, backup_path)
            self.logger.info("データベースバックアップ完了")
        except Exception as e:
            self.logger.error(f"バックアップ作成エラー: {e}")
            raise DatabaseError(f"バックアップの作成に失敗しました: {e}")
    
    def restore_from_backup(self, backup_path: str) -> None:
        try:
            self.logger.info(f"データベース復元開始: {backup_path}")
            if not os.path.exists(backup_path):
                raise DatabaseError(f"バックアップファイルが見つかりません: {backup_path}")
            self.close_connection()
            shutil.copy2(backup_path, self.db_path)
            self.logger.info("データベース復元完了")
        except Exception as e:
            self.logger.error(f"データベース復元エラー: {e}")
            raise DatabaseError(f"データベースの復元に失敗しました: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        result = {
            'status': 'healthy',
            'database_exists': False,
            'connection_ok': False,
            'tables_count': 0,
            'migration_version': 0,
            'file_size_mb': 0.0,
            'errors': []
        }
        try:
            result['database_exists'] = self.db_path.exists()
            if result['database_exists']:
                result['file_size_mb'] = round(self.db_path.stat().st_size / (1024 * 1024), 2)
            conn = self.get_connection()
            result['connection_ok'] = True
            result['tables_count'] = len(self.get_table_names())
            result['migration_version'] = self.get_migration_version()
        except Exception as e:
            result['status'] = 'unhealthy'
            result['errors'].append(str(e))
            self.logger.error(f"ヘルスチェックエラー: {e}")
        return result
    
    def cleanup_temporary_files(self) -> int:
        cleaned_count = 0
        try:
            db_dir = self.db_path.parent
            for suffix in ['-wal', '-shm']:
                temp_file = db_dir / f"{self.db_path.name}{suffix}"
                if temp_file.exists():
                    temp_file.unlink()
                    cleaned_count += 1
                    self.logger.debug(f"一時ファイル削除: {temp_file}")
        except Exception as e:
            self.logger.warning(f"一時ファイルクリーンアップエラー: {e}")
        return cleaned_count
    
    def _run_migrations(self) -> None:
        try:
            conn = self.get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied INTEGER NOT NULL DEFAULT 0,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            migrations = self._get_migrations()
            for version, sql in migrations:
                if not self.is_migration_applied(version):
                    self.logger.info(f"マイグレーション実行: v{version}")
                    with self.transaction() as trans_conn:
                        trans_conn.executescript(sql)
                        trans_conn.execute("""
                            INSERT OR REPLACE INTO schema_migrations 
                            (version, applied, applied_at) 
                            VALUES (?, 1, CURRENT_TIMESTAMP)
                        """, (version,))
                    self.logger.info(f"マイグレーション完了: v{version}")
        except Exception as e:
            self.logger.error(f"マイグレーション実行エラー: {e}")
            raise MigrationError(f"マイグレーションの実行に失敗しました: {e}")
    
    def _get_migrations(self) -> List[Tuple[int, str]]:
        return [(1, self._get_migration_v1())]
    
    def _get_migration_v1(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'initialized',
            config_json TEXT,
            estimated_duration INTEGER,
            actual_duration INTEGER,
            theme TEXT,
            target_length_minutes INTEGER,
            youtube_video_id TEXT,
            youtube_url TEXT
        );

        CREATE TABLE IF NOT EXISTS workflow_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            input_data TEXT,
            output_data TEXT,
            processing_time_seconds REAL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS project_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            api_name TEXT NOT NULL,
            endpoint TEXT,
            request_count INTEGER DEFAULT 1,
            tokens_used INTEGER,
            cost_usd REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
        CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
        CREATE INDEX IF NOT EXISTS idx_workflow_steps_project_id ON workflow_steps(project_id);
        CREATE INDEX IF NOT EXISTS idx_workflow_steps_status ON workflow_steps(status);
        CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
        CREATE INDEX IF NOT EXISTS idx_project_files_type ON project_files(file_type);
        CREATE INDEX IF NOT EXISTS idx_api_usage_project_id ON api_usage(project_id);
        CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp);

        CREATE TRIGGER IF NOT EXISTS update_projects_timestamp 
        AFTER UPDATE ON projects
        BEGIN
            UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;

        CREATE TRIGGER IF NOT EXISTS update_system_config_timestamp 
        AFTER UPDATE ON system_config
        BEGIN
            UPDATE system_config SET updated_at = CURRENT_TIMESTAMP WHERE key = NEW.key;
        END;
        """
'''

# Write to file
with open('src/core/database_manager.py', 'w', encoding='utf-8') as f:
    f.write(db_manager_code)

print("DatabaseManager implementation created successfully!") 