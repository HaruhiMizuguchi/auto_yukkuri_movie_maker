"""
FileSystemManager - ファイルシステム管理

プロジェクトディレクトリ作成、ファイル操作（作成・削除・移動）、
容量管理・クリーンアップを担当するクラス
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from datetime import datetime, timedelta
import time
import re


class FileSystemError(Exception):
    """ファイルシステム操作関連のエラー"""
    pass


class FileSystemManager:
    """
    ファイルシステム管理クラス
    
    プロジェクトごとのディレクトリ構造の管理、
    ファイル操作、容量管理・クリーンアップを担当
    """
    
    def __init__(self, base_directory: str = "projects"):
        """
        FileSystemManager初期化
        
        Args:
            base_directory: プロジェクトの基本ディレクトリ
        """
        self.base_directory = Path(base_directory)
        self.logger = logging.getLogger(__name__)
        
        # サブディレクトリ構造定義
        self.subdirectories = [
            "files/audio",      # 音声ファイル
            "files/video",      # 動画ファイル
            "files/images",     # 画像ファイル
            "files/scripts",    # スクリプト関連
            "files/metadata",   # メタデータファイル
            "files/temp",       # 一時ファイル
            "files/final",      # 最終ファイル
            "files/backup",     # バックアップファイル
            "files/original",   # オリジナルファイル
            "logs",             # ログファイル
            "cache"             # キャッシュファイル
        ]
        
        # 一時ファイルのパターン
        self.temp_file_patterns = [
            r".*\.tmp$",
            r".*\.temp$",
            r".*\.cache$",
            r"cache/.*",
            r"files/temp/.*"
        ]
        
        # 基本ディレクトリの作成
        self._ensure_base_directory()
    
    def _ensure_base_directory(self):
        """基本ディレクトリが存在することを確認"""
        try:
            self.base_directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileSystemError(f"Failed to create base directory: {str(e)}")
    
    def _validate_project_id(self, project_id: str) -> bool:
        """
        プロジェクトIDの安全性を検証
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: 有効な場合True
            
        Raises:
            FileSystemError: 無効なプロジェクトID
        """
        if not project_id:
            raise FileSystemError("Invalid project ID: empty string")
        
        # 危険な文字やパスの検証
        dangerous_patterns = [
            r"\.\.",      # 親ディレクトリ参照
            r"[/\\]",     # パス区切り文字
            r"[<>:\"|?*]" # Windows禁止文字
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, project_id):
                raise FileSystemError(f"Invalid project ID: contains unsafe characters: {project_id}")
        
        return True
    
    def _validate_file_path(self, file_path: str) -> bool:
        """
        ファイルパスの安全性を検証
        
        Args:
            file_path: ファイルパス
            
        Returns:
            bool: 有効な場合True
            
        Raises:
            FileSystemError: 無効なファイルパス
        """
        # 絶対パスの禁止
        if Path(file_path).is_absolute():
            raise FileSystemError(f"Invalid file path: absolute path not allowed: {file_path}")
        
        # 親ディレクトリ参照の禁止
        if ".." in file_path:
            raise FileSystemError(f"Invalid file path: parent directory reference not allowed: {file_path}")
        
        return True
    
    def _get_project_path(self, project_id: str) -> Path:
        """
        プロジェクトの絶対パスを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Path: プロジェクトディレクトリパス
        """
        self._validate_project_id(project_id)
        return self.base_directory / project_id
    
    # プロジェクトディレクトリ管理
    
    def create_project_directory(self, project_id: str) -> bool:
        """
        プロジェクトディレクトリとサブディレクトリを作成
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: 作成成功時True
            
        Raises:
            FileSystemError: 作成失敗時
        """
        try:
            project_path = self._get_project_path(project_id)
            
            # プロジェクトディレクトリ作成
            project_path.mkdir(parents=True, exist_ok=True)
            
            # サブディレクトリ作成
            for subdir in self.subdirectories:
                subdir_path = project_path / subdir
                subdir_path.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"Project directory created: {project_path}")
            return True
            
        except PermissionError as e:
            error_msg = f"Permission denied creating project directory: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
        except Exception as e:
            error_msg = f"Failed to create project directory {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def get_project_directory_path(self, project_id: str) -> Path:
        """
        プロジェクトディレクトリパスを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Path: プロジェクトディレクトリパス
        """
        return self._get_project_path(project_id)
    
    def delete_project_directory(self, project_id: str) -> bool:
        """
        プロジェクトディレクトリを完全削除
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: 削除成功時True
            
        Raises:
            FileSystemError: 削除失敗時
        """
        try:
            project_path = self._get_project_path(project_id)
            
            if project_path.exists():
                shutil.rmtree(project_path)
                self.logger.info(f"Project directory deleted: {project_path}")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete project directory {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    # ファイル操作
    
    def create_file(
        self, 
        project_id: str, 
        file_path: str, 
        content: Union[str, bytes]
    ) -> bool:
        """
        ファイルを作成
        
        Args:
            project_id: プロジェクトID
            file_path: プロジェクト内での相対ファイルパス
            content: ファイル内容（テキストまたはバイナリ）
            
        Returns:
            bool: 作成成功時True
            
        Raises:
            FileSystemError: 作成失敗時
        """
        try:
            self._validate_file_path(file_path)
            project_path = self._get_project_path(project_id)
            
            if not project_path.exists():
                raise FileSystemError(f"Project directory not found: {project_id}")
            
            full_path = project_path / file_path
            
            # ディレクトリを確保
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイル書き込み
            if isinstance(content, bytes):
                with open(full_path, 'wb') as f:
                    f.write(content)
            else:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            self.logger.debug(f"File created: {full_path}")
            return True
            
        except FileSystemError:
            # FileSystemErrorは再発生
            raise
        except Exception as e:
            error_msg = f"Failed to create file {file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def read_file(self, project_id: str, file_path: str) -> str:
        """
        ファイルを読み込み
        
        Args:
            project_id: プロジェクトID
            file_path: プロジェクト内での相対ファイルパス
            
        Returns:
            str: ファイル内容
            
        Raises:
            FileSystemError: 読み込み失敗時
        """
        try:
            self._validate_file_path(file_path)
            project_path = self._get_project_path(project_id)
            full_path = project_path / file_path
            
            if not full_path.exists():
                raise FileSystemError(f"File not found: {file_path}")
            
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            error_msg = f"Failed to read file {file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def delete_file(self, project_id: str, file_path: str) -> bool:
        """
        ファイルを削除
        
        Args:
            project_id: プロジェクトID
            file_path: プロジェクト内での相対ファイルパス
            
        Returns:
            bool: 削除成功時True
            
        Raises:
            FileSystemError: 削除失敗時
        """
        try:
            self._validate_file_path(file_path)
            project_path = self._get_project_path(project_id)
            full_path = project_path / file_path
            
            if full_path.exists():
                full_path.unlink()
                self.logger.debug(f"File deleted: {full_path}")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete file {file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def move_file(
        self, 
        project_id: str, 
        source_path: str, 
        dest_path: str
    ) -> bool:
        """
        ファイルを移動
        
        Args:
            project_id: プロジェクトID
            source_path: 移動元ファイルパス
            dest_path: 移動先ファイルパス
            
        Returns:
            bool: 移動成功時True
            
        Raises:
            FileSystemError: 移動失敗時
        """
        try:
            self._validate_file_path(source_path)
            self._validate_file_path(dest_path)
            
            project_path = self._get_project_path(project_id)
            source_full_path = project_path / source_path
            dest_full_path = project_path / dest_path
            
            if not source_full_path.exists():
                raise FileSystemError(f"Source file not found: {source_path}")
            
            # 移動先ディレクトリを確保
            dest_full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイル移動
            shutil.move(str(source_full_path), str(dest_full_path))
            
            self.logger.debug(f"File moved: {source_path} -> {dest_path}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to move file {source_path} to {dest_path}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def copy_file(
        self, 
        project_id: str, 
        source_path: str, 
        dest_path: str
    ) -> bool:
        """
        ファイルをコピー
        
        Args:
            project_id: プロジェクトID
            source_path: コピー元ファイルパス
            dest_path: コピー先ファイルパス
            
        Returns:
            bool: コピー成功時True
            
        Raises:
            FileSystemError: コピー失敗時
        """
        try:
            self._validate_file_path(source_path)
            self._validate_file_path(dest_path)
            
            project_path = self._get_project_path(project_id)
            source_full_path = project_path / source_path
            dest_full_path = project_path / dest_path
            
            if not source_full_path.exists():
                raise FileSystemError(f"Source file not found: {source_path}")
            
            # コピー先ディレクトリを確保
            dest_full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイルコピー
            shutil.copy2(str(source_full_path), str(dest_full_path))
            
            self.logger.debug(f"File copied: {source_path} -> {dest_path}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to copy file {source_path} to {dest_path}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    # 容量管理・情報取得
    
    def get_directory_size(self, project_id: str) -> int:
        """
        プロジェクトディレクトリの合計サイズを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            int: ディレクトリサイズ（バイト）
            
        Raises:
            FileSystemError: 計算失敗時
        """
        try:
            project_path = self._get_project_path(project_id)
            
            if not project_path.exists():
                return 0
            
            total_size = 0
            for file_path in project_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            return total_size
            
        except Exception as e:
            error_msg = f"Failed to calculate directory size for {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def get_project_file_list(self, project_id: str) -> List[Dict[str, Any]]:
        """
        プロジェクト内のファイル一覧を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            List[Dict]: ファイル情報のリスト
            
        Raises:
            FileSystemError: 取得失敗時
        """
        try:
            project_path = self._get_project_path(project_id)
            
            if not project_path.exists():
                return []
            
            file_list = []
            for file_path in project_path.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(project_path)
                    stat = file_path.stat()
                    
                    file_info = {
                        "relative_path": str(relative_path).replace("\\", "/"),  # Unix形式に統一
                        "absolute_path": str(file_path),
                        "size": stat.st_size,
                        "modified_time": datetime.fromtimestamp(stat.st_mtime),
                        "created_time": datetime.fromtimestamp(stat.st_ctime)
                    }
                    file_list.append(file_info)
            
            return file_list
            
        except Exception as e:
            error_msg = f"Failed to get file list for {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def get_available_disk_space(self) -> int:
        """
        利用可能なディスク容量を取得
        
        Returns:
            int: 利用可能容量（バイト）
        """
        try:
            stat = shutil.disk_usage(self.base_directory)
            return stat.free
        except Exception as e:
            self.logger.error(f"Failed to get disk space: {str(e)}")
            return 0
    
    def check_disk_space(self, required_size: int) -> bool:
        """
        必要な容量が利用可能かチェック
        
        Args:
            required_size: 必要なサイズ（バイト）
            
        Returns:
            bool: 容量が十分な場合True
        """
        available = self.get_available_disk_space()
        return available >= required_size
    
    # クリーンアップ機能
    
    def cleanup_temporary_files(self, project_id: str) -> int:
        """
        一時ファイルをクリーンアップ
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            int: クリーンアップしたファイル数
            
        Raises:
            FileSystemError: クリーンアップ失敗時
        """
        try:
            project_path = self._get_project_path(project_id)
            
            if not project_path.exists():
                return 0
            
            cleaned_count = 0
            
            for file_path in project_path.rglob('*'):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(project_path))
                    
                    # 一時ファイルパターンのチェック
                    is_temp_file = any(
                        re.match(pattern, relative_path, re.IGNORECASE)
                        for pattern in self.temp_file_patterns
                    )
                    
                    if is_temp_file:
                        try:
                            file_path.unlink()
                            cleaned_count += 1
                            self.logger.debug(f"Temp file deleted: {relative_path}")
                        except Exception as e:
                            self.logger.warning(f"Failed to delete temp file {relative_path}: {str(e)}")
            
            self.logger.info(f"Temporary files cleanup completed: {cleaned_count} files removed")
            return cleaned_count
            
        except Exception as e:
            error_msg = f"Failed to cleanup temporary files for {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)
    
    def cleanup_old_files(self, project_id: str, days: int = 30) -> int:
        """
        指定日数より古いファイルをクリーンアップ
        
        Args:
            project_id: プロジェクトID
            days: 保持日数
            
        Returns:
            int: クリーンアップしたファイル数
            
        Raises:
            FileSystemError: クリーンアップ失敗時
        """
        try:
            project_path = self._get_project_path(project_id)
            
            if not project_path.exists():
                return 0
            
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            cleaned_count = 0
            
            for file_path in project_path.rglob('*'):
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            cleaned_count += 1
                            self.logger.debug(f"Old file deleted: {file_path.relative_to(project_path)}")
                    except Exception as e:
                        self.logger.warning(f"Failed to delete old file {file_path}: {str(e)}")
            
            self.logger.info(f"Old files cleanup completed: {cleaned_count} files removed")
            return cleaned_count
            
        except Exception as e:
            error_msg = f"Failed to cleanup old files for {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)

    def get_project_file_path(self, project_id: str, file_path: str) -> Path:
        """
        プロジェクトファイルの絶対パスを取得
        
        Args:
            project_id: プロジェクトID
            file_path: ファイルパス（プロジェクト相対）
            
        Returns:
            Path: ファイルの絶対パス
            
        Raises:
            FileSystemError: パス取得失敗時
        """
        try:
            if not self._validate_project_id(project_id):
                raise FileSystemError(f"Invalid project ID: {project_id}")
            
            if not self._validate_file_path(file_path):
                raise FileSystemError(f"Invalid file path: {file_path}")
            
            project_path = self._get_project_path(project_id)
            full_path = project_path / Path(file_path).as_posix()
            
            # パスの正規化とセキュリティチェック
            normalized_path = full_path.resolve()
            project_path_resolved = project_path.resolve()
            
            if not str(normalized_path).startswith(str(project_path_resolved)):
                raise FileSystemError(f"Path traversal detected: {file_path}")
            
            return normalized_path
            
        except Exception as e:
            error_msg = f"Failed to get project file path {project_id}/{file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)

    def list_files(self, project_id: str, file_pattern: str = "*") -> List[Dict[str, Any]]:
        """
        プロジェクト内のファイル一覧を取得（パターンマッチング対応）
        
        Args:
            project_id: プロジェクトID
            file_pattern: ファイルパターン（glob形式）
            
        Returns:
            List[Dict]: ファイル情報のリスト
            
        Raises:
            FileSystemError: 取得失敗時
        """
        try:
            if not self._validate_project_id(project_id):
                raise FileSystemError(f"Invalid project ID: {project_id}")
            
            project_path = self._get_project_path(project_id)
            
            if not project_path.exists():
                return []
            
            file_list = []
            for file_path in project_path.rglob(file_pattern):
                if file_path.is_file():
                    relative_path = file_path.relative_to(project_path)
                    stat = file_path.stat()
                    
                    file_info = {
                        "relative_path": str(relative_path).replace("\\", "/"),  # Unix形式に統一
                        "absolute_path": str(file_path),
                        "size": stat.st_size,
                        "modified_time": datetime.fromtimestamp(stat.st_mtime),
                        "created_time": datetime.fromtimestamp(stat.st_ctime)
                    }
                    file_list.append(file_info)
            
            return sorted(file_list, key=lambda x: x["relative_path"])  # パスでソートして返す
            
        except Exception as e:
            error_msg = f"Failed to list files for {project_id} with pattern {file_pattern}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)

    def get_project_directory(self, project_id: str) -> str:
        """
        プロジェクトディレクトリのパスを文字列で取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            str: プロジェクトディレクトリの文字列パス
            
        Raises:
            FileSystemError: パス取得失敗時
        """
        try:
            project_path = self._get_project_path(project_id)
            return str(project_path)
            
        except Exception as e:
            error_msg = f"Failed to get project directory for {project_id}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg)

    def get_file_metadata(self, project_id: str, file_path: str) -> Dict[str, Any]:
        """
        ファイルのメタデータを取得
        
        Args:
            project_id: プロジェクトID
            file_path: ファイルパス（プロジェクト相対）
            
        Returns:
            Dict[str, Any]: ファイルメタデータ
            
        Raises:
            FileSystemError: メタデータ取得失敗時
        """
        try:
            full_path = self.get_project_file_path(project_id, file_path)
            
            if not full_path.exists():
                raise FileSystemError(f"File not found: {file_path}")
            
            stat = full_path.stat()
            
            # ファイル拡張子からMIMEタイプを推定
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(full_path))
            
            metadata = {
                "file_size": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime),
                "created_time": datetime.fromtimestamp(stat.st_ctime),
                "mime_type": mime_type,
                "is_directory": full_path.is_dir(),
                "permissions": oct(stat.st_mode)[-3:] if hasattr(stat, 'st_mode') else "644"
            }
            
            return metadata
            
        except Exception as e:
            error_msg = f"Failed to get file metadata for {project_id}/{file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise FileSystemError(error_msg) 