"""
音響効果モジュール用データアクセスオブジェクト

Classes:
    AudioEnhancementDAO: 音響効果処理結果のデータベース操作
"""

import json
import sqlite3
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from ..core.database_manager import DatabaseManager
from ..core.file_system_manager import FileSystemManager


class AudioEnhancementDAO:
    """
    音響効果処理結果のデータベース操作クラス
    
    音響効果の処理結果、効果音配置、BGM情報、音響レベル調整結果を
    データベースに保存・取得する機能を提供します。
    """
    
    def __init__(self, database_manager: DatabaseManager, file_system_manager: FileSystemManager):
        """
        初期化
        
        Args:
            database_manager: データベース管理オブジェクト
            file_system_manager: ファイルシステム管理オブジェクト
        """
        self.database_manager = database_manager
        self.file_system_manager = file_system_manager
        self.logger = logging.getLogger(__name__)
        
        # テーブル作成
        self._create_tables()
    
    def _create_tables(self) -> None:
        """音響効果関連テーブルの作成"""
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 音響効果処理メインテーブル
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audio_enhancements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        input_video_path TEXT NOT NULL,
                        enhanced_video_path TEXT,
                        theme TEXT,
                        mood TEXT,
                        processing_duration REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 効果音配置テーブル
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sound_effects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        effect_type TEXT NOT NULL,
                        file_path TEXT,
                        volume REAL DEFAULT 1.0,
                        fade_in REAL DEFAULT 0.0,
                        fade_out REAL DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # BGM情報テーブル
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS background_music (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        genre TEXT,
                        volume REAL DEFAULT 0.3,
                        fade_in REAL DEFAULT 2.0,
                        fade_out REAL DEFAULT 2.0,
                        start_time REAL DEFAULT 0.0,
                        duration REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 音響レベル調整テーブル
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audio_levels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        track_type TEXT NOT NULL, -- 'voice', 'bgm', 'sfx'
                        original_lufs REAL,
                        target_lufs REAL,
                        adjustment_db REAL,
                        final_lufs REAL,
                        peak_db REAL,
                        rms_db REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # インデックス作成
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_enhancements_project_id ON audio_enhancements (project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sound_effects_project_id ON sound_effects (project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_background_music_project_id ON background_music (project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_levels_project_id ON audio_levels (project_id)')
                
                conn.commit()
                self.logger.info("音響効果関連テーブルを作成しました")
                
        except Exception as e:
            self.logger.error(f"テーブル作成エラー: {e}")
            raise
    
    def save_enhancement_result(self, result: Dict[str, Any]) -> int:
        """
        音響効果処理結果を保存
        
        Args:
            result: 音響効果処理結果
                - project_id: プロジェクトID
                - input_video_path: 入力動画パス
                - enhanced_video_path: 強化済み動画パス
                - theme: テーマ
                - mood: ムード
                - processing_duration: 処理時間
                - sound_effects: 効果音リスト
                - background_music: BGM情報
                - audio_levels: 音響レベル情報
        
        Returns:
            int: 作成されたレコードのID
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # メイン処理結果保存
                cursor.execute('''
                    INSERT INTO audio_enhancements 
                    (project_id, input_video_path, enhanced_video_path, theme, mood, processing_duration)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    result["project_id"],
                    result["input_video_path"],
                    result.get("enhanced_video_path"),
                    result.get("theme"),
                    result.get("mood"),
                    result.get("processing_duration")
                ))
                
                enhancement_id = cursor.lastrowid
                project_id = result["project_id"]
                
                # 効果音情報保存
                if "sound_effects" in result:
                    for effect in result["sound_effects"]:
                        cursor.execute('''
                            INSERT INTO sound_effects 
                            (project_id, timestamp, effect_type, file_path, volume, fade_in, fade_out)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            project_id,
                            effect["timestamp"],
                            effect["effect_type"],
                            effect.get("file_path"),
                            effect.get("volume", 1.0),
                            effect.get("fade_in", 0.0),
                            effect.get("fade_out", 0.0)
                        ))
                
                # BGM情報保存
                if "background_music" in result:
                    bgm = result["background_music"]
                    cursor.execute('''
                        INSERT INTO background_music 
                        (project_id, file_path, genre, volume, fade_in, fade_out, start_time, duration)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        project_id,
                        bgm.get("file_path"),
                        bgm.get("genre"),
                        bgm.get("volume", 0.3),
                        bgm.get("fade_in", 2.0),
                        bgm.get("fade_out", 2.0),
                        bgm.get("start_time", 0.0),
                        bgm.get("duration")
                    ))
                
                # 音響レベル情報保存
                if "audio_levels" in result:
                    for track_type, levels in result["audio_levels"].items():
                        cursor.execute('''
                            INSERT INTO audio_levels 
                            (project_id, track_type, original_lufs, target_lufs, adjustment_db, final_lufs, peak_db, rms_db)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            project_id,
                            track_type,
                            levels.get("original_lufs"),
                            levels.get("target_lufs"),
                            levels.get("adjustment_db"),
                            levels.get("final_lufs"),
                            levels.get("peak_db"),
                            levels.get("rms_db")
                        ))
                
                conn.commit()
                self.logger.info(f"音響効果処理結果を保存しました: project_id={project_id}")
                return enhancement_id
                
        except Exception as e:
            self.logger.error(f"音響効果処理結果保存エラー: {e}")
            raise
    
    def get_enhancement_result(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        音響効果処理結果を取得
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            Dict[str, Any]: 音響効果処理結果、存在しない場合はNone
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # メイン結果取得
                cursor.execute('''
                    SELECT input_video_path, enhanced_video_path, theme, mood, processing_duration, created_at
                    FROM audio_enhancements
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (project_id,))
                
                main_result = cursor.fetchone()
                if not main_result:
                    return None
                
                result = {
                    "project_id": project_id,
                    "input_video_path": main_result[0],
                    "enhanced_video_path": main_result[1],
                    "theme": main_result[2],
                    "mood": main_result[3],
                    "processing_duration": main_result[4],
                    "created_at": main_result[5]
                }
                
                # 効果音情報取得
                cursor.execute('''
                    SELECT timestamp, effect_type, file_path, volume, fade_in, fade_out
                    FROM sound_effects
                    WHERE project_id = ?
                    ORDER BY timestamp
                ''', (project_id,))
                
                sound_effects = []
                for row in cursor.fetchall():
                    sound_effects.append({
                        "timestamp": row[0],
                        "effect_type": row[1],
                        "file_path": row[2],
                        "volume": row[3],
                        "fade_in": row[4],
                        "fade_out": row[5]
                    })
                result["sound_effects"] = sound_effects
                
                # BGM情報取得
                cursor.execute('''
                    SELECT file_path, genre, volume, fade_in, fade_out, start_time, duration
                    FROM background_music
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (project_id,))
                
                bgm_row = cursor.fetchone()
                if bgm_row:
                    result["background_music"] = {
                        "file_path": bgm_row[0],
                        "genre": bgm_row[1],
                        "volume": bgm_row[2],
                        "fade_in": bgm_row[3],
                        "fade_out": bgm_row[4],
                        "start_time": bgm_row[5],
                        "duration": bgm_row[6]
                    }
                
                # 音響レベル情報取得
                cursor.execute('''
                    SELECT track_type, original_lufs, target_lufs, adjustment_db, final_lufs, peak_db, rms_db
                    FROM audio_levels
                    WHERE project_id = ?
                ''', (project_id,))
                
                audio_levels = {}
                for row in cursor.fetchall():
                    audio_levels[row[0]] = {
                        "original_lufs": row[1],
                        "target_lufs": row[2],
                        "adjustment_db": row[3],
                        "final_lufs": row[4],
                        "peak_db": row[5],
                        "rms_db": row[6]
                    }
                result["audio_levels"] = audio_levels
                
                return result
                
        except Exception as e:
            self.logger.error(f"音響効果処理結果取得エラー: {e}")
            raise
    
    def get_sound_effects_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクトの効果音情報を取得
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            List[Dict[str, Any]]: 効果音情報リスト
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, effect_type, file_path, volume, fade_in, fade_out
                    FROM sound_effects
                    WHERE project_id = ?
                    ORDER BY timestamp
                ''', (project_id,))
                
                effects = []
                for row in cursor.fetchall():
                    effects.append({
                        "timestamp": row[0],
                        "effect_type": row[1],
                        "file_path": row[2],
                        "volume": row[3],
                        "fade_in": row[4],
                        "fade_out": row[5]
                    })
                
                return effects
                
        except Exception as e:
            self.logger.error(f"効果音情報取得エラー: {e}")
            raise
    
    def get_audio_levels_by_project(self, project_id: str) -> Dict[str, Dict[str, Any]]:
        """
        プロジェクトの音響レベル情報を取得
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            Dict[str, Dict[str, Any]]: トラック別音響レベル情報
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT track_type, original_lufs, target_lufs, adjustment_db, final_lufs, peak_db, rms_db
                    FROM audio_levels
                    WHERE project_id = ?
                ''', (project_id,))
                
                levels = {}
                for row in cursor.fetchall():
                    levels[row[0]] = {
                        "original_lufs": row[1],
                        "target_lufs": row[2],
                        "adjustment_db": row[3],
                        "final_lufs": row[4],
                        "peak_db": row[5],
                        "rms_db": row[6]
                    }
                
                return levels
                
        except Exception as e:
            self.logger.error(f"音響レベル情報取得エラー: {e}")
            raise
    
    def update_enhancement_status(self, project_id: str, enhanced_video_path: str) -> None:
        """
        音響効果処理の出力パスを更新
        
        Args:
            project_id: プロジェクトID
            enhanced_video_path: 強化済み動画パス
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE audio_enhancements
                    SET enhanced_video_path = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE project_id = ?
                ''', (enhanced_video_path, project_id))
                
                conn.commit()
                self.logger.info(f"音響効果処理ステータスを更新しました: project_id={project_id}")
                
        except Exception as e:
            self.logger.error(f"音響効果処理ステータス更新エラー: {e}")
            raise 