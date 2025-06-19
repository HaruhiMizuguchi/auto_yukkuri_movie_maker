"""
タイトル生成モジュールの統合テスト

実際のAPI呼び出しとデータベース操作を含む統合テスト
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime

from src.modules.title_generator import (
    TitleGenerator,
    DatabaseDataAccess,
    GeminiTitleLLM,
    TitleGenerationInput
)
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
    reason="GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません"
)
class TestTitleGenerationIntegration:
    """タイトル生成の統合テスト"""
    
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
  temperature: 0.7
  max_tokens: 1500

title_generation:
  candidate_count: 5
  max_title_length: 100
  min_title_length: 10
  keywords_weight: 0.3
  ctr_optimization: true
"""
            config_path.write_text(config_content)
            yield ConfigManager(str(config_path))
    
    @pytest.fixture
    def llm_client(self):
        """実際のGemini LLMクライアント"""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return GeminiLLMClient(api_key=api_key)
    
    @pytest.fixture
    def title_generator(self, project_repository, config_manager, llm_client):
        """タイトル生成器"""
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiTitleLLM(llm_client)
        return TitleGenerator(data_access=data_access, llm_interface=llm_interface)
    
    def test_full_title_generation_workflow(
        self, 
        project_repository, 
        title_generator
    ):
        """完全なタイトル生成ワークフローテスト"""
        
        # 1. プロジェクト作成
        project_id = "test-title-integration-001"
        success = project_repository.create_project(
            project_id=project_id,
            theme="古代文明の謎と最新考古学",
            target_length_minutes=8.0,
            config={
                "title_generation": {
                    "candidate_count": 5,
                    "max_title_length": 100,
                    "ctr_optimization": True
                }
            }
        )
        
        assert success, "プロジェクト作成に失敗"
        
        # 2. 前提となるワークフローステップを作成
        # テーマ選定ステップ
        project_repository.create_workflow_step(
            project_id=project_id,
            step_number=1,
            step_name="theme_selection"
        )
        
        project_repository.save_step_result(
            project_id=project_id,
            step_name="theme_selection",
            output_data={
                "selected_theme": {
                    "theme": "古代文明の謎と最新考古学",
                    "category": "歴史・考古学",
                    "description": "古代文明の未解明な謎と最新の考古学技術による発見",
                    "selection_reason": "歴史ミステリーは視聴者の関心が高い"
                }
            },
            status="completed"
        )
        
        # スクリプト生成ステップ
        project_repository.create_workflow_step(
            project_id=project_id,
            step_number=2,
            step_name="script_generation"
        )
        
        project_repository.save_step_result(
            project_id=project_id,
            step_name="script_generation",
            output_data={
                "generated_script": {
                    "segments": [
                        {
                            "segment_id": 1,
                            "speaker": "reimu",
                            "text": "今日は古代文明の謎について話すわよ。最新の考古学技術で何が分かったのかしら？",
                            "estimated_duration": 6.0,
                            "emotion": "curious"
                        },
                        {
                            "segment_id": 2,
                            "speaker": "marisa",
                            "text": "LiDARスキャンとか、すごい技術があるんだぜ！隠された遺跡も見つけられるんだ。",
                            "estimated_duration": 5.5,
                            "emotion": "excited"
                        },
                        {
                            "segment_id": 3,
                            "speaker": "reimu",
                            "text": "エジプトのピラミッドにも隠し部屋が見つかったのよね。古代の技術って本当に謎だらけ。",
                            "estimated_duration": 7.0,
                            "emotion": "amazed"
                        }
                    ],
                    "total_estimated_duration": 18.5,
                    "total_character_count": 125
                }
            },
            status="completed"
        )
        
        # 3. タイトル生成実行
        input_data = TitleGenerationInput(
            project_id=project_id,
            llm_config={
                "model": "gemini-2.0-flash-exp",
                "temperature": 0.7,
                "max_tokens": 1500
            }
        )
        
        output = title_generator.generate_titles(input_data)
        
        # 4. 結果検証
        assert output.generated_titles, "タイトルが生成されませんでした"
        assert len(output.generated_titles.candidates) > 0, "タイトル候補が生成されませんでした"
        assert output.generated_titles.selected_title, "選択されたタイトルが設定されていません"
        
        # 5. 品質検証
        selected_title = output.generated_titles.selected_title
        assert len(selected_title) >= 10, "選択されたタイトルが短すぎます"
        assert len(selected_title) <= 100, "選択されたタイトルが長すぎます"
        
        # テーマ関連性検証（緩い条件）
        title_lower = selected_title.lower()
        theme_keywords = ["古代", "文明", "謎", "考古学", "遺跡", "発見", "歴史", "ピラミッド", "エジプト"]
        theme_related_count = sum(1 for keyword in theme_keywords if keyword in title_lower)
        assert theme_related_count >= 1, f"テーマに関連しないタイトル: {selected_title}"
        
        # 6. データベース保存確認
        from src.dao.title_generation_dao import TitleGenerationDAO
        dao = TitleGenerationDAO(project_repository.db_manager)
        saved_result = dao.get_title_result(project_id)
        
        assert saved_result, "タイトル結果がデータベースに保存されていません"
        assert saved_result["status"] == "completed", "ワークフローステップが完了していません"
        assert "generated_titles" in saved_result["output_data"], "タイトルデータが保存されていません"
        
        print(f"✅ 完全ワークフローテスト成功")
        print(f"  生成候補数: {len(output.generated_titles.candidates)}")
        print(f"  選択タイトル: {selected_title}")
        
        # サンプル候補表示
        for i, candidate in enumerate(output.generated_titles.candidates[:3], 1):
            print(f"  候補{i}: {candidate.title} (スコア: {candidate.total_score:.1f})")
    
    def test_error_handling_and_recovery(
        self, 
        project_repository, 
        title_generator
    ):
        """エラーハンドリングと回復テスト"""
        
        # 1. 不完全なプロジェクトでのタイトル生成
        project_id = "test-title-error-001"
        project_repository.create_project(
            project_id=project_id,
            theme="テストテーマ",
            target_length_minutes=3.0
        )
        
        # スクリプトデータなしでタイトル生成を試行
        input_data = TitleGenerationInput(
            project_id=project_id,
            llm_config={"model": "gemini-2.0-flash-exp"}
        )
        
        # エラーが発生しても適切にハンドリングされることを確認
        try:
            output = title_generator.generate_titles(input_data)
            # フォールバック結果が返されることを確認
            assert output.generated_titles, "フォールバック結果が生成されませんでした"
            assert output.generated_titles.selected_title, "フォールバックタイトルが設定されていません"
            print(f"✅ エラーハンドリングテスト成功: {output.generated_titles.selected_title}")
        except Exception as e:
            pytest.fail(f"エラーハンドリングが適切に動作しませんでした: {e}")
    
    def test_multiple_themes_parallel_processing(
        self,
        project_repository,
        title_generator
    ):
        """複数テーマの並列処理テスト"""
        
        themes = [
            ("量子コンピューターの仕組み", "科学・技術"),
            ("日本の城の建築技術", "歴史・建築"),
            ("深海生物の不思議な生態", "自然・生物")
        ]
        
        results = []
        
        for i, (theme, category) in enumerate(themes, 1):
            project_id = f"test-title-parallel-{i:03d}"
            
            # プロジェクト作成
            project_repository.create_project(
                project_id=project_id,
                theme=theme,
                target_length_minutes=5.0,
                config={"title_generation": {"candidate_count": 3}}
            )
            
            # 前提ステップ作成
            project_repository.create_workflow_step(
                project_id=project_id,
                step_number=1,
                step_name="theme_selection"
            )
            
            project_repository.save_step_result(
                project_id=project_id,
                step_name="theme_selection",
                output_data={
                    "selected_theme": {
                        "theme": theme,
                        "category": category,
                        "description": f"{theme}について詳しく解説"
                    }
                },
                status="completed"
            )
            
            project_repository.create_workflow_step(
                project_id=project_id,
                step_number=2,
                step_name="script_generation"
            )
            
            project_repository.save_step_result(
                project_id=project_id,
                step_name="script_generation",
                output_data={
                    "generated_script": {
                        "segments": [
                            {
                                "segment_id": 1,
                                "speaker": "reimu",
                                "text": f"{theme}について説明するわね。",
                                "estimated_duration": 3.0,
                                "emotion": "neutral"
                            }
                        ],
                        "total_estimated_duration": 3.0,
                        "total_character_count": 20
                    }
                },
                status="completed"
            )
            
            # タイトル生成
            input_data = TitleGenerationInput(
                project_id=project_id,
                llm_config={"model": "gemini-2.0-flash-exp", "temperature": 0.8}
            )
            
            output = title_generator.generate_titles(input_data)
            results.append((theme, output.generated_titles))
        
        # 結果検証
        assert len(results) == 3, "3つのプロジェクトすべてでタイトル生成が完了していません"
        
        total_candidates = 0
        for theme, generated_titles in results:
            assert generated_titles.selected_title, f"{theme}の選択タイトルが設定されていません"
            assert len(generated_titles.candidates) > 0, f"{theme}のタイトル候補が生成されていません"
            total_candidates += len(generated_titles.candidates)
        
        print(f"✅ 並列処理テスト成功")
        print(f"  処理プロジェクト数: {len(results)}")
        print(f"  総候補数: {total_candidates}")
        
        for theme, generated_titles in results:
            print(f"  {theme}: {generated_titles.selected_title}")


if __name__ == "__main__":
    # 統合テストの個別実行
    pytest.main([__file__, "-v", "-s"]) 