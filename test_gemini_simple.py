"""
Gemini動作確認用のシンプルテスト
"""

import asyncio
import sys
import os

# プロジェクトのルートディレクトリをsys.pathに追加
sys.path.insert(0, os.path.abspath('.'))

from src.api.llm_client import GeminiLLMClient, GeminiRequest
from src.core.config_manager import ConfigManager


async def test_gemini_connection():
    """Geminiの接続テスト"""
    print("🔍 Geminiの接続テストを開始します...")
    
    try:
        # 設定管理を初期化
        config_manager = ConfigManager()
        
        # APIキーを取得（設定ファイルまたは環境変数から）
        api_key = None
        try:
            # 設定ファイルを読み込み
            config = config_manager.load_config("llm_config.yaml")
            print("✓ LLM設定ファイルを読み込みました")
            api_key = config_manager.get_value("api.gemini.api_key", config)
            if api_key:
                print("✓ 設定ファイルからAPIキーを取得しました")
        except Exception as e:
            print(f"⚠️ 設定ファイル読み込みエラー: {e}")
            print("📄 環境変数からAPIキーを取得を試行中...")
        
        # 環境変数からフォールバック
        if not api_key:
            # 複数の環境変数パターンを確認
            env_patterns = [
                "GOOGLE_API_KEY",
                "GEMINI_API_KEY", 
                "GOOGLE_AI_API_KEY",
                "GENAI_API_KEY"
            ]
            
            print("🔍 環境変数を確認中...")
            for pattern in env_patterns:
                env_value = os.getenv(pattern)
                if env_value:
                    api_key = env_value
                    print(f"✓ 環境変数 {pattern} からAPIキーを取得しました")
                    break
                else:
                    print(f"❌ 環境変数 {pattern} は設定されていません")
        
        if not api_key:
            print("\n❌ APIキーが設定されていません")
            print("📋 以下のいずれかの方法でAPIキーを設定してください：")
            print("   1. 環境変数 GOOGLE_API_KEY を設定")
            print("   2. 環境変数 GEMINI_API_KEY を設定")
            print("   3. .envファイルにAPIキーを記載")
            print("   4. config/llm_config.yamlにapi.gemini.api_keyを追加")
            print("\n🔧 Google AI Studio (https://aistudio.google.com/) でAPIキーを取得できます")
            return False
        
        print(f"✓ APIキーが設定されています (先頭10文字: {api_key[:10]}...)")
        
        # クライアントを初期化
        client = GeminiLLMClient(api_key=api_key)
        print("✓ Geminiクライアントを初期化しました")
        
        # テスト用のリクエストを作成
        request = GeminiRequest(
            prompt="Hello! 簡単な日本語で「こんにちは」と返答してください。",
            max_output_tokens=100
        )
        print("✓ テストリクエストを作成しました")
        
        # APIリクエストを送信
        print("🌐 Gemini APIにリクエストを送信中...")
        response = await client.generate_text(request)
        
        print(f"✅ Gemini APIから正常にレスポンスを受信しました!")
        print(f"📝 レスポンス: {response.text}")
        print(f"📊 使用トークン数: {response.token_count}")
        print(f"🤖 使用モデル: {response.model}")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")
        print(f"エラータイプ: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン関数"""
    print("=" * 50)
    print("🚀 Gemini API動作確認テスト")
    print("=" * 50)
    
    success = await test_gemini_connection()
    
    print("=" * 50)
    if success:
        print("✅ テスト完了: Gemini APIは正常に動作しています")
    else:
        print("❌ テスト失敗: Gemini APIに問題があります")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main()) 