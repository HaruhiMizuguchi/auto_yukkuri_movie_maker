# Gemini API 使用ガイド

## 概要

このドキュメントは、動作実績のある `simple_gemini_test.py` を参考に、Google Gemini API の正しい使用方法を説明します。

## 前提条件

### 必要なライブラリ

```bash
pip install google-genai>=1.20 pillow httpx python-dotenv
```

### 環境変数設定

`.env` ファイルに以下を設定：

```
GEMINI_API_KEY=your_api_key_here
```

または `GOOGLE_API_KEY` でも可能。

## 基本的な使用パターン

### 1. 初期設定（重要）

```python
import os
from google import genai
import httpx

# HTTPプロキシ設定を無効化（重要）
for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY",
          "http_proxy","https_proxy","all_proxy"):
    os.environ.pop(k, None)

# API キー読込
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY が見つかりません")

# Client 生成
client = genai.Client(api_key=API_KEY)

# 内部 httpx.Client を trust_env=False のものに入れ替え（重要）
new_httpx = httpx.Client(timeout=60.0, trust_env=False)
old_httpx = client._api_client._httpx_client
old_httpx.close()
client._api_client._httpx_client = new_httpx
```

### 2. テキスト生成

```python
# テキスト生成
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="夏の東京を詠む俳句を一句、季語を入れて。"
)

text_result = response.text.strip()
print(f"生成されたテキスト: {text_result}")
```

### 3. 画像生成

```python
from google.genai import types
from PIL import Image
from io import BytesIO
from pathlib import Path

# 画像生成
prompt = "富士山と桜を描いた水彩風イラストを生成してください。"
response = client.models.generate_content(
    model="gemini-2.0-flash-preview-image-generation",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_modalities=["TEXT","IMAGE"]
    )
)

# レスポンス処理
for part in response.candidates[0].content.parts:
    if part.text:
        caption = part.text.strip()
        print(f"画像の説明: {caption}")
    elif part.inline_data:
        # 画像データを保存
        image = Image.open(BytesIO(part.inline_data.data))
        output_path = Path("generated_image.png")
        image.save(output_path)
        print(f"画像を {output_path.resolve()} に保存しました")
```

## 重要なポイント

### 1. プロキシ設定の無効化

```python
# これを忘れると接続エラーが発生する場合があります
for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY",
          "http_proxy","https_proxy","all_proxy"):
    os.environ.pop(k, None)
```

### 2. httpx クライアントの設定

```python
# trust_env=False を設定しないと認証エラーが発生する場合があります
new_httpx = httpx.Client(timeout=60.0, trust_env=False)
client._api_client._httpx_client = new_httpx
```

### 3. 使用可能なモデル

- **テキスト生成**: `gemini-2.0-flash`
- **画像生成**: `gemini-2.0-flash-preview-image-generation`

### 4. エラーハンドリング

```python
try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
except Exception as e:
    print(f"API呼び出しエラー: {e}")
    # 適切なエラー処理
```

## アンチパターン（避けるべき実装）

### 1. REST API の直接呼び出し

```python
# 避けるべき: aiohttp や requests での直接呼び出し
async with aiohttp.ClientSession() as session:
    async with session.post(url, headers=headers, json=data) as response:
        # この方法では認証やプロキシ問題が発生しやすい
```

### 2. プロキシ設定の無視

```python
# 避けるべき: プロキシ環境変数をそのまま残す
# 環境によっては接続エラーの原因となる
```

### 3. 古いライブラリの使用

```python
# 避けるべき: google-generativeai（非推奨）
# import google.generativeai as genai  # 古いライブラリ
```

## 実装例テンプレート

```python
#!/usr/bin/env python
"""
Gemini API 使用テンプレート
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import httpx
from PIL import Image
from io import BytesIO
from google import genai
from google.genai import types


class GeminiClient:
    """Gemini API クライアント"""
    
    def __init__(self, api_key: str):
        # プロキシ設定を無効化
        for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY",
                  "http_proxy","https_proxy","all_proxy"):
            os.environ.pop(k, None)
        
        # クライアント初期化
        self.client = genai.Client(api_key=api_key)
        
        # httpx クライアント設定
        new_httpx = httpx.Client(timeout=60.0, trust_env=False)
        old_httpx = self.client._api_client._httpx_client
        old_httpx.close()
        self.client._api_client._httpx_client = new_httpx
    
    def generate_text(self, prompt: str) -> str:
        """テキスト生成"""
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    
    def generate_image(self, prompt: str, output_path: Path = None) -> tuple[str, Path]:
        """画像生成"""
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT","IMAGE"]
            )
        )
        
        caption = ""
        image_path = None
        
        for part in response.candidates[0].content.parts:
            if part.text:
                caption = part.text.strip()
            elif part.inline_data:
                image = Image.open(BytesIO(part.inline_data.data))
                if output_path is None:
                    output_path = Path("generated_image.png")
                image.save(output_path)
                image_path = output_path
        
        return caption, image_path


# 使用例
def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY が見つかりません")
    
    client = GeminiClient(api_key)
    
    # テキスト生成
    text = client.generate_text("東京の美しい風景を説明してください。")
    print(f"生成テキスト: {text}")
    
    # 画像生成
    caption, image_path = client.generate_image("美しい東京の夜景")
    print(f"画像説明: {caption}")
    print(f"画像保存先: {image_path}")


if __name__ == "__main__":
    main()
```

## トラブルシューティング

### よくあるエラーと対処法

1. **認証エラー**: API キーの確認、環境変数の設定確認
2. **接続エラー**: プロキシ設定の無効化、trust_env=False の設定
3. **タイムアウト**: timeout 値の調整
4. **モデルエラー**: 正しいモデル名の使用確認

### デバッグ方法

```python
# API キーの確認
print(f"API Key: {api_key[:20]}..." if api_key else "未設定")

# プロキシ設定の確認
proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", 
              "http_proxy", "https_proxy", "all_proxy"]
for var in proxy_vars:
    value = os.environ.get(var)
    print(f"{var}: {value if value else '未設定'}")
``` 