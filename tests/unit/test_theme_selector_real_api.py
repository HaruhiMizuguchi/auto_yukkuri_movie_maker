"""
テーマ選定モジュールの実API単体テスト

TDD方式で実装し直し、実際のLLM生成とDB保存をテスト
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from src.modules.theme_selector import (
    ThemeSelector,
    DatabaseDataAccess,
    GeminiThemeLLM,
    UserPreferences,
    ThemeCandidate,
    SelectedTheme,
    ThemeSelectionInput,
    ThemeSelectionOutput
)
from src.dao.theme_selection_dao import ThemeSelectionDAO
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
    reason="GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません"
)
class TestThemeSelectorRealAPI:
    """実際のAPI使用による単体テスト"""
    
    @pytest.fixture
    def temp_database(self):
        """テスト用一時データベース"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        yield db_path
        
        # クリーンアップ
        try:
            if os.path.exists(db_path):
                import gc
                gc.collect()
                import time
                time.sleep(0.1)
                os.unlink(db_path)
        except PermissionError:
            pass
    
    @pytest.fixture
    def db_manager(self, temp_database):
        """初期化済みデータベースマネージャー"""
        db_manager = DatabaseManager(temp_database)
        db_manager.initialize()
        yield db_manager
        db_manager.close_connection()
    
    @pytest.fixture
    def project_repository(self, db_manager):
        """プロジェクトリポジトリ"""
        return ProjectRepository(db_manager)
    
    @pytest.fixture
    def config_manager(self):
        """設定マネージャー"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            config_content = """
llm:
  model: "gemini-2.0-flash-exp"
  temperature: 0.8
  max_tokens: 2000
"""
            config_path.write_text(config_content)
            yield ConfigManager(str(config_path))
    
    @pytest.fixture
    def llm_client(self):
        """実際のGemini LLMクライアント"""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return GeminiLLMClient(api_key=api_key)
    
    @pytest.fixture
    def test_project_id(self, project_repository):
        """テスト用プロジェクト作成"""
        project_id = "test-real-api-001"
        
        user_config = {
            "user_preferences": {
                "genre_history": ["科学", "技術"],
                "preferred_genres": ["教育", "エンターテインメント"],
                "excluded_genres": ["政治", "宗教"],
                "target_audience": "一般",
                "content_style": "親しみやすい"
            }
        }
        
        success = project_repository.create_project(
            project_id=project_id,
            theme="初期テーマ",
            target_length_minutes=5.0,
            config=user_config
        )
        
        assert success, "テストプロジェクト作成に失敗"
        return project_id
    
    def test_dao_operations(self, db_manager, test_project_id):
        """DAO基本操作テスト"""
        dao = ThemeSelectionDAO(db_manager)
        
        # プロジェクト設定取得
        config = dao.get_project_config(test_project_id)
        assert "user_preferences" in config
        
        # プロジェクトテーマ更新
        dao.update_project_theme(
            project_id=test_project_id,
            theme="新しいテーマ",
            target_length_minutes=7.0
        )
        
        # 更新確認
        project_info = dao.get_project_info(test_project_id)
        assert project_info["theme"] == "新しいテーマ"
        assert project_info["target_length_minutes"] == 7.0
        
        print("✅ DAO操作テスト成功")
    
    def test_llm_theme_generation(self, llm_client):
        """LLMテーマ生成テスト"""
        gemini_llm = GeminiThemeLLM(llm_client)
        
        preferences = UserPreferences(
            genre_history=["科学"],
            preferred_genres=["教育"],
            excluded_genres=[],
            target_audience="学生",
            content_style="分かりやすい"
        )
        
        # テーマ候補生成
        candidates = gemini_llm.generate_theme_candidates(preferences, count=2)
        
        # 結果検証
        assert len(candidates) > 0, "テーマ候補が生成されませんでした"
        assert len(candidates) <= 2, "指定数を超えるテーマ候補が生成されました"
        
        for candidate in candidates:
            assert candidate.theme, "テーマが空です"
            assert candidate.category, "カテゴリが空です"
            assert candidate.target_length_minutes > 0, "動画長が0以下です"
            assert candidate.description, "説明が空です"
            assert 1.0 <= candidate.difficulty_score <= 10.0, "難易度スコアが範囲外です"
            assert 1.0 <= candidate.entertainment_score <= 10.0, "エンターテインメントスコアが範囲外です"
            assert 1.0 <= candidate.trend_score <= 10.0, "トレンドスコアが範囲外です"
            assert candidate.total_score > 0, "総合スコアが0以下です"
        
        print(f"✅ LLMテーマ生成テスト成功: {len(candidates)}個の候補生成")
        for i, candidate in enumerate(candidates, 1):
            print(f"  {i}. {candidate.theme} (スコア: {candidate.total_score:.1f})")
    
    def test_database_data_access(self, project_repository, config_manager, test_project_id):
        """DatabaseDataAccessクラステスト"""
        data_access = DatabaseDataAccess(project_repository, config_manager)
        
        # ユーザー設定取得
        preferences = data_access.get_user_preferences(test_project_id)
        assert preferences.target_audience == "一般"
        assert "教育" in preferences.preferred_genres
        
        # テーマ選定結果保存テスト用データ
        selected_theme = SelectedTheme(
            theme="テストテーマ",
            category="教育",
            target_length_minutes=6,
            description="テスト説明",
            selection_reason="テスト理由",
            generation_timestamp=datetime.now()
        )
        
        candidates = [
            ThemeCandidate(
                theme="候補1",
                category="教育",
                target_length_minutes=5,
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
            selection_metadata={"test": True}
        )
        
        # 結果保存
        data_access.save_theme_selection_result(test_project_id, output)
        
        # 保存確認
        dao = ThemeSelectionDAO(project_repository.db_manager)
        project_info = dao.get_project_info(test_project_id)
        assert project_info["theme"] == "テストテーマ"
        
        step_result = dao.get_workflow_step_result(test_project_id, "theme_selection")
        assert step_result["status"] == "completed"
        
        print("✅ DatabaseDataAccessテスト成功")
    
    def test_theme_selector_integration(
        self, 
        project_repository, 
        config_manager, 
        llm_client, 
        test_project_id
    ):
        """ThemeSelectorの統合テスト"""
        
        # データアクセス層とLLM層の準備
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiThemeLLM(llm_client)
        
        # テーマセレクター初期化
        theme_selector = ThemeSelector(
            data_access=data_access,
            llm_interface=llm_interface
        )
        
        # 入力データ準備
        user_preferences = UserPreferences(
            genre_history=["科学"],
            preferred_genres=["教育"],
            excluded_genres=[],
            target_audience="学生",
            content_style="分かりやすい"
        )
        
        input_data = ThemeSelectionInput(
            project_id=test_project_id,
            user_preferences=user_preferences,
            llm_config={"model": "gemini-2.0-flash-exp", "temperature": 0.8},
            max_candidates=2
        )
        
        # テーマ選定実行
        output = theme_selector.select_theme(input_data)
        
        # 結果検証
        assert isinstance(output, ThemeSelectionOutput), "出力型が正しくありません"
        assert output.selected_theme, "選択されたテーマが空です"
        assert output.candidates, "候補が空です"
        assert len(output.candidates) > 0, "候補数が0です"
        
        # データベース保存確認
        dao = ThemeSelectionDAO(project_repository.db_manager)
        project_info = dao.get_project_info(test_project_id)
        assert project_info["theme"] == output.selected_theme.theme, "DBのテーマが更新されていません"
        
        step_result = dao.get_workflow_step_result(test_project_id, "theme_selection")
        assert step_result["status"] == "completed", "ワークフローステップが完了していません"
        
        print(f"✅ ThemeSelector統合テスト成功")
        print(f"  選択テーマ: {output.selected_theme.theme}")
        print(f"  候補数: {len(output.candidates)}")
        print(f"  カテゴリ: {output.selected_theme.category}")
        print(f"  目標長: {output.selected_theme.target_length_minutes}分")


if __name__ == "__main__":
    # 単体テストの個別実行
    pytest.main([__file__, "-v", "-s"]) 