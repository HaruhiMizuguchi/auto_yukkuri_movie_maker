# ゆっくり動画 自動生成ツール

AI / LLM / TTS / 画像生成モデルを連携させ、「ゆっくり動画」（霊夢・魔理沙などの立ち絵と合成音声による解説／雑談動画）を企画からYouTube投稿まで自動生成するツールです。

## 特徴

- 企画からYouTube投稿までをワンストップで自動化
- 見やすく・聞きやすく・処理が止まらない品質を保証
- 二次創作ガイドライン（東方Project 等）、YouTube 利用規約、著作権法を順守

## ドキュメント

- [要件定義書](docs/requirements.md)
- [フロー定義](docs/flow_definition.yaml)
- [開発ガイド](docs/development_guide.md)
- [**📋 セットアップガイド**](docs/setup_guide.md) - **最初にお読みください**
- [タスク分割](docs/task_breakdown.md)

## 技術スタック

- Python 3.8+
- AIVIS Speech API (TTS)
- FFmpeg (動画処理)
- YouTube Data API
- 各種AI/LLMサービス

## クイックスタート

### 1. 環境準備
```bash
# リポジトリのクローン
git clone https://github.com/your-username/auto_yukkuri_movie_maker.git
cd auto_yukkuri_movie_maker

# Python依存関係のインストール
pip install -r requirements.txt

# 必要なディレクトリの作成
mkdir -p {temp,projects,assets,config}
```

### 2. 環境変数の設定
```bash
# 環境変数ファイルの作成
cp env_template.txt .env

# .envファイルを編集して実際のAPIキーを設定
# 詳細は docs/setup_guide.md を参照
```

### 3. 必須APIキーの取得
以下のAPIキーが**必須**です：
- **OpenAI API** (テーマ・スクリプト生成)
- **AIVIS Speech API** (音声合成)
- **画像生成API** (DALL-E/Stable Diffusion等)

詳細な取得方法は [📋 セットアップガイド](docs/setup_guide.md) をご覧ください。

### 4. FFmpegのインストール
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html からダウンロード
```

## インストール

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
python main.py
```

## 費用について

**動画1本あたりの目安料金（5分動画）**：
- OpenAI GPT-4: $0.50-2.00
- AIVIS Speech: ¥50-150
- DALL-E: $0.40
- **合計**: 約¥200-400

詳細な費用計算は [セットアップガイド](docs/setup_guide.md#10-費用見積もり) をご確認ください。

## 開発者向け

テスト駆動開発（TDD）でプロジェクトを進行します：

```bash
# 開発用依存関係のインストール
pip install -r requirements-dev.txt

# テストの実行
pytest

# コード品質チェック
flake8 src/
black src/
mypy src/
```

## ライセンス

MIT License

## 注意事項

- 東方Projectの二次創作ガイドラインを遵守
- YouTube利用規約および著作権法を遵守
- APIキーは適切に管理し、公開しないこと 