#!/usr/bin/env python3
"""
データベース初期化スクリプト
開発時または初回セットアップ時に実行
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager


def initialize_database(db_path: str = "data/yukkuri_system.db") -> bool:
    """データベースを初期化"""
    
    print("=== データベース初期化開始 ===")
    
    # データベースディレクトリ作成
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 データベースディレクトリ確認: {db_dir}")
    
    # 既存ファイルの確認
    if os.path.exists(db_path):
        print(f"⚠️ 既存のデータベースファイルが見つかりました: {db_path}")
        response = input("既存のデータベースを上書きしますか？ (y/N): ")
        if response.lower() != 'y':
            print("❌ 初期化をキャンセルしました")
            return False
        
        # バックアップ作成
        backup_path = f"{db_path}.backup"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(db_path, backup_path)
        print(f"💾 既存データベースをバックアップ: {backup_path}")
    
    # DatabaseManager初期化
    try:
        db_manager = DatabaseManager(db_path)
        
        # データベース初期化（テーブル作成など）
        db_manager.initialize()
        
        print(f"✅ データベース初期化完了: {db_path}")
        print(f"📁 データベースサイズ: {os.path.getsize(db_path):,} bytes")
        
        # 作成されたテーブル確認
        tables = db_manager.get_table_names()
        print(f"📋 作成されたテーブル: {len(tables)}個")
        for table in tables:
            print(f"   - {table}")
        
        # ヘルスチェック
        health = db_manager.health_check()
        print(f"🏥 データベース状態: {health['status']}")
        print(f"📊 テーブル数: {health['table_count']}")
        print(f"💾 ファイルサイズ: {health['db_size_bytes']:,} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ 初期化エラー: {e}")
        return False
        
    finally:
        if 'db_manager' in locals():
            db_manager.close_connection()


def verify_database(db_path: str = "data/yukkuri_system.db") -> bool:
    """データベースの動作確認"""
    
    print("\n=== データベース動作確認 ===")
    
    try:
        db_manager = DatabaseManager(db_path)
        
        # 基本接続確認（テーブル名取得で接続確認）
        try:
            tables = db_manager.get_table_names()
            print("✅ データベース接続成功")
        except Exception as e:
            print(f"❌ データベース接続失敗: {e}")
            return False
        
        # スキーマ検証
        if db_manager.validate_schema():
            print("✅ スキーマ検証成功")
        else:
            print("⚠️ スキーマ検証失敗")
            return False
        
        # テストデータ作成・削除
        from src.core.project_repository import ProjectRepository
        
        project_repo = ProjectRepository(db_manager)
        
        # テストプロジェクト作成
        test_project_id = "test-init-verification"
        success = project_repo.create_project(
            project_id=test_project_id,
            theme="データベース初期化テスト",
            target_length_minutes=1.0
        )
        
        if not success:
            print("❌ テストプロジェクト作成失敗")
            return False
        
        print("✅ テストプロジェクト作成成功")
        
        # テストプロジェクト取得
        project = project_repo.get_project(test_project_id)
        if not project:
            print("❌ テストプロジェクト取得失敗")
            return False
        
        print("✅ テストプロジェクト取得成功")
        
        # テストプロジェクト削除
        if not project_repo.delete_project(test_project_id):
            print("❌ テストプロジェクト削除失敗")
            return False
        
        print("✅ テストプロジェクト削除成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 動作確認エラー: {e}")
        return False
        
    finally:
        if 'db_manager' in locals():
            db_manager.close_connection()


def main():
    """メイン処理"""
    
    print("🎬 ゆっくり動画自動生成ツール - データベース初期化")
    print("=" * 50)
    
    # コマンドライン引数の処理
    db_path = "data/yukkuri_system.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"📄 データベースパス: {db_path}")
    
    # 初期化実行
    if initialize_database(db_path):
        print("\n🎉 データベース初期化が正常に完了しました！")
        
        # 動作確認
        if verify_database(db_path):
            print("\n✅ データベース動作確認も正常に完了しました！")
            print("\n🚀 これで動画作成プロジェクトを開始できます。")
            print("\n📚 次のステップ:")
            print("   1. プロジェクト作成: ProjectManager.create_project()")
            print("   2. ワークフロー実行: WorkflowEngine.execute()")
            print("   3. 詳細は docs/database_usage_guide.md を参照")
        else:
            print("\n⚠️ データベース動作確認に問題があります。")
    else:
        print("\n💥 データベース初期化に失敗しました。")
        print("詳細なエラーログを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    main() 