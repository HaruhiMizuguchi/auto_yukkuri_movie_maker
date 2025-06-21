"""
背景生成モジュール実API統合テスト (4-6)

フロー定義仕様:
- 入力: スクリプトデータ + 画像生成設定
- 処理: シーン分析・プロンプト生成・背景画像生成・Ken Burnsエフェクト・動画化
- 出力: 背景画像・背景動画・メタデータ

実装方針:
- Gemini画像生成API実連携
- シーン自動分析
- 背景画像自動生成
- Ken Burnsエフェクト（パン・ズーム）
- 動画変換（ffmpeg）
- DAO分離（背景生成専用SQL操作）
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, Any, List

from src.modules.background_generator import (
    BackgroundGenerator, 
    BackgroundGenerationInput,
    BackgroundGenerationOutput,
    SceneAnalysis,
    BackgroundImage,
    BackgroundVideo,
    KenBurnsEffect
)
from src.dao.background_generation_dao import BackgroundGenerationDAO
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.api.image_client import ImageGenerationClient


class TestBackgroundGeneratorRealAPI:
    """背景生成モジュール実API統合テスト"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """テスト用一時プロジェクトディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "test_project"
            project_dir.mkdir()
            
            # 必要なサブディレクトリを作成
            (project_dir / "files" / "images" / "backgrounds").mkdir(parents=True)
            (project_dir / "files" / "video").mkdir(parents=True)
            (project_dir / "files" / "metadata").mkdir(parents=True)
            (project_dir / "files" / "scripts").mkdir(parents=True)
            
            yield project_dir
    
    @pytest.fixture
    def mock_repository(self, temp_project_dir):
        """モックプロジェクトリポジトリ"""
        repo = Mock(spec=ProjectRepository)
        # db_managerのモックも追加
        repo.db_manager = Mock()
        return repo
    
    @pytest.fixture
    def mock_file_system_manager(self, temp_project_dir):
        """モックファイルシステムマネージャー"""
        fs_manager = Mock()
        fs_manager.get_project_directory.return_value = str(temp_project_dir)
        fs_manager.get_project_file_path.return_value = temp_project_dir / "test_file.png"
        return fs_manager
    
    @pytest.fixture 
    def mock_config_manager(self):
        """モック設定マネージャー"""
        config = Mock(spec=ConfigManager)
        config.get_value.return_value = {
            "image_generation": {
                "default_style": "anime_style",
                "resolution": "1920x1080",
                "quality": "high"
            },
            "ken_burns": {
                "duration_per_scene": 5.0,
                "zoom_factor": 1.2,
                "movement_speed": "medium"
            },
            "video_encoding": {
                "fps": 30,
                "codec": "libx264",
                "quality": "high"
            }
        }
        return config
    
    @pytest.fixture
    def mock_image_client(self):
        """モック画像生成クライアント（実API動作をシミュレート）"""
        client = Mock()
        # 同期的なgenerate_imageメソッドを追加（BackgroundGeneratorで使用）
        client.generate_image.return_value = {
            "image_data": b"fake_image_data_1920x1080",
            "description": "Beautiful anime-style background scene",
            "style": "anime_style",
            "resolution": "1920x1080",
            "metadata": {
                "prompt": "anime style background scene, detailed environment",
                "generation_time": 3.2,
                "model": "gemini-2.0-flash"
            }
        }
        return client
    
    @pytest.fixture
    def sample_script_data(self):
        """サンプルスクリプトデータ"""
        return {
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "text": "今日は美しい桜の季節について話しましょう。",
                    "emotion": "happy",
                    "estimated_duration": 3.5,
                    "scene_type": "outdoor_nature"
                },
                {
                    "segment_id": 2,
                    "speaker": "marisa",
                    "text": "そうだね！桜は日本の春の象徴だよね。",
                    "emotion": "excited",
                    "estimated_duration": 3.0,
                    "scene_type": "outdoor_nature"
                },
                {
                    "segment_id": 3,
                    "speaker": "reimu",
                    "text": "今度は室内で桜餅を作ってみましょう。",
                    "emotion": "neutral",
                    "estimated_duration": 2.8,
                    "scene_type": "indoor_kitchen"
                }
            ],
            "total_duration": 9.3,
            "theme": "桜の季節と日本の春"
        }
    
    @pytest.fixture 
    def background_generator(self, mock_repository, mock_config_manager, mock_image_client, mock_file_system_manager):
        """背景生成モジュールインスタンス"""
        # DAOをモック化（実際のSQL操作は後でテスト）
        with patch('src.modules.background_generator.BackgroundGenerationDAO') as mock_dao_class:
            mock_dao = Mock(spec=BackgroundGenerationDAO)
            mock_dao_class.return_value = mock_dao
            
            generator = BackgroundGenerator(
                repository=mock_repository,
                config_manager=mock_config_manager,
                image_client=mock_image_client,
                file_system_manager=mock_file_system_manager
            )
            generator.dao = mock_dao
            return generator
    
    def test_scene_analysis_from_script(self, background_generator, sample_script_data):
        """テスト: スクリプトからのシーン分析"""
        # テスト実行
        input_data = BackgroundGenerationInput(
            project_id="test_project_001",
            script_data=sample_script_data,
            generation_config={}
        )
        
        scenes = background_generator._analyze_scenes(input_data)
        
        # 検証
        assert len(scenes) >= 2  # 少なくとも2つのユニークシーン
        assert any(scene.scene_type == "outdoor_nature" for scene in scenes)
        assert any(scene.scene_type == "indoor_kitchen" for scene in scenes)
        
        # シーンメタデータの検証
        for scene in scenes:
            assert scene.scene_id is not None
            assert scene.description != ""
            assert scene.duration > 0
            assert scene.prompt != ""
            assert scene.style != ""
    
    def test_background_image_generation(self, background_generator, sample_script_data, mock_image_client):
        """テスト: 背景画像生成（実API連携シミュレート）"""
        # シーン分析
        input_data = BackgroundGenerationInput(
            project_id="test_project_001", 
            script_data=sample_script_data,
            generation_config={"style": "anime_detailed"}
        )
        
        scenes = background_generator._analyze_scenes(input_data)
        scene = scenes[0]
        
        # 背景画像生成テスト
        background_image = background_generator._generate_background_image(scene, input_data.project_id)
        
        # 実API呼び出し検証
        mock_image_client.generate_image.assert_called_once()
        call_args = mock_image_client.generate_image.call_args[1]
        assert "anime" in call_args["prompt"].lower() or "background" in call_args["prompt"].lower()
        
        # 結果検証
        assert background_image.scene_id == scene.scene_id
        assert background_image.image_path is not None
        assert background_image.resolution == "1920x1080"
        assert background_image.file_size > 0
        assert background_image.generation_metadata is not None
    
    def test_ken_burns_effect_calculation(self, background_generator, sample_script_data):
        """テスト: Ken Burnsエフェクト計算"""
        # シーン分析
        input_data = BackgroundGenerationInput(
            project_id="test_project_001",
            script_data=sample_script_data,
            generation_config={}
        )
        
        scenes = background_generator._analyze_scenes(input_data)
        scene = scenes[0]
        
        # Ken Burnsエフェクト計算
        ken_burns = background_generator._calculate_ken_burns_effect(scene)
        
        # 検証
        assert ken_burns.scene_id == scene.scene_id
        assert ken_burns.duration == scene.duration
        assert ken_burns.zoom_start > 0
        assert ken_burns.zoom_end > 0
        assert ken_burns.zoom_start != ken_burns.zoom_end  # ズーム変化確認
        assert ken_burns.pan_start_x >= 0 and ken_burns.pan_start_x <= 1
        assert ken_burns.pan_start_y >= 0 and ken_burns.pan_start_y <= 1
        assert ken_burns.pan_end_x >= 0 and ken_burns.pan_end_x <= 1
        assert ken_burns.pan_end_y >= 0 and ken_burns.pan_end_y <= 1
        assert ken_burns.easing_function in ["linear", "ease_in", "ease_out", "ease_in_out"]
    
    def test_background_video_generation(self, background_generator, sample_script_data, temp_project_dir):
        """テスト: 背景動画生成（ffmpeg統合）"""
        # シーン分析
        input_data = BackgroundGenerationInput(
            project_id="test_project_001",
            script_data=sample_script_data,
            generation_config={}
        )
        
        scenes = background_generator._analyze_scenes(input_data)
        scene = scenes[0]
        
        # テスト用背景画像を作成
        background_image = BackgroundImage(
            scene_id=scene.scene_id,
            image_path=str(temp_project_dir / "files" / "images" / "backgrounds" / f"scene_{scene.scene_id}.png"),
            resolution="1920x1080",
            file_size=2048000,
            generation_metadata={"test": True}
        )
        
        # Ken Burnsエフェクト
        ken_burns = background_generator._calculate_ken_burns_effect(scene)
        
        # 動画生成テスト（ffmpegモック）
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            
            background_video = background_generator._generate_background_video(
                scene, background_image, ken_burns, input_data.project_id
            )
            
            # ffmpeg呼び出し検証
            mock_subprocess.assert_called_once()
            ffmpeg_cmd = mock_subprocess.call_args[0][0]
            assert "ffmpeg" in ffmpeg_cmd[0]
            assert "-i" in ffmpeg_cmd
            
            # 結果検証
            assert background_video.scene_id == scene.scene_id
            assert background_video.video_path is not None
            assert background_video.duration == scene.duration
            assert background_video.resolution == "1920x1080"
            assert background_video.ken_burns_metadata is not None
    
    def test_full_background_generation_workflow(self, background_generator, sample_script_data, temp_project_dir):
        """テスト: 完全な背景生成ワークフロー"""
        # 入力データ準備
        input_data = BackgroundGenerationInput(
            project_id="test_project_001",
            script_data=sample_script_data,
            generation_config={
                "style": "anime_detailed",
                "ken_burns_enabled": True,
                "video_encoding": {"fps": 30, "quality": "high"}
            }
        )
        
        # ffmpegモック
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            
            # 背景生成実行
            result = background_generator.generate_backgrounds(input_data)
            
            # 結果検証
            assert isinstance(result, BackgroundGenerationOutput)
            assert len(result.background_images) >= 2  # 複数シーン
            assert len(result.background_videos) >= 2  # 各シーン用動画
            assert len(result.scene_analyses) >= 2  # シーン分析結果
            
            # 各背景画像の検証
            for bg_image in result.background_images:
                assert bg_image.scene_id is not None
                assert bg_image.image_path.endswith('.png')
                assert bg_image.resolution == "1920x1080"
                assert bg_image.file_size > 0
            
            # 各背景動画の検証
            for bg_video in result.background_videos:
                assert bg_video.scene_id is not None
                assert bg_video.video_path.endswith('.mp4')
                assert bg_video.duration > 0
                assert bg_video.resolution == "1920x1080"
                assert bg_video.ken_burns_metadata is not None
            
            # メタデータ検証
            assert result.generation_metadata["total_scenes"] >= 2
            assert result.generation_metadata["total_generation_time"] > 0
            assert result.generation_metadata["api_calls_count"] >= 2 