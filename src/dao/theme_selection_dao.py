"""
テーマ選定DAO - SQL操作を集約

テーマ選定に関するデータベース操作を管理
"""

import sqlite3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import asdict

from ..core.database_manager import DatabaseManager


class ThemeSelectionDAO:
    """テーマ選定のデータアクセスオブジェクト"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def get_project_config(self, project_id: str) -> Dict[str, Any]:
        """プロジェクトの設定を取得"""
        query = """
            SELECT config_json 
            FROM projects 
            WHERE id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        if not result:
            raise ValueError(f"Project not found: {project_id}")
        
        config_json = result[0]
        return json.loads(config_json) if config_json else {}
    
    def update_project_theme(
        self, 
        project_id: str, 
        theme: str, 
        target_length_minutes: float
    ) -> None:
        """プロジェクトのテーマ情報を更新"""
        query = """
            UPDATE projects 
            SET theme = ?, 
                target_length_minutes = ?, 
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        
        affected_rows = self.db_manager.execute_query(query, (theme, target_length_minutes, project_id))
        if affected_rows == 0:
            raise ValueError(f"Project not found: {project_id}")
    
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
        
        # SQLiteでは最後のrowidを取得するために特別な処理が必要
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                query, 
                (project_id, file_type, file_category, file_path, file_name, file_size, metadata_json)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_project_info(self, project_id: str) -> Optional[Dict[str, Any]]:
        """プロジェクト基本情報を取得"""
        query = """
            SELECT id, theme, target_length_minutes, status, config_json, 
                   created_at, updated_at
            FROM projects 
            WHERE id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        if not result:
            return None
        
        row = result
        return {
            "id": row[0],
            "theme": row[1],
            "target_length_minutes": row[2],
            "status": row[3],
            "config": json.loads(row[4]) if row[4] else {},
            "created_at": row[5],
            "updated_at": row[6]
        }
    
    def get_workflow_step_result(
        self, 
        project_id: str, 
        step_name: str
    ) -> Optional[Dict[str, Any]]:
        """ワークフローステップの結果を取得"""
        query = """
            SELECT status, output_data, completed_at
            FROM workflow_steps 
            WHERE project_id = ? AND step_name = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id, step_name))
        if not result:
            return None
        
        row = result
        return {
            "status": row[0],
            "output_data": json.loads(row[1]) if row[1] else {},
            "completed_at": row[2]
        }
    
    def _get_next_step_number(self, project_id: str) -> int:
        """次のステップ番号を取得"""
        query = """
            SELECT COALESCE(MAX(step_number), 0) + 1 
            FROM workflow_steps 
            WHERE project_id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        return result[0] if result else 1 