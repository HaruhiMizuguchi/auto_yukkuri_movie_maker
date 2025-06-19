"""
スクリプト生成モジュール

テーマに基づいてゆっくり動画用のスクリプトを生成
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Protocol, Optional
from abc import ABC, abstractmethod

from src.dao.script_generation_dao import ScriptGenerationDAO
from src.core.project_repository import ProjectRepository
from src.core.config_manager import ConfigManager
from src.api.llm_client import GeminiLLMClient, GeminiRequest, ModelType


@dataclass
class ScriptSegment:
    """スクリプトセグメント（話者の発言単位）"""
    segment_id: int
    speaker: str
    text: str
    estimated_duration: float  # 秒
    emotion: str


@dataclass
class GeneratedScript:
    """生成されたスクリプト全体"""
    segments: List[ScriptSegment]
    total_estimated_duration: float  # 秒
    total_character_count: int
    generation_timestamp: datetime


@dataclass
class ScriptConfig:
    """スクリプト生成設定"""
    target_duration_minutes: int
    speaker_count: int
    speaker_names: List[str]
    tone: str


@dataclass
class ScriptGenerationInput:
    """スクリプト生成の入力データ"""
    project_id: str
    llm_config: Dict[str, Any]


@dataclass
class ScriptGenerationOutput:
    """スクリプト生成の出力データ"""
    generated_script: GeneratedScript
    script_metadata: Dict[str, Any]


class DataAccessInterface(Protocol):
    """データアクセス層のインターフェース"""
    
    def get_theme_data(self, project_id: str) -> Dict[str, Any]:
        """テーマデータを取得"""
        ...
    
    def get_script_config(self, project_id: str) -> ScriptConfig:
        """スクリプト設定を取得"""
        ...
    
    def save_script_generation_result(self, project_id: str, output: ScriptGenerationOutput) -> None:
        """スクリプト生成結果を保存"""
        ...


class LLMInterface(Protocol):
    """LLM処理のインターフェース"""
    
    def generate_script(self, theme_data: Dict[str, Any], config: ScriptConfig) -> GeneratedScript:
        """スクリプトを生成"""
        ...


class DatabaseDataAccess:
    """データベースアクセス実装"""
    
    def __init__(self, project_repository: ProjectRepository, config_manager: ConfigManager):
        """
        初期化
        
        Args:
            project_repository: プロジェクトリポジトリ
            config_manager: 設定マネージャー
        """
        self.project_repository = project_repository
        self.config_manager = config_manager
        self.dao = ScriptGenerationDAO(project_repository.db_manager)
    
    def get_theme_data(self, project_id: str) -> Dict[str, Any]:
        """
        テーマデータを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            テーマデータ辞書
        """
        project_data = self.dao.get_project_theme(project_id)
        previous_step = self.dao.get_previous_step_output(project_id, "theme_selection")
        
        theme_data = {
            "theme": project_data["theme"],
            "target_length_minutes": project_data["target_length_minutes"]
        }
        
        # 前ステップの詳細情報があれば追加
        if previous_step and "selected_theme" in previous_step:
            selected_theme = previous_step["selected_theme"]
            theme_data.update({
                "description": selected_theme.get("description", ""),
                "category": selected_theme.get("category", ""),
                "selection_reason": selected_theme.get("selection_reason", "")
            })
        
        return theme_data
    
    def get_script_config(self, project_id: str) -> ScriptConfig:
        """
        スクリプト設定を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            スクリプト設定オブジェクト
        """
        config_dict = self.dao.get_script_config(project_id)
        
        return ScriptConfig(
            target_duration_minutes=config_dict["target_duration_minutes"],
            speaker_count=config_dict["speaker_count"],
            speaker_names=config_dict["speaker_names"],
            tone=config_dict["tone"]
        )
    
    def save_script_generation_result(self, project_id: str, output: ScriptGenerationOutput) -> None:
        """
        スクリプト生成結果を保存
        
        Args:
            project_id: プロジェクトID
            output: 生成結果
        """
        # DAOを使用してデータベースに保存
        self.dao.save_script_result(
            project_id=project_id,
            script=output.generated_script,
            status="completed"
        )
        
        # プロジェクトリポジトリ経由でワークフローステップ更新
        self.project_repository.save_step_result(
            project_id=project_id,
            step_name="script_generation",
            output_data={
                "generated_script": {
                    "total_estimated_duration": output.generated_script.total_estimated_duration,
                    "total_character_count": output.generated_script.total_character_count,
                    "segment_count": len(output.generated_script.segments)
                },
                "metadata": output.script_metadata
            },
            status="completed"
        )


class GeminiScriptLLM:
    """Gemini APIを使用したスクリプト生成"""
    
    def __init__(self, llm_client: GeminiLLMClient):
        """
        初期化
        
        Args:
            llm_client: Gemini LLMクライアント
        """
        self.llm_client = llm_client
    
    def generate_script(self, theme_data: Dict[str, Any], config: ScriptConfig) -> GeneratedScript:
        """
        スクリプトを生成
        
        Args:
            theme_data: テーマデータ
            config: スクリプト設定
            
        Returns:
            生成されたスクリプト
        """
        prompt = self._build_script_prompt(theme_data, config)
        
        # Gemini APIリクエスト作成
        request = GeminiRequest(
            prompt=prompt,
            model=ModelType.GEMINI_2_0_FLASH_EXP,
            max_output_tokens=3000,
            temperature=0.8
        )
        
        # 非同期でスクリプト生成
        response = asyncio.run(self.llm_client.generate_text(request))
        
        # レスポンスをパース
        return self._parse_script_response(response.text, config)
    
    def _build_script_prompt(self, theme_data: Dict[str, Any], config: ScriptConfig) -> str:
        """
        スクリプト生成用プロンプトを構築
        
        Args:
            theme_data: テーマデータ
            config: スクリプト設定
            
        Returns:
            プロンプト文字列
        """
        speaker_names = "、".join(config.speaker_names)
        target_duration = config.target_duration_minutes
        
        prompt = f"""
あなたは東方Project風のゆっくり動画のスクリプト作成の専門家です。
以下の条件に従って、魅力的で視聴者を引きつけるスクリプトを作成してください。

## テーマ情報
- テーマ: {theme_data['theme']}
- 説明: {theme_data.get('description', 'なし')}
- 目標時間: {target_duration}分

## スクリプト要件
- 話者: {speaker_names}
- 話者数: {config.speaker_count}人
- トーン: {config.tone}
- 目標動画時間: {target_duration}分（約{target_duration * 60}秒）

## 出力形式
以下のJSON形式で出力してください：

{{
  "segments": [
    {{
      "segment_id": 1,
      "speaker": "reimu",
      "text": "発言内容",
      "estimated_duration": 推定秒数,
      "emotion": "感情（happy/sad/surprised/angry/neutral）"
    }},
    ...
  ]
}}

## 作成ガイドライン
1. 導入（10-15%）：テーマの紹介、視聴者の関心を引く
2. 展開（70-80%）：メインコンテンツ、具体例や詳細説明
3. 結論（10-15%）：まとめ、視聴者への呼びかけ

## 重要な注意事項
- 各セグメントは自然な会話になるよう作成
- 話者の特徴を活かした発言内容にする
- 視聴者が飽きないよう適度に話者を交代
- 1セグメントあたり2-10秒程度の発言時間
- 教育的かつエンターテイメント性のある内容
- 著作権に配慮した内容

それでは、魅力的なスクリプトを作成してください。
"""
        
        return prompt.strip()
    
    def _parse_script_response(self, response_text: str, config: ScriptConfig) -> GeneratedScript:
        """
        LLMレスポンスをパースしてスクリプトオブジェクトに変換
        
        Args:
            response_text: LLMからのレスポンステキスト
            config: スクリプト設定
            
        Returns:
            パースされたスクリプト
        """
        try:
            # JSONデータの抽出（```json ブロックがある場合を考慮）
            json_text = response_text
            if "```json" in response_text:
                start_idx = response_text.find("```json") + 7
                end_idx = response_text.find("```", start_idx)
                json_text = response_text[start_idx:end_idx].strip()
            elif "```" in response_text:
                start_idx = response_text.find("```") + 3
                end_idx = response_text.find("```", start_idx)
                json_text = response_text[start_idx:end_idx].strip()
            
            # JSONパース
            script_data = json.loads(json_text)
            
            # セグメントリスト作成
            segments = []
            total_duration = 0.0
            total_characters = 0
            
            for seg_data in script_data.get("segments", []):
                segment = ScriptSegment(
                    segment_id=seg_data["segment_id"],
                    speaker=seg_data["speaker"],
                    text=seg_data["text"],
                    estimated_duration=float(seg_data["estimated_duration"]),
                    emotion=seg_data.get("emotion", "neutral")
                )
                segments.append(segment)
                total_duration += segment.estimated_duration
                total_characters += len(segment.text)
            
            return GeneratedScript(
                segments=segments,
                total_estimated_duration=total_duration,
                total_character_count=total_characters,
                generation_timestamp=datetime.now()
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # パースエラーの場合、フォールバック処理
            return self._create_fallback_script(response_text, config)
    
    def _create_fallback_script(self, response_text: str, config: ScriptConfig) -> GeneratedScript:
        """
        パースエラー時のフォールバックスクリプト作成
        
        Args:
            response_text: 元のレスポンステキスト
            config: スクリプト設定
            
        Returns:
            フォールバックスクリプト
        """
        # 簡単な分割処理でセグメント作成
        lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        segments = []
        
        speaker_index = 0
        for i, line in enumerate(lines[:10]):  # 最大10セグメント
            if len(line) > 10:  # 短すぎる行は除外
                segment = ScriptSegment(
                    segment_id=i + 1,
                    speaker=config.speaker_names[speaker_index % len(config.speaker_names)],
                    text=line,
                    estimated_duration=max(2.0, len(line) * 0.1),  # 文字数ベースの推定
                    emotion="neutral"
                )
                segments.append(segment)
                speaker_index += 1
        
        # 最低1セグメントは保証
        if not segments:
            segments = [ScriptSegment(
                segment_id=1,
                speaker=config.speaker_names[0],
                text=f"{config.speaker_names[0]}が{response_text[:50]}について話します。",
                estimated_duration=5.0,
                emotion="neutral"
            )]
        
        total_duration = sum(seg.estimated_duration for seg in segments)
        total_characters = sum(len(seg.text) for seg in segments)
        
        return GeneratedScript(
            segments=segments,
            total_estimated_duration=total_duration,
            total_character_count=total_characters,
            generation_timestamp=datetime.now()
        )


class ScriptGenerator:
    """スクリプト生成メインクラス"""
    
    def __init__(self, data_access: DataAccessInterface, llm_interface: LLMInterface):
        """
        初期化
        
        Args:
            data_access: データアクセス層
            llm_interface: LLM処理層
        """
        self.data_access = data_access
        self.llm_interface = llm_interface
    
    def generate_script(self, input_data: ScriptGenerationInput) -> ScriptGenerationOutput:
        """
        スクリプト生成メイン処理
        
        Args:
            input_data: 入力データ
            
        Returns:
            生成結果
        """
        # 1. テーマデータとスクリプト設定を取得
        theme_data = self.data_access.get_theme_data(input_data.project_id)
        script_config = self.data_access.get_script_config(input_data.project_id)
        
        # 2. LLMでスクリプト生成
        generated_script = self.llm_interface.generate_script(theme_data, script_config)
        
        # 3. メタデータ作成
        script_metadata = {
            "generation_method": "gemini_llm",
            "theme": theme_data["theme"],
            "target_duration_minutes": script_config.target_duration_minutes,
            "actual_duration_seconds": generated_script.total_estimated_duration,
            "speaker_count": len(script_config.speaker_names),
            "segment_count": len(generated_script.segments),
            "llm_config": input_data.llm_config
        }
        
        # 4. 出力データ作成
        output = ScriptGenerationOutput(
            generated_script=generated_script,
            script_metadata=script_metadata
        )
        
        # 5. データベースに保存
        self.data_access.save_script_generation_result(input_data.project_id, output)
        
        return output 