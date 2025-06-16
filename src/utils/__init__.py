"""
ユーティリティモジュール

高レベルで使いやすいラッパー関数を提供します。
"""

# テキスト生成関連
from .text_generation import (
    generate_text,
    generate_yukkuri_script,
    generate_video_title,
    generate_json_data,
    summarize_text,
    safe_generate_text
)

# 音声生成関連
from .audio_generation import (
    generate_speech,
    generate_yukkuri_dialogue,
    generate_script_audio,
    batch_generate_audio,
    get_available_speakers,
    test_tts_connection,
    safe_generate_speech
)

# プロジェクト管理関連
from .project_utils import (
    create_project,
    get_project_info,
    list_projects,
    update_project_status,
    get_project_progress,
    get_project_directory,
    delete_project,
    initialize_project_workflow,
    get_estimated_remaining_time,
    find_projects_by_theme,
    cleanup_incomplete_projects,
    export_project_summary,
    get_project_statistics
)

# テーマ選定関連
from .theme_utils import (
    select_theme,
    generate_theme_candidates,
    get_theme_suggestions_by_keywords,
    get_popular_themes,
    save_theme_to_file,
    load_theme_from_file,
    safe_select_theme
)

# 画像生成関連
from .image_generation import (
    generate_image,
    edit_image,
    generate_yukkuri_thumbnails,
    batch_generate_images,
    test_image_generation,
    get_supported_formats,
    safe_generate_image
)

__all__ = [
    # テキスト生成
    "generate_text",
    "generate_yukkuri_script", 
    "generate_video_title",
    "generate_json_data",
    "summarize_text",
    "safe_generate_text",
    
    # 音声生成
    "generate_speech",
    "generate_yukkuri_dialogue",
    "generate_script_audio",
    "batch_generate_audio", 
    "get_available_speakers",
    "test_tts_connection",
    "safe_generate_speech",
    
    # プロジェクト管理
    "create_project",
    "get_project_info",
    "list_projects",
    "update_project_status",
    "get_project_progress",
    "get_project_directory",
    "delete_project",
    "initialize_project_workflow",
    "get_estimated_remaining_time",
    "find_projects_by_theme",
    "cleanup_incomplete_projects",
    "export_project_summary",
    "get_project_statistics",
    
    # テーマ選定
    "select_theme",
    "generate_theme_candidates",
    "get_theme_suggestions_by_keywords",
    "get_popular_themes",
    "save_theme_to_file",
    "load_theme_from_file",
    "safe_select_theme",
    
    # 画像生成
    "generate_image",
    "edit_image",
    "generate_yukkuri_thumbnails",
    "batch_generate_images",
    "test_image_generation",
    "get_supported_formats",
    "safe_generate_image"
] 