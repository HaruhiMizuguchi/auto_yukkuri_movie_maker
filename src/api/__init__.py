"""
API クライアントモジュール

外部API連携のためのクライアント実装を提供します。
"""

# LLM API クライアント
from .llm_client import (
    GeminiLLMClient,
    GeminiRequest,
    GeminiResponse,
    ModelType,
    OutputFormat
)

# TTS API クライアント
from .tts_client import (
    AivisSpeechClient,
    TTSRequest,
    TTSResponse,
    AudioSettings,
    SpeakerStyle,
    TimestampData
)

# 画像生成 API クライアント
from .image_client import (
    ImageGenerationClient,
    ImageRequest,
    ImageResponse,
    ImageStyle,
    ImageFormat
)

# YouTube API クライアント
from .youtube_client import (
    YouTubeClient,
    VideoUploadRequest,
    VideoUploadResponse,
    VideoMetadata,
    VideoPrivacy
)

__all__ = [
    # LLM API
    "GeminiLLMClient",
    "GeminiRequest", 
    "GeminiResponse",
    "ModelType",
    "OutputFormat",
    
    # TTS API
    "AivisSpeechClient",
    "TTSRequest",
    "TTSResponse",
    "AudioSettings",
    "SpeakerStyle",
    "TimestampData",
    
    # 画像生成 API
    "ImageGenerationClient",
    "ImageRequest",
    "ImageResponse", 
    "ImageStyle",
    "ImageFormat",
    
    # YouTube API
    "YouTubeClient",
    "VideoUploadRequest",
    "VideoUploadResponse",
    "VideoMetadata",
    "VideoPrivacy"
]

# パッケージ初期化 