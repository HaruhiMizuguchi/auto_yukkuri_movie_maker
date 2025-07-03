"""
ステータス確認コマンド

プロジェクトの状況、進捗の確認
"""

import click
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None

if RICH_AVAILABLE:
    console = Console()

@click.group()
def status_group():
    """ステータス確認コマンド"""
    pass

@status_group.command()
@click.argument('project_id')
@click.option('--detailed', '-d', is_flag=True, help='詳細な進捗を表示')
@click.pass_context
def show(ctx: click.Context, project_id: str, detailed: bool) -> None:
    """
    プロジェクトの状況を表示
    
    PROJECT_ID: 確認するプロジェクトのID
    """
    try:
        # TODO: 実際のステータス取得ロジックを実装
        status_info = {
            'id': project_id,
            'name': 'サンプルプロジェクト',
            'status': 'running',
            'current_step': 'TTS処理',
            'progress_percentage': 60,
            'steps_completed': 6,
            'total_steps': 10,
            'start_time': '2025-01-25 09:00:00',
            'estimated_completion': '2025-01-25 11:30:00',
            'last_error': None,
            'steps': [
                {'name': 'テーマ選定', 'status': 'completed', 'duration': '2分'},
                {'name': 'スクリプト生成', 'status': 'completed', 'duration': '5分'},
                {'name': 'タイトル生成', 'status': 'completed', 'duration': '1分'},
                {'name': 'TTS処理', 'status': 'running', 'duration': '進行中'},
                {'name': '立ち絵アニメーション', 'status': 'pending', 'duration': '-'},
                {'name': '背景生成', 'status': 'pending', 'duration': '-'},
                {'name': '字幕生成', 'status': 'pending', 'duration': '-'},
                {'name': '動画合成', 'status': 'pending', 'duration': '-'},
                {'name': '音響効果', 'status': 'pending', 'duration': '-'},
                {'name': '最終エンコード', 'status': 'pending', 'duration': '-'},
            ]
        }
        
        if RICH_AVAILABLE and console:
            # 基本情報
            basic_info = f"""
プロジェクト名: {status_info['name']}
現在のステップ: {status_info['current_step']}
進捗: {status_info['progress_percentage']}% ({status_info['steps_completed']}/{status_info['total_steps']})
開始時刻: {status_info['start_time']}
完了予定: {status_info['estimated_completion']}
"""
            info_panel = Panel(
                basic_info.strip(),
                title=f"📊 プロジェクトステータス: {project_id[:13]}...",
                style="blue"
            )
            console.print(info_panel)
            
            # 進捗バー
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                progress.add_task(
                    "全体進捗", 
                    completed=status_info['progress_percentage'], 
                    total=100
                )
            
            # 詳細ステップ情報（詳細モードの場合）
            if detailed:
                step_table = Table(title="ステップ詳細")
                step_table.add_column("ステップ", style="cyan")
                step_table.add_column("状態", style="yellow")
                step_table.add_column("実行時間", style="green")
                
                for step in status_info['steps']:
                    status_color = {
                        'completed': 'green',
                        'running': 'yellow',
                        'pending': 'dim',
                        'failed': 'red'
                    }.get(step['status'], 'white')
                    
                    step_table.add_row(
                        step['name'],
                        f"[{status_color}]{step['status']}[/{status_color}]",
                        step['duration']
                    )
                
                console.print(step_table)
        else:
            click.echo(f"プロジェクトステータス: {project_id}")
            click.echo(f"  名前: {status_info['name']}")
            click.echo(f"  進捗: {status_info['progress_percentage']}%")
            click.echo(f"  現在のステップ: {status_info['current_step']}")
            
            if detailed:
                click.echo("\nステップ詳細:")
                for step in status_info['steps']:
                    click.echo(f"  {step['name']}: {step['status']} ({step['duration']})")
        
    except Exception as e:
        error_msg = f"ステータス取得中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@status_group.command()
@click.option('--status', type=click.Choice(['all', 'running', 'completed', 'failed', 'pending']), 
              default='all', help='フィルタリングする状態')
@click.pass_context
def list(ctx: click.Context, status: str) -> None:
    """全プロジェクトの状況一覧を表示"""
    try:
        # TODO: 実際のプロジェクト一覧取得ロジックを実装
        projects = [
            {
                'id': 'abc123-def4-5678-9012-345678901234',
                'name': 'サンプルプロジェクト1',
                'status': 'running',
                'progress': 60,
                'current_step': 'TTS処理',
                'start_time': '09:00'
            },
            {
                'id': 'xyz789-abc1-2345-6789-012345678901',
                'name': 'サンプルプロジェクト2',
                'status': 'completed',
                'progress': 100,
                'current_step': '完了',
                'start_time': '08:30'
            },
            {
                'id': 'def456-ghi7-8901-2345-678901234567',
                'name': 'サンプルプロジェクト3',
                'status': 'failed',
                'progress': 30,
                'current_step': 'スクリプト生成',
                'start_time': '10:15'
            }
        ]
        
        filtered_projects = [p for p in projects if status == 'all' or p['status'] == status]
        
        if RICH_AVAILABLE and console:
            table = Table(title=f"プロジェクト一覧 (フィルター: {status})")
            table.add_column("ID", style="cyan")
            table.add_column("名前", style="blue")
            table.add_column("状態", style="yellow")
            table.add_column("進捗", style="green")
            table.add_column("現在のステップ", style="white")
            table.add_column("開始時刻", style="dim")
            
            for project in filtered_projects:
                status_color = {
                    'running': 'yellow',
                    'completed': 'green',
                    'failed': 'red',
                    'pending': 'dim'
                }.get(project['status'], 'white')
                
                table.add_row(
                    project['id'][:13] + "...",
                    project['name'],
                    f"[{status_color}]{project['status']}[/{status_color}]",
                    f"{project['progress']}%",
                    project['current_step'],
                    project['start_time']
                )
            
            console.print(table)
        else:
            click.echo(f"プロジェクト一覧 (フィルター: {status}):")
            for project in filtered_projects:
                click.echo(f"  {project['id'][:13]}... - {project['name']} ({project['status']}, {project['progress']}%)")
        
    except Exception as e:
        error_msg = f"プロジェクト一覧取得中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)

@status_group.command()
@click.pass_context  
def system(ctx: click.Context) -> None:
    """システム全体の状況を表示"""
    try:
        # TODO: 実際のシステム状況取得ロジックを実装
        system_info = {
            'total_projects': 15,
            'running_projects': 2,
            'completed_projects': 10,
            'failed_projects': 1,
            'pending_projects': 2,
            'disk_usage': '2.3GB / 50GB',
            'api_usage_today': {
                'gemini_requests': 45,
                'aivis_requests': 12,
                'image_generations': 8
            },
            'estimated_cost_today': '¥850'
        }
        
        if RICH_AVAILABLE and console:
            system_text = f"""
総プロジェクト数: {system_info['total_projects']}
実行中: {system_info['running_projects']}
完了: {system_info['completed_projects']}
失敗: {system_info['failed_projects']}
待機中: {system_info['pending_projects']}

ディスク使用量: {system_info['disk_usage']}

本日のAPI使用量:
  • Gemini: {system_info['api_usage_today']['gemini_requests']} リクエスト
  • AIVIS Speech: {system_info['api_usage_today']['aivis_requests']} リクエスト
  • 画像生成: {system_info['api_usage_today']['image_generations']} 枚

本日の推定費用: {system_info['estimated_cost_today']}
"""
            system_panel = Panel(
                system_text.strip(),
                title="🖥️ システム状況",
                style="cyan"
            )
            console.print(system_panel)
        else:
            click.echo("システム状況:")
            click.echo(f"  総プロジェクト数: {system_info['total_projects']}")
            click.echo(f"  実行中: {system_info['running_projects']}")
            click.echo(f"  完了: {system_info['completed_projects']}")
            click.echo(f"  本日の推定費用: {system_info['estimated_cost_today']}")
        
    except Exception as e:
        error_msg = f"システム状況取得中にエラーが発生しました: {str(e)}"
        if RICH_AVAILABLE and console:
            error_panel = Panel(error_msg, title="❌ エラー", style="red")
            console.print(error_panel)
        else:
            click.echo(f"❌ {error_msg}", err=True)
        raise click.ClickException(error_msg)