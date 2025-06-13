"""
YouTube API クライアント

YouTube Data API v3 を使用した動画アップロード、
メタデータ設定、サムネイル管理などの機能を提供します。
"""

import asyncio
import aiohttp
import aiofiles
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
from datetime import datetime
import json

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


class VideoPrivacy(Enum):
    """動画プライバシー設定"""
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class VideoCategory(Enum):
    """動画カテゴリ"""
    ENTERTAINMENT = "24"  # エンターテイメント
    EDUCATION = "27"      # 教育
    GAMING = "20"         # ゲーム
    MUSIC = "10"          # 音楽
    SCIENCE_TECH = "28"   # 科学技術
    PEOPLE_BLOGS = "22"   # ブログ
    NEWS_POLITICS = "25"  # ニュース・政治
    COMEDY = "23"         # コメディ


@dataclass
class VideoMetadata:
    """動画メタデータ"""
    title: str
    description: str
    privacy: VideoPrivacy = VideoPrivacy.PRIVATE
    category: VideoCategory = VideoCategory.ENTERTAINMENT
    tags: List[str] = None
    language: str = "ja"
    thumbnail_url: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class VideoUploadRequest:
    """動画アップロードリクエストデータ"""
    video_file_path: str
    metadata: VideoMetadata
    notify_subscribers: bool = True
    enable_auto_chapters: bool = False
    schedule_publish_at: Optional[datetime] = None


@dataclass
class VideoUploadResponse:
    """動画アップロードレスポンスデータ"""
    video_id: str
    upload_status: str
    video_url: str
    processing_status: str
    privacy_status: str = "private"
    upload_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.upload_metadata is None:
            self.upload_metadata = {}
    
    @property
    def is_upload_complete(self) -> bool:
        """アップロード完了判定"""
        return (
            self.upload_status == "uploaded" and 
            self.processing_status in ["succeeded", "completed"]
        )
    
    @property
    def is_published(self) -> bool:
        """公開状態判定"""
        return self.privacy_status == "public"


@dataclass
class ThumbnailRequest:
    """サムネイルアップロードリクエストデータ"""
    video_id: str
    thumbnail_file_path: str


@dataclass
class ThumbnailResponse:
    """サムネイルアップロードレスポンスデータ"""
    video_id: str
    thumbnail_url: str
    upload_status: str
    upload_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.upload_metadata is None:
            self.upload_metadata = {}


class YouTubeAPIError(APIClientError):
    """YouTube API固有のエラー"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "YOUTUBE_API_ERROR",
        video_id: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        context.update({"video_id": video_id})
        kwargs['context'] = context
        
        super().__init__(message, error_code, **kwargs)
        self.video_id = video_id


class VideoUploadError(YouTubeAPIError):
    """動画アップロードエラー"""
    
    def __init__(self, message: str, video_id: Optional[str], video_file_path: str):
        super().__init__(
            message,
            error_code="VIDEO_UPLOAD_ERROR",
            video_id=video_id,
            context={"video_file_path": video_file_path}
        )
        self.video_file_path = video_file_path


class ThumbnailUploadError(YouTubeAPIError):
    """サムネイルアップロードエラー"""
    
    def __init__(self, message: str, video_id: str, thumbnail_file_path: str):
        super().__init__(
            message,
            error_code="THUMBNAIL_UPLOAD_ERROR",
            video_id=video_id,
            context={"thumbnail_file_path": thumbnail_file_path}
        )
        self.thumbnail_file_path = thumbnail_file_path


class QuotaExceededError(YouTubeAPIError):
    """クォータ超過エラー"""
    
    def __init__(self, message: str, quota_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            error_code="QUOTA_EXCEEDED",
            retry_recommended=False,
            context={"quota_info": quota_info}
        )
        self.quota_info = quota_info


class YouTubeClient(BaseAPIClient):
    """YouTube API クライアント"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        oauth_token: Optional[str] = None,
        oauth_refresh_token: Optional[str] = None,
        base_url: str = "https://www.googleapis.com/youtube/v3",
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        # YouTube API の制限に合わせた設定
        if rate_limit_config is None:
            rate_limit_config = RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=1000,
                burst_limit=10
            )
        
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            retry_config=retry_config,
            rate_limit_config=rate_limit_config,
            logger=logger
        )
        
        self.oauth_token = oauth_token
        self.oauth_refresh_token = oauth_refresh_token
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTPセッション取得"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=600)  # アップロードは時間がかかる
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def send_request(self, request: APIRequest) -> APIResponse:
        """リクエスト送信の具体実装"""
        session = await self._get_session()
        
        url = f"{self.base_url}{request.endpoint}"
        headers = {
            "Accept": "application/json",
            **(request.headers or {})
        }
        
        # 認証ヘッダー設定
        if self.oauth_token:
            headers["Authorization"] = f"Bearer {self.oauth_token}"
        elif self.api_key:
            # クエリパラメータでAPI key指定
            params = request.params or {}
            params["key"] = self.api_key
            request = request._replace(params=params)
        
        try:
            async with session.request(
                method=request.method,
                url=url,
                headers=headers,
                params=request.params,
                json=request.data if request.method != "POST" or not hasattr(request, '_multipart_data') else None,
                data=getattr(request, '_multipart_data', None),
                timeout=request.timeout
            ) as response:
                response_headers = dict(response.headers)
                
                if response.content_type == "application/json":
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
    
    def _build_video_metadata(self, metadata: VideoMetadata) -> Dict[str, Any]:
        """動画メタデータ構築"""
        return {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category.value,
                "defaultLanguage": metadata.language
            },
            "status": {
                "privacyStatus": metadata.privacy.value,
                "selfDeclaredMadeForKids": False
            }
        }
    
    def _build_upload_request_data(self, upload_request: VideoUploadRequest) -> Dict[str, Any]:
        """アップロードリクエストデータ構築"""
        data = self._build_video_metadata(upload_request.metadata)
        
        # アップロード固有設定
        if not upload_request.notify_subscribers:
            data["status"]["publishAt"] = None
        
        if upload_request.schedule_publish_at:
            data["status"]["publishAt"] = upload_request.schedule_publish_at.isoformat()
        
        return data
    
    def _parse_upload_response(self, response_data: Dict[str, Any]) -> VideoUploadResponse:
        """アップロードレスポンス解析"""
        video_id = response_data.get("id")
        if not video_id:
            raise YouTubeAPIError("Video ID not found in response")
        
        status = response_data.get("status", {})
        processing_details = response_data.get("processingDetails", {})
        
        return VideoUploadResponse(
            video_id=video_id,
            upload_status=status.get("uploadStatus", "unknown"),
            video_url=f"https://youtube.com/watch?v={video_id}",
            processing_status=processing_details.get("processingStatus", "unknown"),
            privacy_status=status.get("privacyStatus", "private"),
            upload_metadata={
                "upload_time": datetime.now().isoformat(),
                "raw_response": response_data
            }
        )
    
    async def upload_video(self, upload_request: VideoUploadRequest) -> VideoUploadResponse:
        """動画アップロード"""
        # ファイル存在確認
        video_path = Path(upload_request.video_file_path)
        if not video_path.exists():
            raise VideoUploadError(
                f"Video file not found: {upload_request.video_file_path}",
                None,
                upload_request.video_file_path
            )
        
        # メタデータ構築
        metadata = self._build_upload_request_data(upload_request)
        
        # マルチパートデータ準備
        async with aiofiles.open(video_path, 'rb') as video_file:
            video_data = await video_file.read()
        
        # APIリクエスト作成
        api_request = APIRequest(
            endpoint="/videos",
            method="POST",
            params={
                "part": "snippet,status,processingDetails",
                "uploadType": "multipart"
            },
            headers={
                "Content-Type": "application/json"
            },
            data=metadata,
            timeout=600
        )
        
        # マルチパートデータを設定（簡略化）
        setattr(api_request, '_multipart_data', {
            'metadata': json.dumps(metadata),
            'media': video_data
        })
        
        response = await self.send_request_with_retry(api_request)
        
        if not response.is_success:
            # エラー詳細解析
            if response.status_code == 403:
                error_data = response.data
                if isinstance(error_data, dict) and "error" in error_data:
                    error_details = error_data["error"]
                    if any(err.get("reason") == "quotaExceeded" for err in error_details.get("errors", [])):
                        raise QuotaExceededError(
                            "YouTube API quota exceeded",
                            {"daily_limit": 10000, "current_usage": "unknown"}
                        )
            
            raise VideoUploadError(
                f"Failed to upload video: HTTP {response.status_code}",
                None,
                upload_request.video_file_path
            )
        
        return self._parse_upload_response(response.data)
    
    async def upload_thumbnail(self, thumbnail_request: ThumbnailRequest) -> ThumbnailResponse:
        """サムネイルアップロード"""
        # ファイル存在確認
        thumbnail_path = Path(thumbnail_request.thumbnail_file_path)
        if not thumbnail_path.exists():
            raise ThumbnailUploadError(
                f"Thumbnail file not found: {thumbnail_request.thumbnail_file_path}",
                thumbnail_request.video_id,
                thumbnail_request.thumbnail_file_path
            )
        
        # サムネイルデータ読み込み
        async with aiofiles.open(thumbnail_path, 'rb') as thumb_file:
            thumbnail_data = await thumb_file.read()
        
        # APIリクエスト作成
        api_request = APIRequest(
            endpoint=f"/thumbnails/set",
            method="POST",
            params={"videoId": thumbnail_request.video_id},
            headers={
                "Content-Type": "image/jpeg"
            },
            timeout=300
        )
        
        # サムネイルデータを設定
        setattr(api_request, '_multipart_data', thumbnail_data)
        
        response = await self.send_request_with_retry(api_request)
        
        if not response.is_success:
            raise ThumbnailUploadError(
                f"Failed to upload thumbnail: HTTP {response.status_code}",
                thumbnail_request.video_id,
                thumbnail_request.thumbnail_file_path
            )
        
        # レスポンス解析
        data = response.data
        if isinstance(data, dict) and "items" in data and data["items"]:
            thumbnail_info = data["items"][0]
            # 高品質サムネイルURLを取得
            thumbnail_url = thumbnail_info.get("high", {}).get("url", "")
            if not thumbnail_url:
                thumbnail_url = thumbnail_info.get("default", {}).get("url", "")
        else:
            thumbnail_url = f"https://i.ytimg.com/vi/{thumbnail_request.video_id}/hqdefault.jpg"
        
        return ThumbnailResponse(
            video_id=thumbnail_request.video_id,
            thumbnail_url=thumbnail_url,
            upload_status="uploaded",
            upload_metadata={
                "upload_time": datetime.now().isoformat(),
                "file_path": thumbnail_request.thumbnail_file_path
            }
        )
    
    async def get_video_status(self, video_id: str) -> VideoUploadResponse:
        """動画ステータス取得"""
        api_request = APIRequest(
            endpoint="/videos",
            method="GET",
            params={
                "part": "snippet,status,processingDetails",
                "id": video_id
            }
        )
        
        response = await self.send_request_with_retry(api_request)
        
        if not response.is_success:
            raise YouTubeAPIError(f"Failed to get video status: HTTP {response.status_code}")
        
        data = response.data
        if not isinstance(data, dict) or "items" not in data or not data["items"]:
            raise YouTubeAPIError(f"Video not found: {video_id}")
        
        video_info = data["items"][0]
        return self._parse_upload_response(video_info)
    
    async def batch_upload_videos(
        self,
        upload_requests: List[VideoUploadRequest]
    ) -> List[VideoUploadResponse]:
        """バッチ動画アップロード"""
        responses = []
        
        for request in upload_requests:
            try:
                response = await self.upload_video(request)
                responses.append(response)
            except Exception as e:
                self.logger.error(f"Failed to upload video '{request.video_file_path}': {e}")
                # エラーでも続行（空のレスポンスは追加しない）
                continue
        
        return responses
    
    async def update_video_metadata(
        self,
        video_id: str,
        metadata: VideoMetadata
    ) -> VideoUploadResponse:
        """動画メタデータ更新"""
        data = self._build_video_metadata(metadata)
        data["id"] = video_id
        
        api_request = APIRequest(
            endpoint="/videos",
            method="PUT",
            params={"part": "snippet,status"},
            data=data
        )
        
        response = await self.send_request_with_retry(api_request)
        
        if not response.is_success:
            raise YouTubeAPIError(
                f"Failed to update video metadata: HTTP {response.status_code}",
                video_id=video_id
            )
        
        return self._parse_upload_response(response.data)
    
    async def close(self):
        """リソースクリーンアップ"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 