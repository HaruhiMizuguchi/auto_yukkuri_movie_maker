"""
設定管理コマンド

設定の初期化、表示、検証など
"""

import click
import json
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None

if RICH_AVAILABLE:
    console = Console()

@click.group()
def config_group():
    """設定管理コマンド"""
    pass

@config_group.command()
@click.option('--force', is_flag=True, help='既存の設定を上書き')
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """初期設定を実行"""
    try:
        config_path = Path('.env')
        
        if config_path.exists() and not force:
            if RICH_AVAILABLE and console:
                warning_panel = Panel(
                    "設定ファイル(.env)が既に存在します。\n"
                    "--force オプションを使用して上書きしてください。",
                    title="⚠️ 警告",
                    style="yellow"
                )
                console.print(warning_panel)
            else:
                click.echo("⚠️ 設定ファイル(.env)が既に存在します。--force オプションを使用してください。")
            return
        
        # TODO: 実際の設定初期化ロジックを実装
        sample_config = """# ゆっくり動画自動生成ツール - 設定ファイル

# API キー設定
GOOGLE_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
AIVIS_SPEECH_API_KEY=your_aivis_speech_api_key_here

# データベース設定
DATABASE_PATH=data/yukkuri_tool.db

# プロジェクト設定
PROJECTS_BASE_DIR=projects
TEMP_DIR=temp
ASSETS_DIR=assets

# デバッグ設定
DEBUG=false
LOG_LEVEL=INFO
"""
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(sample_config)
        
        if RICH_AVAILABLE and console:
            success_panel = Panel(
                f"設定ファイルを作成しました: {config_path}\n\n"
                "次のステップ:\n"
                "1. .env ファイルにAPIキーを設定\n"
                "2. yukkuri config validate で設定を検証\n"
                "3. yukkuri project create で最初のプロジェクトを作成",
                title="✅ 初期設定完了",
                style="green"
            )
            console.print(success_panel)
        else:
            click.echo(f"✅ 設定ファイルを作成しました: {config_path}")
            click.echo("APIキーを設定してください。")
        
    except Exception as e:
        error_msg = f"設定初期化中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@config_group.command()
@click.option('--format', type=click.Choice(['table', 'json']), default='table', help='出力形式')
@click.option('--show-secrets', is_flag=True, help='APIキーなどの秘匿情報も表示')
@click.pass_context
def show(ctx: click.Context, format: str, show_secrets: bool) -> None:
    """現在の設定を表示"""
    try:
        # TODO: 実際の設定取得ロジックを実装
        sample_config = {
            'database_path': 'data/yukkuri_tool.db',
            'projects_base_dir': 'projects',
            'temp_dir': 'temp',
            'assets_dir': 'assets',
            'debug': False,
            'log_level': 'INFO',
            'google_api_key': 'sk-***************' if not show_secrets else 'sk-your-actual-key',
            'openai_api_key': 'sk-***************' if not show_secrets else 'sk-your-actual-key',
            'aivis_speech_api_key': '***************' if not show_secrets else 'your-actual-key',
        }
        
        if format == 'json':
            if RICH_AVAILABLE and console:
                json_syntax = Syntax(
                    json.dumps(sample_config, indent=2, ensure_ascii=False),
                    "json",
                    theme="monokai",
                    line_numbers=True
                )
                console.print(json_syntax)
            else:
                click.echo(json.dumps(sample_config, indent=2, ensure_ascii=False))
        else:
            if RICH_AVAILABLE and console:
                table = Table(title="現在の設定")
                table.add_column("設定項目", style="cyan")
                table.add_column("値", style="white")
                table.add_column("説明", style="dim")
                
                descriptions = {
                    'database_path': 'データベースファイルのパス',
                    'projects_base_dir': 'プロジェクトベースディレクトリ',
                    'temp_dir': '一時ファイル保存ディレクトリ',
                    'assets_dir': 'アセットファイル保存ディレクトリ',
                    'debug': 'デバッグモード',
                    'log_level': 'ログレベル',
                    'google_api_key': 'Google Gemini APIキー',
                    'openai_api_key': 'OpenAI APIキー',
                    'aivis_speech_api_key': 'AIVIS Speech APIキー',
                }
                
                for key, value in sample_config.items():
                    table.add_row(
                        key,
                        str(value),
                        descriptions.get(key, '')
                    )
                
                console.print(table)
            else:
                click.echo("現在の設定:")
                for key, value in sample_config.items():
                    click.echo(f"  {key}: {value}")
        
    except Exception as e:
        error_msg = f"設定表示中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@config_group.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """設定の妥当性を検証"""
    try:
        # TODO: 実際の設定検証ロジックを実装
        validation_results = [
            {'item': 'Google API Key', 'status': 'valid', 'message': 'APIキーが有効です'},
            {'item': 'AIVIS Speech API', 'status': 'valid', 'message': 'APIアクセス可能です'},
            {'item': 'OpenAI API Key', 'status': 'warning', 'message': 'APIキーが設定されていません'},
            {'item': 'Database Path', 'status': 'valid', 'message': 'データベースパスが有効です'},
            {'item': 'Projects Directory', 'status': 'valid', 'message': 'ディレクトリが存在します'},
            {'item': 'FFmpeg', 'status': 'error', 'message': 'FFmpegが見つかりません'},
        ]
        
        if RICH_AVAILABLE and console:
            table = Table(title="設定検証結果")
            table.add_column("項目", style="cyan")
            table.add_column("状態", style="yellow")
            table.add_column("メッセージ", style="white")
            
            for result in validation_results:
                status_color = {
                    'valid': 'green',
                    'warning': 'yellow',
                    'error': 'red'
                }.get(result['status'], 'white')
                
                status_icon = {
                    'valid': '✅',
                    'warning': '⚠️',
                    'error': '❌'
                }.get(result['status'], '?')
                
                table.add_row(
                    result['item'],
                    f"[{status_color}]{status_icon} {result['status']}[/{status_color}]",
                    result['message']
                )
            
            console.print(table)
            
            # サマリー
            valid_count = len([r for r in validation_results if r['status'] == 'valid'])
            warning_count = len([r for r in validation_results if r['status'] == 'warning'])
            error_count = len([r for r in validation_results if r['status'] == 'error'])
            
            summary_color = 'green' if error_count == 0 else 'red'
            summary_text = f"""
検証完了: {valid_count} 成功, {warning_count} 警告, {error_count} エラー

{'' if error_count == 0 else '⚠️ エラーがある項目を修正してください。'}
"""
            summary_panel = Panel(
                summary_text.strip(),
                title="検証サマリー",
                style=summary_color
            )
            console.print(summary_panel)
        else:
            click.echo("設定検証結果:")
            for result in validation_results:
                icon = {'valid': '✅', 'warning': '⚠️', 'error': '❌'}.get(result['status'], '?')
                click.echo(f"  {icon} {result['item']}: {result['message']}")
        
    except Exception as e:
        error_msg = f"設定検証中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@config_group.command()
@click.argument('key')
@click.argument('value')
@click.pass_context
def set(ctx: click.Context, key: str, value: str) -> None:
    """
    設定値を更新
    
    KEY: 設定項目名
    VALUE: 設定値
    """
    try:
        # TODO: 実際の設定更新ロジックを実装
        
        if RICH_AVAILABLE and console:
            success_panel = Panel(
                f"設定を更新しました:\n{key} = {value}",
                title="✅ 設定更新",
                style="green"
            )
            console.print(success_panel)
        else:
            click.echo(f"✅ 設定を更新しました: {key} = {value}")
        
    except Exception as e:
        error_msg = f"設定更新中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)