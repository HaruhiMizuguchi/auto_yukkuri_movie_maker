#!/usr/bin/env python3
"""
APIキー設定後の確認スクリプト

有効なAPIキーが設定されているかを確認し、実際のAPI呼び出しをテストします。
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import httpx

print("🔑 APIキー設定確認")
print("=" * 50)

# 環境変数読み込み
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY が設定されていません")
    print()
    print("📝 設定手順:")
    print("1. .envファイルを開く")
    print("2. 以下の行を追加:")
    print("   GEMINI_API_KEY=your_actual_api_key_here")
    print("3. ファイルを保存")
    sys.exit(1)

print(f"✅ APIキー読み込み成功: {api_key[:20]}...")
print(f"📏 長さ: {len(api_key)} 文字")

# APIキー形式チェック
if api_key.startswith('AIza'):
    print("✅ Google API キー形式 (AIza...)")
elif len(api_key) >= 35:
    print("✅ 適切な長さ（35文字以上）")
else:
    print("⚠️  短すぎる可能性があります")
    if api_key.startswith('test_key'):
        print("❌ テスト用キーのようです。実際のAPIキーに置き換えてください")
        sys.exit(1)

print()

# 実際のAPI呼び出しテスト
async def test_gemini_apis():
    print("🧪 API呼び出しテスト")
    print("-" * 30)
    
    # プロキシ設定を無効化（simple_gemini_test.py と同様）
    for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY",
              "http_proxy","https_proxy","all_proxy"):
        os.environ.pop(k, None)
    
    # 1. LLMテスト
    print("📝 1. テキスト生成テスト")
    try:
        import google.genai as genai
        client = genai.Client(api_key=api_key)
        
        # httpx クライアントを trust_env=False に設定（simple_gemini_test.py と同様）
        new_httpx = httpx.Client(timeout=60.0, trust_env=False)
        old_httpx = client._api_client._httpx_client
        old_httpx.close()
        client._api_client._httpx_client = new_httpx
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents='こんにちは！簡潔に挨拶を返してください。'
        )
        
        print("🎉 テキスト生成成功！")
        print(f"📄 レスポンス: {response.text}")
        
    except Exception as e:
        print(f"❌ テキスト生成失敗: {e}")
        return False
    
    print()
    
    # 2. 画像生成テスト
    print("🎨 2. 画像生成テスト")
    try:
        from google.genai import types
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-preview-image-generation',
            contents='Create a simple image of a blue circle.',
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
        )
        
        # より安全なレスポンス解析
        image_found = False
        text_content = ""
        
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        # テキスト部分の処理
                        if hasattr(part, 'text') and part.text:
                            text_content = part.text
                        # 画像部分の処理
                        elif hasattr(part, 'inline_data') and part.inline_data:
                            print("🎉 画像生成成功！")
                            print(f"📊 画像データサイズ: {len(part.inline_data.data):,} bytes")
                            if hasattr(part.inline_data, 'mime_type'):
                                print(f"📷 MIME タイプ: {part.inline_data.mime_type}")
                            image_found = True
        
        if text_content:
            print(f"📝 画像説明: {text_content}")
        
        if not image_found:
            print("❌ 画像データが見つかりませんでした")
            print("📊 レスポンス構造:")
            if hasattr(response, 'candidates'):
                print(f"   候補数: {len(response.candidates) if response.candidates else 0}")
                if response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content'):
                        if hasattr(candidate.content, 'parts'):
                            print(f"   パーツ数: {len(candidate.content.parts)}")
                            for i, part in enumerate(candidate.content.parts):
                                print(f"   パーツ{i}: {type(part).__name__}")
                                if hasattr(part, 'text'):
                                    print(f"     テキスト有り: {bool(part.text)}")
                                if hasattr(part, 'inline_data'):
                                    print(f"     画像データ有り: {bool(part.inline_data)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 画像生成失敗: {e}")
        print(f"🔍 エラータイプ: {type(e).__name__}")
        return False

# テスト実行
try:
    success = asyncio.run(test_gemini_apis())
    
    if success:
        print()
        print("🎉 すべてのテストが成功しました！")
        print("✅ APIキーは正常に動作しています")
        print()
        print("🚀 本格的なテストを実行する場合:")
        print("   python scripts/test_api_integration.py")
    else:
        print()
        print("⚠️  一部のテストが失敗しました")
        print("💡 APIキーの権限設定を確認してください")
        
except Exception as e:
    print(f"❌ テスト実行エラー: {e}")
    print()
    print("💡 トラブルシューティング:")
    print("1. APIキーが正しく設定されているか確認")
    print("2. Google AI Studio で API キーが有効か確認")
    print("3. API 利用制限に達していないか確認")

print()
print("🏁 確認完了") 