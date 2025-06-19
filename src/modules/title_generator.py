"""
タイトル生成モジュール

テーマとスクリプトに基づいて高CTRを狙ったタイトルを生成
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Protocol, Optional
from abc import ABC, abstractmethod

from src.dao.title_generation_dao import TitleGenerationDAO
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient, GeminiRequest, ModelType


@dataclass
class TitleCandidate:
    """タイトル候補"""
    title: str
    ctr_score: float  # Click-Through Rate予測スコア (0-10)
    keyword_score: float  # キーワード適合度スコア (0-10)
    length_score: float  # 長さ適正スコア (0-10)
    total_score: float  # 総合スコア (0-10)
    reasons: List[str]  # 選定理由


@dataclass
class GeneratedTitles:
    """生成されたタイトル全体"""
    candidates: List[TitleCandidate]
    selected_title: str
    generation_timestamp: datetime


@dataclass
class TitleConfig:
    """タイトル生成設定"""
    candidate_count: int
    max_title_length: int
    min_title_length: int
    keywords_weight: float
    ctr_optimization: bool


@dataclass
class TitleGenerationInput:
    """タイトル生成入力データ"""
    project_id: str
    llm_config: Dict[str, Any]


@dataclass
class TitleGenerationOutput:
    """タイトル生成出力データ"""
    generated_titles: GeneratedTitles
    analysis_file_path: Optional[str] = None


class TitleLLMInterface(Protocol):
    """タイトル生成LLMインターフェース"""
    
    def generate_titles(
        self, 
        theme_data: Dict[str, Any], 
        script_summary: Dict[str, Any], 
        config: TitleConfig
    ) -> GeneratedTitles:
        """タイトル生成"""
        ...


class TitleDataAccess(Protocol):
    """タイトル生成データアクセスインターフェース"""
    
    def get_project_data(self, project_id: str) -> Dict[str, Any]:
        """プロジェクトデータ取得"""
        ...
    
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """スクリプトデータ取得"""
        ...
    
    def save_title_result(self, project_id: str, titles: GeneratedTitles, status: str) -> None:
        """タイトル結果保存"""
        ...


class GeminiTitleLLM:
    """Gemini APIを使用したタイトル生成"""
    
    def __init__(self, llm_client: GeminiLLMClient):
        """
        初期化
        
        Args:
            llm_client: Gemini LLMクライアント
        """
        self.llm_client = llm_client
    
    def generate_titles(
        self, 
        theme_data: Dict[str, Any], 
        script_summary: Dict[str, Any], 
        config: TitleConfig
    ) -> GeneratedTitles:
        """
        Gemini APIを使用してタイトルを生成
        
        Args:
            theme_data: テーマデータ
            script_summary: スクリプト概要
            config: タイトル生成設定
            
        Returns:
            生成されたタイトル情報
        """
        # プロンプト作成
        prompt = self._create_title_prompt(theme_data, script_summary, config)
        
        # Gemini APIリクエスト作成
        request = GeminiRequest(
            prompt=prompt,
            model=ModelType.GEMINI_2_0_FLASH_EXP,
            max_output_tokens=2000,
            temperature=0.7
        )
        
        # 非同期でタイトル生成
        response = asyncio.run(self.llm_client.generate_text(request))
        
        # レスポンスをパース
        return self._parse_title_response(response.text, config)
    
    def _create_title_prompt(
        self, 
        theme_data: Dict[str, Any], 
        script_summary: Dict[str, Any], 
        config: TitleConfig
    ) -> str:
        """タイトル生成プロンプトを作成"""
        
        theme = theme_data.get("theme", "")
        category = theme_data.get("category", "")
        description = theme_data.get("description", "")
        
        key_points = script_summary.get("key_points", [])
        duration = script_summary.get("total_duration", 0)
        
        key_points_text = "、".join(key_points) if key_points else "なし"
        
        prompt = f"""
あなたは優秀なYouTubeタイトル作成の専門家です。ゆっくり解説動画のタイトルを{config.candidate_count}個生成してください。

## 動画情報
- テーマ: {theme}
- カテゴリ: {category}
- 説明: {description}
- 主要ポイント: {key_points_text}
- 動画時間: {duration:.1f}秒

## タイトル作成要件
1. 長さ: {config.min_title_length}文字以上{config.max_title_length}文字以下
2. 高CTR（クリック率）を狙った魅力的なタイトル
3. ゆっくり解説動画に適したスタイル
4. 検索されやすいキーワードを含む
5. 数字や記号を効果的に使用
6. 疑問形や感嘆符で興味を引く

## 評価基準
- CTRスコア (0-10): クリック率予測
- キーワードスコア (0-10): 検索適合度
- 長さスコア (0-10): 長さの適正度
- 総合スコア: 上記3つの平均

## 出力形式
以下のJSON形式で出力してください：

{{
  "candidates": [
    {{
      "title": "タイトル文字列",
      "ctr_score": 8.5,
      "keyword_score": 9.0,
      "length_score": 8.0,
      "total_score": 8.5,
      "reasons": ["理由1", "理由2", "理由3"]
    }}
  ],
  "selected_title": "最も高スコアのタイトル"
}}

注意: 必ずJSON形式で出力し、各タイトルに適切なスコアと選定理由を付けてください。
"""
        
        return prompt
    
    def _parse_title_response(self, response_text: str, config: TitleConfig) -> GeneratedTitles:
        """タイトル生成レスポンスをパース"""
        
        try:
            # JSONブロック抽出を試行
            json_match = None
            
            # ```json ... ``` ブロックを探す
            import re
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            match = re.search(json_pattern, response_text, re.DOTALL)
            if match:
                json_text = match.group(1)
            else:
                # 直接JSON形式を探す
                brace_start = response_text.find('{')
                if brace_start != -1:
                    # 最後の}を見つける
                    brace_count = 0
                    json_end = -1
                    for i, char in enumerate(response_text[brace_start:], brace_start):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    
                    if json_end > brace_start:
                        json_text = response_text[brace_start:json_end]
                    else:
                        json_text = response_text
                else:
                    json_text = response_text
            
            # JSONパース
            response_data = json.loads(json_text)
            
            candidates = []
            for candidate_data in response_data.get("candidates", []):
                candidate = TitleCandidate(
                    title=candidate_data["title"],
                    ctr_score=float(candidate_data["ctr_score"]),
                    keyword_score=float(candidate_data["keyword_score"]),
                    length_score=float(candidate_data["length_score"]),
                    total_score=float(candidate_data["total_score"]),
                    reasons=candidate_data["reasons"]
                )
                candidates.append(candidate)
            
            # 総合スコア順にソート
            candidates.sort(key=lambda x: x.total_score, reverse=True)
            
            # 最高スコアのタイトルを選択
            selected_title = response_data.get("selected_title", "")
            if not selected_title and candidates:
                selected_title = candidates[0].title
            
            return GeneratedTitles(
                candidates=candidates,
                selected_title=selected_title,
                generation_timestamp=datetime.now()
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"JSON解析エラー: {e}")
            print(f"レスポンス (最初の500文字): {response_text[:500]}")
            # パースエラーの場合はフォールバック
            return self._create_fallback_titles(response_text, config)
    
    def _create_fallback_titles(self, response_text: str, config: TitleConfig) -> GeneratedTitles:
        """パースエラー時のフォールバックタイトル生成"""
        
        # 応答テキストから可能な限りタイトルを抽出
        lines = response_text.split('\n')
        title_candidates = []
        
        for line in lines:
            line = line.strip()
            # 不要な記号や番号を除去
            line = line.lstrip('123456789.-* ')
            line = line.strip('"')
            
            if (line and 
                len(line) >= config.min_title_length and 
                len(line) <= config.max_title_length and
                not line.startswith('{') and
                not line.startswith('}')):
                
                # 基本的なスコアを設定
                candidate = TitleCandidate(
                    title=line,
                    ctr_score=7.0,
                    keyword_score=7.0,
                    length_score=8.0,
                    total_score=7.3,
                    reasons=["フォールバック生成", "基本的な品質確保"]
                )
                title_candidates.append(candidate)
                
                if len(title_candidates) >= config.candidate_count:
                    break
        
        # フォールバックタイトルが不足している場合
        if not title_candidates:
            # テーマベースのフォールバックタイトル生成
            fallback_titles = [
                "【ゆっくり解説】未来の宇宙探査技術について",
                "宇宙探査の最新技術を解説！",
                "未来技術：宇宙探査の革新",
                "【科学】宇宙探査技術の進歩",
                "次世代宇宙探査システム解説"
            ]
            
            for i, title in enumerate(fallback_titles[:config.candidate_count]):
                candidate = TitleCandidate(
                    title=title,
                    ctr_score=6.0 + i * 0.2,
                    keyword_score=7.0 + i * 0.1,
                    length_score=8.0,
                    total_score=7.0 + i * 0.1,
                    reasons=["テーマベースフォールバック", "基本的な形式"]
                )
                title_candidates.append(candidate)
        
        return GeneratedTitles(
            candidates=title_candidates,
            selected_title=title_candidates[0].title,
            generation_timestamp=datetime.now()
        )


class DatabaseDataAccess:
    """データベースベースのデータアクセス実装"""
    
    def __init__(self, project_repository: ProjectRepository, config_manager: ConfigManager):
        """
        初期化
        
        Args:
            project_repository: プロジェクトリポジトリ
            config_manager: 設定マネージャー
        """
        self.dao = TitleGenerationDAO(project_repository.db_manager)
        self.config_manager = config_manager
    
    def get_project_data(self, project_id: str) -> Dict[str, Any]:
        """プロジェクトデータ取得"""
        return self.dao.get_project_data(project_id)
    
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """スクリプトデータ取得と要約作成"""
        script_data = self.dao.get_script_data(project_id)
        
        # スクリプトから要約情報を抽出
        script_content = script_data["output_data"].get("generated_script", {})
        segments = script_content.get("segments", [])
        
        # キーポイント抽出
        key_points = []
        for segment in segments:
            text = segment.get("text", "")
            # 簡単なキーワード抽出（実際にはより高度な処理が可能）
            if len(text) > 20:  # 長めのセグメントからキーポイントを抽出
                key_points.append(text[:30] + "..." if len(text) > 30 else text)
        
        return {
            "key_points": key_points[:5],  # 最大5個のキーポイント
            "total_duration": script_content.get("total_estimated_duration", 0),
            "character_count": script_content.get("total_character_count", 0),
            "segment_count": len(segments)
        }
    
    def save_title_result(self, project_id: str, titles: GeneratedTitles, status: str) -> None:
        """タイトル結果保存"""
        self.dao.save_title_result(project_id, titles, status)


class TitleGenerator:
    """タイトル生成メインクラス"""
    
    def __init__(self, data_access: TitleDataAccess, llm_interface: TitleLLMInterface):
        """
        初期化
        
        Args:
            data_access: データアクセスインターフェース
            llm_interface: LLMインターフェース
        """
        self.data_access = data_access
        self.llm_interface = llm_interface
    
    def generate_titles(self, input_data: TitleGenerationInput) -> TitleGenerationOutput:
        """
        タイトル生成メイン処理
        
        Args:
            input_data: 入力データ
            
        Returns:
            生成結果
        """
        project_id = input_data.project_id
        
        try:
            # 1. プロジェクトデータ取得
            project_data = self.data_access.get_project_data(project_id)
            
            # 2. スクリプトデータ取得
            script_data = self.data_access.get_script_data(project_id)
            
            # 3. 設定準備
            config = self._create_config(project_data, input_data.llm_config)
            
            # 4. テーマデータ準備
            theme_data = {
                "theme": project_data["theme"],
                "category": project_data.get("category", ""),
                "description": project_data.get("description", ""),
                "target_length_minutes": project_data["target_length_minutes"]
            }
            
            # 5. タイトル生成実行
            generated_titles = self.llm_interface.generate_titles(
                theme_data, script_data, config
            )
            
            # 6. 結果保存
            self.data_access.save_title_result(project_id, generated_titles, "completed")
            
            return TitleGenerationOutput(
                generated_titles=generated_titles
            )
            
        except Exception as e:
            # エラー時はフォールバック
            fallback_titles = self._create_fallback_result(project_data)
            self.data_access.save_title_result(project_id, fallback_titles, "failed")
            
            return TitleGenerationOutput(
                generated_titles=fallback_titles
            )
    
    def _create_config(self, project_data: Dict[str, Any], llm_config: Dict[str, Any]) -> TitleConfig:
        """設定オブジェクト作成"""
        
        # プロジェクト設定から取得
        title_config = project_data.get("config", {}).get("title_generation", {})
        
        return TitleConfig(
            candidate_count=title_config.get("candidate_count", 5),
            max_title_length=title_config.get("max_title_length", 100),
            min_title_length=title_config.get("min_title_length", 10),
            keywords_weight=title_config.get("keywords_weight", 0.3),
            ctr_optimization=title_config.get("ctr_optimization", True)
        )
    
    def _create_fallback_result(self, project_data: Dict[str, Any]) -> GeneratedTitles:
        """フォールバック結果作成"""
        
        theme = project_data.get("theme", "動画")
        fallback_title = f"【ゆっくり解説】{theme}について"
        
        candidate = TitleCandidate(
            title=fallback_title,
            ctr_score=5.0,
            keyword_score=6.0,
            length_score=7.0,
            total_score=6.0,
            reasons=["フォールバック生成", "基本的な形式"]
        )
        
        return GeneratedTitles(
            candidates=[candidate],
            selected_title=fallback_title,
            generation_timestamp=datetime.now()
        )
