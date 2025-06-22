"""
字幕生成モジュール (4-7)

flow_definition.yamlに基づく仕様：
- 入力: スクリプトデータ + TTS音声メタデータ
- 処理: 字幕タイミング・スタイル適用・ASS形式出力
- 出力: 字幕セグメント・ASSファイル・メタデータ

実装方針：
- TTSタイムスタンプから字幕タイミング自動生成
- 話者別スタイル設定・読みやすさ最適化
- ASS (Advanced SubStation Alpha) 形式対応
- DAO分離（字幕生成専用SQL操作）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Protocol
import json
import logging
from pathlib import Path
import uuid
from datetime import datetime
import re
import math
import hashlib

from ..core.project_repository import ProjectRepository
from ..core.config_manager import ConfigManager
from ..core.file_system_manager import FileSystemManager
from ..dao.subtitle_generation_dao import SubtitleGenerationDAO


@dataclass
class SubtitleConfig:
    """字幕設定"""
    min_duration: float = 1.0          # 最小表示時間（秒）
    max_duration: float = 8.0          # 最大表示時間（秒）
    char_per_second: int = 15          # 1秒あたりの文字数
    overlap_threshold: float = 0.1     # 重複許容閾値（秒）
    max_line_length: int = 40          # 最大行文字数
    max_lines: int = 2                 # 最大行数
    break_long_sentences: bool = True  # 長文の自動分割


@dataclass
class SubtitleSegment:
    """字幕セグメント"""
    segment_id: int
    speaker: str
    text: str
    start_time: float
    end_time: float
    duration: float
    word_timestamps: List[Dict[str, Any]]
    emotion: str = "neutral"
    style_name: Optional[str] = None
    line_breaks: Optional[List[int]] = None


@dataclass
class SubtitleStyle:
    """字幕スタイル"""
    style_name: str
    font_name: str = "Arial"
    font_size: int = 24
    primary_color: str = "&H00FFFFFF"    # 白
    secondary_color: str = "&H000000FF"  # 赤
    outline_color: str = "&H00000000"    # 黒
    back_color: str = "&H80000000"       # 半透明黒
    bold: bool = False
    italic: bool = False
    underline: bool = False
    outline: int = 2
    shadow: int = 0
    alignment: int = 2
    margin_left: int = 10
    margin_right: int = 10
    margin_vertical: int = 20


@dataclass
class AssSubtitle:
    """ASS字幕"""
    segment: SubtitleSegment
    style: SubtitleStyle
    style_name: str


@dataclass
class SubtitleGenerationInput:
    """字幕生成入力"""
    project_id: str
    script_data: Dict[str, Any]
    audio_metadata: Dict[str, Any]
    subtitle_config: SubtitleConfig


@dataclass
class SubtitleGenerationOutput:
    """字幕生成出力"""
    project_id: str
    subtitle_segments: List[SubtitleSegment]
    ass_file_path: str
    total_duration: float
    generation_metadata: Dict[str, Any]


class SubtitleGenerator:
    """字幕生成モジュール"""
    
    def __init__(
        self,
        repository: ProjectRepository,
        config_manager: ConfigManager,
        file_system_manager: FileSystemManager,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            repository: プロジェクトリポジトリ
            config_manager: 設定マネージャー
            file_system_manager: ファイルシステムマネージャー
            logger: ロガー
        """
        self.repository = repository
        self.config_manager = config_manager
        self.file_system_manager = file_system_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # DAOを初期化
        self.dao = SubtitleGenerationDAO(
            db_manager=repository.db_manager,
            logger=logger
        )
        
        # 字幕設定を読み込み
        self._load_subtitle_config()
    
    def _load_subtitle_config(self) -> None:
        """字幕設定を読み込み"""
        try:
            self.subtitle_settings = self.config_manager.get_value("subtitle_settings", {})
            self.logger.info("字幕設定読み込み完了")
        except Exception as e:
            self.logger.warning(f"字幕設定読み込み失敗、デフォルト設定使用: {e}")
            self.subtitle_settings = self._get_default_subtitle_settings()
    
    def _get_default_subtitle_settings(self) -> Dict[str, Any]:
        """デフォルト字幕設定を取得"""
        return {
            "default_style": {
                "font_name": "Arial",
                "font_size": 24,
                "primary_color": "&H00FFFFFF",
                "secondary_color": "&H000000FF",
                "outline_color": "&H00000000",
                "back_color": "&H80000000",
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
    
    def generate_subtitles(self, input_data: SubtitleGenerationInput) -> SubtitleGenerationOutput:
        """
        字幕を生成
        
        Args:
            input_data: 字幕生成入力
            
        Returns:
            字幕生成出力
        """
        try:
            self.logger.info(f"字幕生成開始: project_id={input_data.project_id}")
            
            # 1. データ取得
            script_data = self.dao.get_script_data(input_data.project_id)
            audio_metadata = self.dao.get_audio_metadata(input_data.project_id)
            
            # 2. 字幕タイミング生成
            subtitle_segments = self._generate_subtitle_timing(script_data, audio_metadata)
            
            # 3. 読みやすさ最適化
            optimized_segments = self._optimize_readability(subtitle_segments)
            
            # 4. スタイル適用
            styled_subtitles = self._apply_subtitle_styles(optimized_segments)
            
            # 5. ASSファイル生成
            ass_file_path = self._generate_ass_file(
                input_data.project_id, styled_subtitles, audio_metadata
            )
            
            # 6. 結果保存
            total_duration = audio_metadata.get("total_duration", 0.0)
            generation_metadata = {
                "segments_count": len(optimized_segments),
                "total_styles": len(set(s.style_name for s in styled_subtitles)),
                "processing_time": datetime.now().isoformat()
            }
            
            # DB保存
            segment_dicts = [asdict(seg) for seg in optimized_segments]
            self.dao.save_subtitle_result(
                project_id=input_data.project_id,
                subtitle_segments=segment_dicts,
                ass_file_path=ass_file_path,
                total_duration=total_duration,
                generation_metadata=generation_metadata
            )
            
            # 結果作成
            result = SubtitleGenerationOutput(
                project_id=input_data.project_id,
                subtitle_segments=optimized_segments,
                ass_file_path=ass_file_path,
                total_duration=total_duration,
                generation_metadata=generation_metadata
            )
            
            self.logger.info(f"字幕生成完了: segments={len(optimized_segments)}")
            return result
            
        except Exception as e:
            self.logger.error(f"字幕生成エラー: {e}")
            raise
    
    def _generate_subtitle_timing(
        self, 
        script_data: Dict[str, Any], 
        audio_metadata: Dict[str, Any]
    ) -> List[SubtitleSegment]:
        """
        字幕タイミングを生成
        
        Args:
            script_data: スクリプトデータ
            audio_metadata: 音声メタデータ
            
        Returns:
            字幕セグメント一覧
        """
        try:
            segments = []
            audio_segments = audio_metadata.get("audio_segments", [])
            
            for audio_seg in audio_segments:
                # スクリプトから対応セグメントを検索
                script_segment = None
                for script_seg in script_data.get("segments", []):
                    if script_seg["segment_id"] == audio_seg["segment_id"]:
                        script_segment = script_seg
                        break
                
                if not script_segment:
                    self.logger.warning(f"対応スクリプトが見つかりません: segment_id={audio_seg['segment_id']}")
                    continue
                
                # 字幕セグメント作成
                subtitle_segment = SubtitleSegment(
                    segment_id=audio_seg["segment_id"],
                    speaker=audio_seg["speaker"],
                    text=script_segment["text"],
                    start_time=0.0,  # 後で調整
                    end_time=audio_seg["duration"],
                    duration=audio_seg["duration"],
                    word_timestamps=audio_seg.get("timestamps", []),
                    emotion=script_segment.get("emotion", "neutral")
                )
                
                segments.append(subtitle_segment)
            
            # タイミング調整
            self._adjust_timing(segments)
            
            self.logger.info(f"字幕タイミング生成完了: {len(segments)}セグメント")
            return segments
            
        except Exception as e:
            self.logger.error(f"字幕タイミング生成エラー: {e}")
            raise
    
    def _adjust_timing(self, segments: List[SubtitleSegment]) -> None:
        """
        タイミングを調整
        
        Args:
            segments: 字幕セグメント一覧
        """
        try:
            timing_config = self.subtitle_settings.get("timing", {})
            min_duration = timing_config.get("min_duration", 1.0)
            max_duration = timing_config.get("max_duration", 8.0)
            char_per_second = timing_config.get("char_per_second", 15)
            
            current_time = 0.0
            
            for segment in segments:
                # 開始時間設定
                segment.start_time = current_time
                
                # 理想的な表示時間を計算
                ideal_duration = len(segment.text) / char_per_second
                ideal_duration = max(min_duration, min(ideal_duration, max_duration))
                
                # 音声継続時間と比較して調整
                actual_duration = max(ideal_duration, segment.duration)
                
                # 終了時間設定
                segment.end_time = segment.start_time + actual_duration
                segment.duration = actual_duration
                
                # 次のセグメントの開始時間更新
                current_time = segment.end_time
            
            self.logger.debug(f"タイミング調整完了: {len(segments)}セグメント")
            
        except Exception as e:
            self.logger.error(f"タイミング調整エラー: {e}")
            raise
    
    def _optimize_readability(self, segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
        """
        読みやすさを最適化
        
        Args:
            segments: 字幕セグメント一覧
            
        Returns:
            最適化された字幕セグメント一覧
        """
        try:
            readability_config = self.subtitle_settings.get("readability", {})
            max_line_length = readability_config.get("max_line_length", 40)
            max_lines = readability_config.get("max_lines", 2)
            break_long_sentences = readability_config.get("break_long_sentences", True)
            
            optimized_segments = []
            
            for segment in segments:
                text = segment.text
                
                # 長い文章の場合は分割を検討
                if break_long_sentences and len(text) > max_line_length * max_lines:
                    split_segments = self._split_long_segment(segment, max_line_length, max_lines)
                    optimized_segments.extend(split_segments)
                else:
                    # 改行位置を計算
                    line_breaks = self._calculate_line_breaks(text, max_line_length)
                    segment.line_breaks = line_breaks
                    optimized_segments.append(segment)
            
            self.logger.info(f"読みやすさ最適化完了: {len(optimized_segments)}セグメント")
            return optimized_segments
            
        except Exception as e:
            self.logger.error(f"読みやすさ最適化エラー: {e}")
            raise
    
    def _split_long_segment(
        self, 
        segment: SubtitleSegment, 
        max_line_length: int, 
        max_lines: int
    ) -> List[SubtitleSegment]:
        """
        長いセグメントを分割
        
        Args:
            segment: 分割対象セグメント
            max_line_length: 最大行文字数
            max_lines: 最大行数
            
        Returns:
            分割されたセグメント一覧
        """
        try:
            text = segment.text
            max_chars = max_line_length * max_lines
            
            # 句読点で分割を試行
            sentences = re.split(r'[。！？.]', text)
            
            split_segments = []
            current_text = ""
            current_duration = 0.0
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                
                # 句読点を復元
                sentence = sentence.strip() + "。"
                
                if len(current_text + sentence) <= max_chars:
                    current_text += sentence
                else:
                    if current_text:
                        # セグメント作成
                        split_seg = SubtitleSegment(
                            segment_id=segment.segment_id,
                            speaker=segment.speaker,
                            text=current_text,
                            start_time=segment.start_time + current_duration,
                            end_time=segment.start_time + current_duration + (len(current_text) / len(text) * segment.duration),
                            duration=len(current_text) / len(text) * segment.duration,
                            word_timestamps=[],
                            emotion=segment.emotion
                        )
                        split_segments.append(split_seg)
                        current_duration += split_seg.duration
                    
                    current_text = sentence
            
            # 残りのテキスト
            if current_text:
                split_seg = SubtitleSegment(
                    segment_id=segment.segment_id,
                    speaker=segment.speaker,
                    text=current_text,
                    start_time=segment.start_time + current_duration,
                    end_time=segment.end_time,
                    duration=segment.end_time - (segment.start_time + current_duration),
                    word_timestamps=[],
                    emotion=segment.emotion
                )
                split_segments.append(split_seg)
            
            return split_segments if split_segments else [segment]
            
        except Exception as e:
            self.logger.error(f"セグメント分割エラー: {e}")
            return [segment]
    
    def _calculate_line_breaks(self, text: str, max_line_length: int) -> List[int]:
        """
        改行位置を計算
        
        Args:
            text: テキスト
            max_line_length: 最大行文字数
            
        Returns:
            改行位置一覧
        """
        try:
            line_breaks = []
            current_pos = 0
            
            while current_pos < len(text):
                if current_pos + max_line_length >= len(text):
                    break
                
                # 理想的な改行位置
                ideal_break = current_pos + max_line_length
                
                # 句読点や空白での改行を優先
                best_break = ideal_break
                for i in range(ideal_break, current_pos + max_line_length // 2, -1):
                    if i < len(text) and text[i] in "。！？.,、 ":
                        best_break = i + 1
                        break
                
                line_breaks.append(best_break)
                current_pos = best_break
            
            return line_breaks
            
        except Exception as e:
            self.logger.error(f"改行位置計算エラー: {e}")
            return []
    
    def _apply_subtitle_styles(self, segments: List[SubtitleSegment]) -> List[AssSubtitle]:
        """
        字幕スタイルを適用
        
        Args:
            segments: 字幕セグメント一覧
            
        Returns:
            スタイル適用済み字幕一覧
        """
        try:
            styled_subtitles = []
            speaker_styles = self.subtitle_settings.get("speaker_styles", {})
            default_style = self.subtitle_settings.get("default_style", {})
            
            for segment in segments:
                # 話者に対応するスタイルを取得
                speaker = segment.speaker
                style_config = speaker_styles.get(speaker, default_style.copy())
                
                # スタイル名を設定
                style_name = speaker if speaker in speaker_styles else "default"
                segment.style_name = style_name
                
                # スタイルオブジェクト作成
                style = SubtitleStyle(
                    style_name=style_name,
                    **style_config
                )
                
                # ASS字幕作成
                ass_subtitle = AssSubtitle(
                    segment=segment,
                    style=style,
                    style_name=style_name
                )
                
                styled_subtitles.append(ass_subtitle)
            
            self.logger.info(f"スタイル適用完了: {len(styled_subtitles)}字幕")
            return styled_subtitles
            
        except Exception as e:
            self.logger.error(f"スタイル適用エラー: {e}")
            raise
    
    def _generate_ass_file(
        self, 
        project_id: str, 
        styled_subtitles: List[AssSubtitle],
        audio_metadata: Dict[str, Any]
    ) -> str:
        """
        ASSファイルを生成
        
        Args:
            project_id: プロジェクトID
            styled_subtitles: スタイル適用済み字幕一覧
            audio_metadata: 音声メタデータ
            
        Returns:
            ASSファイルパス
        """
        try:
            # ファイルパス決定
            project_dir = Path(self.file_system_manager.get_project_directory(project_id))
            subtitle_dir = project_dir / "files" / "subtitles"
            subtitle_dir.mkdir(parents=True, exist_ok=True)
            
            ass_file_path = subtitle_dir / f"subtitle_{project_id}.ass"
            
            # ASS内容生成
            ass_content = self._generate_ass_content(styled_subtitles, audio_metadata)
            
            # ファイル書き込み
            with open(ass_file_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            # メタデータ保存
            file_size = ass_file_path.stat().st_size
            checksum = self._calculate_file_checksum(str(ass_file_path))
            
            self.dao.save_ass_subtitle_file(
                project_id=project_id,
                file_path=str(ass_file_path),
                file_content=ass_content,
                total_segments=len(styled_subtitles),
                total_duration=audio_metadata.get("total_duration", 0.0),
                file_size=file_size,
                checksum=checksum
            )
            
            self.logger.info(f"ASSファイル生成完了: {ass_file_path}")
            return str(ass_file_path)
            
        except Exception as e:
            self.logger.error(f"ASSファイル生成エラー: {e}")
            raise
    
    def _generate_ass_content(
        self, 
        styled_subtitles: List[AssSubtitle], 
        audio_metadata: Dict[str, Any]
    ) -> str:
        """
        ASS内容を生成
        
        Args:
            styled_subtitles: スタイル適用済み字幕一覧
            audio_metadata: 音声メタデータ
            
        Returns:
            ASS形式文字列
        """
        try:
            lines = []
            
            # ヘッダー情報
            lines.append("[Script Info]")
            lines.append("Title: Auto Generated Yukkuri Subtitle")
            lines.append("ScriptType: v4.00+")
            lines.append(f"Collisions: Normal")
            lines.append(f"PlayDepth: 0")
            lines.append(f"Timer: 100.0000")
            lines.append(f"Video File: ")
            lines.append(f"Video AR Value: 1.777778")
            lines.append(f"Video Zoom Percent: 1.000000")
            lines.append("")
            
            # スタイル定義
            lines.append("[V4+ Styles]")
            lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
            
            # ユニークなスタイル一覧
            unique_styles = {}
            for subtitle in styled_subtitles:
                style_name = subtitle.style_name
                if style_name not in unique_styles:
                    unique_styles[style_name] = subtitle.style
            
            for style_name, style in unique_styles.items():
                style_line = self._format_ass_style(style)
                lines.append(style_line)
            
            lines.append("")
            
            # イベント（字幕）
            lines.append("[Events]")
            lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
            
            for subtitle in styled_subtitles:
                event_line = self._format_ass_event(subtitle)
                lines.append(event_line)
            
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"ASS内容生成エラー: {e}")
            raise
    
    def _format_ass_style(self, style: SubtitleStyle) -> str:
        """
        ASSスタイル行をフォーマット
        
        Args:
            style: 字幕スタイル
            
        Returns:
            ASSスタイル行
        """
        return f"Style: {style.style_name},{style.font_name},{style.font_size},{style.primary_color},{style.secondary_color},{style.outline_color},{style.back_color},{1 if style.bold else 0},{1 if style.italic else 0},{1 if style.underline else 0},0,100,100,0,0,1,{style.outline},{style.shadow},{style.alignment},{style.margin_left},{style.margin_right},{style.margin_vertical},1"
    
    def _format_ass_event(self, subtitle: AssSubtitle) -> str:
        """
        ASSイベント行をフォーマット
        
        Args:
            subtitle: ASS字幕
            
        Returns:
            ASSイベント行
        """
        start_time = self._format_ass_time(subtitle.segment.start_time)
        end_time = self._format_ass_time(subtitle.segment.end_time)
        
        # 改行処理
        text = subtitle.segment.text
        if subtitle.segment.line_breaks:
            for break_pos in reversed(subtitle.segment.line_breaks):
                if break_pos < len(text):
                    text = text[:break_pos] + "\\N" + text[break_pos:]
        
        return f"Dialogue: 0,{start_time},{end_time},{subtitle.style_name},,0,0,0,,{text}"
    
    def _format_ass_time(self, seconds: float) -> str:
        """
        時間をASS形式でフォーマット
        
        Args:
            seconds: 秒数
            
        Returns:
            ASS時間形式 (H:MM:SS.CC)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """
        ファイルのチェックサムを計算
        
        Args:
            file_path: ファイルパス
            
        Returns:
            チェックサム
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            self.logger.error(f"チェックサム計算エラー: {e}")
            return ""
    
    def _generate_ass_subtitle(
        self, 
        script_data: Dict[str, Any], 
        audio_metadata: Dict[str, Any], 
        output_path: str
    ) -> str:
        """
        ASS字幕を生成（テスト用メソッド）
        
        Args:
            script_data: スクリプトデータ
            audio_metadata: 音声メタデータ
            output_path: 出力パス
            
        Returns:
            生成されたASS内容
        """
        try:
            # 字幕セグメント生成
            subtitle_segments = self._generate_subtitle_timing(script_data, audio_metadata)
            
            # 読みやすさ最適化
            optimized_segments = self._optimize_readability(subtitle_segments)
            
            # スタイル適用
            styled_subtitles = self._apply_subtitle_styles(optimized_segments)
            
            # ASS内容生成
            ass_content = self._generate_ass_content(styled_subtitles, audio_metadata)
            
            # ファイル書き込み
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            return ass_content
            
        except Exception as e:
            self.logger.error(f"ASS字幕生成エラー: {e}")
            raise 