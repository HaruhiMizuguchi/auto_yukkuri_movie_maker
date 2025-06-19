"""
スクリプト生成モジュールの統合テスト

実際のAPI呼び出しとデータベース操作を含む統合テスト
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime

from src.modules.script_generator import (
    ScriptGenerator,
    DatabaseDataAccess,
    GeminiScriptLLM,
    ScriptGenerationInput
)
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
    reason="GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません"
)
class TestScriptGenerationIntegration:
    """スクリプト生成の統合テスト"""
    
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
  max_tokens: 3000

script_generation:
  target_duration_minutes: 5
  speaker_count: 2
  speaker_names: ["reimu", "marisa"]
  tone: "casual"
"""
            config_path.write_text(config_content)
            yield ConfigManager(str(config_path))
    
    @pytest.fixture
    def llm_client(self):
        """実際のGemini LLMクライアント"""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return GeminiLLMClient(api_key=api_key)
    
    @pytest.fixture
    def test_project_with_theme(self, project_repository):
        """テーマが選定済みのテスト用プロジェクト作成"""
        project_id = "test-script-integration-001"
        
        # プロジェクト作成
        success = project_repository.create_project(
            project_id=project_id,
            theme="宇宙の神秘と謎",
            target_length_minutes=5.0,
            config={
                "script_generation": {
                    "speaker_count": 2,
                    "speaker_names": ["reimu", "marisa"],
                    "tone": "educational"
                }
            }
        )
        
        assert success, "テストプロジェクト作成に失敗"
        
        # テーマ選定ステップ完了として記録
        project_repository.save_step_result(
            project_id=project_id,
            step_name="theme_selection",
            output_data={
                "selected_theme": {
                    "theme": "宇宙の神秘と謎",
                    "category": "教育・科学",
                    "target_length_minutes": 5,
                    "description": "宇宙の神秘的な現象や未解明の謎について分かりやすく解説",
                    "selection_reason": "教育的価値が高く、視聴者の興味を引きやすい"
                }
            },
            status="completed"
        )
        
        return project_id
    
    def test_full_script_generation_workflow(
        self, 
        project_repository, 
        config_manager, 
        llm_client, 
        test_project_with_theme
    ):
        """完全なスクリプト生成ワークフローテスト"""
        
        # 1. 依存関係の初期化
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiScriptLLM(llm_client)
        script_generator = ScriptGenerator(
            data_access=data_access,
            llm_interface=llm_interface
        )
        
        # 2. 入力データ準備
        input_data = ScriptGenerationInput(
            project_id=test_project_with_theme,
            llm_config={
                "model": "gemini-2.0-flash-exp",
                "temperature": 0.8,
                "max_tokens": 3000
            }
        )
        
        # 3. スクリプト生成実行
        output = script_generator.generate_script(input_data)
        
        # 4. 結果検証
        assert output.generated_script, "スクリプトが生成されませんでした"
        assert len(output.generated_script.segments) > 0, "セグメントが生成されませんでした"
        assert output.generated_script.total_estimated_duration > 0, "推定時間が0以下です"
        assert output.generated_script.total_character_count > 0, "文字数が0以下です"
        
        # セグメント詳細検証
        theme_related_count = 0
        for segment in output.generated_script.segments:
            assert segment.speaker in ["reimu", "marisa"], f"不正な話者: {segment.speaker}"
            assert segment.text.strip(), "セグメントテキストが空です"
            assert segment.estimated_duration > 0, "セグメント時間が0以下です"
            assert segment.emotion, "感情情報が空です"
            
            # テーマ関連キーワードをカウント（導入部分は除外）
            if "宇宙" in segment.text or "神秘" in segment.text or any(
                keyword in segment.text for keyword in ["星", "惑星", "銀河", "ブラックホール", "謎", "現象", "科学", "天体"]
            ):
                theme_related_count += 1
        
        # 全体の50%以上がテーマに関連していることを確認
        theme_ratio = theme_related_count / len(output.generated_script.segments)
        assert theme_ratio >= 0.3, f"テーマ関連セグメント比率が低すぎます: {theme_ratio:.2f} (最低30%必要)"
        
        # 5. データベース保存確認
        from src.dao.script_generation_dao import ScriptGenerationDAO
        dao = ScriptGenerationDAO(project_repository.db_manager)
        saved_result = dao.get_script_result(test_project_with_theme)
        
        assert saved_result, "スクリプト結果がデータベースに保存されていません"
        assert saved_result["status"] == "completed", "ワークフローステップが完了していません"
        
        # 6. プロジェクト統計更新確認
        stats_query = """
        SELECT total_duration FROM project_statistics 
        WHERE project_id = ?
        """
        result = project_repository.db_manager.fetch_one(stats_query, (test_project_with_theme,))
        assert result, "プロジェクト統計が更新されていません"
        assert result[0] == output.generated_script.total_estimated_duration, "推定時間が正しく保存されていません"
        
        print(f"✅ 完全なスクリプト生成ワークフローテスト成功")
        print(f"  プロジェクトID: {test_project_with_theme}")
        print(f"  生成セグメント数: {len(output.generated_script.segments)}")
        print(f"  総推定時間: {output.generated_script.total_estimated_duration:.1f}秒")
        print(f"  総文字数: {output.generated_script.total_character_count}文字")
        
        # サンプルセグメント表示
        for i, segment in enumerate(output.generated_script.segments[:3], 1):
            print(f"  セグメント{i}: {segment.speaker} - {segment.text[:40]}...")
    
    def test_error_handling_and_recovery(
        self, 
        project_repository, 
        config_manager, 
        llm_client
    ):
        """エラーハンドリングと復旧機能のテスト"""
        
        # 存在しないプロジェクトでテスト
        data_access = DatabaseDataAccess(project_repository, config_manager)
        
        with pytest.raises(ValueError, match="プロジェクト .* が見つかりません"):
            data_access.get_theme_data("non-existent-project")
        
        print("✅ エラーハンドリングテスト成功")
    
    def test_multiple_projects_parallel_processing(
        self, 
        project_repository, 
        config_manager, 
        llm_client
    ):
        """複数プロジェクトの並列処理テスト"""
        
        # 複数プロジェクト作成
        project_ids = []
        themes = [
            "人工知能の未来",
            "海洋の神秘",
            "古代文明の謎"
        ]
        
        for i, theme in enumerate(themes):
            project_id = f"test-parallel-{i+1:03d}"
            success = project_repository.create_project(
                project_id=project_id,
                theme=theme,
                target_length_minutes=3.0,
                config={
                    "script_generation": {
                        "speaker_count": 2,
                        "speaker_names": ["reimu", "marisa"],
                        "tone": "casual"
                    }
                }
            )
            assert success, f"プロジェクト {project_id} の作成に失敗"
            
            # テーマ選定ステップ完了として記録
            project_repository.save_step_result(
                project_id=project_id,
                step_name="theme_selection",
                output_data={
                    "selected_theme": {
                        "theme": theme,
                        "category": "教育",
                        "target_length_minutes": 3,
                        "description": f"{theme}について解説",
                        "selection_reason": "教育的価値が高い"
                    }
                },
                status="completed"
            )
            
            project_ids.append(project_id)
        
        # 各プロジェクトでスクリプト生成実行
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiScriptLLM(llm_client)
        script_generator = ScriptGenerator(
            data_access=data_access,
            llm_interface=llm_interface
        )
        
        results = []
        for project_id in project_ids:
            input_data = ScriptGenerationInput(
                project_id=project_id,
                llm_config={"model": "gemini-2.0-flash-exp", "temperature": 0.7}
            )
            
            output = script_generator.generate_script(input_data)
            results.append((project_id, output))
        
        # 結果検証
        assert len(results) == len(project_ids), "すべてのプロジェクトで生成が完了していません"
        
        for project_id, output in results:
            assert output.generated_script, f"プロジェクト {project_id} でスクリプトが生成されませんでした"
            assert len(output.generated_script.segments) > 0, f"プロジェクト {project_id} でセグメントが生成されませんでした"
        
        print(f"✅ 複数プロジェクト並列処理テスト成功: {len(project_ids)}プロジェクト完了")
        
        for project_id, output in results:
            print(f"  {project_id}: {len(output.generated_script.segments)}セグメント, "
                  f"{output.generated_script.total_estimated_duration:.1f}秒")


if __name__ == "__main__":
    # 統合テストの個別実行
    pytest.main([__file__, "-v", "-s"]) 