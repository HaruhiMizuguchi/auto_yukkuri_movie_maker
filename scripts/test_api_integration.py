#!/usr/bin/env python3
"""
実際のAPI動作確認用統合テストスクリプト

このスクリプトは以下のAPIクライアントの実際の動作を確認します：
1. Gemini LLM API (テキスト生成)
2. AIVIS Speech TTS API (音声生成)  
3. Gemini 2.0 Flash Preview Image Generation (画像生成)

.env ファイルから環境変数を読み込み、実際のAPIキーを使用してテストを実行します。
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
import logging
import traceback
from dotenv import load_dotenv

# .env ファイルを読み込み
load_dotenv()

print("🚀 外部API統合テスト開始")
print("📁 .env ファイルから環境変数を読み込み済み")

try:
    # プロジェクトルートをパスに追加
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    print(f"プロジェクトパス追加: {project_root}")

    from src.api.llm_client import GeminiLLMClient, GeminiRequest
    from src.api.tts_client import AivisSpeechClient, TTSRequest
    from src.api.image_client import ImageGenerationClient, ImageRequest

    print("✅ 全モジュールのインポート成功")

except Exception as e:
    print(f"❌ インポートエラー: {e}")
    traceback.print_exc()
    sys.exit(1)

# ログ設定
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_gemini_llm():
    """Gemini LLM API の動作確認"""
    print("\n" + "="*60)
    print("🤖 Gemini LLM API テスト開始")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません")
        print("💡 .env ファイルに以下の形式で設定してください:")
        print("   GEMINI_API_KEY=your_actual_api_key_here")
        return False
    
    print(f"✅ API Key確認: {api_key[:20]}..." if len(api_key) > 20 else "短いAPIキー")
    
    try:
        async with GeminiLLMClient(api_key=api_key) as client:
            request = GeminiRequest(
                prompt="こんにちは！ゆっくり動画を作るためのAIアシスタントです。簡潔に自己紹介してください。",
                max_output_tokens=150,
                temperature=0.7
            )
            
            print(f"📝 リクエスト送信中...")
            print(f"   プロンプト: {request.prompt}")
            
            response = await client.generate_text(request)
            
            print(f"🎉 LLM生成成功!")
            print(f"📄 レスポンス: {response.text}")
            print(f"🔢 生成トークン数: {response.token_count}")
            print(f"🔢 プロンプトトークン数: {response.prompt_token_count}")
            print(f"🏁 終了理由: {response.finish_reason}")
            
            return True
            
    except Exception as e:
        print(f"❌ LLM生成失敗: {e}")
        if "API_KEY_INVALID" in str(e):
            print("💡 APIキーが無効です。正しいGemini APIキーを設定してください。")
        traceback.print_exc()
        return False


async def test_aivis_speech():
    """AIVIS Speech TTS API の動作確認"""
    print("\n" + "="*60)
    print("🎵 AIVIS Speech TTS API テスト開始")
    print("="*60)
    
    try:
        async with AivisSpeechClient() as client:
            print("🔍 サーバー接続確認中...")
            
            # サーバーが起動しているかチェック
            available_speakers = await client.get_speakers()
            if not available_speakers:
                print("❌ AIVIS Speechサーバーが起動していないか、スピーカーが利用できません")
                print("💡 AIVIS Speechサーバーを http://127.0.0.1:10101 で起動してください")
                return False
            
            print(f"✅ サーバー接続成功！利用可能なスピーカー数: {len(available_speakers)}")
            
            # 最初のスピーカーを使用してテスト
            speaker_data = available_speakers[0]
            style_id = speaker_data["styles"][0]["id"]
            
            print(f"🎭 使用スピーカー: {speaker_data['name']}")
            print(f"🎨 使用スタイル: {speaker_data['styles'][0]['name']} (ID: {style_id})")
            
            request = TTSRequest(
                text="こんにちは！ゆっくり動画自動生成ツールのテストです。音声合成が正常に動作しています。",
                speaker_id=style_id
            )
            
            print(f"🎤 音声生成中...")
            print(f"   テキスト: {request.text}")
            
            response = await client.generate_audio(request)
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(response.audio_data)
                temp_path = tmp_file.name
            
            print(f"🎉 TTS生成成功!")
            print(f"📁 音声ファイル: {temp_path}")
            print(f"⏱️  音声長: {response.duration_seconds:.2f}秒")
            print(f"📊 ファイルサイズ: {len(response.audio_data):,} bytes")
            print(f"🔊 サンプルレート: {response.sample_rate} Hz")
            print(f"🏷️  タイムスタンプ数: {len(response.timestamps)}")
            
            # ファイルを削除
            os.unlink(temp_path)
            print(f"🗑️  一時ファイルを削除しました")
            
            return True
            
    except Exception as e:
        print(f"❌ TTS生成失敗: {e}")
        if "Connection" in str(e) or "connect" in str(e).lower():
            print("💡 AIVIS Speechサーバーが http://127.0.0.1:10101 で起動していることを確認してください")
        traceback.print_exc()
        return False


async def test_gemini_image_generation():
    """Gemini 2.0 画像生成 API の動作確認"""
    print("\n" + "="*60)
    print("🎨 Gemini 2.0 画像生成 API テスト開始")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません")
        print("💡 .env ファイルに以下の形式で設定してください:")
        print("   GEMINI_API_KEY=your_actual_api_key_here")
        return False
    
    try:
        async with ImageGenerationClient(api_key=api_key) as client:
            request = ImageRequest(
                prompt="A beautiful anime-style landscape with cherry blossoms, traditional Japanese house, peaceful and serene atmosphere, soft colors",
                temperature=0.8
            )
            
            print(f"🎨 画像生成中...")
            print(f"   プロンプト: {request.prompt}")
            print(f"   温度: {request.temperature}")
            
            responses = await client.generate_images(request)
            
            if responses:
                response = responses[0]
                
                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_file.write(response.image_data)
                    temp_path = tmp_file.name
                
                print(f"🎉 画像生成成功!")
                print(f"📁 画像ファイル: {temp_path}")
                print(f"📏 画像サイズ: {response.size}")
                print(f"📊 ファイルサイズ: {len(response.image_data):,} bytes")
                if response.text_content:
                    print(f"📝 説明テキスト: {response.text_content}")
                
                # ファイルを削除
                os.unlink(temp_path)
                print(f"🗑️  一時ファイルを削除しました")
                
                return True
            else:
                print("❌ 画像が生成されませんでした")
                return False
                
    except Exception as e:
        print(f"❌ 画像生成失敗: {e}")
        if "API_KEY_INVALID" in str(e):
            print("💡 APIキーが無効です。正しいGemini APIキーを設定してください。")
        elif "NOT_AVAILABLE" in str(e) or "not available" in str(e).lower():
            print("💡 Gemini 2.0画像生成機能がご利用のアカウントで利用できない可能性があります。")
        traceback.print_exc()
        return False


async def main():
    """メイン実行関数"""
    print("🚀 外部API統合テスト開始")
    print("=" * 80)
    
    results = {
        "LLM (Gemini)": False,
        "TTS (AIVIS Speech)": False,
        "画像生成 (Gemini 2.0)": False
    }
    
    start_time = asyncio.get_event_loop().time()
    
    # 1. Gemini LLM テスト
    print("🔄 テスト 1/3 実行中...")
    results["LLM (Gemini)"] = await test_gemini_llm()
    
    # 2. AIVIS Speech TTS テスト
    print("🔄 テスト 2/3 実行中...")
    results["TTS (AIVIS Speech)"] = await test_aivis_speech()
    
    # 3. Gemini 2.0 画像生成テスト
    print("🔄 テスト 3/3 実行中...")
    results["画像生成 (Gemini 2.0)"] = await test_gemini_image_generation()
    
    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time
    
    # 結果サマリー
    print("\n" + "="*80)
    print("📊 テスト結果サマリー")
    print("="*80)
    
    success_count = 0
    for api_name, success in results.items():
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"{api_name:30} : {status}")
        if success:
            success_count += 1
    
    print("="*80)
    print(f"⏱️  総実行時間: {total_time:.2f}秒")
    print(f"📈 成功率: {success_count}/3 ({success_count/3*100:.1f}%)")
    
    if success_count == 3:
        print("🎉 すべてのAPIクライアントが正常に動作しています！")
        print("🚀 ゆっくり動画自動生成ツールの準備が完了しました！")
        return 0
    else:
        print("⚠️  一部のAPIクライアントでエラーが発生しました。")
        print("\n🔧 トラブルシューティング:")
        
        if not results["LLM (Gemini)"]:
            print("• Gemini LLM API:")
            print("  - .env ファイルに正しい GEMINI_API_KEY を設定")
            print("  - Google AI Studio (https://makersuite.google.com/app/apikey) でAPIキーを取得")
        
        if not results["TTS (AIVIS Speech)"]:
            print("• AIVIS Speech TTS API:")
            print("  - AIVIS Speechサーバーを http://127.0.0.1:10101 で起動")
            print("  - サーバーが正常に動作していることを確認")
        
        if not results["画像生成 (Gemini 2.0)"]:
            print("• Gemini 2.0 画像生成 API:")
            print("  - .env ファイルに正しい GEMINI_API_KEY を設定")
            print("  - Gemini 2.0画像生成機能のアクセス権限を確認")
        
        return 1


if __name__ == "__main__":
    try:
        print("📋 環境変数確認:")
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            print(f"✅ Gemini API Key: 設定済み ({gemini_key[:10]}...)")
        else:
            print("❌ Gemini API Key: 未設定")
        
        print("\n🎬 統合テスト実行開始...")
        exit_code = asyncio.run(main())
        
        print(f"\n🏁 テスト完了: exit_code={exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n⏹️  テストが中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 予期しないエラー: {e}")
        traceback.print_exc()
        sys.exit(1) 