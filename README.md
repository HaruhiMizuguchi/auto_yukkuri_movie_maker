# ゆっくり動画自動生成ツール

AI/LLM/TTS/画像生成モデルを連携させ、ゆっくり動画を企画からYouTube投稿まで自動生成するツールです。

## 🎯 プロジェクト概要

このツールは以下の機能を提供します：
- テーマ選定からスクリプト生成
- TTS による音声合成
- 立ち絵アニメーション
- 背景画像・動画生成
- 字幕生成・動画合成
- YouTube 自動投稿

## ⚙️ 開発時設定

### 推奨モデル（開発時）
開発時は安価で高速なモデルを使用することを推奨します：

**LLM・画像生成共通：**
- `gemini-2.0-flash-preview-image-generation`
  - コスト効率が高い
  - 画像生成とテキスト生成の両方に対応
  - 開発・テスト用途に最適

### 設定ファイル

開発時は以下の設定が自動的に適用されます：

1. **LLM設定** (`config/llm_config.yaml`)
   - プライマリプロバイダー: Google
   - モデル: `gemini-2.0-flash-preview-image-generation`

2. **画像生成設定** (`config/image_generation_config.yaml`)
   - プライマリプロバイダー: Google
   - モデル: `gemini-2.0-flash-preview-image-generation`
   - 開発時制限: 1日20枚まで

3. **開発設定** (`config/development_config.yaml`)
   - デバッグモード有効
   - コスト管理機能
   - キャッシュ機能で効率化

### 本番環境切り替え

本番環境では以下のモデルに切り替え可能：
- LLM: GPT-4 / Claude-3-Sonnet
- 画像生成: DALL-E 3 / Stable Diffusion

## 🚀 クイックスタート

1. **環境設定**
   ```bash
   pip install -r requirements.txt
   cp env_template.txt .env
   ```

2. **API キー設定**
   `.env` ファイルに以下を追加：
   ```
   GOOGLE_API_KEY=your_gemini_api_key
   ```

3. **開発モード実行**
   ```bash
   python src/main.py --dev-mode
   ```

## 📁 プロジェクト構造

詳細な仕様は `docs/flow_definition.yaml` を参照してください。

```
src/
├── core/           # コアロジック
├── modules/        # 各ステップのモジュール
├── utils/          # ユーティリティ
└── config/         # 設定ファイル

config/
├── llm_config.yaml              # LLM設定
├── image_generation_config.yaml # 画像生成設定
├── development_config.yaml     # 開発時設定
└── voice_config.yaml           # 音声合成設定
```

## 🛠️ 開発ルール

このプロジェクトでは厳格な開発ルールを適用しています：

1. **必須事前確認**
   - 全開発作業前に `docs/flow_definition.yaml` を確認
   - データフローと仕様に厳密に従う

2. **テスト駆動開発**
   - コード実装前に必ずテストを作成
   - カバレッジ 80% 以上を目標

3. **コスト管理**
   - 開発時は安価なモデルを使用
   - API呼び出し回数の監視
   - キャッシュ機能の活用

詳細は `.cursorrules` ファイルを参照してください。

## 📚 ドキュメント

- [フロー定義](docs/flow_definition.yaml) - 全体仕様
- [AIVISSpeech使用方法](docs/aivis_speech_usage.md) - TTS設定

## 🔐 ライセンス・著作権

- 二次創作ガイドライン（東方Project等）を遵守
- YouTube利用規約を遵守
- 使用する音楽・画像の著作権を確認してから使用

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