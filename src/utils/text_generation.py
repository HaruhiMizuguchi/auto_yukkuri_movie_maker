"""
テキスト生成高レベル関数

他のファイルから簡単に使える、シンプルなテキスト生成関数を提供します。
内部的に llm_client を使用しますが、呼び出し側は複雑な設定を意識する必要がありません。

使用例:
    from src.utils.text_generation import generate_text, generate_yukkuri_script
    
    # 基本的なテキスト生成
    text = await generate_text("こんにちはと挨拶してください")
    
    # ゆっくり動画台本生成
    script = await generate_yukkuri_script("Python入門", duration_minutes=3)
"""

import os
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Union
from dotenv import load_dotenv

from ..api.llm_client import (
    GeminiLLMClient,
    GeminiRequest, 
    GeminiResponse,
    ModelType,
    OutputFormat,
    GeminiAPIError,
    ContentBlockedError
)

# ログ設定
logger = logging.getLogger(__name__)

# APIキーの自動読み込み
load_dotenv()
_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not _API_KEY:
    logger.warning("GEMINI_API_KEY が設定されていません。generate_text系関数は使用できません。")


async def generate_text(
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    model: str = "gemini-2.0-flash"
) -> str:
    """
    シンプルなテキスト生成関数
    
    Args:
        prompt: 生成指示文
        temperature: 創造性 (0.0=決定的, 1.0=創造的)
        max_tokens: 最大出力トークン数
        model: 使用モデル名
    
    Returns:
        生成されたテキスト
        
    Raises:
        ValueError: APIキーが設定されていない場合
        Exception: 生成に失敗した場合
    """
    if not _API_KEY:
        raise ValueError("GEMINI_API_KEY が設定されていません")
    
    try:
        # モデル名から ModelType に変換
        model_type = _get_model_type(model)
        
        async with GeminiLLMClient(api_key=_API_KEY) as client:
            request = GeminiRequest(
                prompt=prompt,
                model=model_type,
                temperature=temperature,
                max_output_tokens=max_tokens
            )
            response = await client.generate_text(request)
            return response.text
            
    except (GeminiAPIError, ContentBlockedError) as e:
        logger.error(f"テキスト生成エラー: {e}")
        raise Exception(f"テキスト生成に失敗しました: {e}")
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        raise


async def generate_yukkuri_script(
    theme: str,
    duration_minutes: int = 3,
    speakers: List[str] = None,
    tone: str = "casual"
) -> Dict[str, Any]:
    """
    ゆっくり動画台本生成関数
    
    Args:
        theme: 動画のテーマ
        duration_minutes: 目標時間（分）
        speakers: 話者リスト（デフォルト: ["reimu", "marisa"]）
        tone: 口調（"casual", "formal", "funny"等）
    
    Returns:
        構造化された台本データ
        {
            "title": "動画タイトル",
            "speakers": ["reimu", "marisa"],
            "sections": [
                {
                    "section_name": "導入",
                    "duration_seconds": 30,
                    "dialogue": [
                        {"speaker": "reimu", "text": "こんにちは！"},
                        {"speaker": "marisa", "text": "今日は〜について話すぜ！"}
                    ]
                }
            ],
            "total_estimated_duration": 180
        }
    """
    if speakers is None:
        speakers = ["reimu", "marisa"]
    
    speakers_json = json.dumps(speakers)
    
    prompt = f"""
    ゆっくり動画の台本を作成してください。

    【条件】
    - テーマ: {theme}
    - 動画の長さ: {duration_minutes}分程度
    - 話者: {', '.join(speakers)}
    - 口調: {tone}

    【出力形式】
    以下のJSON形式で出力してください:
    {{
        "title": "動画タイトル",
        "speakers": {speakers_json},
        "sections": [
            {{
                "section_name": "導入",
                "duration_seconds": 30,
                "dialogue": [
                    {{"speaker": "reimu", "text": "セリフ内容"}},
                    {{"speaker": "marisa", "text": "セリフ内容"}}
                ]
            }}
        ],
        "total_estimated_duration": {duration_minutes * 60}
    }}

    セクションは「導入」「本編」「まとめ」の3つに分けてください。
    自然な会話形式で、わかりやすく面白い内容にしてください。
    """
    
    try:
        async with GeminiLLMClient(api_key=_API_KEY) as client:
            request = GeminiRequest(
                prompt=prompt,
                output_format=OutputFormat.JSON,
                temperature=0.8,
                max_output_tokens=2000
            )
            response = await client.generate_text(request)
            result = json.loads(response.text)
            # レスポンスがリスト形式の場合、最初の要素を返す
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析エラー: {e}")
        raise Exception("台本の生成に失敗しました（JSON形式エラー）")
    except Exception as e:
        logger.error(f"台本生成エラー: {e}")
        raise Exception(f"台本生成に失敗しました: {e}")


async def generate_video_title(
    theme: str,
    keywords: List[str] = None,
    target_audience: str = "general",
    style: str = "catchy"
) -> List[str]:
    """
    動画タイトル生成関数
    
    Args:
        theme: 動画のテーマ
        keywords: 含めたいキーワードリスト
        target_audience: ターゲット層（"beginner", "intermediate", "advanced", "general"）
        style: タイトルスタイル（"catchy", "informative", "question", "list"）
    
    Returns:
        タイトル候補のリスト（5個）
    """
    keywords_text = f"キーワード: {', '.join(keywords)}" if keywords else ""
    
    prompt = f"""
    YouTube動画のタイトルを5個生成してください。

    【条件】
    - テーマ: {theme}
    - {keywords_text}
    - ターゲット層: {target_audience}
    - スタイル: {style}
    
    【要件】
    - クリック率（CTR）が高くなるような魅力的なタイトル
    - 30文字以内
    - 検索されやすいキーワードを含む
    - スタイルに応じた形式で作成

    JSON形式で以下のように出力してください:
    {{
        "titles": [
            "タイトル1",
            "タイトル2", 
            "タイトル3",
            "タイトル4",
            "タイトル5"
        ]
    }}
    """
    
    try:
        async with GeminiLLMClient(api_key=_API_KEY) as client:
            result = await client.generate_structured_output(
                prompt=prompt,
                schema={
                    "type": "object",
                    "properties": {
                        "titles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 5,
                            "maxItems": 5
                        }
                    },
                    "required": ["titles"]
                },
                temperature=0.9
            )
            return result["titles"]
            
    except Exception as e:
        logger.error(f"タイトル生成エラー: {e}")
        raise Exception(f"タイトル生成に失敗しました: {e}")


async def generate_json_data(
    prompt: str,
    schema: Dict[str, Any],
    temperature: float = 0.7
) -> Dict[str, Any]:
    """
    JSON形式データ生成関数
    
    Args:
        prompt: 生成指示文
        schema: JSONスキーマ辞書
        temperature: 創造性
    
    Returns:
        生成されたJSONデータ
    """
    try:
        async with GeminiLLMClient(api_key=_API_KEY) as client:
            result = await client.generate_structured_output(
                prompt=prompt,
                schema=schema,
                temperature=temperature
            )
            return result
            
    except Exception as e:
        logger.error(f"JSON生成エラー: {e}")
        raise Exception(f"JSON生成に失敗しました: {e}")


async def generate_quiz(
    topic: str,
    difficulty: str = "medium",
    question_count: int = 1
) -> List[Dict[str, Any]]:
    """
    クイズ生成関数
    
    Args:
        topic: クイズのトピック
        difficulty: 難易度（"easy", "medium", "hard"）
        question_count: 問題数
    
    Returns:
        クイズ問題のリスト
    """
    schema = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4
                        },
                        "correct_answer": {"type": "integer", "minimum": 0, "maximum": 3},
                        "explanation": {"type": "string"}
                    },
                    "required": ["question", "options", "correct_answer", "explanation"]
                },
                "minItems": question_count,
                "maxItems": question_count
            }
        },
        "required": ["questions"]
    }
    
    prompt = f"""
    {topic}に関する{difficulty}レベルの4択クイズを{question_count}問作成してください。
    
    【要件】
    - 正確で教育的な内容
    - 適切な難易度
    - 明確で紛らわしくない選択肢
    - 詳しい解説付き
    """
    
    try:
        result = await generate_json_data(prompt, schema, temperature=0.5)
        return result["questions"]
        
    except Exception as e:
        logger.error(f"クイズ生成エラー: {e}")
        raise Exception(f"クイズ生成に失敗しました: {e}")


async def translate_text(
    text: str,
    target_language: str = "English",
    source_language: str = "auto"
) -> str:
    """
    テキスト翻訳関数
    
    Args:
        text: 翻訳したいテキスト
        target_language: 翻訳先言語
        source_language: 翻訳元言語（"auto"で自動検出）
    
    Returns:
        翻訳されたテキスト
    """
    prompt = f"""
    以下のテキストを{target_language}に翻訳してください。
    
    【翻訳元テキスト】
    {text}
    
    【要件】
    - 自然で読みやすい翻訳
    - 文脈を考慮した適切な表現
    - 翻訳結果のみを出力
    """
    
    return await generate_text(prompt, temperature=0.3)


async def summarize_text(text: str, max_length: int = 200) -> str:
    """
    テキスト要約関数
    
    Args:
        text: 要約したいテキスト
        max_length: 最大文字数
    
    Returns:
        要約されたテキスト
    """
    prompt = f"""
    以下のテキストを{max_length}文字以内で要約してください。
    重要なポイントを漏らさず、簡潔にまとめてください。
    
    【テキスト】
    {text}
    """
    
    return await generate_text(prompt, temperature=0.3, max_tokens=max_length//2)


def _get_model_type(model_name: str) -> ModelType:
    """モデル名からModelTypeを取得"""
    model_mapping = {
        "gemini-2.0-flash": ModelType.GEMINI_2_0_FLASH,
        "gemini-2.0-flash-exp": ModelType.GEMINI_2_0_FLASH_EXP,
        "gemini-1.5-flash": ModelType.GEMINI_1_5_FLASH,
        "gemini-1.5-pro": ModelType.GEMINI_1_5_PRO,
    }
    return model_mapping.get(model_name, ModelType.GEMINI_2_0_FLASH)


# エラーハンドリング用のヘルパー関数
async def safe_generate_text(
    prompt: str,
    fallback_text: str = "生成に失敗しました",
    **kwargs
) -> str:
    """
    エラー時にフォールバックテキストを返すテキスト生成関数
    """
    try:
        return await generate_text(prompt, **kwargs)
    except Exception as e:
        logger.warning(f"テキスト生成失敗、フォールバック使用: {e}")
        return fallback_text


# バッチ処理用関数
async def generate_multiple_texts(
    prompts: List[str],
    delay_seconds: float = 2.0,
    **kwargs
) -> List[str]:
    """
    複数のテキストを順次生成（レート制限対応）
    
    Args:
        prompts: プロンプトのリスト
        delay_seconds: リクエスト間の待機時間
        **kwargs: generate_textに渡すオプション
    
    Returns:
        生成されたテキストのリスト
    """
    results = []
    for i, prompt in enumerate(prompts):
        try:
            text = await generate_text(prompt, **kwargs)
            results.append(text)
            
            # レート制限対策の待機（最後の要素以外）
            if i < len(prompts) - 1:
                await asyncio.sleep(delay_seconds)
                
        except Exception as e:
            logger.error(f"プロンプト {i+1} の生成に失敗: {e}")
            results.append(f"[生成失敗: {e}]")
    
    return results 