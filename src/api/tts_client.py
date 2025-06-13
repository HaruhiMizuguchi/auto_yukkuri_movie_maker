"""
AIVIS Speech TTS API クライアント

AIVIS Speech を使用した音声生成、タイムスタンプ処理、
音声品質制御などの機能を提供します。
"""

import asyncio
import aiohttp
import aiofiles
from typing import Any, Dict, List, Optional, Union, BinaryIO
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import json
import tempfile
import shutil

from ..core.api_client import (
    BaseAPIClient,
    APIRequest,
    APIResponse,
    APIClientError,
    AuthenticationError,
    NetworkError,
    RetryConfig,
    RateLimitConfig
)


class SpeakerStyle(Enum):
    """話者スタイル（例: 霊夢、魔理沙など）"""
    REIMU_NORMAL = "reimu_normal"
    REIMU_HAPPY = "reimu_happy"
    REIMU_ANGRY = "reimu_angry"
    MARISA_NORMAL = "marisa_normal"
    MARISA_HAPPY = "marisa_happy"
    MARISA_EXCITED = "marisa_excited"


@dataclass
class AudioSettings:
    """音声生成設定"""
    speaker_id: int = 0
    speed: float = 1.0
    pitch: float = 0.0
    intonation: float = 1.0
    volume: float = 1.0
    pre_phoneme_length: float = 0.1
    post_phoneme_length: float = 0.1


@dataclass
class TimestampData:
    """タイムスタンプデータ"""
    start_time: float
    end_time: float
    text: str
    phoneme: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class TTSRequest:
    """TTS リクエストデータ"""
    text: str
    speaker_id: int = 0
    audio_settings: Optional[AudioSettings] = None
    enable_timestamps: bool = True
    output_format: str = "wav"


@dataclass
class TTSResponse:
    """TTS レスポンスデータ"""
    audio_data: bytes
    audio_length: float
    sample_rate: int
    timestamps: List[TimestampData]
    speaker_info: Dict[str, Any]
    
    @property
    def duration_seconds(self) -> float:
        """音声の長さ（秒）"""
        return self.audio_length
    
    def save_audio(self, file_path: Union[str, Path]) -> None:
        """音声ファイル保存"""
        with open(file_path, 'wb') as f:
            f.write(self.audio_data)


class TTSAPIError(APIClientError):
    """TTS API固有のエラー"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "TTS_API_ERROR",
        speaker_id: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        context.update({"speaker_id": speaker_id})
        kwargs['context'] = context
        
        super().__init__(message, error_code, **kwargs)
        self.speaker_id = speaker_id


class InvalidSpeakerError(TTSAPIError):
    """無効な話者エラー"""
    
    def __init__(self, speaker_id: int):
        super().__init__(
            f"Invalid speaker ID: {speaker_id}",
            error_code="INVALID_SPEAKER",
            speaker_id=speaker_id,
            retry_recommended=False
        )


class AudioGenerationError(TTSAPIError):
    """音声生成エラー"""
    
    def __init__(self, message: str, speaker_id: Optional[int] = None):
        super().__init__(
            message,
            error_code="AUDIO_GENERATION_FAILED",
            speaker_id=speaker_id,
            retry_recommended=True
        )


class AivisSpeechClient(BaseAPIClient):
    """AIVIS Speech TTS API クライアント"""
    
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:10101",
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        # ローカルAPIなので制限は緩め
        if rate_limit_config is None:
            rate_limit_config = RateLimitConfig(
                requests_per_minute=120,
                requests_per_hour=7200,
                burst_limit=10
            )
        
        super().__init__(
            base_url=base_url,
            api_key=None,  # ローカルAPIなのでAPI keyは不要
            retry_config=retry_config,
            rate_limit_config=rate_limit_config,
            logger=logger
        )
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._available_speakers: Optional[List[Dict[str, Any]]] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTPセッション取得"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120)  # 音声生成は時間がかかる
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def send_request(self, request: APIRequest) -> APIResponse:
        """リクエスト送信の具体実装"""
        session = await self._get_session()
        
        url = f"{self.base_url}{request.endpoint}"
        headers = {
            "Content-Type": "application/json",
            **(request.headers or {})
        }
        
        try:
            async with session.request(
                method=request.method,
                url=url,
                headers=headers,
                params=request.params,
                json=request.data,
                timeout=request.timeout
            ) as response:
                response_headers = dict(response.headers)
                
                # バイナリデータ（音声）の場合
                if response.content_type.startswith("audio/"):
                    data = await response.read()
                    return APIResponse(
                        status_code=response.status,
                        headers=response_headers,
                        data=None,
                        raw_content=data
                    )
                # JSONデータの場合
                elif response.content_type == "application/json":
                    data = await response.json()
                else:
                    data = await response.text()
                
                return APIResponse(
                    status_code=response.status,
                    headers=response_headers,
                    data=data
                )
                
        except aiohttp.ClientError as e:
            raise NetworkError(f"HTTP request failed: {e}")
        except asyncio.TimeoutError:
            raise NetworkError("Request timeout")
    
    async def get_speakers(self) -> List[Dict[str, Any]]:
        """利用可能な話者一覧取得"""
        if self._available_speakers is not None:
            return self._available_speakers
        
        api_request = APIRequest(
            endpoint="/speakers",
            method="GET",
            timeout=30
        )
        
        response = await self.send_request_with_retry(api_request)
        
        if not response.is_success:
            raise TTSAPIError(
                f"Failed to get speakers: HTTP {response.status_code}",
                error_code="GET_SPEAKERS_FAILED"
            )
        
        self._available_speakers = response.data
        return self._available_speakers
    
    async def validate_speaker(self, speaker_id: int) -> bool:
        """話者ID検証"""
        speakers = await self.get_speakers()
        
        for speaker in speakers:
            for style in speaker.get("styles", []):
                if style.get("id") == speaker_id:
                    return True
        
        return False
    
    async def get_audio_query(
        self,
        text: str,
        speaker_id: int,
        audio_settings: Optional[AudioSettings] = None
    ) -> Dict[str, Any]:
        """音声クエリ取得"""
        # 話者ID検証
        if not await self.validate_speaker(speaker_id):
            raise InvalidSpeakerError(speaker_id)
        
        params = {
            "speaker": speaker_id,
            "text": text
        }
        
        api_request = APIRequest(
            endpoint="/audio_query",
            method="POST",
            params=params,
            timeout=60
        )
        
        response = await self.send_request_with_retry(api_request)
        
        if not response.is_success:
            raise TTSAPIError(
                f"Failed to get audio query: HTTP {response.status_code}",
                error_code="AUDIO_QUERY_FAILED",
                speaker_id=speaker_id
            )
        
        query_data = response.data
        
        # 音声設定を適用
        if audio_settings:
            query_data.update({
                "speedScale": audio_settings.speed,
                "pitchScale": audio_settings.pitch,
                "intonationScale": audio_settings.intonation,
                "volumeScale": audio_settings.volume,
                "prePhonemeLength": audio_settings.pre_phoneme_length,
                "postPhonemeLength": audio_settings.post_phoneme_length
            })
        
        return query_data
    
    async def synthesize_audio(
        self,
        query_data: Dict[str, Any],
        speaker_id: int
    ) -> bytes:
        """音声合成"""
        params = {"speaker": speaker_id}
        
        api_request = APIRequest(
            endpoint="/synthesis",
            method="POST",
            params=params,
            data=query_data,
            timeout=120  # 音声生成は時間がかかる
        )
        
        response = await self.send_request_with_retry(api_request)
        
        if not response.is_success:
            raise AudioGenerationError(
                f"Failed to synthesize audio: HTTP {response.status_code}",
                speaker_id=speaker_id
            )
        
        if response.raw_content is None:
            raise AudioGenerationError(
                "No audio data in response",
                speaker_id=speaker_id
            )
        
        return response.raw_content
    
    async def generate_audio(self, tts_request: TTSRequest) -> TTSResponse:
        """音声生成（統合メソッド）"""
        audio_settings = tts_request.audio_settings or AudioSettings()
        
        # 音声クエリ取得
        query_data = await self.get_audio_query(
            tts_request.text,
            tts_request.speaker_id,
            audio_settings
        )
        
        # 音声合成
        audio_data = await self.synthesize_audio(
            query_data,
            tts_request.speaker_id
        )
        
        # タイムスタンプ生成
        timestamps = []
        if tts_request.enable_timestamps:
            timestamps = await self._generate_timestamps(
                query_data,
                tts_request.text
            )
        
        # 話者情報取得
        speakers = await self.get_speakers()
        speaker_info = self._find_speaker_info(speakers, tts_request.speaker_id)
        
        # 音声長さ計算（クエリデータから推定）
        audio_length = self._calculate_audio_length(query_data)
        
        return TTSResponse(
            audio_data=audio_data,
            audio_length=audio_length,
            sample_rate=24000,  # AIVIS Speech デフォルト
            timestamps=timestamps,
            speaker_info=speaker_info
        )
    
    async def _generate_timestamps(
        self,
        query_data: Dict[str, Any],
        text: str
    ) -> List[TimestampData]:
        """タイムスタンプ生成"""
        timestamps = []
        
        # accent_phrases からタイミング情報を抽出
        accent_phrases = query_data.get("accent_phrases", [])
        current_time = query_data.get("prePhonemeLength", 0.1)
        
        for phrase in accent_phrases:
            moras = phrase.get("moras", [])
            
            for mora in moras:
                consonant_length = mora.get("consonant_length")
                vowel_length = mora.get("vowel_length", 0)
                
                # 子音
                if consonant_length and consonant_length > 0:
                    consonant = mora.get("consonant", "")
                    if consonant:
                        timestamps.append(TimestampData(
                            start_time=current_time,
                            end_time=current_time + consonant_length,
                            text=consonant,
                            phoneme=consonant
                        ))
                        current_time += consonant_length
                
                # 母音
                vowel = mora.get("vowel", "")
                if vowel and vowel_length > 0:
                    timestamps.append(TimestampData(
                        start_time=current_time,
                        end_time=current_time + vowel_length,
                        text=vowel,
                        phoneme=vowel
                    ))
                    current_time += vowel_length
            
            # ポーズ
            pause_mora = phrase.get("pause_mora")
            if pause_mora:
                pause_length = pause_mora.get("vowel_length", 0)
                if pause_length > 0:
                    timestamps.append(TimestampData(
                        start_time=current_time,
                        end_time=current_time + pause_length,
                        text="[pause]",
                        phoneme="pau"
                    ))
                    current_time += pause_length
        
        # post_phoneme_lengthを追加
        current_time += query_data.get("postPhonemeLength", 0.1)
        
        return timestamps
    
    def _find_speaker_info(
        self,
        speakers: List[Dict[str, Any]],
        speaker_id: int
    ) -> Dict[str, Any]:
        """話者情報取得"""
        for speaker in speakers:
            for style in speaker.get("styles", []):
                if style.get("id") == speaker_id:
                    return {
                        "speaker_name": speaker.get("name", ""),
                        "style_name": style.get("name", ""),
                        "speaker_id": speaker_id,
                        "speaker_uuid": speaker.get("speaker_uuid", "")
                    }
        
        return {"speaker_id": speaker_id}
    
    def _calculate_audio_length(self, query_data: Dict[str, Any]) -> float:
        """音声長さ計算"""
        total_length = 0.0
        
        # pre_phoneme_length
        total_length += query_data.get("prePhonemeLength", 0.1)
        
        # accent_phrases の長さ
        accent_phrases = query_data.get("accent_phrases", [])
        for phrase in accent_phrases:
            moras = phrase.get("moras", [])
            for mora in moras:
                consonant_length = mora.get("consonant_length") or 0
                vowel_length = mora.get("vowel_length") or 0
                total_length += consonant_length + vowel_length
            
            # ポーズ
            pause_mora = phrase.get("pause_mora")
            if pause_mora:
                total_length += pause_mora.get("vowel_length") or 0
        
        # post_phoneme_length
        total_length += query_data.get("postPhonemeLength", 0.1)
        
        return total_length
    
    async def batch_generate_audio(
        self,
        requests: List[TTSRequest]
    ) -> List[TTSResponse]:
        """バッチ音声生成"""
        responses = []
        
        for request in requests:
            try:
                response = await self.generate_audio(request)
                responses.append(response)
            except Exception as e:
                self.logger.error(f"Failed to generate audio for text '{request.text}': {e}")
                # エラーでも続行し、空のレスポンスを追加
                responses.append(TTSResponse(
                    audio_data=b"",
                    audio_length=0.0,
                    sample_rate=24000,
                    timestamps=[],
                    speaker_info={"speaker_id": request.speaker_id}
                ))
        
        return responses
    
    async def close(self):
        """リソースクリーンアップ"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 