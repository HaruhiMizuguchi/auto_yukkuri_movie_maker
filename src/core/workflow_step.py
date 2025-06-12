"""
ワークフロー ステップ管理システム

このモジュールは、ワークフローステップの抽象インターフェース、
データ構造、および実行状態管理を提供します。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime
import json


class StepStatus(Enum):
    """ステップ実行状態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class StepPriority(Enum):
    """ステップ優先度"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class StepExecutionContext:
    """ステップ実行コンテキスト"""
    project_id: str
    step_name: str
    execution_id: str
    started_at: Optional[datetime] = None
    user_context: Dict[str, Any] = field(default_factory=dict)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    resource_limits: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """ステップ実行結果"""
    status: StepStatus
    output_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)  # 生成されたファイルパス
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "status": self.status.value,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "execution_time_seconds": self.execution_time_seconds,
            "resource_usage": self.resource_usage,
            "artifacts": self.artifacts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StepResult':
        """辞書から復元"""
        return cls(
            status=StepStatus(data["status"]),
            output_data=data.get("output_data", {}),
            error_message=data.get("error_message"),
            execution_time_seconds=data.get("execution_time_seconds"),
            resource_usage=data.get("resource_usage", {}),
            artifacts=data.get("artifacts", [])
        )


@dataclass
class WorkflowStepDefinition:
    """ワークフローステップ定義"""
    step_id: int
    step_name: str
    display_name: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    priority: StepPriority = StepPriority.NORMAL
    timeout_seconds: Optional[int] = None
    retry_count: int = 3
    can_skip: bool = False
    can_run_parallel: bool = False
    required_resources: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """初期化後の検証"""
        if self.step_id < 1:
            raise ValueError("step_id must be positive")
        if not self.step_name:
            raise ValueError("step_name cannot be empty")
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative")


class StepProcessor(ABC):
    """ステッププロセッサ抽象インターフェース"""
    
    @abstractmethod
    def execute(
        self,
        context: StepExecutionContext,
        input_data: Dict[str, Any]
    ) -> StepResult:
        """
        ステップを実行
        
        Args:
            context: 実行コンテキスト
            input_data: 入力データ
            
        Returns:
            StepResult: 実行結果
            
        Raises:
            StepExecutionError: 実行失敗時
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        入力データを検証
        
        Args:
            input_data: 検証対象の入力データ
            
        Returns:
            bool: 検証成功時True
            
        Raises:
            ValidationError: 検証失敗時
        """
        pass
    
    @abstractmethod
    def get_required_dependencies(self) -> List[str]:
        """
        必要な依存関係を取得
        
        Returns:
            List[str]: 依存するステップ名のリスト
        """
        pass
    
    @abstractmethod
    def can_run_concurrently_with(self, other_step: str) -> bool:
        """
        他のステップと並列実行可能かチェック
        
        Args:
            other_step: 他のステップ名
            
        Returns:
            bool: 並列実行可能時True
        """
        pass
    
    @abstractmethod
    def estimate_execution_time(self, input_data: Dict[str, Any]) -> float:
        """
        実行時間を推定
        
        Args:
            input_data: 入力データ
            
        Returns:
            float: 推定実行時間（秒）
        """
        pass


class DependencyResolver(ABC):
    """依存関係解決インターフェース"""
    
    @abstractmethod
    def resolve_execution_order(
        self,
        steps: List[WorkflowStepDefinition]
    ) -> List[List[str]]:
        """
        実行順序を解決
        
        Args:
            steps: ステップ定義リスト
            
        Returns:
            List[List[str]]: 実行フェーズ別のステップ名リスト
                           内側のリストは並列実行可能
            
        Raises:
            DependencyError: 循環依存等の解決不可能時
        """
        pass
    
    @abstractmethod
    def check_dependencies_satisfied(
        self,
        step_name: str,
        completed_steps: Set[str]
    ) -> bool:
        """
        依存関係が満たされているかチェック
        
        Args:
            step_name: チェック対象ステップ名
            completed_steps: 完了済みステップ集合
            
        Returns:
            bool: 依存関係が満たされている時True
        """
        pass
    
    @abstractmethod
    def find_circular_dependencies(
        self,
        steps: List[WorkflowStepDefinition]
    ) -> List[List[str]]:
        """
        循環依存を検出
        
        Args:
            steps: ステップ定義リスト
            
        Returns:
            List[List[str]]: 検出された循環依存チェーンのリスト
        """
        pass


class ResourceManager(ABC):
    """リソース管理インターフェース"""
    
    @abstractmethod
    def acquire_resources(
        self,
        resource_names: Set[str],
        timeout_seconds: Optional[int] = None
    ) -> bool:
        """
        リソースを取得
        
        Args:
            resource_names: 取得するリソース名集合
            timeout_seconds: タイムアウト時間
            
        Returns:
            bool: 取得成功時True
        """
        pass
    
    @abstractmethod
    def release_resources(self, resource_names: Set[str]) -> None:
        """
        リソースを解放
        
        Args:
            resource_names: 解放するリソース名集合
        """
        pass
    
    @abstractmethod
    def is_resource_available(self, resource_name: str) -> bool:
        """
        リソースが利用可能かチェック
        
        Args:
            resource_name: リソース名
            
        Returns:
            bool: 利用可能時True
        """
        pass
    
    @abstractmethod
    def get_resource_usage(self) -> Dict[str, Any]:
        """
        リソース使用状況を取得
        
        Returns:
            Dict[str, Any]: リソース使用状況
        """
        pass 