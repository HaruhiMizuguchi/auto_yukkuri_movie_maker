"""
YouTube API クライアントのテスト
"""

import pytest
import json
import tempfile
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from src.api.youtube_client import (
    YouTubeClient,
    VideoUploadRequest,
    VideoUploadResponse,
    VideoMetadata,
    VideoPrivacy,
    VideoCategory,
    ThumbnailRequest,
    ThumbnailResponse,
    YouTubeAPIError,
    VideoUploadError,
    ThumbnailUploadError,
    QuotaExceededError
)
from src.core.api_client import APIResponse, NetworkError


class TestVideoMetadata:
    """VideoMetadata のテスト"""
    
    def test_default_values(self):
        """デフォルト値テスト"""
        metadata = VideoMetadata(
            title="テスト動画",
            description="これはテスト動画です"
        )
        
        assert metadata.title == "テスト動画"
        assert metadata.description == "これはテスト動画です"
        assert metadata.privacy == VideoPrivacy.PRIVATE
        assert metadata.category == VideoCategory.ENTERTAINMENT
        assert metadata.tags == []
        assert metadata.language == "ja"
    
    def test_custom_values(self):
        """カスタム値設定テスト"""
        metadata = VideoMetadata(
            title="カスタム動画",
            description="詳細説明",
            privacy=VideoPrivacy.PUBLIC,
            category=VideoCategory.EDUCATION,
            tags=["ゆっくり", "東方"],
            language="ja",
            thumbnail_url="https://example.com/thumb.jpg"
        )
        
        assert metadata.title == "カスタム動画"
        assert metadata.description == "詳細説明"
        assert metadata.privacy == VideoPrivacy.PUBLIC
        assert metadata.category == VideoCategory.EDUCATION
        assert metadata.tags == ["ゆっくり", "東方"]
        assert metadata.language == "ja"
        assert metadata.thumbnail_url == "https://example.com/thumb.jpg"


class TestVideoUploadRequest:
    """VideoUploadRequest のテスト"""
    
    def test_basic_request(self):
        """基本リクエストテスト"""
        metadata = VideoMetadata(
            title="アップロード動画",
            description="アップロードテスト"
        )
        
        request = VideoUploadRequest(
            video_file_path="test.mp4",
            metadata=metadata
        )
        
        assert request.video_file_path == "test.mp4"
        assert request.metadata.title == "アップロード動画"
        assert request.notify_subscribers is True
        assert request.enable_auto_chapters is False
    
    def test_with_options(self):
        """オプション付きリクエストテスト"""
        metadata = VideoMetadata(
            title="オプション動画",
            description="オプションテスト"
        )
        
        request = VideoUploadRequest(
            video_file_path="option.mp4",
            metadata=metadata,
            notify_subscribers=False,
            enable_auto_chapters=True,
            schedule_publish_at=datetime(2024, 12, 31, 12, 0, 0)
        )
        
        assert request.notify_subscribers is False
        assert request.enable_auto_chapters is True
        assert request.schedule_publish_at == datetime(2024, 12, 31, 12, 0, 0)


class TestVideoUploadResponse:
    """VideoUploadResponse のテスト"""
    
    def test_basic_response(self):
        """基本レスポンステスト"""
        response = VideoUploadResponse(
            video_id="ABC123DEF456",
            upload_status="uploaded",
            video_url="https://youtube.com/watch?v=ABC123DEF456",
            processing_status="processing",
            upload_metadata={
                "upload_time": "2024-01-01T00:00:00Z",
                "file_size": 104857600
            }
        )
        
        assert response.video_id == "ABC123DEF456"
        assert response.upload_status == "uploaded"
        assert response.video_url == "https://youtube.com/watch?v=ABC123DEF456"
        assert response.processing_status == "processing"
        assert response.upload_metadata["file_size"] == 104857600
    
    def test_is_upload_complete(self):
        """アップロード完了判定テスト"""
        # 完了
        response_complete = VideoUploadResponse(
            video_id="ABC123",
            upload_status="uploaded",
            video_url="https://youtube.com/watch?v=ABC123",
            processing_status="succeeded"
        )
        assert response_complete.is_upload_complete is True
        
        # 処理中
        response_processing = VideoUploadResponse(
            video_id="DEF456",
            upload_status="uploaded",
            video_url="https://youtube.com/watch?v=DEF456",
            processing_status="processing"
        )
        assert response_processing.is_upload_complete is False
    
    def test_is_published(self):
        """公開状態判定テスト"""
        # 公開済み
        response_public = VideoUploadResponse(
            video_id="ABC123",
            upload_status="uploaded",
            video_url="https://youtube.com/watch?v=ABC123",
            processing_status="succeeded",
            privacy_status="public"
        )
        assert response_public.is_published is True
        
        # 非公開
        response_private = VideoUploadResponse(
            video_id="DEF456",
            upload_status="uploaded", 
            video_url="https://youtube.com/watch?v=DEF456",
            processing_status="succeeded",
            privacy_status="private"
        )
        assert response_private.is_published is False


class TestThumbnailRequest:
    """ThumbnailRequest のテスト"""
    
    def test_basic_request(self):
        """基本リクエストテスト"""
        request = ThumbnailRequest(
            video_id="ABC123DEF456",
            thumbnail_file_path="thumb.jpg"
        )
        
        assert request.video_id == "ABC123DEF456"
        assert request.thumbnail_file_path == "thumb.jpg"


class TestThumbnailResponse:
    """ThumbnailResponse のテスト"""
    
    def test_basic_response(self):
        """基本レスポンステスト"""
        response = ThumbnailResponse(
            video_id="ABC123DEF456",
            thumbnail_url="https://i.ytimg.com/vi/ABC123DEF456/maxresdefault.jpg",
            upload_status="uploaded",
            upload_metadata={
                "width": 1280,
                "height": 720,
                "format": "jpg"
            }
        )
        
        assert response.video_id == "ABC123DEF456"
        assert response.thumbnail_url.endswith("maxresdefault.jpg")
        assert response.upload_status == "uploaded"
        assert response.upload_metadata["width"] == 1280


class TestYouTubeAPIErrors:
    """YouTube API エラーのテスト"""
    
    def test_youtube_api_error(self):
        """YouTubeAPIError テスト"""
        error = YouTubeAPIError("API error", video_id="ABC123")
        
        assert error.message == "API error"
        assert error.video_id == "ABC123"
        assert error.context["video_id"] == "ABC123"
    
    def test_video_upload_error(self):
        """VideoUploadError テスト"""
        error = VideoUploadError("Upload failed", "DEF456", "test.mp4")
        
        assert "Upload failed" in error.message
        assert error.error_code == "VIDEO_UPLOAD_ERROR"
        assert error.video_id == "DEF456"
        assert error.video_file_path == "test.mp4"
    
    def test_thumbnail_upload_error(self):
        """ThumbnailUploadError テスト"""
        error = ThumbnailUploadError("Thumbnail failed", "GHI789", "thumb.jpg")
        
        assert error.message == "Thumbnail failed"
        assert error.error_code == "THUMBNAIL_UPLOAD_ERROR"
        assert error.video_id == "GHI789"
        assert error.thumbnail_file_path == "thumb.jpg"
    
    def test_quota_exceeded_error(self):
        """QuotaExceededError テスト"""
        quota_info = {"daily_limit": 10000, "used": 9800}
        error = QuotaExceededError("Quota exceeded", quota_info)
        
        assert error.message == "Quota exceeded"
        assert error.error_code == "QUOTA_EXCEEDED"
        assert error.quota_info == quota_info
        assert error.retry_recommended is False


class TestYouTubeClient:
    """YouTubeClient のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        client = YouTubeClient(api_key="test-api-key")
        
        assert client.api_key == "test-api-key"
        assert client.base_url == "https://www.googleapis.com/youtube/v3"
        assert client.rate_limit_config.requests_per_minute == 100
        assert client.rate_limit_config.requests_per_hour == 1000
    
    def test_initialization_with_oauth(self):
        """OAuth認証初期化テスト"""
        client = YouTubeClient(
            oauth_token="oauth-token",
            oauth_refresh_token="refresh-token"
        )
        
        assert client.oauth_token == "oauth-token"
        assert client.oauth_refresh_token == "refresh-token"
        assert client.api_key is None
    
    def test_build_video_metadata(self):
        """動画メタデータ構築テスト"""
        client = YouTubeClient(api_key="test-key")
        
        metadata = VideoMetadata(
            title="テストタイトル",
            description="テスト説明",
            tags=["tag1", "tag2"],
            privacy=VideoPrivacy.PUBLIC,
            category=VideoCategory.GAMING
        )
        
        data = client._build_video_metadata(metadata)
        
        assert data["snippet"]["title"] == "テストタイトル"
        assert data["snippet"]["description"] == "テスト説明"
        assert data["snippet"]["tags"] == ["tag1", "tag2"]
        assert data["snippet"]["categoryId"] == "20"  # Gaming
        assert data["status"]["privacyStatus"] == "public"
    
    def test_build_upload_request_data(self):
        """アップロードリクエストデータ構築テスト"""
        client = YouTubeClient(api_key="test-key")
        
        metadata = VideoMetadata(
            title="アップロード動画",
            description="アップロードテスト"
        )
        
        request = VideoUploadRequest(
            video_file_path="test.mp4",
            metadata=metadata,
            notify_subscribers=False
        )
        
        data = client._build_upload_request_data(request)
        
        assert data["snippet"]["title"] == "アップロード動画"
        assert data["status"]["privacyStatus"] == "private"
        assert data["status"]["selfDeclaredMadeForKids"] is False
    
    def test_parse_upload_response(self):
        """アップロードレスポンス解析テスト"""
        client = YouTubeClient(api_key="test-key")
        
        response_data = {
            "id": "ABC123DEF456",
            "status": {
                "uploadStatus": "uploaded",
                "privacyStatus": "private"
            },
            "processingDetails": {
                "processingStatus": "processing"
            }
        }
        
        response = client._parse_upload_response(response_data)
        
        assert response.video_id == "ABC123DEF456"
        assert response.upload_status == "uploaded"
        assert response.processing_status == "processing"
        assert response.video_url == "https://youtube.com/watch?v=ABC123DEF456"
    
    @pytest.mark.asyncio
    async def test_upload_video_success(self):
        """動画アップロード成功テスト"""
        client = YouTubeClient(api_key="test-key")
        
        # ファイル存在チェックをモック
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('src.api.youtube_client.aiofiles.open') as mock_aiofile:
            
            # ファイルサイズを設定
            mock_stat.return_value.st_size = 10485760  # 10MB
            
            # aiofiles.openの戻り値をモック
            mock_file = AsyncMock()
            mock_file.read.return_value = b"fake_video_data"
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_file
            mock_context.__aexit__.return_value = None
            mock_aiofile.return_value = mock_context
            
            mock_response = APIResponse(
                status_code=200,
                headers={},
                data={
                    "id": "XYZ789ABC123",
                    "status": {
                        "uploadStatus": "uploaded",
                        "privacyStatus": "private"
                    },
                    "processingDetails": {
                        "processingStatus": "processing"
                    }
                }
            )
            
            with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = mock_response
                
                metadata = VideoMetadata(
                    title="テスト動画",
                    description="テスト説明"
                )
                
                request = VideoUploadRequest(
                    video_file_path="test.mp4",
                    metadata=metadata
                )
                
                response = await client.upload_video(request)
                
                assert response.video_id == "XYZ789ABC123"
                assert response.upload_status == "uploaded"
                assert response.processing_status == "processing"
    
    @pytest.mark.asyncio
    async def test_upload_video_file_not_found(self):
        """動画ファイル存在しないエラーテスト"""
        client = YouTubeClient(api_key="test-key")
        
        with patch('pathlib.Path.exists', return_value=False):
            metadata = VideoMetadata(
                title="存在しない動画",
                description="テスト"
            )
            
            request = VideoUploadRequest(
                video_file_path="nonexistent.mp4",
                metadata=metadata
            )
            
            with pytest.raises(VideoUploadError) as exc_info:
                await client.upload_video(request)
            
            assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_upload_video_quota_exceeded(self):
        """動画アップロード クォータ超過テスト"""
        client = YouTubeClient(api_key="test-key")
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('src.api.youtube_client.aiofiles.open') as mock_aiofile:
            
            mock_stat.return_value.st_size = 10485760
            
            # aiofiles.openの戻り値をモック
            mock_file = AsyncMock()
            mock_file.read.return_value = b"fake_video_data"
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_file
            mock_context.__aexit__.return_value = None
            mock_aiofile.return_value = mock_context
            
            mock_response = APIResponse(
                status_code=403,
                headers={},
                data={
                    "error": {
                        "code": 403,
                        "message": "quotaExceeded",
                        "errors": [
                            {
                                "domain": "youtube.quota",
                                "reason": "quotaExceeded"
                            }
                        ]
                    }
                }
            )
            
            with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = mock_response
                
                metadata = VideoMetadata(title="テスト", description="テスト")
                request = VideoUploadRequest("test.mp4", metadata)
                
                with pytest.raises(QuotaExceededError):
                    await client.upload_video(request)
    
    @pytest.mark.asyncio
    async def test_upload_thumbnail_success(self):
        """サムネイルアップロード成功テスト"""
        client = YouTubeClient(api_key="test-key")
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.api.youtube_client.aiofiles.open') as mock_aiofile:
            
            # aiofiles.openの戻り値をモック
            mock_file = AsyncMock()
            mock_file.read.return_value = b"fake_thumbnail_data"
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_file
            mock_context.__aexit__.return_value = None
            mock_aiofile.return_value = mock_context
            
            mock_response = APIResponse(
                status_code=200,
                headers={},
                data={
                    "items": [
                        {
                            "default": {
                                "url": "https://i.ytimg.com/vi/ABC123/default.jpg"
                            },
                            "high": {
                                "url": "https://i.ytimg.com/vi/ABC123/hqdefault.jpg"
                            }
                        }
                    ]
                }
            )
            
            with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = mock_response
                
                request = ThumbnailRequest(
                    video_id="ABC123",
                    thumbnail_file_path="thumb.jpg"
                )
                
                response = await client.upload_thumbnail(request)
                
                assert response.video_id == "ABC123"
                assert response.upload_status == "uploaded"
                assert "hqdefault.jpg" in response.thumbnail_url
    
    @pytest.mark.asyncio
    async def test_get_video_status(self):
        """動画ステータス取得テスト"""
        client = YouTubeClient(api_key="test-key")
        
        mock_response = APIResponse(
            status_code=200,
            headers={},
            data={
                "items": [
                    {
                        "id": "DEF456",
                        "status": {
                            "uploadStatus": "uploaded",
                            "privacyStatus": "public"
                        },
                        "processingDetails": {
                            "processingStatus": "succeeded"
                        }
                    }
                ]
            }
        )
        
        with patch.object(client, 'send_request_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            response = await client.get_video_status("DEF456")
            
            assert response.video_id == "DEF456"
            assert response.upload_status == "uploaded"
            assert response.processing_status == "succeeded"
            assert response.is_published is True
    
    @pytest.mark.asyncio
    async def test_batch_upload_videos(self):
        """バッチ動画アップロードテスト"""
        client = YouTubeClient(api_key="test-key")
        
        # アップロード成功レスポンス
        mock_upload_response = VideoUploadResponse(
            video_id="BATCH123",
            upload_status="uploaded",
            video_url="https://youtube.com/watch?v=BATCH123",
            processing_status="processing"
        )
        
        with patch.object(client, 'upload_video', new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = mock_upload_response
            
            requests = [
                VideoUploadRequest(
                    video_file_path="video1.mp4",
                    metadata=VideoMetadata(title="動画1", description="説明1")
                ),
                VideoUploadRequest(
                    video_file_path="video2.mp4",
                    metadata=VideoMetadata(title="動画2", description="説明2")
                )
            ]
            
            responses = await client.batch_upload_videos(requests)
            
            assert len(responses) == 2
            assert all(r.video_id == "BATCH123" for r in responses)
            assert mock_upload.call_count == 2
    
    @pytest.mark.asyncio
    async def test_close(self):
        """リソースクリーンアップテスト"""
        client = YouTubeClient(api_key="test-key")
        
        # セッションが None の場合
        await client.close()
        
        # セッションがある場合
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session
        
        await client.close()
        
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """コンテキストマネージャーテスト"""
        async with YouTubeClient(api_key="test-key") as client:
            assert isinstance(client, YouTubeClient)
        
        # __aexit__ で close が呼ばれることを確認
        with patch.object(client, 'close', new_callable=AsyncMock) as mock_close:
            async with client:
                pass
            mock_close.assert_called_once()


# パフォーマンステスト
class TestPerformance:
    """パフォーマンステスト"""
    
    def test_metadata_building_performance(self):
        """メタデータ構築パフォーマンステスト"""
        client = YouTubeClient(api_key="test-key")
        
        metadata = VideoMetadata(
            title="長いタイトル " * 20,
            description="詳細な説明 " * 100,
            tags=["tag" + str(i) for i in range(50)]
        )
        
        import time
        start_time = time.time()
        
        for _ in range(100):
            client._build_video_metadata(metadata)
        
        end_time = time.time()
        
        # 100回の処理が1秒以内で完了することを確認
        assert end_time - start_time < 1.0
    
    def test_response_parsing_performance(self):
        """レスポンス解析パフォーマンステスト"""
        client = YouTubeClient(api_key="test-key")
        
        # 大きなレスポンスデータをシミュレート
        response_data = {
            "id": "PERFORMANCE_TEST",
            "status": {
                "uploadStatus": "uploaded",
                "privacyStatus": "public"
            },
            "processingDetails": {
                "processingStatus": "succeeded"
            },
            "snippet": {
                "title": "パフォーマンステスト",
                "description": "説明 " * 1000,
                "tags": ["tag" + str(i) for i in range(100)]
            }
        }
        
        import time
        start_time = time.time()
        
        for _ in range(50):
            client._parse_upload_response(response_data)
        
        end_time = time.time()
        
        # 50回の処理が1秒以内で完了することを確認
        assert end_time - start_time < 1.0 