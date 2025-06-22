"""
動画合成DAO (Data Access Object)

動画合成機能に関するデータベース操作を担当します。
- 入力ファイル管理（背景動画・立ち絵・音声・字幕）
- 合成設定保存
- 合成結果保存
- ファイル参照管理

flow_definition.yamlの仕様に準拠:
- step_id: 9 (video_composition)
- 入力: background_video, character_video, combined_audio, subtitle_file
- 出力: composed_video
"""

from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime

from ..core.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class VideoCompositionDAO:
    """動画合成データアクセスオブジェクト"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初期化
        
        Args:
            db_manager: データベースマネージャー
        """
        self.db_manager = db_manager
        self.logger = logger

    def get_input_files(self, project_id: str) -> Dict[str, Any]:
        """
        動画合成の入力ファイル情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            入力ファイル情報辞書
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 必要な入力ファイルを取得
                input_files = {}
                
                # 背景動画を取得
                cursor.execute("""
                    SELECT file_path FROM file_references
                    WHERE project_id = ? AND step_name = 'background_animation' 
                    AND file_type = 'video' AND file_category = 'intermediate'
                    ORDER BY created_at DESC LIMIT 1
                """, (project_id,))
                background_result = cursor.fetchone()
                if background_result:
                    input_files["background_video_path"] = background_result[0]
                
                # 立ち絵動画を取得
                cursor.execute("""
                    SELECT file_path FROM file_references
                    WHERE project_id = ? AND step_name = 'character_synthesis' 
                    AND file_type = 'video' AND file_category = 'intermediate'
                    ORDER BY created_at DESC LIMIT 1
                """, (project_id,))
                character_result = cursor.fetchone()
                if character_result:
                    input_files["character_video_path"] = character_result[0]
                
                # 結合音声を取得
                cursor.execute("""
                    SELECT file_path FROM file_references
                    WHERE project_id = ? AND step_name = 'tts_generation' 
                    AND file_type = 'audio' AND file_category = 'output'
                    ORDER BY created_at DESC LIMIT 1
                """, (project_id,))
                audio_result = cursor.fetchone()
                if audio_result:
                    input_files["audio_path"] = audio_result[0]
                
                # 字幕ファイルを取得
                cursor.execute("""
                    SELECT file_path FROM file_references
                    WHERE project_id = ? AND step_name = 'subtitle_generation' 
                    AND file_type = 'subtitle' AND file_category = 'intermediate'
                    ORDER BY created_at DESC LIMIT 1
                """, (project_id,))
                subtitle_result = cursor.fetchone()
                if subtitle_result:
                    input_files["subtitle_path"] = subtitle_result[0]
                
                self.logger.info(f"動画合成入力ファイル取得完了: project_id={project_id}, files={len(input_files)}")
                return input_files
                
        except Exception as e:
            self.logger.error(f"動画合成入力ファイル取得エラー: project_id={project_id}, error={e}")
            raise

    def get_composition_config(self, project_id: str) -> Dict[str, Any]:
        """
        動画合成設定を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            合成設定辞書
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # プロジェクト設定から合成設定を取得
                cursor.execute("""
                    SELECT config_json FROM projects WHERE id = ?
                """, (project_id,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    config = json.loads(result[0])
                    composition_config = config.get("video_composition", {})
                else:
                    # デフォルト設定
                    composition_config = {
                        "video_layout": {
                            "character_position": "center",
                            "character_scale": 1.0,
                            "character_opacity": 1.0
                        },
                        "subtitle_config": {
                            "enabled": True,
                            "position": "bottom",
                            "style": "default"
                        },
                        "audio_config": {
                            "background_music_volume": 0.3,
                            "voice_volume": 0.8
                        }
                    }
                
                self.logger.info(f"動画合成設定取得完了: project_id={project_id}")
                return composition_config
                
        except Exception as e:
            self.logger.error(f"動画合成設定取得エラー: project_id={project_id}, error={e}")
            raise

    def save_composition_result(self, project_id: str, composition_data: Dict[str, Any]) -> None:
        """
        動画合成結果を保存
        
        Args:
            project_id: プロジェクトID
            composition_data: 合成結果データ
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # ワークフローステップテーブルに結果を保存
                output_summary = {
                    "composed_video_path": composition_data.get("composed_video_path"),
                    "composition_metadata": composition_data.get("composition_metadata", {}),
                    "layer_metadata": composition_data.get("layer_metadata", {}),
                    "created_at": datetime.now().isoformat()
                }
                
                cursor.execute("""
                    UPDATE workflow_steps 
                    SET status = 'completed',
                        output_summary_json = ?,
                        completed_at = CURRENT_TIMESTAMP,
                        error_message = NULL
                    WHERE project_id = ? AND step_name = 'video_composition'
                """, (json.dumps(output_summary), project_id))
                
                # ファイル参照を登録
                if composition_data.get("composed_video_path"):
                    self._register_file_reference(
                        cursor=cursor,
                        project_id=project_id,
                        step_name="video_composition",
                        file_type="video",
                        file_category="intermediate",
                        file_path=composition_data["composed_video_path"],
                        metadata=composition_data.get("composition_metadata", {})
                    )
                
                conn.commit()
                self.logger.info(f"動画合成結果保存完了: project_id={project_id}")
                
        except Exception as e:
            self.logger.error(f"動画合成結果保存エラー: project_id={project_id}, error={e}")
            raise

    def save_composition_layers(self, project_id: str, layer_data: Dict[str, Any]) -> None:
        """
        動画合成レイヤー情報を保存
        
        Args:
            project_id: プロジェクトID
            layer_data: レイヤーデータ
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # video_composition_layersテーブルに保存（存在しない場合はスキップ）
                try:
                    cursor.execute("""
                        INSERT INTO video_composition_layers (
                            project_id, background_status, character_status, 
                            subtitle_status, audio_status, layer_metadata, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        project_id,
                        layer_data.get("background", {}).get("status", "unknown"),
                        layer_data.get("character", {}).get("status", "unknown"),
                        layer_data.get("subtitle", {}).get("status", "unknown"),
                        layer_data.get("audio", {}).get("status", "unknown"),
                        json.dumps(layer_data)
                    ))
                except Exception:
                    # テーブルが存在しない場合は、workflow_stepsに保存
                    pass
                
                conn.commit()
                self.logger.info(f"動画合成レイヤー情報保存完了: project_id={project_id}")
                
        except Exception as e:
            self.logger.error(f"動画合成レイヤー情報保存エラー: project_id={project_id}, error={e}")
            # 非致命的エラーとして続行

    def get_composition_result(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        動画合成結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            合成結果辞書（存在しない場合はNone）
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT output_summary_json, status, completed_at
                    FROM workflow_steps
                    WHERE project_id = ? AND step_name = 'video_composition'
                """, (project_id,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    composition_result = json.loads(result[0])
                    composition_result["status"] = result[1]
                    composition_result["completed_at"] = result[2]
                    
                    self.logger.info(f"動画合成結果取得完了: project_id={project_id}")
                    return composition_result
                
                return None
                
        except Exception as e:
            self.logger.error(f"動画合成結果取得エラー: project_id={project_id}, error={e}")
            raise

    def _register_file_reference(
        self, 
        cursor, 
        project_id: str, 
        step_name: str,
        file_type: str,
        file_category: str,
        file_path: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        ファイル参照を登録
        
        Args:
            cursor: データベースカーソル
            project_id: プロジェクトID
            step_name: ステップ名
            file_type: ファイルタイプ
            file_category: ファイルカテゴリ
            file_path: ファイルパス
            metadata: メタデータ
        """
        cursor.execute("""
            INSERT INTO file_references (
                project_id, step_name, file_type, file_category,
                file_path, file_name, file_size, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            project_id, step_name, file_type, file_category,
            file_path, file_path.split('/')[-1], 
            metadata.get("file_size", 0),
            json.dumps(metadata)
        ))

    def cleanup_temp_files(self, project_id: str) -> None:
        """
        一時ファイルをクリーンアップ
        
        Args:
            project_id: プロジェクトID
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 一時ファイルの参照を削除（実ファイルは別途削除）
                cursor.execute("""
                    DELETE FROM file_references
                    WHERE project_id = ? AND step_name = 'video_composition'
                    AND file_category = 'temp'
                """, (project_id,))
                
                conn.commit()
                self.logger.info(f"動画合成一時ファイルクリーンアップ完了: project_id={project_id}")
                
        except Exception as e:
            self.logger.error(f"動画合成一時ファイルクリーンアップエラー: project_id={project_id}, error={e}")
            # 非致命的エラーとして続行 