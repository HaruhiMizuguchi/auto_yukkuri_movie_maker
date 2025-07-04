"""
ワークフローオーケストレーターのテスト（TDD）

Red段階: まずテストを書いて失敗させる
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class TestWorkflowOrchestrator:
    """ワークフローオーケストレーターのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        # モックオブジェクトを作成
        self.mock_config = Mock()
        self.mock_project_manager = Mock()
        self.mock_logger = Mock()
        
    def test_workflow_orchestrator_initialization(self):
        """オーケストレーター初期化のテスト"""
        # GIVEN: 設定パスが与えられた時
        config_path = "test_config.yaml"
        
        # WHEN: オーケストレーターを初期化する
        with patch('src.cli.core.workflow_orchestrator.ConfigManager') as mock_config_manager, \
             patch('src.cli.core.workflow_orchestrator.LogManager') as mock_log_manager, \
             patch('src.cli.core.workflow_orchestrator.ProjectManager') as mock_project_manager, \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine') as mock_workflow_engine:
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator(config_path)
            
            # THEN: 必要なコンポーネントが初期化される
            mock_config_manager.assert_called_once_with(config_path)
            mock_log_manager.assert_called_once()
            mock_project_manager.assert_called_once()
            mock_workflow_engine.assert_called_once()
            
            # AND: ワークフローステップが定義される
            assert hasattr(orchestrator, 'workflow_steps')
            assert len(orchestrator.workflow_steps) == 10  # 10ステップ定義されている
    
    def test_workflow_steps_definition(self):
        """ワークフローステップ定義のテスト"""
        # GIVEN: オーケストレーターが初期化された時
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager'), \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # WHEN: ワークフローステップを取得する
            steps = orchestrator.workflow_steps
            
            # THEN: 必要なステップが定義されている
            expected_steps = [
                "theme_selection",
                "script_generation", 
                "title_generation",
                "tts_generation",
                "character_synthesis",
                "background_generation",
                "subtitle_generation",
                "video_composition",
                "audio_enhancement",
                "final_encoding"
            ]
            
            for step_name in expected_steps:
                assert step_name in steps
                assert hasattr(steps[step_name], 'step_id')
                assert hasattr(steps[step_name], 'display_name')
                assert hasattr(steps[step_name], 'module_class')
                assert hasattr(steps[step_name], 'dependencies')
                assert hasattr(steps[step_name], 'estimated_duration')
    
    def test_workflow_step_dependencies(self):
        """ワークフローステップ依存関係のテスト"""
        # GIVEN: オーケストレーターが初期化された時
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager'), \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            steps = orchestrator.workflow_steps
            
            # THEN: 依存関係が正しく定義されている
            assert steps["theme_selection"].dependencies == []
            assert "theme_selection" in steps["script_generation"].dependencies
            assert "script_generation" in steps["tts_generation"].dependencies
            assert "tts_generation" in steps["character_synthesis"].dependencies
            assert "tts_generation" in steps["subtitle_generation"].dependencies
            
            # AND: 動画合成は複数の依存関係を持つ
            video_deps = steps["video_composition"].dependencies
            assert "character_synthesis" in video_deps
            assert "background_generation" in video_deps
            assert "subtitle_generation" in video_deps
    
    @pytest.mark.asyncio
    async def test_execute_workflow_dry_run(self):
        """ドライラン実行のテスト"""
        # GIVEN: オーケストレーターとプロジェクトIDが与えられた時
        project_id = "test-project-123"
        
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager') as mock_pm, \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            # プロジェクト存在をモック
            mock_pm.return_value.get_project.return_value = {"id": project_id, "name": "Test Project"}
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # WHEN: ドライランを実行する
            result = await orchestrator.execute_workflow(project_id, dry_run=True)
            
            # THEN: ドライラン結果が返される
            assert result["mode"] == "dry_run"
            assert result["total_steps"] == 10
            assert "estimated_duration_minutes" in result
            assert "estimated_cost" in result
            assert "steps" in result
            assert len(result["steps"]) == 10
            
            # AND: 各ステップに必要な情報が含まれる
            for step in result["steps"]:
                assert "step_id" in step
                assert "step_name" in step
                assert "display_name" in step
                assert "estimated_duration_minutes" in step
    
    @pytest.mark.asyncio
    async def test_execute_workflow_real_execution(self):
        """実際のワークフロー実行のテスト"""
        # GIVEN: オーケストレーターとプロジェクトIDが与えられた時
        project_id = "test-project-123"
        
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager') as mock_pm, \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            # プロジェクト存在をモック
            mock_pm.return_value.get_project.return_value = {"id": project_id, "name": "Test Project"}
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # ステップ実行をモック
            with patch.object(orchestrator, '_execute_steps', new=AsyncMock()) as mock_execute:
                mock_execute.return_value = {
                    "status": "completed",
                    "project_id": project_id,
                    "executed_steps": ["theme_selection", "script_generation"],
                    "step_results": {}
                }
                
                # WHEN: 実際のワークフローを実行する
                result = await orchestrator.execute_workflow(project_id, dry_run=False)
                
                # THEN: 実行結果が返される
                assert result["status"] == "completed"
                assert result["project_id"] == project_id
                assert "executed_steps" in result
                assert "step_results" in result
    
    @pytest.mark.asyncio
    async def test_execute_workflow_with_start_step(self):
        """特定ステップからの実行のテスト"""
        # GIVEN: オーケストレーターとプロジェクトID、開始ステップが与えられた時
        project_id = "test-project-123"
        start_step = "tts_generation"
        
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager') as mock_pm, \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            mock_pm.return_value.get_project.return_value = {"id": project_id}
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # WHEN: 特定ステップから実行する
            execution_plan = orchestrator._create_execution_plan(start_step)
            
            # THEN: 指定ステップ以降のみが含まれる
            step_names = [step.step_name for step in execution_plan]
            assert "theme_selection" not in step_names  # 前のステップは含まれない
            assert "script_generation" not in step_names
            assert "title_generation" not in step_names
            assert "tts_generation" in step_names  # 指定ステップ以降は含まれる
            assert "character_synthesis" in step_names
    
    def test_create_execution_plan(self):
        """実行プラン作成のテスト"""
        # GIVEN: オーケストレーターが初期化された時
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager'), \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # WHEN: 実行プランを作成する
            execution_plan = orchestrator._create_execution_plan()
            
            # THEN: 正しい順序でステップが並ぶ
            assert len(execution_plan) == 10
            
            # AND: ステップIDが昇順になっている
            step_ids = [step.step_id for step in execution_plan]
            assert step_ids == sorted(step_ids)
            
            # AND: 最初はテーマ選定、最後は最終エンコード
            assert execution_plan[0].step_name == "theme_selection"
            assert execution_plan[-1].step_name == "final_encoding"
    
    def test_generate_dry_run_report(self):
        """ドライラン報告書生成のテスト"""
        # GIVEN: オーケストレーターと実行プランが与えられた時
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager'), \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            execution_plan = orchestrator._create_execution_plan()
            
            # WHEN: ドライラン報告書を生成する
            report = orchestrator._generate_dry_run_report(execution_plan)
            
            # THEN: 必要な情報が含まれる
            assert report["mode"] == "dry_run"
            assert report["total_steps"] == 10
            assert "estimated_duration_seconds" in report
            assert "estimated_duration_minutes" in report
            assert "estimated_cost" in report
            assert "requirements" in report
            assert len(report["steps"]) == 10
    
    @pytest.mark.asyncio
    async def test_execute_single_step(self):
        """単一ステップ実行のテスト"""
        # GIVEN: オーケストレーターとステップが与えられた時
        project_id = "test-project-123"
        
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager'), \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator, WorkflowStep
            from src.modules.theme_selector import ThemeSelector
            
            orchestrator = WorkflowOrchestrator()
            
            # テストステップを作成
            test_step = WorkflowStep(
                step_id=1,
                step_name="test_step",
                display_name="テストステップ",
                description="テスト用",
                module_class=ThemeSelector,
                dependencies=[],
                estimated_duration=60
            )
            
            # 依存メソッドをモック
            with patch.object(orchestrator, '_get_step_input_data', new=AsyncMock()) as mock_input, \
                 patch.object(orchestrator, '_execute_module_process', new=AsyncMock()) as mock_process, \
                 patch.object(orchestrator, '_save_step_result', new=AsyncMock()) as mock_save:
                
                mock_input.return_value = {"test": "input"}
                mock_process.return_value = {"status": "completed", "result": "test_output"}
                
                # WHEN: 単一ステップを実行する
                result = await orchestrator._execute_single_step(project_id, test_step)
                
                # THEN: 正しい結果が返される
                assert result["status"] == "completed"
                assert result["step_name"] == "test_step"
                assert "result" in result
                
                # AND: 必要なメソッドが呼び出される
                mock_input.assert_called_once()
                mock_process.assert_called_once()
                mock_save.assert_called_once()
    
    def test_get_workflow_status(self):
        """ワークフロー状況取得のテスト"""
        # GIVEN: オーケストレーターとプロジェクトIDが与えられた時
        project_id = "test-project-123"
        
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager'), \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # WHEN: ワークフロー状況を取得する
            status = orchestrator.get_workflow_status(project_id)
            
            # THEN: 必要な状況情報が含まれる
            assert status["project_id"] == project_id
            assert "total_steps" in status
            assert "completed_steps" in status
            assert "current_step" in status
            assert "progress_percentage" in status
            assert "estimated_remaining_time" in status
    
    def test_estimate_total_cost(self):
        """総費用見積もりのテスト"""
        # GIVEN: オーケストレーターと実行プランが与えられた時
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager'), \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            execution_plan = orchestrator._create_execution_plan()
            
            # WHEN: 総費用を見積もる
            cost = orchestrator.estimate_total_cost(execution_plan)
            
            # THEN: 費用情報が含まれる
            assert "gemini_requests" in cost
            assert "aivis_speech_minutes" in cost
            assert "image_generations" in cost
            assert "total_jpy" in cost
            assert isinstance(cost["total_jpy"], (int, float))
    
    @pytest.mark.asyncio
    async def test_execute_workflow_project_not_found(self):
        """プロジェクトが見つからない場合のテスト"""
        # GIVEN: 存在しないプロジェクトIDが与えられた時
        project_id = "non-existent-project"
        
        with patch('src.cli.core.workflow_orchestrator.ConfigManager'), \
             patch('src.cli.core.workflow_orchestrator.LogManager'), \
             patch('src.cli.core.workflow_orchestrator.ProjectManager') as mock_pm, \
             patch('src.cli.core.workflow_orchestrator.WorkflowEngine'):
            
            # プロジェクトが見つからない場合をモック
            mock_pm.return_value.get_project.return_value = None
            
            from src.cli.core.workflow_orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # WHEN: ワークフローを実行する
            # THEN: ValueErrorが発生する
            with pytest.raises(ValueError, match="プロジェクトが見つかりません"):
                await orchestrator.execute_workflow(project_id)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])