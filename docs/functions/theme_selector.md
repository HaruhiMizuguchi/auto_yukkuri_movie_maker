# テーマ選定機能 (Theme Selector)

## 概要

`theme_selector.py`は、ゆっくり動画のテーマを自動選定する機能を提供します。AIを使用してユーザーの好みに基づいたテーマ候補を生成し、最適なテーマを選択します。

## 主要クラス

### ThemeSelector

メインのテーマ選定クラスです。

```python
from src.modules import ThemeSelector, DatabaseDataAccess, GeminiThemeLLM
from src.core import ProjectRepository, ConfigManager
from src.api import GeminiLLMClient

# 依存オブジェクトの初期化
project_repository = ProjectRepository(db_manager)
config_manager = ConfigManager()
llm_client = GeminiLLMClient(api_key="your_api_key")

# データアクセスとLLMインターフェースの設定
data_access = DatabaseDataAccess(project_repository, config_manager)
llm_interface = GeminiThemeLLM(llm_client)

# テーマ選定器の初期化
theme_selector = ThemeSelector(data_access, llm_interface)
```

### 使用方法

#### 1. ユーザー設定の定義

```python
from src.modules import UserPreferences

user_preferences = UserPreferences(
    genre_history=["プログラミング", "科学"],
    preferred_genres=["教育", "技術"],
    excluded_genres=["ゲーム", "エンターテインメント"],
    target_audience="プログラマー初心者",
    content_style="分かりやすい"
)
```

#### 2. テーマ選定の実行

```python
from src.modules import ThemeSelectionInput

# 入力データの準備
input_data = ThemeSelectionInput(
    project_id="your-project-id",
    user_preferences=user_preferences,
    llm_config={"model": "gemini-2.0-flash"},
    max_candidates=10
)

# テーマ選定の実行
result = theme_selector.select_theme(input_data)

# 結果の取得
selected_theme = result.selected_theme
print(f"選択されたテーマ: {selected_theme.theme}")
print(f"カテゴリ: {selected_theme.category}")
print(f"目標時間: {selected_theme.target_length_minutes}分")
```

#### 3. 結果の詳細確認

```python
# 候補テーマ一覧
for i, candidate in enumerate(result.candidates):
    print(f"{i+1}. {candidate.theme}")
    print(f"   スコア: {candidate.total_score:.1f}")
    print(f"   説明: {candidate.description}")
    print(f"   魅力ポイント: {', '.join(candidate.appeal_points)}")
    print()

# メタデータ
metadata = result.selection_metadata
print(f"生成方法: {metadata['generation_method']}")
print(f"候補数: {metadata['candidates_count']}")
```

## データクラス

### UserPreferences

ユーザーの設定情報を格納するデータクラスです。

```python
@dataclass
class UserPreferences:
    genre_history: List[str]        # 過去のジャンル履歴
    preferred_genres: List[str]     # 好みのジャンル
    excluded_genres: List[str]      # 除外ジャンル
    target_audience: str            # ターゲット層
    content_style: str              # コンテンツスタイル
```

### ThemeCandidate

テーマ候補の情報を格納するデータクラスです。

```python
@dataclass
class ThemeCandidate:
    theme: str                      # テーマ名
    category: str                   # カテゴリ
    target_length_minutes: int      # 目標時間（分）
    description: str                # 詳細説明
    appeal_points: List[str]        # 魅力ポイント
    difficulty_score: float         # 難易度スコア (1.0-10.0)
    entertainment_score: float      # エンターテインメント性 (1.0-10.0)
    trend_score: float             # トレンド性 (1.0-10.0)
    total_score: float             # 総合スコア
```

### SelectedTheme

選択されたテーマの情報を格納するデータクラスです。

```python
@dataclass
class SelectedTheme:
    theme: str                      # テーマ名
    category: str                   # カテゴリ
    target_length_minutes: int      # 目標時間（分）
    description: str                # 詳細説明
    selection_reason: str           # 選択理由
    generation_timestamp: datetime  # 生成日時
```

## 実際の使用例

### 基本的な使用例

```python
import asyncio
from src.modules import (
    ThemeSelector, DatabaseDataAccess, GeminiThemeLLM,
    UserPreferences, ThemeSelectionInput
)
from src.core import DatabaseManager, ProjectRepository, ConfigManager
from src.api import GeminiLLMClient

async def select_theme_example():
    # データベース・設定の初期化
    db_manager = DatabaseManager("data/yukkuri_tool.db")
    project_repository = ProjectRepository(db_manager)
    config_manager = ConfigManager()
    
    # LLMクライアントの初期化
    async with GeminiLLMClient(api_key="your_api_key") as llm_client:
        # テーマ選定器の設定
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiThemeLLM(llm_client)
        theme_selector = ThemeSelector(data_access, llm_interface)
        
        # ユーザー設定
        preferences = UserPreferences(
            genre_history=["Python", "Web開発"],
            preferred_genres=["プログラミング", "技術解説"],
            excluded_genres=["ゲーム実況"],
            target_audience="プログラミング初心者",
            content_style="実践的で分かりやすい"
        )
        
        # テーマ選定の実行
        input_data = ThemeSelectionInput(
            project_id="test-project-001",
            user_preferences=preferences,
            llm_config={"temperature": 0.7},
            max_candidates=5
        )
        
        result = theme_selector.select_theme(input_data)
        
        print(f"✅ 選択されたテーマ: {result.selected_theme.theme}")
        print(f"📁 カテゴリ: {result.selected_theme.category}")
        print(f"⏱️ 目標時間: {result.selected_theme.target_length_minutes}分")
        print(f"📝 説明: {result.selected_theme.description}")
        
        return result

# 実行
result = asyncio.run(select_theme_example())
```

### カスタムデータアクセスの実装

```python
from src.modules import DataAccessInterface, UserPreferences, ThemeSelectionOutput
from typing import List

class CustomDataAccess(DataAccessInterface):
    """カスタムデータアクセス実装"""
    
    def __init__(self, custom_db):
        self.custom_db = custom_db
    
    def get_user_preferences(self, project_id: str) -> UserPreferences:
        # カスタムデータベースから設定を取得
        settings = self.custom_db.get_user_settings(project_id)
        return UserPreferences(
            genre_history=settings.get("history", []),
            preferred_genres=settings.get("preferred", ["教育"]),
            excluded_genres=settings.get("excluded", []),
            target_audience=settings.get("audience", "一般"),
            content_style=settings.get("style", "親しみやすい")
        )
    
    def save_theme_selection_result(self, project_id: str, output: ThemeSelectionOutput) -> None:
        # カスタムデータベースに保存
        self.custom_db.save_theme_result(project_id, output)
    
    def save_theme_candidates_file(self, project_id: str, candidates: List[ThemeCandidate]) -> str:
        # カスタムファイル保存処理
        return self.custom_db.save_candidates(project_id, candidates)

# 使用例
custom_data_access = CustomDataAccess(my_custom_db)
theme_selector = ThemeSelector(custom_data_access, llm_interface)
```

## エラーハンドリング

```python
try:
    result = theme_selector.select_theme(input_data)
except ValueError as e:
    print(f"入力データエラー: {e}")
except Exception as e:
    print(f"テーマ選定エラー: {e}")
    # フォールバック処理
    fallback_theme = SelectedTheme(
        theme="デフォルトテーマ",
        category="教育",
        target_length_minutes=5,
        description="システムが選択したデフォルトテーマ",
        selection_reason="エラー発生時のフォールバック",
        generation_timestamp=datetime.now()
    )
```

## 設定のカスタマイズ

### LLM設定の調整

```python
llm_config = {
    "model": "gemini-2.0-flash",
    "temperature": 0.8,          # 創造性を高める
    "max_tokens": 2048,          # 詳細な説明を生成
    "top_p": 0.9
}

input_data = ThemeSelectionInput(
    project_id=project_id,
    user_preferences=preferences,
    llm_config=llm_config,
    max_candidates=15            # より多くの候補を生成
)
```

### ユーザー設定の詳細化

```python
advanced_preferences = UserPreferences(
    genre_history=["AI/ML", "データサイエンス", "Python"],
    preferred_genres=["技術解説", "チュートリアル", "ライブラリ紹介"],
    excluded_genres=["ゲーム", "雑談", "React"],
    target_audience="中級プログラマー",
    content_style="実践的で詳細な解説"
)
```

## トラブルシューティング

### よくある問題

1. **LLM API接続エラー**
   ```python
   # API キーの確認
   assert api_key is not None, "API キーが設定されていません"
   
   # ネットワーク接続の確認
   try:
       async with GeminiLLMClient(api_key=api_key) as client:
           # 接続テスト
           pass
   except Exception as e:
       print(f"API接続エラー: {e}")
   ```

2. **データベース接続エラー**
   ```python
   # データベースファイルの存在確認
   db_path = "data/yukkuri_tool.db"
   if not os.path.exists(db_path):
       print(f"データベースファイルが見つかりません: {db_path}")
   ```

3. **テーマ生成失敗**
   ```python
   # フォールバック候補の用意
   fallback_candidates = [
       ThemeCandidate(
           theme="プログラミング基礎",
           category="教育",
           target_length_minutes=5,
           description="プログラミングの基本概念",
           appeal_points=["初心者向け", "実用的"],
           difficulty_score=3.0,
           entertainment_score=6.0,
           trend_score=7.0,
           total_score=5.3
       )
   ]
   ```

## パフォーマンス最適化

### バッチ処理

```python
# 複数プロジェクトの一括処理
async def batch_theme_selection(project_ids: List[str]):
    results = []
    for project_id in project_ids:
        try:
            result = theme_selector.select_theme(
                ThemeSelectionInput(project_id=project_id, ...)
            )
            results.append(result)
        except Exception as e:
            print(f"プロジェクト {project_id} でエラー: {e}")
    return results
```

### キャッシュ活用

```python
# テーマ候補のキャッシュ
cache = {}

def cached_theme_selection(preferences_key: str, input_data: ThemeSelectionInput):
    if preferences_key in cache:
        print("キャッシュからテーマ候補を取得")
        return cache[preferences_key]
    
    result = theme_selector.select_theme(input_data)
    cache[preferences_key] = result
    return result
``` 