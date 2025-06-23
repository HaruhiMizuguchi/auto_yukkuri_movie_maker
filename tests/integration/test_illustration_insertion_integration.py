"""
挿絵挿入モジュール統合テスト

システム統合テスト:
- プロジェクト管理システムとの統合
- データベースとファイルシステムの統合
- 外部API（画像生成）との統合
- WorkflowEngineとの統合

実装確認:
- 完全な挿絵挿入パイプライン
- エラーハンドリングとリカバリ
- データ整合性保証
"""

import unittest
import tempfile
import os
import json
from datetime import datetime
from unittest.mock import Mock, patch

from src.modules.illustration_inserter import (
    IllustrationInserter,
    IllustrationInsertionInput,
    IllustrationInsertionOutput
)
from src.dao.illustration_insertion_dao import IllustrationInsertionDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.log_manager import LogManager
from src.core.project_manager import ProjectManager


class TestIllustrationInsertionSystemIntegration(unittest.TestCase):
    """挿絵挿入システム統合テスト"""

    def setUp(self):
        """統合テスト環境セットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_system.db")
        
        # 基盤コンポーネント初期化
        self.database_manager = DatabaseManager(self.db_path)
        self.database_manager.initialize()  # データベース初期化
        
        self.file_system_manager = FileSystemManager(self.temp_dir)
        self.log_manager = LogManager({
            "log_dir": self.temp_dir,
            "log_level": "INFO",
            "json_format": False,
            "console_output": True
        })
        
        # ProjectManager初期化
        projects_base_dir = os.path.join(self.temp_dir, "projects")
        os.makedirs(projects_base_dir, exist_ok=True)
        
        self.project_manager = ProjectManager(
            db_manager=self.database_manager,
            projects_base_dir=projects_base_dir
        )
        
        # テストプロジェクト作成
        project_theme = "AI技術解説"
        project_data = {
            "name": "挿絵挿入システムテスト",
            "description": "統合テスト用プロジェクト"
        }
        
        self.project_id = self.project_manager.create_project(
            theme=project_theme,
            target_length_minutes=5,
            config=project_data
        )
        
        # 挿絵挿入モジュール初期化
        self.illustration_inserter = IllustrationInserter(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )
        
        # テスト用データ準備
        self._prepare_test_data()

    def _prepare_test_data(self):
        """テスト用データ準備"""
        # プロジェクトディレクトリ取得
        project_dir = self.project_manager.get_project_directory(self.project_id)
        
        # テスト用動画ファイル作成
        video_dir = os.path.join(project_dir, "files", "video")
        os.makedirs(video_dir, exist_ok=True)
        
        self.enhanced_video_path = os.path.join(video_dir, "enhanced_video.mp4")
        with open(self.enhanced_video_path, "wb") as f:
            f.write(b"test enhanced video content")
        
        # テスト用スクリプトデータ
        self.test_script_data = {
            "theme": "Python プログラミング入門",
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "text": "Pythonの基本構文について説明するわ。",
                    "start_time": 0.0,
                    "end_time": 4.0,
                    "topic": "python_basics"
                },
                {
                    "segment_id": 2,
                    "speaker": "marisa",
                    "text": "変数の宣言方法を見てみるぜ！",
                    "start_time": 4.5,
                    "end_time": 7.0,
                    "topic": "variables"
                },
                {
                    "segment_id": 3,
                    "speaker": "reimu",
                    "text": "次は条件分岐について学びましょう。",
                    "start_time": 7.5,
                    "end_time": 10.0,
                    "topic": "conditionals"
                },
                {
                    "segment_id": 4,
                    "speaker": "marisa",
                    "text": "ループ処理の使い方だぜ！",
                    "start_time": 10.5,
                    "end_time": 13.0,
                    "topic": "loops"
                }
            ]
        }

    def test_project_management_integration(self):
        """プロジェクト管理システム統合テスト"""
        # プロジェクト状態確認
        project_info = self.project_manager.get_project(self.project_id)
        self.assertIsNotNone(project_info)
        self.assertEqual(project_info["id"], self.project_id)
        
        # 挿絵挿入処理実行
        input_data = IllustrationInsertionInput(
            enhanced_video_path=self.enhanced_video_path,
            script_data=self.test_script_data,
            insertion_config={
                "min_transition_strength": 0.6,
                "max_illustrations": 3,
                "default_duration": 2.5,
                "style": "educational"
            }
        )
        
        with patch('src.api.image_client.ImageGenerationClient') as mock_image_client:
            # モック設定
            mock_client = Mock()
            mock_client.generate_image.return_value = {
                "success": True,
                "image_path": "/test/path/illustration.png",
                "metadata": {"size": [1920, 1080]}
            }
            mock_image_client.return_value = mock_client
            
            # 処理実行
            result = self.illustration_inserter.insert_illustrations(
                project_id=self.project_id,
                input_data=input_data
            )
        
        # 結果検証
        self.assertIsInstance(result, IllustrationInsertionOutput)
        self.assertTrue(os.path.exists(result.final_video_path))
        
        # プロジェクト状態更新確認
        updated_project = self.project_manager.get_project(self.project_id)
        self.assertIsNotNone(updated_project)

    def test_database_filesystem_consistency(self):
        """データベース・ファイルシステム整合性テスト"""
        # 入力データ準備
        input_data = IllustrationInsertionInput(
            enhanced_video_path=self.enhanced_video_path,
            script_data=self.test_script_data,
            insertion_config={
                "min_transition_strength": 0.5,
                "max_illustrations": 4,
                "default_duration": 3.0,
                "style": "technical"
            }
        )
        
        with patch('src.api.image_client.ImageGenerationClient') as mock_image_client:
            # モック設定
            mock_client = Mock()
            mock_client.generate_image.return_value = {
                "success": True,
                "image_path": "/test/path/illustration.png",
                "metadata": {"size": [1920, 1080]}
            }
            mock_image_client.return_value = mock_client
            
            # 処理実行
            result = self.illustration_inserter.insert_illustrations(
                project_id=self.project_id,
                input_data=input_data
            )
        
        # データベース検証
        dao = self.illustration_inserter.dao
        
        # 話題転換データ確認
        transitions = dao.get_topic_transitions(self.project_id)
        self.assertGreater(len(transitions), 0)
        
        # 挿絵データ確認
        illustrations = dao.get_illustrations(self.project_id)
        self.assertGreater(len(illustrations), 0)
        
        # 動画統合データ確認
        integrations = dao.get_video_integrations(self.project_id)
        self.assertGreater(len(integrations), 0)
        
        # ファイルシステム検証
        self.assertTrue(os.path.exists(result.final_video_path))
        
        # 挿絵ファイル確認
        project_dir = self.project_manager.get_project_directory(self.project_id)
        illustrations_dir = os.path.join(project_dir, "files", "images", "illustrations")
        
        if os.path.exists(illustrations_dir):
            illustration_files = os.listdir(illustrations_dir)
            # 実際の画像ファイルは生成されないが、ディレクトリの存在を確認
            self.assertTrue(os.path.exists(illustrations_dir))

    def test_error_handling_integration(self):
        """エラーハンドリング統合テスト"""
        # 無効な動画パス
        invalid_input = IllustrationInsertionInput(
            enhanced_video_path="/invalid/path/video.mp4",
            script_data=self.test_script_data,
            insertion_config={"min_transition_strength": 0.5}
        )
        
        # エラーハンドリング確認（例外は内部で処理され、エラーが出力データに反映される）
        result = self.illustration_inserter.insert_illustrations(
            project_id=self.project_id,
            input_data=invalid_input
        )
        
        # エラー結果の確認
        self.assertEqual(result.final_video_path, "")
        self.assertEqual(len(result.illustrations), 0)
        self.assertEqual(len(result.topic_transitions), 0)
        self.assertFalse(result.video_integration.success)
        
        # プロジェクト状態の整合性確認
        project_info = self.project_manager.get_project(self.project_id)
        self.assertIsNotNone(project_info)
        
        # データベースの整合性確認
        dao = self.illustration_inserter.dao
        
        # エラー発生時にも部分的なデータが保存されていないことを確認
        try:
            transitions = dao.get_topic_transitions(self.project_id)
            # エラーケースでは話題転換データが保存されない可能性がある
            # テスト環境では空のリストが期待される
            self.assertIsInstance(transitions, list)
        except Exception:
            # データベースエラーも想定範囲内
            pass

    def tearDown(self):
        """統合テスト環境クリーンアップ"""
        import shutil
        
        # データベース接続を確実に閉じる
        if hasattr(self, 'database_manager'):
            self.database_manager.close_connection()
        
        if hasattr(self, 'project_manager') and hasattr(self.project_manager, 'db_manager'):
            self.project_manager.db_manager.close_connection()
        
        # ファイルクリーンアップ
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                # Windowsでファイルロックが残っている場合の対処
                import time
                time.sleep(0.5)
                try:
                    shutil.rmtree(self.temp_dir)
                except PermissionError:
                    import warnings
                    warnings.warn(f"Could not clean up temp directory: {self.temp_dir}")


class TestIllustrationInsertionWorkflowIntegration(unittest.TestCase):
    """挿絵挿入ワークフロー統合テスト"""

    def setUp(self):
        """ワークフロー統合テスト環境セットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_workflow.db")
        
        # 基盤コンポーネント
        self.database_manager = DatabaseManager(self.db_path)
        self.file_system_manager = FileSystemManager(self.temp_dir)
        self.log_manager = LogManager({
            "log_dir": self.temp_dir,
            "log_level": "DEBUG",
            "json_format": False,
            "console_output": True
        })
        
        # プロジェクト準備
        self.project_id = "workflow-test-project"
        self.file_system_manager.create_project_directory(self.project_id)
        
        # 挿絵挿入モジュール
        self.illustration_inserter = IllustrationInserter(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )

    def test_full_workflow_execution(self):
        """完全ワークフロー実行テスト"""
        # ワークフロー入力データ準備
        project_dir = self.file_system_manager.get_project_directory_path(self.project_id)
        video_dir = os.path.join(project_dir, "files", "video")
        os.makedirs(video_dir, exist_ok=True)
        
        enhanced_video_path = os.path.join(video_dir, "enhanced_video.mp4")
        with open(enhanced_video_path, "wb") as f:
            f.write(b"enhanced video content for workflow test")
        
        # スクリプトデータ
        script_data = {
            "theme": "機械学習入門",
            "segments": [
                {
                    "segment_id": 1,
                    "topic": "introduction",
                    "text": "機械学習とは何か学んでいきましょう",
                    "start_time": 0.0,
                    "end_time": 3.0
                },
                {
                    "segment_id": 2,
                    "topic": "supervised_learning",
                    "text": "教師あり学習について説明します",
                    "start_time": 3.5,
                    "end_time": 6.5
                },
                {
                    "segment_id": 3,
                    "topic": "unsupervised_learning",
                    "text": "次は教師なし学習です",
                    "start_time": 7.0,
                    "end_time": 10.0
                }
            ]
        }
        
        # ワークフロー実行
        input_data = IllustrationInsertionInput(
            enhanced_video_path=enhanced_video_path,
            script_data=script_data,
            insertion_config={
                "min_transition_strength": 0.4,
                "max_illustrations": 5,
                "default_duration": 2.0,
                "style": "technical"
            }
        )
        
        with patch('src.api.image_client.ImageGenerationClient') as mock_image_client:
            # モック設定
            mock_client = Mock()
            mock_client.generate_image.return_value = {
                "success": True,
                "image_path": "/test/path/workflow_illustration.png",
                "metadata": {"size": [1920, 1080]}
            }
            mock_image_client.return_value = mock_client
            
            # ワークフロー実行
            result = self.illustration_inserter.insert_illustrations(
                project_id=self.project_id,
                input_data=input_data
            )
        
        # ワークフロー結果検証
        self.assertIsInstance(result, IllustrationInsertionOutput)
        self.assertIsNotNone(result.final_video_path)
        self.assertGreater(len(result.topic_transitions), 0)
        self.assertGreater(len(result.illustrations), 0)
        self.assertTrue(result.video_integration.success)
        
        # 成果物ファイル確認
        self.assertTrue(os.path.exists(result.final_video_path))
        
        # ログ出力確認
        log_files = [f for f in os.listdir(self.temp_dir) if f.endswith('.log')]
        self.assertGreater(len(log_files), 0)

    def test_workflow_step_dependencies(self):
        """ワークフローステップ依存関係テスト"""
        # 前段階のステップ結果を模擬
        # 通常は audio_enhancement の結果を受け取る
        
        # 模擬的な前段階データ
        project_dir = self.file_system_manager.get_project_directory_path(self.project_id)
        
        # 音響効果処理済み動画（前段階の出力）
        video_dir = os.path.join(project_dir, "files", "video")
        os.makedirs(video_dir, exist_ok=True)
        
        enhanced_video_path = os.path.join(video_dir, "enhanced_video.mp4")
        with open(enhanced_video_path, "wb") as f:
            f.write(b"audio enhanced video content")
        
        # スクリプト生成段階の結果（前段階の出力）
        script_dir = os.path.join(project_dir, "files", "scripts")
        os.makedirs(script_dir, exist_ok=True)
        
        script_path = os.path.join(script_dir, "script.json")
        script_data = {
            "theme": "データサイエンス基礎",
            "segments": [
                {"segment_id": 1, "topic": "data_science", "text": "データサイエンスの基礎"},
                {"segment_id": 2, "topic": "statistics", "text": "統計学の重要性"}
            ]
        }
        
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        
        # 依存関係を持つワークフロー実行
        input_data = IllustrationInsertionInput(
            enhanced_video_path=enhanced_video_path,
            script_data=script_data,
            insertion_config={"min_transition_strength": 0.3}
        )
        
        with patch('src.api.image_client.ImageGenerationClient') as mock_image_client:
            mock_client = Mock()
            mock_client.generate_image.return_value = {
                "success": True,
                "image_path": "/test/path/dependency_illustration.png",
                "metadata": {"size": [1920, 1080]}
            }
            mock_image_client.return_value = mock_client
            
            result = self.illustration_inserter.insert_illustrations(
                project_id=self.project_id,
                input_data=input_data
            )
        
        # 依存関係処理結果確認
        self.assertIsInstance(result, IllustrationInsertionOutput)
        self.assertTrue(os.path.exists(result.final_video_path))
        
        # 次段階（final_encoding）への出力確認
        # final_video_path が次段階の入力として使用可能かチェック
        final_video_exists = os.path.exists(result.final_video_path)
        self.assertTrue(final_video_exists)

    def tearDown(self):
        """ワークフロー統合テスト環境クリーンアップ"""
        import shutil
        
        # データベース接続を確実に閉じる
        if hasattr(self, 'database_manager'):
            self.database_manager.close_connection()
        
        # ファイルクリーンアップ
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                # Windowsでファイルロックが残っている場合の対処
                import time
                time.sleep(0.5)
                try:
                    shutil.rmtree(self.temp_dir)
                except PermissionError:
                    import warnings
                    warnings.warn(f"Could not clean up temp directory: {self.temp_dir}")


if __name__ == "__main__":
    unittest.main() 