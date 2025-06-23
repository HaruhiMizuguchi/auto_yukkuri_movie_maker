"""
動画エンコード統合テスト

実際のffmpegとファイルシステムを使用した統合テストです。
"""

import os
import tempfile
import unittest
from pathlib import Path
import time

from src.modules.video_encoder import VideoEncoder
from src.dao.video_encoding_dao import VideoEncodingDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.log_manager import LogManager


class TestVideoEncodingIntegration(unittest.TestCase):
    """動画エンコード統合テストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_id = "test-video-encoding-integration-001"
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_category TEXT NOT NULL,
                    description TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            
            # VideoEncoding関連テーブル作成
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_encoding_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    preset_name TEXT NOT NULL,
                    codec TEXT,
                    crf INTEGER,
                    bitrate TEXT,
                    resolution TEXT,
                    fps INTEGER,
                    custom_args TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_quality_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    video_path TEXT NOT NULL,
                    quality_score REAL NOT NULL,
                    video_info TEXT,
                    detected_issues TEXT,
                    resolution TEXT,
                    duration REAL,
                    file_size INTEGER,
                    bitrate TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_optimizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    input_video_path TEXT NOT NULL,
                    output_video_path TEXT NOT NULL,
                    optimization_config TEXT,
                    before_file_size INTEGER,
                    after_file_size INTEGER,
                    compression_ratio REAL,
                    quality_retained REAL,
                    processing_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_encoding_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    input_video_path TEXT NOT NULL,
                    output_video_path TEXT NOT NULL,
                    encoding_settings TEXT,
                    success BOOLEAN NOT NULL DEFAULT 0,
                    error_message TEXT,
                    processing_time REAL,
                    final_quality_score REAL,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            
            # プロジェクトをprojectsテーブルに登録
            cursor.execute('''
                INSERT INTO projects (project_id, config)
                VALUES (?, ?)
            ''', (self.project_id, '{}'))
            
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
        
        # VideoEncoder初期化
        self.video_encoder = VideoEncoder(
            database_manager=self.database_manager,
            file_system_manager=self.file_system_manager,
            log_manager=self.log_manager
        )
        
        # テスト用動画ファイル作成
        self._create_test_video_files()
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_video_files(self):
        """テスト用動画ファイル作成"""
        # 入力動画ファイルのパス
        input_video_dir = os.path.join(self.temp_dir, self.project_id, "files/video")
        os.makedirs(input_video_dir, exist_ok=True)
        
        self.input_video_path = os.path.join(input_video_dir, "input_video.mp4")
        
        # 簡単なMP4ファイルヘッダーを作成（実際の動画ではないが、ファイル存在テスト用）
        with open(self.input_video_path, 'wb') as f:
            # MP4ファイルの基本ヘッダー
            f.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            # mdatボックス
            f.write(b'\x00\x00\x04\x00mdat')
            # ダミーデータ
            f.write(b'\x00' * 1024)  # 1KB のダミーデータ
        
        # データベースにファイル参照を登録
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workflow_steps (project_id, step_name, status)
                VALUES (?, ?, ?)
            """, (self.project_id, "illustration_insertion", "completed"))
            
            cursor.execute("""
                INSERT INTO file_references 
                (project_id, file_path, file_type, file_category, description)
                VALUES (?, ?, ?, ?, ?)
            """, (
                self.project_id,
                self.input_video_path,
                "video",
                "output",
                "テスト用入力動画"
            ))
            conn.commit()
    
    def test_01_encoding_settings_integration(self):
        """エンコード設定統合テスト"""
        # エンコード設定
        settings = {
            "preset": "fast",
            "crf": 25,
            "resolution": "1280x720",
            "fps": 24
        }
        
        # エンコード設定適用
        applied_settings = self.video_encoder.apply_encoding_settings(settings)
        
        # 結果検証
        self.assertIsInstance(applied_settings, dict)
        self.assertEqual(applied_settings["preset"], "fast")
        self.assertEqual(applied_settings["crf"], 25)
        self.assertIn("ffmpeg_args", applied_settings)
        
        # データベース保存テスト
        setting_id = self.video_encoder.dao.save_encoding_settings(
            self.project_id, applied_settings
        )
        self.assertGreater(setting_id, 0)
    
    def test_02_video_quality_check_integration(self):
        """動画品質チェック統合テスト"""
        # 品質チェック実行
        quality_result = self.video_encoder.check_video_quality(self.input_video_path)
        
        # 結果検証
        self.assertIsInstance(quality_result, dict)
        self.assertIn("video_path", quality_result)
        self.assertIn("video_info", quality_result)
        self.assertIn("quality_score", quality_result)
        self.assertIn("issues", quality_result)
        
        # 品質スコアの範囲チェック
        quality_score = quality_result["quality_score"]
        self.assertGreaterEqual(quality_score, 0.0)
        self.assertLessEqual(quality_score, 1.0)
        
        # データベース保存テスト
        check_id = self.video_encoder.dao.save_quality_check_result(
            self.project_id, quality_result
        )
        self.assertGreater(check_id, 0)
    
    def test_03_video_optimization_integration(self):
        """動画最適化統合テスト"""
        # 出力パス設定
        output_path = os.path.join(
            self.temp_dir, self.project_id, "files/video", "optimized_video.mp4"
        )
        
        # 最適化設定
        config = {
            "quality_priority": "balanced",
            "file_size_target": "5MB",
            "compatibility_mode": "web"
        }
        
        # 動画最適化実行
        optimization_result = self.video_encoder.optimize_video(
            input_path=self.input_video_path,
            output_path=output_path,
            config=config
        )
        
        # 結果検証
        self.assertIsInstance(optimization_result, dict)
        self.assertIn("optimized_path", optimization_result)
        self.assertIn("optimization_stats", optimization_result)
        self.assertTrue(os.path.exists(optimization_result["optimized_path"]))
        
        # 統計情報検証
        stats = optimization_result["optimization_stats"]
        self.assertIn("before_file_size", stats)
        self.assertIn("after_file_size", stats)
        self.assertIn("compression_ratio", stats)
        
        # データベース保存テスト
        opt_id = self.video_encoder.dao.save_optimization_result(
            self.project_id, optimization_result
        )
        self.assertGreater(opt_id, 0)
    
    def test_04_complete_encoding_workflow(self):
        """完全エンコードワークフロー統合テスト"""
        # 入力データ準備
        input_data = {
            "encoding_settings": {
                "preset": "medium",
                "crf": 23,
                "resolution": "1920x1080",
                "fps": 30
            }
        }
        
        start_time = time.time()
        
        # 動画エンコード実行
        result = self.video_encoder.encode_video(self.project_id, input_data)
        
        processing_time = time.time() - start_time
        
        # 結果検証
        self.assertIsInstance(result, dict)
        self.assertIn("encoded_video_path", result)
        self.assertIn("encoding_stats", result)
        
        # ファイル存在確認
        encoded_path = result["encoded_video_path"]
        self.assertTrue(os.path.exists(encoded_path))
        
        # ファイルサイズ確認（空でない）
        file_size = os.path.getsize(encoded_path)
        self.assertGreater(file_size, 0)
        
        # 統計情報確認
        stats = result["encoding_stats"]
        self.assertIn("quality_score", stats)
        self.assertIn("processing_time", stats)
        self.assertIn("success", stats)
        
        # 処理時間が妥当な範囲内（10秒以内）
        self.assertLess(processing_time, 10.0)
        
        print(f"✅ エンコード処理完了: {encoded_path}")
        print(f"📊 処理時間: {processing_time:.2f}秒")
        print(f"📂 ファイルサイズ: {file_size} bytes")
        print(f"⭐ 品質スコア: {stats['quality_score']}")
    
    def test_05_database_consistency(self):
        """データベース整合性テスト"""
        # エンコード実行
        input_data = {"encoding_settings": {"preset": "fast"}}
        result = self.video_encoder.encode_video(self.project_id, input_data)
        
        # データベース内容確認
        encoding_history = self.video_encoder.dao.get_encoding_history(self.project_id)
        self.assertGreater(len(encoding_history), 0)
        
        latest_history = encoding_history[0]
        self.assertEqual(latest_history["input_path"], self.input_video_path)
        self.assertEqual(latest_history["output_path"], result["encoded_video_path"])
        self.assertTrue(latest_history["success"])


if __name__ == '__main__':
    unittest.main() 