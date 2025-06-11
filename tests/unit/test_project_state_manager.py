"""
テスト: プロジェクト状態管理システム (1-1-2: プロジェクト状態管理)

このテストファイルでは以下の機能をテストします：
- 進捗状況追跡
- ステップ完了状況管理
- エラー状態記録
"""

import unittest
import tempfile
import shutil
import os
import uuid
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
from datetime import datetime, timedelta

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.project_state_manager import ProjectStateManager
from core.database_manager import DatabaseManager
from core.project_manager import ProjectManager


class TestProjectStateManager(unittest.TestCase):
    """プロジェクト状態管理システムのテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        # テンポラリディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_yukkuri_tool.db")
        self.projects_dir = os.path.join(self.test_dir, "projects")
        
        # データベースマネージャーを初期化
        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.initialize()
        
        # プロジェクトマネージャーを初期化
        self.project_manager = ProjectManager(
            db_manager=self.db_manager,
            projects_base_dir=self.projects_dir
        )
        
        # プロジェクト状態マネージャーを初期化
        self.state_manager = ProjectStateManager(self.db_manager)
        
        # テスト用プロジェクトを作成
        self.test_project_id = self.project_manager.create_project(
            theme="テスト用プロジェクト",
            target_length_minutes=5
        )
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        # データベース接続を閉じる
        if hasattr(self.db_manager, 'close'):
            self.db_manager.close()
        
        # テンポラリディレクトリを削除
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_initialize_workflow_steps(self):
        """ワークフローステップの初期化テスト"""
        # 13ステップのワークフローを初期化
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
            {"step_number": 3, "step_name": "title_generation", "display_name": "タイトル生成"},
            {"step_number": 4, "step_name": "tts_generation", "display_name": "音声生成"},
            {"step_number": 5, "step_name": "character_synthesis", "display_name": "立ち絵合成"},
            {"step_number": 6, "step_name": "background_generation", "display_name": "背景生成"},
            {"step_number": 7, "step_name": "background_animation", "display_name": "背景動画生成"},
            {"step_number": 8, "step_name": "subtitle_generation", "display_name": "字幕生成"},
            {"step_number": 9, "step_name": "video_composition", "display_name": "動画合成"},
            {"step_number": 10, "step_name": "audio_enhancement", "display_name": "音声強化"},
            {"step_number": 11, "step_name": "illustration_insertion", "display_name": "イラスト挿入"},
            {"step_number": 12, "step_name": "final_encoding", "display_name": "最終エンコード"},
            {"step_number": 13, "step_name": "youtube_upload", "display_name": "YouTube投稿"}
        ]
        
        # ワークフローステップを初期化
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # 初期化されたステップを取得
        steps = self.state_manager.get_workflow_steps(self.test_project_id)
        
        # 13ステップが作成されていることを確認
        self.assertEqual(len(steps), 13)
        
        # 各ステップの初期状態を確認
        for i, step in enumerate(steps):
            expected_step = workflow_definition[i]
            self.assertEqual(step["step_number"], expected_step["step_number"])
            self.assertEqual(step["step_name"], expected_step["step_name"])
            self.assertEqual(step["status"], "pending")
            self.assertIsNone(step["started_at"])
            self.assertIsNone(step["completed_at"])
            self.assertEqual(step["retry_count"], 0)
    
    def test_start_step(self):
        """ステップ開始のテスト"""
        # ワークフローを初期化
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # 入力データ
        input_data = {"theme_preferences": ["教育", "エンターテイメント"]}
        
        # ステップを開始
        self.state_manager.start_step(self.test_project_id, 1, input_data)
        
        # 開始したステップの状態を確認
        step = self.state_manager.get_step_by_number(self.test_project_id, 1)
        self.assertEqual(step["status"], "running")
        self.assertIsNotNone(step["started_at"])
        self.assertIsNone(step["completed_at"])
        self.assertEqual(json.loads(step["input_data"]), input_data)
    
    def test_complete_step(self):
        """ステップ完了のテスト"""
        # ワークフローを初期化してステップを開始
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        self.state_manager.start_step(self.test_project_id, 1, {"test": "input"})
        
        # 出力データ
        output_data = {"selected_theme": "プログラミング入門", "confidence": 0.85}
        
        # ステップを完了
        self.state_manager.complete_step(self.test_project_id, 1, output_data)
        
        # 完了したステップの状態を確認
        step = self.state_manager.get_step_by_number(self.test_project_id, 1)
        self.assertEqual(step["status"], "completed")
        self.assertIsNotNone(step["started_at"])
        self.assertIsNotNone(step["completed_at"])
        self.assertEqual(json.loads(step["output_data"]), output_data)
    
    def test_fail_step_with_error(self):
        """ステップ失敗とエラー記録のテスト"""
        # ワークフローを初期化してステップを開始
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        self.state_manager.start_step(self.test_project_id, 1, {"test": "input"})
        
        # エラー情報
        error_message = "API接続エラー: タイムアウトが発生しました"
        
        # ステップを失敗
        self.state_manager.fail_step(self.test_project_id, 1, error_message)
        
        # 失敗したステップの状態を確認
        step = self.state_manager.get_step_by_number(self.test_project_id, 1)
        self.assertEqual(step["status"], "failed")
        self.assertIsNotNone(step["started_at"])
        self.assertIsNone(step["completed_at"])
        self.assertEqual(step["error_message"], error_message)
        self.assertEqual(step["retry_count"], 0)
    
    def test_retry_step(self):
        """ステップリトライのテスト"""
        # ワークフローを初期化してステップを失敗させる
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        self.state_manager.start_step(self.test_project_id, 1, {"test": "input"})
        self.state_manager.fail_step(self.test_project_id, 1, "初回エラー")
        
        # リトライを実行
        new_input_data = {"retry": True, "updated_params": "new_value"}
        self.state_manager.retry_step(self.test_project_id, 1, new_input_data)
        
        # リトライ後の状態を確認
        step = self.state_manager.get_step_by_number(self.test_project_id, 1)
        self.assertEqual(step["status"], "running")
        self.assertEqual(step["retry_count"], 1)
        self.assertIsNone(step["error_message"])  # エラーメッセージはクリア
        self.assertEqual(json.loads(step["input_data"]), new_input_data)
    
    def test_skip_step(self):
        """ステップスキップのテスト"""
        # ワークフローを初期化
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # ステップをスキップ
        skip_reason = "ユーザーが手動でスクリプトを提供"
        self.state_manager.skip_step(self.test_project_id, 2, skip_reason)
        
        # スキップしたステップの状態を確認
        step = self.state_manager.get_step_by_number(self.test_project_id, 2)
        self.assertEqual(step["status"], "skipped")
        self.assertIsNotNone(step["completed_at"])
        self.assertEqual(step["error_message"], skip_reason)
    
    def test_get_project_progress(self):
        """プロジェクト進捗取得のテスト"""
        # ワークフローを初期化
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
            {"step_number": 3, "step_name": "title_generation", "display_name": "タイトル生成"},
            {"step_number": 4, "step_name": "tts_generation", "display_name": "音声生成"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # 一部のステップを完了
        self.state_manager.start_step(self.test_project_id, 1, {})
        self.state_manager.complete_step(self.test_project_id, 1, {"result": "完了"})
        self.state_manager.start_step(self.test_project_id, 2, {})
        self.state_manager.complete_step(self.test_project_id, 2, {"result": "完了"})
        self.state_manager.start_step(self.test_project_id, 3, {})  # 実行中
        
        # 進捗情報を取得
        progress = self.state_manager.get_project_progress(self.test_project_id)
        
        # 進捗情報の確認
        self.assertEqual(progress["total_steps"], 4)
        self.assertEqual(progress["completed_steps"], 2)
        self.assertEqual(progress["running_steps"], 1)
        self.assertEqual(progress["pending_steps"], 1)
        self.assertEqual(progress["failed_steps"], 0)
        self.assertEqual(progress["skipped_steps"], 0)
        self.assertEqual(progress["completion_percentage"], 50.0)
        self.assertEqual(progress["current_step"]["step_number"], 3)
        self.assertEqual(progress["current_step"]["status"], "running")
    
    def test_get_step_by_name(self):
        """ステップ名での取得テスト"""
        # ワークフローを初期化
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # 名前でステップを取得
        step = self.state_manager.get_step_by_name(self.test_project_id, "script_generation")
        
        # 正しいステップが取得されることを確認
        self.assertEqual(step["step_number"], 2)
        self.assertEqual(step["step_name"], "script_generation")
        self.assertEqual(step["status"], "pending")
    
    def test_get_failed_steps(self):
        """失敗ステップ取得のテスト"""
        # ワークフローを初期化
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
            {"step_number": 3, "step_name": "title_generation", "display_name": "タイトル生成"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # 複数のステップを失敗させる
        self.state_manager.start_step(self.test_project_id, 1, {})
        self.state_manager.fail_step(self.test_project_id, 1, "エラー1")
        self.state_manager.start_step(self.test_project_id, 3, {})
        self.state_manager.fail_step(self.test_project_id, 3, "エラー3")
        
        # 失敗したステップを取得
        failed_steps = self.state_manager.get_failed_steps(self.test_project_id)
        
        # 失敗ステップの確認
        self.assertEqual(len(failed_steps), 2)
        step_numbers = [step["step_number"] for step in failed_steps]
        self.assertIn(1, step_numbers)
        self.assertIn(3, step_numbers)
        
        # エラーメッセージの確認
        for step in failed_steps:
            if step["step_number"] == 1:
                self.assertEqual(step["error_message"], "エラー1")
            elif step["step_number"] == 3:
                self.assertEqual(step["error_message"], "エラー3")
    
    def test_calculate_estimated_time(self):
        """推定時間計算のテスト"""
        # ワークフローを初期化
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
            {"step_number": 3, "step_name": "title_generation", "display_name": "タイトル生成"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # 手動でダミーデータを作成して時間計算をテスト
        start_time = "2025-01-01T10:00:00"
        end_time = "2025-01-01T10:01:00"  # 60秒後
        
        # 最初のステップを手動で完了状態に設定
        self.db_manager.execute_query(
            """
            UPDATE workflow_steps 
            SET status = ?, started_at = ?, completed_at = ?
            WHERE project_id = ? AND step_number = ?
            """,
            ("completed", start_time, end_time, self.test_project_id, 1)
        )
        
        # 推定残り時間を計算
        estimated_time = self.state_manager.calculate_estimated_remaining_time(self.test_project_id)
        
        # 残り2ステップなので約120秒と推定されることを確認
        self.assertAlmostEqual(estimated_time, 120.0, delta=10.0)
    
    def test_reset_step(self):
        """ステップリセットのテスト"""
        # ワークフローを初期化してステップを失敗させる
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, workflow_definition)
        
        # ステップを開始して失敗
        self.state_manager.start_step(self.test_project_id, 1, {"test": "input"})
        self.state_manager.fail_step(self.test_project_id, 1, "テストエラー")
        
        # リトライ回数を増やす
        self.state_manager.retry_step(self.test_project_id, 1, {})
        self.state_manager.fail_step(self.test_project_id, 1, "再度エラー")
        
        # ステップをリセット
        self.state_manager.reset_step(self.test_project_id, 1)
        
        # リセット後の状態を確認
        step = self.state_manager.get_step_by_number(self.test_project_id, 1)
        self.assertEqual(step["status"], "pending")
        self.assertIsNone(step["started_at"])
        self.assertIsNone(step["completed_at"])
        self.assertIsNone(step["error_message"])
        self.assertEqual(step["retry_count"], 0)
        self.assertEqual(step["input_data"], "{}")
        self.assertEqual(step["output_data"], "{}")


if __name__ == '__main__':
    unittest.main() 