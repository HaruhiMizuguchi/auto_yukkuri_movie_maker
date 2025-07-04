"""
設定ファイルテンプレート生成機能

TDD Green段階: テストを通すための最小実装
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging


class ConfigTemplateGenerator:
    """設定ファイルテンプレート生成器"""
    
    def __init__(self, config_dir: str, logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            config_dir: 設定ファイルディレクトリパス
            logger: ロガー
        """
        self.config_dir = Path(config_dir)
        self.logger = logger or logging.getLogger(__name__)
        
        # 設定ディレクトリ作成
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # テンプレート定義
        self._templates = {
            "llm_config.yaml": self._get_llm_template(),
            "voice_config.yaml": self._get_voice_template(),
            "character_config.yaml": self._get_character_template(),
            "subtitle_config.yaml": self._get_subtitle_template(),
            "encoding_config.yaml": self._get_encoding_template(),
            "youtube_config.yaml": self._get_youtube_template()
        }
        
    def get_available_templates(self) -> List[str]:
        """利用可能なテンプレート一覧を取得"""
        return list(self._templates.keys())
        
    def generate_template(
        self, 
        template_name: str, 
        custom_values: Optional[Dict[str, Any]] = None,
        backup_existing: bool = False
    ) -> bool:
        """
        単一テンプレートを生成
        
        Args:
            template_name: テンプレート名
            custom_values: カスタム値
            backup_existing: 既存ファイルをバックアップするか
            
        Returns:
            成功した場合True
        """
        try:
            if template_name not in self._templates:
                self.logger.error(f"テンプレート '{template_name}' は存在しません")
                return False
                
            # テンプレート取得
            template_data = self._templates[template_name].copy()
            
            # カスタム値を適用
            if custom_values:
                template_data = self._apply_custom_values(template_data, custom_values)
                
            # ファイルパス
            file_path = self.config_dir / template_name
            
            # 既存ファイルのバックアップ
            if backup_existing and file_path.exists():
                self._backup_existing_file(file_path)
                
            # ファイル書き込み
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(template_data, f, default_flow_style=False, allow_unicode=True)
                
            self.logger.info(f"テンプレート '{template_name}' を生成しました: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"テンプレート生成エラー: {e}")
            return False
            
    def generate_all_templates(
        self, 
        environment: str = "production",
        custom_values: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        全テンプレートを生成
        
        Args:
            environment: 環境（development/production）
            custom_values: テンプレート別カスタム値
            
        Returns:
            生成結果のリスト
        """
        results = []
        
        for template_name in self.get_available_templates():
            # 環境別設定を適用
            env_values = self._get_environment_values(environment)
            
            # テンプレート別カスタム値を適用
            if custom_values and template_name in custom_values:
                env_values.update(custom_values[template_name])
                
            # テンプレート生成
            success = self.generate_template(template_name, env_values)
            
            results.append({
                "template": template_name,
                "success": success,
                "environment": environment
            })
            
        return results
        
    def validate_template(self, template_name: str) -> Dict[str, Any]:
        """
        テンプレートの検証
        
        Args:
            template_name: テンプレート名
            
        Returns:
            検証結果
        """
        file_path = self.config_dir / template_name
        
        if not file_path.exists():
            return {
                "valid": False,
                "errors": [f"ファイル '{template_name}' が存在しません"]
            }
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
                
            return {
                "valid": True,
                "errors": []
            }
            
        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [f"YAML構文エラー: {e}"]
            }
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"ファイル読み込みエラー: {e}"]
            }
            
    def get_template_info(self, template_name: str) -> Dict[str, Any]:
        """
        テンプレート情報を取得
        
        Args:
            template_name: テンプレート名
            
        Returns:
            テンプレート情報
        """
        template_info = {
            "llm_config.yaml": {
                "name": "LLM Configuration",
                "description": "LLM API設定（OpenAI、Anthropic、Google等）",
                "required_fields": ["llm.primary_provider"],
                "optional_fields": ["llm.openai.temperature", "llm.openai.max_tokens"]
            },
            "voice_config.yaml": {
                "name": "Voice Configuration", 
                "description": "音声合成設定（AIVIS Speech、Azure等）",
                "required_fields": ["tts.primary_provider"],
                "optional_fields": ["tts.aivis.voice_presets"]
            },
            "character_config.yaml": {
                "name": "Character Configuration",
                "description": "キャラクター・立ち絵設定",
                "required_fields": ["characters.available_characters"],
                "optional_fields": ["characters.animation.frame_rate"]
            },
            "subtitle_config.yaml": {
                "name": "Subtitle Configuration",
                "description": "字幕設定",
                "required_fields": ["subtitles.font.family"],
                "optional_fields": ["subtitles.effects.fade_in_duration"]
            },
            "encoding_config.yaml": {
                "name": "Encoding Configuration",
                "description": "動画エンコード設定",
                "required_fields": ["encoding.default_preset"],
                "optional_fields": ["encoding.ffmpeg.crf"]
            },
            "youtube_config.yaml": {
                "name": "YouTube Configuration",
                "description": "YouTube投稿設定",
                "required_fields": ["youtube.upload.privacy_status"],
                "optional_fields": ["youtube.metadata.tags.default"]
            }
        }
        
        return template_info.get(template_name, {
            "name": "Unknown Template",
            "description": "不明なテンプレート",
            "required_fields": [],
            "optional_fields": []
        })
        
    def _apply_custom_values(self, template_data: Dict[str, Any], custom_values: Dict[str, Any]) -> Dict[str, Any]:
        """カスタム値を適用"""
        # 深いマージを実装（簡単な実装）
        for key, value in custom_values.items():
            if key in template_data:
                if isinstance(template_data[key], dict) and isinstance(value, dict):
                    template_data[key].update(value)
                else:
                    template_data[key] = value
            else:
                # LLM設定の特別処理
                if "llm" in template_data and key in ["primary_provider", "temperature", "max_tokens"]:
                    if key == "primary_provider":
                        template_data["llm"]["primary_provider"] = value
                    elif key in ["temperature", "max_tokens"]:
                        template_data["llm"]["openai"][key] = value
                        
        return template_data
        
    def _backup_existing_file(self, file_path: Path) -> None:
        """既存ファイルをバックアップ"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.parent / f"{file_path.name}.backup.{timestamp}"
        
        import shutil
        shutil.copy2(file_path, backup_path)
        self.logger.info(f"既存ファイルをバックアップしました: {backup_path}")
        
    def _get_environment_values(self, environment: str) -> Dict[str, Any]:
        """環境別設定値を取得"""
        if environment == "development":
            return {
                "debug": True,
                "log_level": "DEBUG",
                "timeout": 10
            }
        elif environment == "production":
            return {
                "debug": False,
                "log_level": "INFO",
                "timeout": 30
            }
        else:
            return {}
            
    def _get_llm_template(self) -> Dict[str, Any]:
        """LLM設定テンプレート"""
        return {
            "llm": {
                "primary_provider": "openai",
                "openai": {
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "timeout": 30,
                    "retry_attempts": 3
                },
                "anthropic": {
                    "model": "claude-3-sonnet-20240229",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "timeout": 30
                },
                "prompts": {
                    "theme_generation": "以下の条件で動画テーマを生成してください：\n- ターゲット: {target_audience}\n- ジャンル: {preferred_genres}\n- 除外ジャンル: {excluded_genres}\n- 動画尺: {duration}分\n",
                    "script_generation": "以下のテーマで{speaker_count}人の{tone}な雑談動画スクリプトを生成：\nテーマ: {theme}\n動画尺: {duration}分\n話者: {speakers}"
                }
            }
        }
        
    def _get_voice_template(self) -> Dict[str, Any]:
        """音声設定テンプレート"""
        return {
            "tts": {
                "primary_provider": "aivis",
                "aivis": {
                    "timeout": 60,
                    "retry_attempts": 3,
                    "voice_presets": {
                        "reimu": {
                            "voice_id": "reimu_voice_001",
                            "speed": 1.0,
                            "pitch": 0.0,
                            "emotion": "normal"
                        },
                        "marisa": {
                            "voice_id": "marisa_voice_001",
                            "speed": 1.1,
                            "pitch": -0.1,
                            "emotion": "cheerful"
                        }
                    }
                },
                "audio_processing": {
                    "sample_rate": 44100,
                    "channels": 2,
                    "normalize_volume": True,
                    "target_lufs": -23.0,
                    "fade_in_ms": 100,
                    "fade_out_ms": 200
                }
            }
        }
        
    def _get_character_template(self) -> Dict[str, Any]:
        """キャラクター設定テンプレート"""
        return {
            "characters": {
                "enabled": True,
                "available_characters": {
                    "reimu": {
                        "name": "博麗霊夢",
                        "sprite_path": "assets/characters/reimu/",
                        "expressions": ["normal", "happy", "angry", "surprised"],
                        "mouth_sprites": {
                            "open": "mouth_open.png",
                            "closed": "mouth_closed.png"
                        },
                        "position": {
                            "x": 100,
                            "y": 200,
                            "scale": 1.0
                        }
                    },
                    "marisa": {
                        "name": "霧雨魔理沙",
                        "sprite_path": "assets/characters/marisa/",
                        "expressions": ["normal", "happy", "smug", "thinking"],
                        "mouth_sprites": {
                            "open": "mouth_open.png",
                            "closed": "mouth_closed.png"
                        },
                        "position": {
                            "x": 700,
                            "y": 200,
                            "scale": 1.0
                        }
                    }
                },
                "animation": {
                    "frame_rate": 30,
                    "mouth_sync_enabled": True,
                    "expression_change_threshold": 0.5
                },
                "output": {
                    "resolution": [1920, 1080],
                    "background_alpha": 0,
                    "video_codec": "libx264",
                    "pixel_format": "yuva420p"
                }
            }
        }
        
    def _get_subtitle_template(self) -> Dict[str, Any]:
        """字幕設定テンプレート"""
        return {
            "subtitles": {
                "font": {
                    "family": "Noto Sans CJK JP",
                    "size": 48,
                    "bold": True,
                    "italic": False
                },
                "style": {
                    "primary_color": "#FFFFFF",
                    "secondary_color": "#000000",
                    "outline_width": 3,
                    "shadow_offset": [2, 2],
                    "shadow_color": "#808080"
                },
                "position": {
                    "alignment": "bottom_center",
                    "margin_bottom": 80,
                    "margin_left": 50,
                    "margin_right": 50
                },
                "timing": {
                    "min_duration": 1.0,
                    "max_line_length": 30,
                    "line_break_threshold": 20
                },
                "effects": {
                    "fade_in_duration": 0.3,
                    "fade_out_duration": 0.3,
                    "typewriter_effect": False
                }
            }
        }
        
    def _get_encoding_template(self) -> Dict[str, Any]:
        """エンコード設定テンプレート"""
        return {
            "encoding": {
                "presets": {
                    "youtube_landscape": {
                        "resolution": [1920, 1080],
                        "frame_rate": 30,
                        "video_codec": "libx264",
                        "video_bitrate": "8M",
                        "audio_codec": "aac",
                        "audio_bitrate": "320k",
                        "pixel_format": "yuv420p"
                    },
                    "high_quality": {
                        "resolution": [1920, 1080],
                        "frame_rate": 60,
                        "video_codec": "libx264",
                        "video_bitrate": "15M",
                        "audio_codec": "aac",
                        "audio_bitrate": "320k",
                        "pixel_format": "yuv420p"
                    }
                },
                "default_preset": "youtube_landscape",
                "ffmpeg": {
                    "threads": 0,
                    "preset": "medium",
                    "crf": 18
                }
            }
        }
        
    def _get_youtube_template(self) -> Dict[str, Any]:
        """YouTube設定テンプレート"""
        return {
            "youtube": {
                "upload": {
                    "privacy_status": "private",
                    "category_id": "22",
                    "default_language": "ja"
                },
                "metadata": {
                    "title_template": "{title}",
                    "description_template": "{description}\n\n#ゆっくり解説 #東方 #{tags}\n\n【注意事項】\nこの動画は東方Projectの二次創作です。\n東方Project © 上海アリス幻樂団\n",
                    "tags": {
                        "default": ["ゆっくり解説", "東方", "霊夢", "魔理沙"],
                        "max_count": 15
                    }
                },
                "thumbnail": {
                    "auto_generate": True,
                    "template_path": "assets/templates/thumbnail_template.png"
                },
                "limits": {
                    "max_uploads_per_day": 5,
                    "max_file_size_gb": 2,
                    "check_quotas": True
                }
            }
        }