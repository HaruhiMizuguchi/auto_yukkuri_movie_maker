"""
設定管理システム

このモジュールは設定ファイルの読み込み、環境変数展開、
バリデーション、デフォルト値管理を行うConfigManagerクラスを提供します。
"""

import os
import json
import yaml
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
import copy
from jsonschema import validate, ValidationError as JsonValidationError


class ConfigError(Exception):
    """設定関連のエラー"""
    pass


class ValidationError(Exception):
    """設定値検証エラー"""
    pass


class ConfigManager:
    """
    設定管理システム
    
    YAML/JSON設定ファイルの読み込み、環境変数展開、
    バリデーション、デフォルト値管理機能を提供します。
    """

    def __init__(self, config_dir: str = "config"):
        """
        ConfigManagerを初期化
        
        Args:
            config_dir: 設定ファイルディレクトリのパス
        """
        self.config_dir = Path(config_dir)
        self.current_profile: Optional[str] = None
        self.defaults: Dict[str, Any] = {}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.logger = logging.getLogger(__name__)
        
        # 環境変数展開用の正規表現パターン
        self.env_pattern = re.compile(r'\$\{([^}:]+)(?::([^}]*))?\}')
        
        # サポートするファイル拡張子
        self.supported_extensions = {'.yaml', '.yml', '.json'}

    def load_config(
        self, 
        filename: str, 
        use_cache: bool = True,
        expand_env: bool = True,
        process_includes: bool = True
    ) -> Dict[str, Any]:
        """
        設定ファイルを読み込み
        
        Args:
            filename: 設定ファイル名
            use_cache: キャッシュを使用するか
            expand_env: 環境変数展開を行うか
            process_includes: インクルード処理を行うか
            
        Returns:
            Dict[str, Any]: 読み込まれた設定データ
            
        Raises:
            ConfigError: ファイル読み込みエラー
        """
        config_path = self.config_dir / filename
        
        # ファイル存在確認
        if not config_path.exists():
            raise ConfigError(f"Configuration file '{filename}' not found at '{config_path}'")
        
        # キャッシュ確認
        if use_cache and self._is_cache_valid(filename, config_path):
            self.logger.debug(f"Loading config from cache: {filename}")
            return copy.deepcopy(self.cache[filename])
        
        try:
            # ファイル読み込み
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # ファイル形式に応じて解析
            config = self._parse_config_file(content, config_path.suffix)
            
            # 環境変数展開
            if expand_env:
                config = self._expand_environment_variables(config)
            
            # インクルード処理
            if process_includes:
                config = self._process_includes(config)
            
            # プロファイル適用
            if self.current_profile:
                config = self._apply_profile(config)
            
            # デフォルト値適用
            config = self._apply_defaults(config)
            
            # キャッシュに保存
            if use_cache:
                self.cache[filename] = copy.deepcopy(config)
                self.cache_timestamps[filename] = datetime.now()
            
            self.logger.info(f"Successfully loaded config: {filename}")
            return config
            
        except Exception as e:
            raise ConfigError(f"Failed to load config '{filename}': {str(e)}") from e

    def _parse_config_file(self, content: str, extension: str) -> Dict[str, Any]:
        """
        ファイル形式に応じて設定ファイルを解析
        
        Args:
            content: ファイル内容
            extension: ファイル拡張子
            
        Returns:
            Dict[str, Any]: 解析された設定データ
            
        Raises:
            ConfigError: 解析エラー
        """
        try:
            if extension in {'.yaml', '.yml'}:
                return yaml.safe_load(content) or {}
            elif extension == '.json':
                return json.loads(content)
            else:
                raise ConfigError(f"Unsupported file extension: {extension}")
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parsing error: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise ConfigError(f"JSON parsing error: {str(e)}") from e

    def _expand_environment_variables(self, data: Any) -> Any:
        """
        環境変数展開を再帰的に実行
        
        Args:
            data: 展開対象のデータ
            
        Returns:
            Any: 環境変数が展開されたデータ
        """
        if isinstance(data, dict):
            return {key: self._expand_environment_variables(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._expand_environment_variables(item) for item in data]
        elif isinstance(data, str):
            return self._expand_env_string(data)
        else:
            return data

    def _expand_env_string(self, text: str) -> Any:
        """
        文字列内の環境変数を展開
        
        Args:
            text: 展開対象の文字列
            
        Returns:
            Any: 展開された値（型変換後）
        """
        def replace_env_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            
            env_value = os.environ.get(var_name, default_value)
            return env_value
        
        expanded = self.env_pattern.sub(replace_env_var, text)
        
        # 型変換を試行
        return self._convert_type(expanded)

    def _convert_type(self, value: str) -> Any:
        """
        文字列から適切な型への変換
        
        Args:
            value: 変換対象の文字列
            
        Returns:
            Any: 型変換された値
        """
        if not isinstance(value, str):
            return value
        
        # ブール値変換
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # 数値変換（整数）
        try:
            if '.' not in value and value.isdigit():
                return int(value)
        except ValueError:
            pass
        
        # 数値変換（浮動小数点）
        try:
            return float(value)
        except ValueError:
            pass
        
        # 文字列のまま返す
        return value

    def _process_includes(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        インクルード処理を実行
        
        Args:
            config: 処理対象の設定データ
            
        Returns:
            Dict[str, Any]: インクルード処理後の設定データ
        """
        if 'includes' not in config:
            return config
        
        includes = config.pop('includes')
        if not isinstance(includes, list):
            includes = [includes]
        
        # インクルードファイルを順番に読み込んで統合
        for include_file in includes:
            try:
                included_config = self.load_config(
                    include_file, 
                    use_cache=False, 
                    process_includes=True
                )
                config = self._merge_configs(included_config, config)
            except ConfigError as e:
                self.logger.warning(f"Failed to load included file '{include_file}': {e}")
        
        return config

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        設定を深いマージで統合
        
        Args:
            base: ベース設定
            override: 上書き設定
            
        Returns:
            Dict[str, Any]: マージされた設定
        """
        result = copy.deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        
        return result

    def _apply_profile(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        現在のプロファイル設定を適用
        
        Args:
            config: 適用対象の設定データ
            
        Returns:
            Dict[str, Any]: プロファイル適用後の設定データ
        """
        if not self.current_profile:
            return config
        
        try:
            profile_config = self.load_config(
                f"{self.current_profile}.yaml",
                use_cache=False,
                process_includes=False
            )
            
            # プロファイル設定を除去してマージ
            if 'profile' in profile_config:
                profile_config.pop('profile')
            
            return self._merge_configs(config, profile_config)
            
        except ConfigError:
            self.logger.warning(f"Profile config not found: {self.current_profile}")
            return config

    def _apply_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        デフォルト値を適用
        
        Args:
            config: 適用対象の設定データ
            
        Returns:
            Dict[str, Any]: デフォルト値適用後の設定データ
        """
        if not self.defaults:
            return config
        
        return self._merge_configs(self.defaults, config)

    def _is_cache_valid(self, filename: str, config_path: Path) -> bool:
        """
        キャッシュが有効かチェック
        
        Args:
            filename: ファイル名
            config_path: 設定ファイルパス
            
        Returns:
            bool: キャッシュが有効な場合True
        """
        if filename not in self.cache or filename not in self.cache_timestamps:
            return False
        
        # ファイルの更新時間確認
        file_mtime = datetime.fromtimestamp(config_path.stat().st_mtime)
        cache_time = self.cache_timestamps[filename]
        
        return file_mtime <= cache_time

    def load_schema(self, schema_filename: str) -> Dict[str, Any]:
        """
        バリデーション用スキーマを読み込み
        
        Args:
            schema_filename: スキーマファイル名
            
        Returns:
            Dict[str, Any]: スキーマデータ
        """
        schema_config = self.load_config(schema_filename, use_cache=True)
        return schema_config.get('schema', {})

    def validate_config(
        self, 
        config: Dict[str, Any], 
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        設定値をスキーマに基づいて検証
        
        Args:
            config: 検証対象の設定
            schema: バリデーションスキーマ
            
        Returns:
            Dict[str, Any]: 検証結果
        """
        validation_result = {
            "is_valid": True,
            "errors": []
        }
        
        try:
            from jsonschema import Draft7Validator
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(config))
            
            if errors:
                validation_result["is_valid"] = False
                for error in errors:
                    validation_result["errors"].append({
                        "path": list(error.path),
                        "message": error.message,
                        "invalid_value": error.instance,
                        "property": error.path[-1] if error.path else None
                    })
        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["errors"].append({
                "path": [],
                "message": f"Validation error: {str(e)}",
                "invalid_value": None,
                "property": None
            })
        
        return validation_result

    def set_profile(self, profile: str):
        """
        アクティブプロファイルを設定
        
        Args:
            profile: プロファイル名
        """
        self.current_profile = profile
        self.clear_cache()  # プロファイル変更時はキャッシュをクリア
        self.logger.info(f"Profile set to: {profile}")

    def set_defaults(self, defaults: Dict[str, Any]):
        """
        デフォルト値を設定
        
        Args:
            defaults: デフォルト設定
        """
        self.defaults = copy.deepcopy(defaults)
        self.clear_cache()  # デフォルト値変更時はキャッシュをクリア

    def get_merged_config(self) -> Dict[str, Any]:
        """
        デフォルト値とマージされた設定を取得
        
        Returns:
            Dict[str, Any]: マージされた設定
        """
        return copy.deepcopy(self.defaults)

    def merge_configs(
        self, 
        base_config: Dict[str, Any], 
        override_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        設定を統合（外部API）
        
        Args:
            base_config: ベース設定
            override_config: 上書き設定
            
        Returns:
            Dict[str, Any]: 統合された設定
        """
        return self._merge_configs(base_config, override_config)

    def reload_config(self, filename: str) -> Dict[str, Any]:
        """
        設定ファイルを強制的に再読み込み
        
        Args:
            filename: ファイル名
            
        Returns:
            Dict[str, Any]: 再読み込みされた設定
        """
        # キャッシュをクリア
        if filename in self.cache:
            del self.cache[filename]
        if filename in self.cache_timestamps:
            del self.cache_timestamps[filename]
        
        return self.load_config(filename, use_cache=True)

    def get_value(self, path: str, config: Dict[str, Any]) -> Any:
        """
        ドット記法で設定値を取得
        
        Args:
            path: 設定パス（例: "app.database.host"）
            config: 設定データ
            
        Returns:
            Any: 設定値
        """
        keys = path.split('.')
        current = config
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current

    def clear_cache(self):
        """キャッシュをクリア"""
        self.cache.clear()
        self.cache_timestamps.clear()
        self.logger.debug("Config cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """
        キャッシュ情報を取得
        
        Returns:
            Dict[str, Any]: キャッシュ統計情報
        """
        return {
            "cached_files": list(self.cache.keys()),
            "cache_size": len(self.cache),
            "cache_timestamps": {
                filename: timestamp.isoformat()
                for filename, timestamp in self.cache_timestamps.items()
            }
        } 