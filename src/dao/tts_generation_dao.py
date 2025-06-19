"""
TTS生成用DAO（データアクセスオブジェクト）

データベースアクセスロジックをビジネスロジックから分離
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from src.core.database_manager import DatabaseManager


class TTSGenerationDAO:
    """TTS生成のデータアクセス層"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初期化
        
        Args:
            db_manager: データベースマネージャー
        """
        self.db_manager = db_manager
    
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトのスクリプトデータを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            スクリプトデータ辞書
            
        Raises:
            ValueError: スクリプトが見つからない場合
        """
        query = """
        SELECT output_data
        FROM workflow_steps
        WHERE project_id = ? AND step_name = 'script_generation' AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        
        if not result:
            raise ValueError(f"プロジェクト {project_id} のスクリプトが見つかりません")
        
        output_data_json = result[0]
        script_data = json.loads(output_data_json) if output_data_json else {}
        
        if not script_data.get("segments"):
            raise ValueError(f"プロジェクト {project_id} に有効なスクリプトセグメントがありません")
        
        return script_data
    
    def get_voice_config(self, project_id: str) -> Dict[str, Any]:
        """
        音声生成設定を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            音声設定辞書
        """
        # プロジェクト設定から取得
        query = """
        SELECT config_json
        FROM projects
        WHERE id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        
        if result and result[0]:
            project_config = json.loads(result[0])
            voice_config = project_config.get("voice_config", {})
        else:
            voice_config = {}
        
        # デフォルト設定をマージ
        default_config = {
            "voice_mapping": {
                "reimu": {"speaker_id": 0, "style": "normal"},
                "marisa": {"speaker_id": 1, "style": "cheerful"}
            },
            "audio_settings": {
                "sample_rate": 24000,
                "speed": 1.0,
                "pitch": 0.0,
                "intonation": 1.0,
                "volume": 1.0
            },
            "output_format": "wav",
            "enable_timestamps": True
        }
        
        # 再帰的にデフォルト値をマージ
        def merge_configs(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
            merged = default.copy()
            for key, value in user.items():
                if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = merge_configs(merged[key], value)
                else:
                    merged[key] = value
            return merged
        
        return merge_configs(default_config, voice_config)
    
    def save_tts_result(
        self, 
        project_id: str, 
        tts_result: Dict[str, Any], 
        status: str = "completed"
    ) -> None:
        """
        TTS生成結果を保存
        
        Args:
            project_id: プロジェクトID
            tts_result: TTS生成結果データ
            status: ステップステータス
        """
        # TTS結果データを準備
        result_data = {
            "audio_segments": tts_result.get("audio_segments", []),
            "combined_audio_path": tts_result.get("combined_audio_path"),
            "audio_metadata": tts_result.get("audio_metadata", {}),
            "generation_timestamp": datetime.now().isoformat()
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
                4,  # tts_generation is step 4 according to flow_definition.yaml
                "tts_generation",
                status,
                json.dumps(result_data, ensure_ascii=False),
                datetime.now().isoformat()
            )
        )
        
        # 音声メタデータ統計を更新
        audio_metadata = tts_result.get("audio_metadata", {})
        if audio_metadata.get("total_duration"):
            update_stats_query = """
            UPDATE project_statistics 
            SET audio_duration = ?
            WHERE project_id = ?
            """
            
            self.db_manager.execute_query(
                update_stats_query,
                (audio_metadata["total_duration"], project_id)
            )
    
    def register_audio_files(
        self, 
        project_id: str, 
        audio_files: List[Dict[str, str]]
    ) -> None:
        """
        生成された音声ファイルを登録
        
        Args:
            project_id: プロジェクトID
            audio_files: 音声ファイル情報のリスト
                       [{"file_type": "audio", "file_category": "output", 
                         "file_path": "/path/to/file", "file_name": "filename.wav"}, ...]
        """
        insert_query = """
        INSERT INTO project_files 
        (project_id, file_type, file_category, file_path, file_name, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        current_time = datetime.now().isoformat()
        
        for file_info in audio_files:
            self.db_manager.execute_query(
                insert_query,
                (
                    project_id,
                    file_info["file_type"],
                    file_info["file_category"],
                    file_info["file_path"],
                    file_info["file_name"],
                    current_time
                )
            )
    
    def get_tts_result(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        保存されたTTS結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            TTS結果データ、見つからない場合はNone
        """
        query = """
        SELECT status, output_data, completed_at
        FROM workflow_steps
        WHERE project_id = ? AND step_name = 'tts_generation'
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
    
    def get_audio_files(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクトの音声ファイル一覧を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            音声ファイル情報のリスト
        """
        query = """
        SELECT file_type, file_category, file_path, file_name, created_at
        FROM project_files
        WHERE project_id = ? AND file_type = 'audio'
        ORDER BY created_at DESC
        """
        
        results = self.db_manager.fetch_all(query, (project_id,))
        
        return [
            {
                "file_type": row[0],
                "file_category": row[1], 
                "file_path": row[2],
                "file_name": row[3],
                "created_at": row[4]
            }
            for row in results
        ]
    
    def get_project_info(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクト基本情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            プロジェクト情報辞書
        """
        query = """
        SELECT name, theme, target_length_minutes, config_json
        FROM projects
        WHERE id = ?
        """
        
        result = self.db_manager.fetch_one(query, (project_id,))
        
        if not result:
            raise ValueError(f"プロジェクト {project_id} が見つかりません")
        
        name, theme, target_length_minutes, config_json = result
        
        return {
            "name": name,
            "theme": theme,
            "target_length_minutes": target_length_minutes,
            "config": json.loads(config_json) if config_json else {}
        }
    
    def save_audio_segment_metadata(
        self,
        project_id: str,
        segment_id: int,
        metadata: Dict[str, Any]
    ) -> None:
        """
        音声セグメントのメタデータを保存
        
        Args:
            project_id: プロジェクトID
            segment_id: セグメントID
            metadata: メタデータ辞書
        """
        # 専用のテーブルがある場合は使用、なければworkflow_stepsの一部として保存
        metadata_with_context = {
            "project_id": project_id,
            "segment_id": segment_id,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }
        
        # 簡単な実装として、project_filesのmeta_dataフィールドに保存
        # 実際の運用では専用テーブルを作成することを推奨
        insert_query = """
        INSERT INTO project_files 
        (project_id, file_type, file_category, file_path, file_name, meta_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        self.db_manager.execute_query(
            insert_query,
            (
                project_id,
                "metadata",
                "segment",
                f"segment_{segment_id}_metadata.json",
                f"segment_{segment_id}_metadata.json",
                json.dumps(metadata_with_context, ensure_ascii=False),
                datetime.now().isoformat()
            )
        ) 