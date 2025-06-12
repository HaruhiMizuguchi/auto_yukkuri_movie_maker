"""
フェーズ2: ワークフローエンジン統合テスト

このテストは、ワークフローエンジンの各コンポーネントが
実際に連携して動作することを検証します。
"""

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set
from unittest.mock import Mock

from src.core.workflow_engine import (
    WorkflowEngine,
    WorkflowExecutionState,
    WorkflowExecutionResult,
    WorkflowExecutionPlan,
    DeadlockDetector,
    ParallelExecutionManager
)
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
    CircularDependencyError,
    ResourceLimitError,
    StepExecutionError
)


class MockStepProcessor(StepProcessor):
    """テスト用ステップ処理器"""
    
    def __init__(self, step_name: str, execution_time: float = 0.1, should_fail: bool = False):
        self.step_name = step_name
        self.execution_time = execution_time
        self.should_fail = should_fail
        self.execution_count = 0
        self.last_input_data: Dict[str, Any] = {}
    
    async def execute_async(self, context: StepExecutionContext, input_data: Dict[str, Any]) -> StepResult:
        """非同期実行"""
        await asyncio.sleep(self.execution_time)
        return self.execute(context, input_data)
    
    def execute(self, context: StepExecutionContext, input_data: Dict[str, Any]) -> StepResult:
        """同期実行"""
        self.execution_count += 1
        self.last_input_data = input_data.copy()
        
        if self.should_fail:
            return StepResult(
                status=StepStatus.FAILED,
                output_data={},
                error_message=f"Test failure in {self.step_name}",
                execution_time_seconds=self.execution_time
            )
        
        # 成功時の出力データ生成
        output_data = {
            f"{self.step_name}_result": f"Success from {self.step_name}",
            "execution_count": self.execution_count,
            "timestamp": datetime.now().isoformat()
        }
        
        return StepResult(
            status=StepStatus.COMPLETED,
            output_data=output_data,
            execution_time_seconds=self.execution_time
        )
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """入力データ検証"""
        return True
    
    def get_required_dependencies(self) -> List[str]:
        """必要な依存関係取得"""
        return []
    
    def can_run_concurrently_with(self, other_step: str) -> bool:
        """他ステップとの並列実行可否"""
        return True
    
    def estimate_execution_time(self, input_data: Dict[str, Any]) -> float:
        """実行時間推定"""
        return self.execution_time


class TestDependencyResolver(DependencyResolver):
    """テスト用依存関係解決器"""
    
    def __init__(self):
        self.dependency_map: Dict[str, List[str]] = {}
    
    def resolve_execution_order(self, step_definitions: List[WorkflowStepDefinition]) -> List[List[str]]:
        """実行順序解決"""
        # 依存関係マップ作成
        dependencies = {}
        for step_def in step_definitions:
            dependencies[step_def.step_name] = step_def.dependencies or []
        
        # トポロジカルソート実行
        phases = []
        remaining = set(step.step_name for step in step_definitions)
        
        while remaining:
            # 依存関係のないステップを見つける
            ready = {step for step in remaining 
                    if not any(dep in remaining for dep in dependencies.get(step, []))}
            
            if not ready:
                # 循環依存の可能性
                raise CircularDependencyError(
                    dependency_chain=list(remaining),
                    context={"remaining_steps": list(remaining)}
                )
            
            phases.append(list(ready))
            remaining -= ready
        
        return phases
    
    def find_circular_dependencies(self, step_definitions: List[WorkflowStepDefinition]) -> List[List[str]]:
        """循環依存検出"""
        # 簡単な循環検出（DFS使用）
        dependencies = {}
        for step_def in step_definitions:
            dependencies[step_def.step_name] = step_def.dependencies or []
        
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # 循環検出
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                cycles.append(cycle)
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for dependency in dependencies.get(node, []):
                dfs(dependency, path[:])
            
            rec_stack.remove(node)
            path.pop()
        
        for step_name in dependencies:
            if step_name not in visited:
                dfs(step_name, [])
        
        return cycles
    
    def check_dependencies_satisfied(self, step_name: str, completed_steps: Set[str]) -> bool:
        """依存関係満足チェック"""
        dependencies = self.dependency_map.get(step_name, [])
        return all(dep in completed_steps for dep in dependencies)


class TestResourceManager(ResourceManager):
    """テスト用リソース管理器"""
    
    def __init__(self, max_cpu: int = 4, max_memory: int = 1000):
        self.max_cpu = max_cpu
        self.max_memory = max_memory
        self.allocated_cpu = 0
        self.allocated_memory = 0
        self.allocations: Dict[str, Dict[str, int]] = {}
    
    def is_resource_available(self, required_resources: Set[str]) -> bool:
        """リソース可用性チェック"""
        # 簡単な実装：CPU/メモリの空きをチェック
        required_cpu = 1  # 各ステップは1CPUを使用
        required_memory = 100  # 各ステップは100MBを使用
        
        return (self.allocated_cpu + required_cpu <= self.max_cpu and
                self.allocated_memory + required_memory <= self.max_memory)
    
    def acquire_resources(self, step_name: str, required_resources: Set[str]) -> bool:
        """リソース取得"""
        if not self.is_resource_available(required_resources):
            return False
        
        cpu_needed = 1
        memory_needed = 100
        
        self.allocated_cpu += cpu_needed
        self.allocated_memory += memory_needed
        self.allocations[step_name] = {"cpu": cpu_needed, "memory": memory_needed}
        
        return True
    
    def release_resources(self, step_name: str) -> None:
        """リソース解放"""
        if step_name in self.allocations:
            allocation = self.allocations.pop(step_name)
            self.allocated_cpu -= allocation["cpu"]
            self.allocated_memory -= allocation["memory"]
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """リソース使用状況取得"""
        return {
            "cpu": {
                "allocated": self.allocated_cpu,
                "max": self.max_cpu,
                "usage_percentage": (self.allocated_cpu / self.max_cpu) * 100
            },
            "memory": {
                "allocated": self.allocated_memory,
                "max": self.max_memory,
                "usage_percentage": (self.allocated_memory / self.max_memory) * 100
            },
            "active_allocations": self.allocations.copy()
        }


class TestWorkflowEngineIntegration(unittest.TestCase):
    """ワークフローエンジン統合テスト"""
    
    def setUp(self):
        """テスト初期化"""
        # Mock依存関係注入
        self.dependency_resolver = Mock(spec=DependencyResolver)
        self.resource_manager = Mock(spec=ResourceManager)
        
        # デフォルト設定
        self.dependency_resolver.find_circular_dependencies.return_value = []
        self.dependency_resolver.resolve_execution_order.return_value = [
            ["init"],
            ["process_a", "process_b"],
            ["finalize"]
        ]
        self.resource_manager.is_resource_available.return_value = True
        self.resource_manager.acquire_resources.return_value = True
        
        self.engine = WorkflowEngine(
            dependency_resolver=self.dependency_resolver,
            resource_manager=self.resource_manager,
            max_concurrent_steps=3,
            default_timeout_seconds=300
        )
        
        # テスト用ステップ定義
        self.step_definitions = [
            WorkflowStepDefinition(1, "init", "初期化", "初期化処理"),
            WorkflowStepDefinition(2, "process_a", "処理A", "処理A実行", ["init"]),
            WorkflowStepDefinition(3, "process_b", "処理B", "処理B実行", ["init"]),
            WorkflowStepDefinition(4, "finalize", "完了", "完了処理", ["process_a", "process_b"]),
        ]
        
        # テスト用プロセッサ
        self.processors = {
            "init": MockStepProcessor("init", 0.1),
            "process_a": MockStepProcessor("process_a", 0.15),
            "process_b": MockStepProcessor("process_b", 0.12),
            "finalize": MockStepProcessor("finalize", 0.08),
        }
    
    def test_workflow_registration_and_planning(self):
        """ワークフロー登録と実行計画テスト"""
        workflow_name = "test_workflow"
        project_id = "test-project-123"
        
        # ワークフロー登録
        self.engine.register_workflow(workflow_name, self.step_definitions)
        
        # プロセッサ登録
        for step_name, processor in self.processors.items():
            self.engine.register_step_processor(step_name, processor)
        
        # 実行計画作成
        plan = self.engine.plan_execution(workflow_name, project_id)
        
        # 検証
        self.assertEqual(plan.project_id, project_id)
        self.assertEqual(plan.workflow_name, workflow_name)
        self.assertEqual(len(plan.phases), 3)
        self.assertGreater(plan.estimated_total_time, 0)
    
    def test_full_workflow_execution(self):
        """完全ワークフロー実行テスト"""
        async def run_test():
            workflow_name = "test_workflow"
            project_id = "test-project-123"
            
            # 準備
            self.engine.register_workflow(workflow_name, self.step_definitions)
            for step_name, processor in self.processors.items():
                self.engine.register_step_processor(step_name, processor)
            
            # 進捗コールバック
            progress_updates = []
            def progress_callback(state: WorkflowExecutionState):
                progress_updates.append({
                    "completed": state.completed_steps,
                    "total": state.total_steps,
                    "percentage": state.completion_percentage
                })
            
            # ワークフロー実行
            result = await self.engine.execute_workflow(
                workflow_name=workflow_name,
                project_id=project_id,
                initial_input={"test_input": "integration_test"},
                progress_callback=progress_callback
            )
            
            # 検証
            self.assertIsInstance(result, WorkflowExecutionResult)
            self.assertEqual(result.status, StepStatus.COMPLETED)
            self.assertEqual(result.completed_steps, 4)
            self.assertEqual(result.failed_steps, 0)
            self.assertTrue(result.is_successful)
            self.assertEqual(result.completion_percentage, 100.0)
            
            # 進捗更新の確認
            self.assertGreater(len(progress_updates), 0)
            
            # 各プロセッサの実行確認
            for processor in self.processors.values():
                self.assertEqual(processor.execution_count, 1)
        
        # 非同期テスト実行
        asyncio.run(run_test())
    
    def test_error_handling_integration(self):
        """エラーハンドリング統合テスト"""
        async def run_test():
            # 失敗するステップを含むワークフロー
            error_processors = {
                "init": MockStepProcessor("init", 0.1),
                "process_a": MockStepProcessor("process_a", 0.1, should_fail=True),
                "process_b": MockStepProcessor("process_b", 0.1),
                "finalize": MockStepProcessor("finalize", 0.1),
            }
            
            workflow_name = "error_workflow"
            project_id = "error-test-123"
            
            # 準備
            self.engine.register_workflow(workflow_name, self.step_definitions)
            for step_name, processor in error_processors.items():
                self.engine.register_step_processor(step_name, processor)
            
            # 実行
            result = await self.engine.execute_workflow(
                workflow_name=workflow_name,
                project_id=project_id,
                initial_input={"error_test": True}
            )
            
            # 検証
            self.assertEqual(result.status, StepStatus.FAILED)
            self.assertGreater(result.failed_steps, 0)
            self.assertFalse(result.is_successful)
            self.assertTrue(result.has_failures)
        
        asyncio.run(run_test())
    
    def test_progress_monitoring_integration(self):
        """進捗監視統合テスト"""
        async def run_test():
            workflow_name = "progress_test"
            project_id = "progress-test-123"
            
            # 準備
            self.engine.register_workflow(workflow_name, self.step_definitions)
            for step_name, processor in self.processors.items():
                self.engine.register_step_processor(step_name, processor)
            
            # 進捗詳細記録
            detailed_progress = []
            def detailed_callback(state: WorkflowExecutionState):
                detailed_progress.append({
                    "timestamp": datetime.now().isoformat(),
                    "completed": state.completed_steps,
                    "running": state.running_steps,
                    "pending": state.pending_steps,
                    "percentage": state.completion_percentage,
                    "estimated_remaining": state.estimate_remaining_time(),
                    "status_summary": state.get_status_summary()
                })
            
            # 実行
            result = await self.engine.execute_workflow(
                workflow_name=workflow_name,
                project_id=project_id,
                initial_input={"progress_test": True},
                progress_callback=detailed_callback
            )
            
            # 検証
            self.assertTrue(result.is_successful)
            self.assertGreater(len(detailed_progress), 0)
            
            # 進捗が単調増加することを確認
            percentages = [p["percentage"] for p in detailed_progress]
            for i in range(1, len(percentages)):
                self.assertGreaterEqual(percentages[i], percentages[i-1])
            
            # 最終的に100%になることを確認
            self.assertEqual(percentages[-1], 100.0)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main() 