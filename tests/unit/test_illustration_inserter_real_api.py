"""
挿絵挿入モジュール実API単体テスト

flow_definition.yamlに基づく仕様:
- step_id: 11 (illustration_insertion)
- 入力: enhanced_video + script_content
- 処理: 話題転換点検出・挿絵生成・動画統合
- 出力: final_video + illustrations

実装対象:
- IllustrationInserter: メインクラス
- IllustrationInsertionDAO: データアクセス
- 挿入タイミング検出機能
- 挿絵生成機能
- 動画統合機能
"""

import unittest
import tempfile
import os
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.modules.illustration_inserter import (
    IllustrationInserter,
    IllustrationInsertionInput,
    IllustrationInsertionOutput,
    TopicTransition,
    IllustrationSpec,
    VideoIntegration
)
from src.dao.illustration_insertion_dao import IllustrationInsertionDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.log_manager import LogManager


class TestIllustrationInserter(unittest.TestCase):
    """挿絵挿入モジュール単体テスト"""

    def setUp(self):
        """テスト環境セットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        # コンポーネント初期化
        self.database_manager = DatabaseManager(self.db_path)
        self.file_system_manager = FileSystemManager(self.temp_dir)
        self.log_manager = LogManager({
            "log_dir": self.temp_dir,
            "log_level": "DEBUG",
            "json_format": False,
            "console_output": True
        })
        
        # テスト用プロジェクト作成
        self.project_id = "test-illustration-project"
        self.file_system_manager.create_project_directory(self.project_id)
        
        # IllustrationInserter初期化
        self.illustration_inserter = IllustrationInserter(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )
        
        # テストデータ準備
        self._setup_test_data()

    def _setup_test_data(self):
        """テストデータ準備"""
        # テスト用動画ファイル作成
        self.test_video_dir = os.path.join(
            self.temp_dir, self.project_id, "files", "video"
        )
        os.makedirs(self.test_video_dir, exist_ok=True)
        
        self.enhanced_video_path = os.path.join(
            self.test_video_dir, "enhanced_video.mp4"
        )
        with open(self.enhanced_video_path, "wb") as f:
            f.write(b"test enhanced video content")
        
        # テスト用スクリプト作成
        self.test_script_data = {
            "theme": "プログラミング基礎講座",
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "text": "今日はプログラミングについて学ぼう！",
                    "start_time": 0.0,
                    "end_time": 3.0,
                    "topic": "introduction"
                },
                {
                    "segment_id": 2,
                    "speaker": "marisa",
                    "text": "変数って何だぜ？",
                    "start_time": 3.5,
                    "end_time": 5.0,
                    "topic": "variables"
                },
                {
                    "segment_id": 3,
                    "speaker": "reimu",
                    "text": "変数は値を格納する箱のようなものね。",
                    "start_time": 5.5,
                    "end_time": 8.0,
                    "topic": "variables"
                },
                {
                    "segment_id": 4,
                    "speaker": "marisa",
                    "text": "次は関数について話すぜ！",
                    "start_time": 8.5,
                    "end_time": 10.0,
                    "topic": "functions"
                },
                {
                    "segment_id": 5,
                    "speaker": "reimu",
                    "text": "関数は処理をまとめるためのものよ。",
                    "start_time": 10.5,
                    "end_time": 13.0,
                    "topic": "functions"
                }
            ]
        }

    def test_01_initialization(self):
        """初期化テスト"""
        # 正常初期化確認
        self.assertIsInstance(self.illustration_inserter, IllustrationInserter)
        self.assertIsInstance(self.illustration_inserter.dao, IllustrationInsertionDAO)
        
        # 必要な属性の存在確認
        self.assertTrue(hasattr(self.illustration_inserter, 'database_manager'))
        self.assertTrue(hasattr(self.illustration_inserter, 'file_system_manager'))
        self.assertTrue(hasattr(self.illustration_inserter, 'log_manager'))

    def test_02_detect_topic_transitions(self):
        """話題転換検出テスト"""
        # 話題転換検出実行
        transitions = self.illustration_inserter.detect_topic_transitions(
            self.test_script_data["segments"]
        )
        
        # 結果検証
        self.assertIsInstance(transitions, list)
        self.assertGreater(len(transitions), 0)
        
        # 各転換点の検証
        for transition in transitions:
            self.assertIsInstance(transition, TopicTransition)
            self.assertIsInstance(transition.transition_id, str)
            self.assertIsInstance(transition.from_topic, str)
            self.assertIsInstance(transition.to_topic, str)
            self.assertIsInstance(transition.transition_time, float)
            self.assertIsInstance(transition.transition_type, str)
            self.assertIsInstance(transition.transition_strength, float)
            self.assertGreaterEqual(transition.transition_strength, 0.0)
            self.assertLessEqual(transition.transition_strength, 1.0)
        
        # 期待される転換の確認（introduction→variables、variables→functions）
        topic_pairs = [(t.from_topic, t.to_topic) for t in transitions]
        self.assertIn(("introduction", "variables"), topic_pairs)
        self.assertIn(("variables", "functions"), topic_pairs)

    def test_03_generate_illustrations(self):
        """挿絵生成テスト"""
        # 話題転換検出
        transitions = self.illustration_inserter.detect_topic_transitions(
            self.test_script_data["segments"]
        )
        
        # 挿絵生成実行
        illustrations = self.illustration_inserter.generate_illustrations(
            project_id=self.project_id,
            transitions=transitions,
            theme=self.test_script_data["theme"]
        )
        
        # 結果検証
        self.assertIsInstance(illustrations, list)
        self.assertEqual(len(illustrations), len(transitions))
        
        # 各挿絵の検証
        for illustration in illustrations:
            self.assertIsInstance(illustration, IllustrationSpec)
            self.assertIsInstance(illustration.illustration_id, str)
            self.assertIsInstance(illustration.transition_id, str)
            self.assertIsInstance(illustration.image_prompt, str)
            self.assertIsInstance(illustration.display_duration, float)
            self.assertIsInstance(illustration.display_position, str)
            self.assertIsInstance(illustration.transition_effect, str)
            self.assertGreater(illustration.display_duration, 0.0)
            self.assertIn(illustration.display_position, ["center", "top", "bottom", "left", "right"])
            self.assertIn(illustration.transition_effect, ["fade", "slide", "zoom", "none"])

    @patch('src.api.image_client.ImageGenerationClient')
    def test_04_integrate_into_video(self, mock_image_client):
        """動画統合テスト"""
        # モック設定
        mock_client = Mock()
        mock_client.generate_image.return_value = {
            "success": True,
            "image_path": "/test/path/illustration.png",
            "metadata": {"size": [1920, 1080]}
        }
        mock_image_client.return_value = mock_client
        
        # テスト用挿絵データ
        test_illustrations = [
            IllustrationSpec(
                illustration_id="ill_001",
                transition_id="trans_001",
                image_prompt="プログラミング変数の概念図",
                image_path="/test/path/illustration.png",
                display_duration=2.0,
                display_position="center",
                transition_effect="fade",
                metadata={"topic": "variables"}
            )
        ]
        
        # 動画統合実行
        integration_result = self.illustration_inserter.integrate_into_video(
            project_id=self.project_id,
            input_video_path=self.enhanced_video_path,
            illustrations=test_illustrations
        )
        
        # 結果検証
        self.assertIsInstance(integration_result, VideoIntegration)
        self.assertIsInstance(integration_result.output_video_path, str)
        self.assertIsInstance(integration_result.processing_duration, float)
        self.assertIsInstance(integration_result.integrated_count, int)
        self.assertEqual(integration_result.integrated_count, len(test_illustrations))
        self.assertTrue(integration_result.success)

    def test_05_insert_illustrations(self):
        """完全処理テスト"""
        # 入力データ準備
        input_data = IllustrationInsertionInput(
            enhanced_video_path=self.enhanced_video_path,
            script_data=self.test_script_data,
            insertion_config={
                "min_transition_strength": 0.5,
                "max_illustrations": 5,
                "default_duration": 2.0,
                "style": "educational"
            }
        )
        
        # 挿絵挿入処理実行
        with patch('src.api.image_client.ImageGenerationClient') as mock_image_client:
            # モック設定
            mock_client = Mock()
            mock_client.generate_image.return_value = {
                "success": True,
                "image_path": "/test/path/illustration.png",
                "metadata": {"size": [1920, 1080]}
            }
            mock_image_client.return_value = mock_client
            
            result = self.illustration_inserter.insert_illustrations(
                project_id=self.project_id,
                input_data=input_data
            )
        
        # 結果検証
        self.assertIsInstance(result, IllustrationInsertionOutput)
        self.assertIsInstance(result.final_video_path, str)
        self.assertIsInstance(result.illustrations, list)
        self.assertIsInstance(result.topic_transitions, list)
        self.assertIsInstance(result.video_integration, VideoIntegration)
        self.assertIsInstance(result.processing_duration, float)
        
        # 処理結果の詳細検証
        self.assertGreater(len(result.illustrations), 0)
        self.assertGreater(len(result.topic_transitions), 0)
        self.assertTrue(result.video_integration.success)
        self.assertGreater(result.processing_duration, 0.0)

    def tearDown(self):
        """テスト環境クリーンアップ"""
        import shutil
        
        # データベース接続を確実に閉じる
        if hasattr(self, 'database_manager'):
            self.database_manager.close_connection()
        
        if hasattr(self, 'illustration_inserter') and hasattr(self.illustration_inserter, 'dao'):
            if hasattr(self.illustration_inserter.dao, 'database_manager'):
                self.illustration_inserter.dao.database_manager.close_connection()
        
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


class TestIllustrationInsertionIntegration(unittest.TestCase):
    """挿絵挿入統合テスト"""

    def setUp(self):
        """統合テスト環境セットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        # 基盤コンポーネント
        self.database_manager = DatabaseManager(self.db_path)
        self.file_system_manager = FileSystemManager(self.temp_dir)
        self.log_manager = LogManager({
            "log_dir": self.temp_dir,
            "log_level": "DEBUG",
            "json_format": False,
            "console_output": True
        })
        
        # プロジェクト作成
        self.project_id = "integration-test-project"
        self.file_system_manager.create_project_directory(self.project_id)
        
        # 挿絵挿入モジュール
        self.illustration_inserter = IllustrationInserter(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )

    def test_database_integration(self):
        """データベース統合テスト"""
        # テストデータ作成
        test_transitions = [
            TopicTransition(
                transition_id="trans_001",
                from_topic="introduction",
                to_topic="variables",
                transition_time=3.0,
                transition_type="topic_change",
                transition_strength=0.8,
                metadata={"confidence": 0.9}
            )
        ]
        
        # データベース保存テスト
        dao = self.illustration_inserter.dao
        dao.save_topic_transitions(self.project_id, test_transitions)
        
        # データベース取得テスト
        retrieved_transitions = dao.get_topic_transitions(self.project_id)
        
        # 検証
        self.assertEqual(len(retrieved_transitions), 1)
        transition = retrieved_transitions[0]
        self.assertEqual(transition["transition_id"], "trans_001")
        self.assertEqual(transition["from_topic"], "introduction")
        self.assertEqual(transition["to_topic"], "variables")

    def test_file_system_integration(self):
        """ファイルシステム統合テスト"""
        # 挿絵保存ディレクトリ確認
        illustrations_dir = self.file_system_manager.get_project_directory_path(
            self.project_id
        )
        illustrations_path = os.path.join(
            illustrations_dir, "files", "images", "illustrations"
        )
        
        # ディレクトリ作成確認
        os.makedirs(illustrations_path, exist_ok=True)
        self.assertTrue(os.path.exists(illustrations_path))
        
        # テスト用挿絵ファイル作成
        test_image_path = os.path.join(illustrations_path, "test_illustration.png")
        with open(test_image_path, "wb") as f:
            f.write(b"test illustration data")
        
        # ファイル存在確認
        self.assertTrue(os.path.exists(test_image_path))

    def test_processing_pipeline(self):
        """処理パイプライン統合テスト"""
        # テスト用入力データ
        test_script = {
            "theme": "AI技術入門",
            "segments": [
                {"segment_id": 1, "topic": "ai_basics", "text": "AIとは何か"},
                {"segment_id": 2, "topic": "machine_learning", "text": "機械学習について"}
            ]
        }
        
        # パイプライン実行
        transitions = self.illustration_inserter.detect_topic_transitions(
            test_script["segments"]
        )
        
        with patch('src.api.image_client.ImageGenerationClient') as mock_client:
            # モック設定
            mock_client.return_value.generate_image.return_value = {
                "success": True,
                "image_path": "/test/illustration.png",
                "metadata": {"size": [1920, 1080]}
            }
            
            illustrations = self.illustration_inserter.generate_illustrations(
                project_id=self.project_id,
                transitions=transitions,
                theme=test_script["theme"]
            )
        
        # 結果検証
        self.assertGreater(len(transitions), 0)
        self.assertGreater(len(illustrations), 0)
        
        # データベース保存確認
        dao = self.illustration_inserter.dao
        dao.save_topic_transitions(self.project_id, transitions)
        dao.save_illustrations(self.project_id, illustrations)
        
        # 保存データ取得確認
        saved_transitions = dao.get_topic_transitions(self.project_id)
        saved_illustrations = dao.get_illustrations(self.project_id)
        
        self.assertEqual(len(saved_transitions), len(transitions))
        self.assertEqual(len(saved_illustrations), len(illustrations))

    def tearDown(self):
        """統合テスト環境クリーンアップ"""
        import shutil
        
        # データベース接続を確実に閉じる
        if hasattr(self, 'database_manager'):
            self.database_manager.close_connection()
        
        if hasattr(self, 'illustration_inserter') and hasattr(self.illustration_inserter, 'dao'):
            if hasattr(self.illustration_inserter.dao, 'database_manager'):
                self.illustration_inserter.dao.database_manager.close_connection()
        
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