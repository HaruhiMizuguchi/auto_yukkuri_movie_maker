"""
画像生成 API クライアント

Gemini 2.0 Flash Preview Image Generation を使用した画像生成、
テキストから画像生成、画像編集などの機能を提供します。
"""

import asyncio
import base64
import os
import httpx
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import io
from PIL import Image
import google.genai as genai
from google.genai.types import GenerateContentConfig, Part, Content

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


class ImageFormat(Enum):
    """画像フォーマット"""
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class ImageStyle(Enum):
    """画像スタイル"""
    REALISTIC = "realistic"
    ANIME = "anime"
    CARTOON = "cartoon"
    ARTISTIC = "artistic"
    PHOTOGRAPHIC = "photographic"


class ResponseModality(Enum):
    """レスポンスモダリティ"""
    TEXT = "TEXT"
    IMAGE = "IMAGE"


@dataclass
class ImageRequest:
    """画像生成リクエストデータ"""
    prompt: str
    response_modalities: List[ResponseModality] = None
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    
    def __post_init__(self):
        if self.response_modalities is None:
            self.response_modalities = [ResponseModality.TEXT, ResponseModality.IMAGE]


@dataclass
class ImageEditRequest:
    """画像編集リクエストデータ"""
    prompt: str
    image_data: bytes
    mime_type: str = "image/png"
    response_modalities: List[ResponseModality] = None
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    
    def __post_init__(self):
        if self.response_modalities is None:
            self.response_modalities = [ResponseModality.TEXT, ResponseModality.IMAGE]


@dataclass
class ImageResponse:
    """画像生成レスポンスデータ"""
    image_data: bytes
    text_content: Optional[str] = None
    format: ImageFormat = ImageFormat.PNG
    generation_metadata: Optional[Dict[str, Any]] = None
    
    def save_image(self, file_path: Union[str, Path]) -> None:
        """画像ファイル保存"""
        with open(file_path, 'wb') as f:
            f.write(self.image_data)
    
    def to_pil_image(self) -> Image.Image:
        """PIL Image に変換"""
        return Image.open(io.BytesIO(self.image_data))
    
    @property
    def size(self) -> Tuple[int, int]:
        """画像サイズ（幅、高さ）"""
        try:
            pil_image = self.to_pil_image()
            return pil_image.size
        except Exception:
            return (0, 0)


class ImageGenerationError(APIClientError):
    """画像生成API固有のエラー"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "IMAGE_GENERATION_ERROR",
        prompt: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        context.update({"prompt": prompt})
        kwargs['context'] = context
        
        super().__init__(message, error_code, **kwargs)
        self.prompt = prompt


class InvalidPromptError(ImageGenerationError):
    """無効なプロンプトエラー"""
    
    def __init__(self, message: str, prompt: str):
        super().__init__(
            message,
            error_code="INVALID_PROMPT",
            prompt=prompt,
            retry_recommended=False
        )


class ContentFilterError(ImageGenerationError):
    """コンテンツフィルターエラー"""
    
    def __init__(
        self,
        message: str,
        prompt: str,
        filter_details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code="CONTENT_FILTERED",
            prompt=prompt,
            retry_recommended=False,
            context={"filter_details": filter_details}
        )
        self.filter_details = filter_details


class ImageGenerationClient(BaseAPIClient):
    """Gemini 2.0 画像生成 API クライアント"""
    
    MODEL_NAME = "gemini-2.0-flash-preview-image-generation"
    
    def __init__(
        self,
        api_key: str,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        # Gemini の制限に合わせた設定
        if rate_limit_config is None:
            rate_limit_config = RateLimitConfig(
                requests_per_minute=60,  # Gemini API の制限
                requests_per_hour=1000,
                burst_limit=5
            )
        
        super().__init__(
            base_url="https://generativelanguage.googleapis.com",
            api_key=api_key,
            retry_config=retry_config,
            rate_limit_config=rate_limit_config,
            logger=logger
        )
        
        # プロキシ設定を無効化（simple_gemini_test.py と同様）
        for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY",
                  "http_proxy","https_proxy","all_proxy"):
            os.environ.pop(k, None)
        
        # Gemini クライアント初期化
        self._client = genai.Client(api_key=api_key)
        
        # httpx クライアントを trust_env=False に設定（simple_gemini_test.py と同様）
        new_httpx = httpx.Client(timeout=60.0, trust_env=False)
        old_httpx = self._client._api_client._httpx_client
        old_httpx.close()
        self._client._api_client._httpx_client = new_httpx
        
        self.logger.info("Gemini 画像生成クライアントを初期化しました")
    
    async def send_request(self, request: APIRequest) -> APIResponse:
        """リクエスト送信の具体実装（ここでは使用しない）"""
        # Gemini クライアントを直接使用するため、この関数は使用しない
        raise NotImplementedError("Use Gemini client directly")
    
    def _create_generate_config(
        self,
        response_modalities: List[ResponseModality],
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> GenerateContentConfig:
        """生成設定作成"""
        config_params = {
            "response_modalities": [modality.value for modality in response_modalities]
        }
        
        if max_output_tokens is not None:
            config_params["max_output_tokens"] = max_output_tokens
        if temperature is not None:
            config_params["temperature"] = temperature
        if top_p is not None:
            config_params["top_p"] = top_p
        
        return GenerateContentConfig(**config_params)
    
    def _extract_images_from_response(self, response) -> List[ImageResponse]:
        """レスポンスから画像データを抽出"""
        images = []
        text_content = None
        
        for part in response.candidates[0].content.parts:
            # テキストコンテンツの抽出
            try:
                if part.text is not None:
                    text_content = part.text
            except AttributeError:
                pass
            
            # 画像データの抽出
            try:
                if part.inline_data is not None and part.inline_data.data is not None:
                    image_data = part.inline_data.data
                    images.append(ImageResponse(
                        image_data=image_data,
                        text_content=text_content,
                        generation_metadata={
                            "model": self.MODEL_NAME,
                            "prompt_used": True
                        }
                    ))
            except AttributeError:
                pass
        
        if not images:
            raise ImageGenerationError(
                "No images were generated in the response",
                error_code="NO_IMAGES_GENERATED"
            )
        
        return images
    
    async def _check_rate_limit(self) -> None:
        """非同期レート制限チェック"""
        if not self._can_make_request():
            status = self.get_rate_limit_status()
            wait_time = status["time_until_minute_reset"] + 1.0
            self.logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
            await asyncio.sleep(wait_time)
    
    async def generate_images(self, image_request: ImageRequest) -> List[ImageResponse]:
        """画像生成（テキストから画像）"""
        try:
            await self._check_rate_limit()
            
            config = self._create_generate_config(
                response_modalities=image_request.response_modalities,
                max_output_tokens=image_request.max_output_tokens,
                temperature=image_request.temperature,
                top_p=image_request.top_p
            )
            
            response = self._client.models.generate_content(
                model=self.MODEL_NAME,
                contents=image_request.prompt,
                config=config
            )
            
            # リクエスト記録
            self._record_request()
            
            return self._extract_images_from_response(response)
            
        except Exception as e:
            if "content policy" in str(e).lower() or "safety" in str(e).lower():
                raise ContentFilterError(
                    f"Content filtered: {e}",
                    prompt=image_request.prompt
                )
            elif "invalid" in str(e).lower() and "prompt" in str(e).lower():
                raise InvalidPromptError(
                    f"Invalid prompt: {e}",
                    prompt=image_request.prompt
                )
            else:
                raise ImageGenerationError(
                    f"Image generation failed: {e}",
                    prompt=image_request.prompt
                )
    
    async def edit_image(self, edit_request: ImageEditRequest) -> List[ImageResponse]:
        """画像編集（画像 + テキストから画像）"""
        try:
            await self._check_rate_limit()
            
            # PIL Imageオブジェクトを作成
            pil_image = Image.open(io.BytesIO(edit_request.image_data))
            
            config = self._create_generate_config(
                response_modalities=edit_request.response_modalities,
                max_output_tokens=edit_request.max_output_tokens,
                temperature=edit_request.temperature,
                top_p=edit_request.top_p
            )
            
            contents = [edit_request.prompt, pil_image]
            
            response = self._client.models.generate_content(
                model=self.MODEL_NAME,
                contents=contents,
                config=config
            )
            
            # リクエスト記録
            self._record_request()
            
            return self._extract_images_from_response(response)
            
        except Exception as e:
            if "content policy" in str(e).lower() or "safety" in str(e).lower():
                raise ContentFilterError(
                    f"Content filtered during image editing: {e}",
                    prompt=edit_request.prompt
                )
            elif "invalid" in str(e).lower():
                raise InvalidPromptError(
                    f"Invalid edit request: {e}",
                    prompt=edit_request.prompt
                )
            else:
                raise ImageGenerationError(
                    f"Image editing failed: {e}",
                    prompt=edit_request.prompt
                )
    
    async def batch_generate_images(
        self,
        requests: List[ImageRequest]
    ) -> List[List[ImageResponse]]:
        """バッチ画像生成"""
        results = []
        
        for request in requests:
            try:
                images = await self.generate_images(request)
                results.append(images)
            except Exception as e:
                self.logger.error(f"Batch generation failed for prompt: {request.prompt[:50]}..., error: {e}")
                results.append([])
        
        return results
    
    async def generate_with_conversation(
        self,
        conversation_history: List[Dict[str, Any]]
    ) -> List[ImageResponse]:
        """会話履歴を使った画像生成"""
        try:
            await self._check_rate_limit()
            
            # 会話履歴を Gemini 形式に変換
            contents = []
            for item in conversation_history:
                if item.get("type") == "text":
                    contents.append(item["content"])
                elif item.get("type") == "image":
                    # Base64デコードして PIL Image に変換
                    image_data = base64.b64decode(item["content"])
                    pil_image = Image.open(io.BytesIO(image_data))
                    contents.append(pil_image)
            
            config = self._create_generate_config(
                response_modalities=[ResponseModality.TEXT, ResponseModality.IMAGE]
            )
            
            response = self._client.models.generate_content(
                model=self.MODEL_NAME,
                contents=contents,
                config=config
            )
            
            # リクエスト記録
            self._record_request()
            
            return self._extract_images_from_response(response)
            
        except Exception as e:
            raise ImageGenerationError(f"Conversational image generation failed: {e}")
    
    async def close(self):
        """リソースのクリーンアップ"""
        # Gemini クライアントは特別なクリーンアップ不要
        pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 