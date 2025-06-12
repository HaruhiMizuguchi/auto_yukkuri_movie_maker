"""
進捗監視システム単体テスト

このテストは、進捗監視システムの各機能が
正しく動作することを検証します。
"""

import asyncio
import unittest
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock

from src.core.progress_monitor import (
    ProgressMonitor,
    ProgressEvent,
    ProgressEventType,
    ProgressSubscriber,
    WebSocketSubscriber,
    SSESubscriber,
    DetailedProgressReport
)
from src.core.workflow_engine import WorkflowExecutionState
from src.core.workflow_step import StepStatus


class MockProgressSubscriber(ProgressSubscriber):
    """テスト用進捗購読者"""
    
    def __init__(self, subscriber_id: str, active: bool = True):
        self.subscriber_id = subscriber_id
        self.active = active
        self.received_events: List[ProgressEvent] = []
    
    async def on_progress_event(self, event: ProgressEvent) -> None:
        """進捗イベント受信"""
        self.received_events.append(event)
    
    def get_subscriber_id(self) -> str:
        return self.subscriber_id
    
    async def is_active(self) -> bool:
        return self.active


class TestProgressEvent(unittest.TestCase):
    """進捗イベントテスト"""
    
    def test_event_creation(self):
        """イベント作成テスト"""
        event = ProgressEvent(
            event_type=ProgressEventType.WORKFLOW_STARTED,
            project_id="test-project-123",
            workflow_name="test_workflow",
            step_name="init",
            data={"test": "data"}
        )
        
        self.assertEqual(event.event_type, ProgressEventType.WORKFLOW_STARTED)
        self.assertEqual(event.project_id, "test-project-123")
        self.assertEqual(event.workflow_name, "test_workflow")
        self.assertEqual(event.step_name, "init")
        self.assertEqual(event.data["test"], "data")
        self.assertIsNotNone(event.event_id)
        self.assertIsInstance(event.timestamp, datetime)
    
    def test_event_serialization(self):
        """イベントシリアライゼーションテスト"""
        event = ProgressEvent(
            event_type=ProgressEventType.PROGRESS_UPDATE,
            project_id="test-project",
            workflow_name="test_workflow",
            data={"percentage": 50.0}
        )
        
        # 辞書変換
        event_dict = event.to_dict()
        self.assertEqual(event_dict["event_type"], "progress_update")
        self.assertEqual(event_dict["project_id"], "test-project")
        self.assertEqual(event_dict["data"]["percentage"], 50.0)
        
        # JSON変換
        event_json = event.to_json()
        self.assertIsInstance(event_json, str)
        self.assertIn("progress_update", event_json)


class TestProgressMonitor(unittest.TestCase):
    """進捗監視システムテスト"""
    
    def setUp(self):
        """テスト初期化"""
        self.monitor = ProgressMonitor(max_event_history=100, cleanup_interval=60)
        self.test_subscriber = MockProgressSubscriber("test-subscriber-1")
    
    def test_subscriber_management(self):
        """購読者管理テスト"""
        async def run_test():
            # 購読者登録
            await self.monitor.subscribe(self.test_subscriber)
            self.assertEqual(len(self.monitor.subscribers), 1)
            self.assertIn("test-subscriber-1", self.monitor.subscribers)
            
            # 購読者登録解除
            await self.monitor.unsubscribe("test-subscriber-1")
            self.assertEqual(len(self.monitor.subscribers), 0)
        
        asyncio.run(run_test())
    
    def test_event_publishing(self):
        """イベント配信テスト"""
        async def run_test():
            # 購読者登録
            await self.monitor.subscribe(self.test_subscriber)
            
            # イベント作成
            event = ProgressEvent(
                event_type=ProgressEventType.WORKFLOW_STARTED,
                project_id="test-project",
                workflow_name="test_workflow"
            )
            
            # イベント配信
            await self.monitor.publish_event(event)
            
            # 検証
            self.assertEqual(len(self.test_subscriber.received_events), 1)
            self.assertEqual(self.test_subscriber.received_events[0].event_type, 
                           ProgressEventType.WORKFLOW_STARTED)
            
            # イベント履歴確認
            self.assertEqual(len(self.monitor.event_history), 1)
        
        asyncio.run(run_test())
    
    def test_workflow_registration(self):
        """ワークフロー登録テスト"""
        # ワークフロー状態作成
        workflow_state = WorkflowExecutionState(
            project_id="test-project",
            workflow_name="test_workflow",
            total_steps=4
        )
        
        # 登録
        self.monitor.register_workflow("test-project", workflow_state)
        self.assertIn("test-project", self.monitor.active_workflows)
        
        # 登録解除
        self.monitor.unregister_workflow("test-project")
        self.assertNotIn("test-project", self.monitor.active_workflows)
    
    def test_progress_callback_creation(self):
        """進捗コールバック作成テスト"""
        async def run_test():
            # 購読者登録
            await self.monitor.subscribe(self.test_subscriber)
            
            # コールバック作成
            callback = await self.monitor.create_progress_callback(
                "test-project", "test_workflow"
            )
            
            # ワークフロー状態作成
            workflow_state = WorkflowExecutionState(
                project_id="test-project",
                workflow_name="test_workflow",
                total_steps=4
            )
            
            # コールバック実行
            await callback(workflow_state)
            
            # 検証
            self.assertEqual(len(self.test_subscriber.received_events), 1)
            event = self.test_subscriber.received_events[0]
            self.assertEqual(event.event_type, ProgressEventType.PROGRESS_UPDATE)
            self.assertIn("completion_percentage", event.data)
        
        asyncio.run(run_test())
    
    def test_detailed_report_generation(self):
        """詳細レポート生成テスト"""
        # ワークフロー状態作成
        workflow_state = WorkflowExecutionState(
            project_id="test-project",
            workflow_name="test_workflow",
            total_steps=4
        )
        
        # 実行状況シミュレート
        workflow_state.complete_step("step1", 1.5)
        workflow_state.complete_step("step2", 2.0)
        workflow_state.start_step("step3")
        
        # 登録
        self.monitor.register_workflow("test-project", workflow_state)
        
        # レポート生成
        report = self.monitor.generate_detailed_report("test-project")
        
        # 検証
        self.assertIsNotNone(report)
        self.assertEqual(report.project_id, "test-project")
        self.assertEqual(report.total_steps, 4)
        self.assertEqual(report.completed_steps, 2)
        self.assertEqual(report.running_steps, 1)
        self.assertGreater(report.average_step_duration, 0)
        self.assertIsNotNone(report.fastest_step)
        self.assertIsNotNone(report.slowest_step)
    
    def test_event_history_filtering(self):
        """イベント履歴フィルタリングテスト"""
        async def run_test():
            # 複数のイベントを生成
            events = [
                ProgressEvent(ProgressEventType.WORKFLOW_STARTED, "project-1", "workflow-1"),
                ProgressEvent(ProgressEventType.STEP_STARTED, "project-1", "workflow-1", "step-1"),
                ProgressEvent(ProgressEventType.WORKFLOW_STARTED, "project-2", "workflow-2"),
                ProgressEvent(ProgressEventType.STEP_COMPLETED, "project-1", "workflow-1", "step-1"),
            ]
            
            for event in events:
                await self.monitor.publish_event(event)
            
            # プロジェクトフィルタテスト
            project1_events = self.monitor.get_event_history(project_id="project-1")
            self.assertEqual(len(project1_events), 3)
            
            # イベントタイプフィルタテスト
            start_events = self.monitor.get_event_history(
                event_types=[ProgressEventType.WORKFLOW_STARTED]
            )
            self.assertEqual(len(start_events), 2)
            
            # 制限テスト
            limited_events = self.monitor.get_event_history(limit=2)
            self.assertEqual(len(limited_events), 2)
        
        asyncio.run(run_test())
    
    def test_active_workflows_listing(self):
        """アクティブワークフロー一覧テスト"""
        # 複数のワークフロー状態作成
        workflow1 = WorkflowExecutionState("project-1", "workflow-1", 3)
        workflow2 = WorkflowExecutionState("project-2", "workflow-2", 5)
        
        workflow1.complete_step("step1", 1.0)
        workflow2.complete_step("step1", 1.5)
        workflow2.complete_step("step2", 2.0)
        
        # 登録
        self.monitor.register_workflow("project-1", workflow1)
        self.monitor.register_workflow("project-2", workflow2)
        
        # 一覧取得
        active_workflows = self.monitor.get_active_workflows()
        
        # 検証
        self.assertEqual(len(active_workflows), 2)
        
        project1_info = next(w for w in active_workflows if w["project_id"] == "project-1")
        self.assertEqual(project1_info["workflow_name"], "workflow-1")
        self.assertEqual(project1_info["status"]["completed"], 1)
        
        project2_info = next(w for w in active_workflows if w["project_id"] == "project-2")
        self.assertEqual(project2_info["workflow_name"], "workflow-2")
        self.assertEqual(project2_info["status"]["completed"], 2)
    
    def test_inactive_subscriber_cleanup(self):
        """非アクティブ購読者クリーンアップテスト"""
        async def run_test():
            # アクティブ・非アクティブ購読者作成
            active_subscriber = MockProgressSubscriber("active", active=True)
            inactive_subscriber = MockProgressSubscriber("inactive", active=False)
            
            # 登録
            await self.monitor.subscribe(active_subscriber)
            await self.monitor.subscribe(inactive_subscriber)
            self.assertEqual(len(self.monitor.subscribers), 2)
            
            # イベント配信（クリーンアップをトリガー）
            event = ProgressEvent(
                ProgressEventType.PROGRESS_UPDATE,
                "test-project",
                "test_workflow"
            )
            await self.monitor.publish_event(event)
            
            # 非アクティブ購読者が削除されることを確認
            self.assertEqual(len(self.monitor.subscribers), 1)
            self.assertIn("active", self.monitor.subscribers)
            self.assertNotIn("inactive", self.monitor.subscribers)
        
        asyncio.run(run_test())


class TestWebSocketSubscriber(unittest.TestCase):
    """WebSocket購読者テスト"""
    
    def test_websocket_subscriber_creation(self):
        """WebSocket購読者作成テスト"""
        mock_websocket = Mock()
        
        subscriber = WebSocketSubscriber(
            websocket=mock_websocket,
            subscriber_id="ws-test-1",
            project_filter={"project-1", "project-2"}
        )
        
        self.assertEqual(subscriber.get_subscriber_id(), "ws-test-1")
        self.assertEqual(subscriber.project_filter, {"project-1", "project-2"})
    
    def test_event_filtering(self):
        """イベントフィルタリングテスト"""
        async def run_test():
            mock_websocket = AsyncMock()
            
            subscriber = WebSocketSubscriber(
                websocket=mock_websocket,
                subscriber_id="ws-filter-test",
                project_filter={"project-1"}
            )
            
            # フィルタに一致するイベント
            matching_event = ProgressEvent(
                ProgressEventType.PROGRESS_UPDATE,
                "project-1",
                "workflow-1"
            )
            await subscriber.on_progress_event(matching_event)
            mock_websocket.send_text.assert_called_once()
            
            # フィルタに一致しないイベント
            mock_websocket.reset_mock()
            non_matching_event = ProgressEvent(
                ProgressEventType.PROGRESS_UPDATE,
                "project-2",
                "workflow-2"
            )
            await subscriber.on_progress_event(non_matching_event)
            mock_websocket.send_text.assert_not_called()
        
        asyncio.run(run_test())


class TestDetailedProgressReport(unittest.TestCase):
    """詳細進捗レポートテスト"""
    
    def test_report_creation_and_properties(self):
        """レポート作成とプロパティテスト"""
        report = DetailedProgressReport(
            project_id="test-project",
            workflow_name="test_workflow",
            total_steps=10,
            completed_steps=6,
            skipped_steps=1,
            failed_steps=1
        )
        
        # プロパティ検証
        self.assertEqual(report.completion_percentage, 70.0)  # (6 + 1) / 10 * 100
        self.assertEqual(report.success_rate, 0.6)  # 6 / 10
    
    def test_report_serialization(self):
        """レポートシリアライゼーションテスト"""
        report = DetailedProgressReport(
            project_id="test-project",
            workflow_name="test_workflow",
            total_steps=5,
            completed_steps=3,
            step_durations={"step1": 1.5, "step2": 2.0, "step3": 1.0}
        )
        
        report_dict = report.to_dict()
        
        # 基本情報確認
        self.assertEqual(report_dict["project_id"], "test-project")
        self.assertEqual(report_dict["summary"]["total_steps"], 5)
        self.assertEqual(report_dict["summary"]["completed_steps"], 3)
        
        # ステップ詳細確認
        self.assertIn("step_details", report_dict)
        self.assertEqual(len(report_dict["step_details"]["durations"]), 3)


if __name__ == '__main__':
    unittest.main() 