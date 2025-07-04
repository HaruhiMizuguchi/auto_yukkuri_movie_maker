"""
統合テストパッケージ

フェーズ1で実装した9つのコアモジュール間の統合テストを実装します。
単体テストでは検証できないモジュール間の連携動作を確認します。

統合テスト種類:
1. データベース ↔ ファイルシステム統合
2. プロジェクト管理フロー統合
3. 設定 ↔ ログ ↔ データベース統合
4. エラーハンドリング統合
5. コンカレンシー統合
""" 