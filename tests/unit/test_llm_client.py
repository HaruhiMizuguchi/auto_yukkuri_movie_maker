"""
Gemini LLM クライアントのテスト - 新しい google.genai ライブラリ対応版
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any

from src.api.llm_client import (
    GeminiLLMClient,
    GeminiRequest,
    GeminiResponse,
    GeminiAPIError,
    ContentBlockedError,
    ModelType,
    OutputFormat
)


class TestGeminiRequest:
    """GeminiRequest のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        request = GeminiRequest(prompt="Test prompt")
        
        assert request.prompt == "Test prompt"
        assert request.model == ModelType.GEMINI_2_0_FLASH  # 新しいデフォルト
        assert request.max_output_tokens == 1024
        assert request.temperature == 0.7
        assert request.top_p == 0.9
        assert request.top_k == 40
        assert request.output_format == OutputFormat.TEXT
        assert request.structured_schema is None
        assert request.system_instruction is None
        assert request.safety_settings is None
    
    def test_custom_values(self):
        """カスタム値設定テスト"""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        safety_settings = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}]
        
        request = GeminiRequest(
            prompt="Custom prompt",
            model=ModelType.GEMINI_1_5_PRO,
            max_output_tokens=2048,
            temperature=0.5,
            top_p=0.8,
            top_k=20,
            output_format=OutputFormat.STRUCTURED,
            structured_schema=schema,
            system_instruction="You are a helpful assistant",
            safety_settings=safety_settings
        )
        
        assert request.prompt == "Custom prompt"
        assert request.model == ModelType.GEMINI_1_5_PRO
        assert request.max_output_tokens == 2048
        assert request.temperature == 0.5
        assert request.top_p == 0.8
        assert request.top_k == 20
        assert request.output_format == OutputFormat.STRUCTURED
        assert request.structured_schema == schema
        assert request.system_instruction == "You are a helpful assistant"
        assert request.safety_settings == safety_settings


class TestGeminiResponse:
    """GeminiResponse のテスト"""
    
    def test_normal_response(self):
        """通常レスポンステスト"""
        response = GeminiResponse(
            text="Generated text",
            model="gemini-2.0-flash",
            finish_reason="STOP",
            safety_ratings=[],
            usage_metadata={"candidatesTokenCount": 50, "promptTokenCount": 10},
            candidates=[]
        )
        
        assert response.text == "Generated text"
        assert response.model == "gemini-2.0-flash"
        assert response.finish_reason == "STOP"
        assert response.is_blocked is False
        assert response.token_count == 50
        assert response.prompt_token_count == 10
    
    def test_blocked_response(self):
        """ブロックされたレスポンステスト"""
        response = GeminiResponse(
            text="",
            model="gemini-2.0-flash",
            finish_reason="SAFETY",
            safety_ratings=[{"category": "HARM_CATEGORY_HARASSMENT", "probability": "HIGH"}],
            usage_metadata={},
            candidates=[]
        )
        
        assert response.is_blocked is True
        assert response.finish_reason == "SAFETY"
        assert response.token_count == 0


class TestGeminiAPIError:
    """GeminiAPIError のテスト"""
    
    def test_basic_error(self):
        """基本エラーテスト"""
        error = GeminiAPIError("Test error", api_error_code="400", model="gemini-2.0-flash")
        
        assert error.message == "Test error"
        assert error.api_error_code == "400"
        assert error.model == "gemini-2.0-flash"
        assert error.context["api_error_code"] == "400"
        assert error.context["model"] == "gemini-2.0-flash"
    
    def test_content_blocked_error(self):
        """コンテンツブロックエラーテスト"""
        safety_ratings = [{"category": "HARM_CATEGORY_HARASSMENT", "probability": "HIGH"}]
        error = ContentBlockedError("Content blocked", safety_ratings)
        
        assert error.message == "Content blocked"
        assert error.error_code == "CONTENT_BLOCKED"
        assert error.retry_recommended is False
        assert error.safety_ratings == safety_ratings


class TestGeminiLLMClient:
    """GeminiLLMClient のテスト - 新しい google.genai 実装"""
    
    def test_initialization(self):
        """初期化テスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class, \
             patch('src.api.llm_client.httpx.Client') as mock_httpx_class:
            
            mock_client = Mock()
            mock_client._api_client._httpx_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_httpx = Mock()
            mock_httpx_class.return_value = mock_httpx
            
            client = GeminiLLMClient(api_key="test-key")
            
            # APIキーの設定確認
            assert client.api_key == "test-key"
            
            # Gemini クライアントの初期化確認
            mock_client_class.assert_called_once_with(api_key="test-key")
            
            # httpx クライアントの設定確認
            mock_httpx_class.assert_called_once_with(timeout=60.0, trust_env=False)
    
    def test_parse_response_success(self):
        """正常レスポンス解析テスト"""
        with patch('src.api.llm_client.genai.Client'):
            client = GeminiLLMClient(api_key="test-key")
            
            # モックレスポンスオブジェクト作成
            mock_response = Mock()
            mock_response.text = "Generated response text"
            mock_response.candidates = [Mock()]
            
            # 候補者の設定
            candidate = mock_response.candidates[0]
            candidate.finish_reason = "STOP"
            candidate.safety_ratings = []
            
            # 使用メタデータの設定
            mock_response.usage_metadata = Mock()
            mock_response.usage_metadata.candidates_token_count = 25
            mock_response.usage_metadata.prompt_token_count = 10
            
            result = client._parse_response(mock_response, "gemini-2.0-flash")
            
            assert result.text == "Generated response text"
            assert result.model == "gemini-2.0-flash"
            assert result.finish_reason == "STOP"
            assert result.token_count == 25
            assert result.prompt_token_count == 10
            assert result.is_blocked is False
    
    def test_parse_response_no_candidates(self):
        """候補なしレスポンス解析テスト"""
        with patch('src.api.llm_client.genai.Client'):
            client = GeminiLLMClient(api_key="test-key")
            
            mock_response = Mock()
            mock_response.candidates = []
            
            with pytest.raises(GeminiAPIError) as exc_info:
                client._parse_response(mock_response, "gemini-2.0-flash")
            
            assert exc_info.value.error_code == "NO_CANDIDATES"
    
    def test_parse_response_content_blocked(self):
        """コンテンツブロックレスポンス解析テスト"""
        with patch('src.api.llm_client.genai.Client'):
            client = GeminiLLMClient(api_key="test-key")
            
            mock_response = Mock()
            mock_response.text = ""
            mock_response.candidates = [Mock()]
            
            candidate = mock_response.candidates[0]
            candidate.finish_reason = "SAFETY"
            
            # 安全性評価の設定
            safety_rating = Mock()
            safety_rating.category = "HARM_CATEGORY_HARASSMENT"
            safety_rating.probability = "HIGH"
            candidate.safety_ratings = [safety_rating]
            
            with pytest.raises(ContentBlockedError) as exc_info:
                client._parse_response(mock_response, "gemini-2.0-flash")
            
            assert "safety filters" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_generate_text_success(self):
        """テキスト生成成功テスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class:
            # モッククライアントの設定
            mock_client = Mock()
            mock_client._api_client._httpx_client = Mock()
            mock_client_class.return_value = mock_client
            
            # モックレスポンスの設定
            mock_response = Mock()
            mock_response.text = "Generated text"
            mock_response.candidates = [Mock()]
            mock_response.candidates[0].finish_reason = "STOP"
            mock_response.candidates[0].safety_ratings = []
            mock_response.usage_metadata = Mock()
            mock_response.usage_metadata.candidates_token_count = 15
            mock_response.usage_metadata.prompt_token_count = 5
            
            mock_client.models.generate_content.return_value = mock_response
            
            # クライアント初期化
            with patch('src.api.llm_client.httpx.Client'):
                client = GeminiLLMClient(api_key="test-key")
            
            # テキスト生成
            request = GeminiRequest(prompt="Test prompt")
            result = await client.generate_text(request)
            
            # 結果検証
            assert result.text == "Generated text"
            assert result.finish_reason == "STOP"
            assert result.token_count == 15
            assert result.prompt_token_count == 5
            
            # APIコール確認
            mock_client.models.generate_content.assert_called_once()
            call_args = mock_client.models.generate_content.call_args
            assert call_args[1]['model'] == "gemini-2.0-flash"
            assert call_args[1]['contents'] == "Test prompt"
    
    @pytest.mark.asyncio
    async def test_generate_text_with_config(self):
        """設定付きテキスト生成テスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class, \
             patch('src.api.llm_client.types') as mock_types:
            
            mock_client = Mock()
            mock_client._api_client._httpx_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_response = Mock()
            mock_response.text = "Generated text"
            mock_response.candidates = [Mock()]
            mock_response.candidates[0].finish_reason = "STOP"
            mock_response.candidates[0].safety_ratings = []
            mock_response.usage_metadata = Mock()
            mock_response.usage_metadata.candidates_token_count = 20
            mock_response.usage_metadata.prompt_token_count = 8
            
            mock_client.models.generate_content.return_value = mock_response
            mock_config = Mock()
            mock_types.GenerateContentConfig.return_value = mock_config
            
            with patch('src.api.llm_client.httpx.Client'):
                client = GeminiLLMClient(api_key="test-key")
            
            # カスタム設定でテキスト生成
            request = GeminiRequest(
                prompt="Test prompt",
                temperature=0.5,
                max_output_tokens=2048,
                output_format=OutputFormat.JSON
            )
            result = await client.generate_text(request)
            
            # 設定が作成されたことを確認
            mock_types.GenerateContentConfig.assert_called_once()
            config_kwargs = mock_types.GenerateContentConfig.call_args[1]
            assert config_kwargs['temperature'] == 0.5
            assert config_kwargs['max_output_tokens'] == 2048
            assert config_kwargs['response_mime_type'] == "application/json"
            
            # 設定がAPIコールに渡されたことを確認
            call_args = mock_client.models.generate_content.call_args
            assert call_args[1]['config'] == mock_config
    
    @pytest.mark.asyncio
    async def test_generate_structured_output_success(self):
        """構造化出力生成成功テスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client._api_client._httpx_client = Mock()
            mock_client_class.return_value = mock_client
            
            # JSONレスポンスの設定
            json_output = {"name": "John", "age": 30}
            mock_response = Mock()
            mock_response.text = json.dumps(json_output)
            mock_response.candidates = [Mock()]
            mock_response.candidates[0].finish_reason = "STOP"
            mock_response.candidates[0].safety_ratings = []
            mock_response.usage_metadata = Mock()
            mock_response.usage_metadata.candidates_token_count = 12
            mock_response.usage_metadata.prompt_token_count = 6
            
            mock_client.models.generate_content.return_value = mock_response
            
            with patch('src.api.llm_client.httpx.Client'):
                client = GeminiLLMClient(api_key="test-key")
            
            schema = {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}
            result = await client.generate_structured_output("Generate user data", schema)
            
            assert result == json_output
    
    @pytest.mark.asyncio
    async def test_generate_structured_output_json_error(self):
        """構造化出力JSON解析エラーテスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client._api_client._httpx_client = Mock()
            mock_client_class.return_value = mock_client
            
            # 不正なJSONレスポンス
            mock_response = Mock()
            mock_response.text = "Invalid JSON"
            mock_response.candidates = [Mock()]
            mock_response.candidates[0].finish_reason = "STOP"
            mock_response.candidates[0].safety_ratings = []
            mock_response.usage_metadata = Mock()
            mock_response.usage_metadata.candidates_token_count = 8
            mock_response.usage_metadata.prompt_token_count = 4
            
            mock_client.models.generate_content.return_value = mock_response
            
            with patch('src.api.llm_client.httpx.Client'):
                client = GeminiLLMClient(api_key="test-key")
            
            schema = {"type": "object"}
            with pytest.raises(GeminiAPIError) as exc_info:
                await client.generate_structured_output("Generate data", schema)
            
            assert exc_info.value.error_code == "JSON_PARSE_ERROR"
    
    @pytest.mark.asyncio
    async def test_count_tokens(self):
        """トークン数カウントテスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client._api_client._httpx_client = Mock()
            mock_client_class.return_value = mock_client
            
            with patch('src.api.llm_client.httpx.Client'):
                client = GeminiLLMClient(api_key="test-key")
            
            # 簡易的なトークン数推定のテスト
            text = "This is a test text for token counting"
            token_count = await client.count_tokens(text)
            
            # 概算値の確認（1トークン ≈ 4文字）
            expected = len(text) // 4
            assert token_count == expected
    
    @pytest.mark.asyncio
    async def test_close(self):
        """リソースクリーンアップテスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_httpx_client = Mock()
            mock_client._api_client._httpx_client = mock_httpx_client
            mock_client_class.return_value = mock_client
            
            with patch('src.api.llm_client.httpx.Client'):
                client = GeminiLLMClient(api_key="test-key")
            
            await client.close()
            
            # httpx クライアントのcloseが呼ばれたことを確認
            mock_httpx_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """コンテキストマネージャーテスト"""
        with patch('src.api.llm_client.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_httpx_client = Mock()
            mock_client._api_client._httpx_client = mock_httpx_client
            mock_client_class.return_value = mock_client
            
            with patch('src.api.llm_client.httpx.Client'):
                async with GeminiLLMClient(api_key="test-key") as client:
                    assert isinstance(client, GeminiLLMClient)
            
            # 自動的にcloseが呼ばれることを確認
            mock_httpx_client.close.assert_called_once()


class TestPerformance:
    """パフォーマンステスト"""
    
    def test_response_parsing_performance(self):
        """レスポンス解析パフォーマンステスト"""
        with patch('src.api.llm_client.genai.Client'):
            client = GeminiLLMClient(api_key="test-key")
            
            # 大きなレスポンスデータのモック
            mock_response = Mock()
            mock_response.text = "Generated text " * 1000
            mock_response.candidates = [Mock()]
            mock_response.candidates[0].finish_reason = "STOP"
            mock_response.candidates[0].safety_ratings = []
            mock_response.usage_metadata = Mock()
            mock_response.usage_metadata.candidates_token_count = 1000
            mock_response.usage_metadata.prompt_token_count = 100
            
            import time
            start_time = time.time()
            
            # 100回の解析実行
            for _ in range(100):
                client._parse_response(mock_response, "gemini-2.0-flash")
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # パフォーマンス検証（100回で1秒以内）
            assert elapsed < 1.0, f"レスポンス解析が遅すぎます: {elapsed:.3f}秒"
            print(f"レスポンス解析パフォーマンス: 100回で{elapsed:.3f}秒") 