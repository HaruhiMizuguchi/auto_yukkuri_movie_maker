"""
テーマ選定モジュールの統合テスト

実際のLLM API呼び出しとデータベース保存を含む統合テスト
TDD方式で実装前にテストを作成
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
    ThemeSelectionInput,
    ThemeSelectionOutput
)
from src.dao.theme_selection_dao import ThemeSelectionDAO
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient
from src.utils.text_generation import generate_text


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
    reason="GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません"
)
class TestThemeSelectionIntegration:
    """実際のAPI・DB使用による統合テスト"""
    
    @pytest.fixture
    def temp_database(self):
        """テスト用一時データベース"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        yield db_path
        
        # クリーンアップ（Windowsでファイルロックを回避）
        try:
            if os.path.exists(db_path):
                # ファイルハンドルを確実に閉じる
                import gc
                gc.collect()
                import time
                time.sleep(0.1)  # 短い待機
                os.unlink(db_path)
        except PermissionError:
            # Windowsでファイルがロックされている場合は無視
            pass
    
    @pytest.fixture
    def temp_project_dir(self):
        """テスト用プロジェクトディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def db_manager(self, temp_database):
        """初期化済みデータベースマネージャー"""
        db_manager = DatabaseManager(temp_database)
        db_manager.initialize()
        yield db_manager
        # テスト後のクリーンアップ
        db_manager.close_connection()
    
    @pytest.fixture
    def theme_dao(self, db_manager):
        """テーマ選定DAO"""
        return ThemeSelectionDAO(db_manager)
    
    @pytest.fixture
    def project_repository(self, db_manager):
        """プロジェクトリポジトリ"""
        return ProjectRepository(db_manager)
    
    @pytest.fixture
    def config_manager(self, temp_project_dir):
        """設定マネージャー"""
        config_path = temp_project_dir / "test_config.yaml"
        config_content = """
llm:
  model: "gemini-2.0-flash-exp"
  temperature: 0.8
  max_tokens: 2000
"""
        config_path.write_text(config_content)
        return ConfigManager(str(config_path))
    
    @pytest.fixture
    def llm_client(self):
        """実際のGemini LLMクライアント"""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return GeminiLLMClient(api_key=api_key)
    
    @pytest.fixture
    def test_project_id(self, project_repository):
        """テスト用プロジェクト作成"""
        project_id = "test-theme-integration-001"
        
        # ユーザー設定を含むプロジェクト作成
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
    
    def test_dao_database_operations(self, theme_dao, test_project_id):
        """DAO層のデータベース操作テスト"""
        
        # 1. プロジェクト設定取得
        config = theme_dao.get_project_config(test_project_id)
        assert "user_preferences" in config
        assert config["user_preferences"]["target_audience"] == "一般"
        
        # 2. プロジェクトテーマ更新
        theme_dao.update_project_theme(
            project_id=test_project_id,
            theme="AIと機械学習の基礎",
            target_length_minutes=7.5
        )
        
        # 3. 更新結果確認
        project_info = theme_dao.get_project_info(test_project_id)
        assert project_info["theme"] == "AIと機械学習の基礎"
        assert project_info["target_length_minutes"] == 7.5
        
        # 4. ワークフローステップ結果保存
        output_data = {
            "selected_theme": {
                "theme": "AIと機械学習の基礎",
                "category": "教育",
                "description": "初心者向けAI解説"
            },
            "candidates_count": 5
        }
        
        theme_dao.save_workflow_step_result(
            project_id=test_project_id,
            step_name="theme_selection",
            output_data=output_data,
            status="completed"
        )
        
        # 5. ワークフローステップ結果取得
        step_result = theme_dao.get_workflow_step_result(
            project_id=test_project_id,
            step_name="theme_selection"
        )
        
        assert step_result["status"] == "completed"
        assert step_result["output_data"]["candidates_count"] == 5
        
        # 6. ファイル参照登録
        file_id = theme_dao.register_file_reference(
            project_id=test_project_id,
            file_type="metadata",
            file_category="output",
            file_path=f"projects/{test_project_id}/files/metadata/theme_candidates.json",
            file_name="theme_candidates.json",
            file_size=1024,
            metadata={"generation_time": datetime.now().isoformat()}
        )
        
        assert file_id > 0
    
    def test_real_llm_theme_generation(self, llm_client):
        """実際のLLMを使用したテーマ生成テスト"""
        
        # LLMクライアント動作確認
        gemini_llm = GeminiThemeLLM(llm_client)
        
        # テスト用ユーザー設定
        preferences = UserPreferences(
            genre_history=["科学", "技術"],
            preferred_genres=["教育"],
            excluded_genres=["政治"],
            target_audience="学生",
            content_style="分かりやすい"
        )
        
        # テーマ候補生成
        candidates = gemini_llm.generate_theme_candidates(preferences, count=3)
        
        # 結果検証
        assert len(candidates) > 0, "テーマ候補が生成されませんでした"
        assert len(candidates) <= 3, "指定数を超えるテーマ候補が生成されました"
        
        for candidate in candidates:
            assert candidate.theme, "テーマが空です"
            assert candidate.category, "カテゴリが空です"
            assert candidate.target_length_minutes > 0, "動画長が0以下です"
            assert candidate.description, "説明が空です"
            assert 1.0 <= candidate.difficulty_score <= 10.0, "難易度スコアが範囲外です"
            assert 1.0 <= candidate.entertainment_score <= 10.0, "エンターテインメントスコアが範囲外です"
            assert 1.0 <= candidate.trend_score <= 10.0, "トレンドスコアが範囲外です"
            assert candidate.total_score > 0, "総合スコアが0以下です"
        
        print(f"✅ {len(candidates)}個のテーマ候補が正常に生成されました")
        for i, candidate in enumerate(candidates, 1):
            print(f"  {i}. {candidate.theme} (スコア: {candidate.total_score:.1f})")
    
    def test_theme_evaluation_and_ranking(self, llm_client):
        """テーマ評価・ランキング機能テスト"""
        
        gemini_llm = GeminiThemeLLM(llm_client)
        
        preferences = UserPreferences(
            genre_history=["科学"],
            preferred_genres=["教育"],
            excluded_genres=[],
            target_audience="一般",
            content_style="親しみやすい"
        )
        
        # まずテーマ候補を生成
        candidates = gemini_llm.generate_theme_candidates(preferences, count=3)
        assert len(candidates) > 0
        
        # 評価・ランキング実行
        ranked_candidates = gemini_llm.evaluate_and_rank_themes(candidates, preferences)
        
        # 結果検証
        assert len(ranked_candidates) == len(candidates), "候補数が変わりました"
        
        # スコア順にソートされているか確認
        for i in range(len(ranked_candidates) - 1):
            assert (ranked_candidates[i].total_score >= 
                   ranked_candidates[i + 1].total_score), "スコア順にソートされていません"
        
        print(f"✅ テーマ評価・ランキングが正常に動作しました")
        for i, candidate in enumerate(ranked_candidates, 1):
            print(f"  {i}. {candidate.theme} (スコア: {candidate.total_score:.1f})")
    
    def test_complete_theme_selection_workflow(
        self, 
        theme_dao, 
        config_manager, 
        llm_client, 
        test_project_id,
        temp_project_dir
    ):
        """完全なテーマ選定ワークフローテスト"""
        
        # 1. データアクセス層準備
        data_access = DatabaseDataAccess(
            repository=ProjectRepository(theme_dao.db_manager),
            config_manager=config_manager
        )
        
        # 2. LLM層準備
        llm_interface = GeminiThemeLLM(llm_client)
        
        # 3. テーマセレクター初期化
        theme_selector = ThemeSelector(
            data_access=data_access,
            llm_interface=llm_interface
        )
        
        # 4. 入力データ準備
        user_preferences = UserPreferences(
            genre_history=["科学", "技術"],
            preferred_genres=["教育"],
            excluded_genres=["政治"],
            target_audience="学生",
            content_style="分かりやすい"
        )
        
        input_data = ThemeSelectionInput(
            project_id=test_project_id,
            user_preferences=user_preferences,
            llm_config={"model": "gemini-2.0-flash-exp", "temperature": 0.8},
            max_candidates=3
        )
        
        # 5. プロジェクトディレクトリ作成（ファイル保存用）
        project_dir = temp_project_dir / "projects" / test_project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # 6. テーマ選定実行
        output = theme_selector.select_theme(input_data)
        
        # 7. 結果検証
        assert isinstance(output, ThemeSelectionOutput), "出力型が正しくありません"
        assert output.selected_theme, "選択されたテーマが空です"
        assert output.candidates, "候補が空です"
        assert len(output.candidates) > 0, "候補数が0です"
        
        # 8. データベース保存確認
        project_info = theme_dao.get_project_info(test_project_id)
        assert project_info["theme"] == output.selected_theme.theme, "DBのテーマが更新されていません"
        
        step_result = theme_dao.get_workflow_step_result(test_project_id, "theme_selection")
        assert step_result["status"] == "completed", "ワークフローステップが完了していません"
        
        print(f"✅ 完全なテーマ選定ワークフローが正常に動作しました")
        print(f"  選択テーマ: {output.selected_theme.theme}")
        print(f"  候補数: {len(output.candidates)}")
        print(f"  カテゴリ: {output.selected_theme.category}")
        print(f"  目標長: {output.selected_theme.target_length_minutes}分")
    
    def test_error_handling_and_recovery(self, theme_dao, config_manager, test_project_id):
        """エラーハンドリングと復旧テスト"""
        
        # 無効なAPIキーでLLMクライアント作成
        invalid_llm_client = GeminiLLMClient(api_key="invalid_key")
        llm_interface = GeminiThemeLLM(invalid_llm_client)
        
        data_access = DatabaseDataAccess(
            repository=ProjectRepository(theme_dao.db_manager),
            config_manager=config_manager
        )
        
        theme_selector = ThemeSelector(
            data_access=data_access,
            llm_interface=llm_interface
        )
        
        user_preferences = UserPreferences(
            genre_history=[],
            preferred_genres=["教育"],
            excluded_genres=[],
            target_audience="一般",
            content_style="親しみやすい"
        )
        
        input_data = ThemeSelectionInput(
            project_id=test_project_id,
            user_preferences=user_preferences,
            llm_config={"model": "gemini-2.0-flash-exp"},
            max_candidates=3
        )
        
        # エラーが適切に処理されることを確認
        with pytest.raises(Exception):
            theme_selector.select_theme(input_data)
        
        print("✅ エラーハンドリングが正常に動作しました")
    
    def test_high_level_text_generation_integration(self):
        """高レベルテキスト生成関数との統合テスト"""
        
        # 高レベル関数を使用してテーマ生成
        prompt = """
        ゆっくり動画のテーマを3つ提案してください。
        条件：
        - 教育系コンテンツ
        - 5-7分程度の動画
        - 初心者向け
        
        JSON形式で回答してください。
        """
        
        # 実際のLLM呼び出し
        result = generate_text(prompt)
        
        assert result, "高レベル関数からの結果が空です"
        assert len(result) > 10, "結果が短すぎます"
        
        print(f"✅ 高レベル関数との統合が正常に動作しました")
        print(f"  結果長: {len(result)}文字")


if __name__ == "__main__":
    # 統合テストの個別実行
    pytest.main([__file__, "-v", "-s"]) 