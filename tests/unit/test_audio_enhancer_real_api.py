"""
音響効果モジュールの実API統合テスト

Test Classes:
    TestAudioEnhancer: 音響効果モジュールの基本機能テスト
    TestAudioEnhancerRealAudio: 実際の音声ファイル処理テスト
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import logging

# プロジェクトルートをPythonパスに追加
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.modules.audio_enhancer import AudioEnhancer
from src.dao.audio_enhancement_dao import AudioEnhancementDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.log_manager import LogManager


class TestAudioEnhancer(unittest.TestCase):
    """音響効果モジュールの基本機能テスト"""
    
    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_id = "test-audio-enhancement-001"
        self.db_path = os.path.join(self.temp_dir, "test_db.sqlite")
        
        # コンポーネントの初期化
        self.database_manager = DatabaseManager(self.db_path)
        
        # テスト用テーブル作成
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT UNIQUE NOT NULL,
                    config TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        
        # テスト用プロジェクト作成
        self.file_system_manager.create_project_directory(self.project_id)
        
        # AudioEnhancer初期化
        self.audio_enhancer = AudioEnhancer(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )
        
        # テスト用の音声ファイルパス（実際には存在しない）
        self.test_video_path = os.path.join(
            self.temp_dir, self.project_id, "files/video/composed_video.mp4"
        )
        
        # テスト用字幕データ
        self.test_subtitles = [
            {"start": 0.0, "end": 2.0, "text": "こんにちは", "speaker": "reimu"},
            {"start": 2.5, "end": 4.5, "text": "こんにちは", "speaker": "marisa"},
            {"start": 5.0, "end": 7.0, "text": "今日は良い天気ですね", "speaker": "reimu"}
        ]
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_01_initialization(self):
        """初期化テスト"""
        # AudioEnhancerの初期化確認
        self.assertIsInstance(self.audio_enhancer, AudioEnhancer)
        self.assertEqual(self.audio_enhancer.database_manager, self.database_manager)
        self.assertEqual(self.audio_enhancer.file_system_manager, self.file_system_manager)
        self.assertEqual(self.audio_enhancer.log_manager, self.log_manager)
    
    def test_02_detect_sound_effect_timing(self):
        """効果音タイミング検出テスト"""
        # 字幕データから効果音タイミングを検出
        sound_effect_timings = self.audio_enhancer.detect_sound_effect_timing(
            self.test_subtitles
        )
        
        # 結果検証
        self.assertIsInstance(sound_effect_timings, list)
        self.assertGreater(len(sound_effect_timings), 0)
        
        for timing in sound_effect_timings:
            self.assertIn("timestamp", timing)
            self.assertIn("effect_type", timing)
            self.assertIn("volume", timing)
            self.assertIsInstance(timing["timestamp"], (int, float))
            self.assertIsInstance(timing["effect_type"], str)
            self.assertIsInstance(timing["volume"], (int, float))
    
    def test_03_select_background_music(self):
        """BGM選択テスト"""
        # テーマとムードからBGMを選択
        theme = "プログラミング"
        mood = "casual"
        
        selected_bgm = self.audio_enhancer.select_background_music(theme, mood)
        
        # 結果検証
        self.assertIsInstance(selected_bgm, dict)
        self.assertIn("file_path", selected_bgm)
        self.assertIn("genre", selected_bgm)
        self.assertIn("volume", selected_bgm)
        self.assertIn("fade_in", selected_bgm)
        self.assertIn("fade_out", selected_bgm)
    
    def test_04_normalize_audio_levels(self):
        """音量正規化テスト"""
        # テスト用の音声レベルデータ
        audio_levels = {
            "voice": {"current_lufs": -20.0, "target_lufs": -23.0},
            "bgm": {"current_lufs": -18.0, "target_lufs": -30.0},
            "sfx": {"current_lufs": -15.0, "target_lufs": -20.0}
        }
        
        normalized_levels = self.audio_enhancer.normalize_audio_levels(audio_levels)
        
        # 結果検証
        self.assertIsInstance(normalized_levels, dict)
        for track, data in normalized_levels.items():
            self.assertIn("adjustment_db", data)
            self.assertIn("final_lufs", data)
            self.assertIsInstance(data["adjustment_db"], (int, float))
    
    def test_05_enhance_audio_complete(self):
        """音響効果完全処理テスト"""
        # 入力データ準備
        input_data = {
            "video_path": self.test_video_path,
            "subtitles": self.test_subtitles,
            "theme": "プログラミング",
            "mood": "casual"
        }
        
        # 音響効果処理実行
        result = self.audio_enhancer.enhance_audio(
            project_id=self.project_id,
            input_data=input_data
        )
        
        # 結果検証
        self.assertIsInstance(result, dict)
        self.assertIn("enhanced_video_path", result)
        self.assertIn("sound_effects", result)
        self.assertIn("background_music", result)
        self.assertIn("audio_levels", result)
        self.assertIn("processing_duration", result)
        
        # ファイル存在確認（実際のファイル処理は後のテストで）
        self.assertIsInstance(result["enhanced_video_path"], str)
        self.assertIsInstance(result["sound_effects"], list)
        self.assertIsInstance(result["background_music"], dict)
        self.assertIsInstance(result["audio_levels"], dict)


class TestAudioEnhancerRealAudio(unittest.TestCase):
    """実際の音声ファイル処理テスト"""
    
    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_id = "test-audio-real-001"
        self.db_path = os.path.join(self.temp_dir, "test_db.sqlite")
        
        # コンポーネントの初期化
        self.database_manager = DatabaseManager(self.db_path)
        
        # テスト用テーブル作成
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT UNIQUE NOT NULL,
                    config TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        
        # テスト用プロジェクト作成
        self.file_system_manager.create_project_directory(self.project_id)
        
        # AudioEnhancer初期化
        self.audio_enhancer = AudioEnhancer(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )
        
        # テスト用のダミー音声ファイル作成
        self._create_test_audio_files()
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_audio_files(self):
        """テスト用の音声ファイル作成"""
        try:
            import pydub
            from pydub.generators import Sine
            
            # 無音の音声ファイル作成（3秒）
            silence = pydub.AudioSegment.silent(duration=3000)  # 3秒
            
            # テスト用動画ファイル（音声のみ）
            video_dir = os.path.join(self.temp_dir, self.project_id, "files/video")
            os.makedirs(video_dir, exist_ok=True)
            
            test_video_path = os.path.join(video_dir, "composed_video.wav")
            silence.export(test_video_path, format="wav")
            self.test_video_path = test_video_path
            
            # テスト用BGMファイル
            audio_dir = os.path.join(self.temp_dir, "assets/audio/bgm")
            os.makedirs(audio_dir, exist_ok=True)
            
            # 440Hz正弦波（2秒）
            bgm_tone = Sine(440).to_audio_segment(duration=2000)
            self.test_bgm_path = os.path.join(audio_dir, "test_bgm.wav")
            bgm_tone.export(self.test_bgm_path, format="wav")
            
            # テスト用効果音ファイル
            sfx_dir = os.path.join(self.temp_dir, "assets/audio/sfx")
            os.makedirs(sfx_dir, exist_ok=True)
            
            # 880Hz正弦波（500ms）
            sfx_tone = Sine(880).to_audio_segment(duration=500)
            self.test_sfx_path = os.path.join(sfx_dir, "test_sfx.wav")
            sfx_tone.export(self.test_sfx_path, format="wav")
            
        except ImportError:
            # pydubが利用できない場合はテストをスキップ
            self.skipTest("pydub is not available for audio file creation")
    
    @unittest.skipUnless(
        os.environ.get("RUN_REAL_AUDIO_TESTS", "false").lower() == "true",
        "実際の音声処理テストはRUN_REAL_AUDIO_TESTS=trueでのみ実行"
    )
    def test_01_real_audio_mixing(self):
        """実際の音声ミキシングテスト"""
        # テスト用字幕データ
        subtitles = [
            {"start": 0.0, "end": 1.0, "text": "テスト", "speaker": "reimu"},
            {"start": 1.5, "end": 2.5, "text": "音響効果", "speaker": "marisa"}
        ]
        
        # 入力データ準備
        input_data = {
            "video_path": self.test_video_path,
            "subtitles": subtitles,
            "theme": "テスト",
            "mood": "neutral"
        }
        
        # 音響効果処理実行
        result = self.audio_enhancer.enhance_audio(
            project_id=self.project_id,
            input_data=input_data
        )
        
        # 結果検証
        self.assertIsInstance(result, dict)
        self.assertIn("enhanced_video_path", result)
        
        # 出力ファイル存在確認
        output_path = result["enhanced_video_path"]
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)
    
    @unittest.skipUnless(
        os.environ.get("RUN_REAL_AUDIO_TESTS", "false").lower() == "true",
        "実際の音声処理テストはRUN_REAL_AUDIO_TESTS=trueでのみ実行"
    )
    def test_02_audio_level_analysis(self):
        """音声レベル分析テスト"""
        # 音声レベル分析実行
        levels = self.audio_enhancer.analyze_audio_levels(self.test_video_path)
        
        # 結果検証
        self.assertIsInstance(levels, dict)
        self.assertIn("peak_db", levels)
        self.assertIn("rms_db", levels)
        self.assertIn("lufs", levels)
        
        # 数値検証
        self.assertIsInstance(levels["peak_db"], (int, float))
        self.assertIsInstance(levels["rms_db"], (int, float))
        self.assertIsInstance(levels["lufs"], (int, float))
    
    def test_03_database_integration(self):
        """データベース統合テスト"""
        # テスト用処理結果
        enhancement_result = {
            "project_id": self.project_id,
            "input_video_path": self.test_video_path,
            "enhanced_video_path": "test_output.mp4",
            "sound_effects": [
                {"timestamp": 1.0, "effect_type": "transition", "volume": 0.7}
            ],
            "background_music": {
                "file_path": "test_bgm.mp3",
                "volume": 0.3,
                "fade_in": 2.0,
                "fade_out": 2.0
            },
            "audio_levels": {
                "voice": {"lufs": -23.0},
                "bgm": {"lufs": -30.0},
                "sfx": {"lufs": -20.0}
            }
        }
        
        # データベース保存
        dao = AudioEnhancementDAO(self.database_manager, self.file_system_manager)
        dao.save_enhancement_result(enhancement_result)
        
        # データベースから取得
        retrieved_result = dao.get_enhancement_result(self.project_id)
        
        # 結果検証
        self.assertIsNotNone(retrieved_result)
        self.assertEqual(retrieved_result["project_id"], self.project_id)
        self.assertIn("sound_effects", retrieved_result)
        self.assertIn("background_music", retrieved_result)
        self.assertIn("audio_levels", retrieved_result)


if __name__ == '__main__':
    # ログレベル設定
    logging.basicConfig(level=logging.INFO)
    
    # テスト実行
    unittest.main(verbosity=2) 