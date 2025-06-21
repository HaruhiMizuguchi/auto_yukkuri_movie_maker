"""
キャラクター合成モジュール

立ち絵アニメーション、口パク同期、表情制御、動画生成を提供します。
AIVIS Speech APIのタイムスタンプデータとGemini APIの感情分析を組み合わせて、
高品質なキャラクターアニメーションを生成します。
"""

import os
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging
import json
from datetime import datetime
import math

from src.dao.character_synthesis_dao import CharacterSynthesisDAO
from src.core.file_system_manager import FileSystemManager
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient

# 動画処理ライブラリ（将来的にOpenCVやmovipyを使用）
try:
    import cv2
    import numpy as np
    VIDEO_PROCESSING_AVAILABLE = True
except ImportError:
    VIDEO_PROCESSING_AVAILABLE = False
    cv2 = None
    np = None
    logging.warning("OpenCV not available. Video generation will use mock implementation.")


@dataclass
class LipSyncFrame:
    """口パク同期フレーム"""
    start_time: float
    end_time: float
    phoneme: str
    mouth_shape: str
    speaker: str
    confidence: float = 1.0


@dataclass
class EmotionFrame:
    """感情フレーム"""
    start_time: float
    end_time: float
    emotion: str
    confidence: float
    keywords: List[str]
    speaker: str


@dataclass
class CharacterFrame:
    """キャラクターフレーム"""
    timestamp: float
    speaker: str
    mouth_shape: str
    emotion: str
    position: Tuple[int, int]
    scale: float = 1.0


@dataclass
class CharacterSynthesisResult:
    """キャラクター合成結果"""
    character_video_path: str
    total_duration: float
    frame_count: int
    lip_sync_frames: List[LipSyncFrame]
    emotion_frames: List[EmotionFrame] 
    character_frames: List[CharacterFrame]
    video_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "character_video_path": self.character_video_path,
            "total_duration": self.total_duration,
            "frame_count": self.frame_count,
            "lip_sync_data": [
                {
                    "start_time": frame.start_time,
                    "end_time": frame.end_time,
                    "phoneme": frame.phoneme,
                    "mouth_shape": frame.mouth_shape,
                    "speaker": frame.speaker,
                    "confidence": frame.confidence
                }
                for frame in self.lip_sync_frames
            ],
            "emotion_data": [
                {
                    "start_time": frame.start_time,
                    "end_time": frame.end_time,
                    "emotion": frame.emotion,
                    "confidence": frame.confidence,
                    "keywords": frame.keywords,
                    "speaker": frame.speaker
                }
                for frame in self.emotion_frames
            ],
            "video_metadata": self.video_metadata
        }


class CharacterSynthesizerError(Exception):
    """キャラクター合成エラー"""
    pass


class CharacterSynthesizer:
    """キャラクター合成器"""
    
    def __init__(
        self,
        dao: CharacterSynthesisDAO,
        file_manager: FileSystemManager,
        config_manager: ConfigManager,
        llm_client: Optional[GeminiLLMClient] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            dao: キャラクター合成DAO
            file_manager: ファイルシステムマネージャー
            config_manager: 設定マネージャー
            llm_client: LLMクライアント（感情分析用）
            logger: ロガー
        """
        self.dao = dao
        self.file_manager = file_manager
        self.config_manager = config_manager
        self.llm_client = llm_client
        self.logger = logger or logging.getLogger(__name__)
        
        # 音素と口形状のマッピング
        self.phoneme_to_mouth_shape = {
            "a": "a",
            "i": "i",
            "u": "u", 
            "e": "e",
            "o": "o",
            "": "silence",
            "silence": "silence"
        }
    
    async def synthesize_character_animation(self, project_id: str) -> Dict[str, Any]:
        """
        キャラクターアニメーション合成
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            合成結果辞書
            
        Raises:
            CharacterSynthesizerError: 合成エラー
        """
        try:
            self.logger.info(f"キャラクターアニメーション合成開始: project_id={project_id}")
            
            # 1. 入力データを取得
            audio_metadata = self.dao.get_audio_metadata(project_id)
            character_config = self.dao.get_character_config(project_id)
            
            # 2. 感情分析実行
            emotion_data = await self.analyze_emotion_with_llm(project_id)
            
            # 3. 口パク同期データ生成
            lip_sync_frames = self._generate_lip_sync_frames(audio_metadata)
            
            # 4. 感情フレーム生成
            emotion_frames = self._generate_emotion_frames(emotion_data)
            
            # 5. キャラクターフレーム統合
            character_frames = self._integrate_character_frames(
                lip_sync_frames, emotion_frames, character_config
            )
            
            # 6. 動画生成
            video_path = await self._generate_character_video(
                project_id, character_frames, audio_metadata, character_config
            )
            
            # 7. 結果作成
            result = CharacterSynthesisResult(
                character_video_path=video_path,
                total_duration=audio_metadata["total_duration"],
                frame_count=len(character_frames),
                lip_sync_frames=lip_sync_frames,
                emotion_frames=emotion_frames,
                character_frames=character_frames,
                video_metadata=self._create_video_metadata(character_config, audio_metadata)
            )
            
            # 8. データベースに保存
            await self._save_synthesis_result(project_id, result)
            
            self.logger.info(
                f"キャラクターアニメーション合成完了: project_id={project_id}, "
                f"duration={result.total_duration:.2f}s, frames={result.frame_count}"
            )
            
            return result.to_dict()
            
        except Exception as e:
            self.logger.error(f"キャラクターアニメーション合成エラー: project_id={project_id}: {e}")
            raise CharacterSynthesizerError(f"キャラクターアニメーション合成に失敗: {e}")
    
    async def analyze_emotion_with_llm(self, project_id: str) -> Dict[str, Any]:
        """
        LLMを使用した感情分析
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            感情分析結果
        """
        try:
            # 既存の感情分析結果を確認
            existing_emotion = self.dao.get_emotion_analysis(project_id)
            if existing_emotion:
                self.logger.info(f"既存の感情分析結果を使用: project_id={project_id}")
                return existing_emotion
            
            # スクリプトデータを取得
            script_data = self.dao.get_script_data(project_id)
            segments = script_data.get("segments", [])
            
            if not segments:
                raise ValueError("分析するスクリプトセグメントがありません")
            
            if not self.llm_client:
                # LLMクライアントがない場合はデフォルト感情を使用
                self.logger.warning("LLMクライアントがありません。デフォルト感情を使用します。")
                return self._create_default_emotion_data(segments)
            
            # 感情分析プロンプト作成
            prompt = self._create_emotion_analysis_prompt(segments)
            
            # LLM実行
            self.logger.info(f"LLM感情分析実行: project_id={project_id}, segments={len(segments)}")
            response = await self.llm_client.generate_text_async(prompt)
            
            # レスポンス解析
            emotion_data = self._parse_emotion_analysis_response(response, segments)
            
            # データベースに保存
            self.dao.save_emotion_analysis(project_id, emotion_data)
            
            self.logger.info(
                f"LLM感情分析完了: project_id={project_id}, "
                f"analyzed_segments={len(emotion_data.get('segments', []))}"
            )
            
            return emotion_data
            
        except Exception as e:
            self.logger.error(f"感情分析エラー: project_id={project_id}: {e}")
            # フォールバック: デフォルト感情データ
            script_data = self.dao.get_script_data(project_id)
            return self._create_default_emotion_data(script_data.get("segments", []))
    
    def _generate_lip_sync_frames(self, audio_metadata: Dict[str, Any]) -> List[LipSyncFrame]:
        """
        口パク同期フレーム生成
        
        Args:
            audio_metadata: 音声メタデータ
            
        Returns:
            口パク同期フレームのリスト
        """
        timestamps = audio_metadata.get("timestamps", [])
        lip_sync_frames = []
        
        for ts in timestamps:
            phoneme = ts.get("phoneme", "")
            mouth_shape = self.phoneme_to_mouth_shape.get(phoneme, "silence")
            
            frame = LipSyncFrame(
                start_time=ts["start_time"],
                end_time=ts["end_time"],
                phoneme=phoneme,
                mouth_shape=mouth_shape,
                speaker=ts["speaker"],
                confidence=ts.get("confidence", 1.0)
            )
            lip_sync_frames.append(frame)
        
        self.logger.info(f"口パク同期フレーム生成完了: {len(lip_sync_frames)}フレーム")
        return lip_sync_frames
    
    def _generate_emotion_frames(self, emotion_data: Dict[str, Any]) -> List[EmotionFrame]:
        """
        感情フレーム生成
        
        Args:
            emotion_data: 感情分析データ
            
        Returns:
            感情フレームのリスト
        """
        emotion_segments = emotion_data.get("segments", [])
        emotion_frames = []
        
        # 各セグメントから感情フレームを作成
        current_time = 0.0
        for segment in emotion_segments:
            # セグメントの推定時間（実際の音声時間に基づく）
            segment_duration = self._estimate_segment_duration(segment)
            
            frame = EmotionFrame(
                start_time=current_time,
                end_time=current_time + segment_duration,
                emotion=segment.get("detected_emotion", "neutral"),
                confidence=segment.get("confidence", 1.0),
                keywords=segment.get("keywords", []),
                speaker=segment["speaker"]
            )
            emotion_frames.append(frame)
            current_time += segment_duration
        
        self.logger.info(f"感情フレーム生成完了: {len(emotion_frames)}フレーム")
        return emotion_frames
    
    def _integrate_character_frames(
        self,
        lip_sync_frames: List[LipSyncFrame],
        emotion_frames: List[EmotionFrame],
        character_config: Dict[str, Any]
    ) -> List[CharacterFrame]:
        """
        キャラクターフレーム統合
        
        Args:
            lip_sync_frames: 口パク同期フレーム
            emotion_frames: 感情フレーム
            character_config: キャラクター設定
            
        Returns:
            統合されたキャラクターフレーム
        """
        animation_config = character_config.get("animation", {})
        frame_rate = animation_config.get("frame_rate", 30)
        character_positions = animation_config.get("character_position", {})
        
        # 全時間を通してフレームを生成
        if not lip_sync_frames:
            return []
        
        total_duration = max(frame.end_time for frame in lip_sync_frames)
        frame_count = int(total_duration * frame_rate)
        
        character_frames = []
        
        for i in range(frame_count):
            timestamp = i / frame_rate
            
            # 現在時刻の口パク情報を取得
            current_lip_sync = self._find_frame_at_time(lip_sync_frames, timestamp)
            
            # 現在時刻の感情情報を取得
            current_emotion = self._find_emotion_at_time(emotion_frames, timestamp)
            
            if current_lip_sync:
                speaker = current_lip_sync.speaker
                mouth_shape = current_lip_sync.mouth_shape
                emotion = current_emotion.emotion if current_emotion else "neutral"
                position = character_positions.get(speaker, {"x": 500, "y": 300})
                
                frame = CharacterFrame(
                    timestamp=timestamp,
                    speaker=speaker,
                    mouth_shape=mouth_shape,
                    emotion=emotion,
                    position=(position["x"], position["y"]),
                    scale=animation_config.get("character_scale", 0.8)
                )
                character_frames.append(frame)
        
        self.logger.info(f"キャラクターフレーム統合完了: {len(character_frames)}フレーム, duration={total_duration:.2f}s")
        return character_frames
    
    async def _generate_character_video(
        self,
        project_id: str,
        character_frames: List[CharacterFrame],
        audio_metadata: Dict[str, Any],
        character_config: Dict[str, Any]
    ) -> str:
        """
        キャラクター動画生成
        
        Args:
            project_id: プロジェクトID
            character_frames: キャラクターフレーム
            audio_metadata: 音声メタデータ
            character_config: キャラクター設定
            
        Returns:
            生成された動画ファイルパス
        """
        # プロジェクト動画ディレクトリを準備
        project_dir = self.file_manager.get_project_directory(project_id)
        video_dir = os.path.join(project_dir, "files", "video")
        os.makedirs(video_dir, exist_ok=True)
        
        video_path = os.path.join(video_dir, "character_animation.mp4")
        
        if VIDEO_PROCESSING_AVAILABLE:
            # 実際の動画生成（OpenCV使用）
            await self._generate_video_with_opencv(
                character_frames, video_path, character_config
            )
        else:
            # モック動画生成
            await self._generate_video_mock(
                character_frames, video_path, character_config
            )
        
        return video_path
    
    async def _generate_video_with_opencv(
        self,
        character_frames: List[CharacterFrame],
        output_path: str,
        character_config: Dict[str, Any]
    ) -> None:
        """
        OpenCVを使用した実際の動画生成
        """
        animation_config = character_config.get("animation", {})
        width = animation_config.get("video_width", 1920)
        height = animation_config.get("video_height", 1080)
        fps = animation_config.get("frame_rate", 30)
        
        # 動画ライターを初期化
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        try:
            for frame in character_frames:
                # フレーム画像を生成
                img = self._create_character_frame_image(frame, character_config, width, height)
                out.write(img)
            
        finally:
            out.release()
        
        self.logger.info(f"OpenCV動画生成完了: {output_path}, frames={len(character_frames)}")
    
    async def _generate_video_mock(
        self,
        character_frames: List[CharacterFrame],
        output_path: str,
        character_config: Dict[str, Any]
    ) -> None:
        """
        モック動画生成（OpenCV未使用時）
        """
        # 空ファイルを作成（テスト用）
        with open(output_path, 'w') as f:
            f.write(f"Mock video file: {len(character_frames)} frames")
        
        self.logger.info(f"モック動画生成完了: {output_path}, frames={len(character_frames)}")
    
    def _create_character_frame_image(
        self,
        frame: CharacterFrame,
        character_config: Dict[str, Any],
        width: int,
        height: int
    ) -> 'np.ndarray':
        """
        キャラクターフレーム画像を作成
        """
        # 透明背景画像を作成
        img = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 簡易的なキャラクター描画（実際はキャラクター画像を合成）
        color = (100, 150, 200) if frame.speaker == "reimu" else (200, 150, 100)
        cv2.circle(img, frame.position, 50, color, -1)
        
        # 口形状を表す簡易図形
        mouth_offset = self._get_mouth_offset(frame.mouth_shape)
        mouth_pos = (frame.position[0], frame.position[1] + mouth_offset)
        cv2.circle(img, mouth_pos, 10, (255, 255, 255), -1)
        
        return img
    
    def _get_mouth_offset(self, mouth_shape: str) -> int:
        """口形状に基づくオフセット"""
        offsets = {
            "a": 20,
            "i": 10,
            "u": 15,
            "e": 12,
            "o": 18,
            "silence": 5
        }
        return offsets.get(mouth_shape, 5)
    
    async def _save_synthesis_result(
        self,
        project_id: str,
        result: CharacterSynthesisResult
    ) -> None:
        """
        合成結果をデータベースに保存
        """
        # 動画ファイル参照を登録
        video_files = [{
            "file_type": "video",
            "file_category": "intermediate",
            "file_path": result.character_video_path,
            "file_name": os.path.basename(result.character_video_path)
        }]
        
        self.dao.register_video_files(project_id, video_files)
        
        # 合成結果を保存
        self.dao.save_character_synthesis_result(project_id, result.to_dict())
        
        self.logger.info(f"キャラクター合成結果保存完了: project_id={project_id}")
    
    def _create_emotion_analysis_prompt(self, segments: List[Dict[str, Any]]) -> str:
        """感情分析用プロンプト作成"""
        segments_text = ""
        for segment in segments:
            segments_text += f"{segment['segment_id']}. [{segment['speaker']}] {segment['text']}\n"
        
        prompt = f"""
以下の会話セグメントを分析し、各セグメントの感情を判定してください。

会話セグメント:
{segments_text}

各セグメントについて以下の形式で出力してください：

```json
{{
    "segments": [
        {{
            "segment_id": 1,
            "speaker": "reimu",
            "detected_emotion": "happy",
            "confidence": 0.85,
            "keywords": ["楽しい", "嬉しい"]
        }}
    ]
}}
```

感情は以下から選択してください: neutral, happy, sad, surprised, angry

キーワードは感情の判断根拠となった単語を3個以内で抽出してください。
"""
        return prompt
    
    def _parse_emotion_analysis_response(
        self,
        response: str,
        original_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """LLMレスポンス解析"""
        try:
            # JSON部分を抽出
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)
                
                # タイムスタンプを追加
                for segment in data.get("segments", []):
                    segment["timestamp"] = datetime.now().isoformat()
                
                return data
            else:
                return self._create_default_emotion_data(original_segments)
                
        except Exception as e:
            self.logger.warning(f"感情分析レスポンス解析失敗: {e}")
            return self._create_default_emotion_data(original_segments)
    
    def _create_default_emotion_data(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """デフォルト感情データ作成"""
        return {
            "segments": [
                {
                    "segment_id": segment["segment_id"],
                    "speaker": segment["speaker"],
                    "detected_emotion": "neutral",
                    "confidence": 0.7,
                    "keywords": [],
                    "timestamp": datetime.now().isoformat()
                }
                for segment in segments
            ]
        }
    
    def _estimate_segment_duration(self, segment: Dict[str, Any]) -> float:
        """セグメント時間推定"""
        text = segment.get("text", "")
        # 簡易的な推定（1文字0.15秒）
        return max(len(text) * 0.15, 1.0)
    
    def _find_frame_at_time(self, frames: List[LipSyncFrame], timestamp: float) -> Optional[LipSyncFrame]:
        """指定時刻のフレームを検索"""
        for frame in frames:
            if frame.start_time <= timestamp <= frame.end_time:
                return frame
        return None
    
    def _find_emotion_at_time(self, frames: List[EmotionFrame], timestamp: float) -> Optional[EmotionFrame]:
        """指定時刻の感情を検索"""
        for frame in frames:
            if frame.start_time <= timestamp <= frame.end_time:
                return frame
        return None
    
    def _create_video_metadata(
        self,
        character_config: Dict[str, Any],
        audio_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """動画メタデータ作成"""
        animation_config = character_config.get("animation", {})
        
        return {
            "video_width": animation_config.get("video_width", 1920),
            "video_height": animation_config.get("video_height", 1080),
            "frame_rate": animation_config.get("frame_rate", 30),
            "total_duration": audio_metadata.get("total_duration", 0.0),
            "audio_sample_rate": audio_metadata.get("sample_rate", 24000),
            "has_transparency": True,
            "generation_timestamp": datetime.now().isoformat()
        }
    
    async def get_synthesis_result(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        保存された合成結果を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            合成結果辞書、または None
        """
        return self.dao.get_character_synthesis_result(project_id)
    
    async def cleanup_video_files(self, project_id: str) -> None:
        """
        一時動画ファイルをクリーンアップ
        
        Args:
            project_id: プロジェクトID
        """
        try:
            project_dir = self.file_manager.get_project_directory(project_id)
            video_dir = os.path.join(project_dir, "files", "video")
            
            if os.path.exists(video_dir):
                for file in os.listdir(video_dir):
                    if file.startswith("temp_") or file.startswith("intermediate_"):
                        file_path = os.path.join(video_dir, file)
                        os.remove(file_path)
                        self.logger.debug(f"一時ファイル削除: {file_path}")
            
        except Exception as e:
            self.logger.warning(f"動画ファイルクリーンアップエラー: project_id={project_id}: {e}")
    
    async def close(self) -> None:
        """リソースクリーンアップ"""
        if hasattr(self, 'llm_client') and self.llm_client:
            # LLMクライアントのクリーンアップ（必要に応じて）
            pass 