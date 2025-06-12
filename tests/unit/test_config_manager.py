"""
設定管理システムのテストモジュール

このモジュールは設定ファイルの読み込み、環境変数展開、
バリデーション、デフォルト値管理のテストを行います。
"""

import unittest
import tempfile
import shutil
import os
import yaml
import json
from pathlib import Path
from unittest.mock import patch, mock_open
from typing import Dict, Any, Optional

# テスト対象のインポート
from src.core.config_manager import ConfigManager, ConfigError, ValidationError


class TestConfigManager(unittest.TestCase):
    """設定管理システムのテストクラス"""

    def setUp(self):
        """テスト前の準備"""
        # テンポラリディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        # テスト用設定ファイルを作成
        self._create_test_config_files()
        
        # ConfigManagerを初期化
        self.config_manager = ConfigManager(config_dir=self.config_dir)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # テンポラリディレクトリを削除
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_test_config_files(self):
        """テスト用設定ファイルを作成"""
        # YAML設定ファイル
        yaml_config = {
            "app": {
                "name": "test_app",
                "version": "1.0.0",
                "debug": "${DEBUG:false}",
                "port": "${PORT:8080}"
            },
            "database": {
                "host": "${DB_HOST:localhost}",
                "port": "${DB_PORT:5432}",
                "name": "test_db"
            },
            "includes": ["database_config.yaml"]
        }
        
        with open(os.path.join(self.config_dir, "app_config.yaml"), 'w') as f:
            yaml.dump(yaml_config, f)

        # JSON設定ファイル
        json_config = {
            "api": {
                "endpoints": {
                    "base_url": "${API_BASE_URL:http://localhost}",
                    "timeout": "${API_TIMEOUT:30}"
                },
                "retry_attempts": 3
            }
        }
        
        with open(os.path.join(self.config_dir, "api_config.json"), 'w') as f:
            json.dump(json_config, f)

        # インクルード用設定ファイル
        database_config = {
            "database": {
                "connection_pool": {
                    "min_connections": 1,
                    "max_connections": 10
                }
            }
        }
        
        with open(os.path.join(self.config_dir, "database_config.yaml"), 'w') as f:
            yaml.dump(database_config, f)

        # バリデーション用スキーマファイル
        schema_config = {
            "schema": {
                "type": "object",
                "required": ["app", "database"],
                "properties": {
                    "app": {
                        "type": "object",
                        "required": ["name", "version"],
                        "properties": {
                            "name": {"type": "string"},
                            "version": {"type": "string"},
                            "debug": {"type": "boolean"},
                            "port": {"type": "integer", "minimum": 1, "maximum": 65535}
                        }
                    },
                    "database": {
                        "type": "object",
                        "required": ["host", "name"],
                        "properties": {
                            "host": {"type": "string"},
                            "port": {"type": "integer"},
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }
        
        with open(os.path.join(self.config_dir, "schema.yaml"), 'w') as f:
            yaml.dump(schema_config, f)

        # プロファイル設定ファイル
        dev_profile = {
            "profile": "development",
            "app": {
                "debug": True,
                "log_level": "DEBUG"
            },
            "database": {
                "host": "dev-db.local",
                "debug_queries": True
            }
        }
        
        with open(os.path.join(self.config_dir, "development.yaml"), 'w') as f:
            yaml.dump(dev_profile, f)

        prod_profile = {
            "profile": "production",
            "app": {
                "debug": False,
                "log_level": "INFO"
            },
            "database": {
                "host": "prod-db.com",
                "debug_queries": False
            }
        }
        
        with open(os.path.join(self.config_dir, "production.yaml"), 'w') as f:
            yaml.dump(prod_profile, f)

    def test_load_yaml_config_file(self):
        """YAML設定ファイル読み込みのテスト"""
        config = self.config_manager.load_config("app_config.yaml")
        
        # 基本構造の確認
        self.assertIn("app", config)
        self.assertIn("database", config)
        self.assertEqual(config["app"]["name"], "test_app")
        self.assertEqual(config["app"]["version"], "1.0.0")

    def test_load_json_config_file(self):
        """JSON設定ファイル読み込みのテスト"""
        config = self.config_manager.load_config("api_config.json")
        
        self.assertIn("api", config)
        self.assertEqual(config["api"]["retry_attempts"], 3)

    @patch.dict(os.environ, {
        'DEBUG': 'true',
        'PORT': '9000',
        'DB_HOST': 'production-db.com',
        'API_BASE_URL': 'https://api.example.com'
    })
    def test_environment_variable_expansion(self):
        """環境変数展開のテスト"""
        config = self.config_manager.load_config("app_config.yaml")
        
        # 環境変数が展開されていることを確認
        self.assertEqual(config["app"]["debug"], True)  # 'true' -> True
        self.assertEqual(config["app"]["port"], 9000)   # '9000' -> 9000
        self.assertEqual(config["database"]["host"], "production-db.com")

    def test_environment_variable_defaults(self):
        """環境変数デフォルト値のテスト"""
        # 環境変数が設定されていない場合、デフォルト値が使用される
        config = self.config_manager.load_config("app_config.yaml")
        
        self.assertEqual(config["app"]["debug"], False)  # デフォルト値
        self.assertEqual(config["app"]["port"], 8080)    # デフォルト値
        self.assertEqual(config["database"]["host"], "localhost")  # デフォルト値

    def test_include_functionality(self):
        """インクルード機能のテスト"""
        config = self.config_manager.load_config("app_config.yaml")
        
        # インクルードされたファイルの内容が統合されている
        self.assertIn("connection_pool", config["database"])
        self.assertEqual(config["database"]["connection_pool"]["min_connections"], 1)
        self.assertEqual(config["database"]["connection_pool"]["max_connections"], 10)

    def test_config_validation_success(self):
        """設定値バリデーション成功のテスト"""
        config = self.config_manager.load_config("app_config.yaml")
        
        # スキーマファイルに基づいてバリデーション
        schema = self.config_manager.load_schema("schema.yaml")
        validation_result = self.config_manager.validate_config(config, schema)
        
        self.assertTrue(validation_result["is_valid"])
        self.assertEqual(len(validation_result["errors"]), 0)

    def test_config_validation_failure(self):
        """設定値バリデーション失敗のテスト"""
        # 不正な設定データを作成
        invalid_config = {
            "app": {
                "name": 123,  # 文字列であるべき
                "port": "invalid_port"  # 整数であるべき
            }
            # "database" が欠如している（必須項目）
        }
        
        schema = self.config_manager.load_schema("schema.yaml")
        validation_result = self.config_manager.validate_config(invalid_config, schema)
        
        self.assertFalse(validation_result["is_valid"])
        self.assertGreater(len(validation_result["errors"]), 0)
        
        # エラーメッセージの内容確認
        errors = validation_result["errors"]
        error_messages = [error["message"] for error in errors]
        error_properties = [error.get("property") for error in errors]
        
        # エラーがname、port、databaseに関連するものかチェック
        has_name_error = any("name" in str(msg).lower() or prop == "name" for msg, prop in zip(error_messages, error_properties))
        has_port_error = any("port" in str(msg).lower() or prop == "port" for msg, prop in zip(error_messages, error_properties))
        has_database_error = any("database" in str(msg).lower() or "required" in str(msg).lower() for msg in error_messages)
        
        # デバッグ用：エラー詳細を確認
        if not (has_name_error and has_port_error and has_database_error):
            print(f"Validation errors: {validation_result['errors']}")
        
        self.assertTrue(has_name_error, f"Name error not found in: {error_messages}")
        self.assertTrue(has_port_error, f"Port error not found in: {error_messages}")
        self.assertTrue(has_database_error, f"Database error not found in: {error_messages}")

    def test_type_conversion(self):
        """型変換機能のテスト"""
        with patch.dict(os.environ, {
            'DEBUG': 'true',
            'PORT': '9000',
            'TIMEOUT': '30.5'
        }):
            config = self.config_manager.load_config("app_config.yaml")
        
        # 型変換が正しく行われている
        self.assertIsInstance(config["app"]["debug"], bool)
        self.assertIsInstance(config["app"]["port"], int)

    def test_profile_switching_development(self):
        """プロファイル切り替え（開発環境）のテスト"""
        self.config_manager.set_profile("development")
        config = self.config_manager.load_config("app_config.yaml")
        
        # 開発プロファイルの設定が適用されている
        self.assertEqual(config["app"]["debug"], True)
        self.assertEqual(config["app"]["log_level"], "DEBUG")
        self.assertEqual(config["database"]["host"], "dev-db.local")
        self.assertTrue(config["database"]["debug_queries"])

    def test_profile_switching_production(self):
        """プロファイル切り替え（本番環境）のテスト"""
        self.config_manager.set_profile("production")
        config = self.config_manager.load_config("app_config.yaml")
        
        # 本番プロファイルの設定が適用されている
        self.assertEqual(config["app"]["debug"], False)
        self.assertEqual(config["app"]["log_level"], "INFO")
        self.assertEqual(config["database"]["host"], "prod-db.com")
        self.assertFalse(config["database"]["debug_queries"])

    def test_default_values_management(self):
        """デフォルト値管理のテスト"""
        # デフォルト値を設定
        defaults = {
            "app": {
                "timeout": 30,
                "max_retries": 3
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(levelname)s - %(message)s"
            }
        }
        
        self.config_manager.set_defaults(defaults)
        config = self.config_manager.get_merged_config()
        
        # デフォルト値が設定されている
        self.assertEqual(config["app"]["timeout"], 30)
        self.assertEqual(config["app"]["max_retries"], 3)
        self.assertEqual(config["logging"]["level"], "INFO")

    def test_config_inheritance(self):
        """設定継承のテスト"""
        # 基本設定とプロファイル設定の継承
        base_config = self.config_manager.load_config("app_config.yaml")
        profile_config = self.config_manager.load_config("development.yaml")
        
        merged_config = self.config_manager.merge_configs(base_config, profile_config)
        
        # 継承が正しく行われている
        self.assertEqual(merged_config["app"]["name"], "test_app")  # 基本設定
        self.assertEqual(merged_config["app"]["debug"], True)       # プロファイル設定で上書き

    def test_config_caching(self):
        """設定キャッシュ機能のテスト"""
        # 初回読み込み
        config1 = self.config_manager.load_config("app_config.yaml", use_cache=True)
        
        # キャッシュから読み込み（ファイルが変更されていない場合）
        config2 = self.config_manager.load_config("app_config.yaml", use_cache=True)
        
        # 同じ内容が返されることを確認（deepcopyされているので、オブジェクトは異なる）
        self.assertEqual(config1, config2)
        
        # キャッシュ情報の確認
        cache_info = self.config_manager.get_cache_info()
        self.assertIn("app_config.yaml", cache_info["cached_files"])

    def test_hot_reload_functionality(self):
        """ホットリロード機能のテスト"""
        config = self.config_manager.load_config("app_config.yaml")
        original_name = config["app"]["name"]
        
        # 設定ファイルを変更
        modified_config = {
            "app": {
                "name": "modified_app",
                "version": "2.0.0"
            },
            "database": {
                "host": "localhost",
                "name": "test_db"
            }
        }
        
        config_file_path = os.path.join(self.config_dir, "app_config.yaml")
        with open(config_file_path, 'w') as f:
            yaml.dump(modified_config, f)
        
        # ホットリロード実行
        reloaded_config = self.config_manager.reload_config("app_config.yaml")
        
        # 変更が反映されている
        self.assertNotEqual(reloaded_config["app"]["name"], original_name)
        self.assertEqual(reloaded_config["app"]["name"], "modified_app")

    def test_error_handling_file_not_found(self):
        """ファイルが存在しない場合のエラーハンドリング"""
        with self.assertRaises(ConfigError) as context:
            self.config_manager.load_config("nonexistent_config.yaml")
        
        self.assertIn("not found", str(context.exception))

    def test_error_handling_invalid_yaml(self):
        """不正なYAMLファイルのエラーハンドリング"""
        # 不正なYAMLファイルを作成
        invalid_yaml_file = os.path.join(self.config_dir, "invalid.yaml")
        with open(invalid_yaml_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        with self.assertRaises(ConfigError) as context:
            self.config_manager.load_config("invalid.yaml")
        
        self.assertIn("parsing", str(context.exception).lower())

    def test_error_handling_invalid_json(self):
        """不正なJSONファイルのエラーハンドリング"""
        # 不正なJSONファイルを作成
        invalid_json_file = os.path.join(self.config_dir, "invalid.json")
        with open(invalid_json_file, 'w') as f:
            f.write('{"invalid": json, "content"}')
        
        with self.assertRaises(ConfigError) as context:
            self.config_manager.load_config("invalid.json")
        
        self.assertIn("json", str(context.exception).lower())

    def test_get_config_value_by_path(self):
        """設定値をパスで取得するテスト"""
        config = self.config_manager.load_config("app_config.yaml")
        
        # パス指定での値取得
        app_name = self.config_manager.get_value("app.name", config)
        db_host = self.config_manager.get_value("database.host", config)
        
        self.assertEqual(app_name, "test_app")
        self.assertEqual(db_host, "localhost")  # デフォルト値
        
        # 存在しないパスの場合はNoneが返される
        non_existent = self.config_manager.get_value("app.nonexistent", config)
        self.assertIsNone(non_existent)

    def test_config_interpolation(self):
        """設定値内部参照のテスト"""
        # 設定値内で他の設定値を参照
        interpolation_config = {
            "base": {
                "url": "http://localhost",
                "port": 8080
            },
            "api": {
                "endpoint": "${base.url}:${base.port}/api"
            }
        }
        
        config_file = os.path.join(self.config_dir, "interpolation.yaml")
        with open(config_file, 'w') as f:
            yaml.dump(interpolation_config, f)
        
        config = self.config_manager.load_config("interpolation.yaml")
        
        # 内部参照が展開されている
        self.assertEqual(config["api"]["endpoint"], "http://localhost:8080/api")


if __name__ == "__main__":
    unittest.main() 