"""
字幕生成モジュール実API統合テスト

TDD開発：
- 字幕タイミング（音声同期、読みやすさ、表示時間調整）
- スタイル適用（フォント設定、色・サイズ制御、縁取り効果）
- ASS形式出力（形式準拠、効果適用、互換性確保）

実装方針：
- TTSタイムスタンプデータから字幕生成
- Advanced SubStation Alpha（ASS）形式対応
- スピーカー別スタイル設定
- 読みやすさ最適化（表示時間・改行）
- DAO分離（字幕生成専用SQL操作）
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from src.modules.subtitle_generator import (
    SubtitleGenerator,
    SubtitleGenerationInput,
    SubtitleGenerationOutput,
    SubtitleSegment,
    SubtitleStyle,
    AssSubtitle,
    SubtitleConfig
)
from src.dao.subtitle_generation_dao import SubtitleGenerationDAO
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.core.file_system_manager import FileSystemManager


class TestSubtitleGeneratorRealAPI:
    """字幕生成モジュール実API統合テスト"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """一時プロジェクトディレクトリ"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            
            # 必要なサブディレクトリを作成
            (project_path / "files" / "metadata").mkdir(parents=True)
            (project_path / "files" / "subtitles").mkdir(parents=True)
            
            yield project_path
    
    @pytest.fixture
    def mock_repository(self, temp_project_dir):
        """モックプロジェクトリポジトリ"""
        repo = Mock(spec=ProjectRepository)
        repo.db_manager = Mock()
        return repo
    
    @pytest.fixture
    def mock_config_manager(self):
        """モック設定マネージャー"""
        config = Mock(spec=ConfigManager)
        # 字幕設定を返す
        config.get_value.return_value = {
            "default_style": {
                "font_name": "Arial",
                "font_size": 24,
                "primary_color": "&H00FFFFFF",  # 白
                "secondary_color": "&H000000FF",  # 赤
                "outline_color": "&H00000000",   # 黒
                "back_color": "&H80000000",      # 半透明黒
                "bold": False,
                "italic": False,
                "underline": False,
                "outline": 2,
                "shadow": 0,
                "alignment": 2,
                "margin_left": 10,
                "margin_right": 10,
                "margin_vertical": 20
            },
            "speaker_styles": {
                "reimu": {
                    "font_name": "Arial",
                    "font_size": 26,
                    "primary_color": "&H00FFFFFF",
                    "outline_color": "&H00FF0000"  # 青アウトライン
                },
                "marisa": {
                    "font_name": "Arial", 
                    "font_size": 26,
                    "primary_color": "&H00FFFFFF",
                    "outline_color": "&H0000FF00"  # 緑アウトライン
                }
            },
            "timing": {
                "min_duration": 1.0,
                "max_duration": 8.0,
                "char_per_second": 15,
                "overlap_threshold": 0.1
            },
            "readability": {
                "max_line_length": 40,
                "max_lines": 2,
                "break_long_sentences": True
            }
        }
        return config
    
    @pytest.fixture
    def mock_file_system_manager(self, temp_project_dir):
        """モックファイルシステムマネージャー"""
        fs_manager = Mock()
        fs_manager.get_project_directory.return_value = str(temp_project_dir)
        fs_manager.get_project_file_path.return_value = temp_project_dir / "test_file.ass"
        return fs_manager
    
    @pytest.fixture
    def sample_tts_data(self):
        """サンプルTTSデータ（タイムスタンプ付き）"""
        return {
            "audio_segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "text": "こんにちは、霊夢です！今日は面白い話をお届けします。",
                    "audio_path": "/path/to/segment_1_reimu.wav",
                    "duration": 3.5,
                    "timestamps": [
                        {"word": "こんにちは", "start_time": 0.0, "end_time": 1.2, "confidence": 0.95},
                        {"word": "霊夢", "start_time": 1.3, "end_time": 1.8, "confidence": 0.98},
                        {"word": "です", "start_time": 1.9, "end_time": 2.2, "confidence": 0.97},
                        {"word": "今日は", "start_time": 2.5, "end_time": 3.0, "confidence": 0.96},
                        {"word": "面白い", "start_time": 3.1, "end_time": 3.5, "confidence": 0.94}
                    ],
                    "emotion": "happy"
                },
                {
                    "segment_id": 2,
                    "speaker": "marisa",
                    "text": "魔理沙だぜ！一緒に学んでいこうな。",
                    "audio_path": "/path/to/segment_2_marisa.wav",
                    "duration": 2.8,
                    "timestamps": [
                        {"word": "魔理沙", "start_time": 0.0, "end_time": 0.8, "confidence": 0.99},
                        {"word": "だぜ", "start_time": 0.9, "end_time": 1.3, "confidence": 0.97},
                        {"word": "一緒に", "start_time": 1.6, "end_time": 2.1, "confidence": 0.95},
                        {"word": "学んで", "start_time": 2.2, "end_time": 2.8, "confidence": 0.96}
                    ],
                    "emotion": "neutral"
                }
            ],
            "combined_audio_path": "/path/to/combined_audio.wav",
            "total_duration": 6.3
        }
    
    @pytest.fixture
    def sample_script_data(self):
        """サンプルスクリプトデータ"""
        return {
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "text": "こんにちは、霊夢です！今日は面白い話をお届けします。",
                    "emotion": "happy"
                },
                {
                    "segment_id": 2, 
                    "speaker": "marisa",
                    "text": "魔理沙だぜ！一緒に学んでいこうな。",
                    "emotion": "neutral"
                }
            ]
        }
    
    @pytest.fixture 
    def subtitle_generator(self, mock_repository, mock_config_manager, mock_file_system_manager):
        """字幕生成モジュールインスタンス"""
        # DAOをモック化（実際のSQL操作は後でテスト）
        with patch('src.modules.subtitle_generator.SubtitleGenerationDAO') as mock_dao_class:
            mock_dao = Mock(spec=SubtitleGenerationDAO)
            mock_dao_class.return_value = mock_dao
            
            generator = SubtitleGenerator(
                repository=mock_repository,
                config_manager=mock_config_manager,
                file_system_manager=mock_file_system_manager
            )
            generator.dao = mock_dao
            return generator
    
    def test_subtitle_timing_from_tts_data(self, subtitle_generator, sample_tts_data, sample_script_data):
        """TTSデータからの字幕タイミング生成テスト"""
        # 入力データ準備
        input_data = SubtitleGenerationInput(
            project_id="test-project-001",
            script_data=sample_script_data,
            audio_metadata=sample_tts_data,
            subtitle_config=SubtitleConfig()
        )
        
        # DAOモック設定
        subtitle_generator.dao.get_script_data.return_value = sample_script_data
        subtitle_generator.dao.get_audio_metadata.return_value = sample_tts_data
        
        # 字幕タイミング生成テスト
        subtitle_segments = subtitle_generator._generate_subtitle_timing(
            input_data.script_data, input_data.audio_metadata
        )
        
        # 検証
        assert len(subtitle_segments) == 2
        
        # 最初のセグメント検証
        first_segment = subtitle_segments[0]
        assert first_segment.segment_id == 1
        assert first_segment.speaker == "reimu"
        assert first_segment.text == "こんにちは、霊夢です！今日は面白い話をお届けします。"
        assert first_segment.start_time == 0.0
        assert first_segment.end_time == 3.5
        assert first_segment.emotion == "happy"
        
        # タイムスタンプデータが含まれることを確認
        assert len(first_segment.word_timestamps) == 5
        assert first_segment.word_timestamps[0]["word"] == "こんにちは"
        assert first_segment.word_timestamps[0]["start_time"] == 0.0
        
        print(f"✅ 字幕タイミング生成成功: {len(subtitle_segments)}セグメント")
    
    def test_subtitle_style_application(self, subtitle_generator, sample_tts_data, sample_script_data):
        """字幕スタイル適用テスト"""
        # 入力データ準備
        input_data = SubtitleGenerationInput(
            project_id="test-project-002",
            script_data=sample_script_data,
            audio_metadata=sample_tts_data,
            subtitle_config=SubtitleConfig()
        )
        
        # 字幕セグメント生成
        subtitle_segments = subtitle_generator._generate_subtitle_timing(
            input_data.script_data, input_data.audio_metadata
        )
        
        # スタイル適用テスト
        styled_subtitles = subtitle_generator._apply_subtitle_styles(subtitle_segments)
        
        # 検証
        assert len(styled_subtitles) == 2
        
        # reimuのスタイル確認
        reimu_subtitle = styled_subtitles[0]
        assert reimu_subtitle.style_name == "reimu"
        assert reimu_subtitle.segment.speaker == "reimu"
        
        # marisaのスタイル確認
        marisa_subtitle = styled_subtitles[1]
        assert marisa_subtitle.style_name == "marisa"
        assert marisa_subtitle.segment.speaker == "marisa"
        
        print(f"✅ 字幕スタイル適用成功: {len(styled_subtitles)}字幕")
    
    def test_readability_optimization(self, subtitle_generator, sample_tts_data):
        """読みやすさ最適化テスト"""
        # 長いテキストのテストデータ
        long_text_data = {
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "text": "これは非常に長いテキストの例でありまして、通常の字幕では一行に収まらないため、適切に改行する必要があります。",
                    "emotion": "neutral"
                }
            ]
        }
        
        long_tts_data = {
            "audio_segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "text": "これは非常に長いテキストの例でありまして、通常の字幕では一行に収まらないため、適切に改行する必要があります。",
                    "duration": 8.0,
                    "timestamps": [
                        {"word": "これは", "start_time": 0.0, "end_time": 0.5, "confidence": 0.95},
                        {"word": "非常に", "start_time": 0.6, "end_time": 1.1, "confidence": 0.94},
                        {"word": "長い", "start_time": 1.2, "end_time": 1.5, "confidence": 0.96},
                        {"word": "テキスト", "start_time": 1.6, "end_time": 2.2, "confidence": 0.97},
                        # ... 他の単語
                    ],
                    "emotion": "neutral"
                }
            ],
            "total_duration": 8.0
        }
        
        # 字幕タイミング生成
        subtitle_segments = subtitle_generator._generate_subtitle_timing(long_text_data, long_tts_data)
        
        # 読みやすさ最適化
        optimized_segments = subtitle_generator._optimize_readability(subtitle_segments)
        
        # 検証
        assert len(optimized_segments) >= 1  # 分割されて複数になる可能性
        
        # 各セグメントが読みやすい長さか確認
        for segment in optimized_segments:
            assert len(segment.text) <= 40 * 2  # 最大2行、各行40文字
            assert segment.duration >= 1.0  # 最小表示時間
            
        print(f"✅ 読みやすさ最適化成功: {len(optimized_segments)}セグメント")
    
    def test_ass_format_generation(self, subtitle_generator, sample_tts_data, sample_script_data, temp_project_dir):
        """ASS形式字幕ファイル生成テスト"""
        # 入力データ準備
        input_data = SubtitleGenerationInput(
            project_id="test-project-003",
            script_data=sample_script_data,
            audio_metadata=sample_tts_data,
            subtitle_config=SubtitleConfig()
        )
        
        # DAOモック設定
        subtitle_generator.dao.get_script_data.return_value = sample_script_data
        subtitle_generator.dao.get_audio_metadata.return_value = sample_tts_data
        
        # 出力ファイルパス
        output_path = temp_project_dir / "files" / "metadata" / "subtitle.ass"
        
        # ASS字幕生成テスト
        ass_content = subtitle_generator._generate_ass_subtitle(
            input_data.script_data, input_data.audio_metadata, str(output_path)
        )
        
        # 検証
        assert isinstance(ass_content, str)
        assert "[Script Info]" in ass_content  # ASSファイルヘッダー
        assert "[V4+ Styles]" in ass_content   # スタイル定義
        assert "[Events]" in ass_content       # イベント（字幕）
        
        # 話者ごとのスタイルが含まれているかチェック
        assert "reimu" in ass_content
        assert "marisa" in ass_content
        
        # 実際のセリフが含まれているかチェック
        assert "霊夢です" in ass_content
        assert "魔理沙だぜ" in ass_content
        
        # ファイルが作成されているかチェック
        assert output_path.exists()
        with open(output_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            assert file_content == ass_content
        
        print(f"✅ ASS形式字幕生成成功: {len(ass_content)}文字")
    
    def test_full_subtitle_generation_workflow(self, subtitle_generator, sample_tts_data, sample_script_data, temp_project_dir):
        """字幕生成の全体ワークフローテスト"""
        # 入力データ準備
        input_data = SubtitleGenerationInput(
            project_id="test-project-004",
            script_data=sample_script_data,
            audio_metadata=sample_tts_data,
            subtitle_config=SubtitleConfig()
        )
        
        # DAOモック設定
        subtitle_generator.dao.get_script_data.return_value = sample_script_data
        subtitle_generator.dao.get_audio_metadata.return_value = sample_tts_data
        subtitle_generator.dao.save_subtitle_result.return_value = None
        
        # 全体ワークフロー実行
        result = subtitle_generator.generate_subtitles(input_data)
        
        # 結果検証
        assert isinstance(result, SubtitleGenerationOutput)
        assert result.project_id == "test-project-004"
        assert len(result.subtitle_segments) == 2
        assert result.ass_file_path.endswith(".ass")
        assert result.total_duration == 6.3
        
        # DAOメソッドが呼ばれたことを確認
        subtitle_generator.dao.get_script_data.assert_called_once_with("test-project-004")
        subtitle_generator.dao.get_audio_metadata.assert_called_once_with("test-project-004")
        subtitle_generator.dao.save_subtitle_result.assert_called_once()
        
        print(f"✅ 字幕生成ワークフロー完全成功")
        print(f"   - プロジェクトID: {result.project_id}")
        print(f"   - セグメント数: {len(result.subtitle_segments)}")
        print(f"   - ASSファイル: {result.ass_file_path}")
        print(f"   - 総時間: {result.total_duration}秒") 