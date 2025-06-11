"""
プロジェクト復元機能システム (1-1-3: プロジェクト復元機能)

このモジュールでは以下の機能を提供します：
- 中断からの再開
- 状態ファイル読み込み
- 整合性チェック
"""

import json
import os
import logging
import glob
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .database_manager import DatabaseManager
from .project_manager import ProjectManager
from .project_state_manager import ProjectStateManager


class ProjectRecoveryError(Exception):
    """プロジェクト復元に関するエラー"""
    pass


class ProjectRecoveryManager:
    """
    プロジェクト復元管理システム
    
    プロジェクトの中断・復元、チェックポイント管理、整合性チェックを行います。
    """
    
    def __init__(self, 
                 db_manager: DatabaseManager,
                 project_manager: ProjectManager,
                 state_manager: ProjectStateManager):
        """
        プロジェクト復元マネージャーを初期化
        
        Args:
            db_manager: データベースマネージャーインスタンス
            project_manager: プロジェクトマネージャーインスタンス
            state_manager: プロジェクト状態マネージャーインスタンス
        """
        self.db_manager = db_manager
        self.project_manager = project_manager
        self.state_manager = state_manager
        self.logger = logging.getLogger(__name__)
        
        # チェックポイントディレクトリ
        self.checkpoint_dir = Path("data/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def create_checkpoint(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトのチェックポイントを作成
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            チェックポイントデータ
            
        Raises:
            ProjectRecoveryError: チェックポイント作成に失敗した場合
        """
        try:
            # プロジェクトメタデータを取得
            project = self.project_manager.get_project(project_id)
            if not project:
                raise ProjectRecoveryError(f"Project not found: {project_id}")
            
            # ワークフロー状態を取得
            steps = self.state_manager.get_workflow_steps(project_id)
            progress = self.state_manager.get_project_progress(project_id)
            
            # ファイル整合性情報を取得
            file_integrity = self._collect_file_integrity_info(project_id)
            
            # チェックポイントデータを構築
            checkpoint_data = {
                "project_metadata": {
                    "id": project["id"],
                    "theme": project["theme"],
                    "target_length_minutes": project["target_length_minutes"],
                    "status": project["status"],
                    "created_at": project["created_at"],
                    "updated_at": project["updated_at"]
                },
                "workflow_state": {
                    "steps": steps,
                    "progress": progress
                },
                "file_integrity": file_integrity,
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            self.logger.info(f"Checkpoint created for project {project_id}")
            return checkpoint_data
            
        except Exception as e:
            raise ProjectRecoveryError(f"Failed to create checkpoint: {str(e)}")
    
    def save_checkpoint_to_file(self, 
                                project_id: str, 
                                checkpoint_data: Dict[str, Any],
                                suffix: str = "") -> str:
        """
        チェックポイントをファイルに保存
        
        Args:
            project_id: プロジェクトID
            checkpoint_data: チェックポイントデータ
            suffix: ファイル名のサフィックス（テスト用）
            
        Returns:
            保存されたファイルのパス
            
        Raises:
            ProjectRecoveryError: ファイル保存に失敗した場合
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"checkpoint_{project_id}_{timestamp}{suffix}.json"
            filepath = self.checkpoint_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Checkpoint saved to file: {filepath}")
            return str(filepath)
            
        except Exception as e:
            raise ProjectRecoveryError(f"Failed to save checkpoint: {str(e)}")
    
    def load_checkpoint_from_file(self, checkpoint_file: str) -> Dict[str, Any]:
        """
        ファイルからチェックポイントを読み込み
        
        Args:
            checkpoint_file: チェックポイントファイルのパス
            
        Returns:
            チェックポイントデータ
            
        Raises:
            ProjectRecoveryError: ファイル読み込みに失敗した場合
        """
        try:
            if not os.path.exists(checkpoint_file):
                raise ProjectRecoveryError(f"Checkpoint file not found: {checkpoint_file}")
            
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            # データの基本検証
            validation_result = self.validate_checkpoint_data(checkpoint_data)
            if not validation_result["is_valid"]:
                raise ProjectRecoveryError(
                    f"Invalid checkpoint data: {', '.join(validation_result['errors'])}"
                )
            
            self.logger.info(f"Checkpoint loaded from file: {checkpoint_file}")
            return checkpoint_data
            
        except json.JSONDecodeError as e:
            raise ProjectRecoveryError(f"Invalid JSON in checkpoint file: {str(e)}")
        except Exception as e:
            raise ProjectRecoveryError(f"Failed to load checkpoint: {str(e)}")
    
    def verify_project_integrity(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトの整合性をチェック
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            整合性チェック結果
        """
        integrity_result = {
            "is_valid": True,
            "issues": [],
            "database_consistency": True,
            "file_system_consistency": True,
            "details": {}
        }
        
        try:
            # データベース整合性チェック
            db_issues = self._check_database_consistency(project_id)
            if db_issues:
                integrity_result["database_consistency"] = False
                integrity_result["issues"].extend(db_issues)
            
            # ファイルシステム整合性チェック
            fs_issues = self._check_file_system_consistency(project_id)
            if fs_issues:
                integrity_result["file_system_consistency"] = False
                integrity_result["issues"].extend(fs_issues)
            
            # 全体の整合性判定
            integrity_result["is_valid"] = (
                integrity_result["database_consistency"] and 
                integrity_result["file_system_consistency"]
            )
            
            self.logger.info(
                f"Integrity check for project {project_id}: "
                f"Valid={integrity_result['is_valid']}, "
                f"Issues={len(integrity_result['issues'])}"
            )
            
            return integrity_result
            
        except Exception as e:
            self.logger.error(f"Integrity check failed for project {project_id}: {str(e)}")
            return {
                "is_valid": False,
                "issues": [f"Integrity check failed: {str(e)}"],
                "database_consistency": False,
                "file_system_consistency": False,
                "details": {}
            }
    
    def restore_project_from_checkpoint(self, 
                                      project_id: str, 
                                      checkpoint_file: str) -> Dict[str, Any]:
        """
        チェックポイントからプロジェクトを復元
        
        Args:
            project_id: プロジェクトID
            checkpoint_file: チェックポイントファイルのパス
            
        Returns:
            復元結果
            
        Raises:
            ProjectRecoveryError: 復元に失敗した場合
        """
        try:
            # チェックポイントデータを読み込み
            checkpoint_data = self.load_checkpoint_from_file(checkpoint_file)
            
            # プロジェクトIDの確認
            if checkpoint_data["project_metadata"]["id"] != project_id:
                raise ProjectRecoveryError(
                    f"Project ID mismatch: expected {project_id}, "
                    f"got {checkpoint_data['project_metadata']['id']}"
                )
            
            restored_steps = []
            
            with self.db_manager.transaction():
                # プロジェクトメタデータを復元
                project_metadata = checkpoint_data["project_metadata"]
                self.project_manager.update_project_status(project_id, project_metadata["status"])
                
                # ワークフローステップを復元
                workflow_state = checkpoint_data["workflow_state"]
                for step_data in workflow_state["steps"]:
                    step_number = step_data["step_number"]
                    
                    # ステップの状態を復元
                    if step_data["status"] == "completed":
                        self.state_manager.start_step(
                            project_id, 
                            step_number, 
                            json.loads(step_data["input_data"]) if step_data["input_data"] else {}
                        )
                        self.state_manager.complete_step(
                            project_id, 
                            step_number, 
                            json.loads(step_data["output_data"]) if step_data["output_data"] else {}
                        )
                    elif step_data["status"] == "running":
                        self.state_manager.start_step(
                            project_id, 
                            step_number, 
                            json.loads(step_data["input_data"]) if step_data["input_data"] else {}
                        )
                    elif step_data["status"] == "failed":
                        self.state_manager.start_step(
                            project_id, 
                            step_number, 
                            json.loads(step_data["input_data"]) if step_data["input_data"] else {}
                        )
                        self.state_manager.fail_step(
                            project_id, 
                            step_number, 
                            step_data["error_message"] or "Restored failed state"
                        )
                    elif step_data["status"] == "skipped":
                        self.state_manager.skip_step(
                            project_id, 
                            step_number, 
                            step_data["error_message"] or "Restored skipped state"
                        )
                    
                    # リトライ回数を復元
                    if step_data["retry_count"] > 0:
                        self.db_manager.execute_query(
                            "UPDATE workflow_steps SET retry_count = ? WHERE project_id = ? AND step_number = ?",
                            (step_data["retry_count"], project_id, step_number)
                        )
                    
                    restored_steps.append(step_number)
            
            restore_result = {
                "success": True,
                "restored_steps": restored_steps,
                "checkpoint_timestamp": checkpoint_data["timestamp"],
                "message": f"Successfully restored {len(restored_steps)} steps"
            }
            
            self.logger.info(f"Project {project_id} restored from checkpoint: {checkpoint_file}")
            return restore_result
            
        except Exception as e:
            raise ProjectRecoveryError(f"Failed to restore project: {str(e)}")
    
    def resume_interrupted_project(self, project_id: str) -> Dict[str, Any]:
        """
        中断されたプロジェクトを再開
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            再開結果
            
        Raises:
            ProjectRecoveryError: 再開に失敗した場合
        """
        try:
            # プロジェクトの存在確認
            project = self.project_manager.get_project(project_id)
            if not project:
                raise ProjectRecoveryError(f"Project not found: {project_id}")
            
            # 現在の進捗状況を取得
            progress = self.state_manager.get_project_progress(project_id)
            
            # 実行中のステップを特定
            current_step = progress.get("current_step")
            if not current_step:
                # 実行中のステップがない場合、次に実行すべきステップを見つける
                steps = self.state_manager.get_workflow_steps(project_id)
                pending_steps = [s for s in steps if s["status"] == "pending"]
                if pending_steps:
                    current_step = pending_steps[0]
            
            # プロジェクトステータスを更新
            self.project_manager.update_project_status(project_id, "running")
            
            # 次のアクションを決定
            next_actions = self._determine_next_actions(project_id, progress)
            
            resume_result = {
                "success": True,
                "current_step": current_step,
                "progress": progress,
                "next_actions": next_actions,
                "message": "Project resumed successfully"
            }
            
            self.logger.info(f"Project {project_id} resumed successfully")
            return resume_result
            
        except Exception as e:
            raise ProjectRecoveryError(f"Failed to resume project: {str(e)}")
    
    def find_interrupted_projects(self) -> List[Dict[str, Any]]:
        """
        中断されたプロジェクトを検索
        
        Returns:
            中断プロジェクトのリスト
        """
        try:
            projects = self.project_manager.list_projects()
            interrupted_projects = [
                project for project in projects 
                if project["status"] == "interrupted"
            ]
            
            self.logger.info(f"Found {len(interrupted_projects)} interrupted projects")
            return interrupted_projects
            
        except Exception as e:
            self.logger.error(f"Failed to find interrupted projects: {str(e)}")
            return []
    
    def auto_save_checkpoint(self, project_id: str) -> str:
        """
        自動チェックポイント保存
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            保存されたチェックポイントファイルのパス
        """
        try:
            checkpoint_data = self.create_checkpoint(project_id)
            checkpoint_file = self.save_checkpoint_to_file(project_id, checkpoint_data)
            
            # 古いチェックポイントをクリーンアップ（最新5つを保持）
            self.cleanup_old_checkpoints(project_id, keep_count=5)
            
            return checkpoint_file
            
        except Exception as e:
            self.logger.error(f"Auto-save checkpoint failed for project {project_id}: {str(e)}")
            raise ProjectRecoveryError(f"Auto-save failed: {str(e)}")
    
    def cleanup_old_checkpoints(self, project_id: str, keep_count: int = 5) -> int:
        """
        古いチェックポイントをクリーンアップ
        
        Args:
            project_id: プロジェクトID
            keep_count: 保持するチェックポイント数
            
        Returns:
            削除されたファイル数
        """
        try:
            # プロジェクトのチェックポイントファイルを検索
            pattern = str(self.checkpoint_dir / f"checkpoint_{project_id}_*.json")
            checkpoint_files = glob.glob(pattern)
            
            if len(checkpoint_files) <= keep_count:
                return 0
            
            # ファイルを作成日時でソート（新しい順）
            checkpoint_files.sort(key=os.path.getmtime, reverse=True)
            
            # 古いファイルを削除
            files_to_delete = checkpoint_files[keep_count:]
            deleted_count = 0
            
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete checkpoint file {file_path}: {str(e)}")
            
            self.logger.info(f"Cleaned up {deleted_count} old checkpoint files for project {project_id}")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Checkpoint cleanup failed for project {project_id}: {str(e)}")
            return 0
    
    def validate_checkpoint_data(self, checkpoint_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        チェックポイントデータの検証
        
        Args:
            checkpoint_data: チェックポイントデータ
            
        Returns:
            検証結果
        """
        validation_result = {
            "is_valid": True,
            "errors": []
        }
        
        # 必須フィールドの確認
        required_fields = ["project_metadata", "workflow_state", "timestamp"]
        for field in required_fields:
            if field not in checkpoint_data:
                validation_result["errors"].append(f"Missing required field: {field}")
        
        # プロジェクトメタデータの検証
        if "project_metadata" in checkpoint_data:
            metadata = checkpoint_data["project_metadata"]
            required_metadata_fields = ["id", "theme", "status"]
            for field in required_metadata_fields:
                if field not in metadata:
                    validation_result["errors"].append(f"Missing project metadata field: {field}")
        
        # ワークフロー状態の検証
        if "workflow_state" in checkpoint_data:
            workflow = checkpoint_data["workflow_state"]
            if not isinstance(workflow, dict) or "steps" not in workflow:
                validation_result["errors"].append("Invalid workflow_state format")
        
        # タイムスタンプの検証
        if "timestamp" in checkpoint_data:
            try:
                datetime.fromisoformat(checkpoint_data["timestamp"])
            except ValueError:
                validation_result["errors"].append("Invalid timestamp format")
        
        validation_result["is_valid"] = len(validation_result["errors"]) == 0
        return validation_result
    
    def get_recovery_recommendations(self, project_id: str) -> Dict[str, Any]:
        """
        復旧推奨アクションを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            推奨アクション情報
        """
        try:
            # 失敗したステップを取得
            failed_steps = self.state_manager.get_failed_steps(project_id)
            
            # 進捗情報を取得
            progress = self.state_manager.get_project_progress(project_id)
            
            recommendations = {
                "failed_steps": failed_steps,
                "recommended_actions": [],
                "priority": "medium"
            }
            
            # 失敗ステップに対する推奨アクション
            if failed_steps:
                recommendations["priority"] = "high"
                recommendations["recommended_actions"].extend([
                    "失敗したステップのエラーメッセージを確認してください",
                    "必要に応じてステップをリトライしてください",
                    "問題が解決しない場合は、ステップをスキップすることを検討してください"
                ])
            
            # 実行中ステップがない場合
            if progress["running_steps"] == 0 and progress["pending_steps"] > 0:
                recommendations["recommended_actions"].append(
                    "次のステップを開始してください"
                )
            
            # 進捗が止まっている場合
            if progress["completion_percentage"] > 0 and progress["running_steps"] == 0:
                recommendations["recommended_actions"].append(
                    "プロジェクトの続行または完了処理を検討してください"
                )
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to get recovery recommendations: {str(e)}")
            return {
                "failed_steps": [],
                "recommended_actions": ["エラーが発生しました。システム管理者に連絡してください。"],
                "priority": "high"
            }
    
    def _collect_file_integrity_info(self, project_id: str) -> Dict[str, Any]:
        """ファイル整合性情報を収集"""
        try:
            project_dir = Path(self.project_manager.projects_base_dir) / project_id
            
            file_info = {
                "project_directory_exists": project_dir.exists(),
                "subdirectories": {},
                "file_count": 0
            }
            
            if project_dir.exists():
                # サブディレクトリの存在確認
                required_subdirs = [
                    "files/scripts", "files/audio", "files/video", 
                    "files/images", "files/subtitles", "files/metadata", 
                    "config", "logs", "cache"
                ]
                
                for subdir in required_subdirs:
                    subdir_path = project_dir / subdir
                    file_info["subdirectories"][subdir] = subdir_path.exists()
                
                # ファイル数をカウント
                if project_dir.is_dir():
                    file_info["file_count"] = len(list(project_dir.rglob("*")))
            
            return file_info
            
        except Exception as e:
            self.logger.warning(f"Failed to collect file integrity info: {str(e)}")
            return {"error": str(e)}
    
    def _check_database_consistency(self, project_id: str) -> List[str]:
        """データベース整合性をチェック"""
        issues = []
        
        try:
            # プロジェクトの存在確認
            project = self.project_manager.get_project(project_id)
            if not project:
                issues.append(f"Project not found in database: {project_id}")
                return issues
            
            # ワークフローステップの整合性確認
            steps = self.state_manager.get_workflow_steps(project_id)
            if not steps:
                issues.append("No workflow steps found")
            else:
                # ステップ番号の連続性確認
                step_numbers = [step["step_number"] for step in steps]
                step_numbers.sort()
                for i, step_num in enumerate(step_numbers):
                    if step_num != i + 1:
                        issues.append(f"Missing step number: {i + 1}")
                        break
            
        except Exception as e:
            issues.append(f"Database consistency check failed: {str(e)}")
        
        return issues
    
    def _check_file_system_consistency(self, project_id: str) -> List[str]:
        """ファイルシステム整合性をチェック"""
        issues = []
        
        try:
            project_dir = Path(self.project_manager.projects_base_dir) / project_id
            
            # プロジェクトディレクトリの存在確認
            if not project_dir.exists():
                issues.append(f"Project directory not found: {project_dir}")
                return issues
            
            # 必須サブディレクトリの確認
            required_subdirs = [
                "files/scripts", "files/audio", "files/video", 
                "files/images", "files/subtitles", "files/metadata", 
                "config", "logs", "cache"
            ]
            
            for subdir in required_subdirs:
                subdir_path = project_dir / subdir
                if not subdir_path.exists():
                    issues.append(f"Missing subdirectory: {subdir}")
            
        except Exception as e:
            issues.append(f"File system consistency check failed: {str(e)}")
        
        return issues
    
    def _determine_next_actions(self, project_id: str, progress: Dict[str, Any]) -> List[str]:
        """次のアクションを決定"""
        actions = []
        
        try:
            # 失敗したステップがある場合
            if progress["failed_steps"] > 0:
                actions.append("失敗したステップを確認し、エラーを解決してください")
                actions.append("ステップのリトライまたはスキップを検討してください")
            
            # 実行中のステップがある場合
            if progress["running_steps"] > 0:
                actions.append("実行中のステップの完了を待機してください")
            
            # 待機中のステップがある場合
            if progress["pending_steps"] > 0:
                actions.append("次のステップを開始してください")
            
            # すべて完了している場合
            if progress["completion_percentage"] == 100.0:
                actions.append("プロジェクトが完了しました。最終確認を行ってください")
            
            if not actions:
                actions.append("プロジェクトの現在状態を確認してください")
            
        except Exception as e:
            self.logger.error(f"Failed to determine next actions: {str(e)}")
            actions = ["アクションの決定中にエラーが発生しました"]
        
        return actions