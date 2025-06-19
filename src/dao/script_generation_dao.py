"""
スクリプト生成用DAO（データアクセスオブジェクト）

データベースアクセスロジックをビジネスロジックから分離
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

from src.core.database_manager import DatabaseManager


class ScriptGenerationDAO:
    """スクリプト生成のデータアクセス層"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初期化
        
        Args:
            db_manager: データベースマネージャー
        """
        self.db_manager = db_manager
    
    def get_project_theme(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトのテーマ情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            テーマ情報辞書
            
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
        
        theme, target_length_minutes, config_json = result
        
        return {
            "theme": theme,
            "target_length_minutes": target_length_minutes,
            "config": json.loads(config_json) if config_json else {}
        }
    
    def get_previous_step_output(self, project_id: str, step_name: str = "theme_selection") -> Optional[Dict[str, Any]]:
        """
        前のステップの出力データを取得
        
        Args:
            project_id: プロジェクトID
            step_name: ステップ名（デフォルト: theme_selection）
            
        Returns:
            前ステップの出力データ、見つからない場合はNone
        """
        query = """
        SELECT output_data
        FROM workflow_steps
        WHERE project_id = ? AND step_name = ? AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
        """
        
        result = self.db_manager.fetch_one(query, (project_id, step_name))
        
        if not result:
            return None
        
        output_data_json = result[0]
        return json.loads(output_data_json) if output_data_json else {}
    
    def get_script_config(self, project_id: str) -> Dict[str, Any]:
        """
        スクリプト生成設定を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            スクリプト設定辞書
        """
        # プロジェクト設定から取得
        project_data = self.get_project_theme(project_id)
        project_config = project_data.get("config", {})
        script_config = project_config.get("script_generation", {})
        
        # デフォルト値をマージ
        default_config = {
            "target_duration_minutes": 5,
            "speaker_count": 2,
            "speaker_names": ["reimu", "marisa"],
            "tone": "casual"
        }
        
        # プロジェクト設定でデフォルト値を上書き
        for key, default_value in default_config.items():
            if key not in script_config:
                script_config[key] = default_value
        
        return script_config
    
    def save_script_result(
        self, 
        project_id: str, 
        script: "GeneratedScript", 
        status: str = "completed"
    ) -> None:
        """
        スクリプト生成結果を保存
        
        Args:
            project_id: プロジェクトID
            script: 生成されたスクリプト
            status: ステップステータス
        """
        # スクリプトデータをJSONに変換
        script_data = {
            "segments": [
                {
                    "segment_id": seg.segment_id,
                    "speaker": seg.speaker,
                    "text": seg.text,
                    "estimated_duration": seg.estimated_duration,
                    "emotion": seg.emotion
                }
                for seg in script.segments
            ],
            "total_estimated_duration": script.total_estimated_duration,
            "total_character_count": script.total_character_count,
            "generation_timestamp": script.generation_timestamp.isoformat()
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
                2,  # script_generation is step 2 according to flow_definition.yaml
                "script_generation",
                status,
                json.dumps(script_data, ensure_ascii=False),
                datetime.now().isoformat()
            )
        )
        
        # プロジェクト統計の推定時間を更新
        update_stats_query = """
        INSERT OR REPLACE INTO project_statistics 
        (project_id, total_duration)
        VALUES (?, ?)
        """
        
        self.db_manager.execute_query(
            update_stats_query,
            (project_id, script.total_estimated_duration)
        )
    
    def get_script_result(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        保存されたスクリプト結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            スクリプト結果データ、見つからない場合はNone
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
            return None
        
        status, output_data_json, completed_at = result
        
        return {
            "status": status,
            "output_data": json.loads(output_data_json) if output_data_json else {},
            "completed_at": completed_at
        }
    
    def register_script_files(
        self, 
        project_id: str, 
        script_json_path: str, 
        script_text_path: str
    ) -> None:
        """
        生成されたスクリプトファイルを登録
        
        Args:
            project_id: プロジェクトID
            script_json_path: JSONスクリプトファイルパス
            script_text_path: テキストスクリプトファイルパス
        """
        # JSON形式スクリプトファイルを登録
        json_insert_query = """
        INSERT INTO project_files 
        (project_id, file_type, file_category, file_path, file_name, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        current_time = datetime.now().isoformat()
        
        import os
        
        self.db_manager.execute_query(
            json_insert_query,
            (
                project_id,
                "script",
                "output",
                script_json_path,
                os.path.basename(script_json_path),
                current_time
            )
        )
        
        # テキスト形式スクリプトファイルを登録
        self.db_manager.execute_query(
            json_insert_query,
            (
                project_id,
                "script",
                "output",
                script_text_path,
                os.path.basename(script_text_path),
                current_time
            )
        )
    
    def get_project_info(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクト基本情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            プロジェクト情報辞書
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