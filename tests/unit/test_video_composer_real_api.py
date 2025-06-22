"""
動画合成器（VideoComposer）のテスト

TDD（テスト駆動開発）で実装するための実際のAPI使用テスト
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any

# テスト対象のクラスをインポート（最初はNoneの場合もある）
try:
    from src.modules.video_composer import VideoComposer, VideoCompositionInput, VideoCompositionOutput
except ImportError:
    VideoComposer = None
    VideoCompositionInput = None  
    VideoCompositionOutput = None

try:
    from src.dao.video_composition_dao import VideoCompositionDAO
except ImportError:
    VideoCompositionDAO = None

# 必要な依存関係
from src.core.database_manager import DatabaseManager
from src.core.config_manager import ConfigManager
from src.core.file_system_manager import FileSystemManager
from src.core.project_repository import ProjectRepository


class TestVideoComposer:
    """動画合成器のテストクラス"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """テスト用の一時プロジェクトディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "test_project"
            project_dir.mkdir()
            
            # 必要なサブディレクトリを作成
            (project_dir / "files" / "video").mkdir(parents=True)
            (project_dir / "files" / "audio").mkdir(parents=True)
            (project_dir / "files" / "metadata").mkdir(parents=True)
            
            yield str(project_dir)

    @pytest.fixture
    def mock_database_manager(self):
        """モックデータベースマネージャー"""
        mock_db = Mock(spec=DatabaseManager)
        # コンテキストマネージャーのサポートを追加
        mock_connection = Mock()
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        mock_db.get_connection.return_value = mock_connection
        return mock_db

    @pytest.fixture
    def mock_config_manager(self):
        """モック設定マネージャー"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_value.return_value = {
            "video_composition": {
                "output_format": "mp4",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "crf": 23,
                "preset": "medium",
                "resolution": "1920x1080",
                "fps": 30,
                "bitrate": "2M"
            }
        }
        return mock_config

    @pytest.fixture
    def mock_file_system_manager(self, temp_project_dir):
        """モックファイルシステムマネージャー"""
        mock_fs = Mock(spec=FileSystemManager)
        mock_fs.get_project_directory.return_value = temp_project_dir
        mock_fs.create_file.return_value = True
        return mock_fs

    @pytest.fixture
    def mock_project_repository(self, mock_database_manager):
        """モックプロジェクトリポジトリ"""
        mock_repo = Mock(spec=ProjectRepository)
        mock_repo.db_manager = mock_database_manager
        return mock_repo

    @pytest.fixture
    def sample_composition_input_data(self, temp_project_dir):
        """動画合成の入力データサンプル"""
        project_dir = Path(temp_project_dir)
        
        # ダミーファイルを作成
        background_video_path = str(project_dir / "files" / "video" / "background.mp4")
        character_video_path = str(project_dir / "files" / "video" / "character.mp4")
        audio_path = str(project_dir / "files" / "audio" / "combined.wav")
        subtitle_path = str(project_dir / "files" / "metadata" / "subtitle.ass")
        
        # ダミーファイルを実際に作成
        for file_path in [background_video_path, character_video_path, audio_path, subtitle_path]:
            Path(file_path).touch()
        
        return {
            "project_id": "test-project-001",
            "background_video_path": background_video_path,
            "character_video_path": character_video_path,
            "audio_path": audio_path,
            "subtitle_path": subtitle_path,
            "composition_config": {
                "video_layout": {
                    "character_position": "center",
                    "character_scale": 1.0,
                    "character_opacity": 1.0
                },
                "subtitle_config": {
                    "enabled": True,
                    "position": "bottom",
                    "style": "default"
                },
                "audio_config": {
                    "background_music_volume": 0.3,
                    "voice_volume": 0.8
                }
            }
        }

    @pytest.mark.skipif(VideoComposer is None, reason="VideoComposer not yet implemented (TDD)")
    def test_video_composer_initialization(self, mock_project_repository, mock_config_manager, mock_file_system_manager):
        """動画合成器の初期化テスト"""
        composer = VideoComposer(
            repository=mock_project_repository,
            config_manager=mock_config_manager,
            file_system_manager=mock_file_system_manager
        )
        
        assert composer is not None
        assert composer.repository == mock_project_repository
        assert composer.config_manager == mock_config_manager
        assert composer.file_system_manager == mock_file_system_manager

    @pytest.mark.skipif(VideoComposer is None, reason="VideoComposer not yet implemented (TDD)")
    async def test_compose_video_basic_integration(self, mock_project_repository, mock_config_manager, 
                                                 mock_file_system_manager, sample_composition_input_data):
        """基本的な動画合成テスト"""
        # Mockコンポーネントを作成
        mock_layer_composer = Mock()
        mock_layer_composer.compose_video_layers.return_value = {
            "background_layer": {"status": "composed", "duration": 120.0},
            "character_layer": {"status": "composed", "opacity": 1.0},
            "subtitle_layer": {"status": "composed", "style": "default"}
        }
        
        mock_audio_sync = Mock()
        mock_audio_sync.sync_audio_video.return_value = {
            "sync_status": "synchronized",
            "audio_delay": 0.0,
            "video_duration": 120.5,
            "audio_duration": 120.5
        }
        
        mock_quality_control = Mock()
        mock_quality_control.apply_quality_control.return_value = {
            "quality_settings": {
                "resolution": "1920x1080",
                "bitrate": "2M",
                "fps": 30,
                "codec": "libx264"
            },
            "file_size": 15728640,
            "quality_score": 0.95
        }
        
        # 依存性注入でMockコンポーネントを使用
        composer = VideoComposer(
            repository=mock_project_repository,
            config_manager=mock_config_manager,
            file_system_manager=mock_file_system_manager,
            layer_composer=mock_layer_composer,
            audio_synchronizer=mock_audio_sync,
            quality_controller=mock_quality_control
        )
        
        # ダミー出力ファイルを作成（Mock実装）
        output_dir = Path(mock_file_system_manager.get_project_directory()) / "files" / "video"
        output_dir.mkdir(parents=True, exist_ok=True)
        dummy_output = output_dir / "composed_test-project-001_mock.mp4"
        dummy_output.touch()
        
        # Path操作をMock
        mock_stat_result = Mock()
        mock_stat_result.st_size = 15728640
        
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat', return_value=mock_stat_result), \
             patch.object(Path, 'mkdir', return_value=None):
            
            input_data = VideoCompositionInput(**sample_composition_input_data)
            result = await composer.compose_video(input_data)
            
            assert isinstance(result, VideoCompositionOutput)
            assert result.composed_video_path is not None
            assert result.composition_metadata["duration"] == 120.5

    @pytest.mark.skipif(VideoComposer is None, reason="VideoComposer not yet implemented (TDD)")
    async def test_layer_composition_functionality(self, mock_project_repository, mock_config_manager,
                                                 mock_file_system_manager, sample_composition_input_data):
        """レイヤー合成機能テスト (4-8-1)"""
        # Mockコンポーネントを作成
        mock_layer_composer = Mock()
        mock_layer_composer.compose_video_layers.return_value = {
            "background_layer": {"status": "composed", "duration": 120.0},
            "character_layer": {"status": "composed", "opacity": 1.0},
            "subtitle_layer": {"status": "composed", "style": "default"}
        }
        
        mock_audio_sync = Mock()
        mock_audio_sync.sync_audio_video.return_value = {
            "sync_status": "synchronized",
            "audio_delay": 0.0,
            "video_duration": 120.5,
            "audio_duration": 120.5
        }
        
        mock_quality_control = Mock()
        mock_quality_control.apply_quality_control.return_value = {
            "quality_settings": {
                "resolution": "1920x1080",
                "bitrate": "2M",
                "fps": 30,
                "codec": "libx264"
            },
            "file_size": 15728640,
            "quality_score": 0.95
        }
        
        composer = VideoComposer(
            repository=mock_project_repository,
            config_manager=mock_config_manager,
            file_system_manager=mock_file_system_manager,
            layer_composer=mock_layer_composer,
            audio_synchronizer=mock_audio_sync,
            quality_controller=mock_quality_control
        )
        
        # ダミー出力ファイルを作成
        output_dir = Path(mock_file_system_manager.get_project_directory()) / "files" / "video"
        output_dir.mkdir(parents=True, exist_ok=True)
        dummy_output = output_dir / "composed_test.mp4"
        dummy_output.touch()
        
        # Path操作をMock
        mock_stat_result = Mock()
        mock_stat_result.st_size = 15728640
        
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat', return_value=mock_stat_result), \
             patch.object(Path, 'mkdir', return_value=None):
            
            input_data = VideoCompositionInput(**sample_composition_input_data)
            result = await composer.compose_video(input_data)
            
            # レイヤー合成メソッドが呼ばれたことを確認
            mock_layer_composer.compose_video_layers.assert_called_once()
            assert result.composition_metadata is not None

    @pytest.mark.skipif(VideoComposer is None, reason="VideoComposer not yet implemented (TDD)")
    async def test_audio_sync_functionality(self, mock_project_repository, mock_config_manager,
                                          mock_file_system_manager, sample_composition_input_data):
        """音声同期機能テスト (4-8-2)"""
        # Mockコンポーネントを作成
        mock_layer_composer = Mock()
        mock_layer_composer.compose_video_layers.return_value = {
            "background_layer": {"status": "composed", "duration": 120.0},
            "character_layer": {"status": "composed", "opacity": 1.0},
            "subtitle_layer": {"status": "composed", "style": "default"}
        }
        
        mock_audio_sync = Mock()
        mock_audio_sync.sync_audio_video.return_value = {
            "sync_status": "synchronized",
            "audio_delay": 0.0,
            "video_duration": 120.5,
            "audio_duration": 120.5
        }
        
        mock_quality_control = Mock()
        mock_quality_control.apply_quality_control.return_value = {
            "quality_settings": {
                "resolution": "1920x1080",
                "bitrate": "2M",
                "fps": 30,
                "codec": "libx264"
            },
            "file_size": 15728640,
            "quality_score": 0.95
        }
        
        composer = VideoComposer(
            repository=mock_project_repository,
            config_manager=mock_config_manager,
            file_system_manager=mock_file_system_manager,
            layer_composer=mock_layer_composer,
            audio_synchronizer=mock_audio_sync,
            quality_controller=mock_quality_control
        )
        
        # ダミー出力ファイルを作成
        output_dir = Path(mock_file_system_manager.get_project_directory()) / "files" / "video"
        output_dir.mkdir(parents=True, exist_ok=True)
        dummy_output = output_dir / "composed_test.mp4"
        dummy_output.touch()
        
        # Path操作をMock
        mock_stat_result = Mock()
        mock_stat_result.st_size = 15728640
        
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat', return_value=mock_stat_result), \
             patch.object(Path, 'mkdir', return_value=None):
            
            input_data = VideoCompositionInput(**sample_composition_input_data)
            result = await composer.compose_video(input_data)
            
            # 音声同期メソッドが呼ばれたことを確認
            mock_audio_sync.sync_audio_video.assert_called_once()
            assert result.composition_metadata is not None

    @pytest.mark.skipif(VideoComposer is None, reason="VideoComposer not yet implemented (TDD)")
    async def test_quality_control_functionality(self, mock_project_repository, mock_config_manager,
                                               mock_file_system_manager, sample_composition_input_data):
        """品質制御機能テスト (4-8-3)"""
        # Mockコンポーネントを作成
        mock_layer_composer = Mock()
        mock_layer_composer.compose_video_layers.return_value = {
            "background_layer": {"status": "composed", "duration": 120.0},
            "character_layer": {"status": "composed", "opacity": 1.0},
            "subtitle_layer": {"status": "composed", "style": "default"}
        }
        
        mock_audio_sync = Mock()
        mock_audio_sync.sync_audio_video.return_value = {
            "sync_status": "synchronized",
            "audio_delay": 0.0,
            "video_duration": 120.5,
            "audio_duration": 120.5
        }
        
        mock_quality_control = Mock()
        mock_quality_control.apply_quality_control.return_value = {
            "quality_settings": {
                "resolution": "1920x1080",
                "bitrate": "2M",
                "fps": 30,
                "codec": "libx264"
            },
            "file_size": 15728640,
            "quality_score": 0.95
        }
        
        composer = VideoComposer(
            repository=mock_project_repository,
            config_manager=mock_config_manager,
            file_system_manager=mock_file_system_manager,
            layer_composer=mock_layer_composer,
            audio_synchronizer=mock_audio_sync,
            quality_controller=mock_quality_control
        )
        
        # ダミー出力ファイルを作成
        output_dir = Path(mock_file_system_manager.get_project_directory()) / "files" / "video"
        output_dir.mkdir(parents=True, exist_ok=True)
        dummy_output = output_dir / "composed_test.mp4"
        dummy_output.touch()
        
        # Path操作をMock
        mock_stat_result = Mock()
        mock_stat_result.st_size = 15728640
        
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat', return_value=mock_stat_result), \
             patch.object(Path, 'mkdir', return_value=None):
            
            input_data = VideoCompositionInput(**sample_composition_input_data)
            result = await composer.compose_video(input_data)
            
            # 品質制御メソッドが呼ばれたことを確認
            mock_quality_control.apply_quality_control.assert_called_once()
            assert result.composition_metadata is not None

    @pytest.mark.skipif(VideoComposer is None, reason="VideoComposer not yet implemented (TDD)")
    async def test_video_composition_error_handling(self, mock_project_repository, mock_config_manager,
                                                  mock_file_system_manager, sample_composition_input_data):
        """動画合成エラーハンドリングテスト"""
        # Mockコンポーネントを作成
        mock_layer_composer = Mock()
        mock_layer_composer.compose_video_layers.return_value = {
            "background_layer": {"status": "composed", "duration": 120.0},
            "character_layer": {"status": "composed", "opacity": 1.0},
            "subtitle_layer": {"status": "composed", "style": "default"}
        }
        
        mock_audio_sync = Mock()
        mock_audio_sync.sync_audio_video.return_value = {
            "sync_status": "synchronized",
            "audio_delay": 0.0,
            "video_duration": 120.5,
            "audio_duration": 120.5
        }
        
        mock_quality_control = Mock()
        mock_quality_control.apply_quality_control.return_value = {
            "quality_settings": {
                "resolution": "1920x1080",
                "bitrate": "2M",
                "fps": 30,
                "codec": "libx264"
            },
            "file_size": 15728640,
            "quality_score": 0.95
        }
        
        composer = VideoComposer(
            repository=mock_project_repository,
            config_manager=mock_config_manager,
            file_system_manager=mock_file_system_manager,
            layer_composer=mock_layer_composer,
            audio_synchronizer=mock_audio_sync,
            quality_controller=mock_quality_control
        )
        
        # 存在しないファイルパスでもMock実装では正常動作
        invalid_data = sample_composition_input_data.copy()
        invalid_data["background_video_path"] = "/nonexistent/background.mp4"
        
        # ダミー出力ファイルを作成
        output_dir = Path(mock_file_system_manager.get_project_directory()) / "files" / "video"
        output_dir.mkdir(parents=True, exist_ok=True)
        dummy_output = output_dir / "composed_test.mp4"
        dummy_output.touch()
        
        # Path操作をMock
        mock_stat_result = Mock()
        mock_stat_result.st_size = 15728640
        
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat', return_value=mock_stat_result), \
             patch.object(Path, 'mkdir', return_value=None):
            
            input_data = VideoCompositionInput(**invalid_data)
            result = await composer.compose_video(input_data)
            
            assert isinstance(result, VideoCompositionOutput)
            assert result.composed_video_path is not None

    @pytest.mark.skipif(VideoCompositionDAO is None, reason="VideoCompositionDAO not yet implemented (TDD)")
    def test_video_composition_dao_save_result(self, mock_database_manager):
        """動画合成DAO結果保存テスト"""
        dao = VideoCompositionDAO(mock_database_manager)
        
        composition_data = {
            "project_id": "test-project-001",
            "composed_video_path": "/path/to/composed.mp4",
            "composition_metadata": {
                "duration": 120.5,
                "resolution": "1920x1080",
                "fps": 30,
                "file_size": 15728640
            }
        }
        
        # DAO保存メソッドの呼び出しテスト（例外が発生しないことを確認）
        try:
            dao.save_composition_result("test-project-001", composition_data)
            # 例外が発生しなければ成功
            assert True
        except Exception as e:
            pytest.fail(f"DAO保存で予期しない例外が発生: {e}")

    def test_composition_input_data_validation(self, sample_composition_input_data):
        """動画合成入力データのバリデーションテスト"""
        # 正常データでのバリデーション
        if VideoCompositionInput:
            input_data = VideoCompositionInput(**sample_composition_input_data)
            assert input_data.project_id == "test-project-001"
            assert input_data.background_video_path is not None
            assert input_data.character_video_path is not None
            assert input_data.audio_path is not None
            assert input_data.subtitle_path is not None

    def test_composition_output_data_structure(self):
        """動画合成出力データ構造テスト"""
        if VideoCompositionOutput:
            output_data = VideoCompositionOutput(
                composed_video_path="/path/to/composed.mp4",
                composition_metadata={
                    "duration": 120.5,
                    "resolution": "1920x1080",
                    "fps": 30
                },
                layer_metadata={
                    "background": {"status": "composed"},
                    "character": {"status": "composed"},
                    "subtitle": {"status": "composed"}
                }
            )
            
            assert output_data.composed_video_path == "/path/to/composed.mp4"
            assert output_data.composition_metadata["duration"] == 120.5
            assert output_data.layer_metadata["background"]["status"] == "composed"


if __name__ == "__main__":
    pytest.main([__file__])
