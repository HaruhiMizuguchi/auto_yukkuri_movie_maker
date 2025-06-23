"""
音響効果統合テスト

AudioEnhancerモジュールと他のシステムコンポーネントとの統合テスト。
実際のファイル操作、データベース操作、プロジェクト管理との連携を検証。
"""

import unittest
import tempfile
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Any

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.modules.audio_enhancer import AudioEnhancer
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.log_manager import LogManager
from src.core.project_manager import ProjectManager


class TestAudioEnhancementIntegration(unittest.TestCase):
    """音響効果統合テスト"""
    
    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_id = "test-audio-integration-001"
        self.db_path = os.path.join(self.temp_dir, "test_db.sqlite")
        
        # コンポーネントの初期化
        self.database_manager = DatabaseManager(self.db_path)
        
        # テスト用テーブル作成
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    theme TEXT NOT NULL,
                    target_length_minutes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    config_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    output_summary_json TEXT
                )
            ''')
            conn.commit()
        
        self.file_system_manager = FileSystemManager(self.temp_dir)
        self.log_manager = LogManager({
            "log_dir": self.temp_dir,
            "log_level": "INFO",
            "json_format": True,
            "console_output": False
        })
        
        # プロジェクトマネージャー初期化
        self.project_manager = ProjectManager(
            db_manager=self.database_manager,
            projects_base_dir=self.temp_dir
        )
        
        # AudioEnhancer初期化
        self.audio_enhancer = AudioEnhancer(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )
        
        # テスト用プロジェクト作成
        self.project_config = {
            "theme": "プログラミング入門",
            "characters": ["reimu", "marisa"],
            "duration": 60
        }
        
        self.actual_project_id = self.project_manager.create_project(
            theme=self.project_config["theme"],
            target_length_minutes=self.project_config["duration"],
            config=self.project_config
        )
        
        # テスト用データ準備
        self._prepare_test_data()
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _prepare_test_data(self):
        """テスト用データの準備"""
        # テスト用動画ファイル作成
        video_dir = os.path.join(
            self.temp_dir, self.project_id, "files/video"
        )
        os.makedirs(video_dir, exist_ok=True)
        
        # ダミー動画ファイル
        self.test_video_path = os.path.join(video_dir, "composed_video.mp4")
        with open(self.test_video_path, "wb") as f:
            f.write(b"dummy video content")
        
        # テスト用字幕データ
        self.test_subtitles = [
            {"start": 0.0, "end": 2.0, "text": "こんにちは、プログラミングの世界へようこそ！", "speaker": "reimu"},
            {"start": 2.5, "end": 4.5, "text": "今日は何を学ぶのか？", "speaker": "marisa"},
            {"start": 5.0, "end": 7.0, "text": "Pythonの基礎から始めましょう。", "speaker": "reimu"},
            {"start": 7.5, "end": 9.5, "text": "それは面白そうだね！", "speaker": "marisa"}
        ]
        
        # テスト用音響ライブラリディレクトリ作成
        audio_lib_dir = os.path.join(self.temp_dir, "assets", "audio")
        os.makedirs(os.path.join(audio_lib_dir, "bgm"), exist_ok=True)
        os.makedirs(os.path.join(audio_lib_dir, "sfx"), exist_ok=True)
        
        # ダミー音響ファイル作成
        bgm_files = ["educational_bgm.mp3", "casual_bgm.mp3", "default_bgm.mp3"]
        for bgm_file in bgm_files:
            bgm_path = os.path.join(audio_lib_dir, "bgm", bgm_file)
            with open(bgm_path, "wb") as f:
                f.write(b"dummy bgm content")
        
        sfx_files = ["transition.wav", "emphasis.wav", "intro.wav", "outro.wav"]
        for sfx_file in sfx_files:
            sfx_path = os.path.join(audio_lib_dir, "sfx", sfx_file)
            with open(sfx_path, "wb") as f:
                f.write(b"dummy sfx content")
    
    def test_01_project_integration(self):
        """プロジェクト管理統合テスト"""
        # プロジェクト情報取得
        project_info = self.project_manager.get_project(self.actual_project_id)
        self.assertIsNotNone(project_info)
        
        # 音響効果処理の入力データ準備
        input_data = {
            "video_path": self.test_video_path,
            "subtitles": self.test_subtitles,
            "theme": project_info["theme"],
            "mood": "educational"
        }
        
        # 音響効果処理実行
        result = self.audio_enhancer.enhance_audio(
            project_id=self.actual_project_id,
            input_data=input_data
        )
        
        # 結果検証
        self.assertIsInstance(result, dict)
        self.assertIn("enhanced_video_path", result)
        self.assertIn("sound_effects", result)
        self.assertIn("background_music", result)
        self.assertIn("audio_levels", result)
        
        # データベースに保存されたことを確認
        dao = self.audio_enhancer.dao
        enhancement_record = dao.get_enhancement_result(self.actual_project_id)
        self.assertIsNotNone(enhancement_record)
        self.assertEqual(enhancement_record["project_id"], self.actual_project_id)
    
    def test_02_file_system_integration(self):
        """ファイルシステム統合テスト"""
        # 入力データ準備
        input_data = {
            "video_path": self.test_video_path,
            "subtitles": self.test_subtitles,
            "theme": "プログラミング",
            "mood": "educational"
        }
        
        # 音響効果処理実行
        result = self.audio_enhancer.enhance_audio(
            project_id=self.actual_project_id,
            input_data=input_data
        )
        
        # 出力ファイルの存在確認
        enhanced_video_path = result["enhanced_video_path"]
        self.assertTrue(os.path.exists(enhanced_video_path))
        
        # ファイルがプロジェクトディレクトリ内に作成されていることを確認
        project_path = self.file_system_manager.get_project_directory_path(self.actual_project_id)
        self.assertTrue(enhanced_video_path.startswith(str(project_path)))
        
        # ファイルシステムマネージャーでファイル一覧取得
        file_list = self.file_system_manager.get_project_file_list(self.actual_project_id)
        audio_files = [f for f in file_list if "audio" in f["relative_path"]]
        self.assertGreater(len(audio_files), 0)
    
    def test_03_database_integration(self):
        """データベース統合テスト"""
        # 入力データ準備
        input_data = {
            "video_path": self.test_video_path,
            "subtitles": self.test_subtitles,
            "theme": "プログラミング",
            "mood": "educational"
        }
        
        # 音響効果処理実行
        result = self.audio_enhancer.enhance_audio(
            project_id=self.actual_project_id,
            input_data=input_data
        )
        
        # データベースに正しく保存されていることを確認
        dao = self.audio_enhancer.dao
        
        # メイン記録の確認
        enhancement_record = dao.get_enhancement_result(self.actual_project_id)
        self.assertIsNotNone(enhancement_record)
        self.assertEqual(enhancement_record["project_id"], self.actual_project_id)
        self.assertEqual(enhancement_record["input_video_path"], self.test_video_path)
        self.assertEqual(enhancement_record["enhanced_video_path"], result["enhanced_video_path"])
        
        # 効果音記録の確認
        sound_effects = dao.get_sound_effects_by_project(self.actual_project_id)
        self.assertIsInstance(sound_effects, list)
        self.assertGreater(len(sound_effects), 0)
        
        # BGM記録の確認（enhancement_recordから取得）
        bgm_record = enhancement_record.get("background_music")
        self.assertIsNotNone(bgm_record)
        
        # 音響レベル記録の確認
        audio_levels = dao.get_audio_levels_by_project(self.actual_project_id)
        self.assertIsInstance(audio_levels, dict)
        self.assertGreater(len(audio_levels), 0)
        
        # データの一貫性確認
        for effect in sound_effects:
            self.assertIn("timestamp", effect)
            self.assertIn("effect_type", effect)
            self.assertIn("volume", effect)
        
        for track_type, level in audio_levels.items():
            self.assertIn("adjustment_db", level)
            self.assertIn("final_lufs", level)


if __name__ == "__main__":
    unittest.main() 