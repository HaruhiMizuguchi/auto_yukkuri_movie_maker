#!/usr/bin/env python3
"""
テーマ選定モジュールの実際のAPI統合テスト

実際のGemini APIを使用してテーマ生成が動作することを確認します。
このスクリプトは手動で実行し、LLMとの連携を検証します。
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.modules.theme_selector import (
    ThemeSelector,
    DatabaseDataAccess,
    GeminiThemeLLM,
    UserPreferences,
    ThemeSelectionInput
)
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient


def test_real_api_integration():
    """実際のAPI統合テスト"""
    print("🚀 テーマ選定モジュール実API統合テスト開始")
    
    # 環境変数確認
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY環境変数が設定されていません")
        print("   .envファイルでAPIキーを設定してください")
        return False
    
    print("✅ GEMINI_API_KEY環境変数設定済み")
    
    # 一時データベースで統合テスト
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        print(f"📦 一時データベース作成: {db_path}")
        
        # コンポーネント初期化
        db_manager = DatabaseManager(db_path)
        db_manager.initialize()
        print("✅ データベース初期化完了")
        
        repository = ProjectRepository(db_manager)
        
        # ConfigManager初期化
        config_data = {
            "llm": {
                "model": "gemini-2.0-flash-preview", 
                "temperature": 0.8,
                "max_tokens": 2000
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as config_file:
            import yaml
            yaml.dump(config_data, config_file)
            config_path = config_file.name
        
        config_manager = ConfigManager(config_path)
        print("✅ 設定管理初期化完了")
        
        # テーマ選定コンポーネント初期化
        data_access = DatabaseDataAccess(repository, config_manager)
        llm_client = GeminiLLMClient()
        llm_interface = GeminiThemeLLM(llm_client)
        theme_selector = ThemeSelector(data_access, llm_interface)
        print("✅ テーマ選定コンポーネント初期化完了")
        
        # テストプロジェクト作成
        project_id = repository.create_project(
            project_id="test-integration-001",
            theme="初期テーマ"  # これは上書きされる
        )
        print(f"✅ テストプロジェクト作成: {project_id}")
        
        # ユーザー設定セットアップ
        user_config = {
            "user_preferences": {
                "genre_history": ["科学", "技術", "歴史"],
                "preferred_genres": ["教育", "エンターテインメント"],
                "excluded_genres": ["政治", "宗教"],
                "target_audience": "一般",
                "content_style": "分かりやすく親しみやすい"
            }
        }
        repository.update_project(project_id=project_id, config=user_config)
        print("✅ ユーザー設定完了")
        
        # 入力データ準備
        preferences = data_access.get_user_preferences(project_id)
        input_data = ThemeSelectionInput(
            project_id=project_id,
            user_preferences=preferences,
            llm_config=config_manager.get_value("llm"),
            max_candidates=3  # 少数に限定してテスト
        )
        print("✅ 入力データ準備完了")
        
        # ディレクトリ作成
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                print("🎯 テーマ選定実行中...")
                
                # 実際のテーマ選定実行
                result = theme_selector.select_theme(input_data)
                
                print(f"🎉 テーマ選定完了!")
                print(f"📌 選定テーマ: {result.selected_theme.theme}")
                print(f"📂 カテゴリ: {result.selected_theme.category}")
                print(f"⏱️  目標時間: {result.selected_theme.target_length_minutes}分")
                print(f"📝 説明: {result.selected_theme.description}")
                print(f"💭 選定理由: {result.selected_theme.selection_reason}")
                print(f"🎪 候補総数: {len(result.candidates)}件")
                
                # 候補一覧表示
                print("\n📋 生成された候補一覧:")
                for i, candidate in enumerate(result.candidates, 1):
                    print(f"  {i}. {candidate.theme}")
                    print(f"     カテゴリ: {candidate.category}")
                    print(f"     時間: {candidate.target_length_minutes}分")
                    print(f"     スコア: {candidate.total_score:.1f}")
                    print(f"     説明: {candidate.description[:60]}...")
                    print()
                
                # データベース保存確認
                saved_project = repository.get_project(project_id)
                print(f"💾 データベース保存確認:")
                print(f"   テーマ: {saved_project['theme']}")
                print(f"   時間: {saved_project['target_length_minutes']}分")
                
                # ワークフローステップ確認
                step_result = repository.get_workflow_step(project_id, "theme_selection")
                if step_result:
                    print(f"   ステップ状態: {step_result['status']}")
                
                print("🎊 統合テスト成功!")
                return True
                
            finally:
                os.chdir(original_cwd)
        
        # クリーンアップ
        os.unlink(config_path)
    
    except Exception as e:
        print(f"❌ 統合テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_llm_only():
    """LLMのみの簡易テスト"""
    print("\n🧪 LLM単体テスト")
    
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY環境変数が設定されていません")
        return False
    
    try:
        # LLMクライアント直接テスト
        llm_client = GeminiLLMClient()
        gemini_llm = GeminiThemeLLM(llm_client)
        
        # テスト用ユーザー設定
        preferences = UserPreferences(
            genre_history=["科学"],
            preferred_genres=["教育", "エンターテインメント"],
            excluded_genres=["政治"],
            target_audience="一般",
            content_style="親しみやすい"
        )
        
        print("📡 Gemini APIテーマ生成中...")
        candidates = gemini_llm.generate_theme_candidates(preferences, 2)
        
        print(f"✅ テーマ生成成功: {len(candidates)}件")
        for i, candidate in enumerate(candidates, 1):
            print(f"  {i}. {candidate.theme} ({candidate.category})")
            print(f"     {candidate.description[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM単体テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🎬 ゆっくり動画自動生成ツール - テーマ選定API統合テスト")
    print("=" * 60)
    
    # LLM単体テストから開始
    llm_success = test_llm_only()
    
    if llm_success:
        print("\n" + "=" * 40)
        # 全統合テスト実行
        integration_success = test_real_api_integration()
        
        if integration_success:
            print("\n🎊 全テスト成功! テーマ選定モジュールは正常に動作しています。")
        else:
            print("\n❌ 統合テスト失敗")
            sys.exit(1)
    else:
        print("\n❌ LLM単体テスト失敗")
        sys.exit(1) 