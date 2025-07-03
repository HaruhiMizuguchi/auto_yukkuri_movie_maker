"""
プロジェクト管理コマンド

プロジェクトの作成、一覧表示、削除などの操作
"""

import click
import logging
from typing import Optional
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None

# リッチコンソールの初期化
if RICH_AVAILABLE:
    console = Console()

@click.group()
def project_group():
    """プロジェクト管理コマンド"""
    pass

@project_group.command()
@click.argument('name')
@click.option('--description', '-d', help='プロジェクトの説明')
@click.option('--theme', '-t', help='初期テーマ（オプション）')
@click.option('--target-length', type=int, default=5, help='目標動画長（分）')
@click.pass_context
def create(ctx: click.Context, name: str, description: Optional[str], 
          theme: Optional[str], target_length: int) -> None:
    """
    新しいプロジェクトを作成
    
    NAME: プロジェクト名
    """
    try:
        # TODO: 実際のプロジェクト作成ロジックを実装
        project_id = f"sample-{name[:8]}-project"
        
        if RICH_AVAILABLE and console:
            success_panel = Panel(
                f"プロジェクト '{name}' を作成しました\n"
                f"プロジェクトID: {project_id}\n"
                f"目標動画長: {target_length}分",
                title="✅ プロジェクト作成完了",
                style="green"
            )
            console.print(success_panel)
        else:
            click.echo(f"✅ プロジェクト '{name}' を作成しました")
            click.echo(f"プロジェクトID: {project_id}")
        
    except Exception as e:
        error_msg = f"プロジェクト作成中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(
                error_msg,
                title="❌ エラー",
                style="red"
            )
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@project_group.command()
@click.option('--status', type=click.Choice(['all', 'active', 'completed', 'failed']), 
              default='all', help='フィルタリングする状態')
@click.pass_context
def list(ctx: click.Context, status: str) -> None:
    """プロジェクト一覧を表示"""
    try:
        # TODO: 実際のプロジェクト一覧取得ロジックを実装
        sample_projects = [
            {
                'id': 'abc123-def4-5678-9012-345678901234',
                'name': 'サンプルプロジェクト1',
                'status': 'active',
                'progress': '60%',
                'created': '2025-01-25'
            },
            {
                'id': 'xyz789-abc1-2345-6789-012345678901',
                'name': 'サンプルプロジェクト2', 
                'status': 'completed',
                'progress': '100%',
                'created': '2025-01-24'
            }
        ]
        
        if RICH_AVAILABLE and console:
            table = Table(title="プロジェクト一覧")
            table.add_column("ID", style="cyan")
            table.add_column("名前", style="blue")
            table.add_column("状態", style="yellow")
            table.add_column("進捗", style="green")
            table.add_column("作成日", style="dim")
            
            for project in sample_projects:
                if status == 'all' or project['status'] == status:
                    table.add_row(
                        project['id'][:13] + "...",
                        project['name'],
                        project['status'],
                        project['progress'],
                        project['created']
                    )
            
            console.print(table)
        else:
            click.echo("プロジェクト一覧:")
            for project in sample_projects:
                if status == 'all' or project['status'] == status:
                    click.echo(f"  {project['id']} - {project['name']} ({project['status']}, {project['progress']})")
        
    except Exception as e:
        error_msg = f"プロジェクト一覧取得中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@project_group.command()
@click.argument('project_id')
@click.option('--force', is_flag=True, help='確認なしで削除')
@click.pass_context
def delete(ctx: click.Context, project_id: str, force: bool) -> None:
    """
    プロジェクトを削除
    
    PROJECT_ID: 削除するプロジェクトのID
    """
    try:
        if not force:
            if RICH_AVAILABLE and console:
                confirm = console.input(f"[yellow]プロジェクト {project_id} を削除しますか？ [y/N][/yellow] ")
            else:
                confirm = click.prompt(f"プロジェクト {project_id} を削除しますか？ [y/N]", default='n')
            
            if confirm.lower() not in ['y', 'yes']:
                click.echo("削除をキャンセルしました")
                return
        
        # TODO: 実際のプロジェクト削除ロジックを実装
        
        if RICH_AVAILABLE and console:
            success_panel = Panel(
                f"プロジェクト {project_id} を削除しました",
                title="✅ 削除完了",
                style="green"
            )
            console.print(success_panel)
        else:
            click.echo(f"✅ プロジェクト {project_id} を削除しました")
        
    except Exception as e:
        error_msg = f"プロジェクト削除中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@project_group.command()
@click.argument('project_id')
@click.pass_context
def info(ctx: click.Context, project_id: str) -> None:
    """
    プロジェクトの詳細情報を表示
    
    PROJECT_ID: 情報を表示するプロジェクトのID
    """
    try:
        # TODO: 実際のプロジェクト情報取得ロジックを実装
        sample_info = {
            'id': project_id,
            'name': 'サンプルプロジェクト',
            'description': 'テスト用のプロジェクトです',
            'status': 'active',
            'progress': '60%',
            'created': '2025-01-25',
            'last_updated': '2025-01-25 10:30:00',
            'theme': 'AI技術の最新動向',
            'target_length': 5,
            'current_step': 'TTS処理'
        }
        
        if RICH_AVAILABLE and console:
            info_text = f"""
プロジェクト名: {sample_info['name']}
説明: {sample_info['description']}
テーマ: {sample_info['theme']}
目標長: {sample_info['target_length']}分
状態: {sample_info['status']}
進捗: {sample_info['progress']}
現在のステップ: {sample_info['current_step']}
作成日: {sample_info['created']}
最終更新: {sample_info['last_updated']}
"""
            info_panel = Panel(
                info_text.strip(),
                title=f"📋 プロジェクト情報: {project_id[:13]}...",
                style="blue"
            )
            console.print(info_panel)
        else:
            click.echo(f"プロジェクト情報: {project_id}")
            for key, value in sample_info.items():
                if key != 'id':
                    click.echo(f"  {key}: {value}")
        
    except Exception as e:
        error_msg = f"プロジェクト情報取得中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)