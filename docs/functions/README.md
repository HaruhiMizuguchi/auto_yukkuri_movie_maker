# 機能ドキュメント (Functions Documentation)

## 概要

このディレクトリには、ゆっくり動画自動生成ツールの各機能の詳細なドキュメントが含まれています。フェーズ1〜3で実装された機能の使用方法、サンプルコード、トラブルシューティングなどを提供します。

## ドキュメント一覧

### 📋 機能概要
- **[functions_summary.md](../functions_summary.md)** - 全機能の概要と連携例

### 🎯 コア機能
- **[project_manager.md](project_manager.md)** - プロジェクト管理機能
- **[workflow_engine.md](workflow_engine.md)** - ワークフローエンジン

### 🔧 処理モジュール
- **[theme_selector.md](theme_selector.md)** - テーマ選定機能

### 🌐 API クライアント
- **[tts_client.md](tts_client.md)** - TTS音声生成クライアント

### 🛠️ ユーティリティ
- **[text_generation.md](text_generation.md)** - 高レベルテキスト生成

## 使用方法

### 1. 基本的な読み方

各ドキュメントは以下の構成になっています：

- **概要** - 機能の説明
- **基本的な使用方法** - 初期化と基本操作
- **データクラス** - 使用するデータ構造
- **実際の使用例** - 実践的なサンプルコード
- **エラーハンドリング** - 例外処理とトラブルシューティング
- **パフォーマンス最適化** - 効率的な使用方法

### 2. サンプルコードの実行

ドキュメント内のサンプルコードは、以下の前提で書かれています：

```python
# 必要なインポート
import asyncio
from src.core import ProjectManager, DatabaseManager
from src.modules import ThemeSelector
from src.api import AivisSpeechClient
from src.utils.text_generation import generate_text

# 環境設定（.envファイルに設定）
# GOOGLE_API_KEY=your_gemini_api_key
# DATABASE_PATH=data/yukkuri_tool.db
```

### 3. 段階的な学習

推奨する学習順序：

1. **[functions_summary.md](../functions_summary.md)** - 全体像を把握
2. **[text_generation.md](text_generation.md)** - 高レベルAPIから始める
3. **[project_manager.md](project_manager.md)** - プロジェクト管理を理解
4. **[theme_selector.md](theme_selector.md)** - 具体的な処理を学習
5. **[tts_client.md](tts_client.md)** - 音声生成の実装
6. **[workflow_engine.md](workflow_engine.md)** - 高度なワークフロー管理

## クイックスタート

### 最も簡単な使用例

```python
import asyncio
from src.utils.text_generation import generate_text

async def quick_start():
    # 簡単なテキスト生成
    text = await generate_text("Pythonについて説明して")
    print(text)

# 実行
asyncio.run(quick_start())
```

### プロジェクト管理の基本

```python
from src.core import ProjectManager, DatabaseManager

# プロジェクト作成
db_manager = DatabaseManager("data/yukkuri_tool.db") 
project_manager = ProjectManager(db_manager, "projects")

project_id = project_manager.create_project(
    theme="Python入門",
    target_length_minutes=5
)
print(f"プロジェクト作成: {project_id}")
```

### 音声生成の基本

```python
import asyncio
from src.api import AivisSpeechClient, TTSRequest

async def basic_tts():
    async with AivisSpeechClient() as client:
        request = TTSRequest(
            text="こんにちは！",
            speaker_id=0
        )
        response = await client.generate_audio(request)
        response.save_audio("hello.wav")

asyncio.run(basic_tts())
```

## トラブルシューティング

### よくある問題

#### 1. インポートエラー
```python
# ❌ 間違い
from theme_selector import ThemeSelector

# ✅ 正しい
from src.modules import ThemeSelector
```

#### 2. 非同期関数の実行
```python
# ❌ 間違い（awaitが不要）
text = generate_text("テキスト")

# ✅ 正しい
text = await generate_text("テキスト")
# または
text = asyncio.run(generate_text("テキスト"))
```

#### 3. API キーエラー
```bash
# .envファイルを作成
echo "GOOGLE_API_KEY=your_actual_api_key" > .env
```

### デバッグのヒント

#### ログの有効化
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### エラーの詳細確認
```python
try:
    result = await some_function()
except Exception as e:
    print(f"エラー詳細: {e}")
    import traceback
    traceback.print_exc()
```

## パフォーマンスのヒント

### 1. 並列処理の活用
```python
# 複数のタスクを並列実行
tasks = [generate_text(f"テーマ{i}") for i in range(5)]
results = await asyncio.gather(*tasks)
```

### 2. キャッシュの使用
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_operation(param):
    # 重い処理
    return result
```

### 3. リソース管理
```python
# コンテキストマネージャーを使用
async with AivisSpeechClient() as client:
    # クライアントは自動的にクリーンアップされる
    pass
```

## 拡張とカスタマイズ

### カスタムプロセッサの実装

```python
from src.core.workflow_step import StepProcessor

class CustomProcessor(StepProcessor):
    async def execute(self, context, input_data):
        # カスタム処理
        return StepResult.success("custom_step", {"result": "ok"})
```

### 設定のカスタマイズ

```python
# カスタム設定でクライアント初期化
custom_config = {
    "temperature": 0.8,
    "max_tokens": 1024
}

result = await generate_text("プロンプト", **custom_config)
```

## 貢献とフィードバック

### ドキュメントの改善

- 不明な点や間違いを見つけた場合は報告してください
- 使用例の追加提案も歓迎します
- パフォーマンス改善のアイデアもお寄せください

### コード例の投稿

実際に動作するサンプルコードの投稿を歓迎します：

```python
# examples/custom_workflow.py
async def my_custom_workflow():
    """カスタムワークフローの例"""
    # 実装内容
    pass
```

## 関連リソース

- **[API リファレンス](../api_reference.md)** - 詳細なAPI仕様
- **[アーキテクチャガイド](../architecture.md)** - システム設計の説明  
- **[開発ガイド](../development.md)** - 開発環境の構築
- **[フロー定義](../flow_definition.yaml)** - ワークフロー仕様

## 更新履歴

- **2024-12-21**: 初版作成
  - プロジェクト管理機能のドキュメント追加
  - テーマ選定機能のドキュメント追加
  - TTS音声生成機能のドキュメント追加
  - ワークフローエンジンのドキュメント追加
  - 高レベルテキスト生成機能のドキュメント追加

今後のアップデートでは、フェーズ4以降の新機能ドキュメントが追加される予定です。 