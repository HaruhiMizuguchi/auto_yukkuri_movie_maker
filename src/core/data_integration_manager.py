"""
DataIntegrationManager - データ統合管理

メタデータ（データベース）とファイルシステム間の
双方向同期、整合性チェック、バックアップ・復元を管理
"""

import os
import json
import shutil
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from src.core.project_repository import ProjectRepository
from src.core.file_system_manager import FileSystemManager


class DataIntegrationError(Exception):
    """データ統合エラー"""
    pass


@dataclass
class ConflictInfo:
    """コンフリクト情報"""
    file_path: str
    type: str  # size_mismatch, timestamp_mismatch, metadata_mismatch
    db_info: Dict[str, Any]
    fs_info: Dict[str, Any]
    resolution: Optional[str] = None


@dataclass
class SyncReport:
    """同期レポート"""
    project_id: str
    direction: str  # metadata_to_files, files_to_metadata, bidirectional
    status: str  # success, failed, partial
    timestamp: datetime
    conflicts: List[ConflictInfo]
    files_synced: int
    files_updated: int
    files_added: int
    files_removed: int
    errors: List[str]


class DataIntegrationManager:
    """データ統合管理クラス"""
    
    def __init__(self, project_repository: ProjectRepository, file_system_manager: FileSystemManager):
        """
        初期化
        
        Args:
            project_repository: プロジェクトリポジトリ
            file_system_manager: ファイルシステム管理
        """
        self.repository = project_repository
        self.fs_manager = file_system_manager
        self.logger = logging.getLogger(__name__)
        
        # 並行操作制御
        self._lock = threading.RLock()
        self._active_operations: Dict[str, str] = {}
        self._operation_locks: Dict[str, datetime] = {}
        
        # 最後の同期レポート
        self._last_sync_report: Optional[SyncReport] = None
    
    def sync_metadata_to_files(self, project_id: str) -> bool:
        """
        メタデータからファイルへの同期
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            同期成功フラグ
        """
        try:
            with self._lock:
                if project_id in self._active_operations:
                    raise DataIntegrationError(f"Project {project_id} is already being processed")
                
                self._active_operations[project_id] = "sync_metadata_to_files"
            
            self.logger.info(f"Starting metadata to files sync for project {project_id}")
            
            # プロジェクト存在確認
            project = self.repository.get_project(project_id)
            if not project:
                raise DataIntegrationError(f"Project {project_id} not found")
            
            # 同期レポート初期化
            report = SyncReport(
                project_id=project_id,
                direction="metadata_to_files",
                status="success",
                timestamp=datetime.now(),
                conflicts=[],
                files_synced=0,
                files_updated=0,
                files_added=0,
                files_removed=0,
                errors=[]
            )
            
            # DBからファイル参照一覧取得
            db_files = self.repository.get_files_by_query(project_id)
            
            for db_file in db_files:
                try:
                    file_path = db_file["file_path"]
                    
                    # ファイルの存在確認
                    full_path = self.fs_manager.get_project_file_path(project_id, file_path)
                    
                    if not os.path.exists(full_path):
                        # ファイルが存在しない場合の処理
                        if db_file.get("file_category") == "output":
                            # 出力ファイルの場合は作成
                            self._create_file_from_metadata(project_id, db_file)
                            report.files_added += 1
                        else:
                            self.logger.warning(f"Missing file: {file_path}")
                    else:
                        # ファイル情報の整合性チェック
                        conflicts = self._check_file_integrity(project_id, db_file)
                        report.conflicts.extend(conflicts)
                        
                        if not conflicts:
                            report.files_synced += 1
                
                except Exception as e:
                    error_msg = f"Failed to sync file {db_file.get('file_path', 'unknown')}: {str(e)}"
                    self.logger.error(error_msg)
                    report.errors.append(error_msg)
            
            # 同期結果の最終判定
            if report.errors:
                report.status = "partial" if report.files_synced > 0 else "failed"
            
            self._last_sync_report = report
            
            self.logger.info(f"Metadata to files sync completed for project {project_id}: "
                           f"{report.files_synced} synced, {report.files_added} added, "
                           f"{len(report.conflicts)} conflicts, {len(report.errors)} errors")
            
            return report.status in ["success", "partial"]
        
        except Exception as e:
            self.logger.error(f"Metadata to files sync failed for project {project_id}: {str(e)}")
            return False
        
        finally:
            with self._lock:
                self._active_operations.pop(project_id, None)
    
    def sync_files_to_metadata(self, project_id: str) -> bool:
        """
        ファイルからメタデータへの同期
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            同期成功フラグ
        """
        try:
            with self._lock:
                if project_id in self._active_operations:
                    raise DataIntegrationError(f"Project {project_id} is already being processed")
                
                self._active_operations[project_id] = "sync_files_to_metadata"
            
            self.logger.info(f"Starting files to metadata sync for project {project_id}")
            
            # プロジェクト存在確認
            project = self.repository.get_project(project_id)
            if not project:
                raise DataIntegrationError(f"Project {project_id} not found")
            
            # 同期レポート初期化
            report = SyncReport(
                project_id=project_id,
                direction="files_to_metadata",
                status="success",
                timestamp=datetime.now(),
                conflicts=[],
                files_synced=0,
                files_updated=0,
                files_added=0,
                files_removed=0,
                errors=[]
            )
            
            # ファイルシステムからファイル一覧取得
            fs_files = self.fs_manager.list_files(project_id)
            
            # 既存のDB登録ファイル一覧
            db_files = {f["file_path"]: f for f in self.repository.get_files_by_query(project_id)}
            
            for fs_file in fs_files:
                try:
                    file_path = fs_file["relative_path"]
                    
                    if file_path in db_files:
                        # 既存ファイルの更新チェック
                        conflicts = self._check_file_integrity(project_id, db_files[file_path])
                        if conflicts:
                            # 整合性問題があれば更新
                            self._update_file_metadata(project_id, fs_file, db_files[file_path])
                            report.files_updated += 1
                        else:
                            report.files_synced += 1
                    else:
                        # 新規ファイルの登録
                        self._register_new_file(project_id, fs_file)
                        report.files_added += 1
                
                except Exception as e:
                    error_msg = f"Failed to sync file {fs_file.get('relative_path', 'unknown')}: {str(e)}"
                    self.logger.error(error_msg)
                    report.errors.append(error_msg)
            
            # 同期結果の最終判定
            if report.errors:
                report.status = "partial" if (report.files_synced + report.files_added + report.files_updated) > 0 else "failed"
            
            self._last_sync_report = report
            
            self.logger.info(f"Files to metadata sync completed for project {project_id}: "
                           f"{report.files_synced} synced, {report.files_added} added, "
                           f"{report.files_updated} updated, {len(report.errors)} errors")
            
            return report.status in ["success", "partial"]
        
        except Exception as e:
            self.logger.error(f"Files to metadata sync failed for project {project_id}: {str(e)}")
            return False
        
        finally:
            with self._lock:
                self._active_operations.pop(project_id, None)
    
    def sync_bidirectional(self, project_id: str) -> bool:
        """
        双方向同期（メタデータ↔ファイル）
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            同期成功フラグ
        """
        try:
            with self._lock:
                if project_id in self._active_operations:
                    raise DataIntegrationError(f"Project {project_id} is already being processed")
                
                self._active_operations[project_id] = "sync_bidirectional"
            
            self.logger.info(f"Starting bidirectional sync for project {project_id}")
            
            # プロジェクト存在確認
            project = self.repository.get_project(project_id)
            if not project:
                raise DataIntegrationError(f"Project {project_id} not found")
            
            # 同期レポート初期化
            report = SyncReport(
                project_id=project_id,
                direction="bidirectional",
                status="success",
                timestamp=datetime.now(),
                conflicts=[],
                files_synced=0,
                files_updated=0,
                files_added=0,
                files_removed=0,
                errors=[]
            )
            
            # 1. ファイル→メタデータ同期
            files_to_meta_success = self.sync_files_to_metadata(project_id)
            if self._last_sync_report:
                report.files_added += self._last_sync_report.files_added
                report.files_updated += self._last_sync_report.files_updated
                report.errors.extend(self._last_sync_report.errors)
            
            # 2. メタデータ→ファイル同期
            meta_to_files_success = self.sync_metadata_to_files(project_id)
            if self._last_sync_report:
                report.files_synced += self._last_sync_report.files_synced
                report.conflicts.extend(self._last_sync_report.conflicts)
                report.errors.extend(self._last_sync_report.errors)
            
            # 最終結果判定
            if not files_to_meta_success or not meta_to_files_success:
                report.status = "partial" if (report.files_synced + report.files_added + report.files_updated) > 0 else "failed"
            
            self._last_sync_report = report
            
            self.logger.info(f"Bidirectional sync completed for project {project_id}: "
                           f"status={report.status}, conflicts={len(report.conflicts)}, errors={len(report.errors)}")
            
            return report.status in ["success", "partial"]
        
        except Exception as e:
            self.logger.error(f"Bidirectional sync failed for project {project_id}: {str(e)}")
            return False
        
        finally:
            with self._lock:
                self._active_operations.pop(project_id, None)
    
    def check_integrity(self, project_id: str) -> Dict[str, Any]:
        """
        整合性チェック
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            整合性チェック結果
        """
        try:
            self.logger.info(f"Starting integrity check for project {project_id}")
            
            # プロジェクト存在確認
            project = self.repository.get_project(project_id)
            if not project:
                raise DataIntegrationError(f"Project {project_id} not found")
            
            # 整合性チェック結果
            result = {
                "project_id": project_id,
                "check_timestamp": datetime.now().isoformat(),
                "status": "success",
                "missing_files": [],
                "orphaned_files": [],
                "size_mismatches": [],
                "metadata_errors": [],
                "total_files_checked": 0
            }
            
            # DBファイル参照とファイルシステムの比較
            db_files = {f["file_path"]: f for f in self.repository.get_files_by_query(project_id)}
            fs_files = {f["relative_path"]: f for f in self.fs_manager.list_files(project_id)}
            
            result["total_files_checked"] = len(db_files) + len(fs_files)
            result["total_files"] = len(set(db_files.keys()) | set(fs_files.keys()))  # 重複除去したファイル数
            
            # 不足ファイルチェック（DBにあるがファイルシステムにない）
            for file_path, db_file in db_files.items():
                if file_path not in fs_files:
                    result["missing_files"].append({
                        "file_path": file_path,
                        "file_name": db_file["file_name"],
                        "registered_at": db_file.get("created_at")
                    })
            
            # 孤立ファイルチェック（ファイルシステムにあるがDBにない）
            for file_path, fs_file in fs_files.items():
                if file_path not in db_files:
                    result["orphaned_files"].append({
                        "file_path": file_path,
                        "file_size": fs_file["size"],
                        "modified_at": fs_file.get("modified_at")
                    })
            
            # サイズ不一致チェック
            for file_path in set(db_files.keys()) & set(fs_files.keys()):
                db_file = db_files[file_path]
                fs_file = fs_files[file_path]
                
                if db_file.get("file_size") != fs_file.get("size"):
                    result["size_mismatches"].append({
                        "file_path": file_path,
                        "db_size": db_file.get("file_size"),
                        "fs_size": fs_file.get("size")
                    })
            
            # 一致するファイル数の計算
            consistent_files = set(db_files.keys()) & set(fs_files.keys())
            result["consistent_files"] = len(consistent_files) - len(result["size_mismatches"])
            
            # 不整合のまとめ
            result["inconsistencies"] = (
                result["missing_files"] + 
                result["orphaned_files"] + 
                result["size_mismatches"] + 
                result["metadata_errors"]
            )
            
            # 全体状況の判定
            issues_count = len(result["inconsistencies"])
            
            if issues_count > 0:
                result["status"] = "inconsistent"
            
            self.logger.info(f"Integrity check completed for project {project_id}: "
                           f"status={result['status']}, issues={issues_count}")
            
            return result
        
        except Exception as e:
            self.logger.error(f"Integrity check failed for project {project_id}: {str(e)}")
            return {
                "project_id": project_id,
                "status": "error",
                "error_message": str(e),
                "check_timestamp": datetime.now().isoformat()
            }
    
    def auto_repair_integrity(self, project_id: str) -> bool:
        """
        整合性問題の自動修復
        
        Args:
            project_id: プロジェクトID
        
        Returns:
            修復成功フラグ
        """
        try:
            self.logger.info(f"Starting auto-repair for project {project_id}")
            
            # 整合性チェック実行
            integrity_result = self.check_integrity(project_id)
            
            if integrity_result["status"] == "success":
                self.logger.info(f"No integrity issues found for project {project_id}")
                return True
            
            repair_count = 0
            
            # 孤立ファイルの登録
            for orphaned_file in integrity_result["orphaned_files"]:
                try:
                    file_path = orphaned_file["file_path"]
                    
                    # ファイル情報を再構築
                    fs_file_info = {
                        "relative_path": file_path,
                        "size": orphaned_file["file_size"]
                    }
                    
                    self._register_new_file(project_id, fs_file_info)
                    repair_count += 1
                    self.logger.info(f"Registered orphaned file: {file_path}")
                
                except Exception as e:
                    self.logger.error(f"Failed to register orphaned file {orphaned_file['file_path']}: {str(e)}")
            
            # サイズ不一致の修正（ファイルシステムの値を正とする）
            for size_mismatch in integrity_result["size_mismatches"]:
                try:
                    file_path = size_mismatch["file_path"]
                    new_size = size_mismatch["fs_size"]
                    
                    # DBのファイルサイズを更新
                    file_refs = self.repository.get_files_by_query(project_id)
                    file_ref = [f for f in file_refs if f["file_path"] == file_path]
                    if file_ref:
                        file_id = file_ref[0]["id"]
                        metadata = file_ref[0].get("metadata", {})
                        metadata["auto_repaired"] = True
                        metadata["repaired_at"] = datetime.now().isoformat()
                        metadata["file_size_updated"] = new_size
                        
                        # ファイルサイズ更新のためのSQL実行（直接DB更新）
                        with self.repository.db_manager.transaction() as conn:
                            conn.execute("""
                                UPDATE project_files 
                                SET file_size = ?, metadata = ?
                                WHERE id = ?
                            """, (new_size, json.dumps(metadata), file_id))
                        repair_count += 1
                        self.logger.info(f"Updated file size for {file_path}: {new_size}")
                
                except Exception as e:
                    self.logger.error(f"Failed to update file size for {size_mismatch['file_path']}: {str(e)}")
            
            self.logger.info(f"Auto-repair completed for project {project_id}: {repair_count} issues repaired")
            return repair_count > 0
        
        except Exception as e:
            self.logger.error(f"Auto-repair failed for project {project_id}: {str(e)}")
            return False
    
    def create_project_backup(self, project_id: str, backup_path: str, backup_type: str = "full") -> bool:
        """
        プロジェクトバックアップ作成
        
        Args:
            project_id: プロジェクトID
            backup_path: バックアップ保存先
            backup_type: バックアップタイプ（full/incremental）
        
        Returns:
            バックアップ成功フラグ
        """
        try:
            self.logger.info(f"Starting {backup_type} backup for project {project_id} to {backup_path}")
            
            # プロジェクト存在確認
            project = self.repository.get_project(project_id)
            if not project:
                raise DataIntegrationError(f"Project {project_id} not found")
            
            # バックアップディレクトリ作成
            backup_dir = Path(backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # バックアップメタデータ
            backup_metadata = {
                "project_id": project_id,
                "backup_type": backup_type,
                "created_at": datetime.now().isoformat(),
                "tool_version": "2.0.0"
            }
            
            # プロジェクトメタデータのバックアップ
            project_data = {
                "project": project,
                "workflow_steps": self.repository.get_workflow_steps(project_id),
                "files": self.repository.get_files_by_query(project_id)
            }
            
            # メタデータファイル保存
            metadata_file = backup_dir / "project_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2, default=str)
            
            # バックアップ情報ファイル保存
            backup_info_file = backup_dir / "backup_info.json"
            with open(backup_info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_metadata, f, ensure_ascii=False, indent=2)
            
            # ファイルのバックアップ
            if backup_type == "full":
                # フルバックアップ：すべてのファイルをコピー
                project_dir = self.fs_manager.get_project_directory(project_id)
                if os.path.exists(project_dir):
                    files_backup_dir = backup_dir / "files"
                    shutil.copytree(project_dir, files_backup_dir, dirs_exist_ok=True)
            else:
                # 増分バックアップ：変更されたファイルのみ
                self._create_incremental_backup(project_id, backup_dir)
            
            self.logger.info(f"{backup_type.capitalize()} backup completed for project {project_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Backup failed for project {project_id}: {str(e)}")
            return False
    
    def restore_project_from_backup(self, backup_path: str, target_project_id: Optional[str] = None) -> bool:
        """
        バックアップからプロジェクト復元
        
        Args:
            backup_path: バックアップディレクトリパス
            target_project_id: 復元先プロジェクトID（Noneの場合は元のIDを使用）
        
        Returns:
            復元成功フラグ
        """
        try:
            backup_dir = Path(backup_path)
            
            # バックアップ情報読み込み
            backup_info_file = backup_dir / "backup_info.json"
            if not backup_info_file.exists():
                raise DataIntegrationError(f"Backup info file not found: {backup_info_file}")
            
            with open(backup_info_file, 'r', encoding='utf-8') as f:
                backup_info = json.load(f)
            
            original_project_id = backup_info["project_id"]
            restore_project_id = target_project_id or original_project_id
            
            self.logger.info(f"Starting restore from backup {backup_path} to project {restore_project_id}")
            
            # プロジェクトメタデータ読み込み
            metadata_file = backup_dir / "project_metadata.json"
            if not metadata_file.exists():
                raise DataIntegrationError(f"Project metadata file not found: {metadata_file}")
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # 既存プロジェクトがあれば削除確認
            existing_project = self.repository.get_project(restore_project_id)
            if existing_project:
                self.logger.warning(f"Overwriting existing project {restore_project_id}")
            
            # プロジェクト作成/更新
            project_info = project_data["project"]
            if existing_project:
                # 既存プロジェクト更新
                self.repository.update_project(
                    restore_project_id,
                    project_info["title"],
                    project_info["target_length_minutes"],
                    project_info.get("theme"),
                    project_info.get("status", "draft")
                )
            else:
                # 新規プロジェクト作成
                self.repository.create_project(
                    restore_project_id,
                    project_info["title"],
                    project_info["target_length_minutes"],
                    project_info.get("theme"),
                    project_info.get("status", "draft")
                )
            
            # ワークフローステップ復元
            for step in project_data.get("workflow_steps", []):
                try:
                    self.repository.create_workflow_step(
                        restore_project_id,
                        step["step_name"],
                        step.get("status", "pending"),
                        step.get("input_data"),
                        step.get("output_data"),
                        step.get("error_message")
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to restore workflow step {step['step_name']}: {str(e)}")
            
            # ファイル参照復元
            for file_info in project_data.get("files", []):
                try:
                    self.repository.register_file_reference(
                        restore_project_id,
                        file_info["file_type"],
                        file_info["file_category"],
                        file_info["file_path"],
                        file_info["file_name"],
                        file_info.get("file_size", 0),
                        file_info.get("metadata", {})
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to restore file reference {file_info['file_path']}: {str(e)}")
            
            # ファイル復元
            files_backup_dir = backup_dir / "files"
            if files_backup_dir.exists():
                project_dir = self.fs_manager.get_project_directory(restore_project_id)
                
                # プロジェクトディレクトリ作成
                self.fs_manager.create_project_directory(restore_project_id)
                
                # ファイルコピー
                if os.path.exists(project_dir):
                    shutil.rmtree(project_dir)
                shutil.copytree(files_backup_dir, project_dir)
            
            self.logger.info(f"Project restore completed: {restore_project_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Project restore failed: {str(e)}")
            return False
    
    def get_last_sync_report(self) -> Optional[Dict[str, Any]]:
        """
        最後の同期レポート取得
        
        Returns:
            同期レポート（辞書形式）
        """
        if not self._last_sync_report:
            return None
        
        report = self._last_sync_report
        return {
            "project_id": report.project_id,
            "direction": report.direction,
            "status": report.status,
            "timestamp": report.timestamp.isoformat(),
            "conflicts": [
                {
                    "file_path": c.file_path,
                    "type": c.type,
                    "db_info": c.db_info,
                    "fs_info": c.fs_info,
                    "resolution": c.resolution
                }
                for c in report.conflicts
            ],
            "files_synced": report.files_synced,
            "files_updated": report.files_updated,
            "files_added": report.files_added,
            "files_removed": report.files_removed,
            "errors": report.errors
        }
    
    # プライベートメソッド
    
    def _check_file_integrity(self, project_id: str, db_file: Dict[str, Any]) -> List[ConflictInfo]:
        """ファイル整合性チェック"""
        conflicts = []
        
        try:
            file_path = db_file["file_path"]
            full_path = self.fs_manager.get_project_file_path(project_id, file_path)
            
            if not os.path.exists(full_path):
                return conflicts  # ファイルが存在しない場合は別途処理
            
            # ファイルサイズチェック
            actual_size = os.path.getsize(full_path)
            expected_size = db_file.get("file_size", 0)
            
            if actual_size != expected_size:
                conflicts.append(ConflictInfo(
                    file_path=file_path,
                    type="size_mismatch",
                    db_info={"size": expected_size},
                    fs_info={"size": actual_size}
                ))
        
        except Exception as e:
            self.logger.error(f"Failed to check file integrity for {db_file.get('file_path')}: {str(e)}")
        
        return conflicts
    
    def _create_file_from_metadata(self, project_id: str, db_file: Dict[str, Any]) -> None:
        """メタデータからファイル作成"""
        try:
            file_path = db_file["file_path"]
            
            # デフォルトコンテンツ作成
            if db_file["file_type"] == "script":
                default_content = json.dumps({
                    "title": "Generated Script",
                    "segments": [],
                    "created_from_metadata": True,
                    "created_at": datetime.now().isoformat()
                }, ensure_ascii=False, indent=2)
            else:
                default_content = ""
            
            self.fs_manager.create_file(project_id, file_path, default_content)
            self.logger.info(f"Created file from metadata: {file_path}")
        
        except Exception as e:
            self.logger.error(f"Failed to create file from metadata {db_file.get('file_path')}: {str(e)}")
    
    def _update_file_metadata(self, project_id: str, fs_file: Dict[str, Any], db_file: Dict[str, Any]) -> None:
        """ファイルメタデータ更新"""
        try:
            file_id = db_file["id"]
            
            # ファイルシステムの情報でDB更新
            updates = {}
            if fs_file.get("size") != db_file.get("file_size"):
                updates["file_size"] = fs_file["size"]
            
            metadata = db_file.get("metadata", {})
            metadata["last_fs_sync"] = datetime.now().isoformat()
            
            if updates:
                self.repository.update_file_metadata(file_id, updates, metadata)
        
        except Exception as e:
            self.logger.error(f"Failed to update file metadata for {fs_file.get('relative_path')}: {str(e)}")
    
    def _register_new_file(self, project_id: str, fs_file: Dict[str, Any]) -> None:
        """新規ファイル登録"""
        try:
            file_path = fs_file["relative_path"]
            file_name = os.path.basename(file_path)
            
            # ファイル拡張子からタイプ推定
            ext = os.path.splitext(file_name)[1].lower()
            file_type = "other"
            if ext in [".json", ".txt"]:
                file_type = "script"
            elif ext in [".wav", ".mp3"]:
                file_type = "audio"
            elif ext in [".mp4", ".avi"]:
                file_type = "video"
            elif ext in [".png", ".jpg", ".jpeg"]:
                file_type = "image"
            
            # ディレクトリからカテゴリ推定
            file_category = "other"
            if "/temp/" in file_path:
                file_category = "temp"
            elif "/final/" in file_path:
                file_category = "output"
            elif "/original/" in file_path:
                file_category = "input"
            else:
                file_category = "intermediate"
            
            metadata = {
                "auto_registered": True,
                "registered_at": datetime.now().isoformat()
            }
            
            self.repository.register_file_reference(
                project_id,
                file_type,
                file_category,
                file_path,
                file_name,
                fs_file.get("size", 0),
                None,  # mime_type
                metadata
            )
            
            self.logger.info(f"Registered new file: {file_path}")
        
        except Exception as e:
            self.logger.error(f"Failed to register new file {fs_file.get('relative_path')}: {str(e)}")
    
    def _create_incremental_backup(self, project_id: str, backup_dir: Path) -> None:
        """増分バックアップ作成"""
        try:
            # 前回バックアップとの差分チェック（簡易実装）
            cutoff_time = datetime.now() - timedelta(days=1)  # 1日以内に変更されたファイル
            
            files_backup_dir = backup_dir / "files"
            files_backup_dir.mkdir(exist_ok=True)
            
            # 変更されたファイルのみコピー
            fs_files = self.fs_manager.list_files(project_id)
            
            for fs_file in fs_files:
                try:
                    file_path = fs_file["relative_path"]
                    full_path = self.fs_manager.get_project_file_path(project_id, file_path)
                    
                    # ファイルの更新時刻チェック
                    if os.path.exists(full_path):
                        mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
                        if mtime > cutoff_time:
                            # 変更されたファイルをバックアップ
                            backup_file_path = files_backup_dir / file_path
                            backup_file_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(full_path, backup_file_path)
                
                except Exception as e:
                    self.logger.warning(f"Failed to backup file {fs_file.get('relative_path')}: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Incremental backup failed: {str(e)}")

    def create_incremental_backup(self, project_id: str, backup_path: str) -> bool:
        """
        増分バックアップを作成
        
        Args:
            project_id: プロジェクトID
            backup_path: バックアップ先パス
            
        Returns:
            bool: バックアップ成功時True
        """
        try:
            backup_dir = Path(backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 増分バックアップ実行
            self._create_incremental_backup(project_id, backup_dir)
            
            # バックアップ情報ファイル作成
            backup_info = {
                "project_id": project_id,
                "backup_type": "incremental",
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            with open(backup_dir / "backup_info.json", "w", encoding="utf-8") as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Incremental backup created: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create incremental backup: {str(e)}")
            return False

    def acquire_operation_lock(self, project_id: str) -> bool:
        """
        操作ロックを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: ロック取得成功時True
        """
        try:
            if project_id in self._operation_locks:
                return False  # 既にロックされている
            
            self._operation_locks[project_id] = datetime.now()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to acquire operation lock for {project_id}: {str(e)}")
            return False

    def release_operation_lock(self, project_id: str) -> bool:
        """
        操作ロックを解放
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: ロック解放成功時True
        """
        try:
            if project_id in self._operation_locks:
                del self._operation_locks[project_id]
                return True
            
            return False  # ロックが存在しない
            
        except Exception as e:
            self.logger.error(f"Failed to release operation lock for {project_id}: {str(e)}")
            return False 