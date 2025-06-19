# データベース使用ガイド

## 📋 概要

このドキュメントでは、ゆっくり動画自動生成ツールのデータベースの使用方法について詳しく説明します。

## 🔑 重要なポイント

### データベースの初期化タイミング

**✅ 推奨：開発時またはシステム初回起動時に1回だけ初期化**

データベースは以下のタイミングで初期化します：

1. **開発環境セットアップ時**（推奨）
2. **本番環境初回デプロイ時**
3. **データベースファイルが存在しない場合の自動初期化**

### プロジェクトごとの処理

**各動画作成プロジェクトでは初期化は不要です。**

- ✅ 既存のデータベースに新しいプロジェクトレコードを追加
- ✅ 最初から保存・読み取りが可能
- ❌ プロジェクトごとの初期化処理は不要

## 🚀 データベース初期化方法

### 方法1: 開発時の手動初期化（推奨）

```python
#!/usr/bin/env python3
"""
データベース初期化スクリプト
開発時または初回セットアップ時に実行
"""

from src.core.database_manager import DatabaseManager

def initialize_database():
    """データベースを初期化"""
    # データベースファイルパス
    db_path = "data/yukkuri_system.db"
    
    print("=== データベース初期化開始 ===")
    
    # DatabaseManager初期化
    db_manager = DatabaseManager(db_path)
    
    try:
        # データベース初期化（テーブル作成など）
        db_manager.initialize()
        
        print(f"✅ データベース初期化完了: {db_path}")
        print(f"📁 データベースサイズ: {os.path.getsize(db_path)} bytes")
        
        # 作成されたテーブル確認
        tables = db_manager.get_table_names()
        print(f"📋 作成されたテーブル: {len(tables)}個")
        for table in tables:
            print(f"   - {table}")
        
        # ヘルスチェック
        health = db_manager.health_check()
        print(f"🏥 データベース状態: {health['status']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 初期化エラー: {e}")
        return False
        
    finally:
        db_manager.close_connection()

if __name__ == "__main__":
    success = initialize_database()
    if success:
        print("\n🎉 データベース初期化が正常に完了しました！")
        print("これで動画作成プロジェクトを開始できます。")
    else:
        print("\n💥 データベース初期化に失敗しました。")
```

### 方法2: 自動初期化（プロダクション向け）

```python
from src.core.database_manager import DatabaseManager
import os

def ensure_database_ready(db_path: str = "data/yukkuri_system.db") -> DatabaseManager:
    """
    データベースが使用可能な状態であることを保証
    存在しない場合は自動初期化
    """
    # データベースファイルが存在しない場合は初期化
    if not os.path.exists(db_path):
        print(f"📄 データベースファイルが見つかりません: {db_path}")
        print("🔧 自動初期化を実行します...")
        
        db_manager = DatabaseManager(db_path)
        db_manager.initialize()
        
        print("✅ データベース自動初期化完了")
    else:
        print(f"✅ 既存データベースを使用: {db_path}")
    
    # DatabaseManagerインスタンスを返す
    return DatabaseManager(db_path)

# 使用例
db_manager = ensure_database_ready()
```

## 🎬 動画作成プロジェクトでの使用方法

### 基本的な使用パターン

```python
from src.core.database_manager import DatabaseManager
from src.core.project_repository import ProjectRepository

def create_video_project():
    """動画プロジェクト作成の標準的な流れ"""
    
    # 1. 既存データベースに接続（初期化不要）
    db_manager = DatabaseManager("data/yukkuri_system.db")
    project_repo = ProjectRepository(db_manager)
    
    # 2. 新しいプロジェクトを作成
    project_id = "video-project-001"
    success = project_repo.create_project(
        project_id=project_id,
        theme="Pythonプログラミング入門",
        target_length_minutes=5.0,
        config={
            "voice_settings": {"reimu_speed": 1.0},
            "video_quality": "1080p"
        }
    )
    
    if success:
        print(f"✅ プロジェクト作成成功: {project_id}")
        
        # 3. プロジェクト情報の読み取り
        project = project_repo.get_project(project_id)
        print(f"📝 テーマ: {project['theme']}")
        print(f"⏱️ 目標時間: {project['target_length_minutes']}分")
        
        # 4. ワークフローステップの管理
        project_repo.create_workflow_step(
            project_id=project_id,
            step_number=1,
            step_name="script_generation",
            status="pending"
        )
        
        # 5. ファイル参照の登録
        file_id = project_repo.register_file_reference(
            project_id=project_id,
            file_type="script",
            file_category="output",
            file_path="files/scripts/main_script.txt",
            file_name="main_script.txt",
            file_size=1024
        )
        
        print(f"📁 ファイル登録完了: ID {file_id}")
        
    else:
        print("❌ プロジェクト作成失敗")
    
    # 6. 接続クローズ
    db_manager.close_connection()

# 実行
create_video_project()
```

### 複数プロジェクトの並行処理

```python
def process_multiple_projects():
    """複数プロジェクトの並行処理例"""
    
    # 共有データベース接続
    db_manager = DatabaseManager("data/yukkuri_system.db")
    project_repo = ProjectRepository(db_manager)
    
    # 複数プロジェクトを作成
    project_themes = [
        "Python基礎：変数と型",
        "Python基礎：制御構文", 
        "Python基礎：関数の定義"
    ]
    
    created_projects = []
    
    for i, theme in enumerate(project_themes):
        project_id = f"python-basics-{i+1:03d}"
        
        success = project_repo.create_project(
            project_id=project_id,
            theme=theme,
            target_length_minutes=3.0
        )
        
        if success:
            created_projects.append(project_id)
            print(f"✅ プロジェクト作成: {project_id}")
        else:
            print(f"❌ プロジェクト作成失敗: {project_id}")
    
    print(f"📊 作成されたプロジェクト数: {len(created_projects)}")
    
    # 接続クローズ
    db_manager.close_connection()
    
    return created_projects

# 実行
project_ids = process_multiple_projects()
```

## 🔄 データベースのライフサイクル

### 1. システム起動時

```python
def system_startup():
    """システム起動時の処理"""
    
    # データベース存在確認
    db_path = "data/yukkuri_system.db"
    
    if not os.path.exists(db_path):
        print("🔧 初回起動: データベースを初期化します")
        db_manager = DatabaseManager(db_path)
        db_manager.initialize()
        db_manager.close_connection()
    else:
        print("✅ 既存データベースを使用します")
    
    # ヘルスチェック
    db_manager = DatabaseManager(db_path)
    health = db_manager.health_check()
    
    if health['status'] == 'healthy':
        print("🏥 データベース正常")
    else:
        print(f"⚠️ データベース異常: {health}")
    
    db_manager.close_connection()
```

### 2. プロジェクト実行中

```python
def during_project_execution(project_id: str):
    """プロジェクト実行中のデータベース操作"""
    
    db_manager = DatabaseManager("data/yukkuri_system.db")
    project_repo = ProjectRepository(db_manager)
    
    try:
        # プロジェクト状態更新
        project_repo.update_project(project_id, status="processing")
        
        # ワークフローステップ更新
        project_repo.update_workflow_step_status(
            project_id=project_id,
            step_name="script_generation",
            status="running"
        )
        
        # 処理結果保存
        project_repo.save_step_result(
            project_id=project_id,
            step_name="script_generation",
            output_data={"script_length": 1500, "estimated_duration": 4.5}
        )
        
        # プロジェクト完了
        project_repo.update_project(project_id, status="completed")
        
    except Exception as e:
        print(f"❌ データベース操作エラー: {e}")
        project_repo.update_project(project_id, status="failed")
    
    finally:
        db_manager.close_connection()
```

### 3. システム終了時

```python
def system_shutdown():
    """システム終了時の処理"""
    
    db_manager = DatabaseManager("data/yukkuri_system.db")
    
    try:
        # 一時ファイルクリーンアップ
        db_manager.cleanup_temporary_files()
        
        # バックアップ作成（オプション）
        backup_path = f"backups/yukkuri_system_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        db_manager.create_backup(backup_path)
        
        print("🧹 システム終了処理完了")
        
    except Exception as e:
        print(f"⚠️ 終了処理エラー: {e}")
    
    finally:
        db_manager.close_connection()
```

## 📊 データベース管理操作

### バックアップ・復元

```python
def backup_restore_operations():
    """バックアップ・復元操作"""
    
    db_manager = DatabaseManager("data/yukkuri_system.db")
    
    # バックアップ作成
    backup_path = "backups/manual_backup.db"
    db_manager.create_backup(backup_path)
    print(f"💾 バックアップ作成: {backup_path}")
    
    # 復元（必要時）
    # db_manager.restore_from_backup(backup_path)
    # print(f"🔄 データベース復元完了")
    
    db_manager.close_connection()
```

### ヘルスチェック・メンテナンス

```python
def database_maintenance():
    """データベースメンテナンス"""
    
    db_manager = DatabaseManager("data/yukkuri_system.db")
    
    # ヘルスチェック
    health = db_manager.health_check()
    print(f"🏥 データベース状態: {health}")
    
    # スキーマ検証
    schema_valid = db_manager.validate_schema()
    print(f"📋 スキーマ検証: {'✅ 正常' if schema_valid else '❌ 異常'}")
    
    # テーブル情報
    tables = db_manager.get_table_names()
    print(f"📊 テーブル数: {len(tables)}")
    
    for table in tables:
        schema = db_manager.get_table_schema(table)
        print(f"   {table}: {len(schema)}カラム")
    
    db_manager.close_connection()
```

## ⚠️ 注意事項・ベストプラクティス

### 1. 接続管理

```python
# ✅ 推奨：明示的な接続クローズ
db_manager = DatabaseManager("data/yukkuri_system.db")
try:
    # データベース操作
    pass
finally:
    db_manager.close_connection()

# ✅ 推奨：コンテキストマネージャー使用
with DatabaseManager("data/yukkuri_system.db") as db_manager:
    # データベース操作
    pass
```

### 2. エラーハンドリング

```python
def robust_database_operation():
    """堅牢なデータベース操作"""
    
    try:
        db_manager = DatabaseManager("data/yukkuri_system.db")
        project_repo = ProjectRepository(db_manager)
        
        # データベース操作
        result = project_repo.create_project("test", "テストプロジェクト")
        
        if result:
            print("✅ 操作成功")
        else:
            print("⚠️ 操作失敗（例外なし）")
            
    except FileNotFoundError:
        print("❌ データベースファイルが見つかりません")
    except PermissionError:
        print("❌ データベースファイルへのアクセス権限がありません")
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
    finally:
        if 'db_manager' in locals():
            db_manager.close_connection()
```

### 3. パフォーマンス最適化

```python
def optimized_batch_operations():
    """最適化されたバッチ操作"""
    
    db_manager = DatabaseManager("data/yukkuri_system.db")
    project_repo = ProjectRepository(db_manager)
    
    # トランザクションを使用したバッチ処理
    with db_manager.transaction() as conn:
        for i in range(100):
            conn.execute(
                "INSERT INTO projects (id, theme, status) VALUES (?, ?, ?)",
                (f"batch-{i:03d}", f"バッチテーマ{i}", "created")
            )
    
    print("✅ バッチ処理完了")
    db_manager.close_connection()
```

## 🛠️ トラブルシューティング

### よくある問題と解決方法

#### 1. データベースファイルが見つからない

```python
import os
from pathlib import Path

db_path = "data/yukkuri_system.db"

# ディレクトリ作成
Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# 初期化
if not os.path.exists(db_path):
    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    db_manager.close_connection()
```

#### 2. ファイルロックエラー（Windows）

```python
import time

def safe_database_operation():
    """安全なデータベース操作"""
    
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            db_manager = DatabaseManager("data/yukkuri_system.db")
            # データベース操作
            db_manager.close_connection()
            break
            
        except PermissionError as e:
            if attempt < max_retries - 1:
                print(f"⚠️ ファイルロックエラー、リトライ中... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数バックオフ
            else:
                print(f"❌ ファイルロックエラー、最大リトライ回数に到達: {e}")
                raise
```

#### 3. スキーマバージョン不一致

```python
def check_and_migrate_schema():
    """スキーマバージョン確認・マイグレーション"""
    
    db_manager = DatabaseManager("data/yukkuri_system.db")
    
    # 現在のマイグレーションバージョン確認
    current_version = db_manager.get_migration_version()
    print(f"📊 現在のスキーマバージョン: {current_version}")
    
    # スキーマ検証
    if not db_manager.validate_schema():
        print("⚠️ スキーマ検証失敗、再初期化が必要な可能性があります")
        
        # バックアップ作成後、再初期化
        backup_path = f"backups/pre_migration_{current_version}.db"
        db_manager.create_backup(backup_path)
        print(f"💾 バックアップ作成: {backup_path}")
        
        # 必要に応じて再初期化
        # db_manager.initialize()
    
    db_manager.close_connection()
```

## 📚 関連ドキュメント

- **[database_design.md](database_design.md)** - データベース設計の詳細
- **[functions/project_manager.md](functions/project_manager.md)** - プロジェクト管理機能
- **[development_troubleshooting.md](development_troubleshooting.md)** - 開発時のトラブルシューティング

---

## 🎯 まとめ

### データベース使用の基本原則

1. **初期化は1回だけ**：開発時またはシステム初回起動時
2. **プロジェクトごとに初期化不要**：既存DBに新レコード追加
3. **適切な接続管理**：使用後は必ずクローズ
4. **エラーハンドリング**：堅牢な例外処理を実装
5. **定期バックアップ**：重要なデータの保護

この方式により、効率的で安全なデータベース運用が可能になります。 