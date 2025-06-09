# セットアップガイド - 環境設定とAPIキー設定

このガイドでは、ゆっくり動画自動生成ツールの初期設定方法について説明します。

## 1. 環境変数設定

### 1.1 `.env`ファイルの作成

プロジェクトルートディレクトリに`.env`ファイルを作成し、以下の内容をコピーして実際の値を設定してください：

```bash
# ゆっくり動画自動生成ツール - 環境変数設定

# ===========================================
# LLM API 設定 (必須)
# ===========================================

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ORGANIZATION=your_openai_org_id_here  # オプション

# Anthropic Claude API (代替LLM)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# ===========================================
# TTS (音声合成) API 設定 (必須)
# ===========================================

# AIVIS Speech API
AIVIS_API_KEY=your_aivis_api_key_here
AIVIS_API_URL=https://api.aivis.co.jp/v1
AIVIS_USER_ID=your_aivis_user_id_here

# Azure Speech Services (代替TTS)
AZURE_SPEECH_KEY=your_azure_speech_key_here
AZURE_SPEECH_REGION=your_azure_region_here

# ===========================================
# 画像生成 API 設定 (必須)
# ===========================================

# DALL-E (OpenAI) - OPENAI_API_KEY を使用

# Stable Diffusion API
STABILITY_API_KEY=your_stability_api_key_here

# Leonardo AI
LEONARDO_API_KEY=your_leonardo_api_key_here

# ===========================================
# YouTube Data API 設定 (オプション)
# ===========================================

# YouTube Data API v3
YOUTUBE_API_KEY=your_youtube_api_key_here
YOUTUBE_CLIENT_ID=your_youtube_client_id_here
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret_here
YOUTUBE_REDIRECT_URI=http://localhost:8080/oauth2callback

# ===========================================
# アプリケーション設定
# ===========================================

# 動作環境
ENVIRONMENT=development

# ログレベル
LOG_LEVEL=INFO

# ディレクトリ設定
TEMP_DIR=./temp
PROJECTS_DIR=./projects
ASSETS_DIR=./assets

# 最大並列処理数
MAX_WORKERS=4

# セキュリティ
SECRET_KEY=your_secret_key_32_characters_long

# FFmpeg設定 (自動検出されない場合)
FFMPEG_PATH=/usr/bin/ffmpeg
FFPROBE_PATH=/usr/bin/ffprobe

# ===========================================
# オプション設定
# ===========================================

# デバッグモード
DEBUG=true

# 通知設定
WEBHOOK_URL=your_webhook_url_here

# API使用制限
DAILY_API_QUOTA_OPENAI=1000
DAILY_API_QUOTA_AIVIS=500
DAILY_API_QUOTA_IMAGE_GEN=100
```

## 2. 必須APIキーの取得方法

### 2.1 OpenAI API キー (テーマ・スクリプト・タイトル生成用)

1. [OpenAI Platform](https://platform.openai.com/)にアクセス
2. アカウント作成・ログイン
3. 「API keys」セクションでAPIキーを生成
4. 使用料金の監視設定を推奨

**料金目安**: GPT-4使用時、動画1本あたり$0.50-2.00程度

### 2.2 AIVIS Speech API キー (音声合成用)

1. [AIVIS Speech](https://aivis.co.jp/)にアクセス
2. 開発者アカウント登録
3. APIキーとユーザーIDを取得
4. 使用プランを選択

**料金目安**: 1分間の音声生成で約10-30円

### 2.3 画像生成 API キー

#### DALL-E (OpenAI) - 推奨
- OpenAI APIキーで使用可能
- **料金**: 1024x1024画像1枚あたり$0.040

#### Stable Diffusion API (DreamStudio)
1. [DreamStudio](https://dreamstudio.ai/)でアカウント作成
2. APIキーを取得
3. **料金**: 画像1枚あたり約$0.01-0.05

#### Leonardo AI - 高品質オプション
1. [Leonardo AI](https://leonardo.ai/)でアカウント作成
2. APIアクセスを申請
3. **料金**: プランにより異なる

### 2.4 YouTube Data API (自動投稿用、オプション)

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクト作成
2. YouTube Data API v3を有効化
3. OAuth 2.0認証情報を作成
4. APIキーを取得

**制限**: 1日1万リクエストまで無料

## 3. 代替API設定 (オプション)

### 3.1 Azure Speech Services (TTS代替)
1. [Azure Portal](https://portal.azure.com/)でアカウント作成
2. Speech Servicesリソースを作成
3. キーとリージョンを取得

### 3.2 Google Cloud Text-to-Speech (TTS代替)
1. Google Cloud Platformでプロジェクト作成
2. Text-to-Speech APIを有効化
3. サービスアカウントキーを作成・ダウンロード

## 4. ディレクトリ構造の初期化

以下のコマンドで必要なディレクトリを作成：

```bash
mkdir -p {temp,projects,assets,config}
mkdir -p assets/{characters,audio,fonts,templates}
mkdir -p assets/characters/{reimu,marisa,common}
mkdir -p assets/audio/{bgm,sound_effects,jingles}
```

## 5. 必要なソフトウェアのインストール

### 5.1 FFmpeg (動画処理用)

#### Windows
1. [FFmpeg公式サイト](https://ffmpeg.org/download.html)からダウンロード
2. PATHに追加

#### macOS
```bash
brew install ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

### 5.2 Python依存関係
```bash
pip install -r requirements.txt
```

## 6. 設定ファイルの作成

### 6.1 基本設定ファイル
各種設定ファイルのテンプレートを`config/`ディレクトリに作成します：

- `config/llm_config.yaml` - LLM設定
- `config/voice_config.yaml` - 音声合成設定
- `config/character_config.yaml` - 立ち絵設定
- `config/subtitle_config.yaml` - 字幕設定
- `config/encoding_config.yaml` - 動画エンコード設定
- `config/youtube_config.yaml` - YouTube投稿設定

## 7. セキュリティの注意事項

### 7.1 APIキーの保護
- `.env`ファイルは**絶対に**Gitにコミットしない
- `.gitignore`に`.env`が含まれていることを確認
- 本番環境では環境変数として設定

### 7.2 権限設定
```bash
# .envファイルの権限を制限
chmod 600 .env
```

### 7.3 APIキーのローテーション
- 定期的にAPIキーを更新
- 使用していないキーは無効化

## 8. 初期テスト

環境設定が完了したら、以下のテストを実行：

```bash
# 設定テスト
python -m src.utils.config_loader --test

# API接続テスト
python -m src.api.llm_client --test
python -m src.api.tts_client --test
python -m src.api.image_gen_client --test
```

## 9. トラブルシューティング

### 9.1 よくある問題

#### FFmpegが見つからない
```bash
# FFmpegのパスを確認
which ffmpeg
# または
ffmpeg -version
```

#### APIキーが無効
- APIキーの有効期限を確認
- 使用量制限に達していないか確認
- APIサービスの稼働状況を確認

#### 権限エラー
- ディレクトリの書き込み権限を確認
- 一時ディレクトリの容量を確認

### 9.2 ログの確認
```bash
# ログファイルの確認
tail -f logs/application.log
tail -f logs/errors.log
```

## 10. 費用見積もり

### 10.1 API使用料金（5分動画1本あたりの目安）

| サービス | 用途 | 料金目安 |
|---------|------|----------|
| OpenAI GPT-4 | テーマ・スクリプト・タイトル生成 | $0.50-2.00 |
| AIVIS Speech | 音声合成（5分） | ¥50-150 |
| DALL-E | 背景画像生成（10枚） | $0.40 |
| YouTube API | 投稿 | 無料 |
| **合計** | | **約¥200-400** |

### 10.2 月間費用見積もり（動画30本/月の場合）
- **合計**: 約¥6,000-12,000/月
- **年間**: 約¥72,000-144,000/年

### 10.3 費用削減のヒント
- 画像生成APIは複数サービスを併用
- キャッシュ機能を活用
- API使用量の監視・制限を設定

## 11. 次のステップ

環境設定が完了したら：
1. [開発ガイド](development_guide.md)を参照して開発を開始
2. [タスク分割](task_breakdown.md)に従って段階的に実装
3. テスト駆動開発で品質を確保 