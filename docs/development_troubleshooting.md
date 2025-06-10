# 開発トラブルシューティング

このドキュメントでは、ゆっくり動画自動生成ツールの開発過程で発生したエラーと解決方法をまとめています。

## 📅 作成日: 2025/06/10

---

## 🔧 Phase 1 - DatabaseManager実装時のトラブルシューティング

### 問題1: PowerShellでのファイル作成時のNull Byteエラー

**発生状況**:
- Windows PowerShellでファイル作成時に`null bytes`エラーが発生
- `edit_file`ツールで大きなファイルを作成しようとして失敗

**エラー内容**:
```
SyntaxError: source code string cannot contain null bytes
```

**解決方法**:
1. PowerShellの`New-Item`コマンドでファイルを作成
2. 小さなテンプレートから開始
3. `edit_file`ツールで段階的に実装を追加

**コマンド例**:
```powershell
New-Item -Path src/core/database_manager.py -ItemType File
```

---

### 問題2: テストファイルでのWindowsファイルロック問題

**発生状況**:
- pytest実行後、一時データベースファイルの削除時にファイルロックエラー
- SQLite接続が適切に閉じられていない

**エラー内容**:
```
PermissionError: [WinError 32] プロセスはファイルにアクセスできません。別のプロセスが使用中です。
```

**解決方法**:
1. テストフィクスチャで`db_manager.close_connection()`を明示的に呼び出し
2. `temp_db_path`フィクスチャでファイル削除時の例外処理を追加
3. ファイル削除前に短い待機時間を設ける

**修正コード**:
```python
@pytest.fixture
def db_manager(self, temp_db_path: str) -> DatabaseManager:
    manager = DatabaseManager(db_path=temp_db_path)
    yield manager
    # テスト後のクリーンアップ
    manager.close_connection()

@pytest.fixture
def temp_db_path(self) -> str:
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # クリーンアップ - Windowsでのファイルロック問題を回避
    try:
        if os.path.exists(path):
            # 少し待ってからファイル削除を試行
            import time
            time.sleep(0.1)
            os.unlink(path)
    except (PermissionError, OSError):
        # ファイルが使用中の場合は無視（テスト環境では問題なし）
        pass
```

---

### 問題3: 接続管理テストの設計不一致

**発生状況**:
- `get_connection()`メソッドがコンテキストマネージャーを返すのに、テストが直接オブジェクトを期待

**エラー内容**:
```
assert <contextlib._GeneratorContextManager object> is <contextlib._GeneratorContextManager object>
```

**解決方法**:
- テストをコンテキストマネージャーの使用方法に合わせて修正

**修正前**:
```python
conn1 = db_manager.get_connection()
conn2 = db_manager.get_connection()
assert conn1 is conn2
```

**修正後**:
```python
with db_manager.get_connection() as conn1:
    assert conn1 is not None
    with db_manager.get_connection() as conn2:
        assert conn1 is conn2
```

---

### 問題4: データベーススキーマの制約違反

**発生状況**:
- `projects`テーブルの`theme`フィールドがNOT NULL制約だが、テストで値を提供していない
- `project_files`テーブルで外部キー制約違反

**エラー内容**:
```
sqlite3.IntegrityError: NOT NULL constraint failed: projects.theme
sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

**解決方法**:
1. テストでNOT NULL制約のあるフィールドに適切な値を設定
2. 外部キー参照する前に親レコードを作成

**修正例**:
```python
# 修正前
conn.execute(
    "INSERT INTO projects (id, name, status) VALUES (?, ?, ?)",
    ("test_001", "Test Project", "planning")
)

# 修正後
conn.execute(
    "INSERT INTO projects (id, name, theme, status) VALUES (?, ?, ?, ?)",
    ("test_001", "Test Project", "test_theme", "planning")
)

# project_files挿入前にprojectを作成
with db_manager.transaction() as conn:
    conn.execute(
        "INSERT INTO projects (id, name, theme, status) VALUES (?, ?, ?, ?)",
        ("temp_test", "Temp Test Project", "test_theme", "planning")
    )
```

---

### 問題5: 例外処理の伝播問題

**発生状況**:
- トランザクションロールバックテストで、意図的な例外が`DatabaseError`でラップされて伝播

**エラー内容**:
```
src.core.database_manager.DatabaseError: Transaction failed: Test exception
```

**解決方法**:
- テストで複数の例外タイプをキャッチするように修正

**修正コード**:
```python
try:
    with db_manager.transaction() as conn:
        # ... データ挿入 ...
        raise ValueError("Test exception")
except (ValueError, DatabaseError):
    # ValueErrorまたはDatabaseErrorのどちらでも良い
    pass
```

---

## 🎯 学習ポイント

### 1. Windows環境での開発注意点
- ファイル作成時はエンコーディングを明示的に指定
- SQLite接続は必ず適切に閉じる
- ファイルロック問題を考慮した例外処理

### 2. TDD実装のベストプラクティス
- テストと実装の設計を一致させる
- データベース制約を考慮したテストデータ作成
- 段階的な実装でエラーを早期発見

### 3. SQLiteとPythonの連携
- 外部キー制約を有効にする（`PRAGMA foreign_keys = ON`）
- コンテキストマネージャーを使用したリソース管理
- 適切なトランザクション制御

### 4. エラーハンドリング設計
- カスタム例外の適切な使用
- 例外の伝播チェーンを考慮
- テストでの例外処理パターン

---

## 🔄 今後の参考

このトラブルシューティング情報は、今後の開発フェーズでも参考になる可能性があります：

- **Phase 2**: ワークフローエンジン実装時の状態管理
- **Phase 3**: 外部API連携時のエラーハンドリング
- **Phase 4**: ファイル処理時のリソース管理
- **Phase 5**: UI開発時のマルチプラットフォーム対応

---

**最終更新**: 2025/06/10  
**作成者**: Development Team  
**関連タスク**: Phase 1 - Task 1-4-1 (Database Management) 