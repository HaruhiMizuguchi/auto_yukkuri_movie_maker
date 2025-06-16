# TTS音声生成クライアント (AIVIS Speech Client)

## 概要

`AivisSpeechClient`は、AIVIS Speech APIを使用してゆっくり音声を生成するクライアントです。話者（霊夢、魔理沙など）の音声合成、タイムスタンプ付き音声生成、バッチ処理などの機能を提供します。

## 基本的な使用方法

### クライアントの初期化

```python
from src.api import AivisSpeechClient, TTSRequest, AudioSettings

# 基本的な初期化（ローカルサーバー使用）
async with AivisSpeechClient() as tts_client:
    # 音声生成処理
    pass

# カスタム設定での初期化
async with AivisSpeechClient(
    base_url="http://127.0.0.1:10101",
    rate_limit_config=RateLimitConfig(requests_per_minute=60)
) as tts_client:
    # 音声生成処理
    pass
```

### 基本的な音声生成

```python
import asyncio
from src.api import AivisSpeechClient, TTSRequest

async def generate_basic_audio():
    """基本的な音声生成"""
    
    async with AivisSpeechClient() as client:
        # TTS リクエストの作成
        request = TTSRequest(
            text="こんにちは！ゆっくりしていってね！",
            speaker_id=0,  # 話者ID（0: 霊夢）
            enable_timestamps=True
        )
        
        # 音声生成
        response = await client.generate_audio(request)
        
        # 結果の確認
        print(f"音声長: {response.duration_seconds:.2f}秒")
        print(f"サンプルレート: {response.sample_rate}Hz")
        print(f"タイムスタンプ数: {len(response.timestamps)}")
        
        # 音声ファイル保存
        response.save_audio("output/greeting.wav")
        
        return response

# 実行
response = asyncio.run(generate_basic_audio())
```

### 話者とスタイルの選択

```python
from src.api import SpeakerStyle

# 利用可能な話者スタイル
speaker_styles = {
    "reimu_normal": 0,      # 霊夢（通常）
    "reimu_happy": 1,       # 霊夢（喜び）
    "reimu_angry": 2,       # 霊夢（怒り）
    "marisa_normal": 3,     # 魔理沙（通常）
    "marisa_happy": 4,      # 魔理沙（喜び）
    "marisa_excited": 5     # 魔理沙（興奮）
}

async def generate_with_different_speakers():
    """異なる話者での音声生成"""
    
    async with AivisSpeechClient() as client:
        # 霊夢の音声
        reimu_request = TTSRequest(
            text="私は博麗霊夢よ",
            speaker_id=0
        )
        reimu_response = await client.generate_audio(reimu_request)
        reimu_response.save_audio("output/reimu.wav")
        
        # 魔理沙の音声
        marisa_request = TTSRequest(
            text="私は霧雨魔理沙だぜ！",
            speaker_id=3
        )
        marisa_response = await client.generate_audio(marisa_request)
        marisa_response.save_audio("output/marisa.wav")

# 実行
asyncio.run(generate_with_different_speakers())
```

### 音声パラメータのカスタマイズ

```python
from src.api import AudioSettings

async def generate_custom_audio():
    """カスタム音声設定での生成"""
    
    # 音声設定をカスタマイズ
    custom_settings = AudioSettings(
        speaker_id=0,           # 話者ID
        speed=1.2,              # 話速（1.0が標準）
        pitch=0.1,              # ピッチ（0.0が標準）
        intonation=1.1,         # イントネーション
        volume=1.0,             # 音量
        pre_phoneme_length=0.2, # 音素前の長さ
        post_phoneme_length=0.2 # 音素後の長さ
    )
    
    async with AivisSpeechClient() as client:
        request = TTSRequest(
            text="この設定でより自然な音声になります",
            speaker_id=0,
            audio_settings=custom_settings,
            enable_timestamps=True
        )
        
        response = await client.generate_audio(request)
        response.save_audio("output/custom_audio.wav")
        
        return response

# 実行
response = asyncio.run(generate_custom_audio())
```

## データクラス

### TTSRequest

音声生成リクエストのデータクラスです。

```python
@dataclass
class TTSRequest:
    text: str                               # 生成するテキスト
    speaker_id: int = 0                     # 話者ID
    audio_settings: Optional[AudioSettings] = None  # 音声設定
    enable_timestamps: bool = True          # タイムスタンプ生成
    output_format: str = "wav"              # 出力フォーマット
```

### TTSResponse

音声生成結果のデータクラスです。

```python
@dataclass
class TTSResponse:
    audio_data: bytes                       # 音声データ（バイナリ）
    audio_length: float                     # 音声長（秒）
    sample_rate: int                        # サンプルレート
    timestamps: List[TimestampData]         # タイムスタンプ情報
    speaker_info: Dict[str, Any]            # 話者情報
    
    @property
    def duration_seconds(self) -> float:    # 音声時間
    
    def save_audio(self, file_path: str) -> None:  # ファイル保存
```

### AudioSettings

音声生成パラメータのデータクラスです。

```python
@dataclass
class AudioSettings:
    speaker_id: int = 0                     # 話者ID
    speed: float = 1.0                      # 話速
    pitch: float = 0.0                      # ピッチ
    intonation: float = 1.0                 # イントネーション
    volume: float = 1.0                     # 音量
    pre_phoneme_length: float = 0.1         # 音素前の長さ
    post_phoneme_length: float = 0.1        # 音素後の長さ
```

### TimestampData

タイムスタンプ情報のデータクラスです。

```python
@dataclass
class TimestampData:
    start_time: float                       # 開始時間（秒）
    end_time: float                         # 終了時間（秒）
    text: str                               # 対応テキスト
    phoneme: Optional[str] = None           # 音素情報
    confidence: Optional[float] = None       # 信頼度
```

## 実際の使用例

### ゆっくり動画のスクリプト音声生成

```python
import asyncio
from pathlib import Path
from src.api import AivisSpeechClient, TTSRequest, AudioSettings

# スクリプトデータ（例）
script_data = [
    {"speaker": "reimu", "text": "今日はPythonの基礎について学びましょう"},
    {"speaker": "marisa", "text": "変数とは何かから始めよう！"},
    {"speaker": "reimu", "text": "まず変数の定義方法を見てみましょう"},
    {"speaker": "marisa", "text": "name = 'ゆっくり' のように書くのぜ"},
    {"speaker": "reimu", "text": "とても簡単ですね"}
]

# 話者ID マッピング
SPEAKER_MAPPING = {
    "reimu": 0,
    "marisa": 3
}

# 話者別音声設定
SPEAKER_SETTINGS = {
    "reimu": AudioSettings(
        speed=1.0,
        pitch=0.0,
        intonation=1.0
    ),
    "marisa": AudioSettings(
        speed=1.1,
        pitch=0.1,
        intonation=1.2
    )
}

async def generate_script_audio():
    """スクリプト全体の音声生成"""
    
    async with AivisSpeechClient() as client:
        output_dir = Path("output/script_audio")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        audio_segments = []
        
        for i, segment in enumerate(script_data):
            speaker = segment["speaker"]
            text = segment["text"]
            
            # リクエスト作成
            request = TTSRequest(
                text=text,
                speaker_id=SPEAKER_MAPPING[speaker],
                audio_settings=SPEAKER_SETTINGS[speaker],
                enable_timestamps=True
            )
            
            # 音声生成
            print(f"🎤 音声生成中 [{i+1}/{len(script_data)}]: {speaker}")
            response = await client.generate_audio(request)
            
            # ファイル保存
            filename = f"{i+1:03d}_{speaker}.wav"
            file_path = output_dir / filename
            response.save_audio(str(file_path))
            
            audio_segments.append({
                "file_path": str(file_path),
                "speaker": speaker,
                "text": text,
                "duration": response.duration_seconds,
                "timestamps": response.timestamps
            })
            
            print(f"✅ 完了: {filename} ({response.duration_seconds:.2f}秒)")
        
        # 統計情報
        total_duration = sum(seg["duration"] for seg in audio_segments)
        print(f"\n📊 音声生成完了:")
        print(f"  ファイル数: {len(audio_segments)}")
        print(f"  総時間: {total_duration:.2f}秒")
        print(f"  出力先: {output_dir}")
        
        return audio_segments

# 実行
segments = asyncio.run(generate_script_audio())
```

### バッチ音声生成

```python
async def batch_audio_generation():
    """複数テキストのバッチ音声生成"""
    
    # 生成したいテキスト一覧
    texts = [
        "変数とは値を格納する箱のようなものです",
        "Pythonでは型を明示的に宣言する必要がありません",
        "文字列は引用符で囲みます",
        "数値は直接書くことができます",
        "リストは複数の値を格納できます"
    ]
    
    # TTSリクエストのリストを作成
    requests = [
        TTSRequest(
            text=text,
            speaker_id=0,  # 霊夢
            enable_timestamps=True
        )
        for text in texts
    ]
    
    async with AivisSpeechClient() as client:
        # バッチ音声生成
        print("🎤 バッチ音声生成開始...")
        responses = await client.batch_generate_audio(requests)
        
        # 結果の保存
        output_dir = Path("output/batch_audio")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, response in enumerate(responses):
            filename = f"batch_{i+1:03d}.wav"
            response.save_audio(str(output_dir / filename))
            print(f"✅ 保存: {filename} ({response.duration_seconds:.2f}秒)")
        
        total_duration = sum(r.duration_seconds for r in responses)
        print(f"📊 バッチ生成完了: {len(responses)}ファイル, 総時間 {total_duration:.2f}秒")
        
        return responses

# 実行
responses = asyncio.run(batch_audio_generation())
```

### タイムスタンプ活用

```python
async def generate_with_timestamp_analysis():
    """タイムスタンプ分析付き音声生成"""
    
    text = "プログラミングは創造的な活動です。コードを書いて動作させる喜びを体験してみてください。"
    
    async with AivisSpeechClient() as client:
        request = TTSRequest(
            text=text,
            speaker_id=0,
            enable_timestamps=True
        )
        
        response = await client.generate_audio(request)
        
        # タイムスタンプ分析
        print("🎵 タイムスタンプ分析:")
        print(f"総時間: {response.duration_seconds:.2f}秒")
        print(f"セグメント数: {len(response.timestamps)}")
        print()
        
        # セグメントごとの詳細
        for i, timestamp in enumerate(response.timestamps):
            duration = timestamp.end_time - timestamp.start_time
            print(f"{i+1:2d}. {timestamp.start_time:5.2f}s - {timestamp.end_time:5.2f}s "
                  f"({duration:4.2f}s): '{timestamp.text}'")
        
        # 音声ファイル保存
        response.save_audio("output/timestamped_audio.wav")
        
        # タイムスタンプをJSONで保存
        import json
        timestamp_data = [
            {
                "start_time": ts.start_time,
                "end_time": ts.end_time,
                "text": ts.text,
                "duration": ts.end_time - ts.start_time
            }
            for ts in response.timestamps
        ]
        
        with open("output/timestamps.json", "w", encoding="utf-8") as f:
            json.dump(timestamp_data, f, ensure_ascii=False, indent=2)
        
        return response

# 実行
response = asyncio.run(generate_with_timestamp_analysis())
```

## エラーハンドリング

### 一般的なエラーパターン

```python
from src.api import TTSAPIError, InvalidSpeakerError, AudioGenerationError

async def robust_audio_generation(text: str, speaker_id: int):
    """堅牢な音声生成"""
    
    try:
        async with AivisSpeechClient() as client:
            # 話者検証
            if not await client.validate_speaker(speaker_id):
                raise InvalidSpeakerError(speaker_id)
            
            # 音声生成
            request = TTSRequest(text=text, speaker_id=speaker_id)
            response = await client.generate_audio(request)
            
            # 品質確認
            if response.duration_seconds < 0.1:
                raise AudioGenerationError("音声が短すぎます")
            
            return response
            
    except InvalidSpeakerError as e:
        print(f"❌ 無効な話者ID: {e.speaker_id}")
        # フォールバック: デフォルト話者を使用
        return await robust_audio_generation(text, 0)
        
    except AudioGenerationError as e:
        print(f"❌ 音声生成エラー: {e}")
        return None
        
    except TTSAPIError as e:
        print(f"❌ TTS APIエラー: {e}")
        return None
        
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return None

# 使用例
response = await robust_audio_generation("テストテキスト", 999)  # 無効な話者ID
```

### リトライ機能付き音声生成

```python
import asyncio
from typing import Optional

async def generate_audio_with_retry(
    text: str, 
    speaker_id: int, 
    max_retries: int = 3
) -> Optional[TTSResponse]:
    """リトライ機能付き音声生成"""
    
    for attempt in range(max_retries + 1):
        try:
            async with AivisSpeechClient() as client:
                request = TTSRequest(text=text, speaker_id=speaker_id)
                response = await client.generate_audio(request)
                
                print(f"✅ 音声生成成功 (試行 {attempt + 1})")
                return response
                
        except Exception as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt  # 指数バックオフ
                print(f"⚠️ 試行 {attempt + 1} 失敗: {e}")
                print(f"🔄 {wait_time}秒後に再試行...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ 全試行失敗: {e}")
                return None
    
    return None

# 使用例
response = await generate_audio_with_retry("重要なメッセージ", 0, max_retries=3)
```

## パフォーマンス最適化

### 並列音声生成

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def parallel_audio_generation(texts: List[str], speaker_id: int = 0):
    """並列音声生成"""
    
    async def generate_single_audio(text: str, index: int):
        """単一音声生成（非同期）"""
        try:
            async with AivisSpeechClient() as client:
                request = TTSRequest(text=text, speaker_id=speaker_id)
                response = await client.generate_audio(request)
                
                # ファイル保存
                filename = f"output/parallel_{index+1:03d}.wav"
                response.save_audio(filename)
                
                return {
                    "index": index,
                    "text": text,
                    "filename": filename,
                    "duration": response.duration_seconds,
                    "success": True
                }
        except Exception as e:
            return {
                "index": index,
                "text": text,
                "error": str(e),
                "success": False
            }
    
    # 並列実行
    print(f"🚀 {len(texts)}件の音声を並列生成開始...")
    
    tasks = [
        generate_single_audio(text, i) 
        for i, text in enumerate(texts)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 結果分析
    success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    total_duration = sum(
        r.get("duration", 0) 
        for r in results 
        if isinstance(r, dict) and r.get("success")
    )
    
    print(f"📊 並列生成完了:")
    print(f"  成功: {success_count}/{len(texts)}")
    print(f"  総時間: {total_duration:.2f}秒")
    
    return results

# 使用例
texts = [
    "Python入門の第1章です",
    "変数の概念を学びましょう",
    "データ型について解説します",
    "制御構文の使い方です",
    "関数の定義方法を説明します"
]

results = await parallel_audio_generation(texts)
```

### キャッシュ機能

```python
import hashlib
import json
from pathlib import Path

class CachedTTSClient:
    """キャッシュ機能付きTTSクライアント"""
    
    def __init__(self, cache_dir: str = "cache/tts"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = None
    
    async def __aenter__(self):
        self.client = AivisSpeechClient()
        await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    def _get_cache_key(self, request: TTSRequest) -> str:
        """キャッシュキー生成"""
        # リクエストの内容をハッシュ化
        content = {
            "text": request.text,
            "speaker_id": request.speaker_id,
            "audio_settings": request.audio_settings.__dict__ if request.audio_settings else None
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()
    
    async def generate_audio_cached(self, request: TTSRequest) -> TTSResponse:
        """キャッシュ機能付き音声生成"""
        
        cache_key = self._get_cache_key(request)
        cache_path = self.cache_dir / f"{cache_key}.wav"
        metadata_path = self.cache_dir / f"{cache_key}.json"
        
        # キャッシュ確認
        if cache_path.exists() and metadata_path.exists():
            print(f"📁 キャッシュから取得: {cache_key[:8]}...")
            
            # メタデータ読み込み
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            # 音声データ読み込み
            with open(cache_path, "rb") as f:
                audio_data = f.read()
            
            # TTSResponse再構築
            return TTSResponse(
                audio_data=audio_data,
                audio_length=metadata["audio_length"],
                sample_rate=metadata["sample_rate"],
                timestamps=[TimestampData(**ts) for ts in metadata["timestamps"]],
                speaker_info=metadata["speaker_info"]
            )
        
        # キャッシュがない場合は新規生成
        print(f"🎤 新規生成: {request.text[:20]}...")
        response = await self.client.generate_audio(request)
        
        # キャッシュに保存
        with open(cache_path, "wb") as f:
            f.write(response.audio_data)
        
        metadata = {
            "audio_length": response.audio_length,
            "sample_rate": response.sample_rate,
            "timestamps": [ts.__dict__ for ts in response.timestamps],
            "speaker_info": response.speaker_info,
            "request": {
                "text": request.text,
                "speaker_id": request.speaker_id
            }
        }
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"💾 キャッシュに保存: {cache_key[:8]}...")
        return response

# 使用例
async def generate_with_cache():
    async with CachedTTSClient() as cached_client:
        request = TTSRequest(
            text="このテキストはキャッシュされます",
            speaker_id=0
        )
        
        # 1回目: 新規生成
        response1 = await cached_client.generate_audio_cached(request)
        
        # 2回目: キャッシュから取得
        response2 = await cached_client.generate_audio_cached(request)
        
        print(f"同じデータ: {response1.audio_data == response2.audio_data}")

# 実行
await generate_with_cache()
```

## 設定とカスタマイズ

### レート制限の調整

```python
from src.core.api_client import RateLimitConfig

# カスタムレート制限
custom_rate_limit = RateLimitConfig(
    requests_per_minute=30,    # 1分間に30リクエスト
    requests_per_hour=1800,    # 1時間に1800リクエスト
    burst_limit=5              # バースト制限
)

async with AivisSpeechClient(rate_limit_config=custom_rate_limit) as client:
    # レート制限された環境での音声生成
    pass
```

### タイムアウト設定

```python
# カスタムタイムアウト
async with AivisSpeechClient() as client:
    request = TTSRequest(
        text="長いテキストの音声生成",
        speaker_id=0
    )
    
    # タイムアウト設定でリクエスト送信
    try:
        response = await asyncio.wait_for(
            client.generate_audio(request), 
            timeout=30.0  # 30秒でタイムアウト
        )
    except asyncio.TimeoutError:
        print("音声生成がタイムアウトしました")
``` 