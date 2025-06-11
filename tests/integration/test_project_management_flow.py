"""
プロジェクト管理フロー統合テスト

ProjectManager、ProjectStateManager、ProjectRecoveryManager、ProjectRepository間の
完全なプロジェクトライフサイクルを検証する統合テストです。
"""

import unittest
import tempfile
import shutil
import os
import time
from unittest.mock import patch

from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.project_manager import ProjectManager
from src.core.project_state_manager import ProjectStateManager
from src.core.project_recovery_manager import ProjectRecoveryManager
from src.core.project_repository import ProjectRepository


class TestProjectManagementFlow(unittest.TestCase):
    """プロジェクト管理フロー統合テストクラス"""
    
    def setUp(self):
        """テスト環境のセットアップ"""
        # 一時ディレクトリ作成
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_project_flow.db")
        self.projects_dir = os.path.join(self.temp_dir, "projects")
        
        # マネージャー初期化
        self.db_manager = DatabaseManager(self.db_path)
        self.fs_manager = FileSystemManager(self.projects_dir)
        self.project_repo = ProjectRepository(self.db_manager)
        
        self.project_manager = ProjectManager(
            self.db_manager, self.projects_dir
        )
        self.state_manager = ProjectStateManager(self.db_manager)
        self.recovery_manager = ProjectRecoveryManager(
            self.db_manager, self.project_manager, self.state_manager
        )
        
        # データベース初期化
        self.db_manager.initialize()
        
    def tearDown(self):
        """テスト環境のクリーンアップ"""
        if hasattr(self.db_manager, '_connection') and self.db_manager._connection:
            self.db_manager._connection.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_complete_project_lifecycle(self):
        """完全なプロジェクトライフサイクル統合テスト"""
        # 1. プロジェクト作成
        theme = "ライフサイクルテストテーマ"
        target_length_minutes = 5
        config = {
            "name": "ライフサイクルテストプロジェクト",
            "description": "プロジェクト管理フロー統合テスト"
        }
        
        # プロジェクト作成
        created_id = self.project_manager.create_project(
            theme=theme,
            target_length_minutes=target_length_minutes,
            config=config
        )
        self.assertIsNotNone(created_id)
        
        # 2. プロジェクト状態確認
        project = self.project_manager.get_project(created_id)
        self.assertEqual(project["theme"], theme)
        self.assertEqual(project["status"], "created")
        
        # 3. ワークフローステップ初期化（簡易実装）
        workflow_definition = [
            {"step_number": 1, "step_name": "theme_selection"},
            {"step_number": 2, "step_name": "script_generation"},
            {"step_number": 3, "step_name": "title_generation"}
        ]
        
        # 事前にワークフローステップを作成
        for step in workflow_definition:
            step_num = step["step_number"]
            step_name = step["step_name"]
            
            # ProjectRepositoryを使ってワークフローステップを作成
            self.project_repo.create_workflow_step(
                project_id=created_id,
                step_number=step_num,
                step_name=step_name,
                status="pending"
            )
        
        # ステップ実行（簡易）
        for step in workflow_definition:
            step_num = step["step_number"]
            self.state_manager.start_step(created_id, step_num)
            output_data = {"step": step["step_name"], "completed": True}
            self.state_manager.complete_step(created_id, step_num, output_data)
        
        # 4. 進捗状況確認
        progress = self.state_manager.get_project_progress(created_id)
        self.assertGreater(progress["completed_steps"], 0)
        
        # 5. プロジェクト状態確認
        project = self.project_manager.get_project(created_id)
        self.assertIsNotNone(project)


if __name__ == '__main__':
    unittest.main()