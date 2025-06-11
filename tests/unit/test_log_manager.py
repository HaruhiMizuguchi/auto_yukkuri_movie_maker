"""
ログシステムのテストモジュール

このモジュールは構造化ログ、ローテーション、外部送信、
パフォーマンス計測のテストを行います。
"""

import unittest
import tempfile
import shutil
import os
import json
import logging
import time
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from typing import Dict, Any, List
from datetime import datetime, timedelta

# テスト対象のインポート
from src.core.log_manager import LogManager, LogManagerError


class TestLogManager(unittest.TestCase):
    """ログシステムのテストクラス"""

    def setUp(self):
        """テスト前の準備"""
        # テンポラリディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.test_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # テスト用設定
        self.config = {
            "log_dir": self.log_dir,
            "log_level": "DEBUG",
            "json_format": True,
            "console_output": False,  # テスト時はコンソール出力無効
            "rotation": {
                "max_file_size": "10MB",
                "max_files": 5,
                "rotation_type": "size"
            },
            "external_logging": {
                "enabled": False,
                "webhook_url": None
            }
        }
        
        # LogManagerを初期化
        self.log_manager = LogManager(config=self.config)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # テンポラリディレクトリを削除
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initialize_log_manager(self):
        """ログマネージャー初期化のテスト"""
        # 基本属性の確認
        self.assertIsNotNone(self.log_manager)
        self.assertEqual(self.log_manager.log_dir, Path(self.log_dir))
        self.assertEqual(self.log_manager.log_level, logging.DEBUG)
        self.assertTrue(self.log_manager.json_format)
        
        # ログディレクトリの作成確認
        self.assertTrue(os.path.exists(self.log_dir))

    def test_structured_json_logging(self):
        """構造化JSON ログ出力のテスト"""
        # ログ出力
        self.log_manager.info(
            "テストメッセージ",
            context={
                "user_id": "user123",
                "action": "test_action",
                "metadata": {"key": "value"}
            }
        )
        
        # ログファイルの確認
        log_files = list(Path(self.log_dir).glob("*.log"))
        self.assertGreater(len(log_files), 0)
        
        # JSON構造の確認
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)
        
        # 必須フィールドの確認
        self.assertIn("timestamp", log_data)
        self.assertIn("level", log_data)
        self.assertIn("message", log_data)
        self.assertIn("context", log_data)
        
        # データ内容の確認
        self.assertEqual(log_data["level"], "INFO")
        self.assertEqual(log_data["message"], "テストメッセージ")
        self.assertEqual(log_data["context"]["user_id"], "user123")

    def test_log_levels(self):
        """ログレベル別出力のテスト"""
        # 各レベルでのログ出力
        self.log_manager.debug("デバッグメッセージ")
        self.log_manager.info("情報メッセージ")
        self.log_manager.warning("警告メッセージ")
        self.log_manager.error("エラーメッセージ")
        
        # ログファイルの確認
        log_files = list(Path(self.log_dir).glob("*.log"))
        self.assertGreater(len(log_files), 0)
        
        # 各レベルのメッセージが記録されていることを確認
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        self.assertEqual(len(log_lines), 4)
        
        # レベルの確認
        levels = []
        for line in log_lines:
            log_data = json.loads(line.strip())
            levels.append(log_data["level"])
        
        self.assertIn("DEBUG", levels)
        self.assertIn("INFO", levels)
        self.assertIn("WARNING", levels)
        self.assertIn("ERROR", levels)

    def test_log_level_filtering(self):
        """ログレベルフィルタリングのテスト"""
        # WARNINGレベルに設定
        warning_config = self.config.copy()
        warning_config["log_level"] = "WARNING"
        warning_config["log_dir"] = os.path.join(self.test_dir, "warning_logs")
        os.makedirs(warning_config["log_dir"], exist_ok=True)
        
        warning_log_manager = LogManager(config=warning_config)
        
        # 各レベルでのログ出力
        warning_log_manager.debug("デバッグメッセージ")
        warning_log_manager.info("情報メッセージ")
        warning_log_manager.warning("警告メッセージ")
        warning_log_manager.error("エラーメッセージ")
        
        # WARNING以上のみ記録されることを確認
        warning_log_files = list(Path(warning_config["log_dir"]).glob("*.log"))
        self.assertGreater(len(warning_log_files), 0)
        
        with open(warning_log_files[0], 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        # WARNING、ERRORの2つのみ記録されている
        self.assertEqual(len(log_lines), 2)

    def test_performance_measurement(self):
        """パフォーマンス計測機能のテスト"""
        # 処理時間計測
        with self.log_manager.measure_time("test_operation") as timer:
            time.sleep(0.1)  # 0.1秒待機
        
        # 処理時間がログに記録されていることを確認
        log_files = list(Path(self.log_dir).glob("*.log"))
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        # 最後の行が処理時間ログ
        performance_log = json.loads(log_lines[-1].strip())
        self.assertEqual(performance_log["level"], "INFO")
        self.assertIn("duration_ms", performance_log["context"])
        self.assertGreater(performance_log["context"]["duration_ms"], 90)  # 約100ms

    def test_api_call_tracking(self):
        """API呼び出し追跡のテスト"""
        # API呼び出し記録
        self.log_manager.log_api_call(
            api_name="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            status_code=200,
            request_size=1024,
            response_size=2048,
            duration_ms=500
        )
        
        # ログファイルの確認
        log_files = list(Path(self.log_dir).glob("*.log"))
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_line = f.readline().strip()
            api_log = json.loads(log_line)
        
        # API呼び出し情報の確認
        self.assertEqual(api_log["level"], "INFO")
        self.assertEqual(api_log["context"]["api_name"], "openai")
        self.assertEqual(api_log["context"]["status_code"], 200)
        self.assertEqual(api_log["context"]["duration_ms"], 500)

    def test_error_with_stack_trace(self):
        """エラーログとスタックトレースのテスト"""
        try:
            # 意図的にエラーを発生
            raise ValueError("テストエラー")
        except Exception as e:
            self.log_manager.log_exception(
                "エラーが発生しました",
                exception=e,
                context={"operation": "test"}
            )
        
        # エラーログの確認
        log_files = list(Path(self.log_dir).glob("*.log"))
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_line = f.readline().strip()
            error_log = json.loads(log_line)
        
        # エラー情報の確認
        self.assertEqual(error_log["level"], "ERROR")
        self.assertIn("exception", error_log["context"])
        self.assertIn("ValueError", error_log["context"]["exception"]["type"])
        self.assertIn("テストエラー", error_log["context"]["exception"]["message"])
        self.assertIn("traceback", error_log["context"]["exception"])

    def test_file_rotation_by_size(self):
        """ファイルサイズベースローテーションのテスト"""
        # 小さなファイルサイズでローテーション設定
        rotation_config = self.config.copy()
        rotation_config["rotation"]["max_file_size"] = "1KB"  # 1KBでローテーション
        rotation_log_manager = LogManager(config=rotation_config)
        
        # 大量のログを出力してローテーションを発生させる
        for i in range(100):
            rotation_log_manager.info(f"ログメッセージ {i}", context={"index": i})
        
        # 複数のログファイルが作成されることを確認
        log_files = list(Path(self.log_dir).glob("*.log*"))
        self.assertGreater(len(log_files), 1)

    def test_file_rotation_cleanup(self):
        """古いログファイル削除のテスト"""
        # 専用ディレクトリでテスト
        cleanup_config = self.config.copy()
        cleanup_config["rotation"]["max_files"] = 2
        cleanup_config["rotation"]["max_file_size"] = "1KB"
        cleanup_config["log_dir"] = os.path.join(self.test_dir, "cleanup_logs")
        os.makedirs(cleanup_config["log_dir"], exist_ok=True)
        
        cleanup_log_manager = LogManager(config=cleanup_config)
        
        # 大量のログでローテーションを複数回発生
        for i in range(300):
            cleanup_log_manager.info(f"クリーンアップテスト {i}")
        
        # 専用ディレクトリのファイル数が制限内であることを確認
        cleanup_log_files = list(Path(cleanup_config["log_dir"]).glob("*.log*"))
        self.assertLessEqual(len(cleanup_log_files), 3)  # 現在 + バックアップ2つ

    @patch('requests.post')
    def test_external_logging_webhook(self, mock_post):
        """外部ログ送信（Webhook）のテスト"""
        # 外部ログ送信設定
        webhook_config = self.config.copy()
        webhook_config["external_logging"] = {
            "enabled": True,
            "webhook_url": "https://example.com/webhook",
            "level_threshold": "ERROR"
        }
        
        webhook_log_manager = LogManager(config=webhook_config)
        
        # レスポンスのモック設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # エラーログ送信
        webhook_log_manager.error(
            "外部送信テスト",
            context={"severity": "high"}
        )
        
        # Webhookが呼ばれたことを確認
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # 送信データの確認
        sent_data = call_args[1]['json']
        self.assertEqual(sent_data["level"], "ERROR")
        self.assertEqual(sent_data["message"], "外部送信テスト")

    def test_context_manager_logging(self):
        """コンテキストマネージャーでのログ記録テスト"""
        with self.log_manager.operation_context("ユーザー認証", user_id="user123"):
            self.log_manager.info("認証開始")
            self.log_manager.info("認証成功")
        
        # コンテキスト情報が全てのログに含まれることを確認
        log_files = list(Path(self.log_dir).glob("*.log"))
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        for line in log_lines:
            log_data = json.loads(line.strip())
            self.assertIn("operation", log_data["context"])
            self.assertIn("user_id", log_data["context"])

    def test_log_aggregation_stats(self):
        """ログ集約統計のテスト"""
        # 様々なレベルのログを出力
        for i in range(5):
            self.log_manager.info(f"情報 {i}")
        for i in range(3):
            self.log_manager.warning(f"警告 {i}")
        for i in range(2):
            self.log_manager.error(f"エラー {i}")
        
        # 統計情報取得
        stats = self.log_manager.get_stats()
        
        # 統計の確認
        self.assertEqual(stats["total_logs"], 10)
        self.assertEqual(stats["by_level"]["INFO"], 5)
        self.assertEqual(stats["by_level"]["WARNING"], 3)
        self.assertEqual(stats["by_level"]["ERROR"], 2)

    def test_log_search_functionality(self):
        """ログ検索機能のテスト"""
        # 検索対象ログを出力
        start_search_time = datetime.now() - timedelta(seconds=1)
        
        self.log_manager.info("ユーザー登録", context={"user_id": "user123"})
        self.log_manager.error("データベースエラー", context={"db": "users"})
        self.log_manager.info("ユーザーログイン", context={"user_id": "user456"})
        
        end_search_time = datetime.now() + timedelta(seconds=1)
        
        # 検索実行
        search_results = self.log_manager.search_logs(
            start_time=start_search_time,
            end_time=end_search_time,
            level="INFO",
            message_contains="ユーザー"
        )
        
        # 検索結果の確認
        self.assertEqual(len(search_results), 2)
        self.assertTrue(all("ユーザー" in result["message"] for result in search_results))

    def test_invalid_configuration(self):
        """不正な設定のエラーハンドリングテスト"""
        # 不正な設定
        invalid_config = {
            "log_dir": "/invalid/path/that/does/not/exist",
            "log_level": "INVALID_LEVEL"
        }
        
        # エラーが発生することを確認
        with self.assertRaises(LogManagerError):
            LogManager(config=invalid_config)

    def test_concurrent_logging(self):
        """並行ログ出力のテスト"""
        import threading
        import queue
        
        result_queue = queue.Queue()
        
        def log_worker(worker_id):
            try:
                for i in range(10):
                    self.log_manager.info(
                        f"ワーカー{worker_id}のメッセージ{i}",
                        context={"worker_id": worker_id, "message_id": i}
                    )
                result_queue.put(f"worker_{worker_id}_success")
            except Exception as e:
                result_queue.put(f"worker_{worker_id}_error: {e}")
        
        # 複数スレッドでログ出力
        threads = []
        for worker_id in range(3):
            thread = threading.Thread(target=log_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # スレッド完了待機
        for thread in threads:
            thread.join()
        
        # 結果確認
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())
        
        # 全ワーカーが成功したことを確認
        success_count = len([r for r in results if "success" in r])
        self.assertEqual(success_count, 3)
        
        # ログファイルの確認
        log_files = list(Path(self.log_dir).glob("*.log"))
        with open(log_files[0], 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        # 30個のログ（3ワーカー × 10メッセージ）が記録されている
        self.assertEqual(len(log_lines), 30)


if __name__ == "__main__":
    unittest.main() 