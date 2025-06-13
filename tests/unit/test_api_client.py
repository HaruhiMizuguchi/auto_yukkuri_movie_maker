"""
API クライアント基盤のテスト
"""

import pytest
import asyncio
import time
from typing import Dict, Any
from unittest.mock import Mock, patch

from src.core.api_client import (
    APIRequest,
    APIResponse,
    APIClient,
    BaseAPIClient,
    MockAPIClient,
    APIClientError,
    RateLimitError,
    AuthenticationError,
    NetworkError,
    RetryConfig,
    RateLimitConfig
)
from src.core.workflow_exceptions import ErrorCategory, ErrorSeverity


class TestAPIRequest:
    """APIRequest のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        request = APIRequest(endpoint="/test")
        
        assert request.endpoint == "/test"
        assert request.method == "POST"
        assert request.headers is None
        assert request.params is None
        assert request.data is None
        assert request.files is None
        assert request.timeout == 30
    
    def test_custom_values(self):
        """カスタム値設定テスト"""
        headers = {"Authorization": "Bearer token"}
        params = {"param1": "value1"}
        data = {"field": "value"}
        
        request = APIRequest(
            endpoint="/custom",
            method="GET",
            headers=headers,
            params=params,
            data=data,
            timeout=60
        )
        
        assert request.endpoint == "/custom"
        assert request.method == "GET"
        assert request.headers == headers
        assert request.params == params
        assert request.data == data
        assert request.timeout == 60


class TestAPIResponse:
    """APIResponse のテスト"""
    
    def test_success_response(self):
        """成功レスポンステスト"""
        response = APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            data={"result": "success"}
        )
        
        assert response.is_success is True
        assert response.is_rate_limited is False
    
    def test_client_error_response(self):
        """クライアントエラーレスポンステスト"""
        response = APIResponse(
            status_code=400,
            headers={},
            data={"error": "Bad Request"}
        )
        
        assert response.is_success is False
        assert response.is_rate_limited is False
    
    def test_rate_limit_response(self):
        """レート制限レスポンステスト"""
        response = APIResponse(
            status_code=429,
            headers={"retry-after": "60"},
            data={"error": "Rate limit exceeded"}
        )
        
        assert response.is_success is False
        assert response.is_rate_limited is True
    
    def test_server_error_response(self):
        """サーバーエラーレスポンステスト"""
        response = APIResponse(
            status_code=500,
            headers={},
            data={"error": "Internal Server Error"}
        )
        
        assert response.is_success is False
        assert response.is_rate_limited is False


class TestAPIClientErrors:
    """API クライアントエラーのテスト"""
    
    def test_api_client_error(self):
        """APIClientError テスト"""
        error = APIClientError("Test error")
        
        assert error.message == "Test error"
        assert error.category == ErrorCategory.EXECUTION
        assert error.severity == ErrorSeverity.ERROR
        assert error.retry_recommended is True
    
    def test_rate_limit_error(self):
        """RateLimitError テスト"""
        error = RateLimitError("Rate limited", retry_after=60)
        
        assert error.message == "Rate limited"
        assert error.category == ErrorCategory.TIMEOUT
        assert error.severity == ErrorSeverity.WARNING
        assert error.retry_recommended is True
        assert error.retry_after == 60
    
    def test_authentication_error(self):
        """AuthenticationError テスト"""
        error = AuthenticationError("Invalid API key")
        
        assert error.message == "Invalid API key"
        assert error.category == ErrorCategory.PERMISSION
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.retry_recommended is False
    
    def test_network_error(self):
        """NetworkError テスト"""
        error = NetworkError("Connection timeout")
        
        assert error.message == "Connection timeout"
        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.ERROR
        assert error.retry_recommended is True


class ConcreteAPIClient(BaseAPIClient):
    """テスト用具象クラス"""
    
    def __init__(self, mock_response: APIResponse = None):
        super().__init__("https://api.test.com", "test-key")
        self.mock_response = mock_response or APIResponse(200, {}, {"status": "ok"})
        self.send_request_called = 0
        
    async def send_request(self, request: APIRequest) -> APIResponse:
        """モック実装"""
        self.send_request_called += 1
        return self.mock_response


class TestBaseAPIClient:
    """BaseAPIClient のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        config = RetryConfig(max_retries=5)
        rate_config = RateLimitConfig(requests_per_minute=100)
        
        client = ConcreteAPIClient()
        client.retry_config = config
        client.rate_limit_config = rate_config
        
        assert client.base_url == "https://api.test.com"
        assert client.api_key == "test-key"
        assert client.retry_config.max_retries == 5
        assert client.rate_limit_config.requests_per_minute == 100
    
    def test_validate_config_success(self):
        """設定検証成功テスト"""
        client = ConcreteAPIClient()
        assert client.validate_config() is True
    
    def test_validate_config_no_base_url(self):
        """base_url なし設定検証テスト"""
        client = ConcreteAPIClient()
        client.base_url = ""
        
        with pytest.raises(ValueError, match="base_url is required"):
            client.validate_config()
    
    def test_rate_limit_status_empty(self):
        """レート制限状況（空）テスト"""
        client = ConcreteAPIClient()
        status = client.get_rate_limit_status()
        
        assert status["requests_in_minute"] == 0
        assert status["requests_in_hour"] == 0
        assert status["minute_limit"] == 60
        assert status["hour_limit"] == 1000
        assert status["can_make_request"] is True
    
    def test_rate_limit_tracking(self):
        """レート制限追跡テスト"""
        client = ConcreteAPIClient()
        
        # リクエスト記録
        for _ in range(5):
            client._record_request()
        
        status = client.get_rate_limit_status()
        assert status["requests_in_minute"] == 5
        assert status["requests_in_hour"] == 5
    
    def test_can_make_request_under_limit(self):
        """リクエスト可能（制限内）テスト"""
        client = ConcreteAPIClient()
        client.rate_limit_config.requests_per_minute = 10
        
        # 5リクエスト記録
        for _ in range(5):
            client._record_request()
        
        assert client._can_make_request() is True
    
    def test_can_make_request_over_limit(self):
        """リクエスト不可（制限超過）テスト"""
        client = ConcreteAPIClient()
        client.rate_limit_config.requests_per_minute = 5
        
        # 6リクエスト記録
        for _ in range(6):
            client._record_request()
        
        assert client._can_make_request() is False
    
    def test_retry_delay_calculation(self):
        """リトライ遅延計算テスト"""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter=False
        )
        client = ConcreteAPIClient()
        client.retry_config = config
        
        assert client._calculate_retry_delay(0) == 1.0
        assert client._calculate_retry_delay(1) == 2.0
        assert client._calculate_retry_delay(2) == 4.0
        assert client._calculate_retry_delay(10) == 10.0  # max_delay適用
    
    def test_retry_delay_with_jitter(self):
        """ジッター付きリトライ遅延テスト"""
        config = RetryConfig(base_delay=2.0, jitter=True)
        client = ConcreteAPIClient()
        client.retry_config = config
        
        delay = client._calculate_retry_delay(0)
        assert 1.0 <= delay <= 2.0  # jitterで0.5-1.0倍
    
    @pytest.mark.asyncio
    async def test_send_request_with_retry_success(self):
        """リトライ付きリクエスト成功テスト"""
        response = APIResponse(200, {}, {"data": "success"})
        client = ConcreteAPIClient(response)
        
        request = APIRequest("/test")
        result = await client.send_request_with_retry(request)
        
        assert result == response
        assert client.send_request_called == 1
    
    @pytest.mark.asyncio
    async def test_send_request_with_retry_authentication_error(self):
        """認証エラー（リトライしない）テスト"""
        response = APIResponse(401, {}, {"error": "Unauthorized"})
        client = ConcreteAPIClient(response)
        
        request = APIRequest("/test")
        
        with pytest.raises(AuthenticationError):
            await client.send_request_with_retry(request)
        
        assert client.send_request_called == 1  # リトライしない
    
    @pytest.mark.asyncio  
    async def test_send_request_with_retry_rate_limit_with_header(self):
        """レート制限（retry-afterヘッダー）テスト"""
        response = APIResponse(429, {"retry-after": "1"}, {"error": "Rate limited"})
        success_response = APIResponse(200, {}, {"data": "success"})
        
        client = ConcreteAPIClient(response)
        
        # 2回目の呼び出しで成功レスポンスを返すように設定
        async def mock_send_request(request):
            if client.send_request_called == 0:
                client.send_request_called += 1
                return response
            else:
                return success_response
        
        client.send_request = mock_send_request
        
        request = APIRequest("/test")
        
        # sleep をモック
        with patch('time.sleep'):
            result = await client.send_request_with_retry(request)
        
        assert result == success_response
    
    @pytest.mark.asyncio
    async def test_send_request_with_retry_network_error_retries(self):
        """ネットワークエラー（リトライする）テスト"""
        client = ConcreteAPIClient()
        client.retry_config.max_retries = 2
        
        error_count = 0
        
        async def mock_send_request(request):
            nonlocal error_count
            error_count += 1
            if error_count <= 2:
                raise NetworkError("Connection failed")
            return APIResponse(200, {}, {"data": "success"})
        
        client.send_request = mock_send_request
        
        request = APIRequest("/test")
        result = await client.send_request_with_retry(request)
        
        assert result.data == {"data": "success"}
        assert error_count == 3  # 最初の失敗 + 2回のリトライ + 成功


class TestMockAPIClient:
    """MockAPIClient のテスト"""
    
    @pytest.mark.asyncio
    async def test_mock_response(self):
        """モックレスポンステスト"""
        response = APIResponse(200, {}, {"mock": "data"})
        client = MockAPIClient({"/test": response})
        
        request = APIRequest("/test")
        result = await client.send_request(request)
        
        assert result == response
        assert len(client.request_history) == 1
        assert client.request_history[0] == request
    
    @pytest.mark.asyncio
    async def test_default_response(self):
        """デフォルトレスポンステスト"""
        client = MockAPIClient()
        
        request = APIRequest("/unknown")
        result = await client.send_request(request)
        
        assert result.status_code == 200
        assert result.data["status"] == "success"
        assert result.data["endpoint"] == "/unknown"
    
    def test_add_mock_response(self):
        """モックレスポンス追加テスト"""
        client = MockAPIClient()
        response = APIResponse(201, {}, {"created": True})
        
        client.add_mock_response("/create", response)
        
        assert "/create" in client.mock_responses
        assert client.mock_responses["/create"] == response


# パフォーマンステスト
class TestPerformance:
    """パフォーマンステスト"""
    
    def test_rate_limit_tracking_performance(self):
        """レート制限追跡パフォーマンステスト"""
        client = ConcreteAPIClient()
        
        # 大量のリクエストを記録
        start_time = time.time()
        for _ in range(1000):
            client._record_request()
        
        # ステータス取得
        status = client.get_rate_limit_status()
        end_time = time.time()
        
        # 1秒以内で完了することを確認
        assert end_time - start_time < 1.0
        assert status["requests_in_minute"] <= 1000
        assert status["requests_in_hour"] == 1000
    
    def test_old_timestamp_cleanup(self):
        """古いタイムスタンプ削除テスト"""
        client = ConcreteAPIClient()
        
        # 古いタイムスタンプを追加
        old_time = time.time() - 7200  # 2時間前
        client._request_timestamps = [old_time] * 100
        
        # 新しいリクエストを記録
        client._record_request()
        
        # 古いタイムスタンプが削除されることを確認
        assert len(client._request_timestamps) == 1
        assert client._request_timestamps[0] > old_time 