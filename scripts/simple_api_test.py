#!/usr/bin/env python3
"""
シンプルなGemini APIキーテストスクリプト

.envファイルの読み込みとAPIキーの動作確認を段階的に行います。
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

print("🔍 Gemini APIキー動作確認テスト")
print("=" * 50)

# 1. .envファイルの確認
print("📁 Step 1: .envファイルの確認")
env_path = Path(".env")
if env_path.exists():
    print(f"✅ .envファイルが存在: {env_path.absolute()}")
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
        gemini_lines = [line for line in lines if 'GEMINI_API_KEY' in line and not line.strip().startswith('#')]
        if gemini_lines:
            print(f"✅ GEMINI_API_KEY の設定行が見つかりました:")
            for line in gemini_lines:
                print(f"   {line[:50]}...")
        else:
            print("❌ GEMINI_API_KEY の設定が見つかりません")
else:
    print(f"❌ .envファイルが見つかりません: {env_path.absolute()}")

print()

# 2. dotenvによる環境変数読み込み
print("📋 Step 2: 環境変数の読み込み")
load_dotenv()
print("✅ dotenv.load_dotenv() 実行完了")

# 3. 環境変数の確認
print("🔑 Step 3: 環境変数の確認")
gemini_key = os.getenv("GEMINI_API_KEY")
google_key = os.getenv("GOOGLE_API_KEY")

print(f"GEMINI_API_KEY: {'設定済み' if gemini_key else '未設定'}")
if gemini_key:
    print(f"  値: {gemini_key[:20]}... (長さ: {len(gemini_key)})")

print(f"GOOGLE_API_KEY: {'設定済み' if google_key else '未設定'}")
if google_key:
    print(f"  値: {google_key[:20]}... (長さ: {len(google_key)})")

# 使用するAPIキー
api_key = gemini_key or google_key
if not api_key:
    print("❌ APIキーが見つかりません")
    sys.exit(1)

print(f"✅ 使用するAPIキー: {api_key[:20]}... (長さ: {len(api_key)})")
print()

# 4. Google Gen AI SDK による直接テスト
print("🧪 Step 4: Google Gen AI SDK 直接テスト")
try:
    import google.genai as genai
    print("✅ google.genai インポート成功")
    
    # クライアント設定
    print("🔧 クライアント設定中...")
    client = genai.Client(api_key=api_key)
    print("✅ genai.Client 作成成功")
    
    # 最小限のテキスト生成テスト
    print("📝 簡単なテキスト生成テスト実行中...")
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents='Hello! Please respond with exactly: "API test successful"'
    )
    
    print("🎉 テキスト生成成功!")
    print(f"📄 レスポンス: {response.text}")
    print()
    
except Exception as e:
    print(f"❌ Google Gen AI SDK テスト失敗: {e}")
    print()

# 5. 我々のLLMクライアントテスト
print("🤖 Step 5: 自作LLMクライアントテスト")
try:
    # プロジェクトルートをパスに追加
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from src.api.llm_client import GeminiLLMClient, GeminiRequest
    print("✅ 自作LLMクライアント インポート成功")
    
    import asyncio
    
    async def test_our_client():
        async with GeminiLLMClient(api_key=api_key) as client:
            request = GeminiRequest(
                prompt="Hello! Please respond with exactly: 'Custom client test successful'",
                max_output_tokens=50,
                temperature=0.1
            )
            
            response = await client.generate_text(request)
            print("🎉 自作クライアントテスト成功!")
            print(f"📄 レスポンス: {response.text}")
            print(f"🔢 トークン数: {response.token_count}")
    
    asyncio.run(test_our_client())
    print()
    
except Exception as e:
    print(f"❌ 自作LLMクライアント テスト失敗: {e}")
    import traceback
    traceback.print_exc()
    print()

# 6. 画像生成テスト
print("🎨 Step 6: Gemini 2.0 画像生成テスト (SDK 直接呼び出し)")
try:
    import base64
    from io import BytesIO
    from PIL import Image
    from google.genai import types

    print("🔧 画像生成リクエストを送信中...")
    client_img = genai.Client(api_key=api_key)

    response = client_img.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents="Generate an image of a simple red circle on a white background.",
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )

    saved = False
    for idx, part in enumerate(response.candidates[0].content.parts):
        if part.text is not None:
            print(f"📝 モデルメッセージ: {part.text}")
        elif part.inline_data is not None:
            # 画像データ (base64) をデコードして保存
            image_bytes = part.inline_data.data
            try:
                img = Image.open(BytesIO(image_bytes))
            except Exception:
                # inline_data.data が base64 の場合は decode
                img = Image.open(BytesIO(base64.b64decode(image_bytes)))

            out_path = Path("generated_image.png")
            img.save(out_path)
            print(f"🎉 画像生成テスト成功! -> {out_path.resolve()}")
            print(f"📏 画像サイズ: {img.size}")
            saved = True

    if not saved:
        print("❌ 画像パートが見つかりませんでした")

except Exception as e:
    print(f"❌ 画像生成テスト失敗: {e}")
    import traceback
    traceback.print_exc()

print()
print("🏁 テスト完了!")
print("=" * 50) 