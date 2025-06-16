"""
ゆっくり動画自動生成ツール

このパッケージは、AI/LLM/TTS/画像生成モデルを連携させ、
ゆっくり動画を企画からYouTube投稿まで自動生成するツールです。

フェーズ1〜3で実装された機能:
- プロジェクト管理（作成、状態追跡、設定管理）
- ワークフローエンジン（並列処理、依存関係解決、進捗監視）
- テーマ選定（AI による自動テーマ生成・評価）
- API クライアント（Gemini LLM、AIVIS Speech TTS、画像生成、YouTube）
- 高レベルユーティリティ（簡単インターフェース）

使用例:
    # 簡単なテキスト生成
    from src.utils.text_generation import generate_text
    text = await generate_text("Pythonについて説明して")
    
    # プロジェクト作成・管理
    from src.core import ProjectManager, DatabaseManager
    db_manager = DatabaseManager("data/yukkuri_tool.db")
    project_manager = ProjectManager(db_manager, "projects")
    project_id = project_manager.create_project("Python入門", 5)
    
    # 音声生成
    from src.api import AivisSpeechClient, TTSRequest
    async with AivisSpeechClient() as client:
        request = TTSRequest(text="こんにちは！", speaker_id=0)
        response = await client.generate_audio(request)
        response.save_audio("hello.wav")
"""

__version__ = "1.0.0"
__author__ = "Yukkuri Video Generation Team"
__license__ = "MIT"

# 🎯 コア機能のインポート
from .core import (
    # プロジェクト管理
    ProjectManager,
    
    # ワークフローエンジン
    WorkflowEngine,
    WorkflowExecutionState,
    WorkflowExecutionResult,
    WorkflowExecutionPlan,
    
    # データベース・ストレージ
    DatabaseManager,
    ProjectRepository,
    FileSystemManager,
    
    # 設定・状態管理
    ConfigManager,
    ProjectStateManager,
    DataIntegrationManager,
    
    # 監視
    ProgressMonitor
)

# 🔧 処理モジュールのインポート
from .modules import (
    # テーマ選定機能
    ThemeSelector,
    ThemeSelectionInput,
    ThemeSelectionOutput,
    UserPreferences,
    ThemeCandidate,
    SelectedTheme,
    DatabaseDataAccess,
    GeminiThemeLLM,
    
    # モジュール状態
    MODULE_STATUS
)

# 🌐 API クライアントのインポート
from .api import (
    # LLM API
    GeminiLLMClient,
    GeminiRequest,
    GeminiResponse,
    ModelType,
    OutputFormat,
    
    # TTS API
    AivisSpeechClient,
    TTSRequest,
    TTSResponse,
    AudioSettings,
    SpeakerStyle,
    TimestampData,
    
    # 画像生成 API
    ImageGenerationClient,
    ImageRequest,
    ImageResponse,
    ImageStyle,
    ImageFormat,
    
    # YouTube API
    YouTubeClient,
    VideoUploadRequest,
    VideoUploadResponse,
    VideoMetadata,
    VideoPrivacy
)

# 🛠️ ユーティリティのインポート
from .utils import (
    # 高レベルテキスト生成
    generate_text,
    generate_yukkuri_script,
    generate_video_title,
    generate_json_data,
    summarize_text,
    safe_generate_text,
    
    # 高レベル音声生成
    generate_speech,
    generate_yukkuri_dialogue,
    generate_script_audio,
    batch_generate_audio,
    get_available_speakers,
    test_tts_connection,
    safe_generate_speech,
    
    # 高レベルプロジェクト管理
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
    get_project_statistics,
    
    # 高レベルテーマ選定
    select_theme,
    generate_theme_candidates,
    get_theme_suggestions_by_keywords,
    get_popular_themes,
    save_theme_to_file,
    load_theme_from_file,
    safe_select_theme
)

# 便利な関数の提供
def get_version() -> str:
    """バージョン情報を取得"""
    return __version__

def get_module_status() -> dict:
    """モジュール実装状況を取得"""
    return MODULE_STATUS.copy()

def list_available_functions() -> list:
    """利用可能な関数一覧を取得"""
    return [
        # コア機能
        "ProjectManager", "WorkflowEngine", "DatabaseManager",
        
        # 処理モジュール
        "ThemeSelector", "UserPreferences", "ThemeSelectionInput",
        
        # API クライアント
        "GeminiLLMClient", "AivisSpeechClient", "ImageGenerationClient", "YouTubeClient",
        
        # ユーティリティ
        "generate_text", "generate_yukkuri_script", "generate_video_title"
    ]

# パッケージ情報
PACKAGE_INFO = {
    "name": "ゆっくり動画自動生成ツール",
    "version": __version__,
    "description": "AI/LLM/TTS を活用した動画自動生成システム",
    "phase_status": {
        "phase_1": "完了（基盤システム構築）",
        "phase_2": "完了（API連携基盤）", 
        "phase_3": "完了（コア機能実装）",
        "phase_4": "開発中（処理モジュール開発）"
    },
    "implemented_features": [
        "プロジェクト管理",
        "ワークフローエンジン",
        "テーマ選定",
        "LLM テキスト生成",
        "TTS 音声合成",
        "高レベルユーティリティ"
    ],
    "planned_features": [
        "スクリプト生成",
        "画像生成・アニメーション",
        "動画合成・エンコード",
        "YouTube アップロード"
    ]
}

def get_package_info() -> dict:
    """パッケージ情報を取得"""
    return PACKAGE_INFO.copy()

# 全エクスポート項目
__all__ = [
    # バージョン・情報
    "__version__", "get_version", "get_module_status", "get_package_info",
    "list_available_functions", "PACKAGE_INFO",
    
    # コア機能
    "ProjectManager", "WorkflowEngine", "WorkflowExecutionState", 
    "WorkflowExecutionResult", "WorkflowExecutionPlan",
    "DatabaseManager", "ProjectRepository", "FileSystemManager",
    "ConfigManager", "ProjectStateManager", "DataIntegrationManager",
    "ProgressMonitor",
    
    # 処理モジュール
    "ThemeSelector", "ThemeSelectionInput", "ThemeSelectionOutput",
    "UserPreferences", "ThemeCandidate", "SelectedTheme",
    "DatabaseDataAccess", "GeminiThemeLLM", "MODULE_STATUS",
    
    # API クライアント
    "GeminiLLMClient", "GeminiRequest", "GeminiResponse", "ModelType", "OutputFormat",
    "AivisSpeechClient", "TTSRequest", "TTSResponse", "AudioSettings", 
    "SpeakerStyle", "TimestampData",
    "ImageGenerationClient", "ImageRequest", "ImageResponse", "ImageStyle", "ImageFormat",
    "YouTubeClient", "VideoUploadRequest", "VideoUploadResponse", "VideoMetadata", "VideoPrivacy",
    
    # ユーティリティ
    "generate_text", "generate_yukkuri_script", "generate_video_title",
    "generate_json_data", "summarize_text", "safe_generate_text",
    "generate_speech", "generate_yukkuri_dialogue", "generate_script_audio",
    "batch_generate_audio", "get_available_speakers", "test_tts_connection",
    "safe_generate_speech", "create_project", "get_project_info", "list_projects",
    "update_project_status", "get_project_progress", "get_project_directory",
    "delete_project", "initialize_project_workflow", "get_estimated_remaining_time",
    "find_projects_by_theme", "cleanup_incomplete_projects", "export_project_summary",
    "get_project_statistics", "select_theme", "generate_theme_candidates",
    "get_theme_suggestions_by_keywords", "get_popular_themes", "save_theme_to_file",
    "load_theme_from_file", "safe_select_theme"
]

# 開発者向け情報
if __name__ == "__main__":
    print("🎬 ゆっくり動画自動生成ツール")
    print(f"バージョン: {__version__}")
    print("\n📋 実装済み機能:")
    for feature in PACKAGE_INFO["implemented_features"]:
        print(f"  ✅ {feature}")
    
    print("\n🚧 開発予定機能:")
    for feature in PACKAGE_INFO["planned_features"]:
        print(f"  🔄 {feature}")
    
    print(f"\n📊 モジュール状況:")
    for module, status in MODULE_STATUS.items():
        icon = "✅" if status == "実装済み" else "🚧" if status == "開発中" else "⏳"
        print(f"  {icon} {module}: {status}")
    
    print(f"\n🔗 利用可能な関数: {len(list_available_functions())}個")
    print("\n詳細は docs/functions_summary.md を参照してください。") 