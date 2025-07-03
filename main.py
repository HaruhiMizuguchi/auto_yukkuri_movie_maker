#!/usr/bin/env python3
"""
ゆっくり動画自動生成ツール - メインエントリーポイント

AI/LLM/TTS/画像生成モデルを連携させ、ゆっくり動画を企画からYouTube投稿まで自動生成します。
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.cli.main_cli import main

if __name__ == "__main__":
    main()