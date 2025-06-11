"""
テスト: プロジェクト復元機能システム (1-1-3: プロジェクト復元機能)

このテストファイルでは以下の機能をテストします：
- 中断からの再開
- 状態ファイル読み込み
- 整合性チェック
"""

import unittest
import tempfile
import shutil
import os
import uuid
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.project_recovery_manager import ProjectRecoveryManager, ProjectRecoveryError
from core.database_manager import DatabaseManager
from core.project_manager import ProjectManager
from core.project_state_manager import ProjectStateManager


class TestProjectRecoveryManager(unittest.TestCase):
    """プロジェクト復元機能システムのテストクラス"""
    
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
        
        # プロジェクト復元マネージャーを初期化
        self.recovery_manager = ProjectRecoveryManager(
            db_manager=self.db_manager,
            project_manager=self.project_manager,
            state_manager=self.state_manager
        )
        
        # テスト用プロジェクトを作成
        self.test_project_id = self.project_manager.create_project(
            theme="復元テスト用プロジェクト",
            target_length_minutes=5
        )
        
        # ワークフローを初期化
        self.workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
            {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
            {"step_number": 3, "step_name": "title_generation", "display_name": "タイトル生成"},
            {"step_number": 4, "step_name": "tts_generation", "display_name": "音声生成"}
        ]
        self.state_manager.initialize_workflow_steps(self.test_project_id, self.workflow_definition)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        # データベース接続を閉じる
        if hasattr(self.db_manager, 'close'):
            self.db_manager.close()
        
        # テンポラリディレクトリを削除
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_checkpoint(self):
        """チェックポイント作成のテスト"""
        # 一部のステップを実行状態にする
        self.state_manager.start_step(self.test_project_id, 1, {"input": "test"})
        self.state_manager.complete_step(self.test_project_id, 1, {"output": "completed"})
        self.state_manager.start_step(self.test_project_id, 2, {"input": "script"})
        
        # チェックポイントを作成
        checkpoint_data = self.recovery_manager.create_checkpoint(self.test_project_id)
        
        # チェックポイントデータの確認
        self.assertIn("project_metadata", checkpoint_data)
        self.assertIn("workflow_state", checkpoint_data)
        self.assertIn("file_integrity", checkpoint_data)
        self.assertIn("timestamp", checkpoint_data)
        
        # プロジェクトメタデータの確認
        project_metadata = checkpoint_data["project_metadata"]
        self.assertEqual(project_metadata["id"], self.test_project_id)
        self.assertEqual(project_metadata["theme"], "復元テスト用プロジェクト")
        
        # ワークフロー状態の確認
        workflow_state = checkpoint_data["workflow_state"]
        self.assertEqual(len(workflow_state["steps"]), 4)
        
        # 実行中ステップの確認
        running_steps = [s for s in workflow_state["steps"] if s["status"] == "running"]
        self.assertEqual(len(running_steps), 1)
        self.assertEqual(running_steps[0]["step_number"], 2)
    
    def test_save_checkpoint_to_file(self):
        """チェックポイントファイル保存のテスト"""
        # チェックポイントを作成
        checkpoint_data = self.recovery_manager.create_checkpoint(self.test_project_id)
        
        # ファイルに保存
        checkpoint_file = self.recovery_manager.save_checkpoint_to_file(
            self.test_project_id, 
            checkpoint_data
        )
        
        # ファイルが作成されていることを確認
        self.assertTrue(os.path.exists(checkpoint_file))
        
        # ファイル内容を確認
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data["project_metadata"]["id"], self.test_project_id)
        self.assertIn("workflow_state", saved_data)
        self.assertIn("file_integrity", saved_data)
    
    def test_load_checkpoint_from_file(self):
        """チェックポイントファイル読み込みのテスト"""
        # チェックポイントを保存
        checkpoint_data = self.recovery_manager.create_checkpoint(self.test_project_id)
        checkpoint_file = self.recovery_manager.save_checkpoint_to_file(
            self.test_project_id, 
            checkpoint_data
        )
        
        # ファイルから読み込み
        loaded_data = self.recovery_manager.load_checkpoint_from_file(checkpoint_file)
        
        # データの整合性を確認
        self.assertEqual(loaded_data["project_metadata"]["id"], self.test_project_id)
        self.assertEqual(
            loaded_data["workflow_state"]["steps"], 
            checkpoint_data["workflow_state"]["steps"]
        )
    
    def test_verify_project_integrity(self):
        """プロジェクト整合性チェックのテスト"""
        # 正常な状態での整合性チェック
        integrity_result = self.recovery_manager.verify_project_integrity(self.test_project_id)
        
        # 基本的な整合性チェック結果の確認
        self.assertIn("is_valid", integrity_result)
        self.assertIn("issues", integrity_result)
        self.assertIn("database_consistency", integrity_result)
        self.assertIn("file_system_consistency", integrity_result)
        
        # 正常な場合はvalidであることを確認
        self.assertTrue(integrity_result["is_valid"])
        self.assertEqual(len(integrity_result["issues"]), 0)
    
    def test_verify_project_integrity_with_missing_directory(self):
        """プロジェクトディレクトリ欠如での整合性チェックのテスト"""
        # プロジェクトディレクトリを削除
        project_dir = os.path.join(self.projects_dir, self.test_project_id)
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)
        
        # 整合性チェック
        integrity_result = self.recovery_manager.verify_project_integrity(self.test_project_id)
        
        # 不整合が検出されることを確認
        self.assertFalse(integrity_result["is_valid"])
        self.assertGreater(len(integrity_result["issues"]), 0)
        
        # ディレクトリ関連の問題が報告されることを確認
        directory_issues = [issue for issue in integrity_result["issues"] 
                          if "directory" in issue.lower() or "folder" in issue.lower()]
        self.assertGreater(len(directory_issues), 0)
    
    def test_restore_project_from_checkpoint(self):
        """チェックポイントからのプロジェクト復元のテスト"""
        # テスト用の進行状況を作成
        self.state_manager.start_step(self.test_project_id, 1, {"input": "test"})
        self.state_manager.complete_step(self.test_project_id, 1, {"output": "completed"})
        self.state_manager.start_step(self.test_project_id, 2, {"input": "script"})
        
        # チェックポイントを作成・保存
        checkpoint_data = self.recovery_manager.create_checkpoint(self.test_project_id)
        checkpoint_file = self.recovery_manager.save_checkpoint_to_file(
            self.test_project_id, 
            checkpoint_data
        )
        
        # データベースの状態を変更（復元が必要な状況をシミュレート）
        self.state_manager.reset_step(self.test_project_id, 1)
        self.state_manager.reset_step(self.test_project_id, 2)
        
        # チェックポイントから復元
        restore_result = self.recovery_manager.restore_project_from_checkpoint(
            self.test_project_id, 
            checkpoint_file
        )
        
        # 復元結果の確認
        self.assertTrue(restore_result["success"])
        self.assertIn("restored_steps", restore_result)
        
        # ステップ状態が復元されていることを確認
        step1 = self.state_manager.get_step_by_number(self.test_project_id, 1)
        step2 = self.state_manager.get_step_by_number(self.test_project_id, 2)
        
        self.assertEqual(step1["status"], "completed")
        self.assertEqual(step2["status"], "running")
    
    def test_resume_interrupted_project(self):
        """中断プロジェクトの再開のテスト"""
        # プロジェクトを実行中の状態にする
        self.state_manager.start_step(self.test_project_id, 1, {"input": "test"})
        self.state_manager.complete_step(self.test_project_id, 1, {"output": "completed"})
        self.state_manager.start_step(self.test_project_id, 2, {"input": "script"})
        
        # プロジェクトを中断状態にマーク
        self.project_manager.update_project_status(self.test_project_id, "interrupted")
        
        # プロジェクトを再開
        resume_result = self.recovery_manager.resume_interrupted_project(self.test_project_id)
        
        # 再開結果の確認
        self.assertTrue(resume_result["success"])
        self.assertIn("current_step", resume_result)
        self.assertIn("next_actions", resume_result)
        
        # プロジェクトステータスが更新されていることを確認
        project = self.project_manager.get_project(self.test_project_id)
        self.assertEqual(project["status"], "running")
        
        # 現在のステップが正しく特定されていることを確認
        self.assertEqual(resume_result["current_step"]["step_number"], 2)
        self.assertEqual(resume_result["current_step"]["status"], "running")
    
    def test_find_interrupted_projects(self):
        """中断プロジェクト検索のテスト"""
        # 複数のプロジェクトを作成
        project_id2 = self.project_manager.create_project(
            theme="テストプロジェクト2",
            target_length_minutes=3
        )
        project_id3 = self.project_manager.create_project(
            theme="テストプロジェクト3",
            target_length_minutes=7
        )
        
        # 一部のプロジェクトを中断状態にする
        self.project_manager.update_project_status(self.test_project_id, "interrupted")
        self.project_manager.update_project_status(project_id2, "completed")
        self.project_manager.update_project_status(project_id3, "interrupted")
        
        # 中断プロジェクトを検索
        interrupted_projects = self.recovery_manager.find_interrupted_projects()
        
        # 2つの中断プロジェクトが見つかることを確認
        self.assertEqual(len(interrupted_projects), 2)
        
        interrupted_ids = [p["id"] for p in interrupted_projects]
        self.assertIn(self.test_project_id, interrupted_ids)
        self.assertIn(project_id3, interrupted_ids)
        self.assertNotIn(project_id2, interrupted_ids)
    
    def test_auto_save_checkpoint(self):
        """自動チェックポイント保存のテスト"""
        # ステップを実行
        self.state_manager.start_step(self.test_project_id, 1, {"input": "test"})
        
        # 自動チェックポイント保存を実行
        checkpoint_file = self.recovery_manager.auto_save_checkpoint(self.test_project_id)
        
        # チェックポイントファイルが作成されていることを確認
        self.assertTrue(os.path.exists(checkpoint_file))
        
        # ファイル名にタイムスタンプが含まれていることを確認
        filename = os.path.basename(checkpoint_file)
        self.assertTrue(filename.startswith(f"checkpoint_{self.test_project_id}_"))
        self.assertTrue(filename.endswith(".json"))
    
    def test_cleanup_old_checkpoints(self):
        """古いチェックポイントのクリーンアップのテスト"""
        # 複数のチェックポイントを作成
        checkpoints = []
        for i in range(5):
            checkpoint_data = self.recovery_manager.create_checkpoint(self.test_project_id)
            checkpoint_file = self.recovery_manager.save_checkpoint_to_file(
                self.test_project_id, 
                checkpoint_data,
                suffix=f"_test_{i}"
            )
            checkpoints.append(checkpoint_file)
        
        # 全てのチェックポイントが存在することを確認
        for checkpoint in checkpoints:
            self.assertTrue(os.path.exists(checkpoint))
        
        # 古いチェックポイントをクリーンアップ（最新2つを保持）
        cleaned_count = self.recovery_manager.cleanup_old_checkpoints(
            self.test_project_id, 
            keep_count=2
        )
        
        # 3つのファイルが削除されたことを確認
        self.assertEqual(cleaned_count, 3)
        
        # 最新2つのチェックポイントが残っていることを確認
        existing_checkpoints = [cp for cp in checkpoints if os.path.exists(cp)]
        self.assertEqual(len(existing_checkpoints), 2)
    
    def test_validate_checkpoint_data(self):
        """チェックポイントデータの検証のテスト"""
        # 正常なチェックポイントデータ
        valid_checkpoint = self.recovery_manager.create_checkpoint(self.test_project_id)
        
        # 正常データの検証
        validation_result = self.recovery_manager.validate_checkpoint_data(valid_checkpoint)
        self.assertTrue(validation_result["is_valid"])
        self.assertEqual(len(validation_result["errors"]), 0)
        
        # 不正なデータの検証
        invalid_checkpoint = {
            "project_metadata": {},  # 必須フィールドが欠如
            "workflow_state": None,  # 無効な形式
            "timestamp": "invalid_timestamp"
        }
        
        validation_result = self.recovery_manager.validate_checkpoint_data(invalid_checkpoint)
        self.assertFalse(validation_result["is_valid"])
        self.assertGreater(len(validation_result["errors"]), 0)
    
    def test_get_recovery_recommendations(self):
        """復旧推奨アクションの取得のテスト"""
        # 失敗ステップを含む状況を作成
        self.state_manager.start_step(self.test_project_id, 1, {"input": "test"})
        self.state_manager.fail_step(self.test_project_id, 1, "API エラー")
        self.state_manager.start_step(self.test_project_id, 2, {"input": "script"})
        
        # 推奨アクションを取得
        recommendations = self.recovery_manager.get_recovery_recommendations(self.test_project_id)
        
        # 推奨アクションの確認
        self.assertIn("failed_steps", recommendations)
        self.assertIn("recommended_actions", recommendations)
        self.assertIn("priority", recommendations)
        
        # 失敗ステップに対する推奨アクションが含まれることを確認
        self.assertEqual(len(recommendations["failed_steps"]), 1)
        self.assertGreater(len(recommendations["recommended_actions"]), 0)


if __name__ == '__main__':
    unittest.main() 