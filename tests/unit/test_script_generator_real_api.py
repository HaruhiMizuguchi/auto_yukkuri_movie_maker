"""
スクリプト生成モジュールの実API統合テスト

TDD方式で実装前にテストを作成し、実際のLLM生成とDB保存をテスト
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from src.modules.script_generator import (
    ScriptGenerator,
    DatabaseDataAccess,
    GeminiScriptLLM,
    ScriptConfig,
    ScriptSegment,
    GeneratedScript,
    ScriptGenerationInput,
    ScriptGenerationOutput
)
from src.dao.script_generation_dao import ScriptGenerationDAO
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
    reason="GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません"
)
class TestScriptGeneratorRealAPI:
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
        project_id = "test-script-gen-001"
        
        # プロジェクト作成
        success = project_repository.create_project(
            project_id=project_id,
            theme="科学の不思議な現象",
            target_length_minutes=5.0,
            config={
                "script_generation": {
                    "speaker_count": 2,
                    "speaker_names": ["reimu", "marisa"],
                    "tone": "casual"
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
                    "theme": "科学の不思議な現象",
                    "category": "教育",
                    "target_length_minutes": 5,
                    "description": "日常に隠れた科学現象を分かりやすく解説",
                    "selection_reason": "教育的価値が高い"
                }
            },
            status="completed"
        )
        
        return project_id
    
    def test_dao_operations(self, db_manager, test_project_with_theme):
        """DAO基本操作テスト"""
        dao = ScriptGenerationDAO(db_manager)
        
        # プロジェクトテーマ取得
        theme_data = dao.get_project_theme(test_project_with_theme)
        assert theme_data["theme"] == "科学の不思議な現象"
        assert theme_data["target_length_minutes"] == 5.0
        
        # スクリプト設定取得
        script_config = dao.get_script_config(test_project_with_theme)
        assert script_config["speaker_count"] == 2
        assert "reimu" in script_config["speaker_names"]
        
        # スクリプト結果保存テスト
        test_script = GeneratedScript(
            segments=[
                ScriptSegment(
                    segment_id=1,
                    speaker="reimu",
                    text="こんにちは！今日は科学の話をするよ！",
                    estimated_duration=3.5,
                    emotion="happy"
                )
            ],
            total_estimated_duration=3.5,
            total_character_count=20,
            generation_timestamp=datetime.now()
        )
        
        dao.save_script_result(
            project_id=test_project_with_theme,
            script=test_script,
            status="completed"
        )
        
        # 保存確認
        saved_result = dao.get_script_result(test_project_with_theme)
        assert saved_result["status"] == "completed"
        
        print("✅ DAO操作テスト成功")
    
    def test_llm_script_generation(self, llm_client):
        """LLMスクリプト生成テスト"""
        gemini_llm = GeminiScriptLLM(llm_client)
        
        script_config = ScriptConfig(
            target_duration_minutes=5,
            speaker_count=2,
            speaker_names=["reimu", "marisa"],
            tone="casual"
        )
        
        theme_data = {
            "theme": "科学の不思議な現象",
            "description": "日常に隠れた科学現象を分かりやすく解説",
            "target_length_minutes": 5
        }
        
        # スクリプト生成
        script = gemini_llm.generate_script(theme_data, script_config)
        
        # 結果検証
        assert isinstance(script, GeneratedScript), "スクリプトが生成されませんでした"
        assert len(script.segments) > 0, "セグメントが生成されませんでした"
        assert script.total_estimated_duration > 0, "推定時間が0以下です"
        assert script.total_character_count > 0, "文字数が0以下です"
        
        # セグメント詳細確認
        for segment in script.segments:
            assert segment.speaker in ["reimu", "marisa"], f"不正な話者: {segment.speaker}"
            assert segment.text.strip(), "セグメントテキストが空です"
            assert segment.estimated_duration > 0, "セグメント時間が0以下です"
            assert segment.emotion, "感情情報が空です"
        
        print(f"✅ LLMスクリプト生成テスト成功: {len(script.segments)}セグメント生成")
        print(f"  総推定時間: {script.total_estimated_duration:.1f}秒")
        print(f"  総文字数: {script.total_character_count}文字")
        
        # 最初の数セグメントを表示
        for i, segment in enumerate(script.segments[:3], 1):
            print(f"  セグメント{i}: {segment.speaker} - {segment.text[:50]}...")
    
    def test_database_data_access(self, project_repository, config_manager, test_project_with_theme):
        """DatabaseDataAccessクラステスト"""
        data_access = DatabaseDataAccess(project_repository, config_manager)
        
        # テーマデータ取得
        theme_data = data_access.get_theme_data(test_project_with_theme)
        assert theme_data["theme"] == "科学の不思議な現象"
        
        # スクリプト設定取得
        script_config = data_access.get_script_config(test_project_with_theme)
        assert script_config.speaker_count == 2
        assert "reimu" in script_config.speaker_names
        
        # スクリプト結果保存テスト
        test_script = GeneratedScript(
            segments=[
                ScriptSegment(
                    segment_id=1,
                    speaker="reimu",
                    text="テストセグメント",
                    estimated_duration=2.0,
                    emotion="neutral"
                )
            ],
            total_estimated_duration=2.0,
            total_character_count=7,
            generation_timestamp=datetime.now()
        )
        
        output = ScriptGenerationOutput(
            generated_script=test_script,
            script_metadata={"test": True}
        )
        
        # 結果保存
        data_access.save_script_generation_result(test_project_with_theme, output)
        
        # 保存確認
        dao = ScriptGenerationDAO(project_repository.db_manager)
        saved_result = dao.get_script_result(test_project_with_theme)
        assert saved_result["status"] == "completed"
        
        print("✅ DatabaseDataAccessテスト成功")
    
    def test_script_generator_integration(
        self, 
        project_repository, 
        config_manager, 
        llm_client, 
        test_project_with_theme
    ):
        """ScriptGeneratorの統合テスト"""
        
        # データアクセス層とLLM層の準備
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiScriptLLM(llm_client)
        
        # スクリプトジェネレーター初期化
        script_generator = ScriptGenerator(
            data_access=data_access,
            llm_interface=llm_interface
        )
        
        # 入力データ準備
        input_data = ScriptGenerationInput(
            project_id=test_project_with_theme,
            llm_config={"model": "gemini-2.0-flash-exp", "temperature": 0.8}
        )
        
        # スクリプト生成実行
        output = script_generator.generate_script(input_data)
        
        # 結果検証
        assert isinstance(output, ScriptGenerationOutput), "出力型が正しくありません"
        assert output.generated_script, "生成されたスクリプトが空です"
        assert len(output.generated_script.segments) > 0, "セグメント数が0です"
        assert output.generated_script.total_estimated_duration > 0, "推定時間が0以下です"
        
        # データベース保存確認
        dao = ScriptGenerationDAO(project_repository.db_manager)
        saved_result = dao.get_script_result(test_project_with_theme)
        assert saved_result["status"] == "completed", "ワークフローステップが完了していません"
        
        # プロジェクトの推定時間更新確認
        project = project_repository.get_project(test_project_with_theme)
        # estimated_durationフィールドが更新されているかチェック（実装に依存）
        
        print(f"✅ ScriptGenerator統合テスト成功")
        print(f"  生成セグメント数: {len(output.generated_script.segments)}")
        print(f"  総推定時間: {output.generated_script.total_estimated_duration:.1f}秒")
        print(f"  総文字数: {output.generated_script.total_character_count}文字")
        
        # サンプルセグメント表示
        for i, segment in enumerate(output.generated_script.segments[:2], 1):
            print(f"  サンプル{i}: {segment.speaker} - {segment.text[:30]}...")


if __name__ == "__main__":
    # 単体テストの個別実行
    pytest.main([__file__, "-v", "-s"]) 