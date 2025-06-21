"""
フェーズ4: 処理モジュール開発

動画生成に必要な各処理モジュールを実装
各モジュールはflow_definition.yamlに定義されたデータフローに従って実装される
"""

from typing import Any, Dict

# テーマ選定機能のインポート
from .theme_selector import (
    ThemeSelector,
    ThemeSelectionInput,
    ThemeSelectionOutput,
    UserPreferences,
    ThemeCandidate,
    SelectedTheme,
    DatabaseDataAccess,
    GeminiThemeLLM
)

# その他のモジュール
from .script_generator import ScriptGenerator
from .title_generator import TitleGenerator
from .tts_processor import TTSProcessor
from .character_synthesizer import CharacterSynthesizer

__version__ = "1.0.0"

# 各モジュールの実装状況
MODULE_STATUS = {
    "theme_selection": "実装済み",
    "script_generation": "実装済み",
    "title_generation": "実装済み", 
    "tts_generation": "実装済み",
    "character_synthesis": "実装中",
    "background_generation": "未実装",
    "background_animation": "未実装",
    "subtitle_generation": "未実装",
    "video_composition": "未実装",
    "audio_enhancement": "未実装",
    "illustration_insertion": "未実装",
    "final_encoding": "未実装",
    "youtube_upload": "運用後実装予定"
}

__all__ = [
    "MODULE_STATUS",
    # テーマ選定機能
    "ThemeSelector",
    "ThemeSelectionInput", 
    "ThemeSelectionOutput",
    "UserPreferences",
    "ThemeCandidate",
    "SelectedTheme",
    "DatabaseDataAccess",
    "GeminiThemeLLM",
    # その他のモジュール
    "ScriptGenerator",
    "TitleGenerator",
    "TTSProcessor",
    "CharacterSynthesizer"
] 