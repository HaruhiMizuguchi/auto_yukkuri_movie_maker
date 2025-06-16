"""
画像生成ユーティリティ

ImageGenerationClientの複雑さを隠し、シンプルで使いやすい高レベル関数を提供します。
"""

import asyncio
import logging
import os
import tempfile
from typing import Optional, List, Dict, Any, Union, Tuple
from pathlib import Path
import base64
from PIL import Image
import io

from ..api.image_client import (
    ImageGenerationClient,
    ImageRequest,
    ImageEditRequest,
    ImageResponse,
    ResponseModality,
    ImageFormat,
    ImageGenerationError
)

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_MODEL = "gemini-2.0-flash-preview-image-generation"
DEFAULT_RESPONSE_MODALITIES = [ResponseModality.TEXT, ResponseModality.IMAGE]


async def generate_image(
    prompt: str,
    output_path: Optional[Union[str, Path]] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None
) -> Tuple[str, str]:
    """
    テキストから画像を生成する（最もシンプルな関数）
    
    Args:
        prompt: 画像生成プロンプト
        output_path: 出力ファイルパス（指定しない場合は一時ファイル）
        api_key: Gemini API キー（指定しない場合は環境変数から取得）
        temperature: 生成の創造性（0.0〜1.0）
        max_output_tokens: 最大出力トークン数
    
    Returns:
        Tuple[str, str]: (生成された画像ファイルのパス, 画像の説明テキスト)
    
    Examples:
        >>> # 最もシンプルな使用例
        >>> image_path, description = await generate_image("美しい富士山の風景")
        >>> print(f"画像: {image_path}, 説明: {description}")
        
        >>> # ファイル保存先を指定
        >>> image_path, description = await generate_image(
        ...     "猫が庭で遊んでいる様子",
        ...     output_path="cat_in_garden.png"
        ... )
    """
    try:
        # API キー取得
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません")
        
        # リクエスト作成
        request = ImageRequest(
            prompt=prompt,
            response_modalities=DEFAULT_RESPONSE_MODALITIES,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        # 画像生成
        async with ImageGenerationClient(api_key=api_key) as client:
            responses = await client.generate_images(request)
        
        if not responses:
            raise RuntimeError("画像が生成されませんでした")
        
        response = responses[0]
        
        # ファイル保存
        if output_path is None:
            # 一時ファイルを作成
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", 
                delete=False
            )
            output_path = temp_file.name
            temp_file.close()
        
        response.save_image(output_path)
        
        description = response.text_content or "画像が生成されました"
        
        logger.info(f"画像生成完了: {prompt[:30]}... -> {output_path}")
        return str(output_path), description
        
    except ImageGenerationError as e:
        logger.error(f"画像生成 API エラー: {e}")
        raise ValueError(f"画像生成に失敗しました: {e}")
    except Exception as e:
        logger.error(f"画像生成エラー: {e}")
        raise RuntimeError(f"画像生成中に予期しないエラーが発生しました: {e}")


async def edit_image(
    prompt: str,
    input_image_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7
) -> Tuple[str, str]:
    """
    既存の画像を編集する
    
    Args:
        prompt: 編集指示プロンプト
        input_image_path: 入力画像ファイルパス
        output_path: 出力ファイルパス（指定しない場合は一時ファイル）
        api_key: Gemini API キー
        temperature: 生成の創造性
    
    Returns:
        Tuple[str, str]: (編集された画像ファイルのパス, 編集の説明テキスト)
    
    Examples:
        >>> # 画像に帽子を追加
        >>> edited_path, description = await edit_image(
        ...     "この人に帽子を追加してください",
        ...     "person.jpg"
        ... )
        
        >>> # 背景を変更
        >>> edited_path, description = await edit_image(
        ...     "背景を海に変更してください",
        ...     "portrait.png",
        ...     output_path="portrait_with_sea.png"
        ... )
    """
    try:
        # API キー取得
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY または GOOGLE_API_KEY 環境変数が設定されていません")
        
        # 入力画像読み込み
        input_path = Path(input_image_path)
        if not input_path.exists():
            raise FileNotFoundError(f"入力画像ファイルが見つかりません: {input_path}")
        
        with open(input_path, 'rb') as f:
            image_data = f.read()
        
        # リクエスト作成
        request = ImageEditRequest(
            prompt=prompt,
            image_data=image_data,
            response_modalities=DEFAULT_RESPONSE_MODALITIES,
            temperature=temperature
        )
        
        # 画像編集
        async with ImageGenerationClient(api_key=api_key) as client:
            responses = await client.edit_image(request)
        
        if not responses:
            raise RuntimeError("編集された画像が生成されませんでした")
        
        response = responses[0]
        
        # ファイル保存
        if output_path is None:
            # 一時ファイルを作成
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", 
                delete=False
            )
            output_path = temp_file.name
            temp_file.close()
        
        response.save_image(output_path)
        
        description = response.text_content or "画像が編集されました"
        
        logger.info(f"画像編集完了: {prompt[:30]}... -> {output_path}")
        return str(output_path), description
        
    except ImageGenerationError as e:
        logger.error(f"画像編集 API エラー: {e}")
        raise ValueError(f"画像編集に失敗しました: {e}")
    except Exception as e:
        logger.error(f"画像編集エラー: {e}")
        raise RuntimeError(f"画像編集中に予期しないエラーが発生しました: {e}")


async def generate_yukkuri_thumbnails(
    video_title: str,
    video_description: str,
    output_dir: Optional[Union[str, Path]] = None,
    api_key: Optional[str] = None,
    num_variations: int = 3
) -> List[Dict[str, str]]:
    """
    ゆっくり動画用のサムネイル画像を生成する
    
    Args:
        video_title: 動画タイトル
        video_description: 動画の説明
        output_dir: 出力ディレクトリ
        api_key: Gemini API キー
        num_variations: 生成するバリエーション数
    
    Returns:
        List[Dict[str, str]]: サムネイル情報のリスト
                             [{"path": "ファイルパス", "description": "説明", "style": "スタイル"}]
    
    Examples:
        >>> thumbnails = await generate_yukkuri_thumbnails(
        ...     "Python入門講座",
        ...     "初心者向けのPythonプログラミング解説動画"
        ... )
        >>> for thumb in thumbnails:
        ...     print(f"サムネイル: {thumb['path']}")
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # サムネイルスタイルのバリエーション
    styles = [
        "アニメ風のカラフルで目を引くデザイン",
        "シンプルで読みやすいテキスト重視のデザイン",
        "インパクトのある大胆なデザイン"
    ]
    
    thumbnails = []
    
    for i in range(min(num_variations, len(styles))):
        style = styles[i]
        
        # プロンプト作成
        prompt = f"""
        YouTube動画のサムネイル画像を作成してください。
        
        動画タイトル: {video_title}
        動画内容: {video_description}
        デザインスタイル: {style}
        
        要件:
        - 16:9の横長比率
        - タイトルテキストを含む
        - 視聴者の注意を引く魅力的なデザイン
        - YouTubeサムネイルとして適切
        """
        
        try:
            # ファイル名生成
            filename = f"thumbnail_{i+1:02d}_{style.split('の')[0]}.png"
            output_path = output_dir / filename
            
            # 画像生成
            image_path, description = await generate_image(
                prompt=prompt,
                output_path=output_path,
                api_key=api_key,
                temperature=0.8
            )
            
            thumbnail_info = {
                "path": image_path,
                "description": description,
                "style": style,
                "title": video_title
            }
            
            thumbnails.append(thumbnail_info)
            
        except Exception as e:
            logger.error(f"サムネイル生成エラー (スタイル{i+1}): {e}")
            continue
    
    logger.info(f"サムネイル生成完了: {len(thumbnails)}個 -> {output_dir}")
    return thumbnails


async def batch_generate_images(
    prompts: List[str],
    output_dir: Optional[Union[str, Path]] = None,
    api_key: Optional[str] = None,
    filename_prefix: str = "generated",
    temperature: float = 0.7
) -> List[Dict[str, str]]:
    """
    複数のプロンプトから画像を一括生成する
    
    Args:
        prompts: プロンプトのリスト
        output_dir: 出力ディレクトリ
        api_key: Gemini API キー
        filename_prefix: ファイル名のプレフィックス
        temperature: 生成の創造性
    
    Returns:
        List[Dict[str, str]]: 生成結果のリスト
                             [{"path": "ファイルパス", "description": "説明", "prompt": "プロンプト"}]
    
    Examples:
        >>> prompts = ["美しい夕日", "雪山の風景", "都市の夜景"]
        >>> results = await batch_generate_images(prompts)
        >>> for result in results:
        ...     print(f"'{result['prompt']}' -> {result['path']}")
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for i, prompt in enumerate(prompts):
        if not prompt.strip():
            continue
        
        try:
            # ファイル名生成
            filename = f"{filename_prefix}_{i+1:03d}.png"
            output_path = output_dir / filename
            
            # 画像生成
            image_path, description = await generate_image(
                prompt=prompt,
                output_path=output_path,
                api_key=api_key,
                temperature=temperature
            )
            
            result = {
                "path": image_path,
                "description": description,
                "prompt": prompt
            }
            
            results.append(result)
            
        except Exception as e:
            logger.error(f"バッチ画像生成エラー (プロンプト: {prompt[:30]}...): {e}")
            continue
    
    logger.info(f"バッチ画像生成完了: {len(results)}個 -> {output_dir}")
    return results


async def test_image_generation(api_key: Optional[str] = None) -> bool:
    """
    画像生成機能の接続テスト
    
    Args:
        api_key: Gemini API キー
    
    Returns:
        bool: テスト成功の場合True
    
    Examples:
        >>> is_working = await test_image_generation()
        >>> if is_working:
        ...     print("画像生成機能が利用可能です")
        >>> else:
        ...     print("画像生成機能に問題があります")
    """
    try:
        # API キー確認
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.warning("API キーが設定されていません")
                return False
        
        # 簡単なテスト画像生成
        test_prompt = "シンプルな青い円"
        
        image_path, description = await generate_image(
            prompt=test_prompt,
            api_key=api_key,
            temperature=0.5
        )
        
        # ファイル確認
        if Path(image_path).exists() and Path(image_path).stat().st_size > 0:
            logger.info(f"画像生成テスト成功: {image_path}")
            return True
        else:
            logger.warning("画像ファイルが正常に作成されませんでした")
            return False
            
    except Exception as e:
        logger.warning(f"画像生成テスト失敗: {e}")
        return False


def get_supported_formats() -> List[str]:
    """
    サポートされている画像フォーマット一覧を取得
    
    Returns:
        List[str]: サポートフォーマットのリスト
    
    Examples:
        >>> formats = get_supported_formats()
        >>> print("サポートフォーマット:", formats)
    """
    return [format.value for format in ImageFormat]


# エラーハンドリング付きの安全な画像生成
async def safe_generate_image(
    prompt: str,
    output_path: Optional[Union[str, Path]] = None,
    api_key: Optional[str] = None,
    max_retries: int = 3,
    fallback_prompt: str = "シンプルな風景画"
) -> Optional[Tuple[str, str]]:
    """
    エラーハンドリング付きの安全な画像生成
    
    Args:
        prompt: 画像生成プロンプト
        output_path: 出力ファイルパス
        api_key: Gemini API キー
        max_retries: 最大リトライ回数
        fallback_prompt: 失敗時のフォールバックプロンプト
    
    Returns:
        Optional[Tuple[str, str]]: (画像ファイルパス, 説明)（失敗時はNone）
    """
    for attempt in range(max_retries + 1):
        try:
            current_prompt = prompt if attempt == 0 else fallback_prompt
            return await generate_image(
                prompt=current_prompt,
                output_path=output_path,
                api_key=api_key
            )
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"画像生成リトライ {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(2.0)  # 2秒待機
            else:
                logger.error(f"画像生成に失敗しました（{max_retries + 1}回試行）: {e}")
                return None 