"""
背景生成DAO - SQL操作を集約

背景生成に関するデータベース操作を管理
"""

import sqlite3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import asdict

from ..core.database_manager import DatabaseManager


class BackgroundGenerationDAO:
    """背景生成のデータアクセスオブジェクト"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def save_scene_analysis(
        self, 
        project_id: str, 
        scene_id: str,
        scene_data: Dict[str, Any]
    ) -> None:
        """シーン分析結果を保存"""
        query = """
            INSERT OR REPLACE INTO background_scenes 
            (project_id, scene_id, scene_type, description, duration, 
             prompt, style, analysis_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        metadata_json = json.dumps(scene_data.get("metadata", {}))
        
        self.db_manager.execute_query(
            query, 
            (
                project_id,
                scene_id,
                scene_data.get("scene_type", ""),
                scene_data.get("description", ""),
                scene_data.get("duration", 0.0),
                scene_data.get("prompt", ""),
                scene_data.get("style", ""),
                metadata_json
            )
        )
    
    def save_background_image(
        self, 
        project_id: str, 
        scene_id: str,
        image_data: Dict[str, Any]
    ) -> int:
        """背景画像情報を保存"""
        query = """
            INSERT INTO background_images 
            (project_id, scene_id, image_path, resolution, file_size, 
             generation_metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        metadata_json = json.dumps(image_data.get("generation_metadata", {}))
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                query,
                (
                    project_id,
                    scene_id,
                    image_data.get("image_path", ""),
                    image_data.get("resolution", ""),
                    image_data.get("file_size", 0),
                    metadata_json
                )
            )
            conn.commit()
            return cursor.lastrowid
    
    def save_ken_burns_effect(
        self, 
        project_id: str, 
        scene_id: str,
        ken_burns_data: Dict[str, Any]
    ) -> int:
        """Ken Burnsエフェクト情報を保存"""
        query = """
            INSERT INTO ken_burns_effects 
            (project_id, scene_id, duration, zoom_start, zoom_end,
             pan_start_x, pan_start_y, pan_end_x, pan_end_y,
             easing_function, effect_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        metadata_json = json.dumps(ken_burns_data.get("metadata", {}))
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                query,
                (
                    project_id,
                    scene_id,
                    ken_burns_data.get("duration", 0.0),
                    ken_burns_data.get("zoom_start", 1.0),
                    ken_burns_data.get("zoom_end", 1.0),
                    ken_burns_data.get("pan_start_x", 0.0),
                    ken_burns_data.get("pan_start_y", 0.0),
                    ken_burns_data.get("pan_end_x", 0.0),
                    ken_burns_data.get("pan_end_y", 0.0),
                    ken_burns_data.get("easing_function", "linear"),
                    metadata_json
                )
            )
            conn.commit()
            return cursor.lastrowid
    
    def save_background_video(
        self, 
        project_id: str, 
        scene_id: str,
        video_data: Dict[str, Any]
    ) -> int:
        """背景動画情報を保存"""
        query = """
            INSERT INTO background_videos 
            (project_id, scene_id, video_path, duration, resolution,
             fps, file_size, ken_burns_metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        ken_burns_json = json.dumps(video_data.get("ken_burns_metadata", {}))
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                query,
                (
                    project_id,
                    scene_id,
                    video_data.get("video_path", ""),
                    video_data.get("duration", 0.0),
                    video_data.get("resolution", ""),
                    video_data.get("fps", 30),
                    video_data.get("file_size", 0),
                    ken_burns_json
                )
            )
            conn.commit()
            return cursor.lastrowid
    
    def save_workflow_step_result(
        self, 
        project_id: str, 
        step_name: str, 
        output_data: Dict[str, Any],
        status: str = "completed"
    ) -> None:
        """ワークフローステップの結果を保存"""
        # 既存ステップの確認・更新
        check_query = """
            SELECT id FROM workflow_steps 
            WHERE project_id = ? AND step_name = ?
        """
        
        existing = self.db_manager.fetch_one(check_query, (project_id, step_name))
        
        if existing:
            # 更新
            update_query = """
                UPDATE workflow_steps 
                SET status = ?, 
                    completed_at = CURRENT_TIMESTAMP,
                    output_data = ?
                WHERE project_id = ? AND step_name = ?
            """
            self.db_manager.execute_query(
                update_query, 
                (status, json.dumps(output_data), project_id, step_name)
            )
        else:
            # 新規作成
            insert_query = """
                INSERT INTO workflow_steps 
                (project_id, step_number, step_name, status, completed_at, output_data)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """
            # step_numberを取得
            step_number = self._get_next_step_number(project_id)
            self.db_manager.execute_query(
                insert_query, 
                (project_id, step_number, step_name, status, json.dumps(output_data))
            )
    
    def register_file_reference(
        self, 
        project_id: str, 
        file_type: str, 
        file_category: str, 
        file_path: str, 
        file_name: str, 
        file_size: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """ファイル参照を登録"""
        query = """
            INSERT INTO project_files 
            (project_id, file_type, file_category, file_path, file_name, file_size, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        metadata_json = json.dumps(metadata or {})
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                query, 
                (project_id, file_type, file_category, file_path, file_name, file_size, metadata_json)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_script_data(self, project_id: str) -> Optional[Dict[str, Any]]:
        """スクリプトデータを取得"""
        query = """
            SELECT output_data 
            FROM workflow_steps 
            WHERE project_id = ? AND step_name = 'script_generation' AND status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        if not result:
            return None
        
        output_data = json.loads(result[0]) if result[0] else {}
        return output_data.get("script", {})
    
    def get_background_scenes(self, project_id: str) -> List[Dict[str, Any]]:
        """背景シーン一覧を取得"""
        query = """
            SELECT scene_id, scene_type, description, duration, prompt, style, analysis_metadata
            FROM background_scenes 
            WHERE project_id = ?
            ORDER BY scene_id
        """
        
        results = self.db_manager.fetch_all(query, (project_id,))
        scenes = []
        
        for row in results:
            scenes.append({
                "scene_id": row[0],
                "scene_type": row[1],
                "description": row[2],
                "duration": row[3],
                "prompt": row[4],
                "style": row[5],
                "metadata": json.loads(row[6]) if row[6] else {}
            })
        
        return scenes
    
    def get_background_images(self, project_id: str) -> List[Dict[str, Any]]:
        """背景画像一覧を取得"""
        query = """
            SELECT scene_id, image_path, resolution, file_size, generation_metadata, created_at
            FROM background_images 
            WHERE project_id = ?
            ORDER BY created_at
        """
        
        results = self.db_manager.fetch_all(query, (project_id,))
        images = []
        
        for row in results:
            images.append({
                "scene_id": row[0],
                "image_path": row[1],
                "resolution": row[2],
                "file_size": row[3],
                "generation_metadata": json.loads(row[4]) if row[4] else {},
                "created_at": row[5]
            })
        
        return images
    
    def get_background_videos(self, project_id: str) -> List[Dict[str, Any]]:
        """背景動画一覧を取得"""
        query = """
            SELECT scene_id, video_path, duration, resolution, fps, file_size, 
                   ken_burns_metadata, created_at
            FROM background_videos 
            WHERE project_id = ?
            ORDER BY created_at
        """
        
        results = self.db_manager.fetch_all(query, (project_id,))
        videos = []
        
        for row in results:
            videos.append({
                "scene_id": row[0],
                "video_path": row[1],
                "duration": row[2],
                "resolution": row[3],
                "fps": row[4],
                "file_size": row[5],
                "ken_burns_metadata": json.loads(row[6]) if row[6] else {},
                "created_at": row[7]
            })
        
        return videos
    
    def cleanup_background_data(self, project_id: str) -> None:
        """背景生成データをクリーンアップ"""
        tables = [
            "background_scenes",
            "background_images",
            "ken_burns_effects",
            "background_videos"
        ]
        
        for table in tables:
            query = f"DELETE FROM {table} WHERE project_id = ?"
            self.db_manager.execute_query(query, (project_id,))
    
    def _get_next_step_number(self, project_id: str) -> int:
        """次のステップ番号を取得"""
        query = """
            SELECT COALESCE(MAX(step_number), 0) + 1 
            FROM workflow_steps 
            WHERE project_id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        return result[0] if result else 1 