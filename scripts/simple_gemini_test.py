#!/usr/bin/env python
# simple_gemini_test.py  (google-genai >= 1.20)

import os, sys
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
import httpx
from PIL import Image
from google import genai
from google.genai import types


# 0) 不要な環境変数を“念のため”空に
for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY",
          "http_proxy","https_proxy","all_proxy"):
    os.environ.pop(k, None)

# 1) API キー読込
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    sys.exit("❌ GEMINI_API_KEY が見つかりません")

# 2) Client 生成（通常どおり）
client = genai.Client(api_key=API_KEY)

# 3) 内部 httpx.Client を trust_env=False のものに“入れ替え”
#    ※ 公式 API には未公開だが動作には問題なし
new_httpx = httpx.Client(timeout=60.0, trust_env=False)
old_httpx = client._api_client._httpx_client        # 現在のクライアント
old_httpx.close()                                   # 接続を安全に閉じる
client._api_client._httpx_client = new_httpx        # 差し替え完了

# 4-A) テキスト生成
resp = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="夏の東京を詠む俳句を一句、季語を入れて。"
)
print("📝 Text:", resp.text.strip())

# 4-B) 画像生成
prompt = "富士山と桜を描いた水彩風イラストを生成してください。"
resp_img = client.models.generate_content(
    model="gemini-2.0-flash-preview-image-generation",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_modalities=["TEXT","IMAGE"]
    )
)
out = Path("gemini_test_image.png")
for p in resp_img.candidates[0].content.parts:
    if p.text:
        print("💬 Caption:", p.text.strip())
    elif p.inline_data:
        Image.open(BytesIO(p.inline_data.data)).save(out)
        print(f"🖼️ 画像を {out.resolve()} に保存しました")

print("=== テスト完了 ===")
