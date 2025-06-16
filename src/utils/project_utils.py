"""
プロジェクト管理ユーティリティ

ProjectManagerやDatabaseManagerの複雑さを隠し、
シンプルで使いやすい高レベル関数を提供します。
"""

import os
import logging
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import json
from datetime import datetime

from ..core.project_manager import ProjectManager
from ..core.database_manager import DatabaseManager
from ..core.project_state_manager import ProjectStateManager

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_DB_PATH = "data/yukkuri_tool.db"
DEFAULT_PROJECTS_DIR = "projects"

# グローバルマネージャーのインスタンス（遅延初期化）
_db_manager: Optional[DatabaseManager] = None
_project_manager: Optional[ProjectManager] = None
_state_manager: Optional[ProjectStateManager] = None


def _get_managers() -> tuple[DatabaseManager, ProjectManager, ProjectStateManager]:
    """マネージャーのシングルトンインスタンスを取得"""
    global _db_manager, _project_manager, _state_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager(DEFAULT_DB_PATH)
        _db_manager.initialize()
    
    if _project_manager is None:
        _project_manager = ProjectManager(_db_manager, DEFAULT_PROJECTS_DIR)
    
    if _state_manager is None:
        _state_manager = ProjectStateManager(_db_manager)
    
    return _db_manager, _project_manager, _state_manager


def create_project(
    theme: str,
    target_length_minutes: int = 5,
    project_name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> str:
    """
    新しいプロジェクトを簡単に作成する
    
    Args:
        theme: プロジェクトのテーマ
        target_length_minutes: 目標動画長（分）
        project_name: プロジェクト名（指定しない場合はテーマを使用）
        description: プロジェクトの説明
        tags: プロジェクトのタグ
    
    Returns:
        str: 作成されたプロジェクトのID
    
    Examples:
        >>> # 最もシンプルな使用例
        >>> project_id = create_project("Python入門")
        >>> print(f"プロジェクト作成: {project_id}")
        
        >>> # 詳細設定
        >>> project_id = create_project(
        ...     theme="機械学習基礎",
        ...     target_length_minutes=8,
        ...     project_name="ML入門動画",
        ...     description="初心者向けの機械学習解説動画",
        ...     tags=["教育", "プログラミング", "AI"]
        ... )
    """
    try:
        _, project_manager, _ = _get_managers()
        
        # 設定作成
        config = {
            "name": project_name or theme,
            "description": description or f"{theme}についてのゆっくり動画",
            "tags": tags or [],
            "created_by": "project_utils",
            "auto_created": True
        }
        
        project_id = project_manager.create_project(
            theme=theme,
            target_length_minutes=target_length_minutes,
            config=config
        )
        
        logger.info(f"プロジェクト作成完了: {theme} -> {project_id}")
        return project_id
        
    except Exception as e:
        logger.error(f"プロジェクト作成エラー: {e}")
        raise RuntimeError(f"プロジェクトの作成に失敗しました: {e}")


def get_project_info(project_id: str) -> Optional[Dict[str, Any]]:
    """
    プロジェクト情報を取得する
    
    Args:
        project_id: プロジェクトID
    
    Returns:
        Dict[str, Any]: プロジェクト情報（存在しない場合はNone）
    
    Examples:
        >>> project = get_project_info("your-project-id")
        >>> if project:
        ...     print(f"テーマ: {project['theme']}")
        ...     print(f"状態: {project['status']}")
        ...     print(f"作成日: {project['created_at']}")
    """
    try:
        _, project_manager, _ = _get_managers()
        return project_manager.get_project(project_id)
    except Exception as e:
        logger.error(f"プロジェクト情報取得エラー: {e}")
        return None


def list_projects(
    limit: Optional[int] = 20,
    status_filter: Optional[str] = None,
    include_config: bool = False
) -> List[Dict[str, Any]]:
    """
    プロジェクト一覧を取得する
    
    Args:
        limit: 取得件数の上限
        status_filter: 状態でフィルタ（例: "created", "completed"）
        include_config: 設定情報も含めるかどうか
    
    Returns:
        List[Dict[str, Any]]: プロジェクト一覧
    
    Examples:
        >>> # 最新20件を取得
        >>> projects = list_projects()
        >>> for project in projects:
        ...     print(f"{project['theme']} ({project['status']})")
        
        >>> # 完了済みプロジェクトのみ
        >>> completed = list_projects(status_filter="completed")
    """
    try:
        _, project_manager, _ = _get_managers()
        projects = project_manager.list_projects(limit)
        
        # 状態フィルタリング
        if status_filter:
            projects = [p for p in projects if p.get("status") == status_filter]
        
        # 設定情報の解析
        if include_config:
            for project in projects:
                config_json = project.get("config_json", "{}")
                try:
                    project["config"] = json.loads(config_json)
                except (json.JSONDecodeError, TypeError):
                    project["config"] = {}
        
        return projects
        
    except Exception as e:
        logger.error(f"プロジェクト一覧取得エラー: {e}")
        return []


def update_project_status(project_id: str, status: str) -> bool:
    """
    プロジェクト状態を更新する
    
    Args:
        project_id: プロジェクトID
        status: 新しい状態
    
    Returns:
        bool: 更新成功の場合True
    
    Examples:
        >>> # プロジェクトを開始状態に
        >>> success = update_project_status("project-id", "in_progress")
        >>> if success:
        ...     print("状態更新完了")
    """
    try:
        _, project_manager, _ = _get_managers()
        return project_manager.update_project_status(project_id, status)
    except Exception as e:
        logger.error(f"プロジェクト状態更新エラー: {e}")
        return False


def get_project_progress(project_id: str) -> Dict[str, Any]:
    """
    プロジェクトの進捗を取得する
    
    Args:
        project_id: プロジェクトID
    
    Returns:
        Dict[str, Any]: 進捗情報
    
    Examples:
        >>> progress = get_project_progress("project-id")
        >>> print(f"完了率: {progress['completion_percentage']:.1f}%")
        >>> print(f"完了ステップ: {progress['completed_steps']}/{progress['total_steps']}")
    """
    try:
        _, _, state_manager = _get_managers()
        return state_manager.get_project_progress(project_id)
    except Exception as e:
        logger.error(f"進捗取得エラー: {e}")
        return {
            "total_steps": 0,
            "completed_steps": 0,
            "completion_percentage": 0.0,
            "error": str(e)
        }


def get_project_directory(project_id: str) -> Optional[str]:
    """
    プロジェクトディレクトリのパスを取得する
    
    Args:
        project_id: プロジェクトID
    
    Returns:
        Optional[str]: ディレクトリパス（存在しない場合はNone）
    
    Examples:
        >>> dir_path = get_project_directory("project-id")
        >>> if dir_path:
        ...     print(f"プロジェクトディレクトリ: {dir_path}")
    """
    try:
        _, project_manager, _ = _get_managers()
        return project_manager.get_project_directory(project_id)
    except Exception as e:
        logger.error(f"プロジェクトディレクトリ取得エラー: {e}")
        return None


def delete_project(project_id: str, confirm: bool = False) -> bool:
    """
    プロジェクトを削除する
    
    Args:
        project_id: プロジェクトID
        confirm: 削除確認（安全のため明示的にTrueを指定）
    
    Returns:
        bool: 削除成功の場合True
    
    Examples:
        >>> # 安全のため明示的に確認が必要
        >>> success = delete_project("project-id", confirm=True)
        >>> if success:
        ...     print("プロジェクト削除完了")
    """
    if not confirm:
        logger.warning("プロジェクト削除には confirm=True が必要です")
        return False
    
    try:
        _, project_manager, _ = _get_managers()
        return project_manager.delete_project(project_id)
    except Exception as e:
        logger.error(f"プロジェクト削除エラー: {e}")
        return False


def initialize_project_workflow(
    project_id: str,
    workflow_type: str = "standard"
) -> bool:
    """
    プロジェクトのワークフローを初期化する
    
    Args:
        project_id: プロジェクトID
        workflow_type: ワークフロータイプ（"standard", "simple", "full"）
    
    Returns:
        bool: 初期化成功の場合True
    
    Examples:
        >>> # 標準ワークフローで初期化
        >>> success = initialize_project_workflow("project-id")
        >>> if success:
        ...     print("ワークフロー初期化完了")
    """
    try:
        _, _, state_manager = _get_managers()
        
        # ワークフロー定義
        workflow_definitions = {
            "simple": [
                {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
                {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
                {"step_number": 3, "step_name": "tts_generation", "display_name": "音声生成"}
            ],
            "standard": [
                {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
                {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
                {"step_number": 3, "step_name": "title_generation", "display_name": "タイトル生成"},
                {"step_number": 4, "step_name": "tts_generation", "display_name": "音声生成"},
                {"step_number": 5, "step_name": "video_composition", "display_name": "動画合成"}
            ],
            "full": [
                {"step_number": 1, "step_name": "theme_selection", "display_name": "テーマ選定"},
                {"step_number": 2, "step_name": "script_generation", "display_name": "スクリプト生成"},
                {"step_number": 3, "step_name": "title_generation", "display_name": "タイトル生成"},
                {"step_number": 4, "step_name": "tts_generation", "display_name": "音声生成"},
                {"step_number": 5, "step_name": "character_synthesis", "display_name": "立ち絵合成"},
                {"step_number": 6, "step_name": "background_generation", "display_name": "背景生成"},
                {"step_number": 7, "step_name": "video_composition", "display_name": "動画合成"},
                {"step_number": 8, "step_name": "youtube_upload", "display_name": "YouTube投稿"}
            ]
        }
        
        workflow_def = workflow_definitions.get(workflow_type, workflow_definitions["standard"])
        state_manager.initialize_workflow_steps(project_id, workflow_def)
        
        logger.info(f"ワークフロー初期化完了: {workflow_type} ({len(workflow_def)}ステップ)")
        return True
        
    except Exception as e:
        logger.error(f"ワークフロー初期化エラー: {e}")
        return False


def get_estimated_remaining_time(project_id: str) -> float:
    """
    プロジェクトの推定残り時間を取得する
    
    Args:
        project_id: プロジェクトID
    
    Returns:
        float: 推定残り時間（秒）
    
    Examples:
        >>> remaining = get_estimated_remaining_time("project-id")
        >>> minutes = remaining / 60
        >>> print(f"推定残り時間: {minutes:.1f}分")
    """
    try:
        _, _, state_manager = _get_managers()
        return state_manager.calculate_estimated_remaining_time(project_id)
    except Exception as e:
        logger.error(f"残り時間推定エラー: {e}")
        return 0.0


def find_projects_by_theme(theme_keyword: str) -> List[Dict[str, Any]]:
    """
    テーマキーワードでプロジェクトを検索する
    
    Args:
        theme_keyword: テーマに含まれるキーワード
    
    Returns:
        List[Dict[str, Any]]: マッチしたプロジェクトのリスト
    
    Examples:
        >>> # "Python"を含むプロジェクトを検索
        >>> python_projects = find_projects_by_theme("Python")
        >>> for project in python_projects:
        ...     print(f"{project['theme']} ({project['created_at']})")
    """
    try:
        all_projects = list_projects(limit=None)
        keyword_lower = theme_keyword.lower()
        
        matched_projects = [
            project for project in all_projects
            if keyword_lower in project.get("theme", "").lower()
        ]
        
        logger.info(f"テーマ検索結果: '{theme_keyword}' -> {len(matched_projects)}件")
        return matched_projects
        
    except Exception as e:
        logger.error(f"プロジェクト検索エラー: {e}")
        return []


def cleanup_incomplete_projects(dry_run: bool = True) -> List[str]:
    """
    未完了の古いプロジェクトをクリーンアップする
    
    Args:
        dry_run: 実際の削除を行わず、削除対象のみ表示
    
    Returns:
        List[str]: クリーンアップ対象のプロジェクトIDリスト
    
    Examples:
        >>> # 削除対象を確認
        >>> targets = cleanup_incomplete_projects(dry_run=True)
        >>> print(f"削除対象: {len(targets)}件")
        
        >>> # 実際に削除実行
        >>> if input("削除しますか？(y/N): ").lower() == 'y':
        ...     cleanup_incomplete_projects(dry_run=False)
    """
    try:
        all_projects = list_projects(limit=None)
        
        # 30日以上前の未完了プロジェクトを対象
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)
        
        targets = []
        for project in all_projects:
            created_at_str = project.get("created_at")
            status = project.get("status", "")
            
            if created_at_str and status in ["created", "failed"]:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at < cutoff_date:
                        targets.append(project["id"])
                except ValueError:
                    continue
        
        if not dry_run:
            _, project_manager, _ = _get_managers()
            for project_id in targets:
                project_manager.delete_project(project_id)
            logger.info(f"プロジェクトクリーンアップ完了: {len(targets)}件削除")
        else:
            logger.info(f"クリーンアップ対象: {len(targets)}件（dry_run=True）")
        
        return targets
        
    except Exception as e:
        logger.error(f"プロジェクトクリーンアップエラー: {e}")
        return []


def export_project_summary(
    project_id: str,
    output_path: Optional[Union[str, Path]] = None
) -> Optional[str]:
    """
    プロジェクトサマリーをJSONファイルにエクスポートする
    
    Args:
        project_id: プロジェクトID
        output_path: 出力ファイルパス（指定しない場合は自動生成）
    
    Returns:
        Optional[str]: エクスポートされたファイルパス
    
    Examples:
        >>> # 自動的にファイル名を生成
        >>> exported = export_project_summary("project-id")
        >>> if exported:
        ...     print(f"エクスポート完了: {exported}")
    """
    try:
        project_info = get_project_info(project_id)
        if not project_info:
            logger.error(f"プロジェクトが見つかりません: {project_id}")
            return None
        
        progress = get_project_progress(project_id)
        remaining_time = get_estimated_remaining_time(project_id)
        
        summary = {
            "project_info": project_info,
            "progress": progress,
            "estimated_remaining_time_seconds": remaining_time,
            "exported_at": datetime.now().isoformat(),
            "export_version": "1.0"
        }
        
        if output_path is None:
            safe_theme = "".join(c if c.isalnum() or c in "._-" else "_" for c in project_info["theme"])
            output_path = f"project_summary_{safe_theme}_{project_id[:8]}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"プロジェクトサマリーエクスポート完了: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"プロジェクトサマリーエクスポートエラー: {e}")
        return None


# 便利な統計関数
def get_project_statistics() -> Dict[str, Any]:
    """
    全プロジェクトの統計情報を取得する
    
    Returns:
        Dict[str, Any]: 統計情報
    
    Examples:
        >>> stats = get_project_statistics()
        >>> print(f"総プロジェクト数: {stats['total_projects']}")
        >>> print(f"完了率: {stats['completion_rate']:.1f}%")
    """
    try:
        all_projects = list_projects(limit=None)
        
        if not all_projects:
            return {
                "total_projects": 0,
                "completed_projects": 0,
                "completion_rate": 0.0,
                "status_breakdown": {},
                "average_length_minutes": 0.0
            }
        
        # 状態別集計
        status_counts = {}
        total_length = 0
        
        for project in all_projects:
            status = project.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            total_length += project.get("target_length_minutes", 0)
        
        completed = status_counts.get("completed", 0)
        total = len(all_projects)
        
        return {
            "total_projects": total,
            "completed_projects": completed,
            "completion_rate": (completed / total * 100) if total > 0 else 0.0,
            "status_breakdown": status_counts,
            "average_length_minutes": total_length / total if total > 0 else 0.0
        }
        
    except Exception as e:
        logger.error(f"統計情報取得エラー: {e}")
        return {"error": str(e)} 