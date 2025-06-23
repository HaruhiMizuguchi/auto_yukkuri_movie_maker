"""
挿絵挿入モジュール用DAO (Data Access Object)

flow_definition.yamlに基づくデータアクセス層:
- 話題転換データのCRUD操作
- 挿絵データのCRUD操作
- 動画統合データのCRUD操作
- 挿絵挿入結果のメタデータ管理

テーブル設計:
1. topic_transitions: 話題転換情報
2. illustrations: 挿絵仕様・メタデータ
3. video_integrations: 動画統合結果
4. illustration_insertions: メイン処理結果
"""

import sqlite3
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

from ..core.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class IllustrationInsertionDAO:
    """挿絵挿入モジュール用データアクセスオブジェクト"""

    def __init__(self, database_manager: DatabaseManager):
        """
        DAO初期化
        
        Args:
            database_manager: データベース管理オブジェクト
        """
        self.database_manager = database_manager
        self._initialize_tables()

    def _initialize_tables(self):
        """テーブル初期化"""
        # データベース初期化を確実に実行
        self.database_manager.initialize()
        
        with self.database_manager.get_connection() as conn:
            # 1. 話題転換テーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    transition_id TEXT NOT NULL,
                    from_topic TEXT NOT NULL,
                    to_topic TEXT NOT NULL,
                    transition_time REAL NOT NULL,
                    transition_type TEXT NOT NULL,
                    transition_strength REAL NOT NULL,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, transition_id)
                )
            """)
            
            # 2. 挿絵テーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS illustrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    illustration_id TEXT NOT NULL,
                    transition_id TEXT NOT NULL,
                    image_prompt TEXT NOT NULL,
                    image_path TEXT,
                    display_duration REAL NOT NULL,
                    display_position TEXT NOT NULL,
                    transition_effect TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, illustration_id)
                )
            """)
            
            # 3. 動画統合テーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS video_integrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    integration_id TEXT NOT NULL,
                    input_video_path TEXT NOT NULL,
                    output_video_path TEXT NOT NULL,
                    integrated_count INTEGER NOT NULL,
                    processing_duration REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, integration_id)
                )
            """)
            
            # 4. 挿絵挿入メインテーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS illustration_insertions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    insertion_id TEXT NOT NULL,
                    enhanced_video_path TEXT NOT NULL,
                    final_video_path TEXT NOT NULL,
                    topic_transitions_count INTEGER NOT NULL,
                    illustrations_count INTEGER NOT NULL,
                    processing_duration REAL NOT NULL,
                    insertion_config_json TEXT,
                    result_summary_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, insertion_id)
                )
            """)

    def save_topic_transitions(self, project_id: str, transitions: List[Any]) -> bool:
        """
        話題転換データ保存
        
        Args:
            project_id: プロジェクトID
            transitions: 話題転換データリスト
            
        Returns:
            bool: 保存成功フラグ
        """
        try:
            with self.database_manager.get_connection() as conn:
                for transition in transitions:
                    conn.execute("""
                        INSERT OR REPLACE INTO topic_transitions
                        (project_id, transition_id, from_topic, to_topic, 
                         transition_time, transition_type, transition_strength, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        project_id,
                        transition.transition_id,
                        transition.from_topic,
                        transition.to_topic,
                        transition.transition_time,
                        transition.transition_type,
                        transition.transition_strength,
                        json.dumps(transition.metadata) if hasattr(transition, 'metadata') else None
                    ))
            
            logger.info(f"話題転換データ保存完了: project_id={project_id}, count={len(transitions)}")
            return True
            
        except Exception as e:
            logger.error(f"話題転換データ保存エラー: {str(e)}")
            return False

    def get_topic_transitions(self, project_id: str) -> List[Dict[str, Any]]:
        """
        話題転換データ取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict[str, Any]]: 話題転換データリスト
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT transition_id, from_topic, to_topic, transition_time,
                           transition_type, transition_strength, metadata_json, created_at
                    FROM topic_transitions
                    WHERE project_id = ?
                    ORDER BY transition_time ASC
                """, (project_id,))
                
                rows = cursor.fetchall()
                
                transitions = []
                for row in rows:
                    transition = {
                        "transition_id": row[0],
                        "from_topic": row[1],
                        "to_topic": row[2],
                        "transition_time": row[3],
                        "transition_type": row[4],
                        "transition_strength": row[5],
                        "metadata": json.loads(row[6]) if row[6] else {},
                        "created_at": row[7]
                    }
                    transitions.append(transition)
                
                logger.info(f"話題転換データ取得完了: project_id={project_id}, count={len(transitions)}")
                return transitions
                
        except Exception as e:
            logger.error(f"話題転換データ取得エラー: {str(e)}")
            return []

    def save_illustrations(self, project_id: str, illustrations: List[Any]) -> bool:
        """
        挿絵データ保存
        
        Args:
            project_id: プロジェクトID
            illustrations: 挿絵データリスト
            
        Returns:
            bool: 保存成功フラグ
        """
        try:
            with self.database_manager.get_connection() as conn:
                for illustration in illustrations:
                    conn.execute("""
                        INSERT OR REPLACE INTO illustrations
                        (project_id, illustration_id, transition_id, image_prompt,
                         image_path, display_duration, display_position, 
                         transition_effect, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        project_id,
                        illustration.illustration_id,
                        illustration.transition_id,
                        illustration.image_prompt,
                        getattr(illustration, 'image_path', None),
                        illustration.display_duration,
                        illustration.display_position,
                        illustration.transition_effect,
                        json.dumps(illustration.metadata) if hasattr(illustration, 'metadata') else None
                    ))
            
            logger.info(f"挿絵データ保存完了: project_id={project_id}, count={len(illustrations)}")
            return True
            
        except Exception as e:
            logger.error(f"挿絵データ保存エラー: {str(e)}")
            return False

    def get_illustrations(self, project_id: str) -> List[Dict[str, Any]]:
        """
        挿絵データ取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict[str, Any]]: 挿絵データリスト
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT illustration_id, transition_id, image_prompt, image_path,
                           display_duration, display_position, transition_effect,
                           metadata_json, created_at
                    FROM illustrations
                    WHERE project_id = ?
                    ORDER BY created_at ASC
                """, (project_id,))
                
                rows = cursor.fetchall()
                
                illustrations = []
                for row in rows:
                    illustration = {
                        "illustration_id": row[0],
                        "transition_id": row[1],
                        "image_prompt": row[2],
                        "image_path": row[3],
                        "display_duration": row[4],
                        "display_position": row[5],
                        "transition_effect": row[6],
                        "metadata": json.loads(row[7]) if row[7] else {},
                        "created_at": row[8]
                    }
                    illustrations.append(illustration)
                
                logger.info(f"挿絵データ取得完了: project_id={project_id}, count={len(illustrations)}")
                return illustrations
                
        except Exception as e:
            logger.error(f"挿絵データ取得エラー: {str(e)}")
            return []

    def save_video_integration(self, project_id: str, integration: Any) -> bool:
        """
        動画統合結果保存
        
        Args:
            project_id: プロジェクトID
            integration: 動画統合結果
            
        Returns:
            bool: 保存成功フラグ
        """
        try:
            with self.database_manager.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO video_integrations
                    (project_id, integration_id, input_video_path, output_video_path,
                     integrated_count, processing_duration, success, error_message, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    getattr(integration, 'integration_id', 'default_integration'),
                    getattr(integration, 'input_video_path', ''),
                    integration.output_video_path,
                    integration.integrated_count,
                    integration.processing_duration,
                    integration.success,
                    getattr(integration, 'error_message', None),
                    json.dumps(getattr(integration, 'metadata', {}))
                ))
            
            logger.info(f"動画統合結果保存完了: project_id={project_id}")
            return True
            
        except Exception as e:
            logger.error(f"動画統合結果保存エラー: {str(e)}")
            return False

    def get_video_integrations(self, project_id: str) -> List[Dict[str, Any]]:
        """
        動画統合結果取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict[str, Any]]: 動画統合結果リスト
        """
        try:
            with self.database_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT integration_id, input_video_path, output_video_path,
                           integrated_count, processing_duration, success,
                           error_message, metadata_json, created_at
                    FROM video_integrations
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                """, (project_id,))
                
                rows = cursor.fetchall()
                
                integrations = []
                for row in rows:
                    integration = {
                        "integration_id": row[0],
                        "input_video_path": row[1],
                        "output_video_path": row[2],
                        "integrated_count": row[3],
                        "processing_duration": row[4],
                        "success": row[5],
                        "error_message": row[6],
                        "metadata": json.loads(row[7]) if row[7] else {},
                        "created_at": row[8]
                    }
                    integrations.append(integration)
                
                logger.info(f"動画統合結果取得完了: project_id={project_id}, count={len(integrations)}")
                return integrations
                
        except Exception as e:
            logger.error(f"動画統合結果取得エラー: {str(e)}")
            return []

    def save_illustration_insertion_result(self, project_id: str, insertion_id: str, 
                                         result_data: Dict[str, Any]) -> bool:
        """
        挿絵挿入結果保存
        
        Args:
            project_id: プロジェクトID
            insertion_id: 挿入処理ID
            result_data: 処理結果データ
            
        Returns:
            bool: 保存成功フラグ
        """
        try:
            with self.database_manager.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO illustration_insertions
                    (project_id, insertion_id, enhanced_video_path, final_video_path,
                     topic_transitions_count, illustrations_count, processing_duration,
                     insertion_config_json, result_summary_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    project_id,
                    insertion_id,
                    result_data.get("enhanced_video_path", ""),
                    result_data.get("final_video_path", ""),
                    result_data.get("topic_transitions_count", 0),
                    result_data.get("illustrations_count", 0),
                    result_data.get("processing_duration", 0.0),
                    json.dumps(result_data.get("insertion_config", {})),
                    json.dumps(result_data.get("result_summary", {}))
                ))
            
            logger.info(f"挿絵挿入結果保存完了: project_id={project_id}, insertion_id={insertion_id}")
            return True
            
        except Exception as e:
            logger.error(f"挿絵挿入結果保存エラー: {str(e)}")
            return False

    def get_illustration_insertion_result(self, project_id: str, 
                                        insertion_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        挿絵挿入結果取得
        
        Args:
            project_id: プロジェクトID
            insertion_id: 挿入処理ID（省略時は最新取得）
            
        Returns:
            Optional[Dict[str, Any]]: 挿絵挿入結果
        """
        try:
            with self.database_manager.get_connection() as conn:
                if insertion_id:
                    cursor = conn.execute("""
                        SELECT insertion_id, enhanced_video_path, final_video_path,
                               topic_transitions_count, illustrations_count, processing_duration,
                               insertion_config_json, result_summary_json, created_at, updated_at
                        FROM illustration_insertions
                        WHERE project_id = ? AND insertion_id = ?
                    """, (project_id, insertion_id))
                else:
                    cursor = conn.execute("""
                        SELECT insertion_id, enhanced_video_path, final_video_path,
                               topic_transitions_count, illustrations_count, processing_duration,
                               insertion_config_json, result_summary_json, created_at, updated_at
                        FROM illustration_insertions
                        WHERE project_id = ?
                        ORDER BY updated_at DESC
                        LIMIT 1
                    """, (project_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                result = {
                    "insertion_id": row[0],
                    "enhanced_video_path": row[1],
                    "final_video_path": row[2],
                    "topic_transitions_count": row[3],
                    "illustrations_count": row[4],
                    "processing_duration": row[5],
                    "insertion_config": json.loads(row[6]) if row[6] else {},
                    "result_summary": json.loads(row[7]) if row[7] else {},
                    "created_at": row[8],
                    "updated_at": row[9]
                }
                
                logger.info(f"挿絵挿入結果取得完了: project_id={project_id}, insertion_id={result['insertion_id']}")
                return result
                
        except Exception as e:
            logger.error(f"挿絵挿入結果取得エラー: {str(e)}")
            return None

    def delete_project_data(self, project_id: str) -> bool:
        """
        プロジェクトの挿絵挿入関連データ削除
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: 削除成功フラグ
        """
        try:
            with self.database_manager.get_connection() as conn:
                # 関連テーブルのデータ削除
                tables = [
                    "illustration_insertions",
                    "video_integrations", 
                    "illustrations",
                    "topic_transitions"
                ]
                
                for table in tables:
                    conn.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))
            
            logger.info(f"挿絵挿入プロジェクトデータ削除完了: project_id={project_id}")
            return True
            
        except Exception as e:
            logger.error(f"挿絵挿入プロジェクトデータ削除エラー: {str(e)}")
            return False 