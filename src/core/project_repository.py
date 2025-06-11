"""
ProjectRepository - プロジェクトデータアクセス管理

プロジェクト作成・取得・更新、ワークフローステップ管理、
ファイル参照の登録・取得を担当するリポジトリクラス
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path

from .database_manager import DatabaseManager


class ProjectDataAccessError(Exception):
    """プロジェクトデータアクセス関連のエラー"""
    pass


class ProjectRepository:
    """
    プロジェクトデータアクセス管理クラス
    
    プロジェクト、ワークフローステップ、ファイル参照の
    データベース操作を管理する
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        ProjectRepository初期化
        
        Args:
            db_manager: DatabaseManager インスタンス
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    # プロジェクト基本操作
    
    def create_project(
        self,
        project_id: str,
        theme: str,
        target_length_minutes: float = 5.0,
        config: Optional[Dict[str, Any]] = None,
        status: str = "created"
    ) -> bool:
        """
        新しいプロジェクトを作成
        
        Args:
            project_id: プロジェクトID
            theme: 動画テーマ
            target_length_minutes: 目標動画時間（分）
            config: プロジェクト設定
            status: 初期ステータス
            
        Returns:
            bool: 作成成功時True
            
        Raises:
            ProjectDataAccessError: 作成失敗時
        """
        try:
            config_json = json.dumps(config or {})
            
            with self.db_manager.transaction() as conn:
                # 重複チェック
                existing = conn.execute(
                    "SELECT id FROM projects WHERE id = ?",
                    (project_id,)
                ).fetchone()
                
                if existing:
                    raise ProjectDataAccessError(
                        f"Project with id '{project_id}' already exists"
                    )
                
                # プロジェクト作成
                conn.execute("""
                    INSERT INTO projects (
                        id, theme, target_length_minutes, status, 
                        config_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (project_id, theme, target_length_minutes, status, config_json))
                
                self.logger.info(f"Project created: {project_id}")
                return True
                
        except Exception as e:
            error_msg = f"Failed to create project {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        プロジェクト情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Dict: プロジェクト情報、存在しない場合None
            
        Raises:
            ProjectDataAccessError: 取得失敗時
        """
        try:
            with self.db_manager.get_connection() as conn:
                row = conn.execute("""
                    SELECT id, theme, target_length_minutes, status,
                           config_json, output_summary_json,
                           created_at, updated_at
                    FROM projects WHERE id = ?
                """, (project_id,)).fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row["id"],
                    "theme": row["theme"],
                    "target_length_minutes": row["target_length_minutes"],
                    "status": row["status"],
                    "config": json.loads(row["config_json"]),
                    "output_summary": json.loads(row["output_summary_json"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                
        except Exception as e:
            error_msg = f"Database error retrieving project {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def update_project(self, project_id: str, **updates) -> bool:
        """
        プロジェクト情報を更新
        
        Args:
            project_id: プロジェクトID
            **updates: 更新する項目
            
        Returns:
            bool: 更新成功時True
            
        Raises:
            ProjectDataAccessError: 更新失敗時
        """
        try:
            # 有効なフィールドのみを抽出
            valid_fields = {
                "theme", "target_length_minutes", "status",
                "config", "output_summary"
            }
            
            update_fields = []
            params = []
            
            for key, value in updates.items():
                if key in valid_fields:
                    if key in ["config", "output_summary"]:
                        # JSON形式で保存
                        update_fields.append(f"{key}_json = ?")
                        params.append(json.dumps(value))
                    else:
                        update_fields.append(f"{key} = ?")
                        params.append(value)
            
            if not update_fields:
                return True  # 更新項目なし
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(project_id)
            
            with self.db_manager.transaction() as conn:
                # 存在チェック
                existing = conn.execute(
                    "SELECT id FROM projects WHERE id = ?",
                    (project_id,)
                ).fetchone()
                
                if not existing:
                    raise ProjectDataAccessError(
                        f"Project '{project_id}' not found"
                    )
                
                # 更新実行
                query = f"""
                    UPDATE projects 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """
                
                conn.execute(query, params)
                self.logger.info(f"Project updated: {project_id}")
                return True
                
        except Exception as e:
            error_msg = f"Failed to update project {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def delete_project(self, project_id: str) -> bool:
        """
        プロジェクトを削除（カスケード削除）
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: 削除成功時True
            
        Raises:
            ProjectDataAccessError: 削除失敗時
        """
        try:
            with self.db_manager.transaction() as conn:
                # 外部キー制約により関連データも削除される
                result = conn.execute(
                    "DELETE FROM projects WHERE id = ?",
                    (project_id,)
                )
                
                if result.rowcount == 0:
                    self.logger.warning(f"Project {project_id} not found for deletion")
                    return False
                
                self.logger.info(f"Project deleted: {project_id}")
                return True
                
        except Exception as e:
            error_msg = f"Failed to delete project {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    # ワークフローステップ管理
    
    def create_workflow_step(
        self,
        project_id: str,
        step_number: int,
        step_name: str,
        status: str = "pending",
        input_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        ワークフローステップを作成
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            step_name: ステップ名
            status: ステータス
            input_data: 入力データ
            
        Returns:
            bool: 作成成功時True
            
        Raises:
            ProjectDataAccessError: 作成失敗時
        """
        try:
            # 入力データの検証
            if input_data is not None and not isinstance(input_data, dict):
                raise ProjectDataAccessError("Invalid data format: input_data must be a dictionary")
            
            input_json = json.dumps(input_data or {})
            
            with self.db_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO workflow_steps (
                        project_id, step_number, step_name, status, input_data
                    ) VALUES (?, ?, ?, ?, ?)
                """, (project_id, step_number, step_name, status, input_json))
                
                self.logger.info(f"Workflow step created: {project_id} - {step_name}")
                return True
                
        except Exception as e:
            error_msg = f"Failed to create workflow step {step_name}: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def get_workflow_step(
        self, 
        project_id: str, 
        step_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        ワークフローステップ情報を取得
        
        Args:
            project_id: プロジェクトID
            step_name: ステップ名
            
        Returns:
            Dict: ステップ情報、存在しない場合None
            
        Raises:
            ProjectDataAccessError: 取得失敗時
        """
        try:
            with self.db_manager.get_connection() as conn:
                row = conn.execute("""
                    SELECT id, project_id, step_number, step_name, status,
                           started_at, completed_at, input_data, output_data,
                           error_message, retry_count
                    FROM workflow_steps 
                    WHERE project_id = ? AND step_name = ?
                """, (project_id, step_name)).fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row["id"],
                    "project_id": row["project_id"],
                    "step_number": row["step_number"],
                    "step_name": row["step_name"],
                    "status": row["status"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "input_data": row["input_data"],
                    "output_data": row["output_data"],
                    "error_message": row["error_message"],
                    "retry_count": row["retry_count"]
                }
                
        except Exception as e:
            error_msg = f"Database error retrieving workflow step: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def update_workflow_step_status(
        self,
        project_id: str,
        step_name: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        ワークフローステップのステータスを更新
        
        Args:
            project_id: プロジェクトID
            step_name: ステップ名
            status: 新しいステータス
            error_message: エラーメッセージ（失敗時）
            
        Returns:
            bool: 更新成功時True
            
        Raises:
            ProjectDataAccessError: 更新失敗時
        """
        try:
            with self.db_manager.transaction() as conn:
                # タイムスタンプ更新の設定
                timestamp_update = ""
                params = [status]
                
                if status == "running":
                    timestamp_update = ", started_at = CURRENT_TIMESTAMP"
                elif status in ["completed", "failed", "skipped"]:
                    timestamp_update = ", completed_at = CURRENT_TIMESTAMP"
                
                if error_message:
                    timestamp_update += ", error_message = ?"
                    params.append(error_message)
                
                params.extend([project_id, step_name])
                
                conn.execute(f"""
                    UPDATE workflow_steps 
                    SET status = ?{timestamp_update}
                    WHERE project_id = ? AND step_name = ?
                """, params)
                
                self.logger.info(f"Workflow step status updated: {project_id} - {step_name} -> {status}")
                return True
                
        except Exception as e:
            error_msg = f"Failed to update workflow step status: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def save_step_result(
        self,
        project_id: str,
        step_name: str,
        output_data: Dict[str, Any],
        status: str = "completed"
    ) -> bool:
        """
        ステップ実行結果を保存
        
        Args:
            project_id: プロジェクトID
            step_name: ステップ名
            output_data: 出力データ
            status: 最終ステータス
            
        Returns:
            bool: 保存成功時True
            
        Raises:
            ProjectDataAccessError: 保存失敗時
        """
        try:
            output_json = json.dumps(output_data)
            
            with self.db_manager.transaction() as conn:
                conn.execute("""
                    UPDATE workflow_steps 
                    SET status = ?, output_data = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE project_id = ? AND step_name = ?
                """, (status, output_json, project_id, step_name))
                
                self.logger.info(f"Step result saved: {project_id} - {step_name}")
                return True
                
        except Exception as e:
            error_msg = f"Failed to save step result: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def get_step_input(self, project_id: str, step_name: str) -> Optional[Dict[str, Any]]:
        """
        前のステップの出力を現在のステップの入力として取得
        
        Args:
            project_id: プロジェクトID
            step_name: 現在のステップ名
            
        Returns:
            Dict: 前ステップの出力データ、存在しない場合None
            
        Raises:
            ProjectDataAccessError: 取得失敗時
        """
        try:
            # ステップ名と番号のマッピング（実際の実装では設定ファイルから取得）
            step_order = {
                "theme_selection": 1,
                "script_generation": 2,
                "title_generation": 3,
                "tts_generation": 4,
                "character_synthesis": 5,
                "background_generation": 6,
                "background_animation": 7,
                "subtitle_generation": 8,
                "video_composition": 9,
                "audio_enhancement": 10,
                "illustration_insertion": 11,
                "final_encoding": 12,
                "youtube_upload": 13
            }
            
            current_step_number = step_order.get(step_name)
            if not current_step_number:
                return None
            
            with self.db_manager.get_connection() as conn:
                # 前のステップを取得
                row = conn.execute("""
                    SELECT output_data
                    FROM workflow_steps 
                    WHERE project_id = ? AND step_number = ? AND status = 'completed'
                """, (project_id, current_step_number - 1)).fetchone()
                
                if not row or not row["output_data"]:
                    return None
                
                return json.loads(row["output_data"])
                
        except Exception as e:
            error_msg = f"Failed to get step input: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    # ファイル参照管理
    
    def register_file_reference(
        self,
        project_id: str,
        file_type: str,
        file_category: str,
        file_path: str,
        file_name: str,
        file_size: int = 0,
        mime_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_temporary: bool = False
    ) -> int:
        """
        ファイル参照を登録
        
        Args:
            project_id: プロジェクトID
            file_type: ファイルタイプ
            file_category: ファイルカテゴリ
            file_path: ファイルパス
            file_name: ファイル名
            file_size: ファイルサイズ
            mime_type: MIMEタイプ
            metadata: メタデータ
            is_temporary: 一時ファイルフラグ
            
        Returns:
            int: ファイルID
            
        Raises:
            ProjectDataAccessError: 登録失敗時
        """
        try:
            metadata_json = json.dumps(metadata or {})
            
            with self.db_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO project_files (
                        project_id, file_type, file_category, file_path,
                        file_name, file_size, mime_type, metadata, is_temporary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id, file_type, file_category, file_path,
                    file_name, file_size, mime_type, metadata_json, int(is_temporary)
                ))
                
                file_id = cursor.lastrowid
                self.logger.info(f"File reference registered: {file_id} - {file_path}")
                return file_id
                
        except Exception as e:
            error_msg = f"Failed to register file reference: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def get_file_reference(self, file_id: int) -> Optional[Dict[str, Any]]:
        """
        ファイル参照情報を取得
        
        Args:
            file_id: ファイルID
            
        Returns:
            Dict: ファイル情報、存在しない場合None
            
        Raises:
            ProjectDataAccessError: 取得失敗時
        """
        try:
            with self.db_manager.get_connection() as conn:
                row = conn.execute("""
                    SELECT id, project_id, file_type, file_category, file_path,
                           file_name, file_size, mime_type, metadata, is_temporary,
                           created_at
                    FROM project_files WHERE id = ?
                """, (file_id,)).fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row["id"],
                    "project_id": row["project_id"],
                    "file_type": row["file_type"],
                    "file_category": row["file_category"],
                    "file_path": row["file_path"],
                    "file_name": row["file_name"],
                    "file_size": row["file_size"],
                    "mime_type": row["mime_type"],
                    "metadata": row["metadata"],
                    "is_temporary": bool(row["is_temporary"]),
                    "created_at": row["created_at"]
                }
                
        except Exception as e:
            error_msg = f"Failed to get file reference: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def get_files_by_query(
        self,
        project_id: str,
        file_type: Optional[str] = None,
        file_category: Optional[str] = None,
        is_temporary: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        条件に基づいてファイルを検索
        
        Args:
            project_id: プロジェクトID
            file_type: ファイルタイプ（オプション）
            file_category: ファイルカテゴリ（オプション）
            is_temporary: 一時ファイルフラグ（オプション）
            
        Returns:
            List[Dict]: ファイル情報のリスト
            
        Raises:
            ProjectDataAccessError: 検索失敗時
        """
        try:
            conditions = ["project_id = ?"]
            params = [project_id]
            
            if file_type:
                conditions.append("file_type = ?")
                params.append(file_type)
                
            if file_category:
                conditions.append("file_category = ?")
                params.append(file_category)
                
            if is_temporary is not None:
                conditions.append("is_temporary = ?")
                params.append(int(is_temporary))
            
            query = f"""
                SELECT id, project_id, file_type, file_category, file_path,
                       file_name, file_size, mime_type, metadata, is_temporary,
                       created_at
                FROM project_files 
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at
            """
            
            with self.db_manager.get_connection() as conn:
                rows = conn.execute(query, params).fetchall()
                
                return [
                    {
                        "id": row["id"],
                        "project_id": row["project_id"],
                        "file_type": row["file_type"],
                        "file_category": row["file_category"],
                        "file_path": row["file_path"],
                        "file_name": row["file_name"],
                        "file_size": row["file_size"],
                        "mime_type": row["mime_type"],
                        "metadata": row["metadata"],
                        "is_temporary": bool(row["is_temporary"]),
                        "created_at": row["created_at"]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            error_msg = f"Failed to query files: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    def update_file_metadata(
        self, 
        file_id: int, 
        metadata: Dict[str, Any]
    ) -> bool:
        """
        ファイルメタデータを更新
        
        Args:
            file_id: ファイルID
            metadata: 新しいメタデータ
            
        Returns:
            bool: 更新成功時True
            
        Raises:
            ProjectDataAccessError: 更新失敗時
        """
        try:
            metadata_json = json.dumps(metadata)
            
            with self.db_manager.transaction() as conn:
                result = conn.execute("""
                    UPDATE project_files 
                    SET metadata = ?
                    WHERE id = ?
                """, (metadata_json, file_id))
                
                if result.rowcount == 0:
                    return False
                
                self.logger.info(f"File metadata updated: {file_id}")
                return True
                
        except Exception as e:
            error_msg = f"Failed to update file metadata: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)
    
    # プロジェクト状態管理
    
    def get_project_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        プロジェクト全体の状況を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Dict: プロジェクト状況（プロジェクト情報、ステップ情報、ファイル情報）
            
        Raises:
            ProjectDataAccessError: 取得失敗時
        """
        try:
            project = self.get_project(project_id)
            if not project:
                return None
            
            with self.db_manager.get_connection() as conn:
                # ワークフローステップ情報取得
                step_rows = conn.execute("""
                    SELECT step_number, step_name, status, started_at, completed_at,
                           error_message, retry_count
                    FROM workflow_steps 
                    WHERE project_id = ?
                    ORDER BY step_number
                """, (project_id,)).fetchall()
                
                steps = [
                    {
                        "step_number": row["step_number"],
                        "step_name": row["step_name"],
                        "status": row["status"],
                        "started_at": row["started_at"],
                        "completed_at": row["completed_at"],
                        "error_message": row["error_message"],
                        "retry_count": row["retry_count"]
                    }
                    for row in step_rows
                ]
                
                # ファイル情報取得
                file_rows = conn.execute("""
                    SELECT file_type, file_category, file_path, file_name,
                           file_size, created_at
                    FROM project_files 
                    WHERE project_id = ?
                    ORDER BY created_at
                """, (project_id,)).fetchall()
                
                files = [
                    {
                        "file_type": row["file_type"],
                        "file_category": row["file_category"],
                        "file_path": row["file_path"],
                        "file_name": row["file_name"],
                        "file_size": row["file_size"],
                        "created_at": row["created_at"]
                    }
                    for row in file_rows
                ]
                
                return {
                    "project": project,
                    "workflow_steps": steps,
                    "files": files
                }
                
        except Exception as e:
            error_msg = f"Failed to get project status: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg)

    def get_workflow_steps(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクトのワークフローステップ一覧を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict]: ワークフローステップのリスト
            
        Raises:
            ProjectDataAccessError: 取得失敗時
        """
        try:
            with self.db_manager.get_connection() as conn:
                rows = conn.execute("""
                    SELECT id, project_id, step_number, step_name, status,
                           started_at, completed_at, input_data, output_data,
                           error_message, retry_count
                    FROM workflow_steps 
                    WHERE project_id = ?
                    ORDER BY step_number
                """, (project_id,)).fetchall()
                
                return [
                    {
                        "id": row["id"],
                        "project_id": row["project_id"],
                        "step_number": row["step_number"],
                        "step_name": row["step_name"],
                        "status": row["status"],
                        "started_at": row["started_at"],
                        "completed_at": row["completed_at"],
                        "input_data": json.loads(row["input_data"]) if row["input_data"] else {},
                        "output_data": json.loads(row["output_data"]) if row["output_data"] else {},
                        "error_message": row["error_message"],
                        "retry_count": row["retry_count"]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            error_msg = f"Failed to get workflow steps for project {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise ProjectDataAccessError(error_msg) 