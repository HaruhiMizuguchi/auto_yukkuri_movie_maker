"""
キャラクター合成処理用DAO

立ち絵アニメーション、口パク同期、表情制御に必要な
データベース操作を提供します。
"""

import sqlite3
from typing import Dict, Any, List, Optional, Tuple
import json
import logging
from datetime import datetime

from src.core.database_manager import DatabaseManager


class CharacterSynthesisDAO:
    """キャラクター合成処理用DAO"""
    
    def __init__(self, db_manager: DatabaseManager, logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            db_manager: データベースマネージャー
            logger: ロガー
        """
        self.db_manager = db_manager
        self.logger = logger or logging.getLogger(__name__)
    
    def get_audio_metadata(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトの音声メタデータを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            音声メタデータ辞書
            
        Raises:
            ValueError: データが見つからない場合
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # TTS結果を取得
                cursor.execute("""
                    SELECT output_data
                    FROM workflow_steps
                    WHERE project_id = ? AND step_name = 'tts_generation' AND status = 'completed'
                    ORDER BY completed_at DESC
                    LIMIT 1
                """, (project_id,))
                
                result = cursor.fetchone()
                if not result:
                    raise ValueError(f"TTS結果が見つかりません: project_id={project_id}")
                
                tts_data = json.loads(result[0])
                
                # 音声メタデータを抽出
                audio_metadata = tts_data.get("audio_metadata", {})
                audio_segments = tts_data.get("audio_segments", [])
                
                # 各セグメントのタイムスタンプを統合
                all_timestamps = []
                current_offset = 0.0
                
                for segment in audio_segments:
                    segment_timestamps = segment.get("timestamps", [])
                    for ts in segment_timestamps:
                        all_timestamps.append({
                            "segment_id": segment["segment_id"],
                            "speaker": segment["speaker"],
                            "emotion": segment.get("emotion", "neutral"),
                            "start_time": ts["start_time"] + current_offset,
                            "end_time": ts["end_time"] + current_offset,
                            "text": ts["text"],
                            "phoneme": ts.get("phoneme", ""),
                            "confidence": ts.get("confidence", 1.0)
                        })
                    
                    # 次のセグメントのオフセットを更新
                    current_offset += segment.get("duration", 0.0)
                
                return {
                    "total_duration": audio_metadata.get("total_duration", 0.0),
                    "sample_rate": audio_metadata.get("sample_rate", 24000),
                    "segments_count": len(audio_segments),
                    "timestamps": all_timestamps,
                    "combined_audio_path": tts_data.get("combined_audio_path", ""),
                    "metadata": audio_metadata
                }
                
        except Exception as e:
            self.logger.error(f"音声メタデータ取得エラー: project_id={project_id}: {e}")
            raise
    
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトのスクリプトデータを取得（感情分析用）
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            スクリプトデータ辞書
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT output_data
                    FROM workflow_steps
                    WHERE project_id = ? AND step_name = 'script_generation' AND status = 'completed'
                    ORDER BY completed_at DESC
                    LIMIT 1
                """, (project_id,))
                
                result = cursor.fetchone()
                if not result:
                    raise ValueError(f"スクリプトデータが見つかりません: project_id={project_id}")
                
                script_data = json.loads(result[0])
                return {
                    "segments": script_data.get("segments", []),
                    "estimated_duration": script_data.get("estimated_duration", 0),
                    "total_words": script_data.get("total_words", 0),
                    "speaker_distribution": script_data.get("speaker_distribution", {})
                }
                
        except Exception as e:
            self.logger.error(f"スクリプトデータ取得エラー: project_id={project_id}: {e}")
            raise
    
    def get_character_config(self, project_id: str) -> Dict[str, Any]:
        """
        キャラクター設定を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            キャラクター設定辞書
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # プロジェクト設定からキャラクター設定を取得
                cursor.execute("""
                    SELECT config_json
                    FROM projects
                    WHERE id = ?
                """, (project_id,))
                
                result = cursor.fetchone()
                if not result:
                    raise ValueError(f"プロジェクトが見つかりません: project_id={project_id}")
                
                config = json.loads(result[0]) if result[0] else {}
                
                # デフォルトキャラクター設定
                default_config = {
                    "characters": {
                        "reimu": {
                            "name": "博麗霊夢",
                            "mouth_shapes": {
                                "a": "mouth_a.png",
                                "i": "mouth_i.png", 
                                "u": "mouth_u.png",
                                "e": "mouth_e.png",
                                "o": "mouth_o.png",
                                "silence": "mouth_closed.png"
                            },
                            "emotions": {
                                "neutral": "reimu_neutral.png",
                                "happy": "reimu_happy.png",
                                "sad": "reimu_sad.png",
                                "surprised": "reimu_surprised.png",
                                "angry": "reimu_angry.png"
                            }
                        },
                        "marisa": {
                            "name": "霧雨魔理沙",
                            "mouth_shapes": {
                                "a": "mouth_a.png",
                                "i": "mouth_i.png",
                                "u": "mouth_u.png", 
                                "e": "mouth_e.png",
                                "o": "mouth_o.png",
                                "silence": "mouth_closed.png"
                            },
                            "emotions": {
                                "neutral": "marisa_neutral.png",
                                "happy": "marisa_happy.png",
                                "sad": "marisa_sad.png",
                                "surprised": "marisa_surprised.png", 
                                "angry": "marisa_angry.png"
                            }
                        }
                    },
                    "animation": {
                        "frame_rate": 30,
                        "video_width": 1920,
                        "video_height": 1080,
                        "character_scale": 0.8,
                        "character_position": {
                            "reimu": {"x": 300, "y": 200},
                            "marisa": {"x": 1200, "y": 200}
                        }
                    }
                }
                
                # プロジェクト設定とデフォルト設定をマージ
                character_config = config.get("character_synthesis", default_config)
                
                return character_config
                
        except Exception as e:
            self.logger.error(f"キャラクター設定取得エラー: project_id={project_id}: {e}")
            raise
    
    def save_emotion_analysis(self, project_id: str, emotion_data: Dict[str, Any]) -> None:
        """
        感情分析結果を保存
        
        Args:
            project_id: プロジェクトID
            emotion_data: 感情分析データ
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # emotion_analysis テーブルが存在しない場合は作成
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS emotion_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        segment_id INTEGER NOT NULL,
                        speaker TEXT NOT NULL,
                        detected_emotion TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        emotion_keywords TEXT,
                        analysis_timestamp TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 既存データを削除
                cursor.execute("""
                    DELETE FROM emotion_analysis WHERE project_id = ?
                """, (project_id,))
                
                # 新しい感情分析データを保存
                for segment in emotion_data.get("segments", []):
                    cursor.execute("""
                        INSERT INTO emotion_analysis (
                            project_id, segment_id, speaker, detected_emotion,
                            confidence, emotion_keywords, analysis_timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        project_id,
                        segment["segment_id"],
                        segment["speaker"],
                        segment["detected_emotion"],
                        segment["confidence"],
                        json.dumps(segment.get("keywords", [])),
                        segment.get("timestamp", datetime.now().isoformat())
                    ))
                
                conn.commit()
                self.logger.info(f"感情分析結果保存完了: project_id={project_id}, segments={len(emotion_data.get('segments', []))}")
                
        except Exception as e:
            self.logger.error(f"感情分析結果保存エラー: project_id={project_id}: {e}")
            raise
    
    def get_emotion_analysis(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        保存された感情分析結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            感情分析データ、または None
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT segment_id, speaker, detected_emotion, confidence, 
                           emotion_keywords, analysis_timestamp
                    FROM emotion_analysis
                    WHERE project_id = ?
                    ORDER BY segment_id
                """, (project_id,))
                
                results = cursor.fetchall()
                if not results:
                    return None
                
                segments = []
                for row in results:
                    segments.append({
                        "segment_id": row[0],
                        "speaker": row[1],
                        "detected_emotion": row[2],
                        "confidence": row[3],
                        "keywords": json.loads(row[4]) if row[4] else [],
                        "timestamp": row[5]
                    })
                
                return {
                    "project_id": project_id,
                    "segments": segments,
                    "total_segments": len(segments)
                }
                
        except Exception as e:
            self.logger.error(f"感情分析結果取得エラー: project_id={project_id}: {e}")
            return None
    
    def save_character_synthesis_result(
        self, 
        project_id: str, 
        synthesis_result: Dict[str, Any], 
        status: str = "completed"
    ) -> None:
        """
        キャラクター合成結果を保存
        
        Args:
            project_id: プロジェクトID
            synthesis_result: 合成結果
            status: 処理状態
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # workflow_steps に結果を保存
                cursor.execute("""
                    INSERT OR REPLACE INTO workflow_steps (
                        project_id, step_number, step_name, status, output_data, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    5,  # character_synthesis は step 5
                    "character_synthesis",
                    status,
                    json.dumps(synthesis_result, ensure_ascii=False),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                self.logger.info(f"キャラクター合成結果保存完了: project_id={project_id}")
                
        except Exception as e:
            self.logger.error(f"キャラクター合成結果保存エラー: project_id={project_id}: {e}")
            raise
    
    def register_video_files(self, project_id: str, video_files: List[Dict[str, Any]]) -> None:
        """
        動画ファイル参照を登録
        
        Args:
            project_id: プロジェクトID
            video_files: 動画ファイル情報のリスト
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                for video_file in video_files:
                    cursor.execute("""
                        INSERT INTO project_files (
                            project_id, file_type, file_category,
                            file_path, file_name, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        project_id,
                        video_file["file_type"],
                        video_file["file_category"],
                        video_file["file_path"],
                        video_file["file_name"],
                        datetime.now().isoformat()
                    ))
                
                conn.commit()
                self.logger.info(f"動画ファイル参照登録完了: project_id={project_id}, files={len(video_files)}")
                
        except Exception as e:
            self.logger.error(f"動画ファイル参照登録エラー: project_id={project_id}: {e}")
            raise
    
    def get_character_synthesis_result(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        保存されたキャラクター合成結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            合成結果辞書、または None
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT output_data, status, completed_at
                    FROM workflow_steps
                    WHERE project_id = ? AND step_name = 'character_synthesis'
                    ORDER BY completed_at DESC
                    LIMIT 1
                """, (project_id,))
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                synthesis_data = json.loads(result[0])
                synthesis_data["status"] = result[1]
                synthesis_data["completed_at"] = result[2]
                
                return synthesis_data
                
        except Exception as e:
            self.logger.error(f"キャラクター合成結果取得エラー: project_id={project_id}: {e}")
            return None 