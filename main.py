"""リサーチエージェントのメインエントリーポイント."""
import asyncio
import argparse
import os
from datetime import datetime
import json
from pathlib import Path
from dotenv import load_dotenv

from workflows import (
    run_simple_research,
    run_agentic_research,
    run_comparison_analysis,
)
from models.schemas import ComparisonReportOutput


def format_markdown_output(
    theme: str,
    simple_result,
    agentic_plan,
    agentic_result,
    evaluations,
    comparison_result: ComparisonReportOutput,
    fact_check_history: list = None,
    raw_results: list = None,
) -> tuple:
    """
    各フェーズの結果をMarkdown形式でフォーマットする.
    
    Args:
        raw_results: 各反復のresearcher生結果（URL未変更）。検証用に保存。
    
    Returns:
        Tuple of (simple_md, agentic_md, comparison_md)
    """
    
    # ワンショット検索結果
    simple_md = f"""# ワンショット検索結果

テーマ: {theme}

実行日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

## 調査概要

本検索は、与えられたテーマについてワンショット（1回の検索セッション）で
包括的な情報収集を実施しました。

## 主要な発見事項

発見事項数: {len(simple_result.findings)}

"""
    for i, finding in enumerate(simple_result.findings, 1):
        simple_md += f"{i}. {finding.content}\n   出所: {finding.source}\n\n"
    
    simple_md += f"""

## 根拠情報

根拠情報数: {len(simple_result.evidence)}

"""
    for i, evidence in enumerate(simple_result.evidence, 1):
        url = evidence.url
        title = evidence.title
        summary = evidence.summary
        simple_md += f"{i}. **{title}**\n   - URL: {url}\n   - 概要: {summary}\n\n"
    
    simple_md += f"""## カバーされた領域

- {chr(10).join(f'- {area}' for area in simple_result.coverage_areas)}

## 総括

{simple_result.summary}
"""
    
    # エージェンティック検索結果（調査結果中心のレポート）
    agentic_md = f"""# 調査レポート

テーマ: {theme}

実行日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

---

## エグゼクティブサマリー

{agentic_result.summary}

---

## 主要な発見事項

"""
    # 発見事項を根拠情報と紐付けて詳細に表示
    # 根拠情報をURL→Evidence のマップにする
    evidence_map = {}
    for ev in agentic_result.evidence:
        evidence_map[ev.title] = ev
    
    for i, finding in enumerate(agentic_result.findings, 1):
        agentic_md += f"### {i}. {finding.source}\n\n"
        agentic_md += f"{finding.content}\n\n"
        # 関連する根拠情報を探してURLを付与
        matched_evidence = None
        for ev in agentic_result.evidence:
            if ev.title in finding.source or finding.source in ev.title:
                matched_evidence = ev
                break
        if matched_evidence:
            agentic_md += f"📎 **出典**: [{matched_evidence.title}]({matched_evidence.url})\n"
            agentic_md += f"   {matched_evidence.summary}\n\n"
        else:
            agentic_md += f"📎 **出典**: {finding.source}\n\n"
    
    agentic_md += f"""---

## 領域間の相互関連性

{chr(10).join(f'- {connection}' for connection in agentic_result.interconnections)}

---

## 参考文献・根拠情報一覧

"""
    for i, evidence in enumerate(agentic_result.evidence, 1):
        agentic_md += f"{i}. [{evidence.title}]({evidence.url}) - {evidence.summary}\n"
    
    # ファクトチェック累計の算出
    fc_total_verified = 0
    fc_total_removed = 0
    if fact_check_history:
        fc_total_verified = sum(fc['verified'] for fc in fact_check_history)
        fc_total_removed = sum(fc['removed'] for fc in fact_check_history)
    
    agentic_md += f"""\n---

## 調査プロセスの記録

| 項目 | 値 |
|------|----|
| 総反復回数 | {len(evaluations)} |
| 最終総合スコア | {evaluations[-1].overall_quality_score}/60 |
| 発見事項数 | {len(agentic_result.findings)} |
| 根拠情報数 | {len(agentic_result.evidence)} |
| ファクトチェック検証済み（累計） | {fc_total_verified} |
| ファクトチェック除外（累計） | {fc_total_removed} |

"""
    # ファクトチェック履歴の詳細
    if fact_check_history:
        agentic_md += """### ファクトチェック履歴

| 反復 | 検証済み | 除外 | 信頼性スコア |
|------|---------|------|-------------|
"""
        for fc in fact_check_history:
            agentic_md += f"| {fc['iteration']} | {fc['verified']} | {fc['removed']} | {fc['reliability']:.1%} |\n"
        
        agentic_md += "\n"
        
        # 除外された情報の詳細
        has_removals = any(fc.get('removed_reasons') for fc in fact_check_history)
        if has_removals:
            agentic_md += "<details>\n<summary>除外された情報の詳細</summary>\n\n"
            for fc in fact_check_history:
                if fc.get('removed_reasons'):
                    agentic_md += f"**反復{fc['iteration']}:**\n"
                    for reason in fc['removed_reasons']:
                        agentic_md += f"- ❌ {reason}\n"
                    agentic_md += "\n"
            agentic_md += "</details>\n\n"
    # 各反復の評価を折りたたみ形式で表示
    for i, evaluation in enumerate(evaluations, 1):
        agentic_md += f"""<details>\n<summary>反復{i}の評価詳細（総合: {evaluation.overall_quality_score}/60）</summary>\n\n"""
        agentic_md += f"""| 評価軸 | スコア |\n|--------|--------|\n"""
        agentic_md += f"""| 目的達成度 | {evaluation.objective_achievement_score}/10 |\n"""
        agentic_md += f"""| 網羅性 | {evaluation.coverage_score}/10 |\n"""
        agentic_md += f"""| 深さ・洞察力 | {evaluation.depth_insight_score}/10 |\n"""
        agentic_md += f"""| 実用性 | {evaluation.actionability_score}/10 |\n"""
        agentic_md += f"""| 信頼性 | {evaluation.credibility_score}/10 |\n"""
        agentic_md += f"""| 定量性 | {evaluation.quantitative_score}/10 |\n\n"""
        if evaluation.coverage_gaps:
            agentic_md += f"**観点のヌケモレ:**\n"
            for gap in evaluation.coverage_gaps:
                agentic_md += f"- {gap}\n"
            agentic_md += "\n"
        agentic_md += f"**専門家の観察:** {evaluation.expert_observations}\n\n"
        if evaluation.should_refine and evaluation.refinement_strategy:
            agentic_md += f"**改善戦略:** {evaluation.refinement_strategy}\n\n"
        agentic_md += "</details>\n\n"
    
    agentic_md += f"""\n<details>\n<summary>調査計画の詳細</summary>\n\n### 目的\n\n{agentic_plan.objective}\n\n### 調査領域\n\n{chr(10).join(f'- {area}' for area in agentic_plan.research_areas)}\n\n### 調査戦略\n\n{agentic_plan.research_strategy}\n\n</details>\n"""
    
    # 生データ付録（raw_results がある場合のみ）
    if raw_results:
        agentic_md += "\n---\n\n## 付録: Researcher生出力データ（URL未変更）\n\n"
        agentic_md += "> 以下はresearcherの生出力を変更せずに保存したものです。ファクトチェック前のデータです。\n\n"
        for raw in raw_results:
            iter_num = raw.get('iteration', '?')
            agentic_md += f"### 反復{iter_num}の生データ\n\n"
            raw_findings = raw.get('findings', [])
            raw_evidence = raw.get('evidence', [])
            agentic_md += f"**発見事項（{len(raw_findings)}件）:**\n\n"
            for j, rf in enumerate(raw_findings, 1):
                content = rf.get('content', '') if isinstance(rf, dict) else getattr(rf, 'content', str(rf))
                source = rf.get('source', '') if isinstance(rf, dict) else getattr(rf, 'source', '')
                agentic_md += f"{j}. {content}\n   出所: {source}\n\n"
            agentic_md += f"**根拠情報（{len(raw_evidence)}件）:**\n\n"
            for j, re_ in enumerate(raw_evidence, 1):
                title = re_.get('title', '') if isinstance(re_, dict) else getattr(re_, 'title', '')
                url = re_.get('url', '') if isinstance(re_, dict) else getattr(re_, 'url', '')
                summary = re_.get('summary', '') if isinstance(re_, dict) else getattr(re_, 'summary', '')
                agentic_md += f"{j}. [{title}]({url}) - {summary}\n"
            agentic_md += "\n"
    
    # 比較分析レポート
    comparison_md = f"""# 簡易検索 vs エージェンティック検索 比較分析レポート

テーマ: {theme}

実行日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

## エグゼクティブサマリー

本レポートは、ワンショット検索とエージェンティック検索の2つのアプローチを
多面的に比較分析したものです。

## スコアリング比較（6軸評価）

### 定量比較表

| 観点 | ワンショット検索 | エージェント検索 | 改善率 |
|------|-----------------|-----------------|--------|
| 目的達成度 | {comparison_result.simple_search_objective_score}/10 | {comparison_result.agentic_search_objective_score}/10 | {comparison_result.objective_improvement_rate:+.1f}% |
| 網羅性 | {comparison_result.simple_search_coverage_score}/10 | {comparison_result.agentic_search_coverage_score}/10 | {comparison_result.coverage_improvement_rate:+.1f}% |
| 深さ・洞察力 | {comparison_result.simple_search_depth_insight_score}/10 | {comparison_result.agentic_search_depth_insight_score}/10 | {comparison_result.depth_insight_improvement_rate:+.1f}% |
| 実用性 | {comparison_result.simple_search_actionability_score}/10 | {comparison_result.agentic_search_actionability_score}/10 | {comparison_result.actionability_improvement_rate:+.1f}% |
| 信頼性 | {comparison_result.simple_search_credibility_score}/10 | {comparison_result.agentic_search_credibility_score}/10 | {comparison_result.credibility_improvement_rate:+.1f}% |
| 定量性 | {comparison_result.simple_search_quantitative_score}/10 | {comparison_result.agentic_search_quantitative_score}/10 | {comparison_result.quantitative_improvement_rate:+.1f}% |
| **総合スコア** | **{comparison_result.simple_search_total_score}/60** | **{comparison_result.agentic_search_total_score}/60** | **{(comparison_result.agentic_search_total_score - comparison_result.simple_search_total_score) / comparison_result.simple_search_total_score * 100:+.1f}%** |

### スコア評価

**ワンショット検索:**
- 総合スコア: {comparison_result.simple_search_total_score}/60
- 特徴: {', '.join(comparison_result.simple_search_strengths)}

**エージェンティック検索:**
- 総合スコア: {comparison_result.agentic_search_total_score}/60
- 特徴: {', '.join(comparison_result.agentic_search_strengths)}

## 定性的分析

### 主な相違点

{chr(10).join(f'- {diff}' for diff in comparison_result.key_differences)}

### ワンショット検索の強み

{chr(10).join(f'- {strength}' for strength in comparison_result.simple_search_strengths)}

### ワンショット検索の弱み

{chr(10).join(f'- {weakness}' for weakness in comparison_result.simple_search_weaknesses)}

### エージェンティック検索の強み

{chr(10).join(f'- {strength}' for strength in comparison_result.agentic_search_strengths)}

### エージェンティック検索の弱み

{chr(10).join(f'- {weakness}' for weakness in comparison_result.agentic_search_weaknesses)}

## 費用対効果分析

{comparison_result.cost_effectiveness_analysis}

## 推奨事項

### 活用シーン

{comparison_result.recommendation}

### 適用ガイドライン

#### ワンショット検索が適切なケース
- 時間的制約がある場合
- 高レベルの概要把握が目的
- 初期段階のリサーチ
- 予算が限定的

#### エージェンティック検索が適切なケース
- 深い理解が必要
- 意思決定に重要な調査
- 包括的な分析が必須
- ヌケモレを最小化したい

#### 併用アプローチ（推奨）
1. 初期段階: ワンショット検索で概要把握
2. 精密段階: エージェンティック検索で深掘り
3. 統合: 両結果を組み合わせた包括的な理解

---

*本レポートは自動生成されました。*
"""
    
    return simple_md, agentic_md, comparison_md


async def main():
    """メイン実行関数."""
    parser = argparse.ArgumentParser(
        description="ChatGPT DeepResearch型エージェントシステム"
    )
    parser.add_argument(
        "theme",
        type=str,
        help="調査テーマ"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="エージェンティック検索の最大反復回数（デフォルト: 5）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="出力ディレクトリ（デフォルト: outputs）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="詳細な進捗出力（デフォルト: 有効）"
    )
    
    # .env ファイルから環境変数を読み込む
    load_dotenv()
    
    args = parser.parse_args()
    
    # 出力ディレクトリを作成
    output_dir = Path(__file__).parent / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ワークフロー実行
    try:
        # フェーズA: ワンショット検索
        simple_result = await run_simple_research(
            args.theme,
            verbose=args.verbose
        )
        
        # フェーズB: エージェンティック検索
        agentic_plan, agentic_result, evaluations, fact_check_history, raw_results = await run_agentic_research(
            args.theme,
            max_iterations=args.max_iterations,
            verbose=args.verbose
        )
        
        # フェーズC: 比較分析
        comparison_result = await run_comparison_analysis(
            args.theme,
            simple_result,
            agentic_result,
            verbose=args.verbose
        )
        
        # 結果をMarkdown形式でフォーマット
        simple_md, agentic_md, comparison_md = format_markdown_output(
            args.theme,
            simple_result,
            agentic_plan,
            agentic_result,
            evaluations,
            comparison_result,
            fact_check_history=fact_check_history,
            raw_results=raw_results,
        )
        
        # ファイルに保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        simple_file = output_dir / f"simple_search_{timestamp}.md"
        agentic_file = output_dir / f"agentic_search_{timestamp}.md"
        comparison_file = output_dir / f"comparison_{timestamp}.md"
        raw_file = output_dir / f"raw_research_{timestamp}.json"
        
        simple_file.write_text(simple_md, encoding="utf-8")
        agentic_file.write_text(agentic_md, encoding="utf-8")
        comparison_file.write_text(comparison_md, encoding="utf-8")
        
        # researcher生データをJSONで保存（URL未変更のまま）
        if raw_results:
            # Pydanticモデルをdict化して保存
            serializable_raw = []
            for raw in raw_results:
                entry = {'iteration': raw.get('iteration', 0), 'summary': raw.get('summary', '')}
                entry['findings'] = [
                    f.model_dump() if hasattr(f, 'model_dump') else f
                    for f in raw.get('findings', [])
                ]
                entry['evidence'] = [
                    e.model_dump() if hasattr(e, 'model_dump') else e
                    for e in raw.get('evidence', [])
                ]
                serializable_raw.append(entry)
            raw_file.write_text(
                json.dumps(serializable_raw, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        
        if args.verbose:
            print("\n" + "=" * 80)
            print("📁 結果を保存しました")
            print("=" * 80)
            print(f"簡易検索結果: {simple_file}")
            print(f"詳細検索結果: {agentic_file}")
            print(f"比較レポート: {comparison_file}")
            if raw_results:
                print(f"🔍 Researcher生データ: {raw_file}")
            print("=" * 80)
    
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
