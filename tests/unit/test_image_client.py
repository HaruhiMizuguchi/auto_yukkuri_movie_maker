"""
画像生成 API クライアントのテスト
"""

import pytest
import json
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
from pathlib import Path
from PIL import Image
import io
import base64

from src.api.image_client import (
    ImageGenerationClient,
    ImageRequest,
    ImageEditRequest,
    ImageResponse,
    ResponseModality,
    ImageFormat,
    ImageGenerationError,
    InvalidPromptError,
    ContentFilterError
)
from src.core.api_client import APIResponse, NetworkError


class TestImageRequest:
    """ImageRequest のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        request = ImageRequest(prompt="A beautiful landscape")
        
        assert request.prompt == "A beautiful landscape"
        assert request.response_modalities == [ResponseModality.TEXT, ResponseModality.IMAGE]
        assert request.max_output_tokens is None
        assert request.temperature is None
        assert request.top_p is None
    
    def test_custom_values(self):
        """カスタム値設定テスト"""
        request = ImageRequest(
            prompt="A cat in the garden",
            response_modalities=[ResponseModality.IMAGE],
            max_output_tokens=1000,
            temperature=0.8,
            top_p=0.9
        )
        
        assert request.prompt == "A cat in the garden"
        assert request.response_modalities == [ResponseModality.IMAGE]
        assert request.max_output_tokens == 1000
        assert request.temperature == 0.8
        assert request.top_p == 0.9


class TestImageEditRequest:
    """ImageEditRequest のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        image_data = b"fake_image_data"
        request = ImageEditRequest(
            prompt="Add a hat to this person",
            image_data=image_data
        )
        
        assert request.prompt == "Add a hat to this person"
        assert request.image_data == image_data
        assert request.mime_type == "image/png"
        assert request.response_modalities == [ResponseModality.TEXT, ResponseModality.IMAGE]
        assert request.max_output_tokens is None
        assert request.temperature is None
        assert request.top_p is None
    
    def test_custom_values(self):
        """カスタム値設定テスト"""
        image_data = b"fake_image_data"
        request = ImageEditRequest(
            prompt="Change the background",
            image_data=image_data,
            mime_type="image/jpeg",
            response_modalities=[ResponseModality.IMAGE],
            max_output_tokens=500,
            temperature=0.5,
            top_p=0.8
        )
        
        assert request.prompt == "Change the background"
        assert request.image_data == image_data
        assert request.mime_type == "image/jpeg"
        assert request.response_modalities == [ResponseModality.IMAGE]
        assert request.max_output_tokens == 500
        assert request.temperature == 0.5
        assert request.top_p == 0.8


class TestImageResponse:
    """ImageResponse のテスト"""
    
    def test_basic_response(self):
        """基本レスポンステスト"""
        # 小さなテスト画像を作成
        image = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        response = ImageResponse(
            image_data=image_data,
            text_content="Generated a red square image",
            format=ImageFormat.PNG,
            generation_metadata={
                "model": "gemini-2.0-flash-preview-image-generation",
                "prompt_used": True
            }
        )
        
        assert response.image_data == image_data
        assert response.text_content == "Generated a red square image"
        assert response.format == ImageFormat.PNG
        assert response.generation_metadata["model"] == "gemini-2.0-flash-preview-image-generation"
    
    def test_size_property(self):
        """サイズプロパティテスト"""
        # 小さなテスト画像を作成
        image = Image.new('RGB', (512, 768), color='blue')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        response = ImageResponse(
            image_data=image_data,
            format=ImageFormat.PNG
        )
        
        assert response.size == (512, 768)
    
    def test_size_property_error_handling(self):
        """サイズプロパティのエラーハンドリングテスト"""
        response = ImageResponse(
            image_data=b"invalid_image_data",
            format=ImageFormat.PNG
        )
        
        # 無効な画像データの場合は (0, 0) を返す
        assert response.size == (0, 0)
    
    def test_save_image(self):
        """画像保存テスト"""
        # 小さなテスト画像を作成
        image = Image.new('RGB', (50, 50), color='green')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        response = ImageResponse(
            image_data=image_data,
            format=ImageFormat.PNG
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            tmp_file_path = tmp_file.name
        
        try:
            response.save_image(tmp_file_path)
            
            # 保存された画像を読み込んで検証
            with open(tmp_file_path, 'rb') as f:
                saved_data = f.read()
            
            assert saved_data == image_data
        finally:
            import os
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    def test_to_pil_image(self):
        """PIL Image変換テスト"""
        # 小さなテスト画像を作成
        original_image = Image.new('RGB', (30, 30), color='yellow')
        img_buffer = io.BytesIO()
        original_image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        response = ImageResponse(
            image_data=image_data,
            format=ImageFormat.PNG
        )
        
        pil_image = response.to_pil_image()
        
        assert isinstance(pil_image, Image.Image)
        assert pil_image.size == (30, 30)
        assert pil_image.mode == 'RGB'


class TestImageGenerationErrors:
    """画像生成エラーのテスト"""
    
    def test_image_generation_error(self):
        """ImageGenerationError テスト"""
        error = ImageGenerationError("Test error", prompt="test prompt")
        
        assert error.message == "Test error"
        assert error.prompt == "test prompt"
        assert error.context["prompt"] == "test prompt"
    
    def test_invalid_prompt_error(self):
        """InvalidPromptError テスト"""
        error = InvalidPromptError("Invalid content", "inappropriate prompt")
        
        assert "Invalid content" in error.message
        assert error.error_code == "INVALID_PROMPT"
        assert error.prompt == "inappropriate prompt"
        assert error.retry_recommended is False
    
    def test_content_filter_error(self):
        """ContentFilterError テスト"""
        filter_details = {"reason": "nsfw", "confidence": 0.95}
        error = ContentFilterError("Blocked by filter", "test prompt", filter_details)
        
        assert error.message == "Blocked by filter"
        assert error.error_code == "CONTENT_FILTERED"
        assert error.prompt == "test prompt"
        assert error.filter_details == filter_details
        assert error.retry_recommended is False


class TestImageGenerationClient:
    """ImageGenerationClient のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        client = ImageGenerationClient(api_key="test_key")
        
        assert client.api_key == "test_key"
        assert client.MODEL_NAME == "gemini-2.0-flash-preview-image-generation"
        assert client.base_url == "https://generativelanguage.googleapis.com"
    
    def test_initialization_custom_config(self):
        """カスタム設定での初期化テスト"""
        from src.core.api_client import RetryConfig, RateLimitConfig
        
        retry_config = RetryConfig(max_retries=5)
        rate_limit_config = RateLimitConfig(requests_per_minute=30)
        
        client = ImageGenerationClient(
            api_key="test_key",
            retry_config=retry_config,
            rate_limit_config=rate_limit_config
        )
        
        assert client.retry_config.max_retries == 5
        assert client.rate_limit_config.requests_per_minute == 30
    
    def test_create_generate_config(self):
        """生成設定作成テスト"""
        client = ImageGenerationClient(api_key="test_key")
        
        config = client._create_generate_config(
            response_modalities=[ResponseModality.TEXT, ResponseModality.IMAGE],
            max_output_tokens=1000,
            temperature=0.8,
            top_p=0.9
        )
        
        # GenerateContentConfigオブジェクトが正しく作成されているかを確認
        assert hasattr(config, 'response_modalities')
        # 実際の属性確認はオブジェクトの内部構造に依存するため、作成が成功することのみ確認
    
    @pytest.mark.asyncio
    async def test_generate_images_success(self):
        """画像生成成功テスト"""
        # テスト画像データ作成
        image = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        # モックレスポンス作成
        mock_part = MagicMock()
        mock_part.text = "Generated an image of a beautiful landscape"
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = image_data
        
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        client = ImageGenerationClient(api_key="test_key")
        
        with patch.object(client, '_check_rate_limit', new_callable=AsyncMock):
            with patch.object(client._client.models, 'generate_content', return_value=mock_response):
                request = ImageRequest(prompt="A beautiful landscape")
                
                responses = await client.generate_images(request)
                
                assert len(responses) == 1
                assert responses[0].image_data == image_data
                assert responses[0].text_content == "Generated an image of a beautiful landscape"
    
    @pytest.mark.asyncio
    async def test_generate_images_content_filter(self):
        """画像生成コンテンツフィルターテスト"""
        client = ImageGenerationClient(api_key="test_key")
        
        with patch.object(client, '_check_rate_limit', new_callable=AsyncMock):
            with patch.object(client._client.models, 'generate_content', side_effect=Exception("content policy violation")):
                request = ImageRequest(prompt="inappropriate content")
                
                with pytest.raises(ContentFilterError) as exc_info:
                    await client.generate_images(request)
                
                assert "Content filtered" in str(exc_info.value)
                assert exc_info.value.prompt == "inappropriate content"
    
    @pytest.mark.asyncio
    async def test_generate_images_invalid_prompt(self):
        """画像生成無効プロンプトテスト"""
        client = ImageGenerationClient(api_key="test_key")
        
        with patch.object(client, '_check_rate_limit', new_callable=AsyncMock):
            with patch.object(client._client.models, 'generate_content', side_effect=Exception("invalid prompt format")):
                request = ImageRequest(prompt="")
                
                with pytest.raises(InvalidPromptError) as exc_info:
                    await client.generate_images(request)
                
                assert "Invalid prompt" in str(exc_info.value)
                assert exc_info.value.prompt == ""
    
    @pytest.mark.asyncio
    async def test_generate_images_no_images_generated(self):
        """画像未生成テスト"""
        # テキストのみのレスポンス（画像なし）
        mock_part = MagicMock()
        mock_part.text = "Cannot generate image"
        mock_part.inline_data = None
        
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        client = ImageGenerationClient(api_key="test_key")
        
        with patch.object(client, '_check_rate_limit', new_callable=AsyncMock):
            with patch.object(client._client.models, 'generate_content', return_value=mock_response):
                request = ImageRequest(prompt="test prompt")
                
                with pytest.raises(ImageGenerationError) as exc_info:
                    await client.generate_images(request)
                
                assert "No images were generated" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_edit_image_success(self):
        """画像編集成功テスト"""
        # 入力画像データ作成
        input_image = Image.new('RGB', (100, 100), color='blue')
        input_buffer = io.BytesIO()
        input_image.save(input_buffer, format='PNG')
        input_image_data = input_buffer.getvalue()
        
        # 出力画像データ作成
        output_image = Image.new('RGB', (100, 100), color='green')
        output_buffer = io.BytesIO()
        output_image.save(output_buffer, format='PNG')
        output_image_data = output_buffer.getvalue()
        
        # モックレスポンス作成
        mock_part = MagicMock()
        mock_part.text = "Added a hat to the person"
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = output_image_data
        
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        client = ImageGenerationClient(api_key="test_key")
        
        with patch.object(client, '_check_rate_limit', new_callable=AsyncMock):
            with patch.object(client._client.models, 'generate_content', return_value=mock_response):
                request = ImageEditRequest(
                    prompt="Add a hat to this person",
                    image_data=input_image_data
                )
                
                responses = await client.edit_image(request)
                
                assert len(responses) == 1
                assert responses[0].image_data == output_image_data
                assert responses[0].text_content == "Added a hat to the person"
    
    @pytest.mark.asyncio
    async def test_batch_generate_images_success(self):
        """バッチ画像生成成功テスト"""
        client = ImageGenerationClient(api_key="test_key")
        
        # テスト画像データ作成
        image_data = b"fake_image_data"
        expected_response = [ImageResponse(image_data=image_data)]
        
        with patch.object(client, 'generate_images', new_callable=AsyncMock, return_value=expected_response):
            requests = [
                ImageRequest(prompt="landscape 1"),
                ImageRequest(prompt="landscape 2")
            ]
            
            results = await client.batch_generate_images(requests)
            
            assert len(results) == 2
            assert all(len(result) == 1 for result in results)
            assert all(result[0].image_data == image_data for result in results)
    
    @pytest.mark.asyncio
    async def test_batch_generate_images_with_error(self):
        """バッチ画像生成エラーテスト"""
        client = ImageGenerationClient(api_key="test_key")
        
        async def mock_generate_side_effect(request):
            if "error" in request.prompt:
                raise ImageGenerationError("Test error")
            return [ImageResponse(image_data=b"fake_image_data")]
        
        with patch.object(client, 'generate_images', side_effect=mock_generate_side_effect):
            requests = [
                ImageRequest(prompt="normal prompt"),
                ImageRequest(prompt="error prompt"),
                ImageRequest(prompt="another normal prompt")
            ]
            
            results = await client.batch_generate_images(requests)
            
            assert len(results) == 3
            assert len(results[0]) == 1  # 成功
            assert len(results[1]) == 0  # エラー
            assert len(results[2]) == 1  # 成功
    
    @pytest.mark.asyncio
    async def test_generate_with_conversation_success(self):
        """会話履歴での画像生成成功テスト"""
        # テスト画像データ作成
        image = Image.new('RGB', (100, 100), color='purple')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        base64_image = base64.b64encode(image_data).decode()
        
        # 出力画像データ作成
        output_image_data = b"generated_image_data"
        
        # モックレスポンス作成
        mock_part = MagicMock()
        mock_part.text = "Created based on conversation"
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = output_image_data
        
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        client = ImageGenerationClient(api_key="test_key")
        
        with patch.object(client, '_check_rate_limit', new_callable=AsyncMock):
            with patch.object(client._client.models, 'generate_content', return_value=mock_response):
                conversation_history = [
                    {"type": "text", "content": "Create an image"},
                    {"type": "image", "content": base64_image},
                    {"type": "text", "content": "Make it more colorful"}
                ]
                
                responses = await client.generate_with_conversation(conversation_history)
                
                assert len(responses) == 1
                assert responses[0].image_data == output_image_data
                assert responses[0].text_content == "Created based on conversation"
    
    @pytest.mark.asyncio
    async def test_close(self):
        """クリーンアップテスト"""
        client = ImageGenerationClient(api_key="test_key")
        
        # クリーンアップ実行（エラーが発生しないことを確認）
        await client.close()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """コンテキストマネージャーテスト"""
        async with ImageGenerationClient(api_key="test_key") as client:
            assert client is not None
            assert client.api_key == "test_key"


class TestPerformance:
    """パフォーマンステスト"""
    
    def test_request_creation_performance(self):
        """リクエスト作成パフォーマンステスト"""
        import time
        
        start_time = time.time()
        
        # 大量のリクエスト作成
        for i in range(1000):
            request = ImageRequest(
                prompt=f"Test prompt {i}",
                max_output_tokens=500,
                temperature=0.7
            )
            
        end_time = time.time()
        
        # 1秒以内で完了することを確認
        assert (end_time - start_time) < 1.0
    
    def test_response_creation_performance(self):
        """レスポンス作成パフォーマンステスト"""
        import time
        
        # 小さなテスト画像作成
        image = Image.new('RGB', (10, 10), color='red')
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        start_time = time.time()
        
        # 大量のレスポンス作成
        for i in range(1000):
            response = ImageResponse(
                image_data=image_data,
                text_content=f"Test response {i}",
                generation_metadata={"test": True}
            )
            
        end_time = time.time()
        
        # 1秒以内で完了することを確認
        assert (end_time - start_time) < 1.0 