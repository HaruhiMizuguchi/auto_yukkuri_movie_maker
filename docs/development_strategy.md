# 段階的TDD戦略：柔軟性と品質のバランス

## 🎯 戦略概要

統合テストによる過度な制約を避けながら、品質を確保する段階的アプローチ。

## 📊 開発段階別戦略

### Phase 1: 探索・プロトタイプ段階 (柔軟性最優先)

**目標**: 技術選択・アーキテクチャ探索・創造的実装
**期間**: 1-2週間
**テスト戦略**: 単体テストのみ + モック多用

```python
# Phase 1 例：新機能の探索的実装
class WorkflowEngine:
    def __init__(self, config=None):
        self.config = config or {}
        # 実装詳細は自由に変更可能
    
    def execute_step(self, step_name: str) -> bool:
        # TODO: 実装方法を実験中
        pass

# テスト：実装詳細にコミットしない
@pytest.fixture
def mock_engine():
    return Mock(spec=WorkflowEngine)

def test_workflow_concept(mock_engine):
    """コンセプト検証のみ"""
    mock_engine.execute_step.return_value = True
    assert mock_engine.execute_step("test") == True
```

**利点**:
- 実装方法を自由に変更可能
- 技術選択を後回しにできる
- 迅速なプロトタイピング
- 創造的解決策の探索

**制約**:
- 統合テストなし（意図的）
- インターフェース未固定
- 品質より速度優先

### Phase 2: 安定化・MVP段階 (バランス重視)

**目標**: インターフェース固定・基本品質確保
**期間**: 2-3週間  
**テスト戦略**: 単体テスト + 契約テスト + 重要統合テスト

```python
# Phase 2 例：インターフェース固定化
from abc import ABC, abstractmethod
from typing import Protocol

class WorkflowStepResult(Protocol):
    """ステップ実行結果の契約"""
    success: bool
    output: Dict[str, Any] 
    error_message: Optional[str]

class WorkflowEngine(ABC):
    """ワークフローエンジンの契約"""
    
    @abstractmethod
    def execute_step(self, step_name: str) -> WorkflowStepResult:
        """ステップ実行（契約固定）"""
        pass
    
    @abstractmethod
    def get_step_dependencies(self, step_name: str) -> List[str]:
        """依存関係取得（契約固定）"""
        pass

# 契約テスト：インターフェースのみ検証
def test_workflow_contract():
    """契約遵守の検証"""
    engine = ConcreteWorkflowEngine()
    result = engine.execute_step("test_step")
    
    # 契約チェック（型・必須属性）
    assert hasattr(result, 'success')
    assert hasattr(result, 'output') 
    assert hasattr(result, 'error_message')
    assert isinstance(result.success, bool)

# 重要統合テスト：リスク高い部分のみ
def test_critical_integration():
    """データベース整合性のような重要な統合"""
    engine = ConcreteWorkflowEngine()
    db_manager = DatabaseManager(":memory:")
    
    # 重要：データ整合性確保
    result = engine.execute_step("database_operation")
    assert db_manager.verify_integrity()
```

**利点**:
- インターフェース安定化
- 重要リスクの早期発見
- 実装詳細は依然自由
- 段階的品質向上

### Phase 3: 本格実装段階 (品質最優先)

**目標**: プロダクション品質・完全テストカバレッジ
**期間**: 3-4週間
**テスト戦略**: 全レベルテスト + E2E + パフォーマンステスト

```python
# Phase 3 例：本格的品質保証
class ProductionWorkflowEngine(WorkflowEngine):
    """本格実装：全ての品質要件を満たす"""
    
    def __init__(self, db_manager: DatabaseManager, 
                 log_manager: LogManager,
                 config: Dict[str, Any]):
        self.db_manager = db_manager
        self.log_manager = log_manager
        self.config = config
        self._validate_configuration()
    
    def execute_step(self, step_name: str) -> WorkflowStepResult:
        """本格実装：エラーハンドリング・ログ・メトリクス完備"""
        try:
            with self.log_manager.operation_context(f"step_{step_name}"):
                # 実装詳細は Phase 1-2 で確立済み
                return self._execute_step_internal(step_name)
        except Exception as e:
            self.log_manager.log_exception(f"Step {step_name} failed", e)
            return WorkflowStepResult(
                success=False, 
                output={},
                error_message=str(e)
            )

# 包括的E2Eテスト
def test_complete_workflow_integration():
    """実環境シミュレーション"""
    config = load_production_config()
    db_manager = DatabaseManager(config['database']['path'])
    log_manager = LogManager(config['logging'])
    
    engine = ProductionWorkflowEngine(db_manager, log_manager, config)
    
    # 実際の動画生成ワークフロー実行
    project_id = "integration_test_project"
    
    # 全13ステップの実行
    for step_name in get_workflow_steps():
        result = engine.execute_step(step_name)
        assert result.success, f"Step {step_name} failed: {result.error_message}"
    
    # 最終成果物検証
    output_files = get_project_output_files(project_id)
    assert 'final_video.mp4' in output_files
    assert verify_video_quality(output_files['final_video.mp4'])
```

## 🔧 実践的ツール・技法

### 1. 契約駆動開発 (Contract-Driven Development)

```python
# インターフェース先行定義（実装は後回し）
class TTSServiceContract(Protocol):
    def generate_speech(self, text: str, voice_config: Dict) -> AudioFile:
        """音声生成の契約"""
        ...

# 契約テスト
def test_tts_contract_compliance(tts_service: TTSServiceContract):
    result = tts_service.generate_speech("テスト", {"voice": "yukari"})
    assert isinstance(result, AudioFile)
    assert result.duration > 0
```

### 2. リスク駆動統合テスト

```python
# 高リスク部分のみ早期統合テスト
HIGH_RISK_INTEGRATIONS = [
    "database_operations",    # データ整合性
    "external_api_calls",     # ネットワーク依存
    "file_system_operations", # ファイル破損リスク
]

def test_high_risk_integration(integration_name):
    if integration_name in HIGH_RISK_INTEGRATIONS:
        # 実環境での統合テスト
        run_real_integration_test(integration_name)
    else:
        # モックによる単体テスト
        run_mocked_unit_test(integration_name)
```

### 3. 段階的CI/CD戦略

```yaml
# .github/workflows/staged_testing.yml
name: Staged Testing Strategy

on: [push, pull_request]

jobs:
  phase1_exploration:
    if: contains(github.event.head_commit.message, '[phase1]')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Unit Tests Only
        run: |
          pytest tests/unit/ -v
          # 統合テストは実行しない（意図的）

  phase2_stabilization:
    if: contains(github.event.head_commit.message, '[phase2]')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Contract + Critical Integration Tests
        run: |
          pytest tests/unit/ tests/contracts/ tests/integration/critical/ -v

  phase3_production:
    if: contains(github.event.head_commit.message, '[phase3]') || github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Full Test Suite
        run: |
          pytest tests/ -v --cov=src --cov-report=html
          # E2E・パフォーマンステスト含む
```

## 📈 段階別成功指標

### Phase 1 成功指標
- [ ] 基本機能プロトタイプ完成
- [ ] 技術選択の妥当性確認
- [ ] 単体テストカバレッジ 70%+
- [ ] **統合テストは0%（意図的）**

### Phase 2 成功指標  
- [ ] インターフェース安定化
- [ ] 契約テスト100%パス
- [ ] 重要統合テスト作成・パス
- [ ] アーキテクチャレビュー完了

### Phase 3 成功指標
- [ ] 全テストスイート100%パス
- [ ] E2Eテスト作成・パス  
- [ ] パフォーマンス要件達成
- [ ] プロダクション品質達成

## 🚫 アンチパターン回避

### ❌ 避けるべきパターン

```python
# アンチパターン1: 過早期統合テスト
def test_premature_integration():
    """Phase1で実装詳細まで統合テスト（避けるべき）"""
    engine = WorkflowEngine()
    db = DatabaseManager()
    api = ExternalAPIClient()
    
    # 実装が固まる前に統合テストを書くのは危険
    result = engine.execute_full_workflow(db, api, complex_config)
    # この時点で柔軟性が失われる

# アンチパターン2: 統合テスト放置
def test_ignored_integration():
    """Phase3でも統合テストなし（避けるべき）"""
    mock_db = Mock()
    mock_api = Mock()
    
    # プロダクション前でもモックのみは危険
    result = engine.execute_workflow(mock_db, mock_api)
```

### ✅ 推奨パターン

```python
# Phase1: 探索的単体テスト
@pytest.mark.phase1
def test_workflow_exploration():
    """実装方法の探索（柔軟性重視）"""
    # 実装詳細は自由に変更
    pass

# Phase2: 契約統合テスト  
@pytest.mark.phase2
def test_workflow_contract():
    """インターフェース固定（バランス）"""
    # 契約のみ固定、実装は自由
    pass

# Phase3: 完全統合テスト
@pytest.mark.phase3  
def test_workflow_production():
    """プロダクション品質（品質重視）"""
    # 全体統合で品質保証
    pass
```

## 🎯 まとめ：柔軟性と品質の両立

この段階的アプローチにより：

1. **Phase 1**: 創造性・探索・技術選択の自由
2. **Phase 2**: 段階的安定化・重要リスクの早期発見  
3. **Phase 3**: プロダクション品質・完全テストカバレッジ

**結果**: 開発の柔軟性を保ちながら、最終的な品質を確保できる理想的なバランスを実現。 