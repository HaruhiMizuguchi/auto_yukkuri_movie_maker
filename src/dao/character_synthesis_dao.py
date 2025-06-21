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
        
        # 必要なテーブルを作成
        self._ensure_tables()
    
    def _ensure_tables(self):
        """必要なテーブルを作成"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # facial_expressionsテーブル
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS facial_expressions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        speaker TEXT NOT NULL,
                        primary_emotion TEXT NOT NULL,
                        emotion_weights TEXT NOT NULL,  -- JSON形式
                        transition_state TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                """)
                
                # emotion_transitionsテーブル
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS emotion_transitions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        start_time REAL NOT NULL,
                        end_time REAL NOT NULL,
                        from_emotion TEXT NOT NULL,
                        to_emotion TEXT NOT NULL,
                        speaker TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                """)
                
                # video_generation_resultsテーブル
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS video_generation_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        generation_type TEXT NOT NULL,
                        video_path TEXT NOT NULL,
                        generation_config TEXT,  -- JSON形式
                        result_data TEXT NOT NULL,  -- JSON形式
                        file_size_mb REAL,
                        generation_time_seconds REAL,
                        quality_score REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects (id),
                        UNIQUE(project_id, generation_type)
                    )
                """)
                
                conn.commit()
            
            self.logger.info("キャラクター合成用テーブル作成完了")
            
        except Exception as e:
            self.logger.error(f"テーブル作成エラー: {e}")
            raise
    
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
    
    def save_audio_metadata(self, project_id: str, audio_metadata: Dict[str, Any]) -> None:
        """
        音声メタデータを保存（テスト用）
        
        Args:
            project_id: プロジェクトID
            audio_metadata: 音声メタデータ
        """
        try:
            # テスト用の簡単な実装
            # 実際の実装では workflow_steps テーブルに保存
            tts_data = {
                "audio_metadata": audio_metadata,
                "audio_segments": audio_metadata.get("segments", []),
                "combined_audio_path": f"files/audio/{project_id}_combined.wav"
            }
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # workflow_steps テーブルに TTS 結果として保存
                cursor.execute("""
                    INSERT OR REPLACE INTO workflow_steps 
                    (project_id, step_number, step_name, status, output_data, completed_at)
                    VALUES (?, 4, 'tts_generation', 'completed', ?, ?)
                """, (project_id, json.dumps(tts_data), datetime.now().isoformat()))
                
                conn.commit()
            
            self.logger.info(f"音声メタデータ保存完了: project_id={project_id}")
            
        except Exception as e:
            self.logger.error(f"音声メタデータ保存エラー: {e}")
            raise
    
    def save_character_config(self, project_id: str, character_config: Dict[str, Any]) -> None:
        """
        キャラクター設定を保存（テスト用）
        
        Args:
            project_id: プロジェクトID
            character_config: キャラクター設定
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # workflow_steps テーブルにキャラクター設定として保存
                cursor.execute("""
                    INSERT OR REPLACE INTO workflow_steps 
                    (project_id, step_number, step_name, status, output_data, completed_at)
                    VALUES (?, 0, 'character_config', 'completed', ?, ?)
                """, (project_id, json.dumps(character_config), datetime.now().isoformat()))
                
                conn.commit()
            
            self.logger.info(f"キャラクター設定保存完了: project_id={project_id}")
            
        except Exception as e:
            self.logger.error(f"キャラクター設定保存エラー: {e}")
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
    
    # =================================================================
    # Phase 4-5-2: 表情制御機能用DAO（新規追加）
    # =================================================================
    
    def save_facial_expression_data(self, project_id: str, expression_data: Dict[str, Any]) -> None:
        """
        表情データを保存
        
        Args:
            project_id: プロジェクトID
            expression_data: 表情データ
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # facial_expressions テーブルが存在しない場合は作成
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS facial_expressions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        speaker TEXT NOT NULL,
                        primary_emotion TEXT NOT NULL,
                        emotion_weights TEXT NOT NULL,
                        transition_state TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # emotion_transitions テーブルが存在しない場合は作成
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS emotion_transitions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        start_time REAL NOT NULL,
                        end_time REAL NOT NULL,
                        from_emotion TEXT NOT NULL,
                        to_emotion TEXT NOT NULL,
                        speaker TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 既存データを削除
                cursor.execute("DELETE FROM facial_expressions WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM emotion_transitions WHERE project_id = ?", (project_id,))
                
                # 表情フレームを保存
                for frame in expression_data.get("expression_frames", []):
                    cursor.execute("""
                        INSERT INTO facial_expressions (
                            project_id, timestamp, speaker, primary_emotion,
                            emotion_weights, transition_state
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        project_id,
                        frame["timestamp"],
                        frame["speaker"],
                        frame["primary_emotion"],
                        json.dumps(frame["emotion_weights"]),
                        frame["transition_state"]
                    ))
                
                # 感情切り替えを保存
                for transition in expression_data.get("transitions", []):
                    cursor.execute("""
                        INSERT INTO emotion_transitions (
                            project_id, start_time, end_time, from_emotion,
                            to_emotion, speaker
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        project_id,
                        transition["start_time"],
                        transition["end_time"],
                        transition["from_emotion"],
                        transition["to_emotion"],
                        transition["speaker"]
                    ))
                
                conn.commit()
                self.logger.info(
                    f"表情データ保存完了: project_id={project_id}, "
                    f"frames={len(expression_data.get('expression_frames', []))}, "
                    f"transitions={len(expression_data.get('transitions', []))}"
                )
                
        except Exception as e:
            self.logger.error(f"表情データ保存エラー: project_id={project_id}: {e}")
            raise
    
    def get_facial_expression_data(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        保存された表情データを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            表情データ、または None
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 表情フレームを取得
                cursor.execute("""
                    SELECT timestamp, speaker, primary_emotion, emotion_weights, transition_state
                    FROM facial_expressions
                    WHERE project_id = ?
                    ORDER BY timestamp
                """, (project_id,))
                
                frame_results = cursor.fetchall()
                
                # 感情切り替えを取得
                cursor.execute("""
                    SELECT start_time, end_time, from_emotion, to_emotion, speaker
                    FROM emotion_transitions
                    WHERE project_id = ?
                    ORDER BY start_time
                """, (project_id,))
                
                transition_results = cursor.fetchall()
                
                if not frame_results and not transition_results:
                    return None
                
                # 結果を構造化
                expression_frames = []
                for row in frame_results:
                    expression_frames.append({
                        "timestamp": row[0],
                        "speaker": row[1],
                        "primary_emotion": row[2],
                        "emotion_weights": json.loads(row[3]),
                        "transition_state": row[4]
                    })
                
                transitions = []
                for row in transition_results:
                    transitions.append({
                        "start_time": row[0],
                        "end_time": row[1],
                        "from_emotion": row[2],
                        "to_emotion": row[3],
                        "speaker": row[4]
                    })
                
                return {
                    "project_id": project_id,
                    "expression_frames": expression_frames,
                    "transitions": transitions
                }
                
        except Exception as e:
            self.logger.error(f"表情データ取得エラー: project_id={project_id}: {e}")
            return None
    
    def save_video_generation_result(self, project_id: str, generation_type: str, result_data: Dict[str, Any]) -> None:
        """
        動画生成結果を保存
        
        Args:
            project_id: プロジェクトID
            generation_type: 生成タイプ（transparency, framerate_30, quality_optimized等）
            result_data: 結果データ
        """
        try:
            # 結果データからメタデータを抽出
            video_path = result_data.get("video_path", "")
            generation_config = result_data.get("generation_config", {})
            file_size_mb = result_data.get("file_size_mb", 0.0)
            generation_time_seconds = result_data.get("generation_time_seconds", 0.0)
            
            # 品質スコアを計算
            quality_score = 0.0
            if "quality_assessment" in result_data:
                quality_score = result_data["quality_assessment"].get("overall_quality", 0.0)
            elif "quality_score" in result_data:
                quality_score = result_data["quality_score"]
            elif "quality_metrics" in result_data:
                metrics = result_data["quality_metrics"]
                # PSNR, SSIM, VMEFから総合スコアを計算
                psnr_score = min(metrics.get("psnr", 0) / 50.0 * 100, 100)
                ssim_score = metrics.get("ssim", 0) * 100
                vmaf_score = metrics.get("vmaf", 0)
                quality_score = (psnr_score + ssim_score + vmaf_score) / 3
            
            # データベースに保存（UPSERT）
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO video_generation_results 
                    (project_id, generation_type, video_path, generation_config, result_data, 
                     file_size_mb, generation_time_seconds, quality_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    generation_type,
                    video_path,
                    json.dumps(generation_config),
                    json.dumps(result_data),
                    file_size_mb,
                    generation_time_seconds,
                    quality_score
                ))
                conn.commit()
            
            self.logger.info(
                f"動画生成結果保存完了: project_id={project_id}, type={generation_type}, "
                f"size={file_size_mb}MB, quality={quality_score:.1f}"
            )
            
        except Exception as e:
            self.logger.error(f"動画生成結果保存エラー: project_id={project_id}, type={generation_type}: {e}")
            raise

    def get_video_generation_result(self, project_id: str, generation_type: str) -> Optional[Dict[str, Any]]:
        """
        動画生成結果を取得
        
        Args:
            project_id: プロジェクトID
            generation_type: 生成タイプ
            
        Returns:
            動画生成結果、または None
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT video_path, generation_config, result_data, file_size_mb, 
                           generation_time_seconds, quality_score, created_at
                    FROM video_generation_results 
                    WHERE project_id = ? AND generation_type = ?
                """, (project_id, generation_type))
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                # JSONデータをパース
                generation_config = json.loads(result[1]) if result[1] else {}
                result_data = json.loads(result[2])
                
                # メタデータを追加
                result_data["video_path"] = result[0]
                result_data["generation_config"] = generation_config
                result_data["file_size_mb"] = result[3]
                result_data["generation_time_seconds"] = result[4]
                result_data["quality_score"] = result[5]
                result_data["created_at"] = result[6]
                
                self.logger.info(
                    f"動画生成結果取得完了: project_id={project_id}, type={generation_type}"
                )
                
                return result_data
                
        except Exception as e:
            self.logger.error(f"動画生成結果取得エラー: project_id={project_id}, type={generation_type}: {e}")
            return None

    def get_all_video_generation_results(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクトの全動画生成結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            動画生成結果のリスト
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT generation_type, video_path, file_size_mb, 
                           generation_time_seconds, quality_score, created_at
                    FROM video_generation_results 
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                """, (project_id,))
                
                results = cursor.fetchall()
                if not results:
                    return []
                
                video_results = []
                for result in results:
                    video_results.append({
                        "generation_type": result[0],
                        "video_path": result[1],
                        "file_size_mb": result[2],
                        "generation_time_seconds": result[3],
                        "quality_score": result[4],
                        "created_at": result[5]
                    })
                
                self.logger.info(f"全動画生成結果取得完了: project_id={project_id}, count={len(video_results)}")
                
                return video_results
                
        except Exception as e:
            self.logger.error(f"全動画生成結果取得エラー: project_id={project_id}: {e}")
            return [] 