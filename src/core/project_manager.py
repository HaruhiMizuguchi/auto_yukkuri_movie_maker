"""
プロジェクト管理システム (1-1-1: プロジェクト作成機能)

このモジュールは以下の機能を提供します：
- プロジェクト作成機能
- ディレクトリ構造自動生成
- プロジェクトID管理
- メタデータ保存
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from .database_manager import DatabaseManager


class ProjectManager:
    """
    プロジェクト管理システム
    
    プロジェクトの作成、ディレクトリ構造の自動生成、
    プロジェクトID管理、メタデータ保存を担当する。
    """
    
    # flow_definition.yamlで定義されたディレクトリ構造
    REQUIRED_SUBDIRECTORIES = [
        "files/scripts",    # スクリプト関連
        "files/audio",      # 音声ファイル
        "files/video",      # 動画ファイル
        "files/images",     # 画像ファイル
        "files/subtitles",  # 字幕ファイル
        "files/metadata",   # メタデータファイル
        "config",          # 設定ファイル
        "logs",            # ログファイル
        "cache"            # キャッシュファイル
    ]
    
    def __init__(self, db_manager: DatabaseManager, projects_base_dir: str):
        """
        プロジェクトマネージャーを初期化
        
        Args:
            db_manager: データベース管理インスタンス
            projects_base_dir: プロジェクト格納ベースディレクトリ
        """
        self.db_manager = db_manager
        self.projects_base_dir = projects_base_dir
        
        # ベースディレクトリが存在しない場合は作成
        if not os.path.exists(self.projects_base_dir):
            os.makedirs(self.projects_base_dir, exist_ok=True)
    
    def create_project(
        self,
        theme: str,
        target_length_minutes: int = 5,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        新しいプロジェクトを作成
        
        Args:
            theme: プロジェクトのテーマ
            target_length_minutes: 目標動画長（分）
            config: プロジェクト設定（オプション）
            
        Returns:
            str: 作成されたプロジェクトのID（UUID形式）
            
        Raises:
            ValueError: 無効なパラメータが指定された場合
            OSError: ディレクトリ作成に失敗した場合
        """
        # 入力値のバリデーション
        self._validate_project_params(theme, target_length_minutes)
        
        # 一意のプロジェクトIDを生成
        project_id = str(uuid.uuid4())
        
        # 現在時刻
        now = datetime.now().isoformat()
        
        # 設定をJSONに変換（デフォルト値を含む）
        config = config or {}
        config_json = json.dumps(config, ensure_ascii=False, indent=2)
        
        # トランザクション開始
        with self.db_manager.transaction():
            try:
                # データベースにプロジェクト情報を保存
                self.db_manager.execute_query(
                    """
                    INSERT INTO projects (
                        id, theme, target_length_minutes, status,
                        config_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        theme,
                        target_length_minutes,
                        "created",
                        config_json,
                        now,
                        now
                    )
                )
                
                # プロジェクトディレクトリ構造を作成
                self._create_project_directory_structure(project_id)
                
            except Exception as e:
                # エラーが発生した場合、トランザクションは自動的にロールバックされる
                raise
        
        return project_id
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        プロジェクト情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Dict[str, Any]: プロジェクト情報、存在しない場合はNone
        """
        result = self.db_manager.fetch_one(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)
        )
        
        if result:
            # 辞書形式に変換
            columns = [
                "id", "theme", "target_length_minutes", "status",
                "config_json", "created_at", "updated_at", "output_summary_json"
            ]
            return dict(zip(columns, result))
        
        return None
    
    def list_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        プロジェクト一覧を取得
        
        Args:
            limit: 取得件数の上限（指定しない場合はすべて）
            
        Returns:
            List[Dict[str, Any]]: プロジェクト一覧
        """
        query = "SELECT * FROM projects ORDER BY created_at DESC"
        params = ()
        
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        
        results = self.db_manager.fetch_all(query, params)
        
        # 辞書形式のリストに変換
        columns = [
            "id", "theme", "target_length_minutes", "status",
            "config_json", "created_at", "updated_at", "output_summary_json"
        ]
        
        return [dict(zip(columns, row)) for row in results]
    
    def update_project_status(self, project_id: str, status: str) -> bool:
        """
        プロジェクトの状態を更新
        
        Args:
            project_id: プロジェクトID
            status: 新しい状態
            
        Returns:
            bool: 更新が成功した場合True
        """
        now = datetime.now().isoformat()
        
        rows_affected = self.db_manager.execute_query(
            "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, project_id)
        )
        
        return rows_affected > 0
    
    def get_project_directory(self, project_id: str) -> str:
        """
        プロジェクトディレクトリのパスを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            str: プロジェクトディレクトリの絶対パス
        """
        return os.path.join(self.projects_base_dir, project_id)
    
    def _validate_project_params(self, theme: str, target_length_minutes: int) -> None:
        """
        プロジェクトパラメータのバリデーション
        
        Args:
            theme: プロジェクトのテーマ
            target_length_minutes: 目標動画長（分）
            
        Raises:
            ValueError: バリデーションエラー
        """
        if not theme or not theme.strip():
            raise ValueError("テーマは必須です")
        
        if target_length_minutes <= 0:
            raise ValueError("目標動画長は1分以上である必要があります")
        
        if target_length_minutes > 60:
            raise ValueError("目標動画長は60分以下である必要があります")
    
    def _create_project_directory_structure(self, project_id: str) -> None:
        """
        プロジェクトディレクトリ構造を作成
        
        Args:
            project_id: プロジェクトID
            
        Raises:
            OSError: ディレクトリ作成に失敗した場合
        """
        project_dir = self.get_project_directory(project_id)
        
        try:
            # プロジェクトルートディレクトリを作成
            os.makedirs(project_dir, exist_ok=True)
            
            # 必要なサブディレクトリを作成
            for subdir in self.REQUIRED_SUBDIRECTORIES:
                subdir_path = os.path.join(project_dir, subdir)
                os.makedirs(subdir_path, exist_ok=True)
                
        except OSError as e:
            # ディレクトリ作成に失敗した場合、作成済みのディレクトリを削除してからエラーを再発生
            if os.path.exists(project_dir):
                import shutil
                shutil.rmtree(project_dir, ignore_errors=True)
            raise OSError(f"プロジェクトディレクトリの作成に失敗しました: {e}")
    
    def delete_project(self, project_id: str) -> bool:
        """
        プロジェクトを削除（論理削除）
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: 削除が成功した場合True
        """
        return self.update_project_status(project_id, "deleted")
    
    def get_project_config(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        プロジェクトの設定情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Dict[str, Any]: 設定情報、存在しない場合はNone
        """
        project = self.get_project(project_id)
        if project and project.get("config_json"):
            try:
                return json.loads(project["config_json"])
            except json.JSONDecodeError:
                return {}
        return None
    
    def update_project_config(
        self,
        project_id: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        プロジェクトの設定情報を更新
        
        Args:
            project_id: プロジェクトID
            config: 新しい設定情報
            
        Returns:
            bool: 更新が成功した場合True
        """
        config_json = json.dumps(config, ensure_ascii=False, indent=2)
        now = datetime.now().isoformat()
        
        rows_affected = self.db_manager.execute_query(
            "UPDATE projects SET config_json = ?, updated_at = ? WHERE id = ?",
            (config_json, now, project_id)
        )
        
        return rows_affected > 0 