"""
プロジェクト状態管理システム (1-1-2: プロジェクト状態管理)

このモジュールでは以下の機能を提供します：
- 進捗状況追跡
- ステップ完了状況管理
- エラー状態記録
"""

import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .database_manager import DatabaseManager, DatabaseError


class ProjectStateError(Exception):
    """プロジェクト状態管理に関するエラー"""
    pass


class ProjectStateManager:
    """
    プロジェクト状態管理システム
    
    ワークフローステップの状態管理、進捗追跡、エラー記録を行います。
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        プロジェクト状態マネージャーを初期化
        
        Args:
            db_manager: データベースマネージャーインスタンス
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # ステップ状態の定数
        self.STEP_STATUS = {
            'PENDING': 'pending',
            'RUNNING': 'running', 
            'COMPLETED': 'completed',
            'FAILED': 'failed',
            'SKIPPED': 'skipped'
        }
    
    def initialize_workflow_steps(self, project_id: str, workflow_definition: List[Dict[str, Any]]) -> None:
        """
        ワークフローステップを初期化
        
        Args:
            project_id: プロジェクトID
            workflow_definition: ワークフロー定義（ステップ番号、名前、表示名を含む）
            
        Raises:
            ProjectStateError: 初期化に失敗した場合
        """
        try:
            with self.db_manager.transaction():
                # 既存のステップを削除（再初期化の場合）
                self.db_manager.execute_query(
                    "DELETE FROM workflow_steps WHERE project_id = ?",
                    (project_id,)
                )
                
                # 各ステップを初期化
                for step_def in workflow_definition:
                    self.db_manager.execute_query(
                        """
                        INSERT INTO workflow_steps (
                            project_id, step_number, step_name, status,
                            input_data, output_data, retry_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            project_id,
                            step_def["step_number"],
                            step_def["step_name"],
                            self.STEP_STATUS['PENDING'],
                            '{}',  # 空のJSON
                            '{}',  # 空のJSON
                            0
                        )
                    )
                
                self.logger.info(
                    f"Workflow steps initialized for project {project_id}: "
                    f"{len(workflow_definition)} steps"
                )
                
        except Exception as e:
            raise ProjectStateError(f"Failed to initialize workflow steps: {str(e)}")
    
    def get_workflow_steps(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクトのワークフローステップ一覧を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            ワークフローステップのリスト
        """
        results = self.db_manager.fetch_all(
            """
            SELECT id, project_id, step_number, step_name, status,
                   started_at, completed_at, input_data, output_data,
                   error_message, retry_count
            FROM workflow_steps 
            WHERE project_id = ?
            ORDER BY step_number
            """,
            (project_id,)
        )
        
        return [
            {
                "id": row[0],
                "project_id": row[1],
                "step_number": row[2],
                "step_name": row[3],
                "status": row[4],
                "started_at": row[5],
                "completed_at": row[6],
                "input_data": row[7],
                "output_data": row[8],
                "error_message": row[9],
                "retry_count": row[10]
            }
            for row in results
        ]
    
    def get_step_by_number(self, project_id: str, step_number: int) -> Optional[Dict[str, Any]]:
        """
        ステップ番号でステップを取得
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            
        Returns:
            ステップ情報（見つからない場合はNone）
        """
        result = self.db_manager.fetch_one(
            """
            SELECT id, project_id, step_number, step_name, status,
                   started_at, completed_at, input_data, output_data,
                   error_message, retry_count
            FROM workflow_steps 
            WHERE project_id = ? AND step_number = ?
            """,
            (project_id, step_number)
        )
        
        if not result:
            return None
            
        return {
            "id": result[0],
            "project_id": result[1],
            "step_number": result[2],
            "step_name": result[3],
            "status": result[4],
            "started_at": result[5],
            "completed_at": result[6],
            "input_data": result[7],
            "output_data": result[8],
            "error_message": result[9],
            "retry_count": result[10]
        }
    
    def get_step_by_name(self, project_id: str, step_name: str) -> Optional[Dict[str, Any]]:
        """
        ステップ名でステップを取得
        
        Args:
            project_id: プロジェクトID
            step_name: ステップ名
            
        Returns:
            ステップ情報（見つからない場合はNone）
        """
        result = self.db_manager.fetch_one(
            """
            SELECT id, project_id, step_number, step_name, status,
                   started_at, completed_at, input_data, output_data,
                   error_message, retry_count
            FROM workflow_steps 
            WHERE project_id = ? AND step_name = ?
            """,
            (project_id, step_name)
        )
        
        if not result:
            return None
            
        return {
            "id": result[0],
            "project_id": result[1],
            "step_number": result[2],
            "step_name": result[3],
            "status": result[4],
            "started_at": result[5],
            "completed_at": result[6],
            "input_data": result[7],
            "output_data": result[8],
            "error_message": result[9],
            "retry_count": result[10]
        }
    
    def start_step(self, project_id: str, step_number: int, input_data: Dict[str, Any] = None) -> None:
        """
        ステップを開始
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            input_data: 入力データ
            
        Raises:
            ProjectStateError: ステップ開始に失敗した場合
        """
        try:
            if input_data is None:
                input_data = {}
            
            current_time = datetime.now().isoformat()
            
            rows_affected = self.db_manager.execute_query(
                """
                UPDATE workflow_steps 
                SET status = ?, started_at = ?, input_data = ?, 
                    completed_at = NULL, error_message = NULL
                WHERE project_id = ? AND step_number = ?
                """,
                (
                    self.STEP_STATUS['RUNNING'],
                    current_time,
                    json.dumps(input_data, ensure_ascii=False),
                    project_id,
                    step_number
                )
            )
            
            if rows_affected == 0:
                raise ProjectStateError(f"Step {step_number} not found for project {project_id}")
            
            self.logger.info(f"Started step {step_number} for project {project_id}")
            
        except Exception as e:
            raise ProjectStateError(f"Failed to start step {step_number}: {str(e)}")
    
    def complete_step(self, project_id: str, step_number: int, output_data: Dict[str, Any] = None) -> None:
        """
        ステップを完了
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            output_data: 出力データ
            
        Raises:
            ProjectStateError: ステップ完了に失敗した場合
        """
        try:
            if output_data is None:
                output_data = {}
            
            current_time = datetime.now().isoformat()
            
            rows_affected = self.db_manager.execute_query(
                """
                UPDATE workflow_steps 
                SET status = ?, completed_at = ?, output_data = ?, error_message = NULL
                WHERE project_id = ? AND step_number = ?
                """,
                (
                    self.STEP_STATUS['COMPLETED'],
                    current_time,
                    json.dumps(output_data, ensure_ascii=False),
                    project_id,
                    step_number
                )
            )
            
            if rows_affected == 0:
                raise ProjectStateError(f"Step {step_number} not found for project {project_id}")
            
            self.logger.info(f"Completed step {step_number} for project {project_id}")
            
        except Exception as e:
            raise ProjectStateError(f"Failed to complete step {step_number}: {str(e)}")
    
    def fail_step(self, project_id: str, step_number: int, error_message: str) -> None:
        """
        ステップを失敗
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            error_message: エラーメッセージ
            
        Raises:
            ProjectStateError: ステップ失敗記録に失敗した場合
        """
        try:
            rows_affected = self.db_manager.execute_query(
                """
                UPDATE workflow_steps 
                SET status = ?, error_message = ?, completed_at = NULL
                WHERE project_id = ? AND step_number = ?
                """,
                (
                    self.STEP_STATUS['FAILED'],
                    error_message,
                    project_id,
                    step_number
                )
            )
            
            if rows_affected == 0:
                raise ProjectStateError(f"Step {step_number} not found for project {project_id}")
            
            self.logger.error(f"Failed step {step_number} for project {project_id}: {error_message}")
            
        except Exception as e:
            raise ProjectStateError(f"Failed to record step failure {step_number}: {str(e)}")
    
    def retry_step(self, project_id: str, step_number: int, input_data: Dict[str, Any] = None) -> None:
        """
        ステップをリトライ
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            input_data: 新しい入力データ
            
        Raises:
            ProjectStateError: リトライに失敗した場合
        """
        try:
            if input_data is None:
                input_data = {}
            
            current_time = datetime.now().isoformat()
            
            rows_affected = self.db_manager.execute_query(
                """
                UPDATE workflow_steps 
                SET status = ?, started_at = ?, input_data = ?,
                    retry_count = retry_count + 1, error_message = NULL, completed_at = NULL
                WHERE project_id = ? AND step_number = ?
                """,
                (
                    self.STEP_STATUS['RUNNING'],
                    current_time,
                    json.dumps(input_data, ensure_ascii=False),
                    project_id,
                    step_number
                )
            )
            
            if rows_affected == 0:
                raise ProjectStateError(f"Step {step_number} not found for project {project_id}")
            
            self.logger.info(f"Retrying step {step_number} for project {project_id}")
            
        except Exception as e:
            raise ProjectStateError(f"Failed to retry step {step_number}: {str(e)}")
    
    def skip_step(self, project_id: str, step_number: int, reason: str) -> None:
        """
        ステップをスキップ
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            reason: スキップ理由
            
        Raises:
            ProjectStateError: スキップに失敗した場合
        """
        try:
            current_time = datetime.now().isoformat()
            
            rows_affected = self.db_manager.execute_query(
                """
                UPDATE workflow_steps 
                SET status = ?, completed_at = ?, error_message = ?
                WHERE project_id = ? AND step_number = ?
                """,
                (
                    self.STEP_STATUS['SKIPPED'],
                    current_time,
                    reason,
                    project_id,
                    step_number
                )
            )
            
            if rows_affected == 0:
                raise ProjectStateError(f"Step {step_number} not found for project {project_id}")
            
            self.logger.info(f"Skipped step {step_number} for project {project_id}: {reason}")
            
        except Exception as e:
            raise ProjectStateError(f"Failed to skip step {step_number}: {str(e)}")
    
    def reset_step(self, project_id: str, step_number: int) -> None:
        """
        ステップを初期状態にリセット
        
        Args:
            project_id: プロジェクトID
            step_number: ステップ番号
            
        Raises:
            ProjectStateError: リセットに失敗した場合
        """
        try:
            rows_affected = self.db_manager.execute_query(
                """
                UPDATE workflow_steps 
                SET status = ?, started_at = NULL, completed_at = NULL,
                    input_data = '{}', output_data = '{}', error_message = NULL, retry_count = 0
                WHERE project_id = ? AND step_number = ?
                """,
                (
                    self.STEP_STATUS['PENDING'],
                    project_id,
                    step_number
                )
            )
            
            if rows_affected == 0:
                raise ProjectStateError(f"Step {step_number} not found for project {project_id}")
            
            self.logger.info(f"Reset step {step_number} for project {project_id}")
            
        except Exception as e:
            raise ProjectStateError(f"Failed to reset step {step_number}: {str(e)}")
    
    def get_project_progress(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトの進捗情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            進捗情報の辞書（総ステップ数、完了数、実行中数、待機数、失敗数、完了率等）
        """
        steps = self.get_workflow_steps(project_id)
        
        if not steps:
            return {
                "total_steps": 0,
                "completed_steps": 0,
                "running_steps": 0,
                "pending_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "completion_percentage": 0.0,
                "current_step": None
            }
        
        # ステップ状態別の集計
        status_counts = {
            'completed': 0,
            'running': 0,
            'pending': 0,
            'failed': 0,
            'skipped': 0
        }
        
        current_step = None
        for step in steps:
            status = step['status']
            if status in status_counts:
                status_counts[status] += 1
            
            # 現在実行中のステップを見つける
            if status == 'running' and current_step is None:
                current_step = step
        
        total_steps = len(steps)
        completed_and_skipped = status_counts['completed'] + status_counts['skipped']
        completion_percentage = (completed_and_skipped / total_steps * 100) if total_steps > 0 else 0.0
        
        return {
            "total_steps": total_steps,
            "completed_steps": status_counts['completed'],
            "running_steps": status_counts['running'],
            "pending_steps": status_counts['pending'],
            "failed_steps": status_counts['failed'],
            "skipped_steps": status_counts['skipped'],
            "completion_percentage": completion_percentage,
            "current_step": current_step
        }
    
    def get_failed_steps(self, project_id: str) -> List[Dict[str, Any]]:
        """
        失敗したステップ一覧を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            失敗したステップのリスト
        """
        results = self.db_manager.fetch_all(
            """
            SELECT id, project_id, step_number, step_name, status,
                   started_at, completed_at, input_data, output_data,
                   error_message, retry_count
            FROM workflow_steps 
            WHERE project_id = ? AND status = ?
            ORDER BY step_number
            """,
            (project_id, self.STEP_STATUS['FAILED'])
        )
        
        return [
            {
                "id": row[0],
                "project_id": row[1],
                "step_number": row[2],
                "step_name": row[3],
                "status": row[4],
                "started_at": row[5],
                "completed_at": row[6],
                "input_data": row[7],
                "output_data": row[8],
                "error_message": row[9],
                "retry_count": row[10]
            }
            for row in results
        ]
    
    def calculate_estimated_remaining_time(self, project_id: str) -> float:
        """
        残り時間を推定
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            推定残り時間（秒）
        """
        steps = self.get_workflow_steps(project_id)
        
        if not steps:
            return 0.0
        
        # 完了したステップの実行時間を計算
        completed_durations = []
        for step in steps:
            if (step['status'] == 'completed' and 
                step['started_at'] and step['completed_at']):
                
                started = datetime.fromisoformat(step['started_at'])
                completed = datetime.fromisoformat(step['completed_at'])
                duration = (completed - started).total_seconds()
                completed_durations.append(duration)
        
        if not completed_durations:
            # 完了したステップがない場合はデフォルト時間を使用
            return len([s for s in steps if s['status'] in ['pending', 'running']]) * 60.0
        
        # 平均実行時間を計算
        avg_duration = sum(completed_durations) / len(completed_durations)
        
        # 残りのステップ数を計算
        remaining_steps = len([s for s in steps if s['status'] in ['pending', 'running']])
        
        return remaining_steps * avg_duration 