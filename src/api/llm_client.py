"""
Gemini LLM API クライアント

Google Gemini API を使用したテキスト生成、画像生成付きテキスト生成、
構造化出力生成などの機能を提供します。
"""

import json
import asyncio
import os
import httpx
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

from google import genai
from google.genai import types

from ..core.api_client import (
    APIClientError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
    RetryConfig,
    RateLimitConfig
)


class ModelType(Enum):
    """利用可能なGeminiモデル"""
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_2_0_FLASH_EXP = "gemini-2.0-flash-exp"
    GEMINI_2_0_FLASH_PREVIEW = "gemini-2.0-flash-preview-image-generation"


class OutputFormat(Enum):
    """出力フォーマット"""
    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"


@dataclass
class GeminiRequest:
    """Gemini APIリクエストデータ"""
    prompt: str
    model: ModelType = ModelType.GEMINI_2_0_FLASH
    max_output_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    output_format: OutputFormat = OutputFormat.TEXT
    structured_schema: Optional[Dict[str, Any]] = None
    system_instruction: Optional[str] = None
    safety_settings: Optional[List[Dict[str, Any]]] = None


@dataclass
class GeminiResponse:
    """Gemini APIレスポンスデータ"""
    text: str
    model: str
    finish_reason: str
    safety_ratings: List[Dict[str, Any]]
    usage_metadata: Dict[str, Any]
    candidates: List[Dict[str, Any]]
    
    @property
    def is_blocked(self) -> bool:
        """安全性フィルターでブロックされたかどうか"""
        return self.finish_reason in ["SAFETY", "RECITATION"]
    
    @property
    def token_count(self) -> int:
        """生成されたトークン数"""
        return self.usage_metadata.get("candidatesTokenCount", 0)
    
    @property
    def prompt_token_count(self) -> int:
        """プロンプトのトークン数"""
        return self.usage_metadata.get("promptTokenCount", 0)


class GeminiAPIError(APIClientError):
    """Gemini API固有のエラー"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "GEMINI_API_ERROR",
        api_error_code: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        context.update({
            "api_error_code": api_error_code,
            "model": model
        })
        kwargs['context'] = context
        
        super().__init__(message, error_code, **kwargs)
        self.api_error_code = api_error_code
        self.model = model


class ContentBlockedError(GeminiAPIError):
    """コンテンツ安全性フィルターエラー"""
    
    def __init__(self, message: str, safety_ratings: List[Dict[str, Any]]):
        super().__init__(
            message,
            error_code="CONTENT_BLOCKED",
            retry_recommended=False,
            context={"safety_ratings": safety_ratings}
        )
        self.safety_ratings = safety_ratings


class GeminiLLMClient:
    """Gemini LLM API クライアント"""
    
    def __init__(
        self,
        api_key: str,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.api_key = api_key
        self.retry_config = retry_config
        self.rate_limit_config = rate_limit_config
        self.logger = logger or logging.getLogger(__name__)
        
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
        
        self.logger.info("Gemini LLM クライアントを初期化しました")
    
    def _parse_response(self, response, model: str) -> GeminiResponse:
        """レスポンス解析"""
        try:
            # 候補者があるかチェック
            if not response.candidates:
                raise GeminiAPIError(
                    "No candidates in response",
                    error_code="NO_CANDIDATES",
                    model=model
                )
            
            candidate = response.candidates[0]
            
            # 終了理由をチェック
            finish_reason = candidate.finish_reason if hasattr(candidate, 'finish_reason') else "STOP"
            
            if finish_reason in ["SAFETY", "RECITATION"]:
                safety_ratings = []
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    safety_ratings = [
                        {
                            "category": rating.category if hasattr(rating, 'category') else "UNKNOWN",
                            "probability": rating.probability if hasattr(rating, 'probability') else "UNKNOWN"
                        }
                        for rating in candidate.safety_ratings
                    ]
                raise ContentBlockedError(
                    f"Content blocked due to safety filters: {finish_reason}",
                    safety_ratings
                )
            
            # テキスト抽出
            text = response.text if hasattr(response, 'text') else ""
            
            # 使用メタデータ
            usage_metadata = {}
            if hasattr(response, 'usage_metadata'):
                usage_metadata = {
                    "candidatesTokenCount": response.usage_metadata.candidates_token_count if hasattr(response.usage_metadata, 'candidates_token_count') else 0,
                    "promptTokenCount": response.usage_metadata.prompt_token_count if hasattr(response.usage_metadata, 'prompt_token_count') else 0
                }
            
            # 安全性評価
            safety_ratings = []
            if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                safety_ratings = [
                    {
                        "category": rating.category if hasattr(rating, 'category') else "UNKNOWN",
                        "probability": rating.probability if hasattr(rating, 'probability') else "UNKNOWN"
                    }
                    for rating in candidate.safety_ratings
                ]
            
            return GeminiResponse(
                text=text,
                model=model,
                finish_reason=finish_reason,
                safety_ratings=safety_ratings,
                usage_metadata=usage_metadata,
                candidates=[{"content": {"parts": [{"text": text}]}}]
            )
            
        except Exception as e:
            if isinstance(e, (GeminiAPIError, ContentBlockedError)):
                raise
            
            self.logger.error(f"レスポンス解析エラー: {e}")
            raise GeminiAPIError(
                f"Failed to parse response: {e}",
                error_code="RESPONSE_PARSE_ERROR",
                model=model
            )
    
    async def generate_text(self, gemini_request: GeminiRequest) -> GeminiResponse:
        """テキスト生成"""
        try:
            # 設定作成
            config = None
            if any([
                gemini_request.max_output_tokens != 1024,
                gemini_request.temperature != 0.7,
                gemini_request.top_p != 0.9,
                gemini_request.top_k != 40,
                gemini_request.output_format != OutputFormat.TEXT
            ]):
                config_params = {}
                
                if gemini_request.max_output_tokens != 1024:
                    config_params["max_output_tokens"] = gemini_request.max_output_tokens
                if gemini_request.temperature != 0.7:
                    config_params["temperature"] = gemini_request.temperature
                if gemini_request.top_p != 0.9:
                    config_params["top_p"] = gemini_request.top_p
                if gemini_request.top_k != 40:
                    config_params["top_k"] = gemini_request.top_k
                
                # JSON出力の場合
                if gemini_request.output_format == OutputFormat.JSON:
                    config_params["response_mime_type"] = "application/json"
                elif gemini_request.output_format == OutputFormat.STRUCTURED:
                    config_params["response_mime_type"] = "application/json"
                    if gemini_request.structured_schema:
                        config_params["response_schema"] = gemini_request.structured_schema
                
                config = types.GenerateContentConfig(**config_params)
            
            # システム命令の処理
            contents = gemini_request.prompt
            if gemini_request.system_instruction:
                # システム命令がある場合は別途設定（APIに依存）
                self.logger.warning("システム命令は現在サポートされていません")
            
            # APIコール
            response = self._client.models.generate_content(
                model=gemini_request.model.value,
                contents=contents,
                config=config
            )
            
            return self._parse_response(response, gemini_request.model.value)
            
        except Exception as e:
            if isinstance(e, (GeminiAPIError, ContentBlockedError)):
                raise
            
            self.logger.error(f"テキスト生成エラー: {e}")
            raise GeminiAPIError(
                f"Failed to generate text: {e}",
                model=gemini_request.model.value
            )
    
    async def generate_structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: ModelType = ModelType.GEMINI_2_0_FLASH,
        system_instruction: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """構造化出力生成"""
        gemini_request = GeminiRequest(
            prompt=prompt,
            model=model,
            output_format=OutputFormat.STRUCTURED,
            structured_schema=schema,
            system_instruction=system_instruction,
            **kwargs
        )
        
        response = await self.generate_text(gemini_request)
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            raise GeminiAPIError(
                f"Failed to parse structured output as JSON: {e}",
                error_code="JSON_PARSE_ERROR",
                model=model.value,
                retry_recommended=True
            )
    
    async def count_tokens(self, text: str, model: ModelType = ModelType.GEMINI_2_0_FLASH) -> int:
        """トークン数カウント"""
        try:
            # 簡易的なトークン数推定（正確なAPIが利用可能になるまで）
            # 1トークン ≈ 4文字として概算
            return len(text) // 4
        except Exception as e:
            self.logger.warning(f"トークン数カウントに失敗: {e}")
            return 0
    
    async def close(self):
        """リソースクリーンアップ"""
        try:
            if hasattr(self._client, '_api_client') and hasattr(self._client._api_client, '_httpx_client'):
                self._client._api_client._httpx_client.close()
        except Exception as e:
            self.logger.warning(f"クリーンアップ時にエラー: {e}")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 