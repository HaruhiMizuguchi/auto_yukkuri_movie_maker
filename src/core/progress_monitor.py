"""
進捗監視システム

ワークフローの進捗をリアルタイムで監視し、
WebSocket/SSE経由での配信と詳細レポート機能を提供します。
"""

import asyncio
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
import uuid
from abc import ABC, abstractmethod

from .workflow_engine import WorkflowExecutionState


class ProgressEventType(Enum):
    """進捗イベントタイプ"""
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    
    PROGRESS_UPDATE = "progress_update"
    TIME_ESTIMATE_UPDATE = "time_estimate_update"
    RESOURCE_UPDATE = "resource_update"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class ProgressEvent:
    """進捗イベント"""
    event_type: ProgressEventType
    project_id: str
    workflow_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    step_name: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "project_id": self.project_id,
            "workflow_name": self.workflow_name,
            "step_name": self.step_name,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }
    
    def to_json(self) -> str:
        """JSON形式に変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ProgressSubscriber(ABC):
    """進捗通知の購読者インターフェース"""
    
    @abstractmethod
    async def on_progress_event(self, event: ProgressEvent) -> None:
        """進捗イベント受信"""
        pass
    
    @abstractmethod
    def get_subscriber_id(self) -> str:
        """購読者ID取得"""
        pass
    
    @abstractmethod
    async def is_active(self) -> bool:
        """アクティブ状態確認"""
        pass


class WebSocketSubscriber(ProgressSubscriber):
    """WebSocket購読者"""
    
    def __init__(self, websocket, subscriber_id: str, project_filter: Optional[Set[str]] = None):
        self.websocket = websocket
        self.subscriber_id = subscriber_id
        self.project_filter = project_filter  # 特定プロジェクトのみフィルタ
        self.last_activity = datetime.now()
        
    async def on_progress_event(self, event: ProgressEvent) -> None:
        """進捗イベント送信"""
        try:
            # プロジェクトフィルタチェック
            if self.project_filter and event.project_id not in self.project_filter:
                return
            
            await self.websocket.send_text(event.to_json())
            self.last_activity = datetime.now()
        except Exception as e:
            logging.error(f"WebSocket send error: {e}")
    
    def get_subscriber_id(self) -> str:
        return self.subscriber_id
    
    async def is_active(self) -> bool:
        """WebSocket接続状態確認"""
        try:
            # 簡単なpingテスト
            await self.websocket.ping()
            return True
        except:
            return False


class SSESubscriber(ProgressSubscriber):
    """Server-Sent Events購読者"""
    
    def __init__(self, response_writer, subscriber_id: str, project_filter: Optional[Set[str]] = None):
        self.response_writer = response_writer
        self.subscriber_id = subscriber_id
        self.project_filter = project_filter
        self.last_activity = datetime.now()
        self.is_connected = True
        
    async def on_progress_event(self, event: ProgressEvent) -> None:
        """SSEイベント送信"""
        try:
            # プロジェクトフィルタチェック
            if self.project_filter and event.project_id not in self.project_filter:
                return
            
            sse_data = f"data: {event.to_json()}\n\n"
            await self.response_writer.write(sse_data.encode())
            self.last_activity = datetime.now()
        except Exception as e:
            logging.error(f"SSE send error: {e}")
            self.is_connected = False
    
    def get_subscriber_id(self) -> str:
        return self.subscriber_id
    
    async def is_active(self) -> bool:
        return self.is_connected


@dataclass
class DetailedProgressReport:
    """詳細進捗レポート"""
    project_id: str
    workflow_name: str
    generated_at: datetime = field(default_factory=datetime.now)
    
    # 全体統計
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    running_steps: int = 0
    pending_steps: int = 0
    skipped_steps: int = 0
    
    # 時間統計
    started_at: Optional[datetime] = None
    estimated_completion_at: Optional[datetime] = None
    elapsed_time: float = 0.0
    estimated_remaining_time: float = 0.0
    
    # ステップ詳細
    step_statuses: Dict[str, str] = field(default_factory=dict)
    step_durations: Dict[str, float] = field(default_factory=dict)
    step_errors: Dict[str, str] = field(default_factory=dict)
    
    # パフォーマンス統計
    average_step_duration: float = 0.0
    fastest_step: Optional[str] = None
    slowest_step: Optional[str] = None
    
    # リソース統計
    peak_concurrent_steps: int = 0
    resource_utilization: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def completion_percentage(self) -> float:
        """完了率"""
        if self.total_steps == 0:
            return 100.0
        return (self.completed_steps + self.skipped_steps) / self.total_steps * 100.0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_steps == 0:
            return 1.0
        return self.completed_steps / self.total_steps
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "project_id": self.project_id,
            "workflow_name": self.workflow_name,
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_steps": self.total_steps,
                "completed_steps": self.completed_steps,
                "failed_steps": self.failed_steps,
                "running_steps": self.running_steps,
                "pending_steps": self.pending_steps,
                "skipped_steps": self.skipped_steps,
                "completion_percentage": self.completion_percentage,
                "success_rate": self.success_rate
            },
            "timing": {
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "estimated_completion_at": self.estimated_completion_at.isoformat() if self.estimated_completion_at else None,
                "elapsed_time": self.elapsed_time,
                "estimated_remaining_time": self.estimated_remaining_time
            },
            "step_details": {
                "statuses": self.step_statuses,
                "durations": self.step_durations,
                "errors": self.step_errors
            },
            "performance": {
                "average_step_duration": self.average_step_duration,
                "fastest_step": self.fastest_step,
                "slowest_step": self.slowest_step,
                "peak_concurrent_steps": self.peak_concurrent_steps
            },
            "resources": self.resource_utilization
        }


class ProgressMonitor:
    """進捗監視システム"""
    
    def __init__(self, max_event_history: int = 1000, cleanup_interval: int = 300):
        self.subscribers: Dict[str, ProgressSubscriber] = {}
        self.event_history: deque = deque(maxlen=max_event_history)
        self.active_workflows: Dict[str, WorkflowExecutionState] = {}
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = datetime.now()
        
        self.logger = logging.getLogger(__name__)
        
        # パフォーマンス統計
        self.performance_stats = defaultdict(list)
        self.resource_stats = defaultdict(dict)
    
    async def subscribe(self, subscriber: ProgressSubscriber) -> None:
        """購読者登録"""
        subscriber_id = subscriber.get_subscriber_id()
        self.subscribers[subscriber_id] = subscriber
        self.logger.info(f"Progress subscriber added: {subscriber_id}")
    
    async def unsubscribe(self, subscriber_id: str) -> None:
        """購読者登録解除"""
        if subscriber_id in self.subscribers:
            del self.subscribers[subscriber_id]
            self.logger.info(f"Progress subscriber removed: {subscriber_id}")
    
    async def publish_event(self, event: ProgressEvent) -> None:
        """イベント配信"""
        # イベント履歴に追加
        self.event_history.append(event)
        
        # 統計更新
        self._update_statistics(event)
        
        # 全購読者に配信
        failed_subscribers = []
        for subscriber_id, subscriber in self.subscribers.items():
            try:
                if await subscriber.is_active():
                    await subscriber.on_progress_event(event)
                else:
                    failed_subscribers.append(subscriber_id)
            except Exception as e:
                self.logger.error(f"Error sending event to subscriber {subscriber_id}: {e}")
                failed_subscribers.append(subscriber_id)
        
        # 非アクティブな購読者を削除
        for subscriber_id in failed_subscribers:
            await self.unsubscribe(subscriber_id)
        
        # 定期クリーンアップ
        await self._cleanup_if_needed()
    
    def register_workflow(self, project_id: str, workflow_state: WorkflowExecutionState) -> None:
        """ワークフロー登録"""
        self.active_workflows[project_id] = workflow_state
        self.logger.info(f"Workflow registered for monitoring: {project_id}")
    
    def unregister_workflow(self, project_id: str) -> None:
        """ワークフロー登録解除"""
        if project_id in self.active_workflows:
            del self.active_workflows[project_id]
            self.logger.info(f"Workflow unregistered from monitoring: {project_id}")
    
    async def create_progress_callback(self, project_id: str, workflow_name: str) -> Callable[[WorkflowExecutionState], Awaitable[None]]:
        """進捗コールバック作成"""
        async def progress_callback(state: WorkflowExecutionState) -> None:
            # 進捗更新イベント生成
            event = ProgressEvent(
                event_type=ProgressEventType.PROGRESS_UPDATE,
                project_id=project_id,
                workflow_name=workflow_name,
                data={
                    "completion_percentage": state.completion_percentage,
                    "completed_steps": state.completed_steps,
                    "total_steps": state.total_steps,
                    "running_steps": state.running_steps,
                    "pending_steps": state.pending_steps,
                    "failed_steps": state.failed_steps,
                    "estimated_remaining_time": state.estimate_remaining_time(),
                    "status_summary": state.get_status_summary()
                }
            )
            
            await self.publish_event(event)
        
        return progress_callback
    
    async def emit_workflow_event(self, event_type: ProgressEventType, project_id: str, 
                                workflow_name: str, step_name: Optional[str] = None,
                                additional_data: Optional[Dict[str, Any]] = None) -> None:
        """ワークフローイベント生成"""
        event = ProgressEvent(
            event_type=event_type,
            project_id=project_id,
            workflow_name=workflow_name,
            step_name=step_name,
            data=additional_data or {}
        )
        
        await self.publish_event(event)
    
    def generate_detailed_report(self, project_id: str) -> Optional[DetailedProgressReport]:
        """詳細進捗レポート生成"""
        if project_id not in self.active_workflows:
            return None
        
        state = self.active_workflows[project_id]
        
        report = DetailedProgressReport(
            project_id=project_id,
            workflow_name=state.workflow_name,
            total_steps=state.total_steps,
            completed_steps=state.completed_steps,
            failed_steps=state.failed_steps,
            running_steps=state.running_steps,
            pending_steps=state.pending_steps,
            skipped_steps=state.skipped_steps,
            started_at=state.started_at,
            elapsed_time=(datetime.now() - state.started_at).total_seconds(),
            estimated_remaining_time=state.estimate_remaining_time(),
            step_statuses={k: v.value for k, v in state.step_statuses.items()},
            step_durations=state.step_durations.copy(),
        )
        
        # 推定完了時刻計算
        if report.estimated_remaining_time > 0:
            report.estimated_completion_at = datetime.now() + timedelta(seconds=report.estimated_remaining_time)
        
        # パフォーマンス統計
        if state.step_durations:
            durations = list(state.step_durations.values())
            report.average_step_duration = sum(durations) / len(durations)
            
            # 最速・最遅ステップ
            min_duration = min(durations)
            max_duration = max(durations)
            
            for step_name, duration in state.step_durations.items():
                if duration == min_duration:
                    report.fastest_step = step_name
                if duration == max_duration:
                    report.slowest_step = step_name
        
        # リソース統計
        if project_id in self.resource_stats:
            report.resource_utilization = self.resource_stats[project_id]
        
        return report
    
    def get_event_history(self, project_id: Optional[str] = None, 
                         event_types: Optional[List[ProgressEventType]] = None,
                         limit: Optional[int] = None) -> List[ProgressEvent]:
        """イベント履歴取得"""
        filtered_events = []
        
        for event in self.event_history:
            # プロジェクトフィルタ
            if project_id and event.project_id != project_id:
                continue
            
            # イベントタイプフィルタ
            if event_types and event.event_type not in event_types:
                continue
            
            filtered_events.append(event)
        
        # 制限適用
        if limit:
            filtered_events = filtered_events[-limit:]
        
        return filtered_events
    
    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """アクティブワークフロー一覧"""
        result = []
        for project_id, state in self.active_workflows.items():
            result.append({
                "project_id": project_id,
                "workflow_name": state.workflow_name,
                "completion_percentage": state.completion_percentage,
                "status": {
                    "completed": state.completed_steps,
                    "running": state.running_steps,
                    "pending": state.pending_steps,
                    "failed": state.failed_steps
                },
                "started_at": state.started_at.isoformat(),
                "is_cancelled": state.is_cancelled,
                "is_paused": state.is_paused
            })
        return result
    
    def _update_statistics(self, event: ProgressEvent) -> None:
        """統計更新"""
        project_id = event.project_id
        
        # パフォーマンス統計
        if event.event_type == ProgressEventType.STEP_COMPLETED and 'duration' in event.data:
            self.performance_stats[project_id].append(event.data['duration'])
        
        # リソース統計
        if event.event_type == ProgressEventType.RESOURCE_UPDATE:
            self.resource_stats[project_id].update(event.data)
    
    async def _cleanup_if_needed(self) -> None:
        """定期クリーンアップ"""
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
            await self._cleanup()
            self.last_cleanup = now
    
    async def _cleanup(self) -> None:
        """クリーンアップ処理"""
        # 非アクティブな購読者削除
        inactive_subscribers = []
        for subscriber_id, subscriber in self.subscribers.items():
            if not await subscriber.is_active():
                inactive_subscribers.append(subscriber_id)
        
        for subscriber_id in inactive_subscribers:
            await self.unsubscribe(subscriber_id)
        
        # 古いパフォーマンス統計削除
        cutoff_time = datetime.now() - timedelta(hours=24)
        # 実装は省略（必要に応じて）
        
        self.logger.debug(f"Cleanup completed. Removed {len(inactive_subscribers)} inactive subscribers")


# グローバル進捗監視インスタンス
progress_monitor = ProgressMonitor() 