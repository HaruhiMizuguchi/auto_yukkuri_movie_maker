"""
テスト: プロジェクト管理システム (1-1-1: プロジェクト作成機能)

このテストファイルでは以下の機能をテストします：
- プロジェクト作成機能
- ディレクトリ構造自動生成
- プロジェクトID管理
- メタデータ保存
"""

import unittest
import tempfile
import shutil
import os
import uuid
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
from datetime import datetime

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.project_manager import ProjectManager
from core.database_manager import DatabaseManager


class TestProjectManager(unittest.TestCase):
    """プロジェクト管理システムのテストクラス"""
    
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
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        # データベース接続を閉じる
        if hasattr(self.db_manager, 'close'):
            self.db_manager.close()
        
        # テンポラリディレクトリを削除
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_project_basic(self):
        """基本的なプロジェクト作成のテスト"""
        # テストデータ
        project_config = {
            "theme": "テスト用テーマ",
            "target_length_minutes": 5,
            "content_style": "educational",
            "target_audience": "general"
        }
        
        # プロジェクト作成
        project_id = self.project_manager.create_project(
            theme=project_config["theme"],
            target_length_minutes=project_config["target_length_minutes"],
            config=project_config
        )
        
        # プロジェクトIDが生成されていることを確認
        self.assertIsNotNone(project_id)
        self.assertIsInstance(project_id, str)
        self.assertEqual(len(project_id), 36)  # UUID形式
        
        # プロジェクトがデータベースに登録されていることを確認
        project_data = self.project_manager.get_project(project_id)
        self.assertIsNotNone(project_data)
        self.assertEqual(project_data["theme"], project_config["theme"])
        self.assertEqual(project_data["target_length_minutes"], project_config["target_length_minutes"])
    
    def test_project_directory_structure_creation(self):
        """プロジェクトディレクトリ構造の自動生成テスト"""
        # プロジェクト作成
        project_id = self.project_manager.create_project(
            theme="ディレクトリ構造テスト",
            target_length_minutes=3
        )
        
        # プロジェクトディレクトリの存在確認
        project_dir = os.path.join(self.projects_dir, project_id)
        self.assertTrue(os.path.exists(project_dir))
        self.assertTrue(os.path.isdir(project_dir))
        
        # 必須サブディレクトリの存在確認
        expected_subdirs = [
            "files/audio",
            "files/video",
            "files/images",
            "files/scripts",
            "files/metadata",
            "logs",
            "cache"
        ]
        
        for subdir in expected_subdirs:
            subdir_path = os.path.join(project_dir, subdir)
            self.assertTrue(os.path.exists(subdir_path), f"ディレクトリが存在しない: {subdir}")
            self.assertTrue(os.path.isdir(subdir_path), f"ディレクトリではない: {subdir}")
    
    def test_project_id_uniqueness(self):
        """プロジェクトIDの一意性テスト"""
        # 複数のプロジェクトを作成
        project_ids = []
        for i in range(10):
            project_id = self.project_manager.create_project(
                theme=f"テーマ{i}",
                target_length_minutes=5
            )
            project_ids.append(project_id)
        
        # すべてのIDが一意であることを確認
        unique_ids = set(project_ids)
        self.assertEqual(len(unique_ids), len(project_ids))
        
        # すべてがUUID形式であることを確認
        for project_id in project_ids:
            try:
                uuid.UUID(project_id)
            except ValueError:
                self.fail(f"無効なUUID形式: {project_id}")
    
    def test_project_metadata_saving(self):
        """プロジェクトメタデータの保存テスト"""
        # 詳細な設定でプロジェクト作成
        config = {
            "theme": "詳細設定テスト",
            "target_length_minutes": 7,
            "content_style": "entertainment",
            "target_audience": "adults",
            "preferred_genres": ["comedy", "tutorial"],
            "excluded_genres": ["horror"],
            "custom_settings": {
                "voice_speed": 1.0,
                "background_music": True
            }
        }
        
        project_id = self.project_manager.create_project(
            theme=config["theme"],
            target_length_minutes=config["target_length_minutes"],
            config=config
        )
        
        # 保存されたメタデータを取得
        saved_project = self.project_manager.get_project(project_id)
        
        # 基本情報の確認
        self.assertEqual(saved_project["id"], project_id)
        self.assertEqual(saved_project["theme"], config["theme"])
        self.assertEqual(saved_project["target_length_minutes"], config["target_length_minutes"])
        self.assertEqual(saved_project["status"], "created")
        
        # 設定情報の確認
        saved_config = json.loads(saved_project["config_json"])
        self.assertEqual(saved_config["content_style"], config["content_style"])
        self.assertEqual(saved_config["target_audience"], config["target_audience"])
        self.assertEqual(saved_config["preferred_genres"], config["preferred_genres"])
        self.assertEqual(saved_config["excluded_genres"], config["excluded_genres"])
        self.assertEqual(saved_config["custom_settings"], config["custom_settings"])
        
        # タイムスタンプの確認
        self.assertIsNotNone(saved_project["created_at"])
        self.assertIsNotNone(saved_project["updated_at"])
    
    def test_create_project_with_minimal_params(self):
        """最小限のパラメータでのプロジェクト作成テスト"""
        # 必須パラメータのみでプロジェクト作成
        project_id = self.project_manager.create_project(theme="最小パラメータテスト")
        
        # プロジェクトが正常に作成されることを確認
        self.assertIsNotNone(project_id)
        
        # デフォルト値が適用されることを確認
        project_data = self.project_manager.get_project(project_id)
        self.assertEqual(project_data["theme"], "最小パラメータテスト")
        self.assertEqual(project_data["target_length_minutes"], 5)  # デフォルト値
        self.assertEqual(project_data["status"], "created")
    
    def test_create_project_invalid_params(self):
        """無効なパラメータでのプロジェクト作成エラーテスト"""
        # 空のテーマでエラーが発生することを確認
        with self.assertRaises(ValueError):
            self.project_manager.create_project(theme="")
        
        # 無効な長さでエラーが発生することを確認
        with self.assertRaises(ValueError):
            self.project_manager.create_project(theme="テスト", target_length_minutes=0)
        
        with self.assertRaises(ValueError):
            self.project_manager.create_project(theme="テスト", target_length_minutes=-1)
    
    def test_get_project_not_found(self):
        """存在しないプロジェクトの取得テスト"""
        # 存在しないプロジェクトIDで取得試行
        fake_id = str(uuid.uuid4())
        result = self.project_manager.get_project(fake_id)
        
        # Noneが返されることを確認
        self.assertIsNone(result)
    
    def test_list_projects(self):
        """プロジェクト一覧取得テスト"""
        # 複数のプロジェクトを作成
        project_data = [
            {"theme": "プロジェクト1", "target_length_minutes": 3},
            {"theme": "プロジェクト2", "target_length_minutes": 5},
            {"theme": "プロジェクト3", "target_length_minutes": 7}
        ]
        
        created_ids = []
        for data in project_data:
            project_id = self.project_manager.create_project(**data)
            created_ids.append(project_id)
        
        # プロジェクト一覧を取得
        projects = self.project_manager.list_projects()
        
        # 作成したプロジェクトがすべて含まれることを確認
        self.assertEqual(len(projects), len(project_data))
        
        found_ids = [p["id"] for p in projects]
        for project_id in created_ids:
            self.assertIn(project_id, found_ids)
    
    def test_project_directory_creation_failure_handling(self):
        """ディレクトリ作成失敗時のエラーハンドリングテスト"""
        # モックを使用してディレクトリ作成を失敗させる
        with patch.object(self.project_manager, '_create_project_directory_structure', 
                         side_effect=OSError("ディレクトリ作成に失敗")):
            # ディレクトリ作成に失敗することを確認
            with self.assertRaises((OSError, Exception)):
                self.project_manager.create_project(theme="失敗テスト")
    
    def test_database_transaction_rollback_on_directory_failure(self):
        """ディレクトリ作成失敗時のデータベーストランザクションロールバックテスト"""
        # 初期状態でプロジェクトが0個であることを確認
        initial_projects = self.project_manager.list_projects()
        self.assertEqual(len(initial_projects), 0)
        
        # モックを使用してディレクトリ作成メソッドを失敗させる
        with patch.object(self.project_manager, '_create_project_directory_structure', 
                         side_effect=OSError("ディレクトリ作成失敗")):
            # プロジェクト作成が失敗することを確認
            with self.assertRaises((OSError, Exception)):
                self.project_manager.create_project(theme="ロールバックテスト")
        
        # データベースにプロジェクトが残っていないことを確認
        projects = self.project_manager.list_projects()
        self.assertEqual(len(projects), 0)


if __name__ == '__main__':
    unittest.main() 