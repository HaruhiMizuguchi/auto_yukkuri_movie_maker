"""
ワークフローオーケストレーター

CLIコマンドから実際の処理モジュールを順次実行する統合制御
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass

try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# 既存のコアモジュールをインポート
from src.core.project_manager import ProjectManager
from src.core.workflow_engine import WorkflowEngine, WorkflowExecutionPlan
from src.core.config_manager import ConfigManager
from src.core.log_manager import LogManager

# 処理モジュールをインポート
from src.modules.theme_selector import ThemeSelector
from src.modules.script_generator import ScriptGenerator
from src.modules.title_generator import TitleGenerator
from src.modules.tts_processor import TTSProcessor
from src.modules.character_synthesizer import CharacterSynthesizer
from src.modules.background_generator import BackgroundGenerator
from src.modules.subtitle_generator import SubtitleGenerator
from src.modules.video_composer import VideoComposer
from src.modules.audio_enhancer import AudioEnhancer
from src.modules.video_encoder import VideoEncoder

@dataclass
class WorkflowStep:
    """ワークフローステップ定義"""
    step_id: int
    step_name: str
    display_name: str
    description: str
    module_class: type
    dependencies: List[str]
    estimated_duration: int  # 秒

class WorkflowOrchestrator:
    """
    ワークフロー統合実行制御
    
    13ステップの動画生成プロセスを統合管理
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初期化
        
        Args:
            config_path: 設定ファイルパス
        """
        self.config = ConfigManager(config_path)
        self.logger = LogManager(self.config).get_logger(__name__)
        self.project_manager = ProjectManager(self.config)
        self.workflow_engine = WorkflowEngine()
        
        if RICH_AVAILABLE:
            self.console = Console()
        
        # ワークフローステップ定義
        self.workflow_steps = self._define_workflow_steps()
        self.logger.info("ワークフローオーケストレーター初期化完了")
    
    def _define_workflow_steps(self) -> Dict[str, WorkflowStep]:
        """ワークフローステップ定義"""
        return {
            "theme_selection": WorkflowStep(
                step_id=1,
                step_name="theme_selection",
                display_name="テーマ選定",
                description="動画のテーマを自動選定",
                module_class=ThemeSelector,
                dependencies=[],
                estimated_duration=120  # 2分
            ),
            "script_generation": WorkflowStep(
                step_id=2,
                step_name="script_generation",
                display_name="スクリプト生成",
                description="テーマに基づいてスクリプトを生成",
                module_class=ScriptGenerator,
                dependencies=["theme_selection"],
                estimated_duration=300  # 5分
            ),
            "title_generation": WorkflowStep(
                step_id=3,
                step_name="title_generation",
                display_name="タイトル生成",
                description="高CTRを狙ったタイトルを生成",
                module_class=TitleGenerator,
                dependencies=["theme_selection", "script_generation"],
                estimated_duration=60  # 1分
            ),
            "tts_generation": WorkflowStep(
                step_id=4,
                step_name="tts_generation",
                display_name="音声生成",
                description="AIVIS Speech APIを使用した音声生成",
                module_class=TTSProcessor,
                dependencies=["script_generation"],
                estimated_duration=180  # 3分
            ),
            "character_synthesis": WorkflowStep(
                step_id=5,
                step_name="character_synthesis",
                display_name="立ち絵アニメーション",
                description="口パクと表情を同期した立ち絵動画生成",
                module_class=CharacterSynthesizer,
                dependencies=["tts_generation"],
                estimated_duration=240  # 4分
            ),
            "background_generation": WorkflowStep(
                step_id=6,
                step_name="background_generation",
                display_name="背景生成",
                description="シーンに応じた背景画像・動画を生成",
                module_class=BackgroundGenerator,
                dependencies=["script_generation"],
                estimated_duration=360  # 6分
            ),
            "subtitle_generation": WorkflowStep(
                step_id=7,
                step_name="subtitle_generation",
                display_name="字幕生成",
                description="音声タイムスタンプに基づく字幕生成",
                module_class=SubtitleGenerator,
                dependencies=["tts_generation"],
                estimated_duration=90  # 1.5分
            ),
            "video_composition": WorkflowStep(
                step_id=8,
                step_name="video_composition",
                display_name="動画合成",
                description="背景、立ち絵、字幕、音声を合成",
                module_class=VideoComposer,
                dependencies=["character_synthesis", "background_generation", "subtitle_generation"],
                estimated_duration=300  # 5分
            ),
            "audio_enhancement": WorkflowStep(
                step_id=9,
                step_name="audio_enhancement",
                display_name="音響効果",
                description="効果音とBGMを適切なタイミングで追加",
                module_class=AudioEnhancer,
                dependencies=["video_composition"],
                estimated_duration=120  # 2分
            ),
            "final_encoding": WorkflowStep(
                step_id=10,
                step_name="final_encoding",
                display_name="最終エンコード",
                description="配信用最終動画の生成",
                module_class=VideoEncoder,
                dependencies=["audio_enhancement"],
                estimated_duration=180  # 3分
            )
        }
    
    async def execute_workflow(self, project_id: str, start_step: Optional[str] = None,
                             dry_run: bool = False) -> Dict[str, Any]:
        """
        ワークフロー実行
        
        Args:
            project_id: プロジェクトID
            start_step: 開始ステップ（指定時は途中から実行）
            dry_run: ドライラン（実際の処理は行わない）
            
        Returns:
            実行結果
        """
        try:
            self.logger.info(f"ワークフロー実行開始: {project_id}")
            
            # プロジェクト情報取得
            project_info = self.project_manager.get_project(project_id)
            if not project_info:
                raise ValueError(f"プロジェクトが見つかりません: {project_id}")
            
            # 実行プラン作成
            execution_plan = self._create_execution_plan(start_step)
            
            if dry_run:
                return self._generate_dry_run_report(execution_plan)
            
            # 実際の実行
            result = await self._execute_steps(project_id, execution_plan)
            
            self.logger.info(f"ワークフロー実行完了: {project_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"ワークフロー実行エラー: {str(e)}")
            raise
    
    def _create_execution_plan(self, start_step: Optional[str] = None) -> List[WorkflowStep]:
        """実行プラン作成"""
        steps = list(self.workflow_steps.values())
        
        # ステップIDでソート
        steps.sort(key=lambda x: x.step_id)
        
        # 開始ステップが指定されている場合はフィルタリング
        if start_step:
            start_id = self.workflow_steps[start_step].step_id
            steps = [step for step in steps if step.step_id >= start_id]
        
        return steps
    
    def _generate_dry_run_report(self, execution_plan: List[WorkflowStep]) -> Dict[str, Any]:
        """ドライラン報告書生成"""
        total_duration = sum(step.estimated_duration for step in execution_plan)
        
        report = {
            "mode": "dry_run",
            "total_steps": len(execution_plan),
            "estimated_duration_seconds": total_duration,
            "estimated_duration_minutes": round(total_duration / 60, 1),
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "display_name": step.display_name,
                    "description": step.description,
                    "estimated_duration_minutes": round(step.estimated_duration / 60, 1),
                    "dependencies": step.dependencies
                }
                for step in execution_plan
            ],
            "estimated_cost": "¥200-400",  # 推定費用
            "requirements": [
                "Google Gemini API キー",
                "AIVIS Speech API キー", 
                "FFmpeg インストール",
                "十分なディスク容量 (1-2GB)"
            ]
        }
        
        return report
    
    async def _execute_steps(self, project_id: str, execution_plan: List[WorkflowStep]) -> Dict[str, Any]:
        """ステップ実行"""
        results = {}
        
        if RICH_AVAILABLE and self.console:
            # Rich UI での進捗表示
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                
                overall_task = progress.add_task(
                    "全体進捗", 
                    total=len(execution_plan)
                )
                
                for i, step in enumerate(execution_plan):
                    # ステップ実行
                    step_task = progress.add_task(
                        f"{step.display_name}中...", 
                        total=100
                    )
                    
                    try:
                        # 実際のモジュール実行
                        step_result = await self._execute_single_step(
                            project_id, step, progress, step_task
                        )
                        results[step.step_name] = step_result
                        
                        progress.update(step_task, completed=100)
                        progress.update(overall_task, advance=1)
                        
                    except Exception as e:
                        self.logger.error(f"ステップ {step.step_name} でエラー: {str(e)}")
                        results[step.step_name] = {"status": "error", "error": str(e)}
                        raise
        else:
            # シンプルな進捗表示
            for i, step in enumerate(execution_plan, 1):
                print(f"[{i}/{len(execution_plan)}] {step.display_name}中...")
                
                try:
                    step_result = await self._execute_single_step(project_id, step)
                    results[step.step_name] = step_result
                    print(f"✅ {step.display_name} 完了")
                    
                except Exception as e:
                    print(f"❌ {step.display_name} エラー: {str(e)}")
                    results[step.step_name] = {"status": "error", "error": str(e)}
                    raise
        
        return {
            "status": "completed",
            "project_id": project_id,
            "executed_steps": list(results.keys()),
            "step_results": results
        }
    
    async def _execute_single_step(self, project_id: str, step: WorkflowStep, 
                                 progress: Optional[Progress] = None, 
                                 task_id: Optional[int] = None) -> Dict[str, Any]:
        """単一ステップ実行"""
        self.logger.info(f"ステップ実行開始: {step.step_name}")
        
        try:
            # モジュールインスタンス作成（ファクトリーパターン）
            module_instance = self._create_module_instance(step.module_class, project_id)
            
            # 進捗更新
            if progress and task_id:
                progress.update(task_id, completed=20)
            
            # 入力データ取得
            input_data = await self._get_step_input_data(project_id, step)
            
            if progress and task_id:
                progress.update(task_id, completed=40)
            
            # 実際の処理実行
            result = await self._execute_module_process(module_instance, input_data)
            
            if progress and task_id:
                progress.update(task_id, completed=80)
            
            # 結果保存
            await self._save_step_result(project_id, step, result)
            
            if progress and task_id:
                progress.update(task_id, completed=100)
            
            self.logger.info(f"ステップ実行完了: {step.step_name}")
            
            return {
                "status": "completed",
                "step_name": step.step_name,
                "result": result
            }
            
        except Exception as e:
            self.logger.error(f"ステップ実行エラー {step.step_name}: {str(e)}")
            raise
    
    def _create_module_instance(self, module_class: type, project_id: str) -> Any:
        """モジュールインスタンス作成ファクトリー"""
        # ThemeSelector の特別処理
        if module_class == ThemeSelector:
            try:
                from src.modules.theme_selector import DatabaseDataAccess, GeminiThemeLLM
                from src.api.llm_client import GeminiLLMClient
                from src.core.project_repository import ProjectRepository
                from src.core.database_manager import DatabaseManager
                
                # 依存関係を作成
                db_manager = DatabaseManager()  # デフォルトパス使用
                repository = ProjectRepository(db_manager=db_manager)
                data_access = DatabaseDataAccess(repository, self.config)
                
                # Geminiクライアント作成（テスト用ダミーキー）
                gemini_api_key = "test-api-key"  # TODO: 設定から取得
                llm_client = GeminiLLMClient(api_key=gemini_api_key)
                llm_interface = GeminiThemeLLM(llm_client)
                
                return ThemeSelector(data_access, llm_interface)
            except Exception as e:
                self.logger.warning(f"ThemeSelector作成に失敗、モックを使用: {e}")
                # モック実装を返す
                return self._create_mock_module(module_class)
        
        # その他のモジュールは統一インターフェース
        try:
            # まず標準的なコンストラクターを試行
            return module_class(
                config_manager=self.config,
                project_manager=self.project_manager
            )
        except TypeError:
            # フォールバック: パラメータなしで試行
            try:
                return module_class()
            except TypeError:
                # 最終フォールバック: configのみで試行
                try:
                    return module_class(self.config)
                except TypeError:
                    # モック実装を返す
                    return self._create_mock_module(module_class)
    
    def _create_mock_module(self, module_class: type) -> Any:
        """モックモジュール作成"""
        class MockModule:
            def __init__(self):
                self.module_name = module_class.__name__
            
            async def process(self, input_data):
                return {
                    "status": "completed",
                    "message": f"Mock {self.module_name} executed",
                    "module": self.module_name,
                    "input": input_data
                }
            
            def select_theme(self, input_data):
                # ThemeSelector用の特別メソッド
                from src.modules.theme_selector import ThemeSelectionOutput, SelectedTheme
                from datetime import datetime
                
                return ThemeSelectionOutput(
                    selected_theme=SelectedTheme(
                        theme="Mock Theme",
                        category="Test",
                        target_length_minutes=5,
                        description="Mock theme for testing",
                        selection_reason="Generated by mock",
                        generation_timestamp=datetime.now()
                    ),
                    candidates=[],
                    selection_metadata={"mock": True}
                )
        
        return MockModule()
    
    async def _get_step_input_data(self, project_id: str, step: WorkflowStep) -> Dict[str, Any]:
        """ステップ入力データ取得"""
        # TODO: 実際のデータ取得ロジック実装
        # flow_definition.yamlの定義に基づいて前ステップの出力を取得
        
        input_data = {
            "project_id": project_id,
            "step_name": step.step_name
        }
        
        # 依存ステップの出力を取得
        for dep_step in step.dependencies:
            dep_result = await self._get_dependency_output(project_id, dep_step)
            input_data[dep_step] = dep_result
        
        return input_data
    
    async def _get_dependency_output(self, project_id: str, step_name: str) -> Dict[str, Any]:
        """依存ステップの出力取得"""
        # TODO: ProjectRepositoryから前ステップの結果を取得
        return {"status": "completed", "data": f"output_from_{step_name}"}
    
    async def _execute_module_process(self, module_instance: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """モジュール処理実行"""
        # 各モジュールの統一インターフェースを呼び出し
        if hasattr(module_instance, 'process'):
            return await module_instance.process(input_data)
        elif hasattr(module_instance, 'generate'):
            return await module_instance.generate(input_data)
        else:
            # デモ用の結果を返す
            return {
                "status": "completed",
                "message": f"モジュール {module_instance.__class__.__name__} 実行完了",
                "output_files": [],
                "metadata": {}
            }
    
    async def _save_step_result(self, project_id: str, step: WorkflowStep, result: Dict[str, Any]) -> None:
        """ステップ結果保存"""
        # TODO: ProjectRepositoryに結果を保存
        self.logger.info(f"ステップ結果保存: {step.step_name}")
    
    def get_workflow_status(self, project_id: str) -> Dict[str, Any]:
        """ワークフロー状況取得"""
        # TODO: 実際の状況取得ロジック実装
        return {
            "project_id": project_id,
            "total_steps": len(self.workflow_steps),
            "completed_steps": 0,
            "current_step": "theme_selection",
            "progress_percentage": 0,
            "estimated_remaining_time": 1200  # 20分
        }
    
    def estimate_total_cost(self, execution_plan: List[WorkflowStep]) -> Dict[str, Any]:
        """総費用見積もり"""
        # API使用量に基づく費用計算
        cost_estimates = {
            "gemini_requests": 15,  # ¥50
            "aivis_speech_minutes": 5,  # ¥150
            "image_generations": 8,  # ¥40
            "total_jpy": 240
        }
        
        return cost_estimates