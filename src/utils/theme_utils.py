"""
テーマ選定ユーティリティ

ThemeSelectorの複雑な依存関係注入を隠し、
シンプルで使いやすい高レベル関数を提供します。
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
import json
from pathlib import Path

from ..modules.theme_selector import (
    ThemeSelector,
    ThemeSelectionInput,
    ThemeSelectionOutput,
    UserPreferences,
    ThemeCandidate,
    SelectedTheme,
    DatabaseDataAccess,
    GeminiThemeLLM
)
from ..core.project_repository import ProjectRepository
from ..core.config_manager import ConfigManager
from ..core.database_manager import DatabaseManager
from ..api.llm_client import GeminiLLMClient

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_USER_PREFERENCES = UserPreferences(
    genre_history=[],
    preferred_genres=["教育", "プログラミング"],
    excluded_genres=["ゲーム", "エンターテインメント"],
    target_audience="一般",
    content_style="親しみやすい"
)

# グローバルインスタンス（遅延初期化）
_theme_selector: Optional[ThemeSelector] = None


def _get_theme_selector() -> ThemeSelector:
    """ThemeSelectorのシングルトンインスタンスを取得"""
    global _theme_selector
    
    if _theme_selector is None:
        # 依存関係を初期化
        db_manager = DatabaseManager("data/yukkuri_tool.db")
        db_manager.initialize()
        
        project_repository = ProjectRepository(db_manager)
        config_manager = ConfigManager()
        
        # API キーの取得（環境変数から）
        import os
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY環境変数が設定されていません")
        
        llm_client = GeminiLLMClient(api_key=api_key)
        
        # データアクセスとLLMインターフェースの設定
        data_access = DatabaseDataAccess(project_repository, config_manager)
        llm_interface = GeminiThemeLLM(llm_client)
        
        _theme_selector = ThemeSelector(data_access, llm_interface)
    
    return _theme_selector


def select_theme(
    project_id: str,
    preferred_genres: Optional[List[str]] = None,
    excluded_genres: Optional[List[str]] = None,
    target_audience: str = "一般",
    content_style: str = "親しみやすい",
    max_candidates: int = 10
) -> Dict[str, Any]:
    """
    プロジェクトのテーマを自動選定する（最もシンプルな関数）
    
    Args:
        project_id: プロジェクトID
        preferred_genres: 好みのジャンル
        excluded_genres: 除外ジャンル
        target_audience: ターゲット層
        content_style: コンテンツスタイル
        max_candidates: 最大候補数
    
    Returns:
        Dict[str, Any]: 選定結果
    
    Examples:
        >>> # 最もシンプルな使用例
        >>> result = select_theme("project-123")
        >>> print(f"選定テーマ: {result['selected_theme']['theme']}")
        
        >>> # カスタム設定
        >>> result = select_theme(
        ...     project_id="project-456",
        ...     preferred_genres=["プログラミング", "AI"],
        ...     excluded_genres=["ゲーム"],
        ...     target_audience="エンジニア",
        ...     content_style="実践的"
        ... )
    """
    try:
        # ユーザー設定作成
        user_preferences = UserPreferences(
            genre_history=[],  # 履歴は空で開始
            preferred_genres=preferred_genres or DEFAULT_USER_PREFERENCES.preferred_genres,
            excluded_genres=excluded_genres or DEFAULT_USER_PREFERENCES.excluded_genres,
            target_audience=target_audience,
            content_style=content_style
        )
        
        # 入力データ作成
        input_data = ThemeSelectionInput(
            project_id=project_id,
            user_preferences=user_preferences,
            llm_config={"model": "gemini-2.0-flash"},
            max_candidates=max_candidates
        )
        
        # テーマ選定実行
        theme_selector = _get_theme_selector()
        output = theme_selector.select_theme(input_data)
        
        # 結果を辞書形式に変換
        result = {
            "selected_theme": {
                "theme": output.selected_theme.theme,
                "category": output.selected_theme.category,
                "target_length_minutes": output.selected_theme.target_length_minutes,
                "description": output.selected_theme.description,
                "selection_reason": output.selected_theme.selection_reason,
                "generation_timestamp": output.selected_theme.generation_timestamp.isoformat()
            },
            "candidates": [
                {
                    "theme": candidate.theme,
                    "category": candidate.category,
                    "target_length_minutes": candidate.target_length_minutes,
                    "description": candidate.description,
                    "appeal_points": candidate.appeal_points,
                    "total_score": candidate.total_score,
                    "difficulty_score": candidate.difficulty_score,
                    "entertainment_score": candidate.entertainment_score,
                    "trend_score": candidate.trend_score
                }
                for candidate in output.candidates
            ],
            "metadata": output.selection_metadata
        }
        
        logger.info(f"テーマ選定完了: {output.selected_theme.theme} (プロジェクト: {project_id})")
        return result
        
    except Exception as e:
        logger.error(f"テーマ選定エラー: {e}")
        raise RuntimeError(f"テーマ選定に失敗しました: {e}")


def generate_theme_candidates(
    preferred_genres: Optional[List[str]] = None,
    excluded_genres: Optional[List[str]] = None,
    target_audience: str = "一般",
    content_style: str = "親しみやすい",
    count: int = 10
) -> List[Dict[str, Any]]:
    """
    テーマ候補のみを生成する（プロジェクトIDなし）
    
    Args:
        preferred_genres: 好みのジャンル
        excluded_genres: 除外ジャンル
        target_audience: ターゲット層
        content_style: コンテンツスタイル
        count: 生成する候補数
    
    Returns:
        List[Dict[str, Any]]: テーマ候補のリスト
    
    Examples:
        >>> # プログラミング系のテーマ候補を生成
        >>> candidates = generate_theme_candidates(
        ...     preferred_genres=["プログラミング", "技術"],
        ...     count=5
        ... )
        >>> for candidate in candidates:
        ...     print(f"{candidate['theme']} (スコア: {candidate['total_score']:.1f})")
    """
    try:
        # ユーザー設定作成
        user_preferences = UserPreferences(
            genre_history=[],
            preferred_genres=preferred_genres or DEFAULT_USER_PREFERENCES.preferred_genres,
            excluded_genres=excluded_genres or DEFAULT_USER_PREFERENCES.excluded_genres,
            target_audience=target_audience,
            content_style=content_style
        )
        
        # ThemeSelectorからLLMインターフェースを取得
        theme_selector = _get_theme_selector()
        candidates = theme_selector.llm_interface.generate_theme_candidates(
            user_preferences, count
        )
        
        # 評価・ランキング実行
        ranked_candidates = theme_selector.llm_interface.evaluate_and_rank_themes(
            candidates, user_preferences
        )
        
        # 辞書形式に変換
        result = [
            {
                "theme": candidate.theme,
                "category": candidate.category,
                "target_length_minutes": candidate.target_length_minutes,
                "description": candidate.description,
                "appeal_points": candidate.appeal_points,
                "total_score": candidate.total_score,
                "difficulty_score": candidate.difficulty_score,
                "entertainment_score": candidate.entertainment_score,
                "trend_score": candidate.trend_score
            }
            for candidate in ranked_candidates
        ]
        
        logger.info(f"テーマ候補生成完了: {len(result)}件")
        return result
        
    except Exception as e:
        logger.error(f"テーマ候補生成エラー: {e}")
        raise RuntimeError(f"テーマ候補の生成に失敗しました: {e}")


def get_theme_suggestions_by_keywords(
    keywords: List[str],
    target_audience: str = "一般",
    max_suggestions: int = 5
) -> List[Dict[str, Any]]:
    """
    キーワードベースでテーマを提案する
    
    Args:
        keywords: キーワードリスト
        target_audience: ターゲット層
        max_suggestions: 最大提案数
    
    Returns:
        List[Dict[str, Any]]: テーマ提案のリスト
    
    Examples:
        >>> # "Python", "機械学習"からテーマ提案
        >>> suggestions = get_theme_suggestions_by_keywords(
        ...     keywords=["Python", "機械学習"],
        ...     target_audience="プログラマー"
        ... )
        >>> for suggestion in suggestions:
        ...     print(f"{suggestion['theme']}: {suggestion['description']}")
    """
    try:
        # キーワードから好みのジャンルを推定
        programming_keywords = ["Python", "JavaScript", "Java", "C++", "プログラミング", "コーディング"]
        ai_keywords = ["AI", "機械学習", "深層学習", "ニューラルネットワーク", "データサイエンス"]
        science_keywords = ["物理", "化学", "生物", "数学", "科学", "実験"]
        
        inferred_genres = ["教育"]  # デフォルト
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if any(prog_kw.lower() in keyword_lower for prog_kw in programming_keywords):
                inferred_genres.append("プログラミング")
            if any(ai_kw.lower() in keyword_lower for ai_kw in ai_keywords):
                inferred_genres.append("AI")
            if any(sci_kw.lower() in keyword_lower for sci_kw in science_keywords):
                inferred_genres.append("科学")
        
        # 重複除去
        inferred_genres = list(set(inferred_genres))
        
        # テーマ候補生成
        candidates = generate_theme_candidates(
            preferred_genres=inferred_genres,
            target_audience=target_audience,
            count=max_suggestions * 2  # 多めに生成してフィルタリング
        )
        
        # キーワードマッチングでスコア調整
        for candidate in candidates:
            keyword_match_score = 0
            theme_text = f"{candidate['theme']} {candidate['description']}".lower()
            
            for keyword in keywords:
                if keyword.lower() in theme_text:
                    keyword_match_score += 1
            
            # キーワードマッチボーナスを追加
            candidate['keyword_match_score'] = keyword_match_score
            candidate['adjusted_score'] = candidate['total_score'] + keyword_match_score * 2
        
        # 調整済みスコアでソート
        candidates.sort(key=lambda x: x['adjusted_score'], reverse=True)
        
        logger.info(f"キーワードベーステーマ提案: {keywords} -> {len(candidates[:max_suggestions])}件")
        return candidates[:max_suggestions]
        
    except Exception as e:
        logger.error(f"キーワードベーステーマ提案エラー: {e}")
        raise RuntimeError(f"テーマ提案の生成に失敗しました: {e}")


def get_popular_themes(
    category: Optional[str] = None,
    target_audience: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    人気のテーマを取得する（簡易実装）
    
    Args:
        category: カテゴリでフィルタ
        target_audience: ターゲット層でフィルタ
        limit: 取得件数
    
    Returns:
        List[Dict[str, Any]]: 人気テーマのリスト
    
    Examples:
        >>> # 教育カテゴリの人気テーマ
        >>> popular = get_popular_themes(category="教育", limit=5)
        >>> for theme in popular:
        ...     print(f"{theme['theme']} (人気度: {theme['popularity_score']:.1f})")
    """
    try:
        # 簡易的な人気テーマデータ（実際は過去の選択履歴から生成）
        popular_themes_data = [
            {
                "theme": "プログラミング超入門：変数って何？",
                "category": "教育",
                "target_audience": "初心者",
                "popularity_score": 9.5,
                "description": "プログラミングの基本概念である変数について分かりやすく解説"
            },
            {
                "theme": "AIってどうやって動いてるの？",
                "category": "技術",
                "target_audience": "一般",
                "popularity_score": 9.2,
                "description": "人工知能の仕組みを身近な例で説明"
            },
            {
                "theme": "量子コンピューターの不思議な世界",
                "category": "科学",
                "target_audience": "理系",
                "popularity_score": 8.8,
                "description": "量子力学の原理を使った次世代コンピューター"
            },
            {
                "theme": "暗号技術で守られる私たちの生活",
                "category": "技術",
                "target_audience": "一般",
                "popularity_score": 8.5,
                "description": "日常に隠れている暗号技術について解説"
            },
            {
                "theme": "データサイエンスで見える化する世界",
                "category": "教育",
                "target_audience": "ビジネスパーソン",
                "popularity_score": 8.3,
                "description": "データ分析の力で新しい発見をする方法"
            },
            {
                "theme": "ブロックチェーンの仕組みと未来",
                "category": "技術",
                "target_audience": "投資家",
                "popularity_score": 8.0,
                "description": "仮想通貨の基盤技術を分かりやすく解説"
            },
            {
                "theme": "宇宙開発の最前線：火星移住計画",
                "category": "科学",
                "target_audience": "一般",
                "popularity_score": 7.8,
                "description": "人類の火星移住に向けた技術開発"
            },
            {
                "theme": "環境問題とテクノロジーの力",
                "category": "社会",
                "target_audience": "環境意識層",
                "popularity_score": 7.5,
                "description": "技術革新で解決する地球環境問題"
            }
        ]
        
        # フィルタリング
        filtered_themes = popular_themes_data
        
        if category:
            filtered_themes = [t for t in filtered_themes if t["category"] == category]
        
        if target_audience:
            filtered_themes = [t for t in filtered_themes if t["target_audience"] == target_audience]
        
        # 人気度でソート
        filtered_themes.sort(key=lambda x: x["popularity_score"], reverse=True)
        
        result = filtered_themes[:limit]
        logger.info(f"人気テーマ取得: カテゴリ={category}, 対象={target_audience} -> {len(result)}件")
        return result
        
    except Exception as e:
        logger.error(f"人気テーマ取得エラー: {e}")
        return []


def save_theme_to_file(
    theme_data: Dict[str, Any],
    output_path: Optional[str] = None
) -> str:
    """
    テーマデータをJSONファイルに保存する
    
    Args:
        theme_data: テーマデータ
        output_path: 出力ファイルパス（指定しない場合は自動生成）
    
    Returns:
        str: 保存されたファイルパス
    
    Examples:
        >>> theme_result = select_theme("project-123")
        >>> saved_file = save_theme_to_file(theme_result)
        >>> print(f"テーマデータ保存: {saved_file}")
    """
    try:
        if output_path is None:
            # ファイル名を自動生成
            theme_name = theme_data.get("selected_theme", {}).get("theme", "unknown_theme")
            safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in theme_name)
            output_path = f"theme_{safe_name}_{int(hash(str(theme_data)) % 10000):04d}.json"
        
        # ファイル保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(theme_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"テーマデータ保存完了: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"テーマデータ保存エラー: {e}")
        raise RuntimeError(f"テーマデータの保存に失敗しました: {e}")


def load_theme_from_file(file_path: str) -> Dict[str, Any]:
    """
    JSONファイルからテーマデータを読み込む
    
    Args:
        file_path: JSONファイルパス
    
    Returns:
        Dict[str, Any]: テーマデータ
    
    Examples:
        >>> theme_data = load_theme_from_file("theme_python_basic_1234.json")
        >>> print(f"読み込みテーマ: {theme_data['selected_theme']['theme']}")
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            theme_data = json.load(f)
        
        logger.info(f"テーマデータ読み込み完了: {file_path}")
        return theme_data
        
    except Exception as e:
        logger.error(f"テーマデータ読み込みエラー: {e}")
        raise RuntimeError(f"テーマデータの読み込みに失敗しました: {e}")


# エラーハンドリング付きの安全なテーマ選定
def safe_select_theme(
    project_id: str,
    fallback_theme: str = "プログラミング入門",
    **kwargs
) -> Dict[str, Any]:
    """
    エラーハンドリング付きの安全なテーマ選定
    
    Args:
        project_id: プロジェクトID
        fallback_theme: 失敗時のフォールバックテーマ
        **kwargs: select_theme()の引数
    
    Returns:
        Dict[str, Any]: 選定結果（失敗時はフォールバックテーマ）
    """
    try:
        return select_theme(project_id, **kwargs)
    except Exception as e:
        logger.warning(f"テーマ選定に失敗、フォールバックを使用: {e}")
        
        # フォールバックテーマの作成
        from datetime import datetime
        fallback_result = {
            "selected_theme": {
                "theme": fallback_theme,
                "category": "教育",
                "target_length_minutes": 5,
                "description": f"{fallback_theme}について分かりやすく解説します",
                "selection_reason": "自動選定に失敗したためフォールバックテーマを使用",
                "generation_timestamp": datetime.now().isoformat()
            },
            "candidates": [],
            "metadata": {
                "generation_method": "fallback",
                "original_error": str(e),
                "fallback_used": True
            }
        }
        
        return fallback_result 