"""テーマファイルからリサーチエージェントを実行する."""
import argparse
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from main import main as research_main


async def run_from_file(
    theme_file: str,
    max_iterations: int = 5,
    output_dir: str = "outputs",
    verbose: bool = True,
):
    """
    ファイルからテーマを読み込んでリサーチエージェントを実行する.
    
    Args:
        theme_file: テーマファイルのパス
        max_iterations: 最大反復回数
        output_dir: 出力ディレクトリ
        verbose: 詳細出力
    """
    # テーマファイルを読み込む
    theme_path = Path(theme_file)
    
    if not theme_path.exists():
        print(f"❌ エラー: テーマファイルが見つかりません: {theme_file}")
        return
    
    # ファイルからテーマを読み込む
    with open(theme_path, 'r', encoding='utf-8') as f:
        theme = f.read().strip()
    
    if not theme:
        print(f"❌ エラー: テーマファイルが空です: {theme_file}")
        return
    
    print("=" * 80)
    print("📄 ファイルからテーマを読み込みました")
    print("=" * 80)
    print(f"ファイル: {theme_file}")
    print(f"テーマ: {theme[:100]}{'...' if len(theme) > 100 else ''}")
    print()
    
    # 元のmain関数を呼び出すが、テーマを引数として渡す
    # argparseの代わりに直接パラメータを設定
    import sys
    original_argv = sys.argv
    try:
        sys.argv = [
            'run_from_file.py',
            theme,
            '--max-iterations', str(max_iterations),
            '--output-dir', output_dir,
        ]
        if verbose:
            sys.argv.append('--verbose')
        
        await research_main()
    finally:
        sys.argv = original_argv


def main():
    """コマンドラインインターフェース."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='テーマファイルからリサーチエージェントを実行'
    )
    parser.add_argument(
        'theme_file',
        type=str,
        help='テーマが記述されたファイルのパス（.txt, .md など）'
    )
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=5,
        help='エージェンティック検索の最大反復回数（デフォルト: 5）'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='outputs',
        help='出力ディレクトリのパス（デフォルト: outputs）'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=True,
        help='詳細な進捗を表示（デフォルト: 有効）'
    )
    
    args = parser.parse_args()
    
    asyncio.run(run_from_file(
        theme_file=args.theme_file,
        max_iterations=args.max_iterations,
        output_dir=args.output_dir,
        verbose=args.verbose,
    ))


if __name__ == "__main__":
    main()
