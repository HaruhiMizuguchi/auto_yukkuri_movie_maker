"""
タイトル生成モジュールの実API統合テスト

TDD方式で実装前にテストを作成し、実際のLLM生成とDB保存をテスト
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from src.modules.title_generator import (
    TitleGenerator,
    DatabaseDataAccess,
    GeminiTitleLLM,
    TitleConfig,
    TitleCandidate,
    GeneratedTitles,
    TitleGenerationInput,
    TitleGenerationOutput
)
from src.dao.title_generation_dao import TitleGenerationDAO
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
    reason="GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません"
)
class TestTitleGeneratorRealAPI:
    """タイトル生成モジュールの実API統合テスト"""
    
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
  max_tokens: 1000

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
    def test_project_with_script(self, project_repository):
        """スクリプトが生成済みのテスト用プロジェクト作成"""
        project_id = "test-title-generation-001"
        
        # プロジェクト作成
        success = project_repository.create_project(
            project_id=project_id,
            theme="未来の宇宙探査技術",
            target_length_minutes=5.0,
            config={
                "title_generation": {
                    "candidate_count": 5,
                    "max_title_length": 100,
                    "ctr_optimization": True
                }
            }
        )
        
        assert success, "テストプロジェクト作成に失敗"
        
        # テーマ選定ワークフローステップ作成
        project_repository.create_workflow_step(
            project_id=project_id,
            step_number=1,
            step_name="theme_selection"
        )
        
        # テーマ選定ステップ完了として記録
        project_repository.save_step_result(
            project_id=project_id,
            step_name="theme_selection",
            output_data={
                "selected_theme": {
                    "theme": "未来の宇宙探査技術",
                    "category": "科学・技術",
                    "target_length_minutes": 5,
                    "description": "未来の宇宙探査で使われる革新的な技術について解説",
                    "selection_reason": "科学技術への関心が高く、視聴者の興味を引きやすい"
                }
            },
            status="completed"
        )
        
        # スクリプト生成ワークフローステップ作成
        project_repository.create_workflow_step(
            project_id=project_id,
            step_number=2,
            step_name="script_generation"
        )
        
        # スクリプト生成ステップ完了として記録
        project_repository.save_step_result(
            project_id=project_id,
            step_name="script_generation",
            output_data={
                "generated_script": {
                    "segments": [
                        {
                            "segment_id": 1,
                            "speaker": "reimu",
                            "text": "みんな、こんにちは！霊夢よ。今日は未来の宇宙探査技術について話すわ。",
                            "estimated_duration": 5.0,
                            "emotion": "happy"
                        },
                        {
                            "segment_id": 2,
                            "speaker": "marisa",
                            "text": "魔理沙だぜ！宇宙探査って言うと、どんな技術があるんだ？",
                            "estimated_duration": 4.5,
                            "emotion": "curious"
                        },
                        {
                            "segment_id": 3,
                            "speaker": "reimu",
                            "text": "例えば、イオン推進システムや核融合エンジンなど、革新的な推進技術があるのよ。",
                            "estimated_duration": 6.0,
                            "emotion": "neutral"
                        }
                    ],
                    "total_estimated_duration": 15.5,
                    "total_character_count": 95
                }
            },
            status="completed"
        )
        
        return project_id
    
    def test_dao_operations(self, project_repository, test_project_with_script):
        """DAO操作テスト"""
        
        # DAO初期化
        dao = TitleGenerationDAO(project_repository.db_manager)
        
        # 1. プロジェクトデータ取得テスト
        project_data = dao.get_project_data(test_project_with_script)
        
        assert project_data["theme"] == "未来の宇宙探査技術"
        assert project_data["target_length_minutes"] == 5.0
        assert "config" in project_data
        
        # 2. スクリプトデータ取得テスト
        script_data = dao.get_script_data(test_project_with_script)
        
        assert script_data["status"] == "completed"
        assert "generated_script" in script_data["output_data"]
        assert len(script_data["output_data"]["generated_script"]["segments"]) == 3
        
        # 3. タイトル結果保存テスト
        test_titles = GeneratedTitles(
            candidates=[
                TitleCandidate(
                    title="【ゆっくり解説】未来の宇宙探査技術TOP5！驚きの推進システムとは？",
                    ctr_score=8.5,
                    keyword_score=9.0,
                    length_score=8.0,
                    total_score=8.5,
                    reasons=["科学技術への関心", "数字による具体性", "疑問形で興味喚起"]
                ),
                TitleCandidate(
                    title="宇宙探査の未来！核融合エンジンの秘密",
                    ctr_score=7.8,
                    keyword_score=8.5,
                    length_score=9.0,
                    total_score=8.1,
                    reasons=["未来感のあるキーワード", "秘密で興味喚起"]
                )
            ],
            selected_title="【ゆっくり解説】未来の宇宙探査技術TOP5！驚きの推進システムとは？",
            generation_timestamp=datetime.now()
        )
        
        dao.save_title_result(test_project_with_script, test_titles, "completed")
        
        # 4. 保存されたタイトル結果取得テスト
        saved_result = dao.get_title_result(test_project_with_script)
        
        assert saved_result is not None
        assert saved_result["status"] == "completed"
        assert "generated_titles" in saved_result["output_data"]
        assert saved_result["output_data"]["generated_titles"]["selected_title"] == test_titles.selected_title
        
        print("✅ DAO操作テスト成功")
    
    def test_llm_title_generation(self, llm_client):
        """LLMタイトル生成テスト"""
        
        # LLMインターフェース初期化
        llm_interface = GeminiTitleLLM(llm_client)
        
        # テスト用設定
        config = TitleConfig(
            candidate_count=5,
            max_title_length=100,
            min_title_length=10,
            keywords_weight=0.3,
            ctr_optimization=True
        )
        
        # テスト用データ
        theme_data = {
            "theme": "未来の宇宙探査技術",
            "category": "科学・技術",
            "description": "未来の宇宙探査で使われる革新的な技術について解説"
        }
        
        script_summary = {
            "key_points": ["イオン推進システム", "核融合エンジン", "革新的な推進技術"],
            "total_duration": 15.5,
            "character_count": 95
        }
        
        # タイトル生成実行
        generated_titles = llm_interface.generate_titles(theme_data, script_summary, config)
        
        # 結果検証
        assert generated_titles, "タイトルが生成されませんでした"
        assert len(generated_titles.candidates) > 0, "タイトル候補が生成されませんでした"
        assert generated_titles.selected_title, "選択されたタイトルが設定されていません"
        
        # 各候補の検証
        for candidate in generated_titles.candidates:
            assert candidate.title.strip(), "タイトルが空です"
            assert len(candidate.title) >= config.min_title_length, f"タイトルが短すぎます: {candidate.title}"
            assert len(candidate.title) <= config.max_title_length, f"タイトルが長すぎます: {candidate.title}"
            assert candidate.ctr_score > 0, "CTRスコアが0以下です"
            assert candidate.total_score > 0, "総合スコアが0以下です"
            assert candidate.reasons, "選定理由が空です"
            
            # テーマ関連キーワードの確認
            title_lower = candidate.title.lower()
            assert any(keyword in title_lower for keyword in ["宇宙", "探査", "技術", "未来", "推進"]), \
                f"テーマに関連しないタイトル: {candidate.title}"
        
        print(f"✅ LLM タイトル生成テスト成功: {len(generated_titles.candidates)}候補生成")
        print(f"  選択タイトル: {generated_titles.selected_title}")
        for i, candidate in enumerate(generated_titles.candidates[:3], 1):
            print(f"  候補{i}: {candidate.title} (スコア: {candidate.total_score:.1f})")
    
    def test_database_data_access(self, project_repository, config_manager, test_project_with_script):
        """DatabaseDataAccessクラステスト"""
        
        # DatabaseDataAccess初期化
        data_access = DatabaseDataAccess(project_repository, config_manager)
        
        # 1. プロジェクトデータ取得テスト
        project_data = data_access.get_project_data(test_project_with_script)
        
        assert project_data["theme"] == "未来の宇宙探査技術"
        assert project_data["target_length_minutes"] == 5.0
        
        # 2. スクリプトデータ取得テスト
        script_data = data_access.get_script_data(test_project_with_script)
        
        assert "key_points" in script_data
        assert "total_duration" in script_data
        assert script_data["total_duration"] == 15.5
        
        # 3. タイトル設定保存テスト
        test_titles = GeneratedTitles(
            candidates=[
                TitleCandidate(
                    title="【ゆっくり解説】宇宙探査の未来技術",
                    ctr_score=8.0,
                    keyword_score=8.5,
                    length_score=9.0,
                    total_score=8.5,
                    reasons=["科学技術への関心", "ゆっくり解説ブランド"]
                )
            ],
            selected_title="【ゆっくり解説】宇宙探査の未来技術",
            generation_timestamp=datetime.now()
        )
        
        data_access.save_title_result(test_project_with_script, test_titles, "completed")
        
        # 4. 保存確認
        from src.dao.title_generation_dao import TitleGenerationDAO
        dao = TitleGenerationDAO(project_repository.db_manager)
        saved_result = dao.get_title_result(test_project_with_script)
        
        assert saved_result is not None
        assert saved_result["status"] == "completed"
        
        print("✅ DatabaseDataAccessテスト成功")
    
    def test_title_generator_integration(
        self, 
        project_repository, 
        config_manager, 
        llm_client, 
        test_project_with_script
    ):
        """TitleGeneratorの統合テスト"""
        
        # 1. 依存関係の初期化
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiTitleLLM(llm_client)
        title_generator = TitleGenerator(
            data_access=data_access,
            llm_interface=llm_interface
        )
        
        # 2. 入力データ準備
        input_data = TitleGenerationInput(
            project_id=test_project_with_script,
            llm_config={
                "model": "gemini-2.0-flash-exp",
                "temperature": 0.7,
                "max_tokens": 1000
            }
        )
        
        # 3. タイトル生成実行
        output = title_generator.generate_titles(input_data)
        
        # 4. 結果検証
        assert output.generated_titles, "タイトルが生成されませんでした"
        assert len(output.generated_titles.candidates) > 0, "タイトル候補が生成されませんでした"
        assert output.generated_titles.selected_title, "選択されたタイトルが設定されていません"
        
        # 5. 品質検証
        selected_title = output.generated_titles.selected_title
        assert len(selected_title) >= 10, "選択されたタイトルが短すぎます"
        assert len(selected_title) <= 100, "選択されたタイトルが長すぎます"
        
        # テーマ関連性検証
        title_lower = selected_title.lower()
        assert any(keyword in title_lower for keyword in ["宇宙", "探査", "技術", "未来"]), \
            f"テーマに関連しないタイトル: {selected_title}"
        
        # 6. データベース保存確認
        from src.dao.title_generation_dao import TitleGenerationDAO
        dao = TitleGenerationDAO(project_repository.db_manager)
        saved_result = dao.get_title_result(test_project_with_script)
        
        assert saved_result, "タイトル結果がデータベースに保存されていません"
        assert saved_result["status"] == "completed", "ワークフローステップが完了していません"
        
        print(f"✅ TitleGenerator統合テスト成功")
        print(f"  生成候補数: {len(output.generated_titles.candidates)}")
        print(f"  選択タイトル: {selected_title}")
        
        # サンプル候補表示
        for i, candidate in enumerate(output.generated_titles.candidates[:3], 1):
            print(f"  候補{i}: {candidate.title} (スコア: {candidate.total_score:.1f})")


if __name__ == "__main__":
    # 単体テストの個別実行
    pytest.main([__file__, "-v", "-s"]) 