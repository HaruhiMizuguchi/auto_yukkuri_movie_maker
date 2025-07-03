"""
CLI ヘルパー機能

コマンドライン操作に必要な共通機能を提供
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.logging import RichHandler

console = Console()

def setup_logging(verbose: bool = False) -> None:
    """
    ログ設定を初期化
    
    Args:
        verbose: 詳細ログを有効にするかどうか
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    # Richハンドラーでログを美しく表示
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=verbose,
        rich_tracebacks=True
    )
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[rich_handler]
    )

def display_banner() -> None:
    """
    アプリケーションバナーを表示
    """
    banner_text = Text()
    banner_text.append("ゆっくり動画自動生成ツール", style="bold blue")
    banner_text.append("\n")
    banner_text.append("AI/LLM/TTS/画像生成モデルを連携した動画自動生成システム", style="white")
    banner_text.append("\n")
    banner_text.append("Version 2.0.0", style="dim white")
    
    banner_panel = Panel(
        banner_text,
        title="🎬 Yukkuri Video Generator",
        style="blue",
        padding=(1, 2)
    )
    
    console.print(banner_panel)

def display_error(message: str, suggestion: Optional[str] = None) -> None:
    """
    エラーメッセージを表示
    
    Args:
        message: エラーメッセージ
        suggestion: 解決方法の提案
    """
    error_text = Text()
    error_text.append("❌ エラー: ", style="bold red")
    error_text.append(message, style="red")
    
    if suggestion:
        error_text.append("\n\n💡 解決方法: ", style="bold yellow")
        error_text.append(suggestion, style="yellow")
    
    error_panel = Panel(
        error_text,
        title="Error",
        style="red",
        padding=(1, 2)
    )
    
    console.print(error_panel)

def display_success(message: str) -> None:
    """
    成功メッセージを表示
    
    Args:
        message: 成功メッセージ
    """
    success_text = Text()
    success_text.append("✅ ", style="bold green")
    success_text.append(message, style="green")
    
    success_panel = Panel(
        success_text,
        title="Success",
        style="green",
        padding=(1, 2)
    )
    
    console.print(success_panel)

def display_warning(message: str) -> None:
    """
    警告メッセージを表示
    
    Args:
        message: 警告メッセージ
    """
    warning_text = Text()
    warning_text.append("⚠️ ", style="bold yellow")
    warning_text.append(message, style="yellow")
    
    warning_panel = Panel(
        warning_text,
        title="Warning",
        style="yellow",
        padding=(1, 2)
    )
    
    console.print(warning_panel)

def confirm_action(message: str, default: bool = False) -> bool:
    """
    ユーザーに確認を求める
    
    Args:
        message: 確認メッセージ
        default: デフォルトの選択
        
    Returns:
        ユーザーの選択（True/False）
    """
    suffix = " [Y/n]" if default else " [y/N]"
    
    while True:
        try:
            response = console.input(f"[yellow]{message}{suffix}[/yellow] ").strip().lower()
            
            if not response:
                return default
            elif response in ['y', 'yes', 'はい']:
                return True
            elif response in ['n', 'no', 'いいえ']:
                return False
            else:
                console.print("[red]y/n で答えてください[/red]")
        except KeyboardInterrupt:
            console.print("\n[red]操作がキャンセルされました[/red]")
            return False

def get_project_root() -> Path:
    """
    プロジェクトルートパスを取得
    
    Returns:
        プロジェクトルートのPath
    """
    current_file = Path(__file__)
    # src/cli/utils/cli_helpers.py から3つ上がプロジェクトルート
    return current_file.parent.parent.parent.parent

def validate_project_id(project_id: str) -> bool:
    """
    プロジェクトIDの形式を検証
    
    Args:
        project_id: 検証するプロジェクトID
        
    Returns:
        有効なIDかどうか
    """
    # UUID形式の簡易検証
    parts = project_id.split('-')
    if len(parts) != 5:
        return False
    
    # 各部分の長さチェック（UUID v4形式）
    expected_lengths = [8, 4, 4, 4, 12]
    for part, expected_length in zip(parts, expected_lengths):
        if len(part) != expected_length:
            return False
        # 16進数文字のみかチェック
        if not all(c in '0123456789abcdefABCDEF' for c in part):
            return False
    
    return True