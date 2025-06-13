"""
API クライアント基盤 - 外部API連携の抽象化層

すべての外部APIクライアントが実装すべき共通インターフェースと
共通機能（リトライ、レート制限、エラーハンドリング）を提供
"""

import time
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, List, Protocol, Callable
from dataclasses import dataclass
from enum import Enum
import logging

from .workflow_exceptions import WorkflowEngineError, ErrorCategory, ErrorSeverity


class APIClientError(WorkflowEngineError):
    """API クライアント関連エラーの基底クラス"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "API_CLIENT_ERROR",
        category: ErrorCategory = ErrorCategory.EXECUTION,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        retry_recommended: bool = True,
        **kwargs
    ):
        kwargs.setdefault('recoverable', retry_recommended)
        super().__init__(message, error_code, category, severity, **kwargs)
        self.retry_recommended = retry_recommended


class RateLimitError(APIClientError):
    """レート制限エラー"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(
            message,
            error_code="RATE_LIMIT_EXCEEDED",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.WARNING,
            retry_recommended=True,
            context={"retry_after": retry_after}
        )
        self.retry_after = retry_after


class AuthenticationError(APIClientError):
    """認証エラー"""
    
    def __init__(self, message: str):
        super().__init__(
            message,
            error_code="AUTHENTICATION_FAILED",
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.CRITICAL,
            retry_recommended=False
        )


class NetworkError(APIClientError):
    """ネットワークエラー"""
    
    def __init__(self, message: str):
        super().__init__(
            message,
            error_code="NETWORK_ERROR",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            retry_recommended=True
        )


@dataclass
class APIRequest:
    """API リクエストデータ"""
    endpoint: str
    method: str = "POST"
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    files: Optional[Dict[str, Any]] = None
    timeout: int = 30


@dataclass  
class APIResponse:
    """API レスポンスデータ"""
    status_code: int
    headers: Dict[str, str]
    data: Any
    raw_content: Optional[bytes] = None
    
    @property
    def is_success(self) -> bool:
        """成功レスポンスかどうか"""
        return 200 <= self.status_code < 300
    
    @property
    def is_rate_limited(self) -> bool:
        """レート制限レスポンスかどうか"""
        return self.status_code == 429


class APIClient(Protocol):
    """API クライアントの抽象インターフェース"""
    
    @abstractmethod
    async def send_request(self, request: APIRequest) -> APIResponse:
        """リクエスト送信"""
        ...
    
    @abstractmethod
    def validate_config(self) -> bool:
        """設定検証"""
        ...
    
    @abstractmethod
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """レート制限状況取得"""
        ...


@dataclass
class RetryConfig:
    """リトライ設定"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class RateLimitConfig:
    """レート制限設定"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10


class BaseAPIClient(ABC):
    """API クライアントの基底クラス"""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.retry_config = retry_config or RetryConfig()
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # レート制限追跡
        self._request_timestamps: List[float] = []
        self._last_request_time: float = 0.0
        
    def validate_config(self) -> bool:
        """基本設定検証"""
        if not self.base_url:
            raise ValueError("base_url is required")
        if self.api_key is None:
            self.logger.warning("API key not provided")
        return True
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """レート制限状況取得"""
        current_time = time.time()
        
        # 過去1分間のリクエスト数
        minute_ago = current_time - 60
        requests_in_minute = len([t for t in self._request_timestamps if t > minute_ago])
        
        # 過去1時間のリクエスト数
        hour_ago = current_time - 3600
        requests_in_hour = len([t for t in self._request_timestamps if t > hour_ago])
        
        return {
            "requests_in_minute": requests_in_minute,
            "requests_in_hour": requests_in_hour,
            "minute_limit": self.rate_limit_config.requests_per_minute,
            "hour_limit": self.rate_limit_config.requests_per_hour,
            "time_until_minute_reset": max(0, 60 - (current_time - self._last_request_time)),
            "can_make_request": self._can_make_request()
        }
    
    def _can_make_request(self) -> bool:
        """リクエスト可能かチェック"""
        current_time = time.time()
        
        # 過去1分間のリクエスト数
        minute_ago = current_time - 60
        requests_in_minute = len([t for t in self._request_timestamps if t > minute_ago])
        
        # 過去1時間のリクエスト数
        hour_ago = current_time - 3600
        requests_in_hour = len([t for t in self._request_timestamps if t > hour_ago])
        
        return (
            requests_in_minute < self.rate_limit_config.requests_per_minute and
            requests_in_hour < self.rate_limit_config.requests_per_hour
        )
    
    def _wait_for_rate_limit(self) -> None:
        """レート制限待機"""
        if not self._can_make_request():
            status = self.get_rate_limit_status()
            wait_time = status["time_until_minute_reset"] + 1.0
            self.logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
    
    def _record_request(self) -> None:
        """リクエスト記録"""
        current_time = time.time()
        self._request_timestamps.append(current_time)
        self._last_request_time = current_time
        
        # 古いタイムスタンプを削除（1時間以上前）
        hour_ago = current_time - 3600
        self._request_timestamps = [t for t in self._request_timestamps if t > hour_ago]
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """リトライ遅延計算"""
        delay = self.retry_config.base_delay * (
            self.retry_config.exponential_base ** attempt
        )
        delay = min(delay, self.retry_config.max_delay)
        
        if self.retry_config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    async def send_request_with_retry(self, request: APIRequest) -> APIResponse:
        """リトライ機能付きリクエスト送信"""
        last_exception = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # レート制限チェック
                self._wait_for_rate_limit()
                
                # リクエスト実行
                response = await self.send_request(request)
                
                # リクエスト記録
                self._record_request()
                
                # レート制限レスポンスの処理
                if response.is_rate_limited:
                    retry_after = response.headers.get('retry-after')
                    if retry_after:
                        wait_time = int(retry_after)
                        self.logger.warning(f"Rate limited, waiting {wait_time} seconds")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RateLimitError("Rate limit exceeded")
                
                # 成功レスポンス
                if response.is_success:
                    return response
                
                # エラーレスポンス
                error_msg = f"HTTP {response.status_code}: {response.data}"
                if response.status_code >= 500:
                    # サーバーエラーはリトライ
                    raise NetworkError(error_msg)
                elif response.status_code == 401:
                    # 認証エラーはリトライしない
                    raise AuthenticationError(error_msg)
                else:
                    # その他のクライアントエラー
                    raise APIClientError(error_msg, retry_recommended=False)
                
            except (NetworkError, RateLimitError) as e:
                last_exception = e
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self.logger.warning(
                        f"Request failed (attempt {attempt + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"Request failed after {attempt + 1} attempts: {e}")
                    break
            except (AuthenticationError, APIClientError) as e:
                self.logger.error(f"Request failed: {e}")
                raise
        
        # すべてのリトライが失敗
        if last_exception:
            raise last_exception
        else:
            raise APIClientError("Request failed after all retries")
    
    @abstractmethod
    async def send_request(self, request: APIRequest) -> APIResponse:
        """具象クラスで実装するリクエスト送信メソッド"""
        pass


class MockAPIClient(BaseAPIClient):
    """テスト用モックAPIクライアント"""
    
    def __init__(self, mock_responses: Optional[Dict[str, APIResponse]] = None):
        super().__init__("http://mock-api.test")
        self.mock_responses = mock_responses or {}
        self.request_history: List[APIRequest] = []
    
    def add_mock_response(self, endpoint: str, response: APIResponse) -> None:
        """モックレスポンス追加"""
        self.mock_responses[endpoint] = response
    
    async def send_request(self, request: APIRequest) -> APIResponse:
        """モックリクエスト送信"""
        self.request_history.append(request)
        
        if request.endpoint in self.mock_responses:
            return self.mock_responses[request.endpoint]
        
        # デフォルトは成功レスポンス
        return APIResponse(
            status_code=200,
            headers={},
            data={"status": "success", "endpoint": request.endpoint}
        ) 