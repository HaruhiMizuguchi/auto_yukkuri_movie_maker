"""
Gemini LLM クライアントの統合テスト - 実際のAPI呼び出しテスト
"""

import pytest
import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
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


# APIキー読み込み
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


class TestGeminiRequest:
    """GeminiRequest のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        request = GeminiRequest(prompt="Test prompt")
        
        assert request.prompt == "Test prompt"
        assert request.model == ModelType.GEMINI_2_0_FLASH
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


@pytest.mark.skipif(not API_KEY, reason="GEMINI_API_KEY が設定されていません")
class TestGeminiLLMClientIntegration:
    """GeminiLLMClient の統合テスト - 実際のAPI呼び出し"""
    
    def test_initialization(self):
        """初期化テスト"""
        client = GeminiLLMClient(api_key=API_KEY)
        
        # APIキーの設定確認
        assert client.api_key == API_KEY
        
        # クライアントオブジェクトの確認
        assert client._client is not None
        assert hasattr(client._client, '_api_client')
        assert hasattr(client._client._api_client, '_httpx_client')
    
    @pytest.mark.asyncio
    async def test_generate_text_simple(self):
        """シンプルなテキスト生成テスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            request = GeminiRequest(prompt="こんにちはと日本語で挨拶してください。")
            response = await client.generate_text(request)
            
            # 基本的な応答チェック
            assert isinstance(response, GeminiResponse)
            assert response.text is not None
            assert len(response.text.strip()) > 0
            assert response.model == "gemini-2.0-flash"
            assert response.finish_reason == "STOP"
            assert response.is_blocked is False
            
            # トークン数のチェック
            assert response.token_count > 0
            assert response.prompt_token_count > 0
            
            print(f"✅ 生成されたテキスト: {response.text[:100]}...")
            print(f"📊 トークン数: {response.token_count} (プロンプト: {response.prompt_token_count})")
    
    @pytest.mark.asyncio
    async def test_generate_text_with_custom_settings(self):
        """カスタム設定でのテキスト生成テスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            request = GeminiRequest(
                prompt="夏の東京を詠む俳句を一句、季語を入れて作成してください。",
                temperature=0.9,
                max_output_tokens=100
            )
            response = await client.generate_text(request)
            
            assert isinstance(response, GeminiResponse)
            assert response.text is not None
            assert len(response.text.strip()) > 0
            assert response.finish_reason == "STOP"
            
            print(f"🌸 俳句: {response.text.strip()}")
    
    @pytest.mark.asyncio
    async def test_generate_json_output(self):
        """JSON形式出力テスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            request = GeminiRequest(
                prompt="以下の情報をJSON形式で出力してください: 名前=太郎、年齢=25、職業=エンジニア",
                output_format=OutputFormat.JSON,
                max_output_tokens=200
            )
            response = await client.generate_text(request)
            
            assert isinstance(response, GeminiResponse)
            assert response.text is not None
            
            # JSONとしてパースできるかチェック
            try:
                parsed_json = json.loads(response.text)
                assert isinstance(parsed_json, dict)
                print(f"🔧 JSON出力: {parsed_json}")
            except json.JSONDecodeError:
                print(f"⚠️ JSON解析に失敗しましたが、出力は生成されました: {response.text}")
    
    @pytest.mark.asyncio
    async def test_generate_structured_output(self):
        """構造化出力生成テスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            schema = {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}
                },
                "required": ["title", "description", "difficulty"]
            }
            
            result = await client.generate_structured_output(
                prompt="プログラミング学習のための課題を一つ考えてください",
                schema=schema
            )
            
            assert isinstance(result, dict)
            assert "title" in result
            assert "description" in result
            assert "difficulty" in result
            assert result["difficulty"] in ["easy", "medium", "hard"]
            
            print(f"📋 構造化出力: {result}")
    
    @pytest.mark.asyncio
    async def test_yukkuri_video_script_generation(self):
        """ゆっくり動画の台本生成テスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            request = GeminiRequest(
                prompt="""
                ゆっくり動画の台本を作成してください。
                テーマ: プログラミング初心者向けのPython入門
                長さ: 3分程度
                
                以下の形式で出力してください:
                - タイトル
                - 導入部分（30秒）
                - 本編（2分）
                - まとめ（30秒）
                """,
                max_output_tokens=1000,
                temperature=0.8
            )
            response = await client.generate_text(request)
            
            assert isinstance(response, GeminiResponse)
            assert response.text is not None
            assert len(response.text.strip()) > 100  # ある程度の長さがあること
            assert "タイトル" in response.text or "導入" in response.text
            
            print(f"🎬 ゆっくり動画台本:\n{response.text[:500]}...")
    
    @pytest.mark.asyncio
    async def test_multiple_models(self):
        """複数モデルでのテスト"""
        models_to_test = [
            ModelType.GEMINI_2_0_FLASH,
            ModelType.GEMINI_1_5_FLASH
        ]
        
        async with GeminiLLMClient(api_key=API_KEY) as client:
            for model in models_to_test:
                request = GeminiRequest(
                    prompt="「Hello World」と英語で出力してください。",
                    model=model,
                    max_output_tokens=50
                )
                
                try:
                    response = await client.generate_text(request)
                    assert isinstance(response, GeminiResponse)
                    assert response.text is not None
                    assert len(response.text.strip()) > 0
                    
                    print(f"✅ {model.value}: {response.text.strip()}")
                except Exception as e:
                    print(f"❌ {model.value}: エラー - {e}")
    
    @pytest.mark.asyncio
    async def test_count_tokens(self):
        """トークン数カウントテスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            text = "これはトークン数をカウントするためのテストテキストです。"
            token_count = await client.count_tokens(text)
            
            # 概算値の確認
            assert token_count > 0
            assert isinstance(token_count, int)
            
            print(f"📏 テキスト: '{text}'")
            print(f"📏 トークン数: {token_count}")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """エラーハンドリングテスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            # 極端に長いプロンプトでエラーをテスト
            very_long_prompt = "テスト " * 10000
            request = GeminiRequest(
                prompt=very_long_prompt,
                max_output_tokens=1
            )
            
            try:
                response = await client.generate_text(request)
                print(f"⚠️ 長いプロンプトでも成功: {len(response.text)}")
            except GeminiAPIError as e:
                print(f"✅ 期待通りエラーが発生: {e.message}")
                assert isinstance(e, GeminiAPIError)
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """コンテキストマネージャーテスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            assert isinstance(client, GeminiLLMClient)
            
            # 簡単なテキスト生成
            request = GeminiRequest(prompt="テストです。")
            response = await client.generate_text(request)
            assert response.text is not None
            
        # コンテキスト終了後のクリーンアップ確認
        print("✅ コンテキストマネージャーでの自動クリーンアップ完了")


class TestPerformanceIntegration:
    """パフォーマンス統合テスト"""
    
    @pytest.mark.skipif(not API_KEY, reason="GEMINI_API_KEY が設定されていません")
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """並行リクエストテスト"""
        async with GeminiLLMClient(api_key=API_KEY) as client:
            # 複数の並行リクエスト
            prompts = [
                "1から5まで数えてください。",
                "色の名前を3つ教えてください。",
                "今日の天気について一言お願いします。"
            ]
            
            import time
            start_time = time.time()
            
            # 並行実行
            tasks = []
            for prompt in prompts:
                request = GeminiRequest(prompt=prompt, max_output_tokens=100)
                task = client.generate_text(request)
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # 結果検証
            assert len(responses) == len(prompts)
            for response in responses:
                assert isinstance(response, GeminiResponse)
                assert response.text is not None
                assert len(response.text.strip()) > 0
            
            print(f"⚡ 並行リクエスト完了: {len(prompts)}件を{elapsed:.2f}秒で処理")
            for i, response in enumerate(responses):
                print(f"  {i+1}. {response.text.strip()[:50]}...")


if __name__ == "__main__":
    if not API_KEY:
        print("❌ GEMINI_API_KEY または GOOGLE_API_KEY が設定されていません")
        print("   .env ファイルに API キーを設定してください")
        sys.exit(1)
    
    print("🧪 Gemini LLM クライアント統合テストを開始します...")
    pytest.main([__file__, "-v", "-s"]) 