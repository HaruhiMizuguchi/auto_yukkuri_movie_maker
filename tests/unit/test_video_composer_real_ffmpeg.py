"""
VideoComposer実際のffmpeg動画合成テスト

実際のffmpeg実装を使用して動画を生成し、保存する統合テスト
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock
import logging
from datetime import datetime

# テスト対象のクラスをインポート
from src.modules.video_composer import VideoComposer, VideoCompositionInput, VideoCompositionOutput
from src.dao.video_composition_dao import VideoCompositionDAO

# 必要な依存関係
from src.core.database_manager import DatabaseManager
from src.core.config_manager import ConfigManager
from src.core.file_system_manager import FileSystemManager
from src.core.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


class TestVideoComposerRealFFmpeg:
    """実際のffmpegを使った動画合成テスト"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """テスト用の一時プロジェクトディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "test_real_ffmpeg_project"
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
        mock_connection = Mock()
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        mock_db.get_connection.return_value = mock_connection
        return mock_db

    @pytest.fixture
    def mock_config_manager(self):
        """設定マネージャー（実際の設定を返す）"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_value.return_value = {
            "output_format": "mp4",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "crf": 23,
            "preset": "medium",
            "resolution": "1920x1080",
            "fps": 30,
            "bitrate": "2M"
        }
        return mock_config

    @pytest.fixture
    def mock_file_system_manager(self, temp_project_dir):
        """ファイルシステムマネージャー"""
        mock_fs = Mock(spec=FileSystemManager)
        mock_fs.get_project_directory.return_value = temp_project_dir
        return mock_fs

    @pytest.fixture
    def mock_project_repository(self, mock_database_manager):
        """プロジェクトリポジトリ"""
        mock_repo = Mock(spec=ProjectRepository)
        mock_repo.db_manager = mock_database_manager
        return mock_repo

    def create_test_video_files(self, project_dir: Path):
        """テスト用の動画音声字幕ファイルを生成"""
        import subprocess
        
        try:
            # 簡単な背景動画を生成（青色画面、3秒）
            background_path = project_dir / "files" / "video" / "background.mp4"
            cmd_bg = [
                "ffmpeg", "-y", "-f", "lavfi", 
                "-i", "color=c=blue:size=1920x1080:duration=3",
                "-c:v", "libx264", "-t", "3", str(background_path)
            ]
            subprocess.run(cmd_bg, capture_output=True, check=True)
            
            # 簡単な立ち絵動画を生成（緑色画面、3秒、透明度対応）
            character_path = project_dir / "files" / "video" / "character.mp4"
            cmd_char = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=green:size=640x480:duration=3",
                "-c:v", "libx264", "-t", "3", str(character_path)
            ]
            subprocess.run(cmd_char, capture_output=True, check=True)
            
            # 簡単な音声ファイルを生成（1kHzトーン、3秒）
            audio_path = project_dir / "files" / "audio" / "combined.wav"
            cmd_audio = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=frequency=1000:duration=3",
                "-ac", "2", "-ar", "44100", str(audio_path)
            ]
            subprocess.run(cmd_audio, capture_output=True, check=True)
            
            # 簡単な字幕ファイルを生成（ASS形式）
            subtitle_path = project_dir / "files" / "metadata" / "subtitle.ass"
            subtitle_content = """[Script Info]
Title: Test Subtitle
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:02.50,Default,,0,0,0,,テスト字幕です
Dialogue: 0,0:00:02.50,0:00:03.00,Default,,0,0,0,,動画合成テスト
"""
            subtitle_path.write_text(subtitle_content, encoding='utf-8')
            
            return {
                "background_video_path": str(background_path),
                "character_video_path": str(character_path),
                "audio_path": str(audio_path),
                "subtitle_path": str(subtitle_path)
            }
            
        except subprocess.CalledProcessError as e:
            pytest.skip(f"ffmpegが利用できないため、テストをスキップします: {e}")
        except FileNotFoundError:
            pytest.skip("ffmpegが見つからないため、テストをスキップします")

    def test_real_ffmpeg_video_composition(self, mock_project_repository, mock_config_manager, 
                                         mock_file_system_manager, temp_project_dir):
        """実際のffmpegを使った動画合成テスト"""
        project_dir = Path(temp_project_dir)
        
        # テスト用ファイルを生成
        test_files = self.create_test_video_files(project_dir)
        
        # 合成入力データを作成
        composition_data = {
            "project_id": "real-ffmpeg-test-001",
            **test_files,
            "composition_config": {
                "video_layout": {
                    "character_position": "center",
                    "character_scale": 0.5,
                    "character_opacity": 0.8
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
        
        # VideoComposerを作成（実際のffmpeg実装を使用）
        composer = VideoComposer(
            repository=mock_project_repository,
            config_manager=mock_config_manager,
            file_system_manager=mock_file_system_manager
            # layer_composer, audio_synchronizer, quality_controllerは
            # デフォルトで実際のffmpeg実装が使われる
        )
        
        # 実際の動画合成を実行
        input_data = VideoCompositionInput(**composition_data)
        
        try:
            # 実際に動画を合成
            import asyncio
            result = asyncio.run(composer.compose_video(input_data))
            
            # 結果を検証
            assert isinstance(result, VideoCompositionOutput)
            assert result.composed_video_path is not None
            
            # 生成された動画ファイルが存在することを確認
            output_video = Path(result.composed_video_path)
            assert output_video.exists(), f"動画ファイルが生成されませんでした: {result.composed_video_path}"
            
            # ファイルサイズが0より大きいことを確認
            file_size = output_video.stat().st_size
            assert file_size > 0, f"動画ファイルのサイズが0です: {file_size}"
            
            # メタデータの確認
            assert result.composition_metadata["file_size"] == file_size
            assert result.composition_metadata["resolution"] == "1920x1080"
            assert result.composition_metadata["fps"] == 30
            
            # 実際の保存場所にコピー（永続化）
            self.save_generated_video(output_video, "real_ffmpeg_composition_test.mp4")
            
            logger.info(f" 実際の動画合成テスト成功!")
            logger.info(f" 生成ファイル: {result.composed_video_path}")
            logger.info(f" ファイルサイズ: {file_size:,} bytes")
            logger.info(f" 解像度: {result.composition_metadata['resolution']}")
            logger.info(f" FPS: {result.composition_metadata['fps']}")
            
            return result
            
        except Exception as e:
            logger.error(f"動画合成テストでエラーが発生: {e}")
            # テスト用ファイルの状態を確認
            for name, path in test_files.items():
                file_path = Path(path)
                logger.info(f"{name}: 存在={file_path.exists()}, サイズ={file_path.stat().st_size if file_path.exists() else 'N/A'}")
            raise

    def save_generated_video(self, temp_video_path: Path, filename: str):
        """生成された動画を永続的な場所に保存"""
        try:
            # 保存先ディレクトリを作成
            save_dir = Path("test_real_output/video_composition")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # タイムスタンプ付きファイル名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = save_dir / f"{timestamp}_{filename}"
            
            # ファイルをコピー
            import shutil
            shutil.copy2(temp_video_path, save_path)
            
            logger.info(f" 動画を保存しました: {save_path}")
            logger.info(f" ファイルサイズ: {save_path.stat().st_size:,} bytes")
            
            return str(save_path)
            
        except Exception as e:
            logger.warning(f"動画保存中にエラーが発生: {e}")
            return None

    @pytest.mark.integration
    def test_ffmpeg_layer_composition_only(self, mock_project_repository, mock_config_manager,
                                         mock_file_system_manager, temp_project_dir):
        """レイヤー合成のみのテスト"""
        project_dir = Path(temp_project_dir)
        test_files = self.create_test_video_files(project_dir)
        
        # レイヤー合成器のみをテスト
        from src.modules.video_composer import FFmpegLayerComposer
        
        layer_composer = FFmpegLayerComposer()
        
        output_path = str(project_dir / "files" / "video" / "layer_test.mp4")
        
        composition_config = {
            "video_layout": {
                "character_scale": 0.6,
                "character_opacity": 0.9
            },
            "subtitle_config": {
                "enabled": True
            }
        }
        
        try:
            result = layer_composer.compose_video_layers(
                background_path=test_files["background_video_path"],
                character_path=test_files["character_video_path"], 
                subtitle_path=test_files["subtitle_path"],
                output_path=output_path,
                composition_config=composition_config
            )
            
            # 結果を確認
            assert Path(output_path).exists()
            assert result["background_layer"]["status"] == "composed"
            
            # 保存
            self.save_generated_video(Path(output_path), "layer_composition_test.mp4")
            
            logger.info(f" レイヤー合成テスト成功: {output_path}")
            
        except Exception as e:
            logger.error(f"レイヤー合成テストエラー: {e}")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
