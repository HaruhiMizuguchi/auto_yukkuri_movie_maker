"""
動画エンコーダー実API統合テスト

このテストは実際のffmpegとファイルシステムを使用した統合テストです。
"""

import os
import tempfile
import pytest
from pathlib import Path
from typing import Dict, Any

from src.modules.video_encoder import VideoEncoder
from src.dao.video_encoding_dao import VideoEncodingDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.log_manager import LogManager


class TestVideoEncoderRealAPI:
    """VideoEncoder実API統合テストクラス"""
    
    @pytest.fixture
    def setup_dependencies(self):
        """テスト用依存関係セットアップ"""
        # 一時ディレクトリ作成
        temp_dir = tempfile.mkdtemp()
        
        # LogManager初期化（設定辞書を渡す）
        log_manager = LogManager({
            "log_dir": temp_dir,
            "log_level": "INFO",
            "json_format": True,
            "console_output": False
        })
        
        # FileSystemManager初期化
        file_system_manager = FileSystemManager(base_directory=temp_dir)
        
        # DatabaseManager初期化
        db_path = os.path.join(temp_dir, "test.db")
        database_manager = DatabaseManager(db_path)
        
        # テスト用テーブル作成
        with database_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT UNIQUE NOT NULL,
                    config TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # workflow_steps テーブル作成
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            
            # file_references テーブル作成
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            ''')
            
            # video encoding 関連テーブル作成
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
            
            conn.commit()
        
        # VideoEncoder初期化
        video_encoder = VideoEncoder(
            database_manager=database_manager,
            file_system_manager=file_system_manager,
            log_manager=log_manager
        )
        
        return {
            "video_encoder": video_encoder,
            "temp_dir": temp_dir,
            "database_manager": database_manager,
            "file_system_manager": file_system_manager
        }
    
    def test_encoding_settings_application(self, setup_dependencies):
        """エンコード設定適用テスト"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        
        # テスト用設定
        encoding_settings = {
            "preset": "medium",
            "crf": 23,
            "resolution": "1920x1080",
            "fps": 30,
            "bitrate": "2M",
            "codec": "libx264"
        }
        
        # エンコード設定適用
        applied_settings = video_encoder.apply_encoding_settings(encoding_settings)
        
        # 検証
        assert applied_settings is not None
        assert applied_settings["preset"] == "medium"
        assert applied_settings["crf"] == 23
        assert applied_settings["resolution"] == "1920x1080"
        assert applied_settings["fps"] == 30
        assert "ffmpeg_args" in applied_settings
        
    def test_video_quality_check(self, setup_dependencies):
        """動画品質チェックテスト（模擬ファイル使用）"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        temp_dir = deps["temp_dir"]
        
        # テスト用動画ファイル作成（模擬）
        test_video_path = os.path.join(temp_dir, "test_video.mp4")
        self._create_mock_video_file(test_video_path)
        
        # 品質チェック実行
        quality_result = video_encoder.check_video_quality(test_video_path)
        
        # 検証
        assert quality_result is not None
        assert "video_info" in quality_result
        assert "quality_score" in quality_result
        assert "issues" in quality_result
        assert quality_result["quality_score"] >= 0.0
        assert quality_result["quality_score"] <= 1.0
        
    def test_video_optimization(self, setup_dependencies):
        """動画最適化テスト"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        temp_dir = deps["temp_dir"]
        
        # テスト用入力・出力パス
        input_video_path = os.path.join(temp_dir, "input_video.mp4")
        output_video_path = os.path.join(temp_dir, "optimized_video.mp4")
        
        # テスト用動画ファイル作成
        self._create_mock_video_file(input_video_path)
        
        # 最適化設定
        optimization_config = {
            "file_size_target": "10MB",
            "quality_priority": "balanced",
            "compatibility_mode": "web"
        }
        
        # 動画最適化実行
        optimization_result = video_encoder.optimize_video(
            input_path=input_video_path,
            output_path=output_video_path,
            config=optimization_config
        )
        
        # 検証
        assert optimization_result is not None
        assert "optimized_path" in optimization_result
        assert "optimization_stats" in optimization_result
        assert os.path.exists(optimization_result["optimized_path"])
        
    def test_preset_application(self, setup_dependencies):
        """プリセット適用テスト"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        
        # 複数のプリセットテスト
        presets = ["web_optimized", "high_quality", "small_file", "streaming"]
        
        for preset_name in presets:
            preset_config = video_encoder.get_encoding_preset(preset_name)
            
            # 検証
            assert preset_config is not None
            assert "preset" in preset_config
            assert "crf" in preset_config
            assert "resolution" in preset_config
            assert "target_bitrate" in preset_config
            
    def test_encode_with_quality_validation(self, setup_dependencies):
        """品質検証付きエンコードテスト"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        temp_dir = deps["temp_dir"]
        
        # テスト用入力・出力パス
        input_video_path = os.path.join(temp_dir, "input_video.mp4")
        output_video_path = os.path.join(temp_dir, "encoded_video.mp4")
        
        # テスト用動画ファイル作成
        self._create_mock_video_file(input_video_path)
        
        # エンコード設定
        encoding_config = {
            "preset": "medium",
            "quality_threshold": 0.8,
            "max_retries": 2
        }
        
        # 品質検証付きエンコード実行
        encoding_result = video_encoder.encode_with_validation(
            input_path=input_video_path,
            output_path=output_video_path,
            config=encoding_config
        )
        
        # 検証
        assert encoding_result is not None
        assert "success" in encoding_result
        assert "output_path" in encoding_result
        assert "quality_score" in encoding_result
        assert encoding_result["success"] is True
        assert os.path.exists(encoding_result["output_path"])
        
    def test_database_integration(self, setup_dependencies):
        """データベース統合テスト"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        database_manager = deps["database_manager"]
        temp_dir = deps["temp_dir"]
        
        # プロジェクト作成
        project_id = "test_project_encoding"
        
        # プロジェクトをデータベースに登録
        with database_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO projects (project_id, config)
                VALUES (?, ?)
            ''', (project_id, '{}'))
            
            # workflow_stepsにillustration_insertionステップを完了状態で登録
            cursor.execute('''
                INSERT INTO workflow_steps (project_id, step_name, status)
                VALUES (?, ?, ?)
            ''', (project_id, 'illustration_insertion', 'completed'))
            
            # 入力動画ファイルを模擬的に登録
            test_input_path = os.path.join(temp_dir, "input_video.mp4")
            self._create_mock_video_file(test_input_path)
            
            cursor.execute('''
                INSERT INTO file_references (project_id, file_path, file_type, file_category, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (project_id, test_input_path, 'video', 'output', 'Test input video for encoding'))
            
            conn.commit()
        
        # エンコード処理実行
        input_data = {
            "encoding_settings": {
                "preset": "medium",
                "crf": 23
            }
        }
        
        result = video_encoder.encode_video(project_id, input_data)
        
        # データベース保存確認
        assert result is not None
        assert "encoded_video_path" in result
        assert "encoding_stats" in result
        
    def test_error_handling(self, setup_dependencies):
        """エラーハンドリングテスト"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        
        # 存在しないファイルでのエンコード
        with pytest.raises(FileNotFoundError):
            video_encoder.encode_with_validation(
                input_path="/non/existent/file.mp4",
                output_path="/tmp/output.mp4",
                config={"preset": "medium"}
            )
    
    def test_ffmpeg_integration(self, setup_dependencies):
        """FFmpeg統合テスト"""
        deps = setup_dependencies
        video_encoder = deps["video_encoder"]
        temp_dir = deps["temp_dir"]
        
        # テスト用動画ファイル作成
        input_path = os.path.join(temp_dir, "test_input.mp4")
        output_path = os.path.join(temp_dir, "test_output.mp4")
        
        self._create_mock_video_file(input_path)
        
        # FFmpegコマンド生成テスト
        ffmpeg_cmd = video_encoder.generate_ffmpeg_command(
            input_path=input_path,
            output_path=output_path,
            settings={
                "preset": "fast",
                "crf": 20,
                "resolution": "1280x720"
            }
        )
        
        # 検証
        assert ffmpeg_cmd is not None
        assert isinstance(ffmpeg_cmd, list)
        assert "ffmpeg" in ffmpeg_cmd[0] or "ffmpeg.exe" in ffmpeg_cmd[0]
        assert input_path in ffmpeg_cmd
        assert output_path in ffmpeg_cmd
    
    def _create_mock_video_file(self, file_path: str) -> None:
        """テスト用の模擬動画ファイルを作成"""
        import subprocess
        import shutil
        
        # ffmpegが利用可能かチェック
        if shutil.which("ffmpeg"):
            try:
                # ffmpegで1秒の黒い動画を作成
                cmd = [
                    "ffmpeg", "-f", "lavfi", "-i", "color=black:size=320x240:duration=1",
                    "-c:v", "libx264", "-t", "1", "-pix_fmt", "yuv420p",
                    "-y", file_path
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                assert os.path.exists(file_path)
                return
            except subprocess.CalledProcessError:
                pass
        
        # ffmpegが利用できない場合は、基本的なファイルを作成
        # （品質チェックではフォールバック処理が動作する）
        with open(file_path, 'wb') as f:
            # 最小限の有効なMP4ヘッダーを作成
            f.write(b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41')
            f.write(b'\x00' * 1024)  # 1KB の模擬データ
        
        assert os.path.exists(file_path) 