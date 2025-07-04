"""
設定ファイルテンプレート生成機能のテスト（TDD）

Red段階: まずテストを書いて失敗させる
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any, List
import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cli.core.config_template_generator import ConfigTemplateGenerator


class TestConfigTemplateGenerator:
    """設定ファイルテンプレート生成機能のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        # 一時ディレクトリ作成
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(exist_ok=True)
        
        # モックオブジェクト作成
        self.mock_logger = Mock()
        
    def teardown_method(self):
        """テストクリーンアップ"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_config_template_generator_initialization(self):
        """設定テンプレート生成器の初期化テスト"""
        # GIVEN: 設定ディレクトリパスが与えられた時
        config_path = str(self.config_dir)
        
        # WHEN: 設定テンプレート生成器を初期化する
        generator = ConfigTemplateGenerator(config_path, self.mock_logger)
        
        # THEN: 正常に初期化される
        assert generator.config_dir == Path(config_path)
        assert generator.logger == self.mock_logger
        
    def test_get_available_templates(self):
        """利用可能なテンプレート一覧取得テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: 利用可能なテンプレート一覧を取得する
        templates = generator.get_available_templates()
        
        # THEN: 期待されるテンプレートが含まれている
        expected_templates = [
            "llm_config.yaml",
            "voice_config.yaml", 
            "character_config.yaml",
            "subtitle_config.yaml",
            "encoding_config.yaml",
            "youtube_config.yaml"
        ]
        
        for template in expected_templates:
            assert template in templates
        
    def test_generate_single_template(self):
        """単一テンプレート生成テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: LLM設定テンプレートを生成する
        result = generator.generate_template("llm_config.yaml")
        
        # THEN: テンプレートが正常に生成される
        assert result is True
        
        # AND: ファイルが作成されている
        llm_config_path = self.config_dir / "llm_config.yaml"
        assert llm_config_path.exists()
        
        # AND: 有効なYAMLファイルである
        with open(llm_config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            assert config_data is not None
            assert "llm" in config_data
            
    def test_generate_all_templates(self):
        """全テンプレート生成テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: 全テンプレートを生成する
        results = generator.generate_all_templates()
        
        # THEN: 全テンプレートが正常に生成される
        assert len(results) == 6  # 6つのテンプレート
        assert all(result["success"] for result in results)
        
        # AND: 全ファイルが作成されている
        expected_files = [
            "llm_config.yaml",
            "voice_config.yaml",
            "character_config.yaml", 
            "subtitle_config.yaml",
            "encoding_config.yaml",
            "youtube_config.yaml"
        ]
        
        for filename in expected_files:
            file_path = self.config_dir / filename
            assert file_path.exists()
            
    def test_validate_template_content(self):
        """テンプレート内容検証テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: テンプレートを生成して検証する
        generator.generate_template("llm_config.yaml")
        validation_result = generator.validate_template("llm_config.yaml")
        
        # THEN: 検証が成功する
        assert validation_result["valid"] is True
        assert validation_result["errors"] == []
        
    def test_template_with_custom_values(self):
        """カスタム値でのテンプレート生成テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # AND: カスタム値が指定された時
        custom_values = {
            "primary_provider": "anthropic",
            "temperature": 0.8,
            "max_tokens": 3000
        }
        
        # WHEN: カスタム値でテンプレートを生成する
        result = generator.generate_template("llm_config.yaml", custom_values)
        
        # THEN: テンプレートが正常に生成される
        assert result is True
        
        # AND: カスタム値が反映されている
        with open(self.config_dir / "llm_config.yaml", 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            assert config_data["llm"]["primary_provider"] == "anthropic"
            assert config_data["llm"]["openai"]["temperature"] == 0.8
            assert config_data["llm"]["openai"]["max_tokens"] == 3000
            
    def test_template_generation_error_handling(self):
        """テンプレート生成エラーハンドリングテスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: 存在しないテンプレートを生成しようとする
        result = generator.generate_template("nonexistent_config.yaml")
        
        # THEN: エラーが適切に処理される
        assert result is False
        
        # AND: エラーログが出力される
        self.mock_logger.error.assert_called()
        
    def test_existing_file_backup(self):
        """既存ファイルバックアップテスト"""
        # GIVEN: 既存の設定ファイルがある時
        existing_config = self.config_dir / "llm_config.yaml"
        existing_config.write_text("existing_content", encoding='utf-8')
        
        # AND: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: 同じファイル名でテンプレートを生成する
        result = generator.generate_template("llm_config.yaml", backup_existing=True)
        
        # THEN: テンプレートが正常に生成される
        assert result is True
        
        # AND: バックアップファイルが作成される
        backup_files = list(self.config_dir.glob("llm_config.yaml.backup.*"))
        assert len(backup_files) == 1
        
        # AND: バックアップファイルに元の内容が保存される
        backup_content = backup_files[0].read_text(encoding='utf-8')
        assert backup_content == "existing_content"
        
    def test_get_template_info(self):
        """テンプレート情報取得テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: テンプレート情報を取得する
        info = generator.get_template_info("llm_config.yaml")
        
        # THEN: 期待される情報が含まれている
        assert "name" in info
        assert "description" in info
        assert "required_fields" in info
        assert "optional_fields" in info
        assert info["name"] == "LLM Configuration"
        
    def test_template_validation_with_errors(self):
        """エラーを含むテンプレート検証テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # AND: 無効なYAMLファイルが存在する時
        invalid_config = self.config_dir / "invalid_config.yaml"
        invalid_config.write_text("invalid: yaml: content:", encoding='utf-8')
        
        # WHEN: 無効なファイルを検証する
        validation_result = generator.validate_template("invalid_config.yaml")
        
        # THEN: 検証が失敗する
        assert validation_result["valid"] is False
        assert len(validation_result["errors"]) > 0
        
    def test_generate_templates_with_environment(self):
        """環境別テンプレート生成テスト"""
        # GIVEN: 設定テンプレート生成器が初期化された時
        generator = ConfigTemplateGenerator(str(self.config_dir), self.mock_logger)
        
        # WHEN: 開発環境用テンプレートを生成する
        result = generator.generate_all_templates(environment="development")
        
        # THEN: 環境に応じたテンプレートが生成される
        assert all(result_item["success"] for result_item in result)
        
        # AND: 開発環境用の設定が含まれている
        with open(self.config_dir / "llm_config.yaml", 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            # 開発環境では詳細ログが有効になっている等の確認
            assert config_data is not None