"""
ワークフローエンジンのテスト

このテストファイルは、ワークフローエンジンの並列実行制御、
リソース管理、デッドロック防止機能のテストを提供します。
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set
import time

from src.core.workflow_step import (
    StepStatus,
    StepPriority,
    StepExecutionContext,
    StepResult,
    WorkflowStepDefinition,
    StepProcessor,
    DependencyResolver,
    ResourceManager
)
from src.core.workflow_exceptions import (
    WorkflowEngineError,
    StepExecutionError,
    DependencyError,
    ResourceLimitError,
    TimeoutError,
    CircularDependencyError
)
from src.core.workflow_engine import (
    WorkflowEngine,
    WorkflowExecutionState,
    WorkflowExecutionResult,
    ParallelExecutionManager,
    DeadlockDetector
)


class TestWorkflowExecutionState(unittest.TestCase):
    """ワークフロー実行状態のテスト"""
    
    def test_state_creation(self):
        """実行状態の作成テスト"""
        state = WorkflowExecutionState(
            project_id="test-project-123",
            workflow_name="yukkuri_video_generation",
            total_steps=13
        )
        
        self.assertEqual(state.project_id, "test-project-123")
        self.assertEqual(state.workflow_name, "yukkuri_video_generation")
        self.assertEqual(state.total_steps, 13)
        self.assertEqual(state.completed_steps, 0)
        self.assertEqual(state.failed_steps, 0)
        self.assertEqual(state.running_steps, 0)
        self.assertEqual(state.pending_steps, 13)
        self.assertFalse(state.is_cancelled)
        self.assertFalse(state.is_paused)
        self.assertEqual(state.completion_percentage, 0.0)
    
    def test_state_progress_tracking(self):
        """進捗追跡テスト"""
        state = WorkflowExecutionState(
            project_id="test-project",
            workflow_name="test_workflow",
            total_steps=10
        )
        
        # ステップ完了
        state.complete_step("step_1")
        state.complete_step("step_2")
        
        self.assertEqual(state.completed_steps, 2)
        self.assertEqual(state.pending_steps, 8)
        self.assertEqual(state.completion_percentage, 20.0)
        
        # ステップ開始
        state.start_step("step_3")
        self.assertEqual(state.running_steps, 1)
        self.assertEqual(state.pending_steps, 7)
        
        # ステップ失敗
        state.fail_step("step_3", "Error occurred")
        self.assertEqual(state.failed_steps, 1)
        self.assertEqual(state.running_steps, 0)
    
    def test_state_time_estimation(self):
        """時間推定テスト"""
        state = WorkflowExecutionState(
            project_id="test-project",
            workflow_name="test_workflow",
            total_steps=4
        )
        
        # 実行時間履歴を追加
        state.add_step_duration("step_1", 30.0)
        state.add_step_duration("step_2", 45.0)
        
        # 平均実行時間は37.5秒、残り2ステップなので75秒
        estimated = state.estimate_remaining_time()
        self.assertEqual(estimated, 75.0)
    
    def test_state_cancellation(self):
        """キャンセル機能テスト"""
        state = WorkflowExecutionState(
            project_id="test-project",
            workflow_name="test_workflow",
            total_steps=5
        )
        
        state.cancel("User requested cancellation")
        
        self.assertTrue(state.is_cancelled)
        self.assertEqual(state.cancellation_reason, "User requested cancellation")
        self.assertIsNotNone(state.cancelled_at)


class TestWorkflowExecutionResult(unittest.TestCase):
    """ワークフロー実行結果のテスト"""
    
    def test_successful_result(self):
        """成功結果のテスト"""
        result = WorkflowExecutionResult(
            project_id="test-project",
            workflow_name="test_workflow",
            status=StepStatus.COMPLETED,
            total_steps=5,
            completed_steps=5,
            failed_steps=0,
            execution_time_seconds=150.0
        )
        
        self.assertTrue(result.is_successful)
        self.assertFalse(result.has_failures)
        self.assertEqual(result.success_rate, 1.0)
        self.assertEqual(result.completion_percentage, 100.0)
    
    def test_failed_result(self):
        """失敗結果のテスト"""
        result = WorkflowExecutionResult(
            project_id="test-project",
            workflow_name="test_workflow",
            status=StepStatus.FAILED,
            total_steps=5,
            completed_steps=3,
            failed_steps=2,
            execution_time_seconds=90.0
        )
        
        self.assertFalse(result.is_successful)
        self.assertTrue(result.has_failures)
        self.assertEqual(result.success_rate, 0.6)
        self.assertEqual(result.completion_percentage, 60.0)
    
    def test_result_serialization(self):
        """結果のシリアライゼーション"""
        result = WorkflowExecutionResult(
            project_id="test-project",
            workflow_name="test_workflow",
            status=StepStatus.COMPLETED,
            total_steps=3,
            completed_steps=3,
            failed_steps=0,
            execution_time_seconds=75.0,
            step_results={
                "step_1": StepResult(StepStatus.COMPLETED, {"output": "value1"}),
                "step_2": StepResult(StepStatus.COMPLETED, {"output": "value2"}),
            }
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict["project_id"], "test-project")
        self.assertEqual(result_dict["status"], "completed")
        self.assertEqual(result_dict["completion_percentage"], 100.0)
        self.assertIn("step_results", result_dict)


class AsyncMockStepProcessor(StepProcessor):
    """非同期テスト用のステッププロセッサモック"""
    
    def __init__(self, step_name: str, execution_time: float = 1.0, should_fail: bool = False):
        self.step_name = step_name
        self.execution_time = execution_time
        self.should_fail = should_fail
        self.dependencies = []
        self.concurrent_steps = set()
        self.required_resources = set()
    
    async def execute_async(self, context: StepExecutionContext, input_data: Dict[str, Any]) -> StepResult:
        """非同期実行"""
        await asyncio.sleep(self.execution_time)
        
        if self.should_fail:
            raise StepExecutionError(
                step_name=context.step_name,
                message=f"Mock execution failure for {self.step_name}"
            )
        
        return StepResult(
            status=StepStatus.COMPLETED,
            output_data={"processed_by": self.step_name, "input_count": len(input_data)},
            execution_time_seconds=self.execution_time
        )
    
    def execute(self, context: StepExecutionContext, input_data: Dict[str, Any]) -> StepResult:
        """同期実行（非推奨）"""
        if self.should_fail:
            raise StepExecutionError(
                step_name=context.step_name,
                message=f"Mock execution failure for {self.step_name}"
            )
        
        return StepResult(
            status=StepStatus.COMPLETED,
            output_data={"processed_by": self.step_name},
            execution_time_seconds=self.execution_time
        )
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return isinstance(input_data, dict)
    
    def get_required_dependencies(self) -> List[str]:
        return self.dependencies
    
    def can_run_concurrently_with(self, other_step: str) -> bool:
        return other_step in self.concurrent_steps
    
    def estimate_execution_time(self, input_data: Dict[str, Any]) -> float:
        return self.execution_time


class TestParallelExecutionManager(unittest.TestCase):
    """並列実行管理のテスト"""
    
    def setUp(self):
        self.execution_manager = ParallelExecutionManager(max_concurrent_steps=3)
        
        # テスト用ステッププロセッサ
        self.processors = {
            "step_1": AsyncMockStepProcessor("step_1", 0.1),
            "step_2": AsyncMockStepProcessor("step_2", 0.1),
            "step_3": AsyncMockStepProcessor("step_3", 0.1),
            "step_4": AsyncMockStepProcessor("step_4", 0.1, should_fail=True),
        }
        
        # 並列実行可能な設定
        self.processors["step_1"].concurrent_steps = {"step_2", "step_3"}
        self.processors["step_2"].concurrent_steps = {"step_1", "step_3"}
        self.processors["step_3"].concurrent_steps = {"step_1", "step_2"}
    
    def test_concurrent_step_execution(self):
        """並列ステップ実行テスト"""
        async def run_test():
            contexts = [
                StepExecutionContext("project-1", "step_1", "exec-1"),
                StepExecutionContext("project-1", "step_2", "exec-2"),
                StepExecutionContext("project-1", "step_3", "exec-3"),
            ]
            
            start_time = time.time()
            
            results = await self.execution_manager.execute_steps_parallel(
                [
                    (self.processors["step_1"], contexts[0], {}),
                    (self.processors["step_2"], contexts[1], {}),
                    (self.processors["step_3"], contexts[2], {}),
                ]
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 並列実行により0.3秒ではなく約0.1秒で完了することを確認
            self.assertLess(execution_time, 0.2)
            self.assertEqual(len(results), 3)
            
            for result in results:
                self.assertEqual(result.status, StepStatus.COMPLETED)
        
        asyncio.run(run_test())
    
    def test_error_handling_in_parallel_execution(self):
        """並列実行でのエラーハンドリングテスト"""
        async def run_test():
            contexts = [
                StepExecutionContext("project-1", "step_1", "exec-1"),
                StepExecutionContext("project-1", "step_4", "exec-4"),  # 失敗するステップ
            ]
            
            with self.assertRaises(StepExecutionError):
                await self.execution_manager.execute_steps_parallel(
                    [
                        (self.processors["step_1"], contexts[0], {}),
                        (self.processors["step_4"], contexts[1], {}),
                    ]
                )
        
        asyncio.run(run_test())
    
    def test_resource_limit_respect(self):
        """リソース制限の遵守テスト"""
        async def run_test():
            # 最大3ステップの制限で4ステップを実行
            contexts = [
                StepExecutionContext("project-1", f"step_{i}", f"exec-{i}")
                for i in range(1, 5)
            ]
            
            # 実行開始時刻を記録
            start_time = time.time()
            
            tasks = [
                (self.processors["step_1"], contexts[0], {}),
                (self.processors["step_2"], contexts[1], {}),
                (self.processors["step_3"], contexts[2], {}),
                (self.processors["step_1"], contexts[3], {}),  # 4番目のタスク
            ]
            
            results = await self.execution_manager.execute_steps_parallel(tasks)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 制限により一部は待機が必要なため、0.1秒以上かかることを確認
            self.assertGreater(execution_time, 0.1)
            self.assertEqual(len(results), 4)
        
        asyncio.run(run_test())


class TestDeadlockDetector(unittest.TestCase):
    """デッドロック検出のテスト"""
    
    def setUp(self):
        self.detector = DeadlockDetector()
    
    def test_no_deadlock_detection(self):
        """デッドロックなしの検出テスト"""
        # 正常な依存関係グラフ
        dependencies = {
            "step_1": [],
            "step_2": ["step_1"],
            "step_3": ["step_1"],
            "step_4": ["step_2", "step_3"],
        }
        
        has_deadlock = self.detector.detect_deadlock(dependencies)
        self.assertFalse(has_deadlock)
    
    def test_simple_circular_dependency(self):
        """単純な循環依存の検出テスト"""
        # A -> B -> A の循環
        dependencies = {
            "step_a": ["step_b"],
            "step_b": ["step_a"],
        }
        
        has_deadlock = self.detector.detect_deadlock(dependencies)
        self.assertTrue(has_deadlock)
        
        cycles = self.detector.find_dependency_cycles(dependencies)
        self.assertEqual(len(cycles), 1)
        self.assertIn("step_a", cycles[0])
        self.assertIn("step_b", cycles[0])
    
    def test_complex_circular_dependency(self):
        """複雑な循環依存の検出テスト"""
        # A -> B -> C -> A の循環
        dependencies = {
            "step_a": ["step_b"],
            "step_b": ["step_c"],
            "step_c": ["step_a"],
            "step_d": ["step_a"],  # 循環に関与しない
        }
        
        has_deadlock = self.detector.detect_deadlock(dependencies)
        self.assertTrue(has_deadlock)
        
        cycles = self.detector.find_dependency_cycles(dependencies)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(len(cycles[0]), 3)
    
    def test_self_dependency(self):
        """自己依存の検出テスト"""
        dependencies = {
            "step_a": ["step_a"],  # 自己参照
            "step_b": [],
        }
        
        has_deadlock = self.detector.detect_deadlock(dependencies)
        self.assertTrue(has_deadlock)
    
    def test_resource_deadlock_detection(self):
        """リソースデッドロックの検出テスト"""
        # ステップAがリソース1を要求し、ステップBがリソース2を要求
        # 但し、Aが実行中にリソース2も必要、Bが実行中にリソース1も必要
        resource_requests = {
            "step_a": {"primary": ["resource_1"], "secondary": ["resource_2"]},
            "step_b": {"primary": ["resource_2"], "secondary": ["resource_1"]},
        }
        
        has_resource_deadlock = self.detector.detect_resource_deadlock(resource_requests)
        self.assertTrue(has_resource_deadlock)


class TestWorkflowEngine(unittest.TestCase):
    """ワークフローエンジン統合テスト"""
    
    def setUp(self):
        # モックの依存関係注入
        self.mock_dependency_resolver = Mock(spec=DependencyResolver)
        self.mock_resource_manager = Mock(spec=ResourceManager)
        
        # デフォルトのMock戻り値を設定（循環依存なし）
        self.mock_dependency_resolver.find_circular_dependencies.return_value = []
        
        # ワークフローエンジンの初期化
        self.engine = WorkflowEngine(
            dependency_resolver=self.mock_dependency_resolver,
            resource_manager=self.mock_resource_manager,
            max_concurrent_steps=3,
            default_timeout_seconds=300
        )
        
        # テスト用ステップ定義
        self.step_definitions = [
            WorkflowStepDefinition(1, "theme_selection", "テーマ選定", "テーマ選定"),
            WorkflowStepDefinition(2, "script_generation", "スクリプト生成", "スクリプト生成", ["theme_selection"]),
            WorkflowStepDefinition(3, "title_generation", "タイトル生成", "タイトル生成", ["theme_selection"]),
            WorkflowStepDefinition(4, "tts_generation", "音声生成", "音声生成", ["script_generation"]),
        ]
        
        # テスト用プロセッサ
        self.step_processors = {
            "theme_selection": AsyncMockStepProcessor("theme_selection", 0.1),
            "script_generation": AsyncMockStepProcessor("script_generation", 0.1),
            "title_generation": AsyncMockStepProcessor("title_generation", 0.1),
            "tts_generation": AsyncMockStepProcessor("tts_generation", 0.1),
        }
    
    def test_workflow_registration(self):
        """ワークフロー登録テスト"""
        # 循環依存なしを明示
        self.mock_dependency_resolver.find_circular_dependencies.return_value = []
        
        workflow_name = "yukkuri_video_generation"
        
        self.engine.register_workflow(workflow_name, self.step_definitions)
        
        self.assertIn(workflow_name, self.engine.registered_workflows)
        self.assertEqual(len(self.engine.registered_workflows[workflow_name]), 4)
    
    def test_step_processor_registration(self):
        """ステッププロセッサ登録テスト"""
        for step_name, processor in self.step_processors.items():
            self.engine.register_step_processor(step_name, processor)
        
        self.assertEqual(len(self.engine.step_processors), 4)
        self.assertIn("theme_selection", self.engine.step_processors)
    
    def test_workflow_execution_planning(self):
        """ワークフロー実行計画テスト"""
        # 依存関係解決の設定（循環依存なしを明示）
        self.mock_dependency_resolver.find_circular_dependencies.return_value = []
        self.mock_dependency_resolver.resolve_execution_order.return_value = [
            ["theme_selection"],  # フェーズ1
            ["script_generation", "title_generation"],  # フェーズ2（並列）
            ["tts_generation"]  # フェーズ3
        ]
        
        workflow_name = "yukkuri_video_generation"
        self.engine.register_workflow(workflow_name, self.step_definitions)
        
        execution_plan = self.engine.plan_execution(workflow_name, "test-project-123")
        
        self.assertEqual(len(execution_plan.phases), 3)
        self.assertEqual(execution_plan.phases[0], ["theme_selection"])
        self.assertEqual(set(execution_plan.phases[1]), {"script_generation", "title_generation"})
        self.assertEqual(execution_plan.phases[2], ["tts_generation"])
    
    def test_dependency_validation(self):
        """依存関係検証テスト"""
        # 循環依存の検出
        self.mock_dependency_resolver.find_circular_dependencies.return_value = [
            ["step_a", "step_b", "step_a"]
        ]
        
        workflow_name = "invalid_workflow"
        invalid_steps = [
            WorkflowStepDefinition(1, "step_a", "ステップA", "説明", ["step_b"]),
            WorkflowStepDefinition(2, "step_b", "ステップB", "説明", ["step_a"]),
        ]
        
        with self.assertRaises(CircularDependencyError):
            self.engine.register_workflow(workflow_name, invalid_steps)
    
    def test_resource_availability_check(self):
        """リソース可用性チェックテスト"""
        # 循環依存なしを明示
        self.mock_dependency_resolver.find_circular_dependencies.return_value = []
        # 実行順序の設定
        self.mock_dependency_resolver.resolve_execution_order.return_value = [
            ["theme_selection"],
            ["script_generation", "title_generation"],
            ["tts_generation"]
        ]
        # リソース制限の設定
        self.mock_resource_manager.is_resource_available.return_value = True
        self.mock_resource_manager.acquire_resources.return_value = True
        
        workflow_name = "yukkuri_video_generation"
        self.engine.register_workflow(workflow_name, self.step_definitions)
        
        for step_name, processor in self.step_processors.items():
            self.engine.register_step_processor(step_name, processor)
        
        # リソース可用性のチェック
        can_execute = self.engine.check_resource_availability(workflow_name, "test-project")
        self.assertTrue(can_execute)
    
    def test_workflow_execution_dry_run(self):
        """ワークフロー実行ドライランテスト"""
        # 依存関係解決の設定
        self.mock_dependency_resolver.resolve_execution_order.return_value = [
            ["theme_selection"],
            ["script_generation", "title_generation"],
            ["tts_generation"]
        ]
        self.mock_dependency_resolver.find_circular_dependencies.return_value = []
        
        # リソース管理の設定
        self.mock_resource_manager.is_resource_available.return_value = True
        self.mock_resource_manager.acquire_resources.return_value = True
        
        workflow_name = "yukkuri_video_generation"
        self.engine.register_workflow(workflow_name, self.step_definitions)
        
        for step_name, processor in self.step_processors.items():
            self.engine.register_step_processor(step_name, processor)
        
        # ドライラン実行
        dry_run_result = self.engine.execute_workflow_dry_run(
            workflow_name=workflow_name,
            project_id="test-project-123",
            initial_input={"user_preferences": {"genre": "教育"}}
        )
        
        self.assertIsNotNone(dry_run_result)
        self.assertEqual(dry_run_result.total_phases, 3)
        self.assertGreater(dry_run_result.estimated_total_time, 0)


if __name__ == '__main__':
    unittest.main() 