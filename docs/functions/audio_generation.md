# 音声生成ユーティリティ (Audio Generation Utils)

## 概要

`audio_generation.py`は、AivisSpeechClientの複雑さを隠し、シンプルで使いやすい高レベル関数を提供します。内部の TTS API クライアントの設定や依存関係を意識することなく、簡単に音声生成ができます。

## 主要機能

### 基本的な音声生成

#### generate_speech()

最もシンプルな音声生成関数です。

```python
import asyncio
from src.utils import generate_speech

async def basic_example():
    # 最もシンプルな使用例
    audio_file = await generate_speech("こんにちは！")
    print(f"音声ファイル: {audio_file}")
    
    # 魔理沙の声でゆっくり
    audio_file = await generate_speech(
        "魔法は力だぜ！", 
        speaker="marisa", 
        speed=0.8
    )
    
    # ファイル保存先を指定
    audio_file = await generate_speech(
        "テスト", 
        output_path="test.wav"
    )

asyncio.run(basic_example())
```

**パラメータ：**
- `text`: 読み上げるテキスト
- `speaker`: 話者名またはID（"reimu", "marisa", 0, 1など）
- `speed`: 読み上げ速度（0.5〜2.0）
- `output_path`: 出力ファイルパス（省略時は一時ファイル）
- `server_url`: TTS サーバーURL（デフォルト: "http://127.0.0.1:10101"）

**戻り値：**
- `str`: 生成された音声ファイルのパス

### ゆっくり動画対応

#### generate_yukkuri_dialogue()

ゆっくり動画用の対話音声を生成します。

```python
import asyncio
from src.utils import generate_yukkuri_dialogue

async def dialogue_example():
    dialogue = [
        {"speaker": "reimu", "text": "こんにちは、魔理沙"},
        {"speaker": "marisa", "text": "よう、霊夢！元気だぜ"},
        {"speaker": "reimu", "text": "今日は何をするの？"},
        {"speaker": "marisa", "text": "新しい魔法の実験をするんだ！"}
    ]
    
    audio_files = await generate_yukkuri_dialogue(
        dialogue, 
        output_dir="dialogue_audio"
    )
    
    for i, file in enumerate(audio_files):
        print(f"パート{i+1}: {file}")

asyncio.run(dialogue_example())
```

#### generate_script_audio()

スクリプトデータから音声を一括生成します。

```python
import asyncio
from src.utils import generate_yukkuri_script, generate_script_audio

async def script_audio_example():
    # スクリプト生成
    script = await generate_yukkuri_script("Python入門", duration_minutes=5)
    
    # 音声生成
    audio_result = await generate_script_audio(
        script, 
        output_dir="script_audio",
        voice_settings={
            "reimu": {"speed": 1.0, "pitch": 0.0},
            "marisa": {"speed": 1.1, "pitch": 0.1}
        }
    )
    
    print(f"生成ファイル数: {audio_result['total_files']}")
    print(f"総再生時間: {audio_result['total_duration']:.1f}秒")
    
    # セクション別音声ファイル
    for section_title, files in audio_result['section_audios'].items():
        print(f"\n{section_title}:")
        for file_info in files:
            print(f"  {file_info['speaker']}: {file_info['path']}")

asyncio.run(script_audio_example())
```

### 一括処理

#### batch_generate_audio()

複数のテキストから音声を一括生成します。

```python
import asyncio
from src.utils import batch_generate_audio

async def batch_example():
    texts = [
        "おはよう",
        "こんにちは", 
        "こんばんは",
        "また明日！"
    ]
    
    audio_files = await batch_generate_audio(
        texts, 
        speaker="marisa",
        output_dir="greetings",
        filename_prefix="greeting"
    )
    
    for text, file in zip(texts, audio_files):
        print(f"'{text}' -> {file}")

asyncio.run(batch_example())
```

## 話者管理

### get_available_speakers()

利用可能な話者の一覧を取得します。

```python
from src.utils import get_available_speakers

def speaker_example():
    speakers = get_available_speakers()
    print("利用可能な話者:")
    for name, speaker_id in speakers.items():
        print(f"  {name}: {speaker_id}")

speaker_example()
```

**利用可能な話者：**
- `reimu` (0): 霊夢（デフォルト）
- `marisa` (1): 魔理沙
- `yukari` (2): 紫
- `alice` (3): アリス
- `patchouli` (4): パチュリー

### test_tts_connection()

TTS サーバーとの接続をテストします。

```python
import asyncio
from src.utils import test_tts_connection

async def connection_test():
    is_connected = await test_tts_connection()
    if is_connected:
        print("✅ TTS サーバーに接続できました")
    else:
        print("❌ TTS サーバーに接続できません")

asyncio.run(connection_test())
```

## エラーハンドリング

### safe_generate_speech()

エラーハンドリング付きの安全な音声生成を行います。

```python
import asyncio
from src.utils import safe_generate_speech

async def safe_example():
    # リトライ機能付き
    audio_file = await safe_generate_speech(
        "テスト音声です",
        speaker="reimu",
        max_retries=3,
        fallback_text="音声生成に失敗しました。"
    )
    
    if audio_file:
        print(f"音声生成成功: {audio_file}")
    else:
        print("音声生成に失敗しました")

asyncio.run(safe_example())
```

## 実用的な使用例

### ゆっくり動画の音声生成フロー

```python
import asyncio
from src.utils import (
    generate_yukkuri_script,
    generate_script_audio,
    test_tts_connection
)

async def complete_audio_workflow():
    """完全な音声生成ワークフロー"""
    
    # 1. TTS接続確認
    if not await test_tts_connection():
        print("❌ TTS サーバーが利用できません")
        return
    
    # 2. スクリプト生成
    script = await generate_yukkuri_script(
        "Python プログラミング入門", 
        duration_minutes=3
    )
    print(f"📝 スクリプト生成完了: {script['title']}")
    
    # 3. 音声生成
    audio_result = await generate_script_audio(
        script,
        output_dir="video_audio",
        voice_settings={
            "reimu": {"speed": 0.9},  # 霊夢は少しゆっくり
            "marisa": {"speed": 1.1}  # 魔理沙は少し速め
        }
    )
    
    print(f"🎵 音声生成完了:")
    print(f"  - ファイル数: {audio_result['total_files']}")
    print(f"  - 総時間: {audio_result['total_duration']:.1f}秒")
    print(f"  - 出力先: {audio_result['output_directory']}")
    
    # 4. 結果の詳細表示
    for section_title, files in audio_result['section_audios'].items():
        print(f"\n📁 {section_title}:")
        for file_info in files:
            speaker = file_info['speaker']
            duration = file_info['estimated_duration']
            print(f"   {speaker}: {duration:.1f}秒")

asyncio.run(complete_audio_workflow())
```

### カスタム音声設定

```python
import asyncio
from src.utils import generate_speech

async def custom_voice_example():
    """カスタム音声設定の例"""
    
    # 各キャラクターの特徴的な設定
    voice_configs = {
        "reimu": {"speed": 1.0, "description": "落ち着いた話し方"},
        "marisa": {"speed": 1.2, "description": "元気で快活"},
        "yukari": {"speed": 0.8, "description": "ゆったりと神秘的"},
        "alice": {"speed": 1.1, "description": "丁寧で上品"},
        "patchouli": {"speed": 0.9, "description": "知的で静か"}
    }
    
    text = "今日は良い天気ですね"
    
    for speaker, config in voice_configs.items():
        audio_file = await generate_speech(
            text,
            speaker=speaker,
            speed=config["speed"],
            output_path=f"voice_test_{speaker}.wav"
        )
        print(f"{speaker} ({config['description']}): {audio_file}")

asyncio.run(custom_voice_example())
```

### 長文の分割音声生成

```python
import asyncio
from src.utils import batch_generate_audio

async def long_text_example():
    """長文を分割して音声生成"""
    
    long_text = """
    Pythonは、プログラミング初心者にも優しい言語です。
    シンプルな文法で、読みやすく書きやすいコードが特徴です。
    データサイエンスやWebアプリケーション開発など、
    幅広い分野で活用されています。
    """
    
    # 文章を分割
    sentences = [s.strip() for s in long_text.split('。') if s.strip()]
    
    # 各文を音声化
    audio_files = await batch_generate_audio(
        sentences,
        speaker="reimu",
        output_dir="python_intro",
        filename_prefix="sentence",
        speed=0.9
    )
    
    print("📝 分割音声生成完了:")
    for i, (sentence, file) in enumerate(zip(sentences, audio_files), 1):
        print(f"  {i}. {sentence[:30]}... -> {file}")

asyncio.run(long_text_example())
```

## パフォーマンス最適化

### 一時ファイル管理

```python
import asyncio
import tempfile
import os
from src.utils import generate_speech

async def temp_file_management():
    """一時ファイルの適切な管理"""
    
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"一時ディレクトリ: {temp_dir}")
        
        # 複数音声を生成
        tasks = []
        for i in range(5):
            output_path = os.path.join(temp_dir, f"temp_audio_{i}.wav")
            task = generate_speech(
                f"これは{i+1}番目のテストです",
                output_path=output_path
            )
            tasks.append(task)
        
        # 並列実行
        audio_files = await asyncio.gather(*tasks)
        
        for i, file in enumerate(audio_files):
            print(f"音声{i+1}: {file}")
    
    print("一時ディレクトリが自動削除されました")

asyncio.run(temp_file_management())
```

### 並列音声生成

```python
import asyncio
from src.utils import generate_speech

async def parallel_generation():
    """並列音声生成でパフォーマンス向上"""
    
    texts_and_speakers = [
        ("こんにちは", "reimu"),
        ("元気だぜ", "marisa"),
        ("ご機嫌よう", "yukari"),
        ("お疲れ様", "alice"),
        ("こんばんは", "patchouli")
    ]
    
    # 並列実行用のタスクを作成
    tasks = [
        generate_speech(
            text, 
            speaker=speaker, 
            output_path=f"parallel_{speaker}.wav"
        )
        for text, speaker in texts_and_speakers
    ]
    
    # 並列実行
    start_time = asyncio.get_event_loop().time()
    audio_files = await asyncio.gather(*tasks)
    end_time = asyncio.get_event_loop().time()
    
    print(f"⚡ 並列生成完了 ({end_time - start_time:.2f}秒)")
    for (text, speaker), file in zip(texts_and_speakers, audio_files):
        print(f"  {speaker}: '{text}' -> {file}")

asyncio.run(parallel_generation())
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. TTS サーバー接続エラー

```python
import asyncio
from src.utils import test_tts_connection, generate_speech

async def connection_troubleshooting():
    # 接続テスト
    if not await test_tts_connection():
        print("TTS サーバーに接続できません")
        print("解決方法:")
        print("1. AIVIS Speech が起動しているか確認")
        print("2. サーバーURL (http://127.0.0.1:10101) が正しいか確認")
        print("3. ファイアウォールの設定を確認")
        return
    
    print("✅ TTS サーバー接続OK")
```

#### 2. 音声ファイル保存エラー

```python
import asyncio
import os
from pathlib import Path
from src.utils import generate_speech

async def file_save_troubleshooting():
    output_dir = Path("audio_output")
    
    # ディレクトリが存在しない場合は作成
    output_dir.mkdir(exist_ok=True)
    
    # 権限確認
    if not os.access(output_dir, os.W_OK):
        print(f"❌ ディレクトリに書き込み権限がありません: {output_dir}")
        return
    
    try:
        audio_file = await generate_speech(
            "テスト音声",
            output_path=output_dir / "test.wav"
        )
        print(f"✅ 音声保存成功: {audio_file}")
    except Exception as e:
        print(f"❌ 音声保存エラー: {e}")
```

#### 3. 文字エンコーディング問題

```python
import asyncio
from src.utils import generate_speech

async def encoding_troubleshooting():
    # 特殊文字を含むテキスト
    texts = [
        "こんにちは！",  # 日本語 + 記号
        "Hello World",   # 英語
        "数字123と記号！？", # 混在文字
        "改行\n文字テスト"   # 制御文字
    ]
    
    for i, text in enumerate(texts):
        try:
            # 改行文字等をクリーンアップ
            clean_text = text.replace('\n', ' ').strip()
            audio_file = await generate_speech(
                clean_text,
                output_path=f"encoding_test_{i}.wav"
            )
            print(f"✅ '{clean_text}' -> {audio_file}")
        except Exception as e:
            print(f"❌ '{text}' でエラー: {e}")
```

## 設定のカスタマイズ

### デフォルト設定の変更

```python
# デフォルト話者の変更
from src.utils.audio_generation import DEFAULT_SPEAKERS

# カスタム話者設定
CUSTOM_SPEAKERS = {
    "narrator": 0,    # ナレーター（霊夢）
    "teacher": 1,     # 先生（魔理沙）
    "student": 2,     # 生徒（紫）
    "assistant": 3    # アシスタント（アリス）
}

# デフォルト設定を上書き（実際のプロダクションでは推奨しません）
DEFAULT_SPEAKERS.update(CUSTOM_SPEAKERS)
```

### サーバー設定のカスタマイズ

```python
import asyncio
from src.utils import generate_speech

async def custom_server_example():
    # カスタムサーバーURL
    custom_server_url = "http://192.168.1.100:10101"
    
    audio_file = await generate_speech(
        "カスタムサーバーテスト",
        server_url=custom_server_url
    )
    print(f"カスタムサーバー音声: {audio_file}")
```

この音声生成ユーティリティを使用することで、複雑な TTS API の設定を意識することなく、簡単にゆっくり動画用の音声を生成できます。 