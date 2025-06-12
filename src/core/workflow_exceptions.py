"""
ワークフローエンジン例外定義

このモジュールは、ワークフローエンジン全体で使用される
統一された例外階層とエラーハンドリング機能を提供します。
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import traceback
from datetime import datetime


class ErrorSeverity(Enum):
    """エラー重要度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """エラーカテゴリ"""
    VALIDATION = "validation"
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    EXECUTION = "execution"
    NETWORK = "network"
    IO = "io"
    CONFIGURATION = "configuration"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    EXTERNAL_API = "external_api"


class RecoveryAction(Enum):
    """復旧アクション"""
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    MANUAL_INTERVENTION = "manual_intervention"
    ABORT = "abort"


class WorkflowEngineError(Exception):
    """ワークフローエンジン基底例外"""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        recoverable: bool = True,
        suggested_actions: Optional[List[RecoveryAction]] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.recoverable = recoverable
        self.suggested_actions = suggested_actions or []
        self.context = context or {}
        self.cause = cause
        self.timestamp = datetime.now()
        self.stack_trace = traceback.format_exc() if cause else None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "message": self.message,
            "error_code": self.error_code,
            "category": self.category.value,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "suggested_actions": [action.value for action in self.suggested_actions],
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace,
            "cause": str(self.cause) if self.cause else None
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class StepExecutionError(WorkflowEngineError):
    """ステップ実行エラー"""
    
    def __init__(
        self,
        step_name: str,
        message: str,
        error_code: str = "STEP_EXECUTION_FAILED",
        phase: str = "execution",
        cause: Optional[Exception] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        context.update({
            "step_name": step_name,
            "execution_phase": phase
        })
        kwargs['context'] = context
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.EXECUTION,
            cause=cause,
            **kwargs
        )
        self.step_name = step_name
        self.phase = phase


class DependencyError(WorkflowEngineError):
    """依存関係エラー"""
    
    def __init__(
        self,
        step_name: str,
        missing_dependencies: List[str],
        message: Optional[str] = None,
        error_code: str = "DEPENDENCY_NOT_SATISFIED",
        **kwargs
    ):
        if message is None:
            message = f"Step '{step_name}' dependencies not satisfied: {missing_dependencies}"
        
        context = kwargs.get('context', {})
        context.update({
            "step_name": step_name,
            "missing_dependencies": missing_dependencies
        })
        kwargs['context'] = context
        kwargs.setdefault('suggested_actions', [RecoveryAction.RETRY, RecoveryAction.SKIP])
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.DEPENDENCY,
            **kwargs
        )
        self.step_name = step_name
        self.missing_dependencies = missing_dependencies


class CircularDependencyError(DependencyError):
    """循環依存エラー"""
    
    def __init__(
        self,
        dependency_chain: List[str],
        message: Optional[str] = None,
        **kwargs
    ):
        if message is None:
            message = f"Circular dependency detected: {' -> '.join(dependency_chain)}"
        
        kwargs.setdefault('error_code', "CIRCULAR_DEPENDENCY")
        kwargs.setdefault('recoverable', False)
        kwargs.setdefault('severity', ErrorSeverity.CRITICAL)
        kwargs.setdefault('suggested_actions', [RecoveryAction.MANUAL_INTERVENTION])
        
        context = kwargs.get('context', {})
        context.update({"dependency_chain": dependency_chain})
        kwargs['context'] = context
        
        super().__init__(
            step_name=dependency_chain[0] if dependency_chain else "unknown",
            missing_dependencies=[],
            message=message,
            **kwargs
        )
        self.dependency_chain = dependency_chain


class ResourceLimitError(WorkflowEngineError):
    """リソース制限エラー"""
    
    def __init__(
        self,
        resource_name: str,
        requested_amount: Any,
        available_amount: Any,
        message: Optional[str] = None,
        error_code: str = "RESOURCE_LIMIT_EXCEEDED",
        **kwargs
    ):
        if message is None:
            message = f"Resource '{resource_name}' limit exceeded: requested {requested_amount}, available {available_amount}"
        
        context = kwargs.get('context', {})
        context.update({
            "resource_name": resource_name,
            "requested_amount": requested_amount,
            "available_amount": available_amount
        })
        kwargs['context'] = context
        kwargs.setdefault('suggested_actions', [RecoveryAction.RETRY, RecoveryAction.FALLBACK])
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.RESOURCE,
            **kwargs
        )
        self.resource_name = resource_name
        self.requested_amount = requested_amount
        self.available_amount = available_amount


class ResourceUnavailableError(ResourceLimitError):
    """リソース利用不可エラー"""
    
    def __init__(
        self,
        resource_name: str,
        reason: str = "Resource is currently unavailable",
        **kwargs
    ):
        kwargs.setdefault('error_code', "RESOURCE_UNAVAILABLE")
        super().__init__(
            resource_name=resource_name,
            requested_amount="any",
            available_amount=0,
            message=f"Resource '{resource_name}' is unavailable: {reason}",
            **kwargs
        )
        self.reason = reason


class ValidationError(WorkflowEngineError):
    """データ検証エラー"""
    
    def __init__(
        self,
        field_name: str,
        value: Any,
        validation_rule: str,
        message: Optional[str] = None,
        error_code: str = "VALIDATION_FAILED",
        **kwargs
    ):
        if message is None:
            message = f"Validation failed for field '{field_name}': {validation_rule}"
        
        context = kwargs.get('context', {})
        context.update({
            "field_name": field_name,
            "value": str(value),
            "validation_rule": validation_rule
        })
        kwargs['context'] = context
        kwargs.setdefault('suggested_actions', [RecoveryAction.MANUAL_INTERVENTION])
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )
        self.field_name = field_name
        self.value = value
        self.validation_rule = validation_rule


class TimeoutError(WorkflowEngineError):
    """タイムアウトエラー"""
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        elapsed_seconds: float,
        message: Optional[str] = None,
        error_code: str = "OPERATION_TIMEOUT",
        **kwargs
    ):
        if message is None:
            message = f"Operation '{operation}' timed out after {elapsed_seconds:.1f}s (limit: {timeout_seconds}s)"
        
        context = kwargs.get('context', {})
        context.update({
            "operation": operation,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": elapsed_seconds
        })
        kwargs['context'] = context
        kwargs.setdefault('suggested_actions', [RecoveryAction.RETRY, RecoveryAction.FALLBACK])
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.TIMEOUT,
            **kwargs
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds


class ExternalAPIError(WorkflowEngineError):
    """外部API エラー"""
    
    def __init__(
        self,
        api_name: str,
        http_status: Optional[int] = None,
        api_error_code: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "EXTERNAL_API_ERROR",
        **kwargs
    ):
        if message is None:
            status_text = f" (HTTP {http_status})" if http_status else ""
            api_code_text = f" - {api_error_code}" if api_error_code else ""
            message = f"External API '{api_name}' error{status_text}{api_code_text}"
        
        context = kwargs.get('context', {})
        context.update({
            "api_name": api_name,
            "http_status": http_status,
            "api_error_code": api_error_code
        })
        kwargs['context'] = context
        kwargs.setdefault('suggested_actions', [RecoveryAction.RETRY, RecoveryAction.FALLBACK])
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.EXTERNAL_API,
            **kwargs
        )
        self.api_name = api_name
        self.http_status = http_status
        self.api_error_code = api_error_code


class ConfigurationError(WorkflowEngineError):
    """設定エラー"""
    
    def __init__(
        self,
        config_key: str,
        expected_type: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "CONFIGURATION_ERROR",
        **kwargs
    ):
        if message is None:
            type_text = f" (expected {expected_type})" if expected_type else ""
            message = f"Configuration error for key '{config_key}'{type_text}"
        
        context = kwargs.get('context', {})
        context.update({
            "config_key": config_key,
            "expected_type": expected_type
        })
        kwargs['context'] = context
        kwargs.setdefault('recoverable', False)
        kwargs.setdefault('suggested_actions', [RecoveryAction.MANUAL_INTERVENTION])
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.CONFIGURATION,
            **kwargs
        )
        self.config_key = config_key
        self.expected_type = expected_type


class RecoveryError(WorkflowEngineError):
    """復旧処理エラー"""
    
    def __init__(
        self,
        recovery_action: RecoveryAction,
        original_error: WorkflowEngineError,
        message: Optional[str] = None,
        error_code: str = "RECOVERY_FAILED",
        **kwargs
    ):
        if message is None:
            message = f"Recovery action '{recovery_action.value}' failed for error: {original_error.message}"
        
        context = kwargs.get('context', {})
        context.update({
            "recovery_action": recovery_action.value,
            "original_error_code": original_error.error_code,
            "original_error_message": original_error.message
        })
        kwargs['context'] = context
        kwargs.setdefault('severity', ErrorSeverity.CRITICAL)
        kwargs.setdefault('recoverable', False)
        kwargs.setdefault('suggested_actions', [RecoveryAction.MANUAL_INTERVENTION])
        
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.EXECUTION,
            **kwargs
        )
        self.recovery_action = recovery_action
        self.original_error = original_error


# エラーハンドリングユーティリティ関数

def create_error_context(
    project_id: Optional[str] = None,
    step_name: Optional[str] = None,
    execution_id: Optional[str] = None,
    **additional_context
) -> Dict[str, Any]:
    """エラーコンテキストを作成"""
    context = {}
    if project_id:
        context["project_id"] = project_id
    if step_name:
        context["step_name"] = step_name
    if execution_id:
        context["execution_id"] = execution_id
    context.update(additional_context)
    return context


def is_recoverable_error(error: Exception) -> bool:
    """エラーが復旧可能かチェック"""
    if isinstance(error, WorkflowEngineError):
        return error.recoverable
    
    # その他の一般的な例外の判定
    non_recoverable_types = (
        KeyboardInterrupt,
        SystemExit,
        MemoryError,
        SyntaxError,
        ImportError
    )
    
    return not isinstance(error, non_recoverable_types)


def get_suggested_recovery_actions(error: Exception) -> List[RecoveryAction]:
    """推奨復旧アクションを取得"""
    if isinstance(error, WorkflowEngineError):
        return error.suggested_actions
    
    # 一般的な例外に対するデフォルトアクション
    if isinstance(error, (ConnectionError, TimeoutError)):
        return [RecoveryAction.RETRY]
    elif isinstance(error, FileNotFoundError):
        return [RecoveryAction.FALLBACK, RecoveryAction.MANUAL_INTERVENTION]
    elif isinstance(error, PermissionError):
        return [RecoveryAction.MANUAL_INTERVENTION]
    else:
        return [RecoveryAction.RETRY, RecoveryAction.MANUAL_INTERVENTION] 