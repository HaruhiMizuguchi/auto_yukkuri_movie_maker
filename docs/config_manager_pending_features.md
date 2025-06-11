# ConfigManager 未実装機能リスト

## 概要

設定管理システム（ConfigManager）のコア機能は完成していますが、以下の拡張機能が未実装です。
これらは運用面での利便性を向上させる機能で、必要に応じて段階的に実装可能です。

## 未実装テストケース一覧（8件）

### 🔄 1. 設定継承機能 (`test_config_inheritance`)
**目的**: 基本設定とプロファイル設定の階層的マージ  
**機能詳細**:
- `merge_configs(base_config, profile_config)` メソッド
- 基本設定はそのまま残し、プロファイル設定で上書き
- 深い階層でのマージサポート

**実装必要度**: ⭐⭐⭐ (中) - プロファイル機能拡張時に有用  
**推定工数**: 2-3時間

```python
# 期待される動作例
base_config = {"app": {"name": "test_app", "debug": False}}
profile_config = {"app": {"debug": True}}
merged = config_manager.merge_configs(base_config, profile_config)
# 結果: {"app": {"name": "test_app", "debug": True}}
```

---

### ⚡ 2. 設定キャッシュ機能 (`test_config_caching`)
**目的**: ファイル読み込みパフォーマンスの向上  
**機能詳細**:
- `load_config(filename, use_cache=True)` パラメータ
- ファイル更新時刻監視
- メモリ使用量制限

**実装必要度**: ⭐⭐ (低) - 大規模運用時のパフォーマンス最適化  
**推定工数**: 3-4時間

```python
# 期待される動作例
config1 = config_manager.load_config("app_config.yaml", use_cache=True)
config2 = config_manager.load_config("app_config.yaml", use_cache=True)
# config1 と config2 は同じオブジェクト（キャッシュ利用）
```

---

### 🔥 3. ホットリロード機能 (`test_hot_reload_functionality`)
**目的**: アプリケーション再起動なしでの設定変更反映  
**機能詳細**:
- `reload_config(filename)` メソッド
- ファイル監視機能（optional）
- 設定変更コールバック

**実装必要度**: ⭐⭐ (低) - 開発効率向上  
**推定工数**: 4-5時間

```python
# 期待される動作例
config = config_manager.load_config("app_config.yaml")
# ファイルを外部で変更
reloaded_config = config_manager.reload_config("app_config.yaml")
# 変更が反映されている
```

---

### ❌ 4. ファイルが存在しない場合のエラーハンドリング (`test_error_handling_file_not_found`)
**目的**: 適切なエラーメッセージとログ出力  
**機能詳細**:
- `ConfigError` 例外の詳細メッセージ
- ファイルパス情報を含むエラー
- ログレベル適切化

**実装必要度**: ⭐⭐⭐⭐ (高) - ユーザビリティ向上  
**推定工数**: 1-2時間

```python
# 期待される動作例
with self.assertRaises(ConfigError) as context:
    config_manager.load_config("nonexistent_config.yaml")
self.assertIn("not found", str(context.exception))
```

---

### ❌ 5. 不正なYAMLファイルのエラーハンドリング (`test_error_handling_invalid_yaml`)
**目的**: YAML構文エラーの分かりやすいエラーメッセージ  
**機能詳細**:
- YAML構文エラーの詳細位置情報
- 修正案の提示
- ログ出力

**実装必要度**: ⭐⭐⭐⭐ (高) - ユーザビリティ向上  
**推定工数**: 1-2時間

```python
# 期待される動作例
# 不正なYAML: "invalid: yaml: content: ["
with self.assertRaises(ConfigError) as context:
    config_manager.load_config("invalid.yaml")
self.assertIn("parsing", str(context.exception).lower())
```

---

### ❌ 6. 不正なJSONファイルのエラーハンドリング (`test_error_handling_invalid_json`)
**目的**: JSON構文エラーの分かりやすいエラーメッセージ  
**機能詳細**:
- JSON構文エラーの詳細位置情報
- 修正案の提示
- ログ出力

**実装必要度**: ⭐⭐⭐⭐ (高) - ユーザビリティ向上  
**推定工数**: 1-2時間

```python
# 期待される動作例
# 不正なJSON: '{"invalid": json, "content"}'
with self.assertRaises(ConfigError) as context:
    config_manager.load_config("invalid.json")
self.assertIn("json", str(context.exception).lower())
```

---

### 🔍 7. パス指定での設定値取得 (`test_get_config_value_by_path`)
**目的**: ドット記法での設定値アクセス  
**機能詳細**:
- `get_value("app.database.host", config)` 形式
- デフォルト値サポート
- 配列インデックス対応

**実装必要度**: ⭐⭐⭐ (中) - 利便性向上  
**推定工数**: 2-3時間

```python
# 期待される動作例
config = config_manager.load_config("app_config.yaml")
app_name = config_manager.get_value("app.name", config)
db_host = config_manager.get_value("database.host", config, default="localhost")
```

---

### 🔗 8. 設定値内部参照機能 (`test_config_interpolation`)
**目的**: 設定値内で他の設定値を参照  
**機能詳細**:
- `${section.key}` 形式での内部参照
- 循環参照の検出・エラー
- ネストした参照のサポート

**実装必要度**: ⭐⭐ (低) - 設定の柔軟性向上  
**推定工数**: 4-5時間

```python
# 期待される動作例
config = {
    "base": {"url": "http://localhost", "port": 8080},
    "api": {"endpoint": "${base.url}:${base.port}/api"}
}
# 結果: api.endpoint = "http://localhost:8080/api"
```

---

## 実装優先度別推奨順序

### 🚨 優先度高（ユーザビリティ改善）
1. **エラーハンドリング** (4, 5, 6) - 約4-6時間
   - ファイル未存在エラー
   - YAML/JSON構文エラー

### 🔧 優先度中（機能拡張）
2. **設定継承機能** (1) - 約2-3時間
3. **パス指定取得** (7) - 約2-3時間

### ⚡ 優先度低（パフォーマンス・利便性）
4. **キャッシュ機能** (2) - 約3-4時間
5. **ホットリロード** (3) - 約4-5時間
6. **内部参照機能** (8) - 約4-5時間

---

## 現在の実装状況

✅ **完成済みコア機能**:
- YAML/JSON読み込み
- 環境変数展開（デフォルト値サポート）
- インクルード機能
- JSONスキーマバリデーション
- 型変換（string→boolean, integer等）
- プロファイル切り替え（development/production）
- デフォルト値管理・設定マージ

✅ **テスト状況**: 11/19 テスト PASS
- ✅ 成功: 11テスト（コア機能）
- ⏸️ スキップ: 8テスト（拡張機能）

---

## 実装時の注意点

1. **エラーハンドリング**は1-3ログシステム完成後に実装すると効率的
2. **キャッシュ機能**は1-4ファイルシステム管理と連携すると良い
3. **ホットリロード**は実際のアプリケーション利用時に需要が明確になってから実装
4. 全機能の実装は任意（コア機能は完成済み）

---

**作成日**: 2025年6月11日  
**更新日**: 2025年6月11日  
**関連ファイル**: 
- `src/core/config_manager.py`
- `tests/unit/test_config_manager.py` 