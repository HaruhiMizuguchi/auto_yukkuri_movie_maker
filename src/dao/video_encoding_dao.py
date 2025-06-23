"""
動画エンコーディングデータアクセスオブジェクト

Classes:
    VideoEncodingDAO: 動画エンコーディング処理のデータベース操作を管理
"""

import json
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..core.database_manager import DatabaseManager
from ..core.file_system_manager import FileSystemManager


class VideoEncodingDAO:
    """
    動画エンコーディングデータアクセスオブジェクト
    
    動画エンコーディング処理のデータベース操作とファイル管理を提供します。
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
        
        # テーブル初期化
        self._initialize_tables()
    
    def _initialize_tables(self) -> None:
        """動画エンコーディング関連テーブルを初期化"""
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 動画エンコーディング設定テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS video_encoding_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    preset_name TEXT NOT NULL,
                    codec TEXT NOT NULL,
                    crf INTEGER,
                    bitrate TEXT,
                    resolution TEXT,
                    fps INTEGER,
                    custom_args TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            # 動画品質チェック結果テーブル
            cursor.execute("""
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
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            # 動画最適化結果テーブル
            cursor.execute("""
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
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            # 動画エンコーディング実行履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS video_encoding_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    input_video_path TEXT NOT NULL,
                    output_video_path TEXT NOT NULL,
                    encoding_settings TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    processing_time REAL,
                    final_quality_score REAL,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            conn.commit()
    
    def save_encoding_settings(self, project_id: str, settings: Dict[str, Any]) -> int:
        """
        エンコーディング設定を保存
        
        Args:
            project_id: プロジェクトID
            settings: エンコーディング設定
            
        Returns:
            int: 設定ID
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO video_encoding_settings 
                (project_id, preset_name, codec, crf, bitrate, resolution, fps, custom_args)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                settings.get("preset", "medium"),
                settings.get("codec", "libx264"),
                settings.get("crf"),
                settings.get("bitrate"),
                settings.get("resolution"),
                settings.get("fps"),
                json.dumps(settings.get("custom_args", {}))
            ))
            
            setting_id = cursor.lastrowid
            conn.commit()
            
            return setting_id
    
    def get_encoding_settings(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        プロジェクトのエンコーディング設定を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Optional[Dict[str, Any]]: エンコーディング設定
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT preset_name, codec, crf, bitrate, resolution, fps, custom_args
                FROM video_encoding_settings
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (project_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "preset": row[0],
                    "codec": row[1],
                    "crf": row[2],
                    "bitrate": row[3],
                    "resolution": row[4],
                    "fps": row[5],
                    "custom_args": json.loads(row[6] or "{}")
                }
            
            return None
    
    def save_quality_check_result(self, project_id: str, quality_result: Dict[str, Any]) -> int:
        """
        品質チェック結果を保存
        
        Args:
            project_id: プロジェクトID
            quality_result: 品質チェック結果
            
        Returns:
            int: 品質チェックID
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            video_info = quality_result.get("video_info", {})
            
            cursor.execute("""
                INSERT INTO video_quality_checks 
                (project_id, video_path, quality_score, video_info, detected_issues, 
                 resolution, duration, file_size, bitrate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                quality_result.get("video_path", ""),
                quality_result.get("quality_score", 0.0),
                json.dumps(video_info),
                json.dumps(quality_result.get("issues", [])),
                video_info.get("resolution", ""),
                video_info.get("duration", 0.0),
                video_info.get("file_size", 0),
                video_info.get("bitrate", "")
            ))
            
            check_id = cursor.lastrowid
            conn.commit()
            
            return check_id
    
    def get_quality_check_results(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクトの品質チェック結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict[str, Any]]: 品質チェック結果リスト
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT video_path, quality_score, video_info, detected_issues, created_at
                FROM video_quality_checks
                WHERE project_id = ?
                ORDER BY created_at DESC
            """, (project_id,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "video_path": row[0],
                    "quality_score": row[1],
                    "video_info": json.loads(row[2] or "{}"),
                    "issues": json.loads(row[3] or "[]"),
                    "created_at": row[4]
                })
            
            return results
    
    def save_optimization_result(self, project_id: str, optimization_result: Dict[str, Any]) -> int:
        """
        最適化結果を保存
        
        Args:
            project_id: プロジェクトID
            optimization_result: 最適化結果
            
        Returns:
            int: 最適化結果ID
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = optimization_result.get("optimization_stats", {})
            
            cursor.execute("""
                INSERT INTO video_optimizations 
                (project_id, input_video_path, output_video_path, optimization_config,
                 before_file_size, after_file_size, compression_ratio, quality_retained, processing_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                optimization_result.get("input_path", ""),
                optimization_result.get("optimized_path", ""),
                json.dumps(optimization_result.get("config", {})),
                stats.get("before_file_size", 0),
                stats.get("after_file_size", 0),
                stats.get("compression_ratio", 0.0),
                stats.get("quality_retained", 0.0),
                stats.get("processing_time", 0.0)
            ))
            
            optimization_id = cursor.lastrowid
            conn.commit()
            
            return optimization_id
    
    def save_encoding_history(self, project_id: str, encoding_result: Dict[str, Any]) -> int:
        """
        エンコーディング実行履歴を保存
        
        Args:
            project_id: プロジェクトID
            encoding_result: エンコーディング結果
            
        Returns:
            int: 履歴ID
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO video_encoding_history 
                (project_id, input_video_path, output_video_path, encoding_settings,
                 success, error_message, processing_time, final_quality_score, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                encoding_result.get("input_path", ""),
                encoding_result.get("output_path", ""),
                json.dumps(encoding_result.get("settings", {})),
                encoding_result.get("success", False),
                encoding_result.get("error_message"),
                encoding_result.get("processing_time", 0.0),
                encoding_result.get("quality_score", 0.0),
                encoding_result.get("retry_count", 0)
            ))
            
            history_id = cursor.lastrowid
            conn.commit()
            
            return history_id
    
    def get_encoding_history(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクトのエンコーディング履歴を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict[str, Any]]: エンコーディング履歴リスト
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT input_video_path, output_video_path, encoding_settings, success,
                       error_message, processing_time, final_quality_score, retry_count, created_at
                FROM video_encoding_history
                WHERE project_id = ?
                ORDER BY created_at DESC
            """, (project_id,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    "input_path": row[0],
                    "output_path": row[1],
                    "settings": json.loads(row[2] or "{}"),
                    "success": bool(row[3]),
                    "error_message": row[4],
                    "processing_time": row[5],
                    "quality_score": row[6],
                    "retry_count": row[7],
                    "created_at": row[8]
                })
            
            return history
    
    def get_input_video_files(self, project_id: str) -> List[Dict[str, Any]]:
        """
        エンコード対象の入力動画ファイルを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict[str, Any]]: 入力動画ファイル情報リスト
        """
        # 前のステップ（illustration_insertion）から最終動画を取得
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT fr.file_path, fr.file_type, fr.file_category, fr.description
                FROM file_references fr
                JOIN workflow_steps ws ON fr.project_id = ws.project_id
                WHERE fr.project_id = ? 
                AND ws.step_name = 'illustration_insertion'
                AND fr.file_type = 'video'
                AND fr.file_category = 'output'
                AND ws.status = 'completed'
                ORDER BY fr.created_at DESC
                LIMIT 1
            """, (project_id,))
            
            files = []
            for row in cursor.fetchall():
                files.append({
                    "file_path": row[0],
                    "file_type": row[1],
                    "file_category": row[2],
                    "description": row[3]
                })
            
            return files
    
    def register_encoded_video_file(self, project_id: str, video_path: str, file_info: Dict[str, Any]) -> int:
        """
        エンコード済み動画ファイルを登録
        
        Args:
            project_id: プロジェクトID
            video_path: 動画ファイルパス
            file_info: ファイル情報
            
        Returns:
            int: ファイル参照ID
        """
        with self.database_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO file_references 
                (project_id, file_path, file_type, file_category, description, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                video_path,
                "video",
                "final",
                file_info.get("description", "エンコード済み最終動画"),
                json.dumps(file_info)
            ))
            
            file_id = cursor.lastrowid
            conn.commit()
            
            return file_id 