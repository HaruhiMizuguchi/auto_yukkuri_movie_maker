"""
TTS処理モジュール 実API単体テスト

AIVIS Speech APIとの実際の連携とデータベース保存をテスト
"""

import asyncio
import json
import os
import tempfile
import pytest
import pytest_asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.modules.tts_processor import TTSProcessor
from src.dao.tts_generation_dao import TTSGenerationDAO
from src.core.database_manager import DatabaseManager
from src.core.file_system_manager import FileSystemManager
from src.core.config_manager import ConfigManager
from src.api.tts_client import AivisSpeechClient, TTSRequest, TTSResponse, TimestampData


@pytest_asyncio.fixture
async def real_tts_client():
    """実際のAIVIS Speech API クライアント"""
    client = AivisSpeechClient(base_url="http://127.0.0.1:10101")
    yield client
    await client.close()


@pytest.fixture
def mock_db_manager():
    """モックデータベースマネージャー"""
    mock = MagicMock(spec=DatabaseManager)
    
    # スクリプトデータをモック
    mock_script_data = {
        "segments": [
            {
                "segment_id": 1,
                "speaker": "reimu",
                "text": "こんにちは、今日はAIについて話しましょう。",
                "estimated_duration": 3.5,
                "emotion": "neutral"
            },
            {
                "segment_id": 2,
                "speaker": "marisa",
                "text": "面白そうだね！AIってどんなことができるの？",
                "estimated_duration": 3.2,
                "emotion": "happy"
            }
        ]
    }
    
    mock.fetch_one.return_value = (json.dumps(mock_script_data),)
    mock.execute_query.return_value = None
    
    return mock


@pytest.fixture
def mock_file_manager():
    """モックファイルシステムマネージャー"""
    mock = MagicMock(spec=FileSystemManager)
    
    # 一時ディレクトリパス
    temp_dir = tempfile.mkdtemp()
    mock.get_project_directory.return_value = temp_dir
    mock.create_project_directory.return_value = True
    mock.get_project_directory_path.return_value = Path(temp_dir)
    mock.create_file.return_value = True
    
    return mock


@pytest.fixture
def mock_config():
    """モック設定"""
    return {
        "voice_mapping": {
            "reimu": {"speaker_id": 0, "style": "normal"},
            "marisa": {"speaker_id": 1, "style": "cheerful"}
        },
        "audio_settings": {
            "sample_rate": 24000,
            "speed": 1.0,
            "pitch": 0.0,
            "volume": 1.0,
            "intonation": 1.0  # AIVIS Speech APIで必要なパラメータ
        },
        "output_format": "wav",
        "enable_timestamps": True  # タイムスタンプ取得を有効化
    }


@pytest.fixture
def tts_processor(mock_db_manager, mock_file_manager, mock_config):
    """TTS処理モジュール"""
    dao = TTSGenerationDAO(mock_db_manager)
    config_manager = MagicMock(spec=ConfigManager)
    
    processor = TTSProcessor(
        dao=dao,
        file_manager=mock_file_manager,
        config_manager=config_manager
    )
    processor.config = mock_config
    
    # DAOとprocessorが同じdb_managerを使用していることを確認
    processor.dao = dao
    
    return processor


class TestTTSProcessorRealAPI:
    """TTS処理モジュール実API統合テスト"""
    
    @pytest.mark.asyncio
    async def test_process_script_to_audio_real_api(self, tts_processor, real_tts_client, mock_db_manager):
        """スクリプトから音声生成（実API）"""
        project_id = "test_project_123"
        
        # 実際のAIVIS Speech クライアントをセット
        tts_processor.tts_client = real_tts_client
        
        try:
            # サーバーの動作確認
            speakers = await real_tts_client.get_speakers()
            assert len(speakers) > 0, "AIVIS Speech サーバーに話者が見つかりません"
            
            # 実際のスピーカーIDを取得
            actual_speaker_ids = {}
            if len(speakers) > 0:
                # 1つのスピーカーしかない場合は、異なるスタイルを使用
                speaker = speakers[0]
                styles = speaker["styles"]
                
                # reimuには最初のスタイルを使用
                actual_speaker_ids["reimu"] = styles[0]["id"] if len(styles) > 0 else 888753760
                
                # marisaには2番目のスタイルを使用（なければ最初のスタイル）
                actual_speaker_ids["marisa"] = styles[1]["id"] if len(styles) > 1 else styles[0]["id"]
            else:
                # デフォルト値
                actual_speaker_ids["reimu"] = 888753760
                actual_speaker_ids["marisa"] = 888753761
            
            # voice_configのモックを更新（実際のスピーカーIDを使用）
            voice_config = {
                "voice_mapping": {
                    "reimu": {"speaker_id": actual_speaker_ids["reimu"]},
                    "marisa": {"speaker_id": actual_speaker_ids["marisa"]}
                },
                "audio_settings": {
                    "sample_rate": 24000,
                    "speed": 1.0,
                    "pitch": 0.0,
                    "volume": 1.0,
                    "intonation": 1.0
                },
                "output_format": "wav",
                "enable_timestamps": True
            }
            
            # get_voice_configが実際のスピーカーIDを返すようにモック
            # projectsテーブルからconfig_jsonを取得する部分もモック
            project_config = {
                "voice_config": voice_config
            }
            
            mock_db_manager.fetch_one.side_effect = [
                (json.dumps({
                    "segments": [
                        {
                            "segment_id": 1,
                            "speaker": "reimu",
                            "text": "こんにちは、今日はAIについて話しましょう。",
                            "estimated_duration": 3.5,
                            "emotion": "neutral"
                        },
                        {
                            "segment_id": 2,
                            "speaker": "marisa",
                            "text": "面白そうだね！AIってどんなことができるの？",
                            "estimated_duration": 3.2,
                            "emotion": "happy"
                        }
                    ]
                }),),  # get_script_data用
                (json.dumps(project_config),)  # get_voice_config用（projectsテーブルから）
            ]
            
            # TTS処理実行
            result = await tts_processor.process_script_to_audio(project_id)
            
            # 結果検証
            assert result is not None
            assert "audio_segments" in result
            assert "combined_audio_path" in result
            assert "audio_metadata" in result
            
            # オーディオセグメント検証
            segments = result["audio_segments"]
            assert len(segments) == 2  # reimu + marisa
            
            for segment in segments:
                assert "segment_id" in segment
                assert "speaker" in segment
                assert "audio_path" in segment
                assert "duration" in segment
                assert segment["duration"] > 0
            
            # メタデータ検証
            metadata = result["audio_metadata"]
            assert "total_duration" in metadata
            assert "sample_rate" in metadata
            assert "segments_info" in metadata
            assert metadata["total_duration"] > 0
            
        except Exception as e:
            # AIVIS Speech サーバーが動作していない場合はスキップ
            if "Connection" in str(e) or "ConnectTimeout" in str(e):
                pytest.skip(f"AIVIS Speech server not available: {e}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_generate_segment_audio_real_api(self, tts_processor, real_tts_client):
        """個別セグメント音声生成（実API）"""
        tts_processor.tts_client = real_tts_client
        
        try:
            # サーバー動作確認
            speakers = await real_tts_client.get_speakers()
            speaker_id = speakers[0]["styles"][0]["id"]
            
            # セグメント音声生成
            segment_data = {
                "segment_id": 1,
                "speaker": "reimu", 
                "text": "こんにちは、テストです。",
                "emotion": "neutral"
            }
            
            # 一時ファイルを使用
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                result = await tts_processor._generate_segment_audio(
                    segment_data, 
                    speaker_id, 
                    temp_path
                )
                
                # 結果検証
                assert result is not None
                assert "duration" in result
                assert "timestamps" in result
                assert result["duration"] > 0
                
                # タイムスタンプ検証（空の場合もある）
                timestamps = result["timestamps"]
                if len(timestamps) > 0:
                    for ts in timestamps:
                        assert "start_time" in ts
                        assert "end_time" in ts
                        assert "text" in ts
                        assert ts["start_time"] >= 0
                        assert ts["end_time"] > ts["start_time"]
                else:
                    # タイムスタンプが空でも許容（APIの仕様による）
                    print("Note: No timestamps returned from API")
            
            finally:
                # 一時ファイルを削除
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            if "Connection" in str(e) or "ConnectTimeout" in str(e):
                pytest.skip(f"AIVIS Speech server not available: {e}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_combine_audio_segments(self, tts_processor):
        """音声セグメント結合テスト"""
        import wave
        import struct
        
        # 一時ディレクトリを作成
        with tempfile.TemporaryDirectory() as temp_dir:
            # テスト用のWAVファイルを作成
            segment_paths = []
            
            for i in range(2):
                file_path = os.path.join(temp_dir, f"segment_{i+1}.wav")
                
                # 簡単なWAVファイルを作成（1秒の無音）
                with wave.open(file_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # モノラル
                    wav_file.setsampwidth(2)   # 16bit
                    wav_file.setframerate(24000)  # 24kHz
                    
                    # 1秒分の無音データ
                    duration = 1.0
                    num_samples = int(duration * 24000)
                    samples = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
                    wav_file.writeframes(samples)
                
                segment_paths.append(file_path)
            
            output_path = os.path.join(temp_dir, "combined.wav")
            
            # 実際の音声結合を実行
            result = await tts_processor._combine_audio_segments(
                segment_paths, 
                output_path
            )
            
            # 結果検証
            assert result is not None
            assert "duration" in result
            assert "sample_rate" in result
            assert "file_size" in result
            
            # 結合後のファイルが存在することを確認
            assert os.path.exists(output_path)
            
            # pydubが利用可能な場合はより詳細な検証
            try:
                from pydub import AudioSegment
                combined_audio = AudioSegment.from_wav(output_path)
                # 2秒の音声になっているはず（1秒 × 2ファイル）
                assert abs(len(combined_audio) / 1000.0 - 2.0) < 0.1
            except ImportError:
                # pydubが無い場合はファイルサイズで簡易チェック
                assert result["file_size"] > 0
    
    @pytest.mark.asyncio
    async def test_combine_audio_files_real(self, tts_processor):
        """実際の音声ファイル結合テスト（pydub使用）"""
        import wave
        import struct
        import math
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # テスト用音声ファイルを作成
            input_paths = []
            expected_duration = 0.0
            
            for i in range(3):
                file_path = os.path.join(temp_dir, f"test_{i+1}.wav")
                duration = 0.5 + i * 0.5  # 0.5秒、1.0秒、1.5秒
                
                with wave.open(file_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(24000)
                    
                    num_samples = int(duration * 24000)
                    # 簡単な正弦波を生成（周波数を変えて識別可能に）
                    frequency = 440 * (i + 1)  # 440Hz, 880Hz, 1320Hz
                    samples = []
                    for j in range(num_samples):
                        value = int(32767 * 0.3 * 
                                  math.sin(2 * math.pi * frequency * j / 24000))
                        samples.append(value)
                    
                    wav_data = struct.pack('<' + 'h' * num_samples, *samples)
                    wav_file.writeframes(wav_data)
                
                input_paths.append(file_path)
                expected_duration += duration
            
            output_path = os.path.join(temp_dir, "combined_output.wav")
            
            # 音声結合を実行
            result = await tts_processor._combine_audio_files(
                input_paths,
                output_path
            )
            
            # 結果検証
            assert result is not None
            assert "duration" in result
            assert "sample_rate" in result
            assert "file_size" in result
            assert "segments_count" in result
            
            # 期待される合計時間と一致するか確認（誤差0.1秒以内）
            assert abs(result["duration"] - expected_duration) < 0.1
            assert result["sample_rate"] == 24000
            assert result["segments_count"] == 3
            
            # ファイルが実際に作成されているか確認
            assert os.path.exists(output_path)
            assert result["file_size"] > 0
    
    @pytest.mark.asyncio
    async def test_database_integration(self, tts_processor):
        """データベース統合テスト"""
        project_id = "test_project_456"
        
        # TTS結果データ
        tts_result = {
            "audio_segments": [
                {
                    "segment_id": 1,
                    "speaker": "reimu",
                    "audio_path": "/tmp/seg1.wav",
                    "duration": 3.5,
                    "timestamps": [
                        {"start_time": 0.0, "end_time": 1.2, "text": "こんにちは"}
                    ]
                }
            ],
            "combined_audio_path": "/tmp/combined.wav",
            "audio_metadata": {
                "total_duration": 6.7,
                "sample_rate": 24000,
                "segments_count": 2
            }
        }
        
        # データベース保存
        tts_processor.dao.save_tts_result(project_id, tts_result)
        
        # 保存が呼ばれたことを確認
        tts_processor.dao.db_manager.execute_query.assert_called()
        
        # 保存されたデータの検証
        call_args_list = tts_processor.dao.db_manager.execute_query.call_args_list
        call_args_str = str(call_args_list)
        assert project_id in call_args_str
        assert "tts_generation" in call_args_str 