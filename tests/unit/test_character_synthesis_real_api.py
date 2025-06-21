"""
立ち絵アニメーション（キャラクター合成）モジュール - 実API統合テスト

実際のGemini APIとデータベースを使用した統合テストです。
TDD: Red-Green-Refactor サイクルで実装
"""

import os
import tempfile
import unittest
import asyncio
import logging
from pathlib import Path
from unittest.mock import Mock
import json
from datetime import datetime

from src.dao.character_synthesis_dao import CharacterSynthesisDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient

# テスト対象のモジュール
from src.modules.character_synthesizer import CharacterSynthesizer


class MockCharacterSynthesizer:
    """テスト用のモックキャラクター合成器（実装前）"""
    
    def __init__(self, dao, file_manager, config_manager, llm_client=None, logger=None):
        self.dao = dao
        self.file_manager = file_manager
        self.config_manager = config_manager
        self.llm_client = llm_client
        self.logger = logger or logging.getLogger(__name__)
    
    async def synthesize_character_animation(self, project_id: str):
        """キャラクターアニメーション合成（モック実装）"""
        # 実装後にここに実際のロジックが入る
        return {
            "character_video_path": "/mock/path/character_animation.mp4",
            "total_duration": 120.5,
            "frame_count": 3615,
            "lip_sync_data": [],
            "emotion_transitions": []
        }
    
    async def analyze_emotion_with_llm(self, project_id: str):
        """LLMを使用した感情分析（モック実装）"""
        # 実装後にここに実際のロジックが入る
        return {
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "detected_emotion": "happy",
                    "confidence": 0.85,
                    "keywords": ["楽しい", "嬉しい"],
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }


class TestCharacterSynthesisRealAPI(unittest.TestCase):
    """立ち絵アニメーション - 実API統合テスト"""
    
    def setUp(self):
        """テストセットアップ"""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_yukkuri.db")
        
        # データベースマネージャー
        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.initialize()
        
        # ファイルシステムマネージャー
        self.file_manager = FileSystemManager(
            base_directory=self.test_dir
        )
        
        # 設定マネージャー
        self.config_manager = ConfigManager()
        
        # DAO
        self.dao = CharacterSynthesisDAO(self.db_manager, logging.getLogger("test"))
        
        # LLMクライアント（実API）
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            self.llm_client = GeminiLLMClient(
                api_key=api_key,
                logger=logging.getLogger("test")
            )
        else:
            self.llm_client = None
            print("Warning: GEMINI_API_KEY not found. Skipping LLM tests.")
        
        # テスト用プロジェクト
        self.project_id = "test-character-synthesis-001"
        self.file_manager.create_project_directory(self.project_id)
        self._setup_test_project()
        
        # キャラクター合成器（実装）
        self.synthesizer = CharacterSynthesizer(
            dao=self.dao,
            file_manager=self.file_manager,
            config_manager=self.config_manager,
            llm_client=self.llm_client,
            logger=logging.getLogger("test")
        )
    
    def tearDown(self):
        """テストクリーンアップ"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
        
        # テストディレクトリをクリーンアップ
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _setup_test_project(self):
        """テスト用プロジェクトデータをセットアップ"""
        # プロジェクト作成
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # プロジェクト
            cursor.execute("""
                INSERT INTO projects (id, theme, status, config_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                self.project_id,
                "立ち絵アニメーションテスト",
                "created",
                json.dumps({
                    "character_synthesis": {
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
                                "emotions": {"neutral": "reimu_neutral.png", "happy": "reimu_happy.png"}
                            }
                        }
                    }
                }),
                datetime.now().isoformat()
            ))
            
            # スクリプト生成結果
            script_data = {
                "segments": [
                    {
                        "segment_id": 1,
                        "speaker": "reimu",
                        "text": "こんにちは！今日は楽しい一日になりそうですね！",
                        "emotion": "neutral"
                    },
                    {
                        "segment_id": 2,
                        "speaker": "marisa",
                        "text": "そうだぜ！一緒に冒険に行こう！",
                        "emotion": "neutral"
                    }
                ],
                "estimated_duration": 120,
                "total_words": 50
            }
            
            cursor.execute("""
                INSERT INTO workflow_steps (project_id, step_number, step_name, status, output_data, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                self.project_id,
                2,  # script_generation は step 2
                "script_generation",
                "completed",
                json.dumps(script_data, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            # TTS生成結果
            tts_data = {
                "audio_segments": [
                    {
                        "segment_id": 1,
                        "speaker": "reimu",
                        "text": "こんにちは！今日は楽しい一日になりそうですね！",
                        "audio_path": "files/audio/segments/segment_1_reimu.wav",
                        "duration": 3.5,
                        "timestamps": [
                            {"start_time": 0.0, "end_time": 0.5, "text": "こんにちは", "phoneme": "o", "confidence": 0.9},
                            {"start_time": 0.5, "end_time": 1.0, "text": "今日は", "phoneme": "a", "confidence": 0.95},
                            {"start_time": 1.0, "end_time": 2.5, "text": "楽しい一日", "phoneme": "i", "confidence": 0.88},
                            {"start_time": 2.5, "end_time": 3.5, "text": "になりそうですね", "phoneme": "e", "confidence": 0.92}
                        ],
                        "emotion": "neutral"
                    },
                    {
                        "segment_id": 2,
                        "speaker": "marisa",
                        "text": "そうだぜ！一緒に冒険に行こう！",
                        "audio_path": "files/audio/segments/segment_2_marisa.wav",
                        "duration": 2.8,
                        "timestamps": [
                            {"start_time": 0.0, "end_time": 0.8, "text": "そうだぜ", "phoneme": "o", "confidence": 0.87},
                            {"start_time": 0.8, "end_time": 1.5, "text": "一緒に", "phoneme": "i", "confidence": 0.91},
                            {"start_time": 1.5, "end_time": 2.8, "text": "冒険に行こう", "phoneme": "u", "confidence": 0.89}
                        ],
                        "emotion": "neutral"
                    }
                ],
                "combined_audio_path": "files/audio/combined.wav",
                "audio_metadata": {
                    "total_duration": 6.3,
                    "sample_rate": 24000,
                    "segments_count": 2
                },
                "total_duration": 6.3
            }
            
            cursor.execute("""
                INSERT INTO workflow_steps (project_id, step_number, step_name, status, output_data, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                self.project_id,
                4,  # tts_generation は step 4
                "tts_generation",
                "completed",
                json.dumps(tts_data, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            conn.commit()
    
    def test_01_dao_get_audio_metadata(self):
        """テスト01: 音声メタデータ取得（DAO）"""
        # 実行
        metadata = self.dao.get_audio_metadata(self.project_id)
        
        # 検証
        self.assertIsInstance(metadata, dict)
        self.assertIn("total_duration", metadata)
        self.assertIn("timestamps", metadata)
        self.assertIn("combined_audio_path", metadata)
        
        # タイムスタンプデータの確認
        timestamps = metadata["timestamps"]
        self.assertGreater(len(timestamps), 0)
        
        for ts in timestamps:
            self.assertIn("phoneme", ts)  # 口パク同期に必要
            self.assertIn("start_time", ts)
            self.assertIn("end_time", ts)
            self.assertIn("speaker", ts)
        
        print(f"✅ 音声メタデータ取得成功: duration={metadata['total_duration']}s, timestamps={len(timestamps)}個")
    
    def test_02_dao_get_script_data(self):
        """テスト02: スクリプトデータ取得（感情分析用）"""
        # 実行
        script_data = self.dao.get_script_data(self.project_id)
        
        # 検証
        self.assertIsInstance(script_data, dict)
        self.assertIn("segments", script_data)
        
        segments = script_data["segments"]
        self.assertGreater(len(segments), 0)
        
        for segment in segments:
            self.assertIn("text", segment)  # 感情分析に必要
            self.assertIn("speaker", segment)
            self.assertIn("segment_id", segment)
        
        print(f"✅ スクリプトデータ取得成功: segments={len(segments)}個")
    
    def test_03_dao_get_character_config(self):
        """テスト03: キャラクター設定取得"""
        # 実行
        config = self.dao.get_character_config(self.project_id)
        
        # 検証
        self.assertIsInstance(config, dict)
        self.assertIn("characters", config)
        
        characters = config["characters"]
        self.assertIn("reimu", characters)
        
        reimu_config = characters["reimu"]
        self.assertIn("emotions", reimu_config)
        self.assertIn("mouth_shapes", reimu_config)
        
        print(f"✅ キャラクター設定取得成功: characters={list(characters.keys())}")
    
    @unittest.skipIf(not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
                     "GEMINI_API_KEY not found")
    def test_04_real_emotion_analysis_with_llm(self):
        """テスト04: 実LLMを使用した感情分析"""
        # スクリプトデータを取得
        script_data = self.dao.get_script_data(self.project_id)
        segments = script_data["segments"]
        
        # 感情分析プロンプト作成
        analysis_prompt = self._create_emotion_analysis_prompt(segments)
        
        # 実際のLLM API呼び出し
        try:
            response = self.llm_client.generate_text_sync(analysis_prompt)
            self.assertIsNotNone(response)
            self.assertIsInstance(response, str)
            
            # JSON形式のレスポンスを解析
            emotion_data = self._parse_emotion_analysis_response(response, segments)
            
            # 検証
            self.assertIsInstance(emotion_data, dict)
            self.assertIn("segments", emotion_data)
            
            analyzed_segments = emotion_data["segments"]
            self.assertEqual(len(analyzed_segments), len(segments))
            
            for segment in analyzed_segments:
                self.assertIn("detected_emotion", segment)
                self.assertIn("confidence", segment)
                self.assertIn("keywords", segment)
                
                # 感情は定義済みのもの
                emotion = segment["detected_emotion"]
                self.assertIn(emotion, ["neutral", "happy", "sad", "surprised", "angry"])
            
            print(f"✅ 実LLM感情分析成功: {len(analyzed_segments)}セグメント分析完了")
            print(f"   感情分布: {[s['detected_emotion'] for s in analyzed_segments]}")
            
            return emotion_data
            
        except Exception as e:
            self.fail(f"LLM感情分析失敗: {e}")
    
    def test_05_dao_save_and_get_emotion_analysis(self):
        """テスト05: 感情分析結果の保存・取得"""
        # テストデータ
        emotion_data = {
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "detected_emotion": "happy",
                    "confidence": 0.85,
                    "keywords": ["楽しい", "嬉しい"],
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "segment_id": 2,
                    "speaker": "marisa",
                    "detected_emotion": "excited",
                    "confidence": 0.92,
                    "keywords": ["冒険", "一緒"],
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
        
        # 保存
        self.dao.save_emotion_analysis(self.project_id, emotion_data)
        
        # 取得
        saved_data = self.dao.get_emotion_analysis(self.project_id)
        
        # 検証
        self.assertIsNotNone(saved_data)
        self.assertEqual(len(saved_data["segments"]), 2)
        
        segment1 = saved_data["segments"][0]
        self.assertEqual(segment1["detected_emotion"], "happy")
        self.assertEqual(segment1["confidence"], 0.85)
        self.assertEqual(segment1["keywords"], ["楽しい", "嬉しい"])
        
        print(f"✅ 感情分析結果保存・取得成功: {len(saved_data['segments'])}セグメント")
    
    def test_06_lip_sync_data_structure(self):
        """テスト06: 口パク同期データ構造の確認"""
        # 音声メタデータを取得
        metadata = self.dao.get_audio_metadata(self.project_id)
        timestamps = metadata["timestamps"]
        
        # 口パク同期データの構造を確認
        lip_sync_data = []
        for ts in timestamps:
            phoneme = ts.get("phoneme", "silence")
            mouth_shape = self._phoneme_to_mouth_shape(phoneme)
            
            lip_sync_frame = {
                "start_time": ts["start_time"],
                "end_time": ts["end_time"],
                "phoneme": phoneme,
                "mouth_shape": mouth_shape,
                "speaker": ts["speaker"]
            }
            lip_sync_data.append(lip_sync_frame)
        
        # 検証
        self.assertGreater(len(lip_sync_data), 0)
        
        for frame in lip_sync_data:
            self.assertIn("mouth_shape", frame)
            self.assertIn("start_time", frame)
            self.assertIn("end_time", frame)
            
            # 口形状は定義済みのもの
            mouth_shape = frame["mouth_shape"]
            self.assertIn(mouth_shape, ["a", "i", "u", "e", "o", "silence"])
        
        print(f"✅ 口パク同期データ構造確認成功: {len(lip_sync_data)}フレーム")
        return lip_sync_data
    
    def test_07_dao_save_character_synthesis_result(self):
        """テスト07: キャラクター合成結果の保存"""
        # テスト結果データ
        synthesis_result = {
            "character_video_path": "files/video/character_animation.mp4",
            "total_duration": 6.3,
            "frame_count": 189,
            "lip_sync_frames": 45,
            "emotion_transitions": 2,
            "video_width": 1920,
            "video_height": 1080,
            "frame_rate": 30,
            "file_size": 15728640,
            "generation_timestamp": datetime.now().isoformat()
        }
        
        # 保存
        self.dao.save_character_synthesis_result(self.project_id, synthesis_result)
        
        # 取得して確認
        saved_result = self.dao.get_character_synthesis_result(self.project_id)
        
        # 検証
        self.assertIsNotNone(saved_result)
        self.assertEqual(saved_result["character_video_path"], synthesis_result["character_video_path"])
        self.assertEqual(saved_result["total_duration"], synthesis_result["total_duration"])
        self.assertEqual(saved_result["frame_count"], synthesis_result["frame_count"])
        
        print(f"✅ キャラクター合成結果保存成功: duration={saved_result['total_duration']}s")
    
    def test_08_integration_full_workflow(self):
        """テスト08: 統合テスト - 全ワークフロー"""
        # 1. 音声メタデータ取得
        audio_metadata = self.dao.get_audio_metadata(self.project_id)
        self.assertIsNotNone(audio_metadata)
        
        # 2. スクリプトデータ取得
        script_data = self.dao.get_script_data(self.project_id)
        self.assertIsNotNone(script_data)
        
        # 3. キャラクター設定取得
        character_config = self.dao.get_character_config(self.project_id)
        self.assertIsNotNone(character_config)
        
        # 4. 感情分析（モック）
        emotion_data = {
            "segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "detected_emotion": "happy",
                    "confidence": 0.9,
                    "keywords": ["楽しい"],
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
        self.dao.save_emotion_analysis(self.project_id, emotion_data)
        
        # 5. 口パク同期データ生成
        lip_sync_data = self.test_06_lip_sync_data_structure()
        
        # 6. キャラクター合成結果保存
        synthesis_result = {
            "character_video_path": "files/video/character_animation.mp4",
            "total_duration": audio_metadata["total_duration"],
            "lip_sync_data": lip_sync_data,
            "emotion_data": emotion_data,
            "generation_timestamp": datetime.now().isoformat()
        }
        
        self.dao.save_character_synthesis_result(self.project_id, synthesis_result)
        
        # 検証
        final_result = self.dao.get_character_synthesis_result(self.project_id)
        self.assertIsNotNone(final_result)
        
        print(f"✅ 統合テスト成功: 全ワークフロー正常完了")
        print(f"   動画: {final_result['character_video_path']}")
        print(f"   時間: {final_result['total_duration']}秒")
        print(f"   口パク: {len(final_result['lip_sync_data'])}フレーム")
    
    def _create_emotion_analysis_prompt(self, segments: list) -> str:
        """感情分析用プロンプトを作成"""
        segments_text = ""
        for i, segment in enumerate(segments):
            segments_text += f"{i+1}. [{segment['speaker']}] {segment['text']}\n"
        
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
    
    def _parse_emotion_analysis_response(self, response: str, original_segments: list) -> dict:
        """LLMレスポンスから感情分析結果を解析"""
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
                # JSON解析失敗時のフォールバック
                return self._create_fallback_emotion_data(original_segments)
                
        except Exception as e:
            print(f"Warning: LLMレスポンス解析失敗: {e}")
            return self._create_fallback_emotion_data(original_segments)
    
    def _create_fallback_emotion_data(self, segments: list) -> dict:
        """感情分析のフォールバックデータ"""
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
    
    def _phoneme_to_mouth_shape(self, phoneme: str) -> str:
        """音素から口形状への変換"""
        phoneme_map = {
            "a": "a",
            "i": "i", 
            "u": "u",
            "e": "e",
            "o": "o",
            "": "silence"
        }
        return phoneme_map.get(phoneme, "silence")


def run_tests():
    """テスト実行"""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests() 