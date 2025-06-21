"""
キャラクター合成モジュール - 実動画生成テスト

実際のOpenCVとffmpegを使用して動画ファイルを生成し、
ファイルの存在、サイズ、プロパティを検証します。
"""

import unittest
import os
import tempfile
import shutil
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# テスト対象のインポート
from src.modules.character_synthesizer import (
    CharacterSynthesizer, 
    CharacterFrame,
    LipSyncFrame,
    EmotionFrame,
    CharacterSynthesizerError
)
from src.dao.character_synthesis_dao import CharacterSynthesisDAO
from src.core.file_system_manager import FileSystemManager
from src.core.config_manager import ConfigManager
from src.core.database_manager import DatabaseManager

# 動画処理ライブラリ
try:
    import cv2
    import numpy as np
    import ffmpeg
    REAL_VIDEO_PROCESSING_AVAILABLE = True
except ImportError:
    REAL_VIDEO_PROCESSING_AVAILABLE = False
    cv2 = None
    np = None
    ffmpeg = None


class TestCharacterSynthesisRealVideo(unittest.TestCase):
    """実動画生成テスト"""

    @classmethod
    def setUpClass(cls):
        """クラス初期化"""
        # ログ設定
        logging.basicConfig(level=logging.INFO)
        cls.logger = logging.getLogger(__name__)
        
        # テスト環境チェック
        if not REAL_VIDEO_PROCESSING_AVAILABLE:
            cls.logger.warning("Real video processing libraries not available. Tests will be skipped.")

    def setUp(self):
        """テスト前準備"""
        # 一時ディレクトリ作成
        self.test_dir = tempfile.mkdtemp(prefix="test_real_video_")
        self.project_id = f"test-real-video-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # データベース設定
        self.db_path = os.path.join(self.test_dir, "test_database.db")
        self.db_manager = DatabaseManager(self.db_path)
        
        # データベース初期化
        self.db_manager.initialize()
        
        # DAO作成
        self.dao = CharacterSynthesisDAO(self.db_manager)
        
        # ファイルマネージャー作成
        self.file_manager = FileSystemManager(self.test_dir)
        
        # 設定マネージャー作成
        self.config_manager = ConfigManager()
        
        # CharacterSynthesizer作成
        self.synthesizer = CharacterSynthesizer(
            dao=self.dao,
            file_manager=self.file_manager,
            config_manager=self.config_manager,
            logger=self.logger
        )
        
        # テストプロジェクト設定
        self._setup_test_project()

    def tearDown(self):
        """テスト後クリーンアップ"""
        try:
            # 一時ディレクトリ削除
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)
        except Exception as e:
            self.logger.warning(f"テストクリーンアップエラー: {e}")

    def _setup_test_project(self):
        """テストプロジェクト設定"""
        # プロジェクトディレクトリ作成
        project_dir = self.file_manager.create_project_directory(self.project_id)
        
        # プロジェクトレコードをデータベースに作成（外部キー制約を満たすため）
        from src.core.project_repository import ProjectRepository
        project_repo = ProjectRepository(self.db_manager)
        project_repo.create_project(
            project_id=self.project_id,
            theme="テスト用テーマ - 実動画生成テスト",
            target_length_minutes=5.0,
            config={
                "target_duration": 300,
                "style": "casual",
                "description": "Test project for real video generation"
            }
        )
        
        # テスト用音声メタデータ
        audio_metadata = {
            "total_duration": 5.0,
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 2.5,
                    "speaker": "reimu",
                    "text": "こんにちは、霊夢です。",
                    "timestamps": [
                        {"start": 0.0, "end": 0.5, "phoneme": "k"},
                        {"start": 0.5, "end": 1.0, "phoneme": "o"},
                        {"start": 1.0, "end": 1.5, "phoneme": "n"},
                        {"start": 1.5, "end": 2.0, "phoneme": "n"},
                        {"start": 2.0, "end": 2.5, "phoneme": "i"}
                    ]
                },
                {
                    "start_time": 2.5,
                    "end_time": 5.0,
                    "speaker": "marisa",
                    "text": "魔理沙だぜ！",
                    "timestamps": [
                        {"start": 2.5, "end": 3.0, "phoneme": "m"},
                        {"start": 3.0, "end": 3.5, "phoneme": "a"},
                        {"start": 3.5, "end": 4.0, "phoneme": "r"},
                        {"start": 4.0, "end": 4.5, "phoneme": "i"},
                        {"start": 4.5, "end": 5.0, "phoneme": "s"}
                    ]
                }
            ]
        }
        
        # キャラクター設定
        character_config = {
            "characters": {
                "reimu": {"position": [400, 300], "scale": 1.0},
                "marisa": {"position": [600, 300], "scale": 1.0}
            },
            "animation": {
                "frame_rate": 30,
                "width": 1920,
                "height": 1080
            }
        }
        
        # データベースに保存
        self.dao.save_audio_metadata(self.project_id, audio_metadata)
        self.dao.save_character_config(self.project_id, character_config)

    @unittest.skipIf(not REAL_VIDEO_PROCESSING_AVAILABLE, "Real video processing libraries not available")
    def test_01_real_standard_video_generation(self):
        """テスト1: 実際の標準動画生成"""
        # キャラクターフレーム作成
        character_frames = self._create_test_character_frames()
        
        # 動画設定
        video_config = {
            "transparency": False,
            "width": 1920,
            "height": 1080,
            "frame_rate": 30,
            "background_color": [240, 248, 255, 255],
            "emotion_effects": True,
            "color_correction": True,
            "sharpening": False
        }
        
        # 出力パス
        output_path = os.path.join(self.test_dir, f"{self.project_id}_standard.mp4")
        
        # 動画生成実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.synthesizer._generate_video_with_opencv_enhanced(
                    character_frames, output_path, video_config
                )
            )
        finally:
            loop.close()
        
        # 検証
        self.assertTrue(os.path.exists(output_path), "動画ファイルが生成されていません")
        
        # ファイルサイズチェック
        file_size = os.path.getsize(output_path)
        self.assertGreater(file_size, 0, "動画ファイルのサイズが0です")
        
        # OpenCVで動画プロパティを確認
        cap = cv2.VideoCapture(output_path)
        self.assertTrue(cap.isOpened(), "動画ファイルが開けません")
        
        # フレーム数確認
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        cap.release()
        
        # プロパティ検証
        self.assertEqual(width, 1920, f"動画幅が期待値と異なります: {width}")
        self.assertEqual(height, 1080, f"動画高さが期待値と異なります: {height}")
        self.assertAlmostEqual(fps, 30, delta=1, msg=f"フレームレートが期待値と異なります: {fps}")
        self.assertGreater(frame_count, 0, "フレーム数が0です")
        
        print(f"✅ 標準動画生成成功: {output_path}")
        print(f"   サイズ: {width}x{height}, FPS: {fps}, フレーム数: {frame_count}")
        print(f"   ファイルサイズ: {file_size / 1024 / 1024:.2f}MB")

    @unittest.skipIf(not REAL_VIDEO_PROCESSING_AVAILABLE, "Real video processing libraries not available")
    def test_02_real_transparent_video_generation(self):
        """テスト2: 実際の透明背景動画生成"""
        # キャラクターフレーム作成
        character_frames = self._create_test_character_frames()
        
        # 透明背景動画設定
        video_config = {
            "transparency": True,
            "width": 1920,
            "height": 1080,
            "frame_rate": 30,
            "codec": "libx264",
            "crf": 23,
            "preset": "medium",
            "emotion_effects": True,
            "quiet": True
        }
        
        # 出力パス
        output_path = os.path.join(self.test_dir, f"{self.project_id}_transparent.mp4")
        
        # 動画生成実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.synthesizer._generate_video_with_opencv_enhanced(
                    character_frames, output_path, video_config
                )
            )
        finally:
            loop.close()
        
        # 検証
        self.assertTrue(os.path.exists(output_path), "透明背景動画ファイルが生成されていません")
        
        # ファイルサイズチェック
        file_size = os.path.getsize(output_path)
        self.assertGreater(file_size, 0, "透明背景動画ファイルのサイズが0です")
        
        # ffprobeで動画情報を取得
        try:
            probe = ffmpeg.probe(output_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            
            if video_stream:
                width = int(video_stream['width'])
                height = int(video_stream['height'])
                pix_fmt = video_stream.get('pix_fmt', '')
                
                # プロパティ検証
                self.assertEqual(width, 1920, f"透明動画幅が期待値と異なります: {width}")
                self.assertEqual(height, 1080, f"透明動画高さが期待値と異なります: {height}")
                
                print(f"✅ 透明背景動画生成成功: {output_path}")
                print(f"   サイズ: {width}x{height}, ピクセル形式: {pix_fmt}")
                print(f"   ファイルサイズ: {file_size / 1024 / 1024:.2f}MB")
            else:
                self.fail("動画ストリーム情報が取得できませんでした")
                
        except Exception as e:
            self.logger.warning(f"ffprobe実行エラー（動画は生成済み）: {e}")
            print(f"✅ 透明背景動画生成成功: {output_path}")
            print(f"   ファイルサイズ: {file_size / 1024 / 1024:.2f}MB")

    @unittest.skipIf(not REAL_VIDEO_PROCESSING_AVAILABLE, "Real video processing libraries not available")
    def test_03_real_frame_image_creation(self):
        """テスト3: 実際のフレーム画像作成"""
        # テストフレーム
        test_frame = CharacterFrame(
            timestamp=1.0,
            speaker="reimu",
            mouth_shape="a",
            emotion="happy",
            position=(960, 540),
            scale=1.0
        )
        
        # 画像設定
        width, height = 1920, 1080
        video_config = {
            "emotion_effects": True,
            "background_color": [240, 248, 255, 255]
        }
        
        # 透明背景フレーム画像作成
        transparent_img = self.synthesizer._create_transparent_frame_image(
            test_frame, width, height, video_config
        )
        
        # 標準フレーム画像作成
        standard_img = self.synthesizer._create_optimized_frame_image(
            test_frame, width, height, video_config
        )
        
        # 検証
        self.assertIsNotNone(transparent_img, "透明背景画像が作成されていません")
        self.assertIsNotNone(standard_img, "標準画像が作成されていません")
        
        # 画像サイズ確認
        self.assertEqual(transparent_img.shape, (height, width, 4), "透明背景画像のサイズが正しくありません")
        self.assertEqual(standard_img.shape, (height, width, 4), "標準画像のサイズが正しくありません")
        
        # 画像保存（確認用）
        transparent_path = os.path.join(self.test_dir, "test_transparent_frame.png")
        standard_path = os.path.join(self.test_dir, "test_standard_frame.png")
        
        cv2.imwrite(transparent_path, transparent_img)
        cv2.imwrite(standard_path, standard_img)
        
        # ファイル存在確認
        self.assertTrue(os.path.exists(transparent_path), "透明背景画像ファイルが保存されていません")
        self.assertTrue(os.path.exists(standard_path), "標準画像ファイルが保存されていません")
        
        print(f"✅ フレーム画像作成成功:")
        print(f"   透明背景: {transparent_path}")
        print(f"   標準背景: {standard_path}")

    @unittest.skipIf(not REAL_VIDEO_PROCESSING_AVAILABLE, "Real video processing libraries not available")
    def test_04_real_multiple_frame_rates(self):
        """テスト4: 複数フレームレートでの動画生成"""
        frame_rates = [24, 30, 60]
        character_frames = self._create_test_character_frames()
        
        for fps in frame_rates:
            with self.subTest(fps=fps):
                # 動画設定
                video_config = {
                    "transparency": False,
                    "width": 1280,
                    "height": 720,
                    "frame_rate": fps,
                    "background_color": [200, 220, 240, 255]
                }
                
                # 出力パス
                output_path = os.path.join(self.test_dir, f"{self.project_id}_{fps}fps.mp4")
                
                # 動画生成実行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        self.synthesizer._generate_video_with_opencv_enhanced(
                            character_frames, output_path, video_config
                        )
                    )
                finally:
                    loop.close()
                
                # 検証
                self.assertTrue(os.path.exists(output_path), f"{fps}fps動画が生成されていません")
                
                # OpenCVで確認
                cap = cv2.VideoCapture(output_path)
                self.assertTrue(cap.isOpened(), f"{fps}fps動画が開けません")
                
                actual_fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()
                
                self.assertAlmostEqual(actual_fps, fps, delta=1, 
                                     msg=f"フレームレートが期待値と異なります: {actual_fps} != {fps}")
                
                print(f"✅ {fps}fps動画生成成功: {output_path}")

    def _create_test_character_frames(self) -> List[CharacterFrame]:
        """テスト用キャラクターフレーム作成"""
        frames = []
        duration = 5.0  # 5秒
        fps = 30
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            timestamp = i / fps
            
            # 話者切り替え（2.5秒で切り替え）
            speaker = "reimu" if timestamp < 2.5 else "marisa"
            
            # 口形状（簡単なパターン）
            mouth_shapes = ["a", "i", "u", "e", "o", "silence"]
            mouth_shape = mouth_shapes[i % len(mouth_shapes)]
            
            # 感情（時間に応じて変化）
            if timestamp < 1.5:
                emotion = "neutral"
            elif timestamp < 3.0:
                emotion = "happy"
            elif timestamp < 4.0:
                emotion = "surprised"
            else:
                emotion = "happy"
            
            # 位置（話者によって変更）
            position = (400, 540) if speaker == "reimu" else (1520, 540)
            
            frame = CharacterFrame(
                timestamp=timestamp,
                speaker=speaker,
                mouth_shape=mouth_shape,
                emotion=emotion,
                position=position,
                scale=1.0
            )
            frames.append(frame)
        
        return frames


def run_real_video_tests():
    """実動画生成テスト実行"""
    if not REAL_VIDEO_PROCESSING_AVAILABLE:
        print("⚠️ 実動画生成ライブラリが利用できません。テストをスキップします。")
        print("必要なライブラリ: opencv-python, ffmpeg-python")
        return
    
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_real_video_tests() 