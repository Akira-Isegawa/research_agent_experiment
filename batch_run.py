"""複数のテーマファイルをバッチ実行する."""
import argparse
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from run_from_file import run_from_file


async def batch_run(
    input_dir: str = "inputs",
    max_iterations: int = 5,
    output_dir: str = "outputs",
    output_subdir: bool = False,
    verbose: bool = True,
):
    """
    入力ディレクトリ内の全テーマファイルを順次実行する.
    
    Args:
        input_dir: テーマファイルが配置されたディレクトリ
        max_iterations: 最大反復回数
        output_dir: 出力ディレクトリ
        output_subdir: テーマごとにサブディレクトリを作成するか
        verbose: 詳細出力
    """
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"❌ エラー: 入力ディレクトリが見つかりません: {input_dir}")
        return
    
    # テーマファイルを検索（.txt, .md）
    theme_files = list(input_path.glob("*.txt")) + list(input_path.glob("*.md"))
    
    if not theme_files:
        print(f"❌ エラー: {input_dir} 内にテーマファイル (.txt, .md) が見つかりません")
        return
    
    print("=" * 80)
    print("📦 バッチ実行を開始します")
    print("=" * 80)
    print(f"入力ディレクトリ: {input_dir}")
    print(f"検出されたテーマファイル: {len(theme_files)}個")
    print()
    
    for theme_file in theme_files:
        print("\n" + "=" * 80)
        print(f"📄 処理中: {theme_file.name}")
        print("=" * 80)
        
        # 出力ディレクトリを決定
        if output_subdir:
            # ファイル名（拡張子なし）をサブディレクトリ名として使用
            subdir_name = theme_file.stem
            current_output_dir = f"{output_dir}/{subdir_name}"
        else:
            current_output_dir = output_dir
        
        try:
            await run_from_file(
                theme_file=str(theme_file),
                max_iterations=max_iterations,
                output_dir=current_output_dir,
                verbose=verbose,
            )
            print(f"✅ 完了: {theme_file.name}")
        except Exception as e:
            print(f"❌ エラー: {theme_file.name} の処理中にエラーが発生しました")
            print(f"   {str(e)}")
            continue
    
    print("\n" + "=" * 80)
    print("🎉 バッチ実行が完了しました")
    print("=" * 80)
    print(f"処理されたファイル数: {len(theme_files)}")


def main():
    """コマンドラインインターフェース."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='複数のテーマファイルをバッチ実行'
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        default='inputs',
        help='テーマファイルが配置されたディレクトリ（デフォルト: inputs）'
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
        '--output-subdir',
        action='store_true',
        help='テーマごとにサブディレクトリを作成（デフォルト: 無効）'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=True,
        help='詳細な進捗を表示（デフォルト: 有効）'
    )
    
    args = parser.parse_args()
    
    asyncio.run(batch_run(
        input_dir=args.input_dir,
        max_iterations=args.max_iterations,
        output_dir=args.output_dir,
        output_subdir=args.output_subdir,
        verbose=args.verbose,
    ))


if __name__ == "__main__":
    main()
