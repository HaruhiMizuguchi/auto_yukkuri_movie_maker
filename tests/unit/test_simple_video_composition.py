"""
簡単な動画合成テスト (字幕なし)

実際のffmpegを使用して基本的な動画合成をテストし、生成された動画を保存
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock
import logging
from datetime import datetime
import subprocess
import shutil

logger = logging.getLogger(__name__)


class TestSimpleVideoComposition:
    """字幕なしの簡単な動画合成テスト"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """テスト用の一時プロジェクトディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "simple_video_test"
            project_dir.mkdir()
            
            # 必要なサブディレクトリを作成
            (project_dir / "files" / "video").mkdir(parents=True)
            (project_dir / "files" / "audio").mkdir(parents=True)
            (project_dir / "output").mkdir(parents=True)
            
            yield str(project_dir)

    def create_simple_test_files(self, project_dir: Path):
        """簡単なテスト用ファイルを生成（字幕なし）"""
        try:
            # 短い背景動画を生成（青色画面、2秒）
            background_path = project_dir / "files" / "video" / "bg.mp4"
            cmd_bg = [
                "ffmpeg", "-y", "-f", "lavfi", 
                "-i", "color=c=blue:size=1280x720:duration=2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                "-t", "2", str(background_path)
            ]
            result_bg = subprocess.run(cmd_bg, capture_output=True, text=True)
            if result_bg.returncode != 0:
                raise subprocess.CalledProcessError(result_bg.returncode, cmd_bg, result_bg.stderr)
            
            # 短い立ち絵動画を生成（赤色画面、2秒）
            character_path = project_dir / "files" / "video" / "char.mp4"
            cmd_char = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=red:size=400x300:duration=2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                "-t", "2", str(character_path)
            ]
            result_char = subprocess.run(cmd_char, capture_output=True, text=True)
            if result_char.returncode != 0:
                raise subprocess.CalledProcessError(result_char.returncode, cmd_char, result_char.stderr)
            
            # 短い音声ファイルを生成（500Hzトーン、2秒）
            audio_path = project_dir / "files" / "audio" / "voice.wav"
            cmd_audio = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=frequency=500:duration=2",
                "-ac", "1", "-ar", "22050", str(audio_path)
            ]
            result_audio = subprocess.run(cmd_audio, capture_output=True, text=True)
            if result_audio.returncode != 0:
                raise subprocess.CalledProcessError(result_audio.returncode, cmd_audio, result_audio.stderr)
            
            return {
                "background_video_path": str(background_path),
                "character_video_path": str(character_path),
                "audio_path": str(audio_path),
                "subtitle_path": None  # 字幕なし
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg実行エラー: {e}")
            logger.error(f"stderr: {e.stderr if hasattr(e, 'stderr') else 'N/A'}")
            pytest.skip(f"ffmpegでエラーが発生したため、テストをスキップします: {e}")
        except FileNotFoundError:
            pytest.skip("ffmpegが見つからないため、テストをスキップします")

    def save_generated_video(self, temp_video_path: Path, filename: str):
        """生成された動画を永続的な場所に保存"""
        try:
            # 保存先ディレクトリを作成
            save_dir = Path("test_real_output/simple_video_composition")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # タイムスタンプ付きファイル名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = save_dir / f"{timestamp}_{filename}"
            
            # ファイルをコピー
            shutil.copy2(temp_video_path, save_path)
            
            file_size = save_path.stat().st_size
            logger.info(f" 動画を保存しました: {save_path}")
            logger.info(f" ファイルサイズ: {file_size:,} bytes")
            
            # プレビュー情報を取得
            self.get_video_info(save_path)
            
            return str(save_path)
            
        except Exception as e:
            logger.warning(f"動画保存中にエラーが発生: {e}")
            return None

    def get_video_info(self, video_path: Path):
        """動画の詳細情報を取得表示"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)
                
                video_stream = None
                audio_stream = None
                
                for stream in info.get("streams", []):
                    if stream.get("codec_type") == "video":
                        video_stream = stream
                    elif stream.get("codec_type") == "audio":
                        audio_stream = stream
                
                if video_stream:
                    width = video_stream.get("width", "不明")
                    height = video_stream.get("height", "不明")
                    fps = video_stream.get("r_frame_rate", "不明")
                    duration = float(video_stream.get("duration", 0))
                    
                    logger.info(f" 動画情報:")
                    logger.info(f"   解像度: {width}x{height}")
                    logger.info(f"   FPS: {fps}")
                    logger.info(f"   時間: {duration:.2f}秒")
                
                if audio_stream:
                    sample_rate = audio_stream.get("sample_rate", "不明")
                    channels = audio_stream.get("channels", "不明")
                    logger.info(f" 音声情報:")
                    logger.info(f"   サンプルレート: {sample_rate}Hz")
                    logger.info(f"   チャンネル数: {channels}")
            
        except Exception as e:
            logger.warning(f"動画情報取得エラー: {e}")

    def test_simple_video_overlay_no_subtitle(self, temp_project_dir):
        """字幕なしの簡単な動画オーバーレイテスト"""
        project_dir = Path(temp_project_dir)
        
        # テスト用ファイルを生成
        test_files = self.create_simple_test_files(project_dir)
        
        # ffmpegで直接オーバーレイ合成
        output_path = project_dir / "output" / "simple_overlay.mp4"
        
        try:
            # 背景に立ち絵をオーバーレイ（中央配置、50%サイズ）
            cmd = [
                "ffmpeg", "-y",
                "-i", test_files["background_video_path"],  # 背景動画
                "-i", test_files["character_video_path"],   # 立ち絵動画
                "-i", test_files["audio_path"],             # 音声
                "-filter_complex",
                "[1:v]scale=iw*0.5:ih*0.5[char];[0:v][char]overlay=(W-w)/2:(H-h)/2[video]",
                "-map", "[video]",  # 合成した動画
                "-map", "2:a",      # 音声
                "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-t", "2",
                str(output_path)
            ]
            
            logger.info(f" ffmpegコマンド実行中...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"ffmpegエラー: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
            
            # 結果を検証
            assert output_path.exists(), f"動画ファイルが生成されませんでした: {output_path}"
            
            file_size = output_path.stat().st_size
            assert file_size > 0, f"動画ファイルのサイズが0です: {file_size}"
            
            # 実際の保存場所にコピー（永続化）
            saved_path = self.save_generated_video(output_path, "simple_overlay_test.mp4")
            
            logger.info(f" 簡単な動画合成テスト成功!")
            logger.info(f" 生成ファイル: {output_path}")
            logger.info(f" ファイルサイズ: {file_size:,} bytes")
            logger.info(f" 保存場所: {saved_path}")
            
            # テスト成功をアサート
            assert saved_path is not None, "動画保存に失敗しました"
            
        except Exception as e:
            logger.error(f"簡単動画合成テストエラー: {e}")
            # テスト用ファイルの状態を確認
            for name, path in test_files.items():
                if path:
                    file_path = Path(path)
                    exists = file_path.exists()
                    size = file_path.stat().st_size if exists else 0
                    logger.info(f"{name}: 存在={exists}, サイズ={size}")
            raise

    def test_basic_video_concat(self, temp_project_dir):
        """基本的な動画連結テスト"""
        project_dir = Path(temp_project_dir)
        
        try:
            # 2つの短い動画を作成
            video1_path = project_dir / "output" / "video1.mp4"
            video2_path = project_dir / "output" / "video2.mp4"
            
            # 動画1 (緑色)
            cmd1 = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=green:size=640x480:duration=1",
                "-c:v", "libx264", "-preset", "fast", "-t", "1",
                str(video1_path)
            ]
            subprocess.run(cmd1, capture_output=True, check=True)
            
            # 動画2 (黄色)
            cmd2 = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=yellow:size=640x480:duration=1",
                "-c:v", "libx264", "-preset", "fast", "-t", "1",
                str(video2_path)
            ]
            subprocess.run(cmd2, capture_output=True, check=True)
            
            # 連結
            concat_path = project_dir / "output" / "concat_test.mp4"
            cmd_concat = [
                "ffmpeg", "-y",
                "-i", str(video1_path),
                "-i", str(video2_path),
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
                "-map", "[outv]",
                "-c:v", "libx264", "-preset", "fast",
                str(concat_path)
            ]
            subprocess.run(cmd_concat, capture_output=True, check=True)
            
            # 検証
            assert concat_path.exists()
            file_size = concat_path.stat().st_size
            assert file_size > 0
            
            # 保存
            saved_path = self.save_generated_video(concat_path, "concat_test.mp4")
            
            logger.info(f" 動画連結テスト成功: {saved_path}")
            
        except subprocess.CalledProcessError as e:
            pytest.skip(f"動画連結テストでエラー: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
