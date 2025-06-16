# ワークフローエンジン (Workflow Engine)

## 概要

`WorkflowEngine`は、ゆっくり動画生成の複雑なワークフローを管理・実行するエンジンです。並列処理、依存関係解決、リソース管理、進捗監視、エラーハンドリングなどの機能を提供します。

## 基本的な使用方法

### ワークフローエンジンの初期化

```python
from src.core import (
    WorkflowEngine, 
    WorkflowExecutionState,
    WorkflowExecutionResult
)
from src.core.workflow_step import DependencyResolver, ResourceManager

# 依存関係解決とリソース管理の設定
dependency_resolver = DependencyResolver()
resource_manager = ResourceManager()

# ワークフローエンジンの初期化
workflow_engine = WorkflowEngine(
    dependency_resolver=dependency_resolver,
    resource_manager=resource_manager,
    max_concurrent_steps=3,        # 最大並列実行数
    default_timeout_seconds=300    # デフォルトタイムアウト（5分）
)
```

### ワークフローの定義と登録

```python
from src.core.workflow_step import WorkflowStepDefinition, StepPriority

# ワークフローステップの定義
workflow_steps = [
    WorkflowStepDefinition(
        name="theme_selection",
        display_name="テーマ選定",
        dependencies=[],                    # 依存なし
        priority=StepPriority.HIGH,
        timeout_seconds=120,
        required_resources=set(),
        estimated_duration=30.0
    ),
    WorkflowStepDefinition(
        name="script_generation", 
        display_name="スクリプト生成",
        dependencies=["theme_selection"],   # テーマ選定に依存
        priority=StepPriority.HIGH,
        timeout_seconds=300,
        required_resources={"llm_api"},
        estimated_duration=120.0
    ),
    WorkflowStepDefinition(
        name="tts_generation",
        display_name="音声生成", 
        dependencies=["script_generation"], # スクリプト生成に依存
        priority=StepPriority.NORMAL,
        timeout_seconds=600,
        required_resources={"tts_api"},
        estimated_duration=180.0
    ),
    WorkflowStepDefinition(
        name="video_composition",
        display_name="動画合成",
        dependencies=["tts_generation"],    # 音声生成に依存
        priority=StepPriority.NORMAL, 
        timeout_seconds=900,
        required_resources={"video_encoder"},
        estimated_duration=300.0
    )
]

# ワークフローの登録
workflow_engine.register_workflow("yukkuri_video_generation", workflow_steps)
```

### ステップ処理の実装と登録

```python
from src.core.workflow_step import StepProcessor, StepExecutionContext, StepResult

class ThemeSelectionProcessor(StepProcessor):
    """テーマ選定ステップのプロセッサ"""
    
    async def execute(
        self, 
        context: StepExecutionContext, 
        input_data: Dict[str, Any]
    ) -> StepResult:
        try:
            # テーマ選定の実際の処理
            theme_selector = context.get_resource("theme_selector")
            
            # 処理実行
            result = theme_selector.select_theme(input_data)
            
            return StepResult.success(
                step_name="theme_selection",
                output_data={"selected_theme": result.selected_theme},
                metadata={"candidates_count": len(result.candidates)}
            )
            
        except Exception as e:
            return StepResult.failure(
                step_name="theme_selection",
                error_message=str(e),
                error_details={"error_type": type(e).__name__}
            )

class ScriptGenerationProcessor(StepProcessor):
    """スクリプト生成ステップのプロセッサ"""
    
    async def execute(
        self,
        context: StepExecutionContext,
        input_data: Dict[str, Any]
    ) -> StepResult:
        try:
            # 前のステップの結果を取得
            theme_data = input_data.get("selected_theme")
            if not theme_data:
                raise ValueError("テーマデータが見つかりません")
            
            # スクリプト生成処理
            script_generator = context.get_resource("script_generator")
            script = script_generator.generate(theme_data)
            
            return StepResult.success(
                step_name="script_generation",
                output_data={"script": script},
                metadata={"script_length": len(script.segments)}
            )
            
        except Exception as e:
            return StepResult.failure(
                step_name="script_generation", 
                error_message=str(e),
                error_details={"input_data": input_data}
            )

# ステップ処理の登録
workflow_engine.register_step_processor("theme_selection", ThemeSelectionProcessor())
workflow_engine.register_step_processor("script_generation", ScriptGenerationProcessor())
```

### ワークフローの実行

```python
import asyncio

async def execute_video_generation_workflow():
    """動画生成ワークフローの実行"""
    
    project_id = "video-project-001"
    
    # 初期入力データ
    initial_input = {
        "user_preferences": {
            "preferred_genres": ["プログラミング", "技術解説"],
            "target_audience": "初心者", 
            "content_style": "分かりやすい"
        },
        "target_length_minutes": 8
    }
    
    # 進捗コールバック関数
    def progress_callback(state: WorkflowExecutionState):
        print(f"📊 進捗: {state.completion_percentage:.1f}% "
              f"({state.completed_steps}/{state.total_steps})")
        print(f"   実行中: {state.running_steps}, 待機中: {state.pending_steps}")
        
        if state.failed_steps > 0:
            print(f"❌ 失敗: {state.failed_steps}ステップ")
    
    try:
        # ワークフロー実行
        print("🚀 ワークフロー実行開始...")
        
        result = await workflow_engine.execute_workflow(
            workflow_name="yukkuri_video_generation",
            project_id=project_id,
            initial_input=initial_input,
            progress_callback=progress_callback
        )
        
        # 結果の確認
        if result.is_successful:
            print(f"✅ ワークフロー完了: {result.completion_percentage:.1f}%")
            print(f"⏱️ 実行時間: {result.execution_time_seconds:.1f}秒")
            print(f"📝 完了ステップ: {result.completed_steps}/{result.total_steps}")
        else:
            print(f"❌ ワークフロー失敗:")
            print(f"   失敗ステップ: {result.failed_steps}")
            print(f"   成功率: {result.success_rate:.1%}")
            
            if result.error_summary:
                print(f"   エラー詳細: {result.error_summary}")
        
        return result
        
    except Exception as e:
        print(f"❌ ワークフロー実行エラー: {e}")
        return None

# 実行
result = asyncio.run(execute_video_generation_workflow())
```

## データクラス

### WorkflowExecutionState

ワークフロー実行状態を管理するクラスです。

```python
class WorkflowExecutionState:
    # 基本情報
    project_id: str
    workflow_name: str
    total_steps: int
    
    # ステップ数
    completed_steps: int = 0
    failed_steps: int = 0
    running_steps: int = 0
    pending_steps: int
    skipped_steps: int = 0
    
    # 状態管理
    started_at: datetime
    completed_at: Optional[datetime] = None
    is_cancelled: bool = False
    is_paused: bool = False
    
    # メソッド
    @property
    def completion_percentage(self) -> float
    def estimate_remaining_time(self) -> float
    def get_status_summary(self) -> Dict[str, Any]
```

### WorkflowExecutionResult

ワークフロー実行結果を格納するデータクラスです。

```python
@dataclass
class WorkflowExecutionResult:
    project_id: str
    workflow_name: str
    status: StepStatus
    total_steps: int
    completed_steps: int
    failed_steps: int
    execution_time_seconds: float
    step_results: Dict[str, StepResult]
    
    @property
    def is_successful(self) -> bool
    @property
    def success_rate(self) -> float
    @property
    def completion_percentage(self) -> float
```

### WorkflowExecutionPlan

ワークフロー実行計画を表すデータクラスです。

```python
@dataclass
class WorkflowExecutionPlan:
    project_id: str
    workflow_name: str
    phases: List[List[str]]         # 実行フェーズ（並列実行可能なステップ群）
    total_phases: int
    estimated_total_time: float
    resource_requirements: Dict[str, Set[str]]
    
    def get_phase_steps(self, phase_index: int) -> List[str]
    def get_step_phase(self, step_name: str) -> int
```

## 実際の使用例

### 完全なワークフロー実装例

```python
import asyncio
from typing import Dict, Any
from src.core import WorkflowEngine, WorkflowExecutionState
from src.core.workflow_step import (
    WorkflowStepDefinition, StepProcessor, StepExecutionContext, 
    StepResult, StepPriority, DependencyResolver, ResourceManager
)

class VideoGenerationWorkflow:
    """動画生成ワークフローの完全実装"""
    
    def __init__(self):
        self.workflow_engine = WorkflowEngine(
            dependency_resolver=DependencyResolver(),
            resource_manager=ResourceManager(),
            max_concurrent_steps=2,
            default_timeout_seconds=600
        )
        self._setup_workflow()
    
    def _setup_workflow(self):
        """ワークフローの設定"""
        
        # ステップ定義
        steps = [
            WorkflowStepDefinition(
                name="theme_selection",
                display_name="テーマ選定",
                dependencies=[],
                priority=StepPriority.HIGH,
                timeout_seconds=120,
                required_resources={"llm_api"},
                estimated_duration=30.0
            ),
            WorkflowStepDefinition(
                name="script_generation",
                display_name="スクリプト生成", 
                dependencies=["theme_selection"],
                priority=StepPriority.HIGH,
                timeout_seconds=300,
                required_resources={"llm_api"},
                estimated_duration=120.0
            ),
            WorkflowStepDefinition(
                name="title_generation",
                display_name="タイトル生成",
                dependencies=["theme_selection"],  # テーマと並列実行可能
                priority=StepPriority.NORMAL,
                timeout_seconds=180,
                required_resources={"llm_api"},
                estimated_duration=60.0
            ),
            WorkflowStepDefinition(
                name="tts_generation",
                display_name="音声生成",
                dependencies=["script_generation"],
                priority=StepPriority.NORMAL,
                timeout_seconds=900,
                required_resources={"tts_api"},
                estimated_duration=300.0
            ),
            WorkflowStepDefinition(
                name="video_composition",
                display_name="動画合成", 
                dependencies=["tts_generation", "title_generation"],
                priority=StepPriority.LOW,
                timeout_seconds=1200,
                required_resources={"video_encoder", "storage"},
                estimated_duration=600.0
            )
        ]
        
        # ワークフロー登録
        self.workflow_engine.register_workflow("complete_video_generation", steps)
        
        # プロセッサ登録
        self.workflow_engine.register_step_processor("theme_selection", ThemeSelectionProcessor())
        self.workflow_engine.register_step_processor("script_generation", ScriptGenerationProcessor())
        self.workflow_engine.register_step_processor("title_generation", TitleGenerationProcessor())
        self.workflow_engine.register_step_processor("tts_generation", TTSGenerationProcessor())
        self.workflow_engine.register_step_processor("video_composition", VideoCompositionProcessor())
    
    async def execute_complete_workflow(self, project_id: str, config: Dict[str, Any]):
        """完全なワークフローの実行"""
        
        # 実行計画の確認
        plan = self.workflow_engine.plan_execution("complete_video_generation", project_id)
        print(f"📋 実行計画:")
        print(f"   フェーズ数: {plan.total_phases}")
        print(f"   推定時間: {plan.estimated_total_time:.1f}秒")
        
        for i, phase_steps in enumerate(plan.phases):
            print(f"   フェーズ{i+1}: {', '.join(phase_steps)}")
        
        # 進捗監視
        progress_history = []
        
        def detailed_progress_callback(state: WorkflowExecutionState):
            progress_info = {
                "timestamp": datetime.now(),
                "completion_percentage": state.completion_percentage,
                "completed_steps": state.completed_steps,
                "running_steps": state.running_steps,
                "failed_steps": state.failed_steps,
                "estimated_remaining": state.estimate_remaining_time()
            }
            progress_history.append(progress_info)
            
            print(f"📊 [{progress_info['timestamp'].strftime('%H:%M:%S')}] "
                  f"進捗: {progress_info['completion_percentage']:.1f}%")
            print(f"   完了: {progress_info['completed_steps']}, "
                  f"実行中: {progress_info['running_steps']}, "
                  f"失敗: {progress_info['failed_steps']}")
            print(f"   残り推定時間: {progress_info['estimated_remaining']:.1f}秒")
        
        # ワークフロー実行
        try:
            result = await self.workflow_engine.execute_workflow(
                workflow_name="complete_video_generation",
                project_id=project_id,
                initial_input=config,
                progress_callback=detailed_progress_callback
            )
            
            # 詳細結果レポート
            self._print_execution_report(result, progress_history)
            return result
            
        except Exception as e:
            print(f"❌ ワークフロー実行中にエラー: {e}")
            return None
    
    def _print_execution_report(self, result: WorkflowExecutionResult, progress_history: List[Dict]):
        """実行結果の詳細レポート"""
        
        print("\n" + "="*60)
        print("📊 ワークフロー実行レポート")
        print("="*60)
        
        # 基本統計
        print(f"プロジェクトID: {result.project_id}")
        print(f"ワークフロー名: {result.workflow_name}")
        print(f"最終ステータス: {result.status.value}")
        print(f"実行時間: {result.execution_time_seconds:.1f}秒")
        print(f"成功率: {result.success_rate:.1%}")
        print(f"完了率: {result.completion_percentage:.1f}%")
        print()
        
        # ステップ別結果
        print("📝 ステップ別結果:")
        for step_name, step_result in result.step_results.items():
            status_icon = "✅" if step_result.is_successful else "❌"
            print(f"  {status_icon} {step_name}: {step_result.status.value}")
            if step_result.execution_time:
                print(f"      実行時間: {step_result.execution_time:.1f}秒")
            if not step_result.is_successful and step_result.error_message:
                print(f"      エラー: {step_result.error_message}")
        print()
        
        # 進捗履歴
        if progress_history:
            print("📈 進捗履歴:")
            for i, progress in enumerate(progress_history[::max(1, len(progress_history)//5)]):
                timestamp = progress["timestamp"].strftime("%H:%M:%S")
                print(f"  {timestamp}: {progress['completion_percentage']:.1f}% "
                      f"(完了: {progress['completed_steps']})")

# 使用例
async def run_complete_video_workflow():
    """完全な動画生成ワークフローの実行例"""
    
    workflow = VideoGenerationWorkflow()
    
    config = {
        "user_preferences": {
            "preferred_genres": ["プログラミング", "AI"],
            "target_audience": "エンジニア",
            "content_style": "実践的"
        },
        "video_settings": {
            "target_length_minutes": 10,
            "resolution": "1920x1080",
            "fps": 30
        },
        "voice_settings": {
            "reimu_speed": 1.0,
            "marisa_speed": 1.1
        }
    }
    
    result = await workflow.execute_complete_workflow("video-001", config)
    return result

# 実行
# result = asyncio.run(run_complete_video_workflow())
```

### ワークフロー制御機能

```python
async def workflow_control_example():
    """ワークフロー制御機能の使用例"""
    
    workflow_engine = WorkflowEngine(
        dependency_resolver=DependencyResolver(),
        resource_manager=ResourceManager()
    )
    
    project_id = "controllable-project"
    
    # 非同期でワークフロー開始
    workflow_task = asyncio.create_task(
        workflow_engine.execute_workflow(
            workflow_name="yukkuri_video_generation",
            project_id=project_id,
            initial_input={"test": True}
        )
    )
    
    # 少し待ってから制御操作
    await asyncio.sleep(2)
    
    # 実行状態確認
    execution_state = workflow_engine.get_execution_status(project_id)
    if execution_state:
        print(f"現在の進捗: {execution_state.completion_percentage:.1f}%")
    
    # 一時停止
    if workflow_engine.pause_workflow(project_id):
        print("🔄 ワークフローを一時停止しました")
        await asyncio.sleep(3)
        
        # 再開
        if workflow_engine.resume_workflow(project_id):
            print("▶️ ワークフローを再開しました")
    
    # 必要に応じてキャンセル
    # workflow_engine.cancel_workflow(project_id, "ユーザーによるキャンセル")
    
    # 完了まで待機
    try:
        result = await workflow_task
        print(f"ワークフロー完了: {result.is_successful}")
    except Exception as e:
        print(f"ワークフローエラー: {e}")

# 実行
# asyncio.run(workflow_control_example())
```

### エラーハンドリングと復旧

```python
from src.core.workflow_exceptions import (
    WorkflowEngineError, StepExecutionError, DependencyError, 
    ResourceLimitError, TimeoutError
)

class RobustWorkflowRunner:
    """堅牢なワークフロー実行者"""
    
    def __init__(self, workflow_engine: WorkflowEngine):
        self.workflow_engine = workflow_engine
        self.retry_config = {
            "max_retries": 3,
            "retry_delay": 5.0,
            "exponential_backoff": True
        }
    
    async def execute_with_error_handling(
        self, 
        workflow_name: str, 
        project_id: str, 
        initial_input: Dict[str, Any]
    ) -> WorkflowExecutionResult:
        """エラーハンドリング付きワークフロー実行"""
        
        for attempt in range(self.retry_config["max_retries"] + 1):
            try:
                print(f"🚀 ワークフロー実行試行 {attempt + 1}")
                
                # リソース可用性確認
                if not self.workflow_engine.check_resource_availability(workflow_name, project_id):
                    raise ResourceLimitError("必要なリソースが利用できません")
                
                # ワークフロー実行
                result = await self.workflow_engine.execute_workflow(
                    workflow_name=workflow_name,
                    project_id=project_id,
                    initial_input=initial_input,
                    progress_callback=self._create_error_aware_callback()
                )
                
                if result.is_successful:
                    print(f"✅ ワークフロー成功 (試行 {attempt + 1})")
                    return result
                else:
                    # 部分的失敗の場合
                    failed_steps = [
                        name for name, step_result in result.step_results.items()
                        if not step_result.is_successful
                    ]
                    print(f"⚠️ 部分的失敗: {failed_steps}")
                    
                    if attempt < self.retry_config["max_retries"]:
                        await self._handle_partial_failure(result, attempt)
                    else:
                        return result
                        
            except TimeoutError as e:
                print(f"⏰ タイムアウト: {e}")
                if attempt < self.retry_config["max_retries"]:
                    await self._handle_timeout_error(e, attempt)
                else:
                    raise
                    
            except ResourceLimitError as e:
                print(f"🚫 リソース不足: {e}")
                if attempt < self.retry_config["max_retries"]:
                    await self._handle_resource_error(e, attempt)
                else:
                    raise
                    
            except DependencyError as e:
                print(f"🔗 依存関係エラー: {e}")
                # 依存関係エラーはリトライしない
                raise
                
            except WorkflowEngineError as e:
                print(f"⚙️ ワークフローエンジンエラー: {e}")
                if attempt < self.retry_config["max_retries"]:
                    await self._handle_engine_error(e, attempt)
                else:
                    raise
        
        raise RuntimeError("ワークフローの実行に失敗しました")
    
    def _create_error_aware_callback(self):
        """エラー監視機能付き進捗コールバック"""
        
        def error_aware_callback(state: WorkflowExecutionState):
            # 通常の進捗表示
            print(f"📊 進捗: {state.completion_percentage:.1f}%")
            
            # エラー状態の監視
            if state.failed_steps > 0:
                print(f"❌ 失敗ステップ検出: {state.failed_steps}件")
                
                # 失敗ステップの詳細を取得
                failed_step_names = [
                    name for name, status in state.step_statuses.items()
                    if status == StepStatus.FAILED
                ]
                print(f"   失敗ステップ: {', '.join(failed_step_names)}")
            
            # 長時間実行の警告
            if state.estimate_remaining_time() > 1800:  # 30分超
                print("⚠️ 実行時間が予想より長くなっています")
        
        return error_aware_callback
    
    async def _handle_partial_failure(self, result: WorkflowExecutionResult, attempt: int):
        """部分的失敗の処理"""
        delay = self._calculate_retry_delay(attempt)
        print(f"🔄 {delay}秒後に失敗ステップを再実行します...")
        await asyncio.sleep(delay)
    
    async def _handle_timeout_error(self, error: TimeoutError, attempt: int):
        """タイムアウトエラーの処理"""
        delay = self._calculate_retry_delay(attempt)
        print(f"⏱️ タイムアウト後 {delay}秒待機...")
        await asyncio.sleep(delay)
    
    async def _handle_resource_error(self, error: ResourceLimitError, attempt: int):
        """リソースエラーの処理"""
        delay = self._calculate_retry_delay(attempt) * 2  # リソース回復のため長めに待機
        print(f"💾 リソース回復待機: {delay}秒...")
        await asyncio.sleep(delay)
    
    async def _handle_engine_error(self, error: WorkflowEngineError, attempt: int):
        """エンジンエラーの処理"""
        delay = self._calculate_retry_delay(attempt)
        print(f"⚙️ エンジン復旧待機: {delay}秒...")
        await asyncio.sleep(delay)
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """リトライ遅延時間の計算"""
        base_delay = self.retry_config["retry_delay"]
        if self.retry_config["exponential_backoff"]:
            return base_delay * (2 ** attempt)
        return base_delay

# 使用例
async def run_robust_workflow():
    """堅牢なワークフロー実行例"""
    
    workflow_engine = WorkflowEngine(
        dependency_resolver=DependencyResolver(),
        resource_manager=ResourceManager()
    )
    
    runner = RobustWorkflowRunner(workflow_engine)
    
    try:
        result = await runner.execute_with_error_handling(
            workflow_name="yukkuri_video_generation",
            project_id="robust-test",
            initial_input={"robust_mode": True}
        )
        
        print(f"最終結果: {'成功' if result.is_successful else '失敗'}")
        return result
        
    except Exception as e:
        print(f"回復不可能なエラー: {e}")
        return None

# 実行
# result = asyncio.run(run_robust_workflow())
```

## パフォーマンス最適化

### 並列実行の最適化

```python
class OptimizedWorkflowEngine:
    """最適化されたワークフローエンジン"""
    
    def __init__(self, base_engine: WorkflowEngine):
        self.base_engine = base_engine
        self.performance_metrics = {
            "execution_times": {},
            "resource_usage": {},
            "throughput": {}
        }
    
    async def execute_optimized_workflow(
        self, 
        workflow_name: str, 
        project_id: str, 
        initial_input: Dict[str, Any]
    ):
        """最適化されたワークフロー実行"""
        
        start_time = time.time()
        
        # 実行計画の最適化
        plan = self.base_engine.plan_execution(workflow_name, project_id)
        optimized_plan = self._optimize_execution_plan(plan)
        
        # リソース事前確保
        await self._pre_allocate_resources(optimized_plan)
        
        # 並列度の動的調整
        original_max_concurrent = self.base_engine.max_concurrent_steps
        optimal_concurrent = self._calculate_optimal_concurrency(plan)
        self.base_engine.max_concurrent_steps = optimal_concurrent
        
        try:
            # パフォーマンス監視付き実行
            result = await self.base_engine.execute_workflow(
                workflow_name=workflow_name,
                project_id=project_id, 
                initial_input=initial_input,
                progress_callback=self._create_performance_callback()
            )
            
            # メトリクス記録
            execution_time = time.time() - start_time
            self.performance_metrics["execution_times"][project_id] = execution_time
            
            print(f"⚡ 最適化実行完了: {execution_time:.1f}秒")
            return result
            
        finally:
            # 設定復元
            self.base_engine.max_concurrent_steps = original_max_concurrent
    
    def _optimize_execution_plan(self, plan: WorkflowExecutionPlan) -> WorkflowExecutionPlan:
        """実行計画の最適化"""
        # フェーズ内のステップ順序を依存関係とリソース使用量で最適化
        optimized_phases = []
        
        for phase_steps in plan.phases:
            # リソース競合を避けるようにステップを並び替え
            sorted_steps = self._sort_steps_by_resource_efficiency(phase_steps)
            optimized_phases.append(sorted_steps)
        
        return WorkflowExecutionPlan(
            project_id=plan.project_id,
            workflow_name=plan.workflow_name,
            phases=optimized_phases,
            total_phases=len(optimized_phases),
            estimated_total_time=plan.estimated_total_time * 0.8,  # 最適化による短縮
            resource_requirements=plan.resource_requirements
        )
    
    def _calculate_optimal_concurrency(self, plan: WorkflowExecutionPlan) -> int:
        """最適な並列度計算"""
        # 利用可能リソースとステップ特性から最適な並列度を計算
        max_parallel_in_phase = max(len(phase) for phase in plan.phases)
        resource_limited = len(plan.resource_requirements)
        
        return min(max_parallel_in_phase, resource_limited, 4)  # 上限4
    
    def _create_performance_callback(self):
        """パフォーマンス監視コールバック"""
        last_update = time.time()
        
        def performance_callback(state: WorkflowExecutionState):
            current_time = time.time()
            time_since_last = current_time - last_update
            
            # スループット計算
            if time_since_last > 0:
                steps_per_second = 1.0 / time_since_last if state.completed_steps > 0 else 0
                self.performance_metrics["throughput"][state.project_id] = steps_per_second
                
                print(f"⚡ スループット: {steps_per_second:.2f} ステップ/秒")
            
            nonlocal last_update
            last_update = current_time
        
        return performance_callback

# 使用例
async def run_optimized_workflow():
    base_engine = WorkflowEngine(
        dependency_resolver=DependencyResolver(),
        resource_manager=ResourceManager()
    )
    
    optimized_engine = OptimizedWorkflowEngine(base_engine)
    
    result = await optimized_engine.execute_optimized_workflow(
        workflow_name="yukkuri_video_generation",
        project_id="optimized-test",
        initial_input={"optimization_enabled": True}
    )
    
    return result
```

### リソース管理の最適化

```python
class SmartResourceManager(ResourceManager):
    """スマートリソース管理"""
    
    def __init__(self):
        super().__init__()
        self.resource_pool = {
            "llm_api": 3,           # LLM API同時接続数
            "tts_api": 2,           # TTS API同時接続数  
            "video_encoder": 1,     # 動画エンコーダー
            "storage": 5            # ストレージアクセス
        }
        self.usage_history = {}
        self.performance_stats = {}
    
    async def acquire_resource_smart(self, resource_name: str, step_name: str) -> bool:
        """スマートリソース取得"""
        
        # 使用履歴に基づく優先度調整
        priority_multiplier = self._calculate_priority_multiplier(resource_name, step_name)
        
        # リソースプールの動的調整
        if self._should_expand_pool(resource_name):
            self.resource_pool[resource_name] += 1
            print(f"📈 リソースプール拡張: {resource_name} -> {self.resource_pool[resource_name]}")
        
        # 通常のリソース取得
        acquired = await super().acquire_resource(resource_name)
        
        if acquired:
            # 使用履歴記録
            self._record_resource_usage(resource_name, step_name)
        
        return acquired
    
    def _calculate_priority_multiplier(self, resource_name: str, step_name: str) -> float:
        """優先度乗数計算"""
        # 過去の実行時間から優先度を計算
        if step_name in self.performance_stats:
            avg_time = self.performance_stats[step_name].get("avg_execution_time", 60.0)
            if avg_time > 300:  # 5分超の場合は高優先度
                return 1.5
            elif avg_time < 30:  # 30秒未満は低優先度
                return 0.8
        return 1.0
    
    def _should_expand_pool(self, resource_name: str) -> bool:
        """プール拡張判定"""
        current_size = self.resource_pool.get(resource_name, 0)
        usage_rate = self._get_resource_usage_rate(resource_name)
        
        # 使用率が80%超で、かつプールサイズが上限未満の場合
        return usage_rate > 0.8 and current_size < 5

# 使用例 
smart_resource_manager = SmartResourceManager()
workflow_engine = WorkflowEngine(
    dependency_resolver=DependencyResolver(),
    resource_manager=smart_resource_manager,
    max_concurrent_steps=4
)
``` 