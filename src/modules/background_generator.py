"""
背景生成モジュール (4-6)

flow_definition.yamlに基づく仕様:
- 入力: スクリプトデータ + 画像生成設定
- 処理: シーン分析・プロンプト生成・背景画像生成・Ken Burnsエフェクト・動画化
- 出力: 背景画像・背景動画・メタデータ

実装方針:
- Gemini画像生成API実連携
- シーン自動分析
- 背景画像自動生成
- Ken Burnsエフェクト（パン・ズーム）
- 動画変換（ffmpeg）
- DAO分離（背景生成専用SQL操作）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Protocol
import json
import logging
from pathlib import Path
import uuid
from datetime import datetime
import math
import random
import subprocess
import os

from ..core.project_repository import ProjectRepository
from ..core.config_manager import ConfigManager
from ..core.file_system_manager import FileSystemManager
from ..api.image_client import ImageGenerationClient
from ..dao.background_generation_dao import BackgroundGenerationDAO

logger = logging.getLogger(__name__)


@dataclass
class SceneAnalysis:
    """シーン分析データクラス"""
    scene_id: str
    scene_type: str
    description: str
    duration: float
    prompt: str
    style: str
    segments: List[int]  # 含まれるセグメントID
    metadata: Dict[str, Any]


@dataclass
class BackgroundImage:
    """背景画像データクラス"""
    scene_id: str
    image_path: str
    resolution: str
    file_size: int
    generation_metadata: Dict[str, Any]


@dataclass
class KenBurnsEffect:
    """Ken Burnsエフェクトデータクラス"""
    scene_id: str
    duration: float
    zoom_start: float
    zoom_end: float
    pan_start_x: float
    pan_start_y: float
    pan_end_x: float
    pan_end_y: float
    easing_function: str
    metadata: Dict[str, Any]


@dataclass
class BackgroundVideo:
    """背景動画データクラス"""
    scene_id: str
    video_path: str
    duration: float
    resolution: str
    fps: int
    file_size: int
    ken_burns_metadata: Dict[str, Any]


@dataclass
class BackgroundGenerationInput:
    """背景生成処理の入力データ"""
    project_id: str
    script_data: Dict[str, Any]
    generation_config: Dict[str, Any]


@dataclass
class BackgroundGenerationOutput:
    """背景生成処理の出力データ"""
    background_images: List[BackgroundImage]
    background_videos: List[BackgroundVideo]
    scene_analyses: List[SceneAnalysis]
    generation_metadata: Dict[str, Any]


class BackgroundGeneratorProtocol(Protocol):
    """背景生成の抽象インターフェース"""
    
    def generate_backgrounds(self, input_data: BackgroundGenerationInput) -> BackgroundGenerationOutput:
        """背景生成を実行"""
        ...


class DataAccessInterface(ABC):
    """データアクセス抽象インターフェース"""
    
    @abstractmethod
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """スクリプトデータを取得"""
        pass
    
    @abstractmethod
    def save_background_generation_result(
        self, 
        project_id: str, 
        output: BackgroundGenerationOutput
    ) -> None:
        """背景生成結果を保存"""
        pass


class ImageGenerationInterface(ABC):
    """画像生成抽象インターフェース"""
    
    @abstractmethod
    def generate_background_image(
        self, 
        prompt: str,
        style: str,
        resolution: str
    ) -> Dict[str, Any]:
        """背景画像を生成"""
        pass


class VideoProcessingInterface(ABC):
    """動画処理抽象インターフェース"""
    
    @abstractmethod
    def create_ken_burns_video(
        self,
        image_path: str,
        output_path: str,
        ken_burns: KenBurnsEffect,
        fps: int
    ) -> Dict[str, Any]:
        """Ken Burnsエフェクト動画を作成"""
        pass


class DatabaseDataAccess(DataAccessInterface):
    """データベースデータアクセス実装（DAO使用）"""
    
    def __init__(self, repository: ProjectRepository, config_manager: ConfigManager):
        self.repository = repository
        self.config_manager = config_manager
        self.dao = BackgroundGenerationDAO(repository.db_manager)
    
    def get_script_data(self, project_id: str) -> Dict[str, Any]:
        """スクリプトデータを取得"""
        script_data = self.dao.get_script_data(project_id)
        if not script_data:
            raise ValueError(f"Script data not found for project: {project_id}")
        return script_data
    
    def save_background_generation_result(
        self, 
        project_id: str, 
        output: BackgroundGenerationOutput
    ) -> None:
        """背景生成結果をデータベースに保存"""
        # シーン分析結果を保存
        for scene in output.scene_analyses:
            scene_data = asdict(scene)
            self.dao.save_scene_analysis(project_id, scene.scene_id, scene_data)
        
        # 背景画像を保存
        for image in output.background_images:
            image_data = asdict(image)
            self.dao.save_background_image(project_id, image.scene_id, image_data)
            
            # ファイル参照を登録
            self.dao.register_file_reference(
                project_id=project_id,
                file_type="image",
                file_category="background",
                file_path=image.image_path,
                file_name=Path(image.image_path).name,
                file_size=image.file_size,
                metadata={"scene_id": image.scene_id}
            )
        
        # 背景動画を保存
        for video in output.background_videos:
            video_data = asdict(video)
            self.dao.save_background_video(project_id, video.scene_id, video_data)
            
            # ファイル参照を登録
            self.dao.register_file_reference(
                project_id=project_id,
                file_type="video",
                file_category="background",
                file_path=video.video_path,
                file_name=Path(video.video_path).name,
                file_size=video.file_size,
                metadata={"scene_id": video.scene_id}
            )
        
        # ワークフローステップ結果を保存
        output_dict = asdict(output)
        # datetimeオブジェクトをISO文字列に変換
        self._convert_datetimes_to_iso(output_dict)
        
        self.dao.save_workflow_step_result(
            project_id=project_id,
            step_name="background_generation",
            output_data=output_dict,
            status="completed"
        )
        
        logger.info(f"背景生成結果を保存: プロジェクト={project_id}, シーン数={len(output.scene_analyses)}")
    
    def _convert_datetimes_to_iso(self, data: Any) -> None:
        """辞書内のdatetimeオブジェクトをISO文字列に変換"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                elif isinstance(value, (dict, list)):
                    self._convert_datetimes_to_iso(value)
        elif isinstance(data, list):
            for item in data:
                self._convert_datetimes_to_iso(item)


class GeminiImageGeneration(ImageGenerationInterface):
    """Gemini画像生成実装"""
    
    def __init__(self, image_client: ImageGenerationClient):
        self.image_client = image_client
    
    def generate_background_image(
        self, 
        prompt: str,
        style: str,
        resolution: str
    ) -> Dict[str, Any]:
        """背景画像を生成"""
        # プロンプトを背景画像用に最適化
        optimized_prompt = self._optimize_background_prompt(prompt, style)
        
        try:
            # Gemini APIで画像生成
            result = self.image_client.generate_image(
                prompt=optimized_prompt,
                temperature=0.7,
                response_modalities=["image"]
            )
            
            return {
                "image_data": result["image_data"],
                "description": result.get("description", ""),
                "style": style,
                "resolution": resolution,
                "metadata": {
                    "original_prompt": prompt,
                    "optimized_prompt": optimized_prompt,
                    "generation_time": result.get("metadata", {}).get("generation_time", 0),
                    "model": result.get("metadata", {}).get("model", "")
                }
            }
            
        except Exception as e:
            logger.error(f"背景画像生成エラー: {e}")
            # フォールバック処理
            return self._get_fallback_image_data(style, resolution)
    
    def _optimize_background_prompt(self, prompt: str, style: str) -> str:
        """背景画像用プロンプト最適化"""
        # スタイル情報を追加
        style_modifiers = {
            "anime_style": "anime style, detailed background, scenic view",
            "realistic": "photorealistic, high quality, cinematic lighting",
            "watercolor": "watercolor painting style, soft colors, artistic",
            "digital_art": "digital art, vibrant colors, detailed illustration"
        }
        
        modifier = style_modifiers.get(style, "high quality, detailed background")
        
        # 背景特化キーワードを追加
        background_keywords = "background scene, environment, landscape, no characters, wide shot"
        
        return f"{prompt}, {modifier}, {background_keywords}"
    
    def _get_fallback_image_data(self, style: str, resolution: str) -> Dict[str, Any]:
        """フォールバック画像データ"""
        return {
            "image_data": b"fallback_image_data",
            "description": f"Fallback {style} background",
            "style": style,
            "resolution": resolution,
            "metadata": {
                "fallback": True,
                "generation_time": 0,
                "model": "fallback"
            }
        }


class FFmpegVideoProcessing(VideoProcessingInterface):
    """ffmpeg動画処理実装"""
    
    def create_ken_burns_video(
        self,
        image_path: str,
        output_path: str,
        ken_burns: KenBurnsEffect,
        fps: int
    ) -> Dict[str, Any]:
        """Ken Burnsエフェクト動画を作成"""
        try:
            # ffmpegコマンドを構築
            cmd = self._build_ken_burns_command(
                image_path, output_path, ken_burns, fps
            )
            
            # ffmpeg実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2分でタイムアウト
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")
            
            # 出力ファイルサイズを取得
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            
            return {
                "video_path": output_path,
                "duration": ken_burns.duration,
                "fps": fps,
                "file_size": file_size,
                "success": True,
                "metadata": {
                    "ken_burns_params": asdict(ken_burns),
                    "ffmpeg_command": " ".join(cmd)
                }
            }
            
        except Exception as e:
            logger.error(f"Ken Burns動画生成エラー: {e}")
            raise RuntimeError(f"Video generation failed: {e}")
    
    def _build_ken_burns_command(
        self,
        image_path: str,
        output_path: str,
        ken_burns: KenBurnsEffect,
        fps: int
    ) -> List[str]:
        """Ken Burnsエフェクト用ffmpegコマンドを構築"""
        duration_str = f"{ken_burns.duration:.2f}"
        
        # ズーム・パンエフェクトのフィルター
        zoom_filter = self._create_zoom_pan_filter(ken_burns, fps)
        
        cmd = [
            "ffmpeg",
            "-y",  # 上書き許可
            "-loop", "1",  # 画像をループ
            "-i", image_path,
            "-t", duration_str,
            "-vf", zoom_filter,
            "-r", str(fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",  # 高品質
            output_path
        ]
        
        return cmd
    
    def _create_zoom_pan_filter(self, ken_burns: KenBurnsEffect, fps: int) -> str:
        """ズーム・パンフィルターを作成"""
        total_frames = int(ken_burns.duration * fps)
        
        # easing関数に基づく補間
        easing_func = self._get_easing_function(ken_burns.easing_function)
        
        # zoompanフィルターパラメータ
        zoom_expr = f"if(lte(on,1),{ken_burns.zoom_start},{ken_burns.zoom_start}+({ken_burns.zoom_end}-{ken_burns.zoom_start})*{easing_func})"
        x_expr = f"if(lte(on,1),{ken_burns.pan_start_x}*iw,{ken_burns.pan_start_x}*iw+({ken_burns.pan_end_x}-{ken_burns.pan_start_x})*iw*{easing_func})"
        y_expr = f"if(lte(on,1),{ken_burns.pan_start_y}*ih,{ken_burns.pan_start_y}*ih+({ken_burns.pan_end_y}-{ken_burns.pan_start_y})*ih*{easing_func})"
        
        return f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s=1920x1080"
    
    def _get_easing_function(self, easing_type: str) -> str:
        """イージング関数を取得"""
        easing_functions = {
            "linear": "on/duration",
            "ease_in": "pow(on/duration,2)",
            "ease_out": "1-pow(1-on/duration,2)",
            "ease_in_out": "if(lt(on/duration,0.5),2*pow(on/duration,2),1-2*pow(1-on/duration,2))"
        }
        
        return easing_functions.get(easing_type, easing_functions["linear"])


class BackgroundGenerator:
    """背景生成モジュール"""
    
    def __init__(
        self, 
        repository: ProjectRepository,
        config_manager: ConfigManager,
        image_client: ImageGenerationClient,
        file_system_manager: FileSystemManager
    ):
        self.repository = repository
        self.config_manager = config_manager
        self.image_client = image_client
        self.file_system_manager = file_system_manager
        
        # 依存注入
        self.data_access = DatabaseDataAccess(repository, config_manager)
        self.image_generation = GeminiImageGeneration(image_client)
        self.video_processing = FFmpegVideoProcessing()
        
        # DAO初期化
        self.dao = BackgroundGenerationDAO(repository.db_manager)
    
    def generate_backgrounds(self, input_data: BackgroundGenerationInput) -> BackgroundGenerationOutput:
        """背景生成メイン処理"""
        start_time = datetime.now()
        logger.info(f"背景生成開始: プロジェクト={input_data.project_id}")
        
        try:
            # 1. シーン分析
            scenes = self._analyze_scenes(input_data)
            
            # 2. 背景画像生成
            background_images = []
            for scene in scenes:
                bg_image = self._generate_background_image(scene, input_data.project_id)
                background_images.append(bg_image)
            
            # 3. Ken Burnsエフェクト計算
            ken_burns_effects = []
            for scene in scenes:
                ken_burns = self._calculate_ken_burns_effect(scene)
                ken_burns_effects.append(ken_burns)
            
            # 4. 背景動画生成
            background_videos = []
            for scene, bg_image, ken_burns in zip(scenes, background_images, ken_burns_effects):
                bg_video = self._generate_background_video(scene, bg_image, ken_burns, input_data.project_id)
                background_videos.append(bg_video)
            
            # 5. 結果組み立て
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            output = BackgroundGenerationOutput(
                background_images=background_images,
                background_videos=background_videos,
                scene_analyses=scenes,
                generation_metadata={
                    "total_scenes": len(scenes),
                    "total_generation_time": generation_time,
                    "api_calls_count": len(background_images),
                    "timestamp": end_time.isoformat()
                }
            )
            
            # 6. データベース保存
            self.data_access.save_background_generation_result(input_data.project_id, output)
            
            logger.info(f"背景生成完了: プロジェクト={input_data.project_id}, シーン数={len(scenes)}, 処理時間={generation_time:.2f}秒")
            return output
            
        except Exception as e:
            logger.error(f"背景生成エラー: {e}")
            raise RuntimeError(f"Background generation failed: {e}")
    
    def _analyze_scenes(self, input_data: BackgroundGenerationInput) -> List[SceneAnalysis]:
        """スクリプトからシーン分析"""
        script_data = input_data.script_data
        segments = script_data.get("segments", [])
        
        # セグメントをシーンタイプでグループ化
        scene_groups = {}
        for segment in segments:
            scene_type = segment.get("scene_type", "general")
            if scene_type not in scene_groups:
                scene_groups[scene_type] = []
            scene_groups[scene_type].append(segment)
        
        # シーン分析結果を作成
        scenes = []
        for scene_type, group_segments in scene_groups.items():
            scene_id = str(uuid.uuid4())[:8]
            
            # シーン説明を生成
            description = self._generate_scene_description(group_segments, script_data.get("theme", ""))
            
            # 総時間計算
            total_duration = sum(seg.get("estimated_duration", 3.0) for seg in group_segments)
            
            # プロンプト生成
            prompt = self._generate_scene_prompt(scene_type, description, script_data.get("theme", ""))
            
            # スタイル決定
            style = input_data.generation_config.get("style", "anime_style")
            
            scene = SceneAnalysis(
                scene_id=scene_id,
                scene_type=scene_type,
                description=description,
                duration=total_duration,
                prompt=prompt,
                style=style,
                segments=[seg.get("segment_id", 0) for seg in group_segments],
                metadata={
                    "segment_count": len(group_segments),
                    "theme": script_data.get("theme", ""),
                    "analysis_timestamp": datetime.now().isoformat()
                }
            )
            
            scenes.append(scene)
        
        return scenes
    
    def _generate_scene_description(self, segments: List[Dict[str, Any]], theme: str) -> str:
        """シーン説明を生成"""
        # セグメントのテキストから重要なキーワードを抽出
        all_text = " ".join(seg.get("text", "") for seg in segments)
        
        # 簡単なキーワード抽出（実装簡略化）
        keywords = []
        if "桜" in all_text or "春" in all_text:
            keywords.append("桜・春")
        if "室内" in all_text or "家" in all_text:
            keywords.append("室内")
        if "自然" in all_text or "外" in all_text:
            keywords.append("自然・屋外")
        
        if keywords:
            return f"{theme}について、{', '.join(keywords)}の場面"
        else:
            return f"{theme}に関する一般的な場面"
    
    def _generate_scene_prompt(self, scene_type: str, description: str, theme: str) -> str:
        """シーン用画像生成プロンプトを生成"""
        scene_prompts = {
            "outdoor_nature": f"Beautiful outdoor nature scene, {description}, scenic landscape, natural lighting",
            "indoor_kitchen": f"Cozy indoor kitchen scene, {description}, warm lighting, comfortable atmosphere",
            "indoor_room": f"Comfortable indoor room scene, {description}, soft lighting, homey atmosphere",
            "general": f"General scene for {description}, appropriate setting for the theme"
        }
        
        base_prompt = scene_prompts.get(scene_type, scene_prompts["general"])
        return f"{base_prompt}, related to {theme}"
    
    def _generate_background_image(self, scene: SceneAnalysis, project_id: str) -> BackgroundImage:
        """背景画像を生成"""
        # プロジェクトディレクトリ取得
        project_dir = Path(self.file_system_manager.get_project_directory(project_id))
        images_dir = project_dir / "files" / "images" / "backgrounds"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # 画像ファイルパス
        image_filename = f"scene_{scene.scene_id}.png"
        image_path = images_dir / image_filename
        
        # 画像生成
        generation_result = self.image_generation.generate_background_image(
            prompt=scene.prompt,
            style=scene.style,
            resolution="1920x1080"
        )
        
        # 画像データをファイルに保存
        with open(image_path, "wb") as f:
            f.write(generation_result["image_data"])
        
        file_size = os.path.getsize(image_path)
        
        return BackgroundImage(
            scene_id=scene.scene_id,
            image_path=str(image_path),
            resolution="1920x1080",
            file_size=file_size,
            generation_metadata=generation_result["metadata"]
        )
    
    def _calculate_ken_burns_effect(self, scene: SceneAnalysis) -> KenBurnsEffect:
        """Ken Burnsエフェクトを計算"""
        # エフェクトパラメータをランダムに生成（自然な動きのため）
        zoom_start = random.uniform(1.0, 1.1)
        zoom_end = random.uniform(1.1, 1.3)
        
        # パン開始・終了位置（画像内の相対座標）
        pan_start_x = random.uniform(0.0, 0.2)
        pan_start_y = random.uniform(0.0, 0.2)
        pan_end_x = random.uniform(0.8, 1.0)
        pan_end_y = random.uniform(0.8, 1.0)
        
        # イージング関数選択
        easing_functions = ["linear", "ease_in", "ease_out", "ease_in_out"]
        easing_function = random.choice(easing_functions)
        
        return KenBurnsEffect(
            scene_id=scene.scene_id,
            duration=scene.duration,
            zoom_start=zoom_start,
            zoom_end=zoom_end,
            pan_start_x=pan_start_x,
            pan_start_y=pan_start_y,
            pan_end_x=pan_end_x,
            pan_end_y=pan_end_y,
            easing_function=easing_function,
            metadata={
                "calculation_method": "random_natural",
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def _generate_background_video(
        self, 
        scene: SceneAnalysis,
        background_image: BackgroundImage,
        ken_burns: KenBurnsEffect,
        project_id: str
    ) -> BackgroundVideo:
        """背景動画を生成"""
        # プロジェクトディレクトリ取得
        project_dir = Path(self.file_system_manager.get_project_directory(project_id))
        video_dir = project_dir / "files" / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # 動画ファイルパス
        video_filename = f"background_{scene.scene_id}.mp4"
        video_path = video_dir / video_filename
        
        # 設定から動画パラメータを取得
        config = self.config_manager.get_value("background_generation", {})
        fps = config.get("video_encoding", {}).get("fps", 30)
        
        # Ken Burns動画生成
        video_result = self.video_processing.create_ken_burns_video(
            image_path=background_image.image_path,
            output_path=str(video_path),
            ken_burns=ken_burns,
            fps=fps
        )
        
        return BackgroundVideo(
            scene_id=scene.scene_id,
            video_path=str(video_path),
            duration=ken_burns.duration,
            resolution="1920x1080",
            fps=fps,
            file_size=video_result["file_size"],
            ken_burns_metadata=video_result["metadata"]
        ) 