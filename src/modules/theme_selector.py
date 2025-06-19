"""
テーマ選定モジュール (4-1)

flow_definition.yamlに基づく仕様:
- 入力: データベース（ユーザー設定）+ 設定ファイル（LLM設定）
- 処理: LLMを使用したテーマ候補生成・評価・選定
- 出力: データベース（選択テーマ）+ ファイル（候補一覧JSON）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Protocol
import json
import logging
from pathlib import Path
import uuid
from datetime import datetime

from ..core.project_repository import ProjectRepository
from ..core.config_manager import ConfigManager
from ..api.llm_client import GeminiLLMClient


logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """ユーザー設定データクラス"""
    genre_history: List[str]
    preferred_genres: List[str]
    excluded_genres: List[str]
    target_audience: str
    content_style: str


@dataclass
class ThemeCandidate:
    """テーマ候補データクラス"""
    theme: str
    category: str
    target_length_minutes: int
    description: str
    appeal_points: List[str]
    difficulty_score: float  # 1.0-10.0
    entertainment_score: float  # 1.0-10.0
    trend_score: float  # 1.0-10.0
    total_score: float


@dataclass
class SelectedTheme:
    """選択されたテーマデータクラス"""
    theme: str
    category: str
    target_length_minutes: int
    description: str
    selection_reason: str
    generation_timestamp: datetime


@dataclass
class ThemeSelectionInput:
    """テーマ選定処理の入力データ"""
    project_id: str
    user_preferences: UserPreferences
    llm_config: Dict[str, Any]
    max_candidates: int = 10


@dataclass
class ThemeSelectionOutput:
    """テーマ選定処理の出力データ"""
    selected_theme: SelectedTheme
    candidates: List[ThemeCandidate]
    selection_metadata: Dict[str, Any]


class ThemeSelectorProtocol(Protocol):
    """テーマ選定の抽象インターフェース"""
    
    def select_theme(self, input_data: ThemeSelectionInput) -> ThemeSelectionOutput:
        """テーマ選定を実行"""
        ...


class DataAccessInterface(ABC):
    """データアクセス抽象インターフェース"""
    
    @abstractmethod
    def get_user_preferences(self, project_id: str) -> UserPreferences:
        """ユーザー設定を取得"""
        pass
    
    @abstractmethod
    def save_theme_selection_result(
        self, 
        project_id: str, 
        output: ThemeSelectionOutput
    ) -> None:  
        """テーマ選定結果を保存"""
        pass
    
    @abstractmethod
    def save_theme_candidates_file(
        self, 
        project_id: str, 
        candidates: List[ThemeCandidate]
    ) -> str:
        """テーマ候補をファイルに保存"""
        pass


class LLMInterface(ABC):
    """LLM抽象インターフェース"""
    
    @abstractmethod
    def generate_theme_candidates(
        self, 
        preferences: UserPreferences, 
        count: int
    ) -> List[ThemeCandidate]:
        """テーマ候補を生成"""
        pass
    
    @abstractmethod
    def evaluate_and_rank_themes(
        self, 
        candidates: List[ThemeCandidate], 
        preferences: UserPreferences
    ) -> List[ThemeCandidate]:
        """テーマ候補を評価・ランキング"""
        pass


class DatabaseDataAccess(DataAccessInterface):
    """データベースデータアクセス実装（DAO使用）"""
    
    def __init__(self, repository: ProjectRepository, config_manager: ConfigManager):
        self.repository = repository
        self.config_manager = config_manager
        # DAOを初期化
        from ..dao.theme_selection_dao import ThemeSelectionDAO
        self.dao = ThemeSelectionDAO(repository.db_manager)
    
    def get_user_preferences(self, project_id: str) -> UserPreferences:
        """プロジェクトからユーザー設定を取得"""
        # DAOを使用して設定を取得
        config = self.dao.get_project_config(project_id)
        user_prefs = config.get("user_preferences", {})
        
        return UserPreferences(
            genre_history=user_prefs.get("genre_history", []),
            preferred_genres=user_prefs.get("preferred_genres", ["教育", "エンターテインメント"]),
            excluded_genres=user_prefs.get("excluded_genres", []),
            target_audience=user_prefs.get("target_audience", "一般"),
            content_style=user_prefs.get("content_style", "親しみやすい")
        )
    
    def save_theme_selection_result(
        self, 
        project_id: str, 
        output: ThemeSelectionOutput
    ) -> None:
        """テーマ選定結果をデータベースに保存"""
        # DAOを使用してプロジェクトテーマを更新
        self.dao.update_project_theme(
            project_id=project_id,
            theme=output.selected_theme.theme,
            target_length_minutes=output.selected_theme.target_length_minutes
        )
        
        # DAOを使用してワークフローステップ結果を保存
        # datetimeオブジェクトをISO文字列に変換
        output_dict = asdict(output)
        if 'selected_theme' in output_dict and 'generation_timestamp' in output_dict['selected_theme']:
            timestamp = output_dict['selected_theme']['generation_timestamp']
            if isinstance(timestamp, datetime):
                output_dict['selected_theme']['generation_timestamp'] = timestamp.isoformat()
        
        self.dao.save_workflow_step_result(
            project_id=project_id,
            step_name="theme_selection",
            output_data=output_dict,
            status="completed"
        )
        
        logger.info(f"テーマ選定結果を保存: プロジェクト={project_id}, テーマ={output.selected_theme.theme}")
    
    def save_theme_candidates_file(
        self, 
        project_id: str, 
        candidates: List[ThemeCandidate]
    ) -> str:
        """テーマ候補をJSONファイルに保存"""
        # プロジェクトのディレクトリ構造を取得
        project_dir = Path("projects") / project_id
        metadata_dir = project_dir / "files" / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = metadata_dir / "theme_candidates.json"
        candidates_data = {
            "generation_timestamp": datetime.now().isoformat(),
            "candidates": [asdict(candidate) for candidate in candidates],
            "count": len(candidates)
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(candidates_data, f, ensure_ascii=False, indent=2)
        
        # DAOを使用してファイル参照を登録
        file_size = file_path.stat().st_size if file_path.exists() else 0
        self.dao.register_file_reference(
            project_id=project_id,
            file_type="metadata",
            file_category="output",
            file_path=str(file_path),
            file_name="theme_candidates.json",
            file_size=file_size,
            metadata={"generation_time": datetime.now().isoformat()}
        )
        
        logger.info(f"テーマ候補ファイルを保存: {file_path}")
        return str(file_path)


class GeminiThemeLLM(LLMInterface):
    """Gemini LLMを使用したテーマ生成実装"""
    
    def __init__(self, llm_client: GeminiLLMClient):
        self.llm_client = llm_client
    
    def generate_theme_candidates(
        self, 
        preferences: UserPreferences, 
        count: int
    ) -> List[ThemeCandidate]:
        """LLMを使用してテーマ候補を生成"""
        prompt = self._build_theme_generation_prompt(preferences, count)
        
        try:
            from ..api.llm_client import GeminiRequest, ModelType
            
            gemini_request = GeminiRequest(
                prompt=prompt,
                model=ModelType.GEMINI_2_0_FLASH_EXP,
                max_output_tokens=2000,
                temperature=0.8
            )
            
            # asyncメソッドなので同期的に呼び出し
            import asyncio
            response = asyncio.run(self.llm_client.generate_text(gemini_request))
            
            return self._parse_theme_candidates(response.text)
            
        except Exception as e:
            logger.error(f"テーマ候補生成でエラー: {e}")
            # フォールバック候補を返す
            return self._get_fallback_candidates(preferences)
    
    def evaluate_and_rank_themes(
        self, 
        candidates: List[ThemeCandidate], 
        preferences: UserPreferences
    ) -> List[ThemeCandidate]:
        """テーマ候補を評価してランキング"""
        prompt = self._build_evaluation_prompt(candidates, preferences)
        
        try:
            from ..api.llm_client import GeminiRequest, ModelType
            
            gemini_request = GeminiRequest(
                prompt=prompt,
                model=ModelType.GEMINI_2_0_FLASH_EXP,
                max_output_tokens=1500,
                temperature=0.3  # 評価は一貫性重視
            )
            
            # asyncメソッドなので同期的に呼び出し
            import asyncio
            response = asyncio.run(self.llm_client.generate_text(gemini_request))
            
            return self._parse_ranked_themes(response.text, candidates)
            
        except Exception as e:
            logger.error(f"テーマ評価でエラー: {e}")
            # スコアベースでソート
            return sorted(candidates, key=lambda x: x.total_score, reverse=True)
    
    def _build_theme_generation_prompt(self, preferences: UserPreferences, count: int) -> str:
        """テーマ生成用プロンプトを構築"""
        return f"""ゆっくり動画のテーマを{count}個生成してください。

ユーザー設定:
- 好みのジャンル: {', '.join(preferences.preferred_genres)}
- 除外ジャンル: {', '.join(preferences.excluded_genres)}
- ターゲット層: {preferences.target_audience}
- コンテンツスタイル: {preferences.content_style}
- 過去のジャンル履歴: {', '.join(preferences.genre_history)}

要求:
1. 各テーマは5-10分程度の動画に適している
2. エンターテインメント性が高い
3. ユーザーの好みに合致している
4. 著作権に問題がない
5. 教育的価値がある

出力形式（JSON）:
{{
  "themes": [
    {{
      "theme": "テーマ名",
      "category": "カテゴリ",
      "target_length_minutes": 数値,
      "description": "詳細説明",
      "appeal_points": ["魅力ポイント1", "魅力ポイント2"],
      "difficulty_score": 数値,
      "entertainment_score": 数値,
      "trend_score": 数値,
      "total_score": 数値
    }}
  ]
}}

スコアは1.0-10.0の範囲で設定してください。"""
    
    def _build_evaluation_prompt(self, candidates: List[ThemeCandidate], preferences: UserPreferences) -> str:
        """テーマ評価用プロンプトを構築"""
        candidates_text = "\n".join([
            f"{i+1}. {c.theme} - {c.description}"
            for i, c in enumerate(candidates)
        ])
        
        return f"""以下のテーマ候補を評価して、最適な順序にランキングしてください。

候補テーマ:
{candidates_text}

評価基準:
- ユーザー好み適合度（好み: {', '.join(preferences.preferred_genres)}）
- エンターテインメント性
- 教育的価値
- 制作難易度（低いほど良い）
- トレンド性

上位5つのテーマの順位と理由を出力してください。

出力形式:
1位: テーマ名 - 理由
2位: テーマ名 - 理由
...
"""
    
    def _parse_theme_candidates(self, response_text: str) -> List[ThemeCandidate]:
        """LLM応答からテーマ候補をパース"""
        try:
            # JSONの抽出を試行
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_text = response_text[start_idx:end_idx]
                data = json.loads(json_text)
                
                candidates = []
                for theme_data in data.get("themes", []):
                    candidate = ThemeCandidate(
                        theme=theme_data.get("theme", ""),
                        category=theme_data.get("category", ""),
                        target_length_minutes=theme_data.get("target_length_minutes", 5),
                        description=theme_data.get("description", ""),
                        appeal_points=theme_data.get("appeal_points", []),
                        difficulty_score=theme_data.get("difficulty_score", 5.0),
                        entertainment_score=theme_data.get("entertainment_score", 5.0),
                        trend_score=theme_data.get("trend_score", 5.0),
                        total_score=theme_data.get("total_score", 5.0)
                    )
                    candidates.append(candidate)
                
                return candidates
        
        except Exception as e:
            logger.warning(f"LLM応答のパースに失敗: {e}")
        
        # パース失敗時はフォールバック
        return self._get_fallback_candidates(UserPreferences([], [], [], "一般", "親しみやすい"))
    
    def _parse_ranked_themes(self, response_text: str, original_candidates: List[ThemeCandidate]) -> List[ThemeCandidate]:
        """評価結果からランキングされたテーマを取得"""
        # 簡易実装：元の候補をtotal_scoreでソート
        return sorted(original_candidates, key=lambda x: x.total_score, reverse=True)
    
    def _get_fallback_candidates(self, preferences: UserPreferences) -> List[ThemeCandidate]:
        """フォールバック用の候補テーマ"""
        return [
            ThemeCandidate(
                theme="科学の不思議な現象",
                category="教育",
                target_length_minutes=7,
                description="日常に隠れた科学現象を分かりやすく解説",
                appeal_points=["身近な話題", "学習効果", "驚きの要素"],
                difficulty_score=4.0,
                entertainment_score=7.0,
                trend_score=6.0,
                total_score=5.7
            ),
            ThemeCandidate(
                theme="歴史上の面白エピソード",
                category="教育",
                target_length_minutes=8,
                description="教科書には載らない歴史の興味深い話",
                appeal_points=["意外性", "教養", "エンターテインメント"],
                difficulty_score=5.0,
                entertainment_score=8.0,
                trend_score=5.0,
                total_score=6.0
            )
        ]


class ThemeSelector:
    """テーマ選定メインクラス"""
    
    def __init__(
        self, 
        data_access: DataAccessInterface,
        llm_interface: LLMInterface
    ):
        self.data_access = data_access
        self.llm_interface = llm_interface
    
    def select_theme(self, input_data: ThemeSelectionInput) -> ThemeSelectionOutput:
        """テーマ選定を実行"""
        logger.info(f"テーマ選定開始: プロジェクト={input_data.project_id}")
        
        try:
            # 1. テーマ候補生成
            candidates = self.llm_interface.generate_theme_candidates(
                input_data.user_preferences,
                input_data.max_candidates
            )
            logger.info(f"テーマ候補生成完了: {len(candidates)}件")
            
            # 2. 評価・ランキング
            ranked_candidates = self.llm_interface.evaluate_and_rank_themes(
                candidates,
                input_data.user_preferences
            )
            logger.info("テーマ評価・ランキング完了")
            
            # 3. 最適テーマ選択
            if not ranked_candidates:
                raise ValueError("有効なテーマ候補が生成されませんでした")
            
            best_candidate = ranked_candidates[0]
            selected_theme = SelectedTheme(
                theme=best_candidate.theme,
                category=best_candidate.category,
                target_length_minutes=best_candidate.target_length_minutes,
                description=best_candidate.description,
                selection_reason=f"総合スコア{best_candidate.total_score:.1f}で最高評価",
                generation_timestamp=datetime.now()
            )
            
            # 4. 結果の構築
            output = ThemeSelectionOutput(
                selected_theme=selected_theme,
                candidates=ranked_candidates,
                selection_metadata={
                    "generation_method": "gemini_llm",
                    "candidates_count": len(candidates),
                    "selection_timestamp": datetime.now().isoformat(),
                    "user_preferences": asdict(input_data.user_preferences)
                }
            )
            
            # 5. 結果保存
            self.data_access.save_theme_selection_result(input_data.project_id, output)
            self.data_access.save_theme_candidates_file(input_data.project_id, ranked_candidates)
            
            logger.info(f"テーマ選定完了: {selected_theme.theme}")
            return output
            
        except Exception as e:
            logger.error(f"テーマ選定でエラー: {e}")
            raise 