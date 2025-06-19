"""
タイトル生成用DAO（データアクセスオブジェクト）

データベースアクセスロジックをビジネスロジックから分離
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

from src.core.database_manager import DatabaseManager


class TitleGenerationDAO:
    """タイトル生成のデータアクセス層"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初期化
        
        Args:
            db_manager: データベースマネージャー
        """
        self.db_manager = db_manager
    
    def get_project_data(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトの基本データを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            プロジェクトデータ辞書
            
        Raises:
            ValueError: プロジェクトが見つからない場合
        """
        query = """
        SELECT theme, target_length_minutes, config_json
        FROM projects 
        WHERE id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        
        if not result:
            raise ValueError(f"プロジェクト {project_id} が見つかりません")
        
        theme, target_length, config_json = result
        
        return {
            "theme": theme,
            "target_length_minutes": target_length,
            "config": json.loads(config_json) if config_json else {}
        }
    
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """
        スクリプト生成結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            スクリプトデータ辞書
            
        Raises:
            ValueError: スクリプトデータが見つからない場合
        """
        query = """
        SELECT status, output_data, completed_at
        FROM workflow_steps
        WHERE project_id = ? AND step_name = 'script_generation'
        ORDER BY completed_at DESC
        LIMIT 1
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        
        if not result:
            raise ValueError(f"プロジェクト {project_id} のスクリプトデータが見つかりません")
        
        status, output_data_json, completed_at = result
        
        return {
            "status": status,
            "output_data": json.loads(output_data_json) if output_data_json else {},
            "completed_at": completed_at
        }
    
    def save_title_result(
        self, 
        project_id: str, 
        generated_titles: Any,  # GeneratedTitles型
        status: str = "completed"
    ) -> None:
        """
        タイトル生成結果をデータベースに保存
        
        Args:
            project_id: プロジェクトID
            generated_titles: 生成されたタイトル情報
            status: ステップ実行状態
        """
        current_time = datetime.now().isoformat()
        
        # タイトルデータをJSONにシリアライズ
        title_data = {
            "generated_titles": {
                "candidates": [
                    {
                        "title": candidate.title,
                        "ctr_score": candidate.ctr_score,
                        "keyword_score": candidate.keyword_score,
                        "length_score": candidate.length_score,
                        "total_score": candidate.total_score,
                        "reasons": candidate.reasons
                    }
                    for candidate in generated_titles.candidates
                ],
                "selected_title": generated_titles.selected_title,
                "generation_timestamp": generated_titles.generation_timestamp.isoformat()
            }
        }
        
        # workflow_stepsテーブルに保存
        insert_query = """
        INSERT OR REPLACE INTO workflow_steps 
        (project_id, step_number, step_name, status, output_data, completed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        self.db_manager.execute_query(
            insert_query,
            (
                project_id,
                3,  # タイトル生成はステップ3
                "title_generation",
                status,
                json.dumps(title_data, ensure_ascii=False),
                current_time
            )
        )
        
        # 注意: projectsテーブルにselected_titleカラムがないため、
        # タイトル情報はworkflow_stepsテーブルのoutput_dataに保存されます
    
    def get_title_result(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        保存されたタイトル生成結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            タイトル結果辞書（見つからない場合はNone）
        """
        query = """
        SELECT status, output_data, completed_at
        FROM workflow_steps
        WHERE project_id = ? AND step_name = 'title_generation'
        ORDER BY completed_at DESC
        LIMIT 1
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        
        if not result:
            return None
        
        status, output_data_json, completed_at = result
        
        return {
            "status": status,
            "output_data": json.loads(output_data_json) if output_data_json else {},
            "completed_at": completed_at
        }
    
    def register_title_files(
        self, 
        project_id: str, 
        title_analysis_path: str
    ) -> None:
        """
        タイトル関連ファイルをproject_filesテーブルに登録
        
        Args:
            project_id: プロジェクトID
            title_analysis_path: タイトル分析ファイルパス
        """
        current_time = datetime.now().isoformat()
        
        # タイトル分析ファイルを登録
        # 注意: project_filesテーブルの実際のスキーマに合わせて調整
        insert_query = """
        INSERT INTO project_files 
        (project_id, file_type, file_path, file_size, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        """
        
        import os
        
        # ファイルサイズ取得（ファイルが存在しない場合は0）
        file_size = 0
        if os.path.exists(title_analysis_path):
            file_size = os.path.getsize(title_analysis_path)
        
        metadata = {
            "file_name": os.path.basename(title_analysis_path),
            "file_category": "output",
            "created_at": current_time,
            "description": "タイトル分析結果ファイル"
        }
        
        self.db_manager.execute_query(
            insert_query,
            (
                project_id,
                "metadata",
                title_analysis_path,
                file_size,
                json.dumps(metadata, ensure_ascii=False)
            )
        )
    
    def get_project_info(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトの詳細情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            プロジェクト情報辞書
            
        Raises:
            ValueError: プロジェクトが見つからない場合
        """
        query = """
        SELECT id, theme, target_length_minutes, created_at, config_json
        FROM projects
        WHERE id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        
        if not result:
            raise ValueError(f"プロジェクト {project_id} が見つかりません")
        
        project_id, theme, target_length, created_at, config_json = result
        
        return {
            "id": project_id,
            "theme": theme,
            "target_length_minutes": target_length,
            "created_at": created_at,
            "config": json.loads(config_json) if config_json else {}
        }
    
    def get_workflow_step_result(self, project_id: str, step_name: str) -> Optional[Dict[str, Any]]:
        """
        指定されたワークフローステップの結果を取得
        
        Args:
            project_id: プロジェクトID
            step_name: ステップ名
            
        Returns:
            ステップ結果辞書（見つからない場合はNone）
        """
        query = """
        SELECT step_number, status, output_data, completed_at, error_message
        FROM workflow_steps
        WHERE project_id = ? AND step_name = ?
        ORDER BY completed_at DESC
        LIMIT 1
        """
        
        result = self.db_manager.fetch_one(query, (project_id, step_name))
        
        if not result:
            return None
        
        step_number, status, output_data_json, completed_at, error_message = result
        
        return {
            "step_number": step_number,
            "step_name": step_name,
            "status": status,
            "output_data": json.loads(output_data_json) if output_data_json else {},
            "completed_at": completed_at,
            "error_message": error_message
        } 