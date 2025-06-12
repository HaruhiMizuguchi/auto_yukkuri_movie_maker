"""
Phase 2: 契約テスト例（プロジェクトの次段階で実装予定）

インターフェース固定・重要統合テストの例
"""

import pytest
from typing import Protocol, Dict, Any, List, Optional
from abc import ABC, abstractmethod


# 契約定義：ワークフローエンジン
class WorkflowStepResult(Protocol):
    """ステップ実行結果の契約"""
    success: bool
    output: Dict[str, Any]
    error_message: Optional[str]
    execution_time: float


class WorkflowEngineContract(ABC):
    """ワークフローエンジンの契約（インターフェース固定）"""
    
    @abstractmethod
    def execute_step(self, step_name: str, input_data: Dict[str, Any]) -> WorkflowStepResult:
        """ステップ実行（契約確定）"""
        pass
    
    @abstractmethod
    def get_step_dependencies(self, step_name: str) -> List[str]:
        """依存関係取得（契約確定）"""
        pass
    
    @abstractmethod
    def validate_step_input(self, step_name: str, input_data: Dict[str, Any]) -> bool:
        """入力検証（契約確定）"""
        pass


# 契約テスト：実装に依存しない
class TestWorkflowEngineContract:
    """ワークフローエンジン契約テスト（Phase 2）"""
    
    @pytest.fixture
    def workflow_engine(self):
        """実装は自由、契約のみチェック"""
        # この時点では具体実装は決めない
        from src.workflow.concrete_engine import ConcreteWorkflowEngine
        return ConcreteWorkflowEngine()
    
    def test_execute_step_contract(self, workflow_engine):
        """ステップ実行契約の検証"""
        result = workflow_engine.execute_step(
            "theme_selection", 
            {"user_preferences": {"genre": "tech"}}
        )
        
        # 契約チェック（型・必須属性のみ）
        assert hasattr(result, 'success')
        assert hasattr(result, 'output')
        assert hasattr(result, 'error_message')
        assert hasattr(result, 'execution_time')
        
        assert isinstance(result.success, bool)
        assert isinstance(result.output, dict)
        assert isinstance(result.execution_time, (int, float))
        
        if not result.success:
            assert result.error_message is not None
    
    def test_dependency_management_contract(self, workflow_engine):
        """依存関係管理契約の検証"""
        deps = workflow_engine.get_step_dependencies("script_generation")
        
        # 契約チェック
        assert isinstance(deps, list)
        assert all(isinstance(dep, str) for dep in deps)
        
        # 基本的な依存関係の妥当性
        assert "theme_selection" in deps  # 論理的依存関係


# 重要統合テスト：リスク高い部分のみ（Phase 2）
class TestCriticalIntegrations:
    """重要統合テスト（データ整合性等のリスク高い部分）"""
    
    def test_database_workflow_integration(self):
        """データベース-ワークフロー統合（重要）"""
        # 実データベース使用（リスク回避のため）
        db_manager = DatabaseManager(":memory:")
        db_manager.initialize()
        
        engine = WorkflowEngine(db_manager=db_manager)
        
        # 重要：データ整合性確保
        result = engine.execute_step("database_operation", {})
        
        # データベース状態の検証
        assert db_manager.verify_integrity()
        
        # トランザクション整合性の確認
        if not result.success:
            # 失敗時はロールバックされているか
            assert db_manager.get_transaction_count() == 0
    
    def test_file_system_workflow_integration(self):
        """ファイルシステム-ワークフロー統合（重要）"""
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_manager = FileSystemManager(base_dir=temp_dir)
            engine = WorkflowEngine(file_manager=file_manager)
            
            # ファイル操作を含むステップ実行
            result = engine.execute_step("file_generation", {
                "output_path": "test_output.json"
            })
            
            if result.success:
                # 成功時はファイルが作成されているか
                assert file_manager.file_exists("test_output.json")
            else:
                # 失敗時は中間ファイルがクリーンアップされているか
                assert not file_manager.has_temporary_files()


# リスク駆動テスト戦略
CRITICAL_INTEGRATIONS = [
    "database_operations",
    "external_api_calls", 
    "file_system_operations",
    "workflow_state_management"
]

def test_integration_by_risk_level(integration_name):
    """リスクレベル別統合テスト"""
    if integration_name in CRITICAL_INTEGRATIONS:
        # 高リスク：実環境統合テスト
        run_real_integration_test(integration_name)
    else:
        # 低リスク：モック使用
        run_mocked_unit_test(integration_name)


def run_real_integration_test(integration_name):
    """実環境での統合テスト"""
    # データベース、ファイルシステム等の実環境使用
    pass


def run_mocked_unit_test(integration_name):
    """モックによる単体テスト"""
    # 外部依存をモック化
    pass 