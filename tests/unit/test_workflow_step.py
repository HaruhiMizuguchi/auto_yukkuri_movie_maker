"""
ワークフローステップ管理のテスト

このテストファイルは、ワークフローステップの抽象インターフェース、
データ構造、および実行状態管理のテストを提供します。
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Any, Dict, List

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
    ValidationError
)


class TestStepStatus(unittest.TestCase):
    """ステップ状態Enumのテスト"""
    
    def test_step_status_values(self):
        """ステップ状態の値が正しいことを確認"""
        self.assertEqual(StepStatus.PENDING.value, "pending")
        self.assertEqual(StepStatus.RUNNING.value, "running")
        self.assertEqual(StepStatus.COMPLETED.value, "completed")
        self.assertEqual(StepStatus.FAILED.value, "failed")
        self.assertEqual(StepStatus.SKIPPED.value, "skipped")
        self.assertEqual(StepStatus.CANCELLED.value, "cancelled")


class TestStepPriority(unittest.TestCase):
    """ステップ優先度Enumのテスト"""
    
    def test_step_priority_values(self):
        """優先度の数値が正しいことを確認"""
        self.assertEqual(StepPriority.LOW.value, 1)
        self.assertEqual(StepPriority.NORMAL.value, 2)
        self.assertEqual(StepPriority.HIGH.value, 3)
        self.assertEqual(StepPriority.CRITICAL.value, 4)
    
    def test_priority_comparison(self):
        """優先度の比較が正しく動作することを確認"""
        self.assertTrue(StepPriority.CRITICAL.value > StepPriority.HIGH.value)
        self.assertTrue(StepPriority.HIGH.value > StepPriority.NORMAL.value)
        self.assertTrue(StepPriority.NORMAL.value > StepPriority.LOW.value)


class TestStepExecutionContext(unittest.TestCase):
    """ステップ実行コンテキストのテスト"""
    
    def test_context_creation(self):
        """コンテキストの作成テスト"""
        context = StepExecutionContext(
            project_id="test-project-123",
            step_name="theme_selection",
            execution_id="exec-456"
        )
        
        self.assertEqual(context.project_id, "test-project-123")
        self.assertEqual(context.step_name, "theme_selection")
        self.assertEqual(context.execution_id, "exec-456")
        self.assertIsNone(context.started_at)
        self.assertEqual(context.user_context, {})
        self.assertEqual(context.environment_vars, {})
        self.assertEqual(context.resource_limits, {})
    
    def test_context_with_additional_data(self):
        """追加データを含むコンテキストのテスト"""
        started_time = datetime.now()
        context = StepExecutionContext(
            project_id="test-project-123",
            step_name="theme_selection",
            execution_id="exec-456",
            started_at=started_time,
            user_context={"user_id": "user123"},
            environment_vars={"API_KEY": "secret"},
            resource_limits={"memory_mb": 1024}
        )
        
        self.assertEqual(context.started_at, started_time)
        self.assertEqual(context.user_context["user_id"], "user123")
        self.assertEqual(context.environment_vars["API_KEY"], "secret")
        self.assertEqual(context.resource_limits["memory_mb"], 1024)


class TestStepResult(unittest.TestCase):
    """ステップ実行結果のテスト"""
    
    def test_successful_result_creation(self):
        """成功結果の作成テスト"""
        result = StepResult(
            status=StepStatus.COMPLETED,
            output_data={"theme": "教育動画", "category": "学習"},
            execution_time_seconds=45.2,
            resource_usage={"memory_mb": 512},
            artifacts=["theme_candidates.json"]
        )
        
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_data["theme"], "教育動画")
        self.assertEqual(result.execution_time_seconds, 45.2)
        self.assertEqual(result.resource_usage["memory_mb"], 512)
        self.assertEqual(result.artifacts, ["theme_candidates.json"])
        self.assertIsNone(result.error_message)
    
    def test_failed_result_creation(self):
        """失敗結果の作成テスト"""
        result = StepResult(
            status=StepStatus.FAILED,
            error_message="API接続エラー: タイムアウト",
            execution_time_seconds=30.0
        )
        
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.error_message, "API接続エラー: タイムアウト")
        self.assertEqual(result.execution_time_seconds, 30.0)
        self.assertEqual(result.output_data, {})
    
    def test_result_to_dict(self):
        """結果の辞書変換テスト"""
        result = StepResult(
            status=StepStatus.COMPLETED,
            output_data={"result": "success"},
            execution_time_seconds=10.5,
            artifacts=["output.json"]
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict["status"], "completed")
        self.assertEqual(result_dict["output_data"]["result"], "success")
        self.assertEqual(result_dict["execution_time_seconds"], 10.5)
        self.assertEqual(result_dict["artifacts"], ["output.json"])
        self.assertIsNone(result_dict["error_message"])
    
    def test_result_from_dict(self):
        """辞書からの結果復元テスト"""
        data = {
            "status": "completed",
            "output_data": {"result": "success"},
            "error_message": None,
            "execution_time_seconds": 10.5,
            "resource_usage": {"cpu_percent": 25},
            "artifacts": ["output.json"]
        }
        
        result = StepResult.from_dict(data)
        
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_data["result"], "success")
        self.assertEqual(result.execution_time_seconds, 10.5)
        self.assertEqual(result.resource_usage["cpu_percent"], 25)
        self.assertEqual(result.artifacts, ["output.json"])


class TestWorkflowStepDefinition(unittest.TestCase):
    """ワークフローステップ定義のテスト"""
    
    def test_basic_step_definition(self):
        """基本的なステップ定義のテスト"""
        step_def = WorkflowStepDefinition(
            step_id=1,
            step_name="theme_selection",
            display_name="テーマ選定",
            description="動画のテーマを自動または手動で選定"
        )
        
        self.assertEqual(step_def.step_id, 1)
        self.assertEqual(step_def.step_name, "theme_selection")
        self.assertEqual(step_def.display_name, "テーマ選定")
        self.assertEqual(step_def.description, "動画のテーマを自動または手動で選定")
        self.assertEqual(step_def.dependencies, [])
        self.assertEqual(step_def.priority, StepPriority.NORMAL)
        self.assertIsNone(step_def.timeout_seconds)
        self.assertEqual(step_def.retry_count, 3)
        self.assertFalse(step_def.can_skip)
        self.assertFalse(step_def.can_run_parallel)
        self.assertEqual(step_def.required_resources, set())
    
    def test_advanced_step_definition(self):
        """高度なステップ定義のテスト"""
        step_def = WorkflowStepDefinition(
            step_id=2,
            step_name="script_generation",
            display_name="スクリプト生成",
            description="テーマに基づいてスクリプトを生成",
            dependencies=["theme_selection"],
            priority=StepPriority.HIGH,
            timeout_seconds=300,
            retry_count=5,
            can_skip=True,
            can_run_parallel=False,
            required_resources={"llm_api", "memory_2gb"}
        )
        
        self.assertEqual(step_def.dependencies, ["theme_selection"])
        self.assertEqual(step_def.priority, StepPriority.HIGH)
        self.assertEqual(step_def.timeout_seconds, 300)
        self.assertEqual(step_def.retry_count, 5)
        self.assertTrue(step_def.can_skip)
        self.assertFalse(step_def.can_run_parallel)
        self.assertEqual(step_def.required_resources, {"llm_api", "memory_2gb"})
    
    def test_step_definition_validation(self):
        """ステップ定義の検証テスト"""
        # 正常なケース
        step_def = WorkflowStepDefinition(
            step_id=1,
            step_name="test_step",
            display_name="テストステップ",
            description="テスト用ステップ"
        )
        self.assertEqual(step_def.step_id, 1)
        
        # step_id が 0 以下の場合
        with self.assertRaises(ValueError) as context:
            WorkflowStepDefinition(
                step_id=0,
                step_name="test_step",
                display_name="テストステップ",
                description="テスト用ステップ"
            )
        self.assertIn("step_id must be positive", str(context.exception))
        
        # step_name が空の場合
        with self.assertRaises(ValueError) as context:
            WorkflowStepDefinition(
                step_id=1,
                step_name="",
                display_name="テストステップ",
                description="テスト用ステップ"
            )
        self.assertIn("step_name cannot be empty", str(context.exception))
        
        # retry_count が負の場合
        with self.assertRaises(ValueError) as context:
            WorkflowStepDefinition(
                step_id=1,
                step_name="test_step",
                display_name="テストステップ",
                description="テスト用ステップ",
                retry_count=-1
            )
        self.assertIn("retry_count cannot be negative", str(context.exception))


class MockStepProcessor(StepProcessor):
    """テスト用のステッププロセッサモック"""
    
    def __init__(self, execution_time: float = 1.0, should_fail: bool = False):
        self.execution_time = execution_time
        self.should_fail = should_fail
        self.dependencies = []
        self.concurrent_steps = set()
    
    def execute(self, context: StepExecutionContext, input_data: Dict[str, Any]) -> StepResult:
        if self.should_fail:
            raise StepExecutionError(
                step_name=context.step_name,
                message="Mock execution failure"
            )
        
        return StepResult(
            status=StepStatus.COMPLETED,
            output_data={"processed": True, "input_count": len(input_data)},
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


class TestStepProcessor(unittest.TestCase):
    """ステッププロセッサインターフェースのテスト"""
    
    def setUp(self):
        self.context = StepExecutionContext(
            project_id="test-project",
            step_name="test_step",
            execution_id="exec-123"
        )
        self.input_data = {"theme": "教育", "length": 300}
    
    def test_successful_execution(self):
        """正常な実行テスト"""
        processor = MockStepProcessor(execution_time=2.5)
        result = processor.execute(self.context, self.input_data)
        
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertTrue(result.output_data["processed"])
        self.assertEqual(result.output_data["input_count"], 2)
        self.assertEqual(result.execution_time_seconds, 2.5)
    
    def test_failed_execution(self):
        """実行失敗テスト"""
        processor = MockStepProcessor(should_fail=True)
        
        with self.assertRaises(StepExecutionError) as context:
            processor.execute(self.context, self.input_data)
        
        self.assertEqual(context.exception.step_name, "test_step")
        self.assertIn("Mock execution failure", context.exception.message)
    
    def test_input_validation(self):
        """入力検証テスト"""
        processor = MockStepProcessor()
        
        # 正常なケース
        self.assertTrue(processor.validate_input({"key": "value"}))
        
        # 異常なケース
        self.assertFalse(processor.validate_input("not_a_dict"))
    
    def test_dependency_management(self):
        """依存関係管理テスト"""
        processor = MockStepProcessor()
        processor.dependencies = ["theme_selection", "config_validation"]
        
        dependencies = processor.get_required_dependencies()
        self.assertEqual(dependencies, ["theme_selection", "config_validation"])
    
    def test_concurrency_check(self):
        """並列実行チェックテスト"""
        processor = MockStepProcessor()
        processor.concurrent_steps = {"background_generation", "character_synthesis"}
        
        self.assertTrue(processor.can_run_concurrently_with("background_generation"))
        self.assertFalse(processor.can_run_concurrently_with("script_generation"))
    
    def test_execution_time_estimation(self):
        """実行時間推定テスト"""
        processor = MockStepProcessor(execution_time=60.0)
        
        estimated_time = processor.estimate_execution_time(self.input_data)
        self.assertEqual(estimated_time, 60.0)


class MockDependencyResolver(DependencyResolver):
    """テスト用の依存関係解決モック"""
    
    def __init__(self):
        self.step_dependencies = {}
        self.circular_deps = []
    
    def resolve_execution_order(self, steps: List[WorkflowStepDefinition]) -> List[List[str]]:
        # 簡単な実装: 依存関係に基づいて段階的に分ける
        phase_1 = [step.step_name for step in steps if not step.dependencies]
        phase_2 = [step.step_name for step in steps if step.dependencies and len(step.dependencies) == 1]
        phase_3 = [step.step_name for step in steps if step.dependencies and len(step.dependencies) > 1]
        
        return [phase for phase in [phase_1, phase_2, phase_3] if phase]
    
    def check_dependencies_satisfied(self, step_name: str, completed_steps: set) -> bool:
        required_deps = self.step_dependencies.get(step_name, [])
        return all(dep in completed_steps for dep in required_deps)
    
    def find_circular_dependencies(self, steps: List[WorkflowStepDefinition]) -> List[List[str]]:
        return self.circular_deps


class TestDependencyResolver(unittest.TestCase):
    """依存関係解決インターフェースのテスト"""
    
    def setUp(self):
        self.resolver = MockDependencyResolver()
        
        # テスト用ステップ定義
        self.steps = [
            WorkflowStepDefinition(1, "theme_selection", "テーマ選定", "テーマ選定"),
            WorkflowStepDefinition(2, "script_generation", "スクリプト生成", "スクリプト生成", ["theme_selection"]),
            WorkflowStepDefinition(3, "title_generation", "タイトル生成", "タイトル生成", ["theme_selection"]),
            WorkflowStepDefinition(4, "tts_generation", "音声生成", "音声生成", ["script_generation", "title_generation"])
        ]
    
    def test_execution_order_resolution(self):
        """実行順序解決テスト"""
        execution_order = self.resolver.resolve_execution_order(self.steps)
        
        # 依存関係のないステップが最初に来ることを確認
        self.assertIn("theme_selection", execution_order[0])
        
        # 1つの依存関係を持つステップが2番目に来ることを確認
        if len(execution_order) > 1:
            self.assertIn("script_generation", execution_order[1])
            self.assertIn("title_generation", execution_order[1])
        
        # 複数の依存関係を持つステップが最後に来ることを確認
        if len(execution_order) > 2:
            self.assertIn("tts_generation", execution_order[2])
    
    def test_dependencies_satisfied_check(self):
        """依存関係満足チェックテスト"""
        self.resolver.step_dependencies = {
            "script_generation": ["theme_selection"],
            "tts_generation": ["script_generation", "title_generation"]
        }
        
        # 依存関係が満たされていない場合
        self.assertFalse(self.resolver.check_dependencies_satisfied("script_generation", set()))
        
        # 依存関係が満たされている場合
        self.assertTrue(self.resolver.check_dependencies_satisfied("script_generation", {"theme_selection"}))
        
        # 部分的に満たされている場合
        self.assertFalse(self.resolver.check_dependencies_satisfied("tts_generation", {"script_generation"}))
        
        # 完全に満たされている場合
        self.assertTrue(self.resolver.check_dependencies_satisfied("tts_generation", {"script_generation", "title_generation"}))
    
    def test_circular_dependency_detection(self):
        """循環依存検出テスト"""
        # 循環依存がない場合
        circular_deps = self.resolver.find_circular_dependencies(self.steps)
        self.assertEqual(circular_deps, [])
        
        # 循環依存がある場合
        self.resolver.circular_deps = [["step_a", "step_b", "step_a"]]
        circular_deps = self.resolver.find_circular_dependencies(self.steps)
        self.assertEqual(len(circular_deps), 1)
        self.assertEqual(circular_deps[0], ["step_a", "step_b", "step_a"])


class MockResourceManager(ResourceManager):
    """テスト用のリソース管理モック"""
    
    def __init__(self):
        self.available_resources = {"cpu", "memory_1gb", "llm_api", "tts_api"}
        self.allocated_resources = set()
    
    def acquire_resources(self, resource_names: set, timeout_seconds: int = None) -> bool:
        if resource_names.issubset(self.available_resources - self.allocated_resources):
            self.allocated_resources.update(resource_names)
            return True
        return False
    
    def release_resources(self, resource_names: set) -> None:
        self.allocated_resources -= resource_names
    
    def is_resource_available(self, resource_name: str) -> bool:
        return resource_name in self.available_resources and resource_name not in self.allocated_resources
    
    def get_resource_usage(self) -> Dict[str, Any]:
        return {
            "allocated": list(self.allocated_resources),
            "available": list(self.available_resources - self.allocated_resources),
            "total": list(self.available_resources)
        }


class TestResourceManager(unittest.TestCase):
    """リソース管理インターフェースのテスト"""
    
    def setUp(self):
        self.resource_manager = MockResourceManager()
    
    def test_resource_acquisition(self):
        """リソース取得テスト"""
        # 利用可能なリソースの取得
        success = self.resource_manager.acquire_resources({"cpu", "memory_1gb"})
        self.assertTrue(success)
        
        # 同じリソースの再取得（失敗）
        success = self.resource_manager.acquire_resources({"cpu"})
        self.assertFalse(success)
        
        # 利用できないリソースの取得（失敗）
        success = self.resource_manager.acquire_resources({"gpu"})
        self.assertFalse(success)
    
    def test_resource_release(self):
        """リソース解放テスト"""
        # リソースを取得
        self.resource_manager.acquire_resources({"cpu", "memory_1gb"})
        
        # リソースを解放
        self.resource_manager.release_resources({"cpu"})
        
        # 解放されたリソースが再取得可能か確認
        success = self.resource_manager.acquire_resources({"cpu"})
        self.assertTrue(success)
    
    def test_resource_availability_check(self):
        """リソース利用可能性チェックテスト"""
        # 初期状態では利用可能
        self.assertTrue(self.resource_manager.is_resource_available("cpu"))
        
        # 取得後は利用不可
        self.resource_manager.acquire_resources({"cpu"})
        self.assertFalse(self.resource_manager.is_resource_available("cpu"))
        
        # 存在しないリソースは利用不可
        self.assertFalse(self.resource_manager.is_resource_available("gpu"))
    
    def test_resource_usage_reporting(self):
        """リソース使用状況レポートテスト"""
        # 初期状態
        usage = self.resource_manager.get_resource_usage()
        self.assertEqual(usage["allocated"], [])
        self.assertEqual(len(usage["available"]), 4)
        
        # リソース取得後
        self.resource_manager.acquire_resources({"cpu", "memory_1gb"})
        usage = self.resource_manager.get_resource_usage()
        
        self.assertEqual(len(usage["allocated"]), 2)
        self.assertIn("cpu", usage["allocated"])
        self.assertIn("memory_1gb", usage["allocated"])
        self.assertEqual(len(usage["available"]), 2)


if __name__ == '__main__':
    unittest.main() 