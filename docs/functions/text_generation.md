# テキスト生成関数一覧

`src/utils/text_generation.py` で提供されている高レベルなテキスト生成関数の使い方をまとめています。

## 📋 利用可能な関数

### 🔧 基本関数

#### `generate_text(prompt, temperature=0.7, max_tokens=1024, model="gemini-2.0-flash")`

最も基本的なテキスト生成関数です。

```python
from src.utils.text_generation import generate_text

# 基本的な使用例
text = await generate_text("こんにちはと日本語で挨拶してください")
print(text)  # → "こんにちは！"

# パラメータ調整例
creative_text = await generate_text(
    "面白い話を考えてください",
    temperature=0.9,  # 創造的に
    max_tokens=500
)
```

**パラメータ:**
- `prompt` (str): 生成指示文
- `temperature` (float): 創造性 (0.0=決定的, 1.0=創造的)
- `max_tokens` (int): 最大出力トークン数
- `model` (str): 使用モデル名

---

### 🎬 ゆっくり動画専用関数

#### `generate_yukkuri_script(theme, duration_minutes=3, speakers=None, tone="casual")`

ゆっくり動画の台本を自動生成します。

```python
from src.utils.text_generation import generate_yukkuri_script

# 基本的な台本生成
script = await generate_yukkuri_script("Python入門")

# カスタマイズ例
script = await generate_yukkuri_script(
    theme="機械学習の基礎",
    duration_minutes=5,
    speakers=["reimu", "marisa", "youmu"],
    tone="formal"
)

# 生成される構造
print(script["title"])         # → "【Python入門】初心者でもわかる基本講座"
print(script["sections"])      # → [{"section_name": "導入", "dialogue": [...]}]
```

**戻り値:**
```python
{
    "title": "動画タイトル",
    "speakers": ["reimu", "marisa"],
    "sections": [
        {
            "section_name": "導入",
            "duration_seconds": 30,
            "dialogue": [
                {"speaker": "reimu", "text": "セリフ内容"},
                {"speaker": "marisa", "text": "セリフ内容"}
            ]
        }
    ],
    "total_estimated_duration": 180
}
```

#### `generate_video_title(theme, keywords=None, target_audience="general", style="catchy")`

YouTube動画のタイトルを複数生成します。

```python
from src.utils.text_generation import generate_video_title

# 基本的なタイトル生成
titles = await generate_video_title("Python入門")

# 詳細指定
titles = await generate_video_title(
    theme="機械学習",
    keywords=["初心者", "わかりやすい", "実践"],
    target_audience="beginner",
    style="question"
)

print(titles)  # → ["初心者でもわかる！機械学習って何？", "今さら聞けない機械学習の基本", ...]
```

---

### 🔧 ユーティリティ関数

#### `generate_json_data(prompt, schema, temperature=0.7)`

構造化されたJSONデータを生成します。

```python
from src.utils.text_generation import generate_json_data

# スキーマ定義
character_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "level": {"type": "integer"},
        "skills": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["name", "level", "skills"]
}

# データ生成
character = await generate_json_data(
    "RPGゲームのキャラクターデータを生成してください",
    character_schema
)

print(character)  # → {"name": "勇者アルベルト", "level": 25, "skills": ["剣術", "回復魔法"]}
```

#### `summarize_text(text, max_length=200)`

長いテキストを要約します。

```python
from src.utils.text_generation import summarize_text

long_text = """
（長い文章）
"""

summary = await summarize_text(long_text, max_length=100)
print(summary)  # → "要約された短いテキスト"
```

#### `safe_generate_text(prompt, fallback_text="生成に失敗しました", **kwargs)`

エラー時にフォールバックテキストを返す安全な生成関数です。

```python
from src.utils.text_generation import safe_generate_text

# エラーが発生してもアプリが止まらない
text = await safe_generate_text(
    "複雑な処理",
    fallback_text="デフォルトテキスト"
)
```

---

## 🚀 実用例

### 1. ゆっくり動画の完全自動生成

```python
from src.utils.text_generation import generate_yukkuri_script, generate_video_title

async def create_yukkuri_video_content(theme):
    # 台本生成
    script = await generate_yukkuri_script(theme, duration_minutes=3)
    
    # タイトル候補生成
    titles = await generate_video_title(theme, style="catchy")
    
    return {
        "selected_title": titles[0],
        "alternative_titles": titles[1:],
        "script": script
    }

# 使用例
content = await create_yukkuri_video_content("プログラミング学習法")
```

### 2. バッチ処理でのコンテンツ生成

```python
from src.utils.text_generation import generate_text
import asyncio

async def generate_multiple_contents(themes):
    tasks = []
    for theme in themes:
        task = generate_text(f"{theme}について簡潔に説明してください")
        tasks.append(task)
    
    # 並行実行（レート制限に注意）
    results = []
    for task in tasks:
        result = await task
        results.append(result)
        await asyncio.sleep(2)  # レート制限対策
    
    return results
```

### 3. エラーハンドリングありの堅牢な処理

```python
from src.utils.text_generation import generate_yukkuri_script, safe_generate_text

async def robust_script_generation(theme):
    try:
        # メインの台本生成を試行
        script = await generate_yukkuri_script(theme)
        return script
    except Exception as e:
        # 失敗時は簡単なテキスト生成にフォールバック
        print(f"台本生成に失敗: {e}")
        
        fallback_text = await safe_generate_text(
            f"{theme}について3分程度で話す内容を考えてください",
            fallback_text=f"{theme}に関する基本的な内容です。"
        )
        
        return {
            "title": f"{theme}について",
            "content": fallback_text,
            "is_fallback": True
        }
```

---

## ⚙️ 設定

### 環境変数

`.env` ファイルに以下を設定してください：

```env
GEMINI_API_KEY=your_api_key_here
# または
GOOGLE_API_KEY=your_api_key_here
```

### インポート方法

```python
# 個別インポート（推奨）
from src.utils.text_generation import generate_text, generate_yukkuri_script

# モジュール全体インポート
import src.utils.text_generation as text_gen
text = await text_gen.generate_text("こんにちは")
```

---

## 🚨 注意事項

1. **APIキー必須**: 環境変数 `GEMINI_API_KEY` または `GOOGLE_API_KEY` の設定が必要
2. **非同期関数**: 全ての関数は `async/await` で使用
3. **レート制限**: 連続実行時は適切な間隔（2秒程度）を設ける
4. **エラーハンドリング**: 本番環境では適切な例外処理を実装

---

## 🔗 関連ファイル

- **実装**: `src/utils/text_generation.py`
- **低レベルAPI**: `src/api/llm_client.py`
- **プロジェクト設計**: `docs/flow_definition.yaml`

---

このドキュメントを参考に、シンプルで効率的なテキスト生成を実装してください！ 