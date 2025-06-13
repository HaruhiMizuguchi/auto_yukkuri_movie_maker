#!/usr/bin/env python3
"""
.envファイルと環境変数の詳細デバッグスクリプト
"""

import os
import sys
from pathlib import Path

print("🔍 .envファイル・環境変数デバッグ")
print("=" * 60)

# 1. カレントディレクトリ確認
print("📁 Step 1: カレントディレクトリ確認")
current_dir = Path.cwd()
print(f"現在のディレクトリ: {current_dir}")
print()

# 2. .envファイルの確認
print("📄 Step 2: .envファイルの確認")
env_paths = [
    Path(".env"),
    Path("../.env"),
    current_dir / ".env",
    current_dir.parent / ".env"
]

found_env = None
for env_path in env_paths:
    abs_path = env_path.resolve()
    if env_path.exists():
        print(f"✅ .envファイル発見: {abs_path}")
        found_env = env_path
        break
    else:
        print(f"❌ 未発見: {abs_path}")

if not found_env:
    print("❌ .envファイルが見つかりません")
    print()
    print("🔍 プロジェクトディレクトリの内容:")
    for item in current_dir.iterdir():
        print(f"  {item.name}")
    sys.exit(1)

print()

# 3. .envファイルの内容確認
print("📋 Step 3: .envファイルの内容確認")
try:
    with open(found_env, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    print(f"総行数: {len(lines)}")
    print(f"ファイルサイズ: {len(content)} bytes")
    print()
    
    print("内容 (先頭20行):")
    for i, line in enumerate(lines[:20], 1):
        if 'API_KEY' in line.upper():
            # APIキーを含む行は一部マスク
            if '=' in line:
                key, value = line.split('=', 1)
                masked_value = value[:10] + '...' if len(value) > 10 else value
                print(f"  {i:2d}: {key}={masked_value}")
            else:
                print(f"  {i:2d}: {line}")
        else:
            print(f"  {i:2d}: {line}")
    
    if len(lines) > 20:
        print(f"  ... (残り {len(lines) - 20} 行)")
    
except Exception as e:
    print(f"❌ ファイル読み込みエラー: {e}")

print()

# 4. 実行前の環境変数確認
print("🔑 Step 4: 実行前の環境変数確認")
gemini_before = os.getenv("GEMINI_API_KEY")
google_before = os.getenv("GOOGLE_API_KEY")

print(f"GEMINI_API_KEY (実行前): {'設定済み' if gemini_before else '未設定'}")
if gemini_before:
    print(f"  値: {gemini_before[:20]}... (長さ: {len(gemini_before)})")

print(f"GOOGLE_API_KEY (実行前): {'設定済み' if google_before else '未設定'}")
if google_before:
    print(f"  値: {google_before[:20]}... (長さ: {len(google_before)})")

print()

# 5. dotenv読み込み
print("📥 Step 5: python-dotenv による読み込み")
try:
    from dotenv import load_dotenv
    print("✅ dotenv インポート成功")
    
    # 明示的にパスを指定して読み込み
    result = load_dotenv(found_env)
    print(f"✅ load_dotenv 実行: {result}")
    
except Exception as e:
    print(f"❌ dotenv読み込みエラー: {e}")

print()

# 6. 読み込み後の環境変数確認
print("🔑 Step 6: 読み込み後の環境変数確認")
gemini_after = os.getenv("GEMINI_API_KEY")
google_after = os.getenv("GOOGLE_API_KEY")

print(f"GEMINI_API_KEY (読み込み後): {'設定済み' if gemini_after else '未設定'}")
if gemini_after:
    print(f"  値: {gemini_after[:20]}... (長さ: {len(gemini_after)})")

print(f"GOOGLE_API_KEY (読み込み後): {'設定済み' if google_after else '未設定'}")
if google_after:
    print(f"  値: {google_after[:20]}... (長さ: {len(google_after)})")

print()

# 7. 変更の確認
print("🔄 Step 7: 変更の確認")
if gemini_before != gemini_after:
    print("✅ GEMINI_API_KEY が変更されました")
else:
    print("⚠️  GEMINI_API_KEY に変化なし")

if google_before != google_after:
    print("✅ GOOGLE_API_KEY が変更されました")
else:
    print("⚠️  GOOGLE_API_KEY に変化なし")

print()

# 8. 最終的なAPIキー確認
print("🎯 Step 8: 最終的なAPIキー確認")
final_key = gemini_after or google_after
if final_key:
    print(f"✅ 使用可能なAPIキー: {final_key[:20]}... (長さ: {len(final_key)})")
    
    # APIキーの形式チェック
    if final_key.startswith('AIza'):
        print("✅ Google API キーの形式 (AIza...)")
    else:
        print(f"⚠️  予期しない形式: {final_key[:10]}...")
        
    # 文字数チェック
    if len(final_key) >= 35:
        print("✅ 長さは適切 (35文字以上)")
    else:
        print(f"⚠️  短すぎる可能性 (長さ: {len(final_key)})")
        
else:
    print("❌ APIキーが設定されていません")

print()
print("🏁 デバッグ完了!")
print("=" * 60) 