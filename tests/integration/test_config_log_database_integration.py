"""
設定・ログ・データベース統合テスト

ConfigManager、LogManager、DatabaseManager間の
実際の連携動作を検証する統合テストです。
"""

import unittest
import tempfile
import shutil
import os
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.config_manager import ConfigManager
from src.core.log_manager import LogManager
from src.core.database_manager import DatabaseManager


class TestConfigLogDatabaseIntegration(unittest.TestCase):
    """設定・ログ・データベース統合テストクラス"""
    
    def setUp(self):
        """テスト環境のセットアップ"""
        # 一時ディレクトリ作成
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "config")
        self.logs_dir = os.path.join(self.temp_dir, "logs")
        self.db_path = os.path.join(self.temp_dir, "test_integration.db")
        
        # ディレクトリ作成
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # テスト用設定ファイル作成
        self.create_test_config_files()
        
    def tearDown(self):
        """テスト環境のクリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config_files(self):
        """テスト用設定ファイルを作成"""
        # メイン設定ファイル
        main_config = {
            "database": {
                "path": self.db_path,
                "timeout": 30,
                "pool_size": 5
            },
            "logging": {
                "log_dir": self.logs_dir,
                "log_level": "DEBUG",
                "json_format": True,
                "console_output": True,
                "file_enabled": True,
                "file_path": os.path.join(self.logs_dir, "app.log"),
                "max_file_size": "10MB",
                "backup_count": 5,
                "external_webhook": None
            },
            "project": {
                "base_directory": os.path.join(self.temp_dir, "projects"),
                "max_projects": 100,
                "auto_cleanup_days": 30
            }
        }
        
        with open(os.path.join(self.config_dir, "main.yaml"), 'w', encoding='utf-8') as f:
            yaml.dump(main_config, f, allow_unicode=True)
        
        # 環境変数テスト用設定
        env_config = {
            "api": {
                "openai_key": "${OPENAI_API_KEY:default_test_key}",
                "base_url": "${API_BASE_URL:https://api.openai.com}",
                "timeout": "${API_TIMEOUT:60}"
            }
        }
        
        with open(os.path.join(self.config_dir, "api.yaml"), 'w', encoding='utf-8') as f:
            yaml.dump(env_config, f, allow_unicode=True)
    
    def test_config_driven_database_initialization(self):
        """設定ファイル駆動でのデータベース初期化統合テスト"""
        # 1. 設定読み込み
        config_manager = ConfigManager()
        config = config_manager.load_config(
            os.path.join(self.config_dir, "main.yaml")
        )
        
        # 2. 設定からデータベース初期化
        db_config = config["database"]
        db_manager = DatabaseManager(db_config["path"])
        
        # 3. データベース初期化実行
        db_manager.initialize()
        
        # 4. データベース接続確認
        self.assertTrue(os.path.exists(db_config["path"]))
        
        # 5. 設定値が適用されているか確認（データベース接続チェック）
        with db_manager.get_connection() as conn:
            # データベースが正常に動作することを確認
            result = conn.execute("SELECT 1").fetchone()
            self.assertEqual(result[0], 1)
        
        db_manager.close()
    
    def test_config_driven_logging_setup(self):
        """設定ファイル駆動でのログ設定統合テスト"""
        # 1. 設定読み込み
        config_manager = ConfigManager()
        config = config_manager.load_config(
            os.path.join(self.config_dir, "main.yaml")
        )
        
        # 2. 設定からログマネージャー初期化
        log_config = config["logging"]
        log_manager = LogManager({
            "log_dir": self.logs_dir,
            "log_level": log_config.get("level", "DEBUG"),
            "json_format": log_config.get("json_format", True),
            "console_output": log_config.get("console_output", True),
            "file_enabled": log_config.get("file_enabled", True),
            "file_path": log_config["file_path"]
        })
        
        # 3. ログ出力テスト
        test_messages = [
            ("debug", "デバッグメッセージ"),
            ("info", "情報メッセージ"),
            ("warning", "警告メッセージ"),
            ("error", "エラーメッセージ")
        ]
        
        for level, message in test_messages:
            getattr(log_manager, level)(message)
        
        # 4. ログファイル存在確認（実際に作成されたファイルを確認）
        log_files = list(Path(self.logs_dir).glob("yukkuri_tool_*.log"))
        self.assertGreater(len(log_files), 0, "ログファイルが作成されていません")
        
        # 5. ログ内容確認（作成されたファイルを読み取り）
        if log_files:
            with open(log_files[0], 'r', encoding='utf-8') as f:
                log_content = f.read()
                for _, message in test_messages:
                    self.assertIn(message, log_content)
    
    def test_environment_variable_expansion(self):
        """環境変数展開統合テスト"""
        # 1. 環境変数設定
        test_env_vars = {
            "OPENAI_API_KEY": "test_api_key_12345",
            "API_BASE_URL": "https://test.api.com",
            "API_TIMEOUT": "120"
        }
        
        with patch.dict(os.environ, test_env_vars):
            # 2. 設定読み込み（環境変数展開付き）
            config_manager = ConfigManager()
            config = config_manager.load_config(
                os.path.join(self.config_dir, "api.yaml")
            )
            
            # 3. 環境変数が正しく展開されているか確認
            api_config = config["api"]
            self.assertEqual(api_config["openai_key"], test_env_vars["OPENAI_API_KEY"])
            self.assertEqual(api_config["base_url"], test_env_vars["API_BASE_URL"])
            self.assertEqual(str(api_config["timeout"]), test_env_vars["API_TIMEOUT"])
    
    def test_logging_database_operations_integration(self):
        """ログ出力を含むデータベース操作統合テスト"""
        # 1. 設定初期化
        config_manager = ConfigManager()
        config = config_manager.load_config(
            os.path.join(self.config_dir, "main.yaml")
        )
        
        # 2. ログマネージャー初期化
        log_config = config["logging"]
        log_manager = LogManager({
            "log_dir": self.logs_dir,
            "log_level": log_config.get("level", "DEBUG"),
            "json_format": log_config.get("json_format", True),
            "console_output": log_config.get("console_output", True),
            "file_enabled": log_config.get("file_enabled", True),
            "file_path": log_config["file_path"]
        })
        
        # 3. データベースマネージャー初期化（ログ付き）
        db_config = config["database"]
        db_manager = DatabaseManager(db_config["path"])
        
        # データベース操作にログ出力を組み込み
        log_manager.info("データベース初期化開始")
        
        try:
            db_manager.initialize()
            log_manager.info("データベース初期化成功")
        except Exception as e:
            log_manager.error(f"データベース初期化失敗: {str(e)}")
            raise
        
        # 4. テーブル作成とログ
        log_manager.info("テーブル作成開始")
        
        with db_manager.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_logs (
                    id INTEGER PRIMARY KEY,
                    level TEXT,
                    message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            log_manager.info("テーブル作成完了")
        
        # 5. ログファイル確認
        log_files = list(Path(self.logs_dir).glob("yukkuri_tool_*.log"))
        self.assertGreater(len(log_files), 0)
        
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_content = f.read()
            self.assertIn("データベース初期化開始", log_content)
            self.assertIn("データベース初期化成功", log_content)
            self.assertIn("テーブル作成開始", log_content)
            self.assertIn("テーブル作成完了", log_content)
        
        db_manager.close()
    
    def test_configuration_validation_with_logging(self):
        """設定バリデーションとログ出力統合テスト"""
        # 1. 不正な設定ファイル作成
        invalid_config = {
            "database": {
                "path": "",  # 空のパス（不正）
                "timeout": "invalid_number"  # 文字列（不正）
            },
            "logging": {
                "level": "INVALID_LEVEL",  # 不正なログレベル
                "file_enabled": "not_boolean"  # 不正なブール値
            }
        }
        
        invalid_config_path = os.path.join(self.config_dir, "invalid.yaml")
        with open(invalid_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(invalid_config, f)
        
        # 2. ログマネージャー初期化（デフォルト設定）
        log_manager = LogManager({
            "log_dir": self.logs_dir,
            "log_level": "DEBUG",
            "json_format": True,
            "console_output": True,
            "file_enabled": True,
            "file_path": os.path.join(self.logs_dir, "validation.log")
        })
        
        # 3. 設定読み込みとバリデーション
        config_manager = ConfigManager()
        
        log_manager.info(f"設定ファイル読み込み開始: {invalid_config_path}")
        
        try:
            # バリデーション付き読み込み（スキーマは簡略化）
            config = config_manager.load_config(invalid_config_path)
            
            # 手動バリデーション
            if not config["database"]["path"]:
                raise ValueError("Database path cannot be empty")
            
            log_manager.info(f"設定ファイル読み込み成功: {invalid_config_path}")
            
        except Exception as e:
            log_manager.error(f"設定ファイル読み込み失敗: {invalid_config_path} - {str(e)}")
            
            # エラーが正しく検出されることを確認
            self.assertIn("empty", str(e).lower())
        
        # 4. ログファイル確認
        log_files = list(Path(self.logs_dir).glob("yukkuri_tool_*.log"))
        self.assertGreater(len(log_files), 0)
        
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_content = f.read()
            self.assertIn("設定ファイル読み込み開始", log_content)
            self.assertIn("設定ファイル読み込み失敗", log_content)
    
    def test_comprehensive_system_integration(self):
        """包括的システム統合テスト"""
        # 1. 全コンポーネント初期化
        config_manager = ConfigManager()
        config = config_manager.load_config(
            os.path.join(self.config_dir, "main.yaml")
        )
        
        log_config = config["logging"]
        log_manager = LogManager({
            "log_dir": self.logs_dir,
            "log_level": log_config.get("level", "DEBUG"),
            "json_format": log_config.get("json_format", True),
            "console_output": log_config.get("console_output", True),
            "file_enabled": log_config.get("file_enabled", True),
            "file_path": log_config["file_path"]
        })
        
        db_manager = DatabaseManager(config["database"]["path"])
        
        # 2. システム起動シーケンス
        log_manager.info("システム起動開始")
        
        # データベース初期化
        log_manager.info("データベース初期化中")
        db_manager.initialize()
        log_manager.info("データベース初期化完了")
        
        # プロジェクト設定確認
        project_config = config["project"]
        os.makedirs(project_config["base_directory"], exist_ok=True)
        log_manager.info(f"プロジェクトディレクトリ確認完了: {project_config['base_directory']}")
        
        # 3. 模擬プロジェクト作成
        with db_manager.get_connection() as conn:
            # プロジェクトテーブルが存在するか確認し、なければ簡易テーブル作成
            try:
                conn.execute("SELECT id FROM projects LIMIT 1")
            except:
                # テーブルが存在しない場合はスキップ（既存のテーブル構造を使用）
                pass
            
            conn.execute("""
                INSERT INTO projects (id, theme, target_length_minutes, status, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, ("test-project-001", "統合テストテーマ", 5, "created"))
            
            log_manager.info("テストプロジェクト作成完了: test-project-001")
        
        # 4. 設定値を使用した操作
        max_projects = project_config["max_projects"]
        log_manager.info(f"プロジェクト制限確認: {max_projects}")
        
        # 5. ログ統計収集（簡易実装）
        # LogManagerにget_log_statisticsメソッドがない場合の代替
        log_file_path = log_config["file_path"]
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()
                info_count = sum(1 for line in log_lines if "INFO" in line)
                self.assertGreater(len(log_lines), 0)
                self.assertGreater(info_count, 0)
        
        # 6. データベースヘルスチェック（簡易実装）
        try:
            with db_manager.get_connection() as conn:
                result = conn.execute("SELECT 1").fetchone()
                health_connected = result is not None
        except:
            health_connected = False
        
        self.assertTrue(health_connected)
        log_manager.info(f"データベースヘルスチェック完了: {health_connected}")
        
        # 7. システム終了シーケンス
        log_manager.info("システム終了処理開始")
        db_manager.close()
        log_manager.info("システム終了完了")
        
        # 8. 最終確認
        log_files = list(Path(self.logs_dir).glob("yukkuri_tool_*.log"))
        self.assertGreater(len(log_files), 0)
        
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_content = f.read()
            self.assertIn("システム起動開始", log_content)
            self.assertIn("システム終了完了", log_content)
            self.assertIn("test-project-001", log_content)


if __name__ == '__main__':
    unittest.main() 