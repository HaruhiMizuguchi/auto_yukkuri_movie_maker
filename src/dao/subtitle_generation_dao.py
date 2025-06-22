"""
字幕生成DAO

字幕生成に関するデータベース操作を集約：
- スクリプトデータ取得
- 音声メタデータ取得  
- 字幕セグメント保存・取得
- 字幕スタイル管理
- ASS字幕ファイル管理
"""

import sqlite3
import json
from typing import Dict, Any, List, Optional
from dataclasses import asdict
import logging
from datetime import datetime

from ..core.database_manager import DatabaseManager


class SubtitleGenerationDAO:
    """字幕生成データアクセスオブジェクト"""
    
    def __init__(self, db_manager: DatabaseManager, logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            db_manager: データベースマネージャー
            logger: ロガー
        """
        self.db_manager = db_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # 字幕生成用テーブルを初期化
        self._initialize_tables()
    
    def _initialize_tables(self) -> None:
        """字幕生成用テーブルを初期化"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # 字幕セグメントテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subtitle_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    segment_id INTEGER NOT NULL,
                    speaker TEXT NOT NULL,
                    text TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    duration REAL NOT NULL,
                    word_timestamps TEXT,  -- JSON形式
                    emotion TEXT DEFAULT 'neutral',
                    style_name TEXT,
                    line_breaks TEXT,  -- 改行位置の情報
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, segment_id)
                )
            """)
            
            # 字幕スタイルテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subtitle_styles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    style_name TEXT NOT NULL,
                    font_name TEXT NOT NULL,
                    font_size INTEGER NOT NULL,
                    primary_color TEXT NOT NULL,
                    secondary_color TEXT,
                    outline_color TEXT,
                    back_color TEXT,
                    bold BOOLEAN DEFAULT FALSE,
                    italic BOOLEAN DEFAULT FALSE,
                    underline BOOLEAN DEFAULT FALSE,
                    outline INTEGER DEFAULT 2,
                    shadow INTEGER DEFAULT 0,
                    alignment INTEGER DEFAULT 2,
                    margin_left INTEGER DEFAULT 10,
                    margin_right INTEGER DEFAULT 10,
                    margin_vertical INTEGER DEFAULT 20,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, style_name)
                )
            """)
            
            # ASS字幕ファイルテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ass_subtitle_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_content TEXT NOT NULL,  -- ASS形式の全内容
                    total_segments INTEGER NOT NULL,
                    total_duration REAL NOT NULL,
                    file_size INTEGER,
                    checksum TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id)
                )
            """)
            
            conn.commit()
            self.logger.info("字幕生成用テーブル初期化完了")
            
        except sqlite3.Error as e:
            self.logger.error(f"字幕生成用テーブル初期化エラー: {e}")
            raise
    
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """
        スクリプトデータを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            スクリプトデータ辞書
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # スクリプト生成ステップの結果を取得
            cursor.execute("""
                SELECT output_summary_json
                FROM workflow_steps
                WHERE project_id = ? AND step_name = 'script_generation'
                ORDER BY completed_at DESC
                LIMIT 1
            """, (project_id,))
            
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"スクリプトデータが見つかりません: project_id={project_id}")
            
            script_data = json.loads(result[0])
            self.logger.info(f"スクリプトデータ取得成功: project_id={project_id}, segments={len(script_data.get('segments', []))}")
            
            return script_data
            
        except sqlite3.Error as e:
            self.logger.error(f"スクリプトデータ取得エラー: {e}")
            raise
    
    def get_audio_metadata(self, project_id: str) -> Dict[str, Any]:
        """
        音声メタデータを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            音声メタデータ辞書
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # TTS生成ステップの結果を取得
            cursor.execute("""
                SELECT output_summary_json
                FROM workflow_steps
                WHERE project_id = ? AND step_name = 'tts_generation'
                ORDER BY completed_at DESC
                LIMIT 1
            """, (project_id,))
            
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"音声メタデータが見つかりません: project_id={project_id}")
            
            audio_data = json.loads(result[0])
            self.logger.info(f"音声メタデータ取得成功: project_id={project_id}, duration={audio_data.get('total_duration', 0)}")
            
            return audio_data
            
        except sqlite3.Error as e:
            self.logger.error(f"音声メタデータ取得エラー: {e}")
            raise
    
    def save_subtitle_segment(
        self, 
        project_id: str,
        segment_id: int,
        speaker: str,
        text: str,
        start_time: float,
        end_time: float,
        duration: float,
        word_timestamps: List[Dict[str, Any]],
        emotion: str = "neutral",
        style_name: Optional[str] = None,
        line_breaks: Optional[List[int]] = None
    ) -> None:
        """
        字幕セグメントを保存
        
        Args:
            project_id: プロジェクトID
            segment_id: セグメントID
            speaker: 話者
            text: テキスト
            start_time: 開始時間
            end_time: 終了時間
            duration: 継続時間
            word_timestamps: 単語タイムスタンプ
            emotion: 感情
            style_name: スタイル名
            line_breaks: 改行位置
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO subtitle_segments (
                    project_id, segment_id, speaker, text, start_time, end_time, duration,
                    word_timestamps, emotion, style_name, line_breaks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, segment_id, speaker, text, start_time, end_time, duration,
                json.dumps(word_timestamps, ensure_ascii=False),
                emotion, style_name,
                json.dumps(line_breaks) if line_breaks else None
            ))
            
            conn.commit()
            self.logger.debug(f"字幕セグメント保存: segment_id={segment_id}, speaker={speaker}")
            
        except sqlite3.Error as e:
            self.logger.error(f"字幕セグメント保存エラー: {e}")
            raise
    
    def get_subtitle_segments(self, project_id: str) -> List[Dict[str, Any]]:
        """
        字幕セグメント一覧を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            字幕セグメント一覧
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT segment_id, speaker, text, start_time, end_time, duration,
                       word_timestamps, emotion, style_name, line_breaks
                FROM subtitle_segments
                WHERE project_id = ?
                ORDER BY segment_id
            """, (project_id,))
            
            segments = []
            for row in cursor.fetchall():
                segment = {
                    "segment_id": row[0],
                    "speaker": row[1], 
                    "text": row[2],
                    "start_time": row[3],
                    "end_time": row[4],
                    "duration": row[5],
                    "word_timestamps": json.loads(row[6]) if row[6] else [],
                    "emotion": row[7],
                    "style_name": row[8],
                    "line_breaks": json.loads(row[9]) if row[9] else None
                }
                segments.append(segment)
            
            self.logger.info(f"字幕セグメント取得: project_id={project_id}, count={len(segments)}")
            return segments
            
        except sqlite3.Error as e:
            self.logger.error(f"字幕セグメント取得エラー: {e}")
            raise
    
    def save_subtitle_style(
        self,
        project_id: str,
        style_name: str,
        style_config: Dict[str, Any]
    ) -> None:
        """
        字幕スタイルを保存
        
        Args:
            project_id: プロジェクトID
            style_name: スタイル名
            style_config: スタイル設定
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO subtitle_styles (
                    project_id, style_name, font_name, font_size, primary_color,
                    secondary_color, outline_color, back_color, bold, italic, underline,
                    outline, shadow, alignment, margin_left, margin_right, margin_vertical
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, style_name, 
                style_config.get("font_name", "Arial"),
                style_config.get("font_size", 24),
                style_config.get("primary_color", "&H00FFFFFF"),
                style_config.get("secondary_color", "&H000000FF"),
                style_config.get("outline_color", "&H00000000"),
                style_config.get("back_color", "&H80000000"),
                style_config.get("bold", False),
                style_config.get("italic", False),
                style_config.get("underline", False),
                style_config.get("outline", 2),
                style_config.get("shadow", 0),
                style_config.get("alignment", 2),
                style_config.get("margin_left", 10),
                style_config.get("margin_right", 10),
                style_config.get("margin_vertical", 20)
            ))
            
            conn.commit()
            self.logger.debug(f"字幕スタイル保存: style_name={style_name}")
            
        except sqlite3.Error as e:
            self.logger.error(f"字幕スタイル保存エラー: {e}")
            raise
    
    def get_subtitle_styles(self, project_id: str) -> Dict[str, Dict[str, Any]]:
        """
        字幕スタイル一覧を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            字幕スタイル辞書
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT style_name, font_name, font_size, primary_color, secondary_color,
                       outline_color, back_color, bold, italic, underline, outline, shadow,
                       alignment, margin_left, margin_right, margin_vertical
                FROM subtitle_styles
                WHERE project_id = ?
            """, (project_id,))
            
            styles = {}
            for row in cursor.fetchall():
                style_name = row[0]
                styles[style_name] = {
                    "font_name": row[1],
                    "font_size": row[2],
                    "primary_color": row[3],
                    "secondary_color": row[4],
                    "outline_color": row[5],
                    "back_color": row[6],
                    "bold": bool(row[7]),
                    "italic": bool(row[8]),
                    "underline": bool(row[9]),
                    "outline": row[10],
                    "shadow": row[11],
                    "alignment": row[12],
                    "margin_left": row[13],
                    "margin_right": row[14],
                    "margin_vertical": row[15]
                }
            
            self.logger.info(f"字幕スタイル取得: project_id={project_id}, count={len(styles)}")
            return styles
            
        except sqlite3.Error as e:
            self.logger.error(f"字幕スタイル取得エラー: {e}")
            raise
    
    def save_ass_subtitle_file(
        self,
        project_id: str,
        file_path: str,
        file_content: str,
        total_segments: int,
        total_duration: float,
        file_size: Optional[int] = None,
        checksum: Optional[str] = None
    ) -> None:
        """
        ASS字幕ファイル情報を保存
        
        Args:
            project_id: プロジェクトID
            file_path: ファイルパス
            file_content: ファイル内容
            total_segments: 総セグメント数
            total_duration: 総時間
            file_size: ファイルサイズ
            checksum: チェックサム
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO ass_subtitle_files (
                    project_id, file_path, file_content, total_segments, total_duration,
                    file_size, checksum
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, file_path, file_content, total_segments, total_duration,
                file_size, checksum
            ))
            
            conn.commit()
            self.logger.info(f"ASS字幕ファイル保存: project_id={project_id}, path={file_path}")
            
        except sqlite3.Error as e:
            self.logger.error(f"ASS字幕ファイル保存エラー: {e}")
            raise
    
    def get_ass_subtitle_file(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        ASS字幕ファイル情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            ASS字幕ファイル情報
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT file_path, file_content, total_segments, total_duration, 
                       file_size, checksum, created_at
                FROM ass_subtitle_files
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (project_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            file_info = {
                "file_path": result[0],
                "file_content": result[1],
                "total_segments": result[2],
                "total_duration": result[3],
                "file_size": result[4],
                "checksum": result[5],
                "created_at": result[6]
            }
            
            self.logger.info(f"ASS字幕ファイル取得: project_id={project_id}")
            return file_info
            
        except sqlite3.Error as e:
            self.logger.error(f"ASS字幕ファイル取得エラー: {e}")
            raise
    
    def save_subtitle_result(
        self,
        project_id: str,
        subtitle_segments: List[Dict[str, Any]],
        ass_file_path: str,
        total_duration: float,
        generation_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        字幕生成結果を保存
        
        Args:
            project_id: プロジェクトID
            subtitle_segments: 字幕セグメント一覧
            ass_file_path: ASSファイルパス
            total_duration: 総時間
            generation_metadata: 生成メタデータ
        """
        try:
            # 各セグメントを保存
            for segment in subtitle_segments:
                self.save_subtitle_segment(
                    project_id=project_id,
                    segment_id=segment["segment_id"],
                    speaker=segment["speaker"],
                    text=segment["text"],
                    start_time=segment["start_time"],
                    end_time=segment["end_time"],
                    duration=segment["duration"],
                    word_timestamps=segment.get("word_timestamps", []),
                    emotion=segment.get("emotion", "neutral"),
                    style_name=segment.get("style_name"),
                    line_breaks=segment.get("line_breaks")
                )
            
            # ワークフローステップに結果を記録
            summary_data = {
                "segments_count": len(subtitle_segments),
                "ass_file_path": ass_file_path,
                "total_duration": total_duration,
                "generation_metadata": generation_metadata or {}
            }
            
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO workflow_steps (
                    project_id, step_name, step_number, display_name, status,
                    output_summary_json, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, "subtitle_generation", 8, "字幕生成", "completed",
                json.dumps(summary_data, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            self.logger.info(f"字幕生成結果保存完了: project_id={project_id}")
            
        except sqlite3.Error as e:
            self.logger.error(f"字幕生成結果保存エラー: {e}")
            raise
    
    def cleanup_subtitle_data(self, project_id: str) -> None:
        """
        字幕データをクリーンアップ
        
        Args:
            project_id: プロジェクトID
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # 関連データを削除
            cursor.execute("DELETE FROM subtitle_segments WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM subtitle_styles WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM ass_subtitle_files WHERE project_id = ?", (project_id,))
            
            conn.commit()
            self.logger.info(f"字幕データクリーンアップ完了: project_id={project_id}")
            
        except sqlite3.Error as e:
            self.logger.error(f"字幕データクリーンアップエラー: {e}")
            raise 