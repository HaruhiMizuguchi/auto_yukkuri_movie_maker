# AivisSpeech API 使用方法

## 概要
AivisSpeechを使用してテキストから音声を生成する最小限のコード例です。

## 前提条件
- AivisSpeechサーバーが `http://127.0.0.1:10101` で起動している
- 必要なPythonパッケージ: `requests`

## 基本的な使用方法

### 1. 必要なライブラリ
```python
import requests
import json
```

### 2. 最小限のコード例
```python
def generate_voice(text, output_file="voice.wav"):
    """
    テキストから音声ファイルを生成する
    
    Args:
        text (str): 読み上げるテキスト
        output_file (str): 出力ファイル名
    
    Returns:
        bool: 成功時True、失敗時False
    """
    BASE_URL = "http://127.0.0.1:10101"
    
    try:
        # 1. 利用可能なスピーカーを取得
        res = requests.get(f"{BASE_URL}/speakers", timeout=10)
        res.raise_for_status()
        speakers = res.json()
        
        # 最初のスタイルIDを使用（例: 888753760）
        style_id = speakers[0]["styles"][0]["id"]
        
        # 2. audio_query でクエリパラメータを取得
        aq_res = requests.post(
            f"{BASE_URL}/audio_query",
            params={"speaker": style_id, "text": text},
            timeout=30
        )
        aq_res.raise_for_status()
        query_json = aq_res.json()
        
        # 3. synthesis で音声を生成
        syn_res = requests.post(
            f"{BASE_URL}/synthesis",
            params={"speaker": style_id},
            json=query_json,
            timeout=60
        )
        syn_res.raise_for_status()
        
        # 4. 音声ファイルとして保存
        with open(output_file, "wb") as f:
            f.write(syn_res.content)
        
        return True
        
    except Exception as e:
        print(f"音声生成エラー: {e}")
        return False

# 使用例
if __name__ == "__main__":
    success = generate_voice("こんにちは、世界！")
    if success:
        print("音声生成完了: voice.wav")
    else:
        print("音声生成失敗")

# 高レベルユーティリティ関数の使用例
# より簡単に音声生成を行う場合は、以下のように使用できます：
"""
import asyncio
from src.utils.audio_generation import generate_speech

async def simple_example():
    # 最もシンプルな使用例
    audio_file = await generate_speech("こんにちは！")
    print(f"音声ファイル: {audio_file}")

# 実行
asyncio.run(simple_example())
"""
```

## 重要なポイント

### JSONデータの送信
- `requests.post()` で JSON データを送信する際は `json` パラメーターを使用
- `data=json.dumps()` ではなく `json=query_json` を使用することで適切なヘッダーが自動設定される

### エラーハンドリング
- ネットワークエラー、サーバーエラーを適切にキャッチ
- タイムアウト設定を必ず指定

### スピーカー選択
- `/speakers` エンドポイントで利用可能なスピーカーとスタイルを確認
- `style_id` を指定して音声の特徴を選択

## API エンドポイント
- `GET /speakers`: 利用可能なスピーカー一覧
- `POST /audio_query`: 音声クエリパラメータ生成
- `POST /synthesis`: 音声合成実行 