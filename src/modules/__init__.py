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
from .background_generator import BackgroundGenerator
from .subtitle_generator import SubtitleGenerator
from .video_composer import VideoComposer

__version__ = "1.0.0"

# 各モジュールの実装状況
MODULE_STATUS = {
    "theme_selection": "実装済み",
    "script_generation": "実装済み",
    "title_generation": "実装済み", 
    "tts_generation": "実装済み",
    "character_synthesis": "実装済み",
    "background_generation": "実装済み",
    "background_animation": "実装済み", 
    "subtitle_generation": "実装済み",
    "video_composition": "実装済み",
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
    "CharacterSynthesizer",
    "BackgroundGenerator",
    "SubtitleGenerator",
    "VideoComposer"
] 