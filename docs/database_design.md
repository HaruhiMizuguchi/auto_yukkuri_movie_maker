# データベース設計 - ゆっくり動画自動生成ツール

## 概要

このドキュメントでは、ゆっくり動画自動生成ツールのデータ管理方式について説明します。
従来の各工程毎のファイル管理から、**単一データベース + プロジェクト別ファイル管理**のハイブリッド方式に変更することで、データの整合性、管理性、スケーラビリティを向上させます。

## 設計方針

### 基本コンセプト
- **単一データベース**: 全プロジェクトの情報を一元管理
- **ファイル分離**: 大きなファイル（音声、動画、画像）はファイルシステムで管理
- **トランザクション制御**: SQLiteによる整合性保証
- **統計・分析**: 複数プロジェクト間での比較・分析が容易

### データ管理の分離
- **データベース管理**: メタデータ、進捗状況、設定、統計
- **ファイルシステム管理**: 実際のメディアファイル、ログ、キャッシュ

## ディレクトリ構造

```
auto_yukkuri_movie_maker/
├── data/
│   └── yukkuri_tool.db          # 【唯一のデータベース】
├── projects/                     # プロジェクトファイル群
│   ├── 20241215_001/            # プロジェクトID = 日付_連番
│   │   ├── files/
│   │   │   ├── audio/           # 音声ファイル
│   │   │   │   ├── segments/   # セグメント別音声
│   │   │   │   └── combined.wav # 結合音声
│   │   │   ├── video/           # 動画ファイル
│   │   │   │   ├── backgrounds/ # 背景動画
│   │   │   │   ├── characters/  # 立ち絵動画
│   │   │   │   └── final.mp4    # 最終動画
│   │   │   ├── images/          # 画像ファイル
│   │   │   │   ├── backgrounds/ # 背景画像
│   │   │   │   └── illustrations/ # 挿絵
│   │   │   ├── scripts/         # スクリプト関連
│   │   │   │   ├── script.json  # スクリプトデータ
│   │   │   │   └── script.txt   # プレーンテキスト
│   │   │   └── metadata/        # メタデータファイル
│   │   │       ├── audio_metadata.json
│   │   │       └── video_metadata.json
│   │   ├── logs/                # ログファイル
│   │   │   ├── processing.log
│   │   │   └── errors.log
│   │   └── cache/               # キャッシュファイル
│   │       └── api_cache.json
│   └── 20241215_002/            # 別のプロジェクト
├── config/                       # グローバル設定
├── assets/                       # 共通アセット
└── src/                          # ソースコード
```

## データベース設計

### ERD概要
```
projects (1) --- (n) workflow_steps
projects (1) --- (n) project_files
projects (1) --- (n) project_statistics
projects (0..1) --- (n) api_usage
```

### テーブル定義

#### 1. projects（プロジェクト管理）
```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,              -- プロジェクトID（例: 20241215_001）
    name TEXT NOT NULL,               -- プロジェクト名
    description TEXT,                 -- プロジェクト説明
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'initialized', -- initialized/processing/completed/failed
    config_json TEXT,                 -- プロジェクト固有設定
    estimated_duration INTEGER,       -- 予想処理時間(秒)
    actual_duration INTEGER,          -- 実際の処理時間(秒)
    theme TEXT,                       -- 動画テーマ
    target_length_minutes INTEGER,    -- 目標動画長(分)
    youtube_video_id TEXT,           -- アップロード後のYouTube動画ID
    youtube_url TEXT                 -- YouTube動画URL
);
```

#### 2. workflow_steps（ワークフロー実行状況）
```sql
CREATE TABLE workflow_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    step_name TEXT NOT NULL,          -- 'theme_selection', 'script_generation', etc.
    step_order INTEGER NOT NULL,      -- 実行順序
    status TEXT DEFAULT 'pending',    -- pending/running/completed/failed/skipped
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    input_params_json TEXT,           -- 入力パラメータ
    output_summary_json TEXT,         -- 出力サマリー（主要な結果データ）
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    processing_time_seconds INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

#### 3. project_files（ファイル管理）
```sql
CREATE TABLE project_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    step_name TEXT,                   -- どのステップで生成されたか
    file_type TEXT NOT NULL,          -- 'audio', 'video', 'image', 'script', 'metadata'
    file_category TEXT,               -- 'input', 'output', 'intermediate', 'final'
    file_path TEXT NOT NULL,          -- projects/{project_id}/files/... からの相対パス
    file_name TEXT NOT NULL,
    file_size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,               -- ファイル固有のメタデータ
    is_temporary BOOLEAN DEFAULT 0,   -- 一時ファイルかどうか
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

#### 4. project_statistics（プロジェクト統計）
```sql
CREATE TABLE project_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    stat_name TEXT NOT NULL,          -- 'api_calls', 'generation_time', 'file_size', etc.
    stat_value REAL NOT NULL,
    stat_unit TEXT,                   -- 'seconds', 'bytes', 'count', etc.
    step_name TEXT,                   -- どのステップの統計か
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

#### 5. api_usage（API使用履歴）
```sql
CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,                  -- NULLの場合はシステム全体の使用
    api_provider TEXT NOT NULL,       -- 'openai', 'google', 'aivis', etc.
    api_endpoint TEXT NOT NULL,       -- '/v1/chat/completions', '/synthesis', etc.
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    estimated_cost_usd REAL DEFAULT 0,
    response_time_ms INTEGER,
    status_code INTEGER,
    step_name TEXT,                   -- どのステップで使用されたか
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
```

#### 6. system_config（システム設定）
```sql
CREATE TABLE system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type TEXT DEFAULT 'string', -- 'string', 'integer', 'boolean', 'json'
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT DEFAULT 'system'
);
```

### インデックス定義
```sql
-- パフォーマンス最適化のためのインデックス
CREATE INDEX idx_workflow_steps_project_status ON workflow_steps(project_id, status);
CREATE INDEX idx_workflow_steps_step_name ON workflow_steps(step_name);
CREATE INDEX idx_project_files_project_type ON project_files(project_id, file_type);
CREATE INDEX idx_project_files_step_category ON project_files(step_name, file_category);
CREATE INDEX idx_api_usage_provider_date ON api_usage(api_provider, date(request_timestamp));
CREATE INDEX idx_api_usage_project_step ON api_usage(project_id, step_name);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_created_at ON projects(created_at);
```

## データアクセスパターン

### 1. プロジェクト作成
```python
def create_project(project_id: str, name: str, config: dict) -> str:
    # 1. データベースにプロジェクト情報を登録
    # 2. ディレクトリ構造を作成
    # 3. 初期ワークフローステップを設定
```

### 2. ステップ実行
```python
def execute_step(project_id: str, step_name: str):
    # 1. ステップ状態を'running'に更新
    # 2. 前のステップの出力データを取得
    # 3. ステップ実行
    # 4. 結果をデータベース + ファイルシステムに保存
    # 5. ステップ状態を'completed'に更新
```

### 3. データ取得
```python
def get_step_output(project_id: str, step_name: str) -> dict:
    # 1. データベースから出力サマリーを取得
    # 2. 必要に応じてファイルシステムからファイルを読み込み
    # 3. 統合されたデータを返す
```

## マイグレーション戦略

### 既存データの移行
1. **flow_definition.yaml**: 新しいデータベース設計に対応
2. **入出力定義**: ファイルパスから関数呼び出しに変更
3. **設定ファイル**: データベース接続設定を追加

### 互換性の維持
- 既存のファイル構造は当面維持
- 段階的な移行を実施
- ロールバック可能な設計

## 運用・監視

### バックアップ戦略
- **データベース**: 定期的なSQLiteファイルのバックアップ
- **ファイル**: プロジェクトディレクトリの差分バックアップ

### 監視項目
- データベースサイズ
- API使用量とコスト
- 処理時間のトレンド
- エラー率

### パフォーマンス最適化
- インデックスの適切な設定
- 不要なファイルの自動削除
- キャッシュ機能の活用

## セキュリティ考慮事項

### データ保護
- SQLiteファイルの適切な権限設定
- 機密情報の暗号化
- APIキーの安全な管理

### バックアップセキュリティ
- バックアップファイルの暗号化
- アクセス制御の実装

## 今後の拡張性

### スケールアップ
- PostgreSQLへの移行対応
- 分散ファイルシステムの対応
- マルチユーザー対応

### 機能拡張
- プロジェクトテンプレート機能
- バッチ処理機能
- API経由でのプロジェクト管理

---

このデータベース設計により、従来のファイルベースの課題を解決し、スケーラブルで保守性の高いシステムを構築できます。 