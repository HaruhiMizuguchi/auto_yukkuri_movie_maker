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