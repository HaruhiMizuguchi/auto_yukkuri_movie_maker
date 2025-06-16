"""
テーマ選定モジュールの単体テスト

開発ルールに従って:
- TDD (テスト駆動開発) を実施
- 実際のLLM APIを使用したテストで機能確認
- データベース連携を厳密にテスト
- モック使用は外部サービス・I/O操作のみに限定
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock

from src.modules.theme_selector import (
    ThemeSelector,
    DatabaseDataAccess,
    GeminiThemeLLM,
    UserPreferences,
    ThemeCandidate,
    SelectedTheme,
    ThemeSelectionInput,
    ThemeSelectionOutput,
    DataAccessInterface,
    LLMInterface
)
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient


class TestUserPreferences:
    """UserPreferencesデータクラスのテスト"""
    
    def test_user_preferences_creation(self):
        """ユーザー設定データクラスの作成テスト"""
        prefs = UserPreferences(
            genre_history=["科学", "歴史"],
            preferred_genres=["教育", "エンターテインメント"],
            excluded_genres=["政治"],
            target_audience="一般",
            content_style="親しみやすい"
        )
        
        assert prefs.genre_history == ["科学", "歴史"]
        assert prefs.preferred_genres == ["教育", "エンターテインメント"]
        assert prefs.excluded_genres == ["政治"]
        assert prefs.target_audience == "一般"
        assert prefs.content_style == "親しみやすい"


class TestThemeCandidate:
    """ThemeCandidateデータクラスのテスト"""
    
    def test_theme_candidate_creation(self):
        """テーマ候補データクラスの作成テスト"""
        candidate = ThemeCandidate(
            theme="科学の不思議",
            category="教育",
            target_length_minutes=7,
            description="面白い科学現象の解説",
            appeal_points=["学習効果", "驚き"],
            difficulty_score=4.0,
            entertainment_score=7.0,
            trend_score=6.0,
            total_score=5.7
        )
        
        assert candidate.theme == "科学の不思議"
        assert candidate.category == "教育"
        assert candidate.target_length_minutes == 7
        assert candidate.difficulty_score == 4.0
        assert candidate.total_score == 5.7


class TestDatabaseDataAccess:
    """DatabaseDataAccessクラスのテスト"""
    
    @pytest.fixture
    def temp_database(self):
        """テスト用一時データベース"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        yield db_path
        
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def repository(self, temp_database):
        """テスト用ProjectRepository"""
        from src.core.database_manager import DatabaseManager
        db_manager = DatabaseManager(temp_database)
        db_manager.initialize()
        repo = ProjectRepository(db_manager)
        return repo
    
    @pytest.fixture
    def config_manager(self):
        """テスト用ConfigManager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            config_path.write_text("""
llm:
  model: "gemini-2.0-flash-preview"
  temperature: 0.8
""")
            return ConfigManager(str(config_path))
    
    @pytest.fixture
    def data_access(self, repository, config_manager):
        """テスト用DatabaseDataAccess"""
        return DatabaseDataAccess(repository, config_manager)
    
    def test_get_user_preferences_with_config(self, data_access, repository):
        """ユーザー設定取得テスト（設定あり）"""
        # テストプロジェクト作成
        project_id = repository.create_project("テストプロジェクト")
        
        # ユーザー設定を含むconfig_jsonを設定
        user_config = {
            "user_preferences": {
                "genre_history": ["科学", "歴史"],
                "preferred_genres": ["教育"],
                "excluded_genres": ["政治"],
                "target_audience": "学生",
                "content_style": "分かりやすい"
            }
        }
        repository.update_project(
            project_id=project_id,
            config=user_config
        )
        
        # ユーザー設定取得
        prefs = data_access.get_user_preferences(project_id)
        
        assert prefs.genre_history == ["科学", "歴史"]
        assert prefs.preferred_genres == ["教育"]
        assert prefs.excluded_genres == ["政治"]
        assert prefs.target_audience == "学生"
        assert prefs.content_style == "分かりやすい"
    
    def test_get_user_preferences_default(self, data_access, repository):
        """ユーザー設定取得テスト（デフォルト値）"""
        # テストプロジェクト作成（設定なし）
        project_id = repository.create_project("テストプロジェクト")
        
        # ユーザー設定取得（デフォルト値期待）
        prefs = data_access.get_user_preferences(project_id)
        
        assert prefs.genre_history == []
        assert prefs.preferred_genres == ["教育", "エンターテインメント"]
        assert prefs.excluded_genres == []
        assert prefs.target_audience == "一般"
        assert prefs.content_style == "親しみやすい"
    
    def test_get_user_preferences_project_not_found(self, data_access):
        """存在しないプロジェクトでのエラーテスト"""
        with pytest.raises(ValueError, match="Project not found"):
            data_access.get_user_preferences("non-existent-id")
    
    def test_save_theme_selection_result(self, data_access, repository):
        """テーマ選定結果保存テスト"""
        # テストプロジェクト作成
        project_id = repository.create_project("テストプロジェクト")
        
        # テスト結果データ
        selected_theme = SelectedTheme(
            theme="テスト科学",
            category="教育",
            target_length_minutes=8,
            description="テスト説明",
            selection_reason="テスト理由",
            generation_timestamp=datetime.now()
        )
        
        candidates = [
            ThemeCandidate(
                theme="候補1",
                category="教育",
                target_length_minutes=7,
                description="説明1",
                appeal_points=["ポイント1"],
                difficulty_score=5.0,
                entertainment_score=6.0,
                trend_score=7.0,
                total_score=6.0
            )
        ]
        
        output = ThemeSelectionOutput(
            selected_theme=selected_theme,
            candidates=candidates,
            selection_metadata={"test": "metadata"}
        )
        
        # 結果保存
        data_access.save_theme_selection_result(project_id, output)
        
        # 保存確認
        project = repository.get_project(project_id)
        assert project.theme == "テスト科学"
        assert project.target_length_minutes == 8
        
        # ワークフローステップ確認
        step_result = repository.get_workflow_step(project_id, "theme_selection")
        assert step_result is not None
        assert step_result["status"] == "completed"
    
    def test_save_theme_candidates_file(self, data_access, repository):
        """テーマ候補ファイル保存テスト"""
        # テストプロジェクト作成
        project_id = repository.create_project("テストプロジェクト")
        
        # テスト候補データ
        candidates = [
            ThemeCandidate(
                theme="候補1",
                category="教育",
                target_length_minutes=7,
                description="説明1",
                appeal_points=["ポイント1", "ポイント2"],
                difficulty_score=5.0,
                entertainment_score=6.0,
                trend_score=7.0,
                total_score=6.0
            ),
            ThemeCandidate(
                theme="候補2",
                category="エンターテインメント",
                target_length_minutes=9,
                description="説明2",
                appeal_points=["ポイント3"],
                difficulty_score=4.0,
                entertainment_score=8.0,
                trend_score=5.0,
                total_score=5.7
            )
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # projectsディレクトリを一時ディレクトリに設定
            projects_dir = Path(temp_dir) / "projects"
            original_cwd = os.getcwd()
            
            try:
                os.chdir(temp_dir)
                
                # ファイル保存実行
                file_path = data_access.save_theme_candidates_file(project_id, candidates)
                
                # ファイル存在確認
                assert os.path.exists(file_path)
                
                # ファイル内容確認
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                assert data["count"] == 2
                assert len(data["candidates"]) == 2
                assert data["candidates"][0]["theme"] == "候補1"
                assert data["candidates"][1]["theme"] == "候補2"
                
                # データベースのファイル参照確認
                file_refs = repository.get_files_by_query(project_id, file_type="metadata")
                assert len(file_refs) == 1
                assert file_refs[0]["file_type"] == "metadata"
            
            finally:
                os.chdir(original_cwd)


class TestGeminiThemeLLM:
    """GeminiThemeLLMクラスのテスト"""
    
    @pytest.fixture
    def mock_llm_client(self):
        """モックLLMクライアント"""
        mock_client = Mock(spec=GeminiLLMClient)
        return mock_client
    
    @pytest.fixture
    def gemini_theme_llm(self, mock_llm_client):
        """テスト用GeminiThemeLLM"""
        return GeminiThemeLLM(mock_llm_client)
    
    @pytest.fixture
    def sample_preferences(self):
        """サンプルユーザー設定"""
        return UserPreferences(
            genre_history=["科学"],
            preferred_genres=["教育", "エンターテインメント"],
            excluded_genres=["政治"],
            target_audience="一般",
            content_style="親しみやすい"
        )
    
    def test_generate_theme_candidates_success(self, gemini_theme_llm, mock_llm_client, sample_preferences):
        """テーマ候補生成成功テスト"""
        # モックレスポンス
        mock_response = Mock()
        mock_response.text = """{
  "themes": [
    {
      "theme": "宇宙の不思議",
      "category": "科学",
      "target_length_minutes": 8,
      "description": "宇宙の謎について分かりやすく解説",
      "appeal_points": ["学習効果", "驚き", "視覚的美しさ"],
      "difficulty_score": 5.0,
      "entertainment_score": 8.0,
      "trend_score": 7.0,
      "total_score": 6.7
    },
    {
      "theme": "古代文明の謎",
      "category": "歴史",
      "target_length_minutes": 9,
      "description": "古代文明に隠された謎を探る",
      "appeal_points": ["ミステリー", "教養", "想像力"],
      "difficulty_score": 6.0,
      "entertainment_score": 7.0,
      "trend_score": 6.0,
      "total_score": 6.3
    }
  ]
}"""
        mock_llm_client.generate_text.return_value = mock_response
        
        # テーマ候補生成実行
        candidates = gemini_theme_llm.generate_theme_candidates(sample_preferences, 5)
        
        # 結果確認
        assert len(candidates) == 2
        assert candidates[0].theme == "宇宙の不思議"
        assert candidates[0].category == "科学"
        assert candidates[0].target_length_minutes == 8
        assert candidates[0].total_score == 6.7
        assert candidates[1].theme == "古代文明の謎"
        
        # LLMクライアント呼び出し確認
        mock_llm_client.generate_text.assert_called_once()
        call_args = mock_llm_client.generate_text.call_args
        assert call_args[1]["temperature"] == 0.8
        assert call_args[1]["max_tokens"] == 2000
        assert "教育, エンターテインメント" in call_args[1]["prompt"]
    
    def test_generate_theme_candidates_parse_error(self, gemini_theme_llm, mock_llm_client, sample_preferences):
        """JSON解析エラー時のフォールバック テスト"""
        # 不正なJSONレスポンス
        mock_response = Mock()
        mock_response.text = "不正なJSONレスポンス"
        mock_llm_client.generate_text.return_value = mock_response
        
        # テーマ候補生成実行（フォールバック期待）
        candidates = gemini_theme_llm.generate_theme_candidates(sample_preferences, 5)
        
        # フォールバック候補確認
        assert len(candidates) == 2
        assert candidates[0].theme == "科学の不思議な現象"
        assert candidates[1].theme == "歴史上の面白エピソード"
    
    def test_generate_theme_candidates_api_error(self, gemini_theme_llm, mock_llm_client, sample_preferences):
        """API呼び出しエラー時のフォールバック テスト"""
        # API呼び出しエラー
        mock_llm_client.generate_text.side_effect = Exception("API Error")
        
        # テーマ候補生成実行（フォールバック期待）
        candidates = gemini_theme_llm.generate_theme_candidates(sample_preferences, 5)
        
        # フォールバック候補確認
        assert len(candidates) == 2
        assert all(isinstance(c, ThemeCandidate) for c in candidates)
    
    def test_evaluate_and_rank_themes(self, gemini_theme_llm, mock_llm_client, sample_preferences):
        """テーマ評価・ランキング テスト"""
        # テスト候補
        candidates = [
            ThemeCandidate(
                theme="候補A", category="教育", target_length_minutes=7,
                description="説明A", appeal_points=["ポイント1"], 
                difficulty_score=5.0, entertainment_score=6.0,
                trend_score=7.0, total_score=6.0
            ),
            ThemeCandidate(
                theme="候補B", category="科学", target_length_minutes=8,
                description="説明B", appeal_points=["ポイント2"],
                difficulty_score=4.0, entertainment_score=8.0,
                trend_score=6.0, total_score=6.7
            )
        ]
        
        # モックレスポンス（評価結果）
        mock_response = Mock()
        mock_response.text = """1位: 候補B - 高いエンターテインメント性
2位: 候補A - 教育的価値"""
        mock_llm_client.generate_text.return_value = mock_response
        
        # 評価・ランキング実行
        ranked = gemini_theme_llm.evaluate_and_rank_themes(candidates, sample_preferences)
        
        # スコア順ソート確認（簡易実装）
        assert len(ranked) == 2
        assert ranked[0].total_score >= ranked[1].total_score
    
    def test_build_theme_generation_prompt(self, gemini_theme_llm, sample_preferences):
        """テーマ生成プロンプト構築テスト"""
        prompt = gemini_theme_llm._build_theme_generation_prompt(sample_preferences, 5)
        
        # プロンプト内容確認
        assert "ゆっくり動画のテーマを5個生成" in prompt
        assert "教育, エンターテインメント" in prompt
        assert "政治" in prompt
        assert "一般" in prompt
        assert "親しみやすい" in prompt
        assert "JSON" in prompt
    
    def test_get_fallback_candidates(self, gemini_theme_llm, sample_preferences):
        """フォールバック候補取得テスト"""
        candidates = gemini_theme_llm._get_fallback_candidates(sample_preferences)
        
        assert len(candidates) == 2
        assert all(isinstance(c, ThemeCandidate) for c in candidates)
        assert all(c.total_score > 0 for c in candidates)


class TestThemeSelector:
    """ThemeSelectorメインクラスのテスト"""
    
    @pytest.fixture
    def mock_data_access(self):
        """モックデータアクセス"""
        mock = Mock(spec=DataAccessInterface)
        return mock
    
    @pytest.fixture
    def mock_llm_interface(self):
        """モックLLMインターフェース"""
        mock = Mock(spec=LLMInterface)
        return mock
    
    @pytest.fixture
    def theme_selector(self, mock_data_access, mock_llm_interface):
        """テスト用ThemeSelector"""
        return ThemeSelector(mock_data_access, mock_llm_interface)
    
    @pytest.fixture
    def sample_input(self):
        """サンプル入力データ"""
        preferences = UserPreferences(
            genre_history=["科学"],
            preferred_genres=["教育"],
            excluded_genres=[],
            target_audience="一般",
            content_style="親しみやすい"
        )
        
        return ThemeSelectionInput(
            project_id="test-project-123",
            user_preferences=preferences,
            llm_config={"model": "gemini-2.0-flash-preview"},
            max_candidates=5
        )
    
    def test_select_theme_success(self, theme_selector, mock_data_access, mock_llm_interface, sample_input):
        """テーマ選定成功テスト"""
        # モック設定
        mock_candidates = [
            ThemeCandidate(
                theme="最優秀テーマ", category="教育", target_length_minutes=8,
                description="素晴らしい説明", appeal_points=["魅力1", "魅力2"],
                difficulty_score=4.0, entertainment_score=9.0,
                trend_score=8.0, total_score=7.0
            ),
            ThemeCandidate(
                theme="次点テーマ", category="科学", target_length_minutes=7,
                description="良い説明", appeal_points=["魅力3"],
                difficulty_score=5.0, entertainment_score=7.0,
                trend_score=6.0, total_score=6.0
            )
        ]
        
        mock_llm_interface.generate_theme_candidates.return_value = mock_candidates
        mock_llm_interface.evaluate_and_rank_themes.return_value = mock_candidates  # すでにソート済み
        
        # テーマ選定実行
        result = theme_selector.select_theme(sample_input)
        
        # 結果確認
        assert isinstance(result, ThemeSelectionOutput)
        assert result.selected_theme.theme == "最優秀テーマ"
        assert result.selected_theme.category == "教育"
        assert result.selected_theme.target_length_minutes == 8
        assert "総合スコア7.0で最高評価" in result.selected_theme.selection_reason
        
        assert len(result.candidates) == 2
        assert result.selection_metadata["generation_method"] == "gemini_llm"
        assert result.selection_metadata["candidates_count"] == 2
        
        # モック呼び出し確認
        mock_llm_interface.generate_theme_candidates.assert_called_once_with(
            sample_input.user_preferences, sample_input.max_candidates
        )
        mock_llm_interface.evaluate_and_rank_themes.assert_called_once_with(
            mock_candidates, sample_input.user_preferences
        )
        
        mock_data_access.save_theme_selection_result.assert_called_once()
        mock_data_access.save_theme_candidates_file.assert_called_once()
    
    def test_select_theme_no_candidates(self, theme_selector, mock_data_access, mock_llm_interface, sample_input):
        """候補なし時のエラーテスト"""
        # 空の候補リスト
        mock_llm_interface.generate_theme_candidates.return_value = []
        mock_llm_interface.evaluate_and_rank_themes.return_value = []
        
        # エラー期待
        with pytest.raises(ValueError, match="有効なテーマ候補が生成されませんでした"):
            theme_selector.select_theme(sample_input)
    
    def test_select_theme_llm_error_propagation(self, theme_selector, mock_data_access, mock_llm_interface, sample_input):
        """LLMエラーの伝播テスト"""
        # LLMエラー設定
        mock_llm_interface.generate_theme_candidates.side_effect = Exception("LLM API Error")
        
        # エラーの伝播確認
        with pytest.raises(Exception, match="LLM API Error"):
            theme_selector.select_theme(sample_input)


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"), 
    reason="GEMINI_API_KEY環境変数が設定されていません"
)
class TestThemeSelectorRealAPI:
    """実際のAPI使用統合テスト"""
    
    def test_real_gemini_theme_generation(self):
        """実際のGemini APIを使用したテーマ生成テスト"""
        # 実際のGeminiクライアント作成
        llm_client = GeminiLLMClient()
        gemini_llm = GeminiThemeLLM(llm_client)
        
        # テスト用ユーザー設定
        preferences = UserPreferences(
            genre_history=["科学"],
            preferred_genres=["教育", "エンターテインメント"],
            excluded_genres=["政治", "宗教"],
            target_audience="一般",
            content_style="親しみやすい"
        )
        
        try:
            # 実際のテーマ候補生成
            candidates = gemini_llm.generate_theme_candidates(preferences, 3)
            
            # 基本的な結果確認
            assert len(candidates) > 0
            assert all(isinstance(c, ThemeCandidate) for c in candidates)
            assert all(c.theme for c in candidates)  # テーマ名が空でない
            assert all(c.category for c in candidates)  # カテゴリが空でない
            assert all(c.target_length_minutes > 0 for c in candidates)  # 時間が正の値
            
            print(f"🎯 実際のGemini APIでテーマ生成成功: {len(candidates)}件")
            for i, candidate in enumerate(candidates, 1):
                print(f"  {i}. {candidate.theme} ({candidate.category}, {candidate.target_length_minutes}分)")
                print(f"     スコア: {candidate.total_score:.1f}, 説明: {candidate.description[:50]}...")
            
        except Exception as e:
            pytest.fail(f"実際のGemini API呼び出しでエラー: {e}")


# 実際のAPI動作確認用の統合テスト関数
def run_integration_test():
    """統合テスト実行（手動実行用）"""
    print("🚀 テーマ選定モジュール統合テスト開始")
    
    # 環境変数確認
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY環境変数が設定されていません")
        return
    
    # 一時データベースで統合テスト
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # コンポーネント初期化
        repository = ProjectRepository(db_path)
        repository.initialize_database()
        
        config_data = {"llm": {"model": "gemini-2.0-flash-preview", "temperature": 0.8}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as config_file:
            import yaml
            yaml.dump(config_data, config_file)
            config_path = config_file.name
        
        config_manager = ConfigManager(config_path)
        data_access = DatabaseDataAccess(repository, config_manager)
        
        llm_client = GeminiLLMClient()
        llm_interface = GeminiThemeLLM(llm_client)
        
        theme_selector = ThemeSelector(data_access, llm_interface)
        
        # テストプロジェクト作成
        project_id = repository.create_project("統合テストプロジェクト")
        user_config = {
            "user_preferences": {
                "genre_history": ["科学", "技術"],
                "preferred_genres": ["教育", "エンターテインメント"],
                "excluded_genres": ["政治"],
                "target_audience": "一般",
                "content_style": "分かりやすい"
            }
        }
        repository.update_project(project_id=project_id, config_json=json.dumps(user_config))
        
        # 入力データ準備
        preferences = data_access.get_user_preferences(project_id)
        input_data = ThemeSelectionInput(
            project_id=project_id,
            user_preferences=preferences,
            llm_config=config_manager.get_value("llm"),
            max_candidates=5
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # 実際のテーマ選定実行
                print("📊 テーマ選定実行中...")
                result = theme_selector.select_theme(input_data)
                
                # 結果確認
                print(f"✅ テーマ選定完了!")
                print(f"🎯 選定テーマ: {result.selected_theme.theme}")
                print(f"📂 カテゴリ: {result.selected_theme.category}")
                print(f"⏱️  目標時間: {result.selected_theme.target_length_minutes}分")
                print(f"📝 説明: {result.selected_theme.description}")
                print(f"🎪 候補数: {len(result.candidates)}件")
                
                # データベース保存確認
                saved_project = repository.get_project(project_id)
                print(f"💾 データベース保存確認: テーマ={saved_project.theme}, 時間={saved_project.target_length_minutes}")
                
                print("🎉 統合テスト成功!")
                
            finally:
                os.chdir(original_cwd)
        
        # クリーンアップ
        os.unlink(config_path)
    
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    run_integration_test() 