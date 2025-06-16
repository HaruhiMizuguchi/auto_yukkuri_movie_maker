# プロジェクト管理機能 (Project Manager)

## 概要

`ProjectManager`は、ゆっくり動画生成プロジェクトの作成、管理、状態追跡を行うクラスです。データベースとファイルシステムを使って、プロジェクトのライフサイクル全体を管理します。

## 基本的な使用方法

### プロジェクトマネージャーの初期化

```python
from src.core import ProjectManager, DatabaseManager

# データベースマネージャーの初期化
db_manager = DatabaseManager("data/yukkuri_tool.db")

# プロジェクトマネージャーの初期化
project_manager = ProjectManager(
    db_manager=db_manager,
    projects_base_dir="projects"
)
```

### プロジェクトの作成

```python
# 基本的なプロジェクト作成
project_id = project_manager.create_project(
    theme="Pythonの基礎解説",
    target_length_minutes=7
)
print(f"作成されたプロジェクトID: {project_id}")

# 設定付きプロジェクト作成
config = {
    "voice_settings": {
        "reimu_speed": 1.0,
        "marisa_speed": 1.1
    },
    "video_settings": {
        "resolution": "1920x1080",
        "fps": 30
    },
    "user_preferences": {
        "preferred_genres": ["プログラミング", "技術解説"],
        "target_audience": "初心者",
        "content_style": "分かりやすい"
    }
}

project_id = project_manager.create_project(
    theme="Web開発入門",
    target_length_minutes=10,
    config=config
)
```

### プロジェクト情報の取得

```python
# プロジェクト詳細取得
project = project_manager.get_project(project_id)
if project:
    print(f"テーマ: {project['theme']}")
    print(f"目標時間: {project['target_length_minutes']}分")
    print(f"状態: {project['status']}")
    print(f"作成日時: {project['created_at']}")
else:
    print("プロジェクトが見つかりませんでした")

# プロジェクト一覧取得
projects = project_manager.list_projects(limit=10)
for project in projects:
    print(f"ID: {project['id']}")
    print(f"テーマ: {project['theme']}")
    print(f"状態: {project['status']}")
    print("---")
```

### プロジェクト状態の更新

```python
# ステータス更新
success = project_manager.update_project_status(project_id, "processing")
if success:
    print("ステータスを更新しました")

# 利用可能なステータス
statuses = [
    "created",      # 作成済み
    "processing",   # 処理中
    "completed",    # 完了
    "failed",       # 失敗
    "cancelled"     # キャンセル
]
```

### プロジェクト設定の管理

```python
# 設定取得
config = project_manager.get_project_config(project_id)
if config:
    print("現在の設定:")
    for key, value in config.items():
        print(f"  {key}: {value}")

# 設定更新
new_config = {
    "voice_settings": {
        "reimu_speed": 1.2,
        "marisa_speed": 1.0
    },
    "video_settings": {
        "resolution": "1920x1080",
        "fps": 60
    }
}

success = project_manager.update_project_config(project_id, new_config)
if success:
    print("設定を更新しました")
```

### プロジェクトディレクトリの操作

```python
# プロジェクトディレクトリパス取得
project_dir = project_manager.get_project_directory(project_id)
print(f"プロジェクトディレクトリ: {project_dir}")

# ディレクトリ構造
"""
projects/
└── {project_id}/
    ├── files/
    │   ├── scripts/        # スクリプトファイル
    │   ├── audio/          # 音声ファイル
    │   ├── video/          # 動画ファイル
    │   ├── images/         # 画像ファイル
    │   ├── subtitles/      # 字幕ファイル
    │   └── metadata/       # メタデータ
    ├── config/             # 設定ファイル
    ├── logs/               # ログファイル
    └── cache/              # キャッシュファイル
"""
```

### プロジェクトの削除

```python
# プロジェクト削除（注意：データベースとファイルの両方が削除されます）
success = project_manager.delete_project(project_id)
if success:
    print("プロジェクトを削除しました")
else:
    print("プロジェクトの削除に失敗しました")
```

## 実際の使用例

### 完全なプロジェクト作成フロー

```python
import json
from pathlib import Path
from src.core import ProjectManager, DatabaseManager

def create_video_project():
    """ビデオプロジェクト作成の完全例"""
    
    # 1. データベース初期化
    db_manager = DatabaseManager("data/yukkuri_tool.db")
    project_manager = ProjectManager(db_manager, "projects")
    
    # 2. プロジェクト設定定義
    project_config = {
        "voice_settings": {
            "reimu": {
                "speed": 1.0,
                "pitch": 0.0,
                "volume": 1.0
            },
            "marisa": {
                "speed": 1.1,
                "pitch": 0.1,
                "volume": 1.0
            }
        },
        "video_settings": {
            "resolution": "1920x1080",
            "fps": 30,
            "bitrate": "5000k"
        },
        "user_preferences": {
            "genre_history": ["プログラミング", "AI"],
            "preferred_genres": ["技術解説", "チュートリアル"],
            "excluded_genres": ["ゲーム実況"],
            "target_audience": "プログラマー",
            "content_style": "実践的"
        }
    }
    
    # 3. プロジェクト作成
    try:
        project_id = project_manager.create_project(
            theme="機械学習の基礎：線形回帰を理解しよう",
            target_length_minutes=8,
            config=project_config
        )
        
        print(f"✅ プロジェクト作成成功: {project_id}")
        
        # 4. 作成したプロジェクトの確認
        project = project_manager.get_project(project_id)
        print(f"📝 テーマ: {project['theme']}")
        print(f"⏱️ 目標時間: {project['target_length_minutes']}分")
        print(f"📁 ディレクトリ: {project_manager.get_project_directory(project_id)}")
        
        return project_id
        
    except Exception as e:
        print(f"❌ プロジェクト作成エラー: {e}")
        return None

# 実行
project_id = create_video_project()
```

### バッチプロジェクト作成

```python
def create_multiple_projects():
    """複数プロジェクトの一括作成"""
    
    project_manager = ProjectManager(
        DatabaseManager("data/yukkuri_tool.db"),
        "projects"
    )
    
    # プロジェクトテンプレート
    project_templates = [
        {
            "theme": "Python基礎：変数と型",
            "target_length_minutes": 5,
            "config": {"difficulty": "beginner"}
        },
        {
            "theme": "Python基礎：制御構文",
            "target_length_minutes": 7,
            "config": {"difficulty": "beginner"}
        },
        {
            "theme": "Python基礎：関数の使い方",
            "target_length_minutes": 8,
            "config": {"difficulty": "intermediate"}
        }
    ]
    
    created_projects = []
    
    for template in project_templates:
        try:
            project_id = project_manager.create_project(**template)
            created_projects.append(project_id)
            print(f"✅ 作成: {template['theme']} -> {project_id}")
        except Exception as e:
            print(f"❌ 失敗: {template['theme']} -> {e}")
    
    return created_projects

# 実行
project_ids = create_multiple_projects()
print(f"作成されたプロジェクト数: {len(project_ids)}")
```

### プロジェクト進捗管理

```python
def manage_project_lifecycle(project_id: str):
    """プロジェクトライフサイクル管理"""
    
    project_manager = ProjectManager(
        DatabaseManager("data/yukkuri_tool.db"),
        "projects"
    )
    
    try:
        # 1. 処理開始
        project_manager.update_project_status(project_id, "processing")
        print("🚀 処理開始")
        
        # 2. 各段階での状態更新（実際の処理は省略）
        stages = [
            ("theme_selection", "テーマ選定"),
            ("script_generation", "スクリプト生成"),
            ("audio_generation", "音声生成"),
            ("video_composition", "動画合成")
        ]
        
        for stage_id, stage_name in stages:
            print(f"📝 {stage_name}を実行中...")
            # 実際の処理をここに書く
            # process_stage(project_id, stage_id)
            
        # 3. 処理完了
        project_manager.update_project_status(project_id, "completed")
        print("✅ 処理完了")
        
        # 4. 最終結果確認
        project = project_manager.get_project(project_id)
        print(f"最終状態: {project['status']}")
        
    except Exception as e:
        # エラー発生時は失敗状態に更新
        project_manager.update_project_status(project_id, "failed")
        print(f"❌ 処理失敗: {e}")

# 使用例
# manage_project_lifecycle("your-project-id")
```

### プロジェクト検索・フィルタリング

```python
def find_projects_by_criteria():
    """条件によるプロジェクト検索"""
    
    project_manager = ProjectManager(
        DatabaseManager("data/yukkuri_tool.db"),
        "projects"
    )
    
    # 全プロジェクト取得
    all_projects = project_manager.list_projects()
    
    # 完了済みプロジェクトを検索
    completed_projects = [
        p for p in all_projects 
        if p['status'] == 'completed'
    ]
    print(f"完了済みプロジェクト: {len(completed_projects)}件")
    
    # プログラミング関連プロジェクトを検索
    programming_projects = [
        p for p in all_projects
        if 'プログラミング' in p['theme'] or 'Python' in p['theme']
    ]
    print(f"プログラミング関連: {len(programming_projects)}件")
    
    # 長時間動画プロジェクトを検索
    long_videos = [
        p for p in all_projects
        if p['target_length_minutes'] > 10
    ]
    print(f"10分超の動画: {len(long_videos)}件")
    
    return {
        'completed': completed_projects,
        'programming': programming_projects,
        'long_videos': long_videos
    }

# 実行
search_results = find_projects_by_criteria()
```

## エラーハンドリング

### 一般的なエラーパターン

```python
def robust_project_creation(theme: str, target_length: int):
    """堅牢なプロジェクト作成"""
    
    try:
        # データベース接続確認
        db_manager = DatabaseManager("data/yukkuri_tool.db")
        if not db_manager.is_connected():
            raise ConnectionError("データベースに接続できません")
        
        project_manager = ProjectManager(db_manager, "projects")
        
        # 入力値検証
        if not theme.strip():
            raise ValueError("テーマが空です")
        
        if target_length < 1 or target_length > 60:
            raise ValueError("目標時間は1-60分の間で指定してください")
        
        # プロジェクト作成
        project_id = project_manager.create_project(theme, target_length)
        
        # 作成確認
        created_project = project_manager.get_project(project_id)
        if not created_project:
            raise RuntimeError("プロジェクト作成の確認に失敗しました")
        
        return project_id
        
    except ValueError as e:
        print(f"入力値エラー: {e}")
        return None
    except ConnectionError as e:
        print(f"接続エラー: {e}")
        return None
    except OSError as e:
        print(f"ファイルシステムエラー: {e}")
        return None
    except Exception as e:
        print(f"予期しないエラー: {e}")
        return None

# 使用例
project_id = robust_project_creation("AI入門", 5)
if project_id:
    print(f"✅ プロジェクト作成成功: {project_id}")
else:
    print("❌ プロジェクト作成失敗")
```

### データベース整合性確認

```python
def verify_project_integrity(project_id: str):
    """プロジェクト整合性確認"""
    
    project_manager = ProjectManager(
        DatabaseManager("data/yukkuri_tool.db"),
        "projects"
    )
    
    # データベース内のプロジェクト確認
    project = project_manager.get_project(project_id)
    if not project:
        print(f"❌ データベースにプロジェクトが見つかりません: {project_id}")
        return False
    
    # ディレクトリ存在確認
    project_dir = Path(project_manager.get_project_directory(project_id))
    if not project_dir.exists():
        print(f"❌ プロジェクトディレクトリが見つかりません: {project_dir}")
        return False
    
    # 必須サブディレクトリ確認
    required_dirs = [
        "files/scripts", "files/audio", "files/video",
        "files/images", "files/metadata", "config", "logs", "cache"
    ]
    
    missing_dirs = []
    for subdir in required_dirs:
        if not (project_dir / subdir).exists():
            missing_dirs.append(subdir)
    
    if missing_dirs:
        print(f"⚠️ 不足ディレクトリ: {missing_dirs}")
    
    # 設定ファイル確認
    config = project_manager.get_project_config(project_id)
    if config is None:
        print("⚠️ プロジェクト設定が見つかりません")
    
    print(f"✅ プロジェクト整合性確認完了: {project_id}")
    return True

# 使用例
# verify_project_integrity("your-project-id")
```

## 設定管理のベストプラクティス

### 設定テンプレート

```python
# 設定テンプレート定義
CONFIG_TEMPLATES = {
    "beginner": {
        "voice_settings": {
            "reimu": {"speed": 0.9, "pitch": 0.0},
            "marisa": {"speed": 0.9, "pitch": 0.0}
        },
        "video_settings": {
            "resolution": "1280x720",
            "fps": 30
        },
        "complexity": "low"
    },
    "advanced": {
        "voice_settings": {
            "reimu": {"speed": 1.2, "pitch": 0.1},
            "marisa": {"speed": 1.3, "pitch": 0.2}
        },
        "video_settings": {
            "resolution": "1920x1080",
            "fps": 60
        },
        "complexity": "high"
    }
}

def create_project_with_template(theme: str, template_name: str):
    """テンプレートを使用したプロジェクト作成"""
    
    if template_name not in CONFIG_TEMPLATES:
        raise ValueError(f"不正なテンプレート名: {template_name}")
    
    config = CONFIG_TEMPLATES[template_name].copy()
    
    project_manager = ProjectManager(
        DatabaseManager("data/yukkuri_tool.db"),
        "projects"
    )
    
    return project_manager.create_project(
        theme=theme,
        target_length_minutes=5,
        config=config
    )

# 使用例
project_id = create_project_with_template("Python入門", "beginner")
```

### 設定の継承・マージ

```python
def merge_configs(base_config: dict, override_config: dict) -> dict:
    """設定のマージ（深い結合）"""
    import copy
    
    result = copy.deepcopy(base_config)
    
    for key, value in override_config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result

# 使用例
base_config = CONFIG_TEMPLATES["beginner"]
custom_overrides = {
    "voice_settings": {
        "reimu": {"speed": 1.0}  # speedのみ上書き
    },
    "custom_setting": "value"   # 新しい設定追加
}

final_config = merge_configs(base_config, custom_overrides)
```

## パフォーマンス最適化

### バッチ操作

```python
def batch_status_update(project_ids: List[str], new_status: str):
    """プロジェクト状態の一括更新"""
    
    project_manager = ProjectManager(
        DatabaseManager("data/yukkuri_tool.db"),
        "projects"
    )
    
    success_count = 0
    failed_count = 0
    
    for project_id in project_ids:
        try:
            if project_manager.update_project_status(project_id, new_status):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"エラー {project_id}: {e}")
            failed_count += 1
    
    print(f"一括更新完了: 成功 {success_count}件, 失敗 {failed_count}件")
    return success_count, failed_count

# 使用例
project_ids = ["id1", "id2", "id3"]
batch_status_update(project_ids, "archived")
```

### キャッシュ活用

```python
class CachedProjectManager:
    """キャッシュ機能付きプロジェクトマネージャー"""
    
    def __init__(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        self._project_cache = {}
        self._list_cache = None
        self._cache_timestamp = None
    
    def get_project(self, project_id: str):
        # キャッシュ確認
        if project_id in self._project_cache:
            return self._project_cache[project_id]
        
        # データベースから取得
        project = self.project_manager.get_project(project_id)
        
        # キャッシュに保存
        if project:
            self._project_cache[project_id] = project
        
        return project
    
    def clear_cache(self):
        """キャッシュクリア"""
        self._project_cache.clear()
        self._list_cache = None

# 使用例
base_manager = ProjectManager(db_manager, "projects")
cached_manager = CachedProjectManager(base_manager) 