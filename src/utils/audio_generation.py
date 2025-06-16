"""
音声生成ユーティリティ

AivisSpeechClientの複雑さを隠し、シンプルで使いやすい高レベル関数を提供します。
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import tempfile
import os

from ..api.tts_client import (
    AivisSpeechClient,
    TTSRequest,
    TTSResponse,
    AudioSettings,
    SpeakerStyle,
    TTSAPIError
)

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_SPEAKERS = {
    "reimu": 0,      # 霊夢（デフォルト）
    "marisa": 1,     # 魔理沙
    "yukari": 2,     # 紫
    "alice": 3,      # アリス
    "patchouli": 4   # パチュリー
}

DEFAULT_SETTINGS = AudioSettings(
    speaker_id=0,
    speed=1.0,
    pitch=0.0,
    intonation=1.0,
    volume=1.0,
    pre_phoneme_length=0.1,
    post_phoneme_length=0.1
)


async def generate_speech(
    text: str,
    speaker: Union[str, int] = "reimu",
    speed: float = 1.0,
    output_path: Optional[Union[str, Path]] = None,
    server_url: str = "http://127.0.0.1:10101"
) -> str:
    """
    テキストから音声を生成する（最もシンプルな関数）
    
    Args:
        text: 読み上げるテキスト
        speaker: 話者名または話者ID（"reimu", "marisa", 0, 1など）
        speed: 読み上げ速度（0.5〜2.0）
        output_path: 出力ファイルパス（指定しない場合は一時ファイル）
        server_url: AIVIS Speech サーバーURL
    
    Returns:
        str: 生成された音声ファイルのパス
    
    Examples:
        >>> # 最もシンプルな使用例
        >>> audio_file = await generate_speech("こんにちは！")
        >>> print(f"音声ファイル: {audio_file}")
        
        >>> # 魔理沙の声でゆっくり
        >>> audio_file = await generate_speech("魔法は力だぜ！", speaker="marisa", speed=0.8)
        
        >>> # ファイル保存先を指定
        >>> audio_file = await generate_speech("テスト", output_path="test.wav")
    """
    try:
        # 話者IDの解決
        speaker_id = _resolve_speaker_id(speaker)
        
        # 音声設定
        audio_settings = AudioSettings(
            speaker_id=speaker_id,
            speed=speed,
            pitch=0.0,
            intonation=1.0,
            volume=1.0
        )
        
        # リクエスト作成
        request = TTSRequest(
            text=text,
            speaker_id=speaker_id,
            audio_settings=audio_settings,
            enable_timestamps=False,  # シンプルにするため無効
            output_format="wav"
        )
        
        # 音声生成
        async with AivisSpeechClient(base_url=server_url) as client:
            response = await client.generate_audio(request)
        
        # ファイル保存
        if output_path is None:
            # 一時ファイルを作成
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav", 
                delete=False
            )
            output_path = temp_file.name
            temp_file.close()
        
        response.save_audio(output_path)
        
        logger.info(f"音声生成完了: {text[:20]}... -> {output_path}")
        return str(output_path)
        
    except TTSAPIError as e:
        logger.error(f"TTS API エラー: {e}")
        raise ValueError(f"音声生成に失敗しました: {e}")
    except Exception as e:
        logger.error(f"音声生成エラー: {e}")
        raise RuntimeError(f"音声生成中に予期しないエラーが発生しました: {e}")


async def generate_yukkuri_dialogue(
    dialogue_parts: List[Dict[str, str]],
    output_dir: Optional[Union[str, Path]] = None,
    speed: float = 1.0
) -> List[str]:
    """
    ゆっくり動画用の対話音声を生成する
    
    Args:
        dialogue_parts: 対話部分のリスト
                       [{"speaker": "reimu", "text": "こんにちは"}, ...]
        output_dir: 出力ディレクトリ（指定しない場合は一時ディレクトリ）
        speed: 読み上げ速度
    
    Returns:
        List[str]: 生成された音声ファイルのパスリスト
    
    Examples:
        >>> dialogue = [
        ...     {"speaker": "reimu", "text": "こんにちは、魔理沙"},
        ...     {"speaker": "marisa", "text": "よう、霊夢！元気だぜ"},
        ...     {"speaker": "reimu", "text": "今日は何をするの？"}
        ... ]
        >>> audio_files = await generate_yukkuri_dialogue(dialogue)
        >>> for i, file in enumerate(audio_files):
        ...     print(f"パート{i+1}: {file}")
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    audio_files = []
    
    for i, part in enumerate(dialogue_parts):
        speaker = part.get("speaker", "reimu")
        text = part.get("text", "")
        
        if not text.strip():
            continue
        
        # ファイル名生成
        filename = f"dialogue_{i+1:03d}_{speaker}.wav"
        output_path = output_dir / filename
        
        # 音声生成
        audio_file = await generate_speech(
            text=text,
            speaker=speaker,
            speed=speed,
            output_path=output_path
        )
        
        audio_files.append(audio_file)
    
    logger.info(f"対話音声生成完了: {len(audio_files)}ファイル -> {output_dir}")
    return audio_files


async def generate_script_audio(
    script_data: Dict[str, Any],
    output_dir: Optional[Union[str, Path]] = None,
    voice_settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    スクリプトデータから音声を一括生成する
    
    Args:
        script_data: generate_yukkuri_script()の出力形式
        output_dir: 出力ディレクトリ
        voice_settings: 音声設定（話者別の速度設定など）
    
    Returns:
        Dict[str, Any]: 音声ファイル情報と統計データ
    
    Examples:
        >>> script = await generate_yukkuri_script("Python入門", duration_minutes=5)
        >>> audio_result = await generate_script_audio(script)
        >>> print(f"生成ファイル数: {audio_result['total_files']}")
        >>> print(f"総再生時間: {audio_result['total_duration']:.1f}秒")
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # デフォルト音声設定
    default_voice_settings = {
        "reimu": {"speed": 1.0, "pitch": 0.0},
        "marisa": {"speed": 1.1, "pitch": 0.1}
    }
    if voice_settings:
        default_voice_settings.update(voice_settings)
    
    audio_files = []
    section_audios = {}
    total_duration = 0.0
    
    # スクリプトの各セクションを処理
    for section in script_data.get("sections", []):
        section_title = section.get("title", "無題")
        section_content = section.get("content", [])
        
        section_files = []
        
        for i, content_item in enumerate(section_content):
            speaker = content_item.get("speaker", "reimu")
            text = content_item.get("text", "")
            
            if not text.strip():
                continue
            
            # 音声設定取得
            voice_config = default_voice_settings.get(speaker, {"speed": 1.0})
            
            # ファイル名生成
            safe_title = "".join(c if c.isalnum() or c in "._-" else "_" for c in section_title)
            filename = f"section_{safe_title}_{i+1:03d}_{speaker}.wav"
            output_path = output_dir / filename
            
            # 音声生成
            audio_file = await generate_speech(
                text=text,
                speaker=speaker,
                speed=voice_config.get("speed", 1.0),
                output_path=output_path
            )
            
            # 音声長取得（簡易推定）
            estimated_duration = len(text) * 0.1  # 文字数 × 0.1秒の概算
            total_duration += estimated_duration
            
            file_info = {
                "path": audio_file,
                "speaker": speaker,
                "text": text,
                "estimated_duration": estimated_duration
            }
            
            section_files.append(file_info)
            audio_files.append(file_info)
        
        section_audios[section_title] = section_files
    
    result = {
        "script_title": script_data.get("title", "無題"),
        "output_directory": str(output_dir),
        "section_audios": section_audios,
        "all_files": audio_files,
        "total_files": len(audio_files),
        "total_duration": total_duration,
        "voice_settings": default_voice_settings
    }
    
    logger.info(f"スクリプト音声生成完了: {len(audio_files)}ファイル, 推定{total_duration:.1f}秒")
    return result


async def batch_generate_audio(
    text_list: List[str],
    speaker: Union[str, int] = "reimu",
    output_dir: Optional[Union[str, Path]] = None,
    filename_prefix: str = "audio",
    speed: float = 1.0
) -> List[str]:
    """
    複数のテキストから音声を一括生成する
    
    Args:
        text_list: テキストのリスト
        speaker: 話者
        output_dir: 出力ディレクトリ
        filename_prefix: ファイル名のプレフィックス
        speed: 読み上げ速度
    
    Returns:
        List[str]: 生成された音声ファイルのパスリスト
    
    Examples:
        >>> texts = ["おはよう", "こんにちは", "こんばんは"]
        >>> audio_files = await batch_generate_audio(texts, speaker="marisa")
        >>> for text, file in zip(texts, audio_files):
        ...     print(f"'{text}' -> {file}")
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    audio_files = []
    
    for i, text in enumerate(text_list):
        if not text.strip():
            continue
        
        filename = f"{filename_prefix}_{i+1:03d}.wav"
        output_path = output_dir / filename
        
        audio_file = await generate_speech(
            text=text,
            speaker=speaker,
            speed=speed,
            output_path=output_path
        )
        
        audio_files.append(audio_file)
    
    logger.info(f"一括音声生成完了: {len(audio_files)}ファイル -> {output_dir}")
    return audio_files


def get_available_speakers() -> Dict[str, int]:
    """
    利用可能な話者の一覧を取得する
    
    Returns:
        Dict[str, int]: 話者名と話者IDの辞書
    
    Examples:
        >>> speakers = get_available_speakers()
        >>> print("利用可能な話者:")
        >>> for name, speaker_id in speakers.items():
        ...     print(f"  {name}: {speaker_id}")
    """
    return DEFAULT_SPEAKERS.copy()


async def test_tts_connection(server_url: str = "http://127.0.0.1:10101") -> bool:
    """
    TTS サーバーとの接続をテストする
    
    Args:
        server_url: サーバーURL
    
    Returns:
        bool: 接続成功の場合True
    
    Examples:
        >>> is_connected = await test_tts_connection()
        >>> if is_connected:
        ...     print("TTS サーバーに接続できました")
        >>> else:
        ...     print("TTS サーバーに接続できません")
    """
    try:
        async with AivisSpeechClient(base_url=server_url) as client:
            speakers = await client.get_speakers()
            return len(speakers) > 0
    except Exception as e:
        logger.warning(f"TTS 接続テスト失敗: {e}")
        return False


def _resolve_speaker_id(speaker: Union[str, int]) -> int:
    """話者名またはIDを話者IDに変換"""
    if isinstance(speaker, int):
        return speaker
    
    if isinstance(speaker, str):
        speaker_lower = speaker.lower()
        if speaker_lower in DEFAULT_SPEAKERS:
            return DEFAULT_SPEAKERS[speaker_lower]
    
    # デフォルトは霊夢
    logger.warning(f"不明な話者: {speaker}, デフォルト(reimu)を使用")
    return DEFAULT_SPEAKERS["reimu"]


# エラーハンドリング付きの安全な音声生成
async def safe_generate_speech(
    text: str,
    speaker: Union[str, int] = "reimu",
    speed: float = 1.0,
    max_retries: int = 3,
    fallback_text: str = "音声生成に失敗しました。"
) -> Optional[str]:
    """
    エラーハンドリング付きの安全な音声生成
    
    Args:
        text: 読み上げるテキスト
        speaker: 話者
        speed: 速度
        max_retries: 最大リトライ回数
        fallback_text: 失敗時のフォールバックテキスト
    
    Returns:
        Optional[str]: 音声ファイルパス（失敗時はNone）
    """
    for attempt in range(max_retries + 1):
        try:
            return await generate_speech(text, speaker, speed)
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"音声生成リトライ {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(1.0)  # 1秒待機
            else:
                logger.error(f"音声生成に失敗しました（{max_retries + 1}回試行）: {e}")
                
                # フォールバック音声生成を試行
                try:
                    return await generate_speech(fallback_text, speaker, speed)
                except Exception:
                    logger.error("フォールバック音声生成も失敗しました")
                    return None 