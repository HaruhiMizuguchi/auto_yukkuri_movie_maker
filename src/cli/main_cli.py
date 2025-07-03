"""
ゆっくり動画自動生成ツール - メインCLIインターフェース

コマンドライン操作のメインエントリーポイント
"""

import click
import sys
import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# プロジェクトルートを追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.cli.commands.project_commands import project_group
from src.cli.commands.generate_commands import generate_group
from src.cli.commands.status_commands import status_group
from src.cli.commands.config_commands import config_group
from src.cli.utils.cli_helpers import setup_logging, display_banner

console = Console()

@click.group()
@click.version_option(version="2.0.0", prog_name="yukkuri")
@click.option('--verbose', '-v', is_flag=True, help='詳細ログを表示')
@click.option('--config', '-c', type=click.Path(), help='設定ファイルパス')
@click.pass_context
def main(ctx: click.Context, verbose: bool, config: Optional[str]) -> None:
    """
    ゆっくり動画自動生成ツール
    
    AI/LLM/TTS/画像生成モデルを連携させ、ゆっくり動画を企画からYouTube投稿まで自動生成します。
    """
    # コンテキストオブジェクトの初期化
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config'] = config
    
    # ログ設定
    setup_logging(verbose)
    
    # バナー表示（メインコマンドの場合のみ）
    if ctx.invoked_subcommand is None:
        display_banner()
        console.print("\n使用方法: yukkuri [COMMAND] --help で詳細なヘルプを表示")

# サブコマンドグループの追加
main.add_command(project_group, name="project")
main.add_command(generate_group, name="generate")
main.add_command(status_group, name="status")
main.add_command(config_group, name="config")

@main.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """バージョン情報を表示"""
    console.print(Panel(
        Text("ゆっくり動画自動生成ツール v2.0.0", style="bold blue"),
        title="Version Info",
        style="blue"
    ))

@main.command()
@click.pass_context
def help(ctx: click.Context) -> None:
    """詳細なヘルプ情報を表示"""
    display_banner()
    
    help_text = """
[bold blue]主要コマンド:[/bold blue]

[yellow]プロジェクト管理:[/yellow]
  • yukkuri project create [NAME]     - 新しいプロジェクトを作成
  • yukkuri project list              - プロジェクト一覧を表示
  • yukkuri project delete [ID]       - プロジェクトを削除

[yellow]動画生成:[/yellow]
  • yukkuri generate [PROJECT_ID]     - 動画生成を実行
  • yukkuri generate resume [ID]      - 中断したプロジェクトを再開

[yellow]状況確認:[/yellow]
  • yukkuri status [PROJECT_ID]       - プロジェクト状況を確認
  • yukkuri status list               - 全プロジェクト状況を表示

[yellow]設定管理:[/yellow]
  • yukkuri config init               - 初期設定を実行
  • yukkuri config show               - 現在の設定を表示
  • yukkuri config validate           - 設定の妥当性を検証

[bold blue]例:[/bold blue]
  yukkuri project create "tech_video"
  yukkuri generate abc123-def4-5678
  yukkuri status abc123-def4-5678

[bold blue]詳細ヘルプ:[/bold blue]
  各コマンドの詳細は 'yukkuri [COMMAND] --help' で確認できます。
"""
    
    console.print(Panel(help_text, title="ゆっくり動画自動生成ツール - ヘルプ", style="blue"))

if __name__ == "__main__":
    main()