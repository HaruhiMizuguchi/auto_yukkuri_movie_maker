"""
ログシステム

このモジュールは構造化ログ、ローテーション、外部送信、
パフォーマンス計測を行うLogManagerクラスを提供します。
"""

import os
import json
import logging
import logging.handlers
import traceback
import threading
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, ContextManager
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass
import queue
from collections import defaultdict, deque


class LogManagerError(Exception):
    """ログマネージャー関連のエラー"""
    pass


@dataclass
class LogStats:
    """ログ統計情報"""
    total_logs: int
    by_level: Dict[str, int]
    start_time: datetime
    end_time: datetime


class JsonFormatter(logging.Formatter):
    """JSON形式ログフォーマッター"""
    
    def format(self, record):
        """ログレコードをJSON形式に変換"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # コンテキスト情報があれば追加
        if hasattr(record, 'context'):
            log_entry["context"] = record.context
        
        # 例外情報があれば追加
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, ensure_ascii=False)


class LogManager:
    """
    ログ管理システム
    
    構造化ログ、ローテーション、外部送信、パフォーマンス計測機能を提供します。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        LogManagerを初期化
        
        Args:
            config: ログ設定
            
        Raises:
            LogManagerError: 初期化に失敗した場合
        """
        try:
            # 設定の検証と保存
            self._validate_config(config)
            self.config = config
            
            # 基本設定
            self.log_dir = Path(config["log_dir"])
            self.log_level = self._parse_log_level(config.get("log_level", "INFO"))
            self.json_format = config.get("json_format", True)
            self.console_output = config.get("console_output", True)
            
            # ログディレクトリ作成
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # 統計情報
            self._stats = {
                "total_logs": 0,
                "by_level": defaultdict(int),
                "start_time": datetime.now()
            }
            self._stats_lock = threading.Lock()
            
            # コンテキスト管理
            self._local_context = threading.local()
            
            # 外部ログ送信設定
            self._setup_external_logging()
            
            # ログ履歴（検索用）
            self._log_history = deque(maxlen=1000)  # 最新1000件のログを保持
            
            # ロガーの設定
            self._setup_logger()
            
        except Exception as e:
            raise LogManagerError(f"Failed to initialize LogManager: {str(e)}") from e
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """設定の検証"""
        if "log_dir" not in config:
            raise LogManagerError("log_dir is required in config")
        
        # ログレベルの検証
        if "log_level" in config:
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if config["log_level"] not in valid_levels:
                raise LogManagerError(f"Invalid log_level: {config['log_level']}")
    
    def _parse_log_level(self, level_str: str) -> int:
        """ログレベル文字列を数値に変換"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return level_map.get(level_str.upper(), logging.INFO)
    
    def _setup_external_logging(self) -> None:
        """外部ログ送信の設定"""
        self.external_config = self.config.get("external_logging", {})
        self.external_enabled = self.external_config.get("enabled", False)
        self.webhook_url = self.external_config.get("webhook_url")
        self.external_threshold = self._parse_log_level(
            self.external_config.get("level_threshold", "ERROR")
        )
    
    def _setup_logger(self) -> None:
        """ロガーの設定"""
        # 一意なロガー名を生成して独立性を確保
        import uuid
        unique_logger_name = f"yukkuri_tool_{str(uuid.uuid4())[:8]}"
        
        # メインロガー作成
        self.logger = logging.getLogger(unique_logger_name)
        self.logger.setLevel(self.log_level)
        
        # 既存のハンドラーをクリア
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 親ロガーへの伝播を無効化（独立性確保）
        self.logger.propagate = False
        
        # ファイルハンドラーの設定
        self._setup_file_handler()
        
        # コンソールハンドラーの設定
        if self.console_output:
            self._setup_console_handler()
    
    def _setup_file_handler(self) -> None:
        """ファイルハンドラーの設定"""
        # 複数のLogManagerインスタンスが競合しないよう、一意のファイル名を生成
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        log_file = self.log_dir / f"yukkuri_tool_{unique_id}.log"
        
        # ローテーション設定
        rotation_config = self.config.get("rotation", {})
        max_size = self._parse_file_size(rotation_config.get("max_file_size", "10MB"))
        max_files = rotation_config.get("max_files", 5)
        
        # RotatingFileHandlerを使用
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_size,
            backupCount=max_files,
            encoding='utf-8'
        )
        
        # フォーマッター設定
        if self.json_format:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        file_handler.setFormatter(formatter)
        file_handler.setLevel(self.log_level)  # ハンドラーにもレベル設定
        self.logger.addHandler(file_handler)
    
    def _setup_console_handler(self) -> None:
        """コンソールハンドラーの設定"""
        console_handler = logging.StreamHandler()
        
        if self.json_format:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.log_level)  # ハンドラーにもレベル設定
        self.logger.addHandler(console_handler)
    
    def _parse_file_size(self, size_str: str) -> int:
        """ファイルサイズ文字列をバイト数に変換"""
        size_str = size_str.upper().strip()
        
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def _log_with_context(self, level: int, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """コンテキスト付きログ出力"""
        # 統計更新
        with self._stats_lock:
            self._stats["total_logs"] += 1
            level_name = logging.getLevelName(level)
            self._stats["by_level"][level_name] += 1
        
        # コンテキスト情報を統合
        combined_context = {}
        
        # スレッドローカルコンテキスト
        if hasattr(self._local_context, 'context'):
            combined_context.update(self._local_context.context)
        
        # 引数のコンテキスト
        if context:
            combined_context.update(context)
        
        # ログ記録作成
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        if combined_context:
            log_record.context = combined_context
        
        # ログ履歴に追加
        log_entry = {
            "timestamp": datetime.fromtimestamp(log_record.created),
            "level": logging.getLevelName(level),
            "message": message,
            "context": combined_context
        }
        self._log_history.append(log_entry)
        
        # ログ出力
        self.logger.handle(log_record)
        
        # 外部送信（必要な場合）
        if (self.external_enabled and level >= self.external_threshold):
            self._send_to_external(log_entry)
    
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """DEBUGレベルログ出力"""
        self._log_with_context(logging.DEBUG, message, context)
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """INFOレベルログ出力"""
        self._log_with_context(logging.INFO, message, context)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """WARNINGレベルログ出力"""
        self._log_with_context(logging.WARNING, message, context)
    
    def error(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """ERRORレベルログ出力"""
        self._log_with_context(logging.ERROR, message, context)
    
    def critical(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """CRITICALレベルログ出力"""
        self._log_with_context(logging.CRITICAL, message, context)
    
    def log_exception(self, message: str, exception: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """例外情報付きログ出力"""
        combined_context = context or {}
        combined_context["exception"] = {
            "type": exception.__class__.__name__,
            "message": str(exception),
            "traceback": traceback.format_exc().split('\n')
        }
        
        self.error(message, combined_context)
    
    def log_api_call(self, api_name: str, endpoint: str, method: str, 
                     status_code: int, request_size: int = 0, 
                     response_size: int = 0, duration_ms: float = 0) -> None:
        """API呼び出し情報のログ記録"""
        context = {
            "api_name": api_name,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "request_size": request_size,
            "response_size": response_size,
            "duration_ms": duration_ms,
            "category": "api_call"
        }
        
        self.info(f"API呼び出し: {api_name} {method} {endpoint}", context)
    
    @contextmanager
    def measure_time(self, operation_name: str, context: Optional[Dict[str, Any]] = None):
        """処理時間計測のコンテキストマネージャー"""
        start_time = time.time()
        
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            measurement_context = {"operation": operation_name, "duration_ms": duration_ms}
            if context:
                measurement_context.update(context)
            
            self.info(f"処理完了: {operation_name}", measurement_context)
    
    @contextmanager
    def operation_context(self, operation: str, **kwargs):
        """操作コンテキストの設定"""
        # 既存のコンテキストを保存
        previous_context = getattr(self._local_context, 'context', {})
        
        # 新しいコンテキストを設定
        new_context = previous_context.copy()
        new_context.update({"operation": operation, **kwargs})
        self._local_context.context = new_context
        
        try:
            yield
        finally:
            # コンテキストを復元
            self._local_context.context = previous_context
    
    def _send_to_external(self, log_entry: Dict[str, Any]) -> None:
        """外部システムへのログ送信"""
        if not self.webhook_url:
            return
        
        try:
            # タイムスタンプをISO形式に変換
            log_data = log_entry.copy()
            log_data["timestamp"] = log_entry["timestamp"].isoformat()
            
            response = requests.post(
                self.webhook_url,
                json=log_data,
                timeout=5  # 5秒でタイムアウト
            )
            response.raise_for_status()
            
        except Exception as e:
            # 外部送信エラーはローカルログにのみ記録（無限ループ回避）
            error_msg = f"Failed to send log to external system: {str(e)}"
            self.logger.error(error_msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """ログ統計情報を取得"""
        with self._stats_lock:
            return {
                "total_logs": self._stats["total_logs"],
                "by_level": dict(self._stats["by_level"]),
                "start_time": self._stats["start_time"],
                "end_time": datetime.now()
            }
    
    def search_logs(self, start_time: datetime, end_time: datetime,
                    level: Optional[str] = None, message_contains: Optional[str] = None) -> List[Dict[str, Any]]:
        """ログ検索"""
        results = []
        
        for log_entry in self._log_history:
            # 時間範囲チェック
            if not (start_time <= log_entry["timestamp"] <= end_time):
                continue
            
            # レベルチェック
            if level and log_entry["level"] != level:
                continue
            
            # メッセージ検索
            if message_contains and message_contains not in log_entry["message"]:
                continue
            
            # タイムスタンプをISO形式に変換してコピー
            result = log_entry.copy()
            result["timestamp"] = log_entry["timestamp"].isoformat()
            results.append(result)
        
        return results
    
    def clear_stats(self) -> None:
        """統計情報をクリア"""
        with self._stats_lock:
            self._stats = {
                "total_logs": 0,
                "by_level": defaultdict(int),
                "start_time": datetime.now()
            }
    
    def get_log_files(self) -> List[Path]:
        """ログファイル一覧を取得"""
        return list(self.log_dir.glob("*.log*"))
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """古いログファイルのクリーンアップ"""
        cutoff_time = datetime.now() - timedelta(days=days)
        cleaned_count = 0
        
        for log_file in self.get_log_files():
            if log_file.stat().st_mtime < cutoff_time.timestamp():
                try:
                    log_file.unlink()
                    cleaned_count += 1
                except Exception as e:
                    self.warning(f"Failed to delete log file {log_file}: {str(e)}")
        
        return cleaned_count 