"""
CLI コマンドの単体テスト

CLIインターフェースの各機能をテスト
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import click
    from click.testing import CliRunner
    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False

# テスト対象のインポート（click不要のフォールバック実装を使用）
try:
    from src.cli.commands.project_commands import project_group
    from src.cli.commands.generate_commands import generate_group
    from src.cli.commands.status_commands import status_group
    from src.cli.commands.config_commands import config_group
    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False

@pytest.mark.skipif(not CLICK_AVAILABLE or not CLI_AVAILABLE, 
                   reason="Click または CLI モジュールが利用できません")
class TestProjectCommands:
    """プロジェクト管理コマンドのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.runner = CliRunner()
    
    def test_project_create(self):
        """プロジェクト作成コマンドのテスト"""
        result = self.runner.invoke(project_group, ['create', 'test_project'])
        assert result.exit_code == 0
        assert 'test_project' in result.output
        assert 'プロジェクト' in result.output
    
    def test_project_list(self):
        """プロジェクト一覧コマンドのテスト"""
        result = self.runner.invoke(project_group, ['list'])
        assert result.exit_code == 0
        assert 'プロジェクト' in result.output
    
    def test_project_list_with_status_filter(self):
        """ステータスフィルター付きプロジェクト一覧のテスト"""
        result = self.runner.invoke(project_group, ['list', '--status', 'active'])
        assert result.exit_code == 0
    
    def test_project_delete_with_confirmation(self):
        """確認付きプロジェクト削除のテスト"""
        with patch('builtins.input', return_value='n'):
            result = self.runner.invoke(project_group, ['delete', 'test-project-id'])
            assert result.exit_code == 0
            assert 'キャンセル' in result.output
    
    def test_project_delete_with_force(self):
        """強制削除のテスト"""
        result = self.runner.invoke(project_group, ['delete', 'test-project-id', '--force'])
        assert result.exit_code == 0
        assert '削除しました' in result.output
    
    def test_project_info(self):
        """プロジェクト情報表示のテスト"""
        result = self.runner.invoke(project_group, ['info', 'test-project-id'])
        assert result.exit_code == 0
        assert 'プロジェクト' in result.output

@pytest.mark.skipif(not CLICK_AVAILABLE or not CLI_AVAILABLE,
                   reason="Click または CLI モジュールが利用できません")
class TestGenerateCommands:
    """動画生成コマンドのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.runner = CliRunner()
    
    def test_generate_start_dry_run(self):
        """ドライラン実行のテスト"""
        result = self.runner.invoke(generate_group, ['start', 'test-project-id', '--dry-run'])
        assert result.exit_code == 0
        assert '実行プラン' in result.output
    
    @patch('time.sleep')  # 実際の待機をスキップ
    def test_generate_start(self, mock_sleep):
        """動画生成開始のテスト"""
        mock_sleep.return_value = None
        result = self.runner.invoke(generate_group, ['start', 'test-project-id'])
        assert result.exit_code == 0
    
    def test_generate_resume(self):
        """プロジェクト再開のテスト"""
        result = self.runner.invoke(generate_group, ['resume', 'test-project-id'])
        assert result.exit_code == 0
        assert '再開' in result.output
    
    def test_generate_stop(self):
        """プロジェクト停止のテスト"""
        with patch('builtins.input', return_value='y'):
            result = self.runner.invoke(generate_group, ['stop', 'test-project-id'])
            assert result.exit_code == 0
            assert '停止' in result.output

@pytest.mark.skipif(not CLICK_AVAILABLE or not CLI_AVAILABLE,
                   reason="Click または CLI モジュールが利用できません")
class TestStatusCommands:
    """ステータス確認コマンドのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.runner = CliRunner()
    
    def test_status_show(self):
        """プロジェクトステータス表示のテスト"""
        result = self.runner.invoke(status_group, ['show', 'test-project-id'])
        assert result.exit_code == 0
        assert 'プロジェクト' in result.output
    
    def test_status_show_detailed(self):
        """詳細ステータス表示のテスト"""
        result = self.runner.invoke(status_group, ['show', 'test-project-id', '--detailed'])
        assert result.exit_code == 0
        assert 'ステップ' in result.output
    
    def test_status_list(self):
        """全プロジェクトステータス一覧のテスト"""
        result = self.runner.invoke(status_group, ['list'])
        assert result.exit_code == 0
        assert 'プロジェクト' in result.output
    
    def test_status_system(self):
        """システムステータス表示のテスト"""
        result = self.runner.invoke(status_group, ['system'])
        assert result.exit_code == 0
        assert 'システム' in result.output

@pytest.mark.skipif(not CLICK_AVAILABLE or not CLI_AVAILABLE,
                   reason="Click または CLI モジュールが利用できません")
class TestConfigCommands:
    """設定管理コマンドのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.runner = CliRunner()
    
    def test_config_init(self):
        """設定初期化のテスト"""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(config_group, ['init'])
            assert result.exit_code == 0
            assert '設定ファイルを作成' in result.output
            assert Path('.env').exists()
    
    def test_config_init_force(self):
        """強制設定初期化のテスト"""
        with self.runner.isolated_filesystem():
            # 最初に設定ファイルを作成
            Path('.env').touch()
            result = self.runner.invoke(config_group, ['init', '--force'])
            assert result.exit_code == 0
            assert '設定ファイルを作成' in result.output
    
    def test_config_show_table(self):
        """設定表示（テーブル形式）のテスト"""
        result = self.runner.invoke(config_group, ['show'])
        assert result.exit_code == 0
        assert '設定' in result.output
    
    def test_config_show_json(self):
        """設定表示（JSON形式）のテスト"""
        result = self.runner.invoke(config_group, ['show', '--format', 'json'])
        assert result.exit_code == 0
    
    def test_config_validate(self):
        """設定検証のテスト"""
        result = self.runner.invoke(config_group, ['validate'])
        assert result.exit_code == 0
        assert '検証' in result.output
    
    def test_config_set(self):
        """設定値更新のテスト"""
        result = self.runner.invoke(config_group, ['set', 'test_key', 'test_value'])
        assert result.exit_code == 0
        assert '設定を更新' in result.output

class TestCLIHelpers:
    """CLI ヘルパー機能のテスト"""
    
    def test_validate_project_id_valid(self):
        """有効なプロジェクトIDの検証"""
        from src.cli.utils.cli_helpers import validate_project_id
        
        valid_ids = [
            'abcd1234-ab12-cd34-ef56-123456789012',
            '12345678-1234-1234-1234-123456789abc'
        ]
        
        for project_id in valid_ids:
            assert validate_project_id(project_id) == True
    
    def test_validate_project_id_invalid(self):
        """無効なプロジェクトIDの検証"""
        from src.cli.utils.cli_helpers import validate_project_id
        
        invalid_ids = [
            'invalid-id',
            'short',
            'abcd1234-ab12-cd34-ef56',  # 短すぎる
            'abcd1234-ab12-cd34-ef56-123456789012-extra',  # 長すぎる
            'gggg1234-ab12-cd34-ef56-123456789012',  # 無効な16進数文字
        ]
        
        for project_id in invalid_ids:
            assert validate_project_id(project_id) == False
    
    def test_get_project_root(self):
        """プロジェクトルート取得のテスト"""
        from src.cli.utils.cli_helpers import get_project_root
        
        root = get_project_root()
        assert isinstance(root, Path)
        assert root.exists()

# テスト実行用のメイン関数
if __name__ == "__main__":
    pytest.main([__file__, "-v"])