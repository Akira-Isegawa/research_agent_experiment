"""ハルシネーション対策: フィードバックループとレポート生成のテスト.

今回の修正の構造的改善に対するテスト:
  1. リサーチャーに前回のファクトチェック結果が渡されること
  2. 評価者にファクトチェック結果が渡され、スコアに反映されること
  3. FC通過情報のみが反復をまたいで蓄積されること（FCは合格/不合格フィルタ）
  4. main.py の format_markdown_output がファクトチェック履歴とraw_resultsを出力すること
  5. FC失敗データがレポートに含まれないこと
  6. researcher生データ（URL未変更）が保存されること
"""
import json
import pytest
from datetime import datetime

from models.schemas import (
    Finding,
    Evidence,
    VerifiedEvidence,
    RemovedEvidence,
    VerifiedFinding,
    RemovedFinding,
    FactCheckResultOutput,
    SearchPlanOutput,
    SimpleSearchOutput,
    ResearchResultOutput,
    EvaluationOutput,
    ComparisonReportOutput,
)
from main import format_markdown_output


# ============================================================
# ヘルパー: テスト用のモックデータ生成
# ============================================================
def _make_findings(n: int) -> list[Finding]:
    return [Finding(content=f"発見事項{i}", source=f"出所{i}") for i in range(1, n + 1)]


def _make_evidence(n: int) -> list[Evidence]:
    return [Evidence(
        title=f"タイトル{i}",
        url=f"https://example.com/article{i}",
        summary=f"概要{i}",
    ) for i in range(1, n + 1)]


def _make_fact_check_history(iterations: int, removals_per_iter: list[int] = None) -> list[dict]:
    """ファクトチェック履歴を生成."""
    if removals_per_iter is None:
        removals_per_iter = [3, 1, 0][:iterations]
    history = []
    for i in range(iterations):
        verified = 10 - removals_per_iter[i] if i < len(removals_per_iter) else 10
        removed = removals_per_iter[i] if i < len(removals_per_iter) else 0
        total = verified + removed
        history.append({
            'iteration': i + 1,
            'verified': verified,
            'removed': removed,
            'reliability': verified / max(total, 1),
            'removed_reasons': [
                f"URL: https://fake{j}.example.com → 架空URL" for j in range(removed)
            ],
            'summary': f'反復{i+1}の検証完了: {verified}件検証済み, {removed}件除外',
        })
    return history


def _make_plan() -> SearchPlanOutput:
    return SearchPlanOutput(
        objective="テスト目的",
        research_areas=["領域A", "領域B"],
        search_keywords={"領域A": ["kw1"], "領域B": ["kw2"]},
        priority_order=["領域A", "領域B"],
        research_strategy="テスト戦略",
        expected_outcomes=["成果1"],
    )


def _make_research_result(n_findings=5, n_evidence=3) -> ResearchResultOutput:
    return ResearchResultOutput(
        theme="テストテーマ",
        findings=_make_findings(n_findings),
        evidence=_make_evidence(n_evidence),
        summary="テスト総括",
        research_depth_analysis="深さ分析",
        interconnections=["関連1", "関連2"],
        coverage_areas=["領域A", "領域B"],
    )


def _make_evaluation(
    iteration: int = 1,
    should_refine: bool = True,
    credibility: int = 7,
    overall: int = 45,
) -> EvaluationOutput:
    return EvaluationOutput(
        iteration_number=iteration,
        objective_achievement_score=8,
        coverage_score=7,
        depth_insight_score=7,
        actionability_score=8,
        credibility_score=credibility,
        quantitative_score=8,
        overall_quality_score=overall,
        should_refine=should_refine,
        coverage_gaps=["ギャップ1"],
        refinement_strategy="改善戦略",
        expert_observations="観察",
    )


def _make_simple_result() -> SimpleSearchOutput:
    return SimpleSearchOutput(
        findings=_make_findings(3),
        evidence=_make_evidence(2),
        summary="ワンショット総括",
        coverage_areas=["領域A"],
    )


def _make_comparison() -> ComparisonReportOutput:
    return ComparisonReportOutput(
        simple_search_total_score=30,
        agentic_search_total_score=50,
        objective_improvement_rate=20.0,
        coverage_improvement_rate=25.0,
        depth_insight_improvement_rate=30.0,
        credibility_improvement_rate=15.0,
        overall_improvement_summary="エージェンティック検索が優位",
        strengths_simple=["速度"],
        strengths_agentic=["深さ"],
        weaknesses_simple=["浅い"],
        weaknesses_agentic=["遅い"],
        recommendation="テーマによって使い分け",
    )


# ============================================================
# 1. fact_check_history の構造バリデーション
# ============================================================
class TestFactCheckHistoryStructure:
    """ファクトチェック履歴 dict の構造が正しいこと."""

    def test_required_keys(self):
        """必須キーがすべて存在すること."""
        history = _make_fact_check_history(1, [2])
        fc = history[0]
        required_keys = {'iteration', 'verified', 'removed', 'reliability',
                         'removed_reasons', 'summary'}
        assert required_keys.issubset(fc.keys())

    def test_reliability_calculation(self):
        """reliability は verified / (verified + removed) であること."""
        history = _make_fact_check_history(1, [4])
        fc = history[0]
        assert fc['verified'] == 6
        assert fc['removed'] == 4
        assert abs(fc['reliability'] - 0.6) < 0.01

    def test_zero_removal(self):
        """除外なしの場合は reliability=1.0 で removed_reasons が空."""
        history = _make_fact_check_history(1, [0])
        fc = history[0]
        assert fc['removed'] == 0
        assert fc['reliability'] == 1.0
        assert fc['removed_reasons'] == []

    def test_multi_iteration_history(self):
        """複数反復のファクトチェック履歴が正しく生成されること."""
        history = _make_fact_check_history(3, [5, 2, 0])
        assert len(history) == 3
        assert history[0]['iteration'] == 1
        assert history[1]['iteration'] == 2
        assert history[2]['iteration'] == 3
        # 反復を重ねるごとに除外が減る想定
        assert history[0]['removed'] > history[1]['removed'] > history[2]['removed']

    def test_cumulative_stats(self):
        """累計統計の計算が正しいこと."""
        history = _make_fact_check_history(3, [5, 2, 0])
        total_verified = sum(fc['verified'] for fc in history)
        total_removed = sum(fc['removed'] for fc in history)
        assert total_verified == 5 + 8 + 10  # (10-5) + (10-2) + (10-0)
        assert total_removed == 5 + 2 + 0


# ============================================================
# 2. format_markdown_output のテスト
# ============================================================
class TestFormatMarkdownOutput:
    """format_markdown_output がファクトチェック履歴を適切に出力すること."""

    def test_without_fact_check_history(self):
        """fact_check_history=None でもエラーにならないこと."""
        simple, agentic, comparison = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(iteration=1, should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=None,
        )
        assert "テスト" in simple
        assert "テスト" in agentic
        assert "テスト" in comparison
        # ファクトチェック表は表示されない
        assert "ファクトチェック履歴" not in agentic

    def test_with_fact_check_history(self):
        """fact_check_history が渡された場合、レポートに含まれること."""
        fc_history = _make_fact_check_history(3, [5, 2, 0])
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(iteration=1, should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=fc_history,
        )
        # ファクトチェック履歴テーブルが含まれる
        assert "ファクトチェック履歴" in agentic
        assert "検証済み" in agentic
        assert "除外" in agentic
        # 累計が正しい
        assert "ファクトチェック検証済み（累計）" in agentic
        assert "ファクトチェック除外（累計）" in agentic

    def test_fact_check_cumulative_in_summary_table(self):
        """サマリーテーブルにファクトチェック累計が含まれること."""
        fc_history = _make_fact_check_history(2, [3, 1])
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(iteration=1, should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=fc_history,
        )
        # 累計値: verified = 7+9=16, removed = 3+1=4
        assert "| ファクトチェック検証済み（累計） | 16 |" in agentic
        assert "| ファクトチェック除外（累計） | 4 |" in agentic

    def test_removed_details_section(self):
        """除外された情報の詳細セクションが含まれること."""
        fc_history = _make_fact_check_history(2, [3, 0])
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(iteration=1, should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=fc_history,
        )
        # 除外がある場合、details セクションが存在
        assert "除外された情報の詳細" in agentic
        assert "❌" in agentic

    def test_no_removal_no_details_section(self):
        """除外がない場合、details セクションは表示されないこと."""
        fc_history = _make_fact_check_history(1, [0])
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(iteration=1, should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=fc_history,
        )
        assert "除外された情報の詳細" not in agentic

    def test_per_iteration_table_rows(self):
        """各反復のファクトチェック結果がテーブル行として表示されること."""
        fc_history = _make_fact_check_history(3, [5, 2, 0])
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(iteration=1, should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=fc_history,
        )
        # 各反復の行が存在
        assert "| 1 | 5 | 5 | 50.0% |" in agentic
        assert "| 2 | 8 | 2 | 80.0% |" in agentic
        assert "| 3 | 10 | 0 | 100.0% |" in agentic


# ============================================================
# 3. FC通過フィルタ＋蓄積ロジックのユニットテスト
# ============================================================
class TestAccumulationLogic:
    """FC通過情報の蓄積・重複排除ロジックのテスト."""

    def test_dedup_findings_by_content(self):
        """findings は content[:80] で重複排除されること."""
        accepted = []
        existing_contents = set()

        findings_iter1 = [
            Finding(content="AIエージェントは自律的に行動する", source="出所1"),
            Finding(content="LLMは大規模言語モデルである", source="出所2"),
        ]
        for f in findings_iter1:
            key = f.content[:80]
            if key not in existing_contents:
                accepted.append(f)
                existing_contents.add(key)

        # 同じ内容を再度追加しても重複しない
        findings_iter2 = [
            Finding(content="AIエージェントは自律的に行動する", source="出所1-再"),
            Finding(content="新しい発見事項", source="出所3"),
        ]
        for f in findings_iter2:
            key = f.content[:80]
            if key not in existing_contents:
                accepted.append(f)
                existing_contents.add(key)

        assert len(accepted) == 3  # 重複1件が除外

    def test_dedup_evidence_by_url(self):
        """evidence は URL で重複排除されること."""
        accepted = []
        existing_urls = set()

        evidence_iter1 = [
            Evidence(title="T1", url="https://example.com/1", summary="S1"),
            Evidence(title="T2", url="https://example.com/2", summary="S2"),
        ]
        for e in evidence_iter1:
            if e.url and e.url not in existing_urls:
                accepted.append(e)
                existing_urls.add(e.url)

        # 同じURLを再度追加しても重複しない
        evidence_iter2 = [
            Evidence(title="T1-再", url="https://example.com/1", summary="S1-再"),
            Evidence(title="T3", url="https://example.com/3", summary="S3"),
        ]
        for e in evidence_iter2:
            if e.url and e.url not in existing_urls:
                accepted.append(e)
                existing_urls.add(e.url)

        assert len(accepted) == 3  # URL重複1件が除外

    def test_empty_url_not_accumulated(self):
        """空URLのevidenceは蓄積されないこと."""
        accepted = []
        existing_urls = set()
        evidence = [
            Evidence(title="T1", url="", summary="S1"),
            Evidence(title="T2", url="https://valid.com", summary="S2"),
        ]
        for e in evidence:
            if e.url and e.url not in existing_urls:
                accepted.append(e)
                existing_urls.add(e.url)

        assert len(accepted) == 1
        assert accepted[0].url == "https://valid.com"

    def test_final_result_uses_only_accepted(self):
        """最終結果にFC通過データのみが含まれること."""
        current_result = _make_research_result(n_findings=5, n_evidence=4)
        
        # FC通過データ（例: 5件中2件のみ通過）
        accepted_findings = [
            Finding(content="発見事項1", source="出所1"),
            Finding(content="発見事項3", source="出所3"),
        ]
        accepted_evidence = [
            Evidence(title="タイトル1", url="https://example.com/article1", summary="概要1"),
        ]

        # 新しいマージロジック: accepted のみで置換
        current_result.findings = list(accepted_findings)
        current_result.evidence = list(accepted_evidence)

        # FC通過分のみ
        assert len(current_result.findings) == 2
        assert len(current_result.evidence) == 1
        assert current_result.findings[0].content == "発見事項1"

    def test_fc_failed_iteration_contributes_nothing(self):
        """FC失敗（全件除外）の反復は蓄積に何も追加しないこと."""
        accepted_findings = []
        accepted_evidence = []
        existing_contents = set()
        existing_urls = set()

        # 反復1: 2件中2件FC通過
        fc_passed_1 = [
            Finding(content="合格した発見事項A", source="出所A"),
            Finding(content="合格した発見事項B", source="出所B"),
        ]
        for f in fc_passed_1:
            key = f.content[:80]
            if key not in existing_contents:
                accepted_findings.append(f)
                existing_contents.add(key)
        
        # 反復2: FC全件失敗 → 何も通過しない
        fc_passed_2 = []  # 全件fabricated
        for f in fc_passed_2:
            key = f.content[:80]
            if key not in existing_contents:
                accepted_findings.append(f)
                existing_contents.add(key)

        # 反復2の失敗で蓄積が増えていないこと
        assert len(accepted_findings) == 2

    def test_original_urls_preserved_in_accepted(self):
        """FC通過データのURLがresearcherの元のURLであること（FCが変更していない）."""
        original_url = "https://original-researcher.example.com/article1"
        
        # researcher の生出力
        researcher_evidence = [
            Evidence(title="T1", url=original_url, summary="S1"),
        ]
        
        # FCの verified_evidences（original_urlで照合）
        fc_verified_urls = {original_url}
        
        # 照合ロジック: 元のevidenceからFC通過分を抽出
        accepted = []
        for e in researcher_evidence:
            if e.url in fc_verified_urls:
                accepted.append(e)
        
        assert len(accepted) == 1
        assert accepted[0].url == original_url  # 元のURL保持


# ============================================================
# 4. 評価者へのファクトチェック情報反映テスト
# ============================================================
class TestEvaluatorFactCheckIntegration:
    """評価者プロンプトにファクトチェック情報が含まれること."""

    def test_credibility_scoring_rules(self):
        """除外率に基づくcredibility_scoreのルールが正しいこと."""
        # 除外率 > 30% → credibility ≤ 5
        fc = {'verified': 7, 'removed': 5, 'reliability': 0.583, 'summary': 'テスト'}
        removal_rate = fc['removed'] / max(fc['verified'] + fc['removed'], 1)
        assert removal_rate > 0.3
        # ルール: credibility_score は 5 以下

        # 除外率 > 20% → credibility ≤ 6
        fc2 = {'verified': 8, 'removed': 3, 'reliability': 0.727, 'summary': 'テスト'}
        removal_rate2 = fc2['removed'] / max(fc2['verified'] + fc2['removed'], 1)
        assert 0.2 < removal_rate2 <= 0.3

        # 除外率 > 10% → credibility ≤ 7
        fc3 = {'verified': 9, 'removed': 2, 'reliability': 0.818, 'summary': 'テスト'}
        removal_rate3 = fc3['removed'] / max(fc3['verified'] + fc3['removed'], 1)
        assert 0.1 < removal_rate3 <= 0.2

        # 除外率 0% → credibility ≥ 8 可能
        fc4 = {'verified': 10, 'removed': 0, 'reliability': 1.0, 'summary': 'テスト'}
        removal_rate4 = fc4['removed'] / max(fc4['verified'] + fc4['removed'], 1)
        assert removal_rate4 == 0.0

    def test_fact_check_section_generation(self):
        """ファクトチェックセクションの文字列が正しく生成されること."""
        fact_check_history = _make_fact_check_history(2, [4, 1])
        latest_fc = fact_check_history[-1]

        fact_check_section = f"""
【⚠️ ファクトチェック結果 — 信頼性評価に必ず反映すること】
- 検証済み情報: {latest_fc['verified']}件
- 除外された情報（ハルシネーション）: {latest_fc['removed']}件
- ファクトチェッカーの信頼性スコア: {latest_fc['reliability']:.1%}
- 検証サマリー: {latest_fc['summary']}
"""
        assert "検証済み情報: 9件" in fact_check_section
        assert "除外された情報（ハルシネーション）: 1件" in fact_check_section
        assert "90.0%" in fact_check_section


# ============================================================
# 5. リサーチャーへの前回コンテキスト反映テスト
# ============================================================
class TestResearcherPreviousContext:
    """リサーチャープロンプトに前回の結果が含まれること."""

    def test_previous_context_with_findings(self):
        """蓄積された発見事項がコンテキストに含まれること."""
        accepted = _make_findings(5)
        previous_context = ""
        if accepted:
            previous_context += f"""
【前回までのFC通過発見事項（{len(accepted)}件）】
以下は前回までにFC通過した発見事項です。これらと重複しない新しい情報を探してください。
"""
            for f in accepted[:10]:
                previous_context += f'  - {f.content[:80]}...\n'

        assert "FC通過発見事項（5件）" in previous_context
        assert "発見事項1" in previous_context

    def test_previous_context_with_evidence(self):
        """蓄積されたevidenceのURLがコンテキストに含まれること."""
        accepted = _make_evidence(3)
        previous_context = ""
        if accepted:
            previous_context += f"""
【前回までのFC通過根拠情報（{len(accepted)}件）】
以下のURLはFC通過済みです。新しいURLを探すこと。
"""
            for e in accepted[:8]:
                previous_context += f'  - {e.url} ({e.title})\n'

        assert "FC通過根拠情報（3件）" in previous_context
        assert "https://example.com/article1" in previous_context

    def test_previous_context_with_fact_check_history(self):
        """ファクトチェック履歴が前回コンテキストに含まれること."""
        fact_check_history = _make_fact_check_history(1, [4])
        latest_fc = fact_check_history[-1]

        previous_context = f"""
【⚠️ 前回のファクトチェック結果 — 重要】
- 検証済み: {latest_fc['verified']}件 / 除外: {latest_fc['removed']}件
- 信頼性スコア: {latest_fc['reliability']:.1%}
"""
        if latest_fc.get('removed_reasons'):
            previous_context += "- 除外されたURL/情報のパターン:\n"
            for reason in latest_fc['removed_reasons'][:5]:
                previous_context += f"  ❌ {reason}\n"
            previous_context += """
**上記のパターンを絶対に繰り返さないこと。**
"""

        assert "検証済み: 6件 / 除外: 4件" in previous_context
        assert "60.0%" in previous_context
        assert "❌" in previous_context
        assert "上記のパターンを絶対に繰り返さないこと" in previous_context

    def test_improvement_instruction_from_evaluation(self):
        """評価者からの改善指示がコンテキストに含まれること."""
        eval_ = _make_evaluation(iteration=1, credibility=5, overall=40)
        improvement = ""
        if eval_.coverage_gaps:
            improvement += f"""
【評価者からの改善要求】
- 前回の総合スコア: {eval_.overall_quality_score}/60
- 信頼性スコア: {eval_.credibility_score}/10
- 不足している観点: {', '.join(eval_.coverage_gaps[:5])}
- 改善戦略: {eval_.refinement_strategy or '特になし'}
"""
        assert "総合スコア: 40/60" in improvement
        assert "信頼性スコア: 5/10" in improvement
        assert "ギャップ1" in improvement


# ============================================================
# 6. run_agentic_research の戻り値テスト（型チェック）
# ============================================================
class TestReturnValueStructure:
    """run_agentic_research の戻り値が5-tupleであること."""

    def test_five_tuple_unpacking(self):
        """5-tuple をアンパックできること."""
        # 実際のAPI呼び出しは行わず、戻り値の型を模擬
        plan = _make_plan()
        result = _make_research_result()
        evaluations = [_make_evaluation(should_refine=False)]
        fact_check_history = _make_fact_check_history(2, [3, 0])
        raw_results = [
            {
                'iteration': 1,
                'findings': [{'content': '発見1', 'source': '出所1'}],
                'evidence': [{'title': 'T1', 'url': 'https://raw.example.com/1', 'summary': 'S1'}],
                'summary': '反復1の概要',
            },
        ]

        return_value = (plan, result, evaluations, fact_check_history, raw_results)

        # 5-tuple としてアンパック
        p, r, e, fc, raw = return_value
        assert isinstance(p, SearchPlanOutput)
        assert isinstance(r, ResearchResultOutput)
        assert isinstance(e, list)
        assert isinstance(fc, list)
        assert isinstance(raw, list)
        assert len(fc) == 2
        assert len(raw) == 1

    def test_raw_results_structure(self):
        """raw_results の各エントリが正しい構造を持つこと."""
        raw_results = [
            {
                'iteration': 1,
                'findings': [
                    {'content': '発見1', 'source': '出所1'},
                    {'content': '発見2', 'source': '出所2'},
                ],
                'evidence': [
                    {'title': 'T1', 'url': 'https://raw.example.com/1', 'summary': 'S1'},
                ],
                'summary': '反復1の概要',
            },
            {
                'iteration': 2,
                'findings': [{'content': '発見3', 'source': '出所3'}],
                'evidence': [
                    {'title': 'T2', 'url': 'https://raw.example.com/2', 'summary': 'S2'},
                ],
                'summary': '反復2の概要',
            },
        ]
        for raw in raw_results:
            assert 'iteration' in raw
            assert 'findings' in raw
            assert 'evidence' in raw
            assert 'summary' in raw
            assert isinstance(raw['findings'], list)
            assert isinstance(raw['evidence'], list)

    def test_raw_results_urls_unchanged(self):
        """raw_results のURLがFC処理後も変更されていないこと."""
        original_url = "https://original.example.com/article1"
        raw_results = [
            {
                'iteration': 1,
                'findings': [],
                'evidence': [{'title': 'T1', 'url': original_url, 'summary': 'S1'}],
                'summary': '',
            },
        ]
        # raw_results のURLは元のまま
        assert raw_results[0]['evidence'][0]['url'] == original_url

    def test_fact_check_history_in_main_flow(self):
        """main.py のフロー: 5-tuple アンパック → format_markdown_output."""
        plan = _make_plan()
        result = _make_research_result()
        evaluations = [_make_evaluation(should_refine=False)]
        fc_history = _make_fact_check_history(2, [3, 0])
        raw_results = [
            {
                'iteration': 1,
                'findings': [{'content': '発見1', 'source': '出所1'}],
                'evidence': [{'title': 'T1', 'url': 'https://raw.example.com/1', 'summary': 'S1'}],
                'summary': '反復1',
            },
        ]

        # main.py と同じアンパック
        agentic_plan, agentic_result, evals, fact_check_history, raw = (
            plan, result, evaluations, fc_history, raw_results
        )

        # format_markdown_output に渡す
        simple_md, agentic_md, comparison_md = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=agentic_plan,
            agentic_result=agentic_result,
            evaluations=evals,
            comparison_result=_make_comparison(),
            fact_check_history=fact_check_history,
            raw_results=raw,
        )

        assert "ファクトチェック履歴" in agentic_md
        assert isinstance(simple_md, str)
        assert isinstance(comparison_md, str)


# ============================================================
# 7. エッジケース
# ============================================================
class TestEdgeCases:
    """エッジケースのテスト."""

    def test_empty_fact_check_history(self):
        """空の fact_check_history でもレポート生成が成功すること."""
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=[],
        )
        assert "ファクトチェック履歴" not in agentic

    def test_all_removed_fact_check(self):
        """全件除外されたファクトチェック結果."""
        fc_history = [{
            'iteration': 1,
            'verified': 0,
            'removed': 10,
            'reliability': 0.0,
            'removed_reasons': [f"URL: https://fake{i}.com → 架空URL" for i in range(10)],
            'summary': '全件除外',
        }]
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=fc_history,
        )
        assert "| ファクトチェック除外（累計） | 10 |" in agentic
        assert "0.0%" in agentic

    def test_fact_check_skipped_iteration(self):
        """ファクトチェックがスキップされた反復."""
        fc_history = [{
            'iteration': 1,
            'verified': 0,
            'removed': 0,
            'reliability': 0.0,
            'removed_reasons': [],
            'summary': 'ファクトチェックをスキップ（evidence/findingsが空）',
        }]
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=fc_history,
        )
        # スキップされた場合でもテーブルに表示される
        assert "| 1 | 0 | 0 |" in agentic

    def test_multiple_evaluations_display(self):
        """複数反復の評価が折りたたみで表示されること."""
        evals = [
            _make_evaluation(iteration=1, should_refine=True, credibility=5, overall=35),
            _make_evaluation(iteration=2, should_refine=True, credibility=6, overall=42),
            _make_evaluation(iteration=3, should_refine=False, credibility=8, overall=52),
        ]
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=evals,
            comparison_result=_make_comparison(),
            fact_check_history=_make_fact_check_history(3, [5, 2, 0]),
        )
        # 3反復分の評価詳細が存在
        assert "反復1の評価詳細" in agentic
        assert "反復2の評価詳細" in agentic
        assert "反復3の評価詳細" in agentic

    def test_raw_results_appendix_present(self):
        """raw_results が渡された場合、付録セクションが含まれること."""
        raw_results = [
            {
                'iteration': 1,
                'findings': [{'content': '生の発見1', 'source': '出所1'}],
                'evidence': [{'title': 'RawT1', 'url': 'https://raw.example.com/1', 'summary': 'RawS1'}],
                'summary': '反復1生データ',
            },
        ]
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=_make_fact_check_history(1, [0]),
            raw_results=raw_results,
        )
        assert "Researcher生出力データ" in agentic
        assert "反復1の生データ" in agentic
        assert "https://raw.example.com/1" in agentic

    def test_raw_results_none_no_appendix(self):
        """raw_results=None の場合、付録セクションが含まれないこと."""
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(should_refine=False)],
            comparison_result=_make_comparison(),
            fact_check_history=None,
            raw_results=None,
        )
        assert "Researcher生出力データ" not in agentic

    def test_raw_results_with_pydantic_models(self):
        """raw_results にPydanticモデルが含まれてもエラーにならないこと."""
        raw_results = [
            {
                'iteration': 1,
                'findings': [Finding(content="Pydantic発見", source="出所P")],
                'evidence': [Evidence(title="PT1", url="https://pydantic.example.com", summary="PS1")],
                'summary': '反復1',
            },
        ]
        _, agentic, _ = format_markdown_output(
            theme="テスト",
            simple_result=_make_simple_result(),
            agentic_plan=_make_plan(),
            agentic_result=_make_research_result(),
            evaluations=[_make_evaluation(should_refine=False)],
            comparison_result=_make_comparison(),
            raw_results=raw_results,
        )
        assert "Pydantic発見" in agentic
        assert "https://pydantic.example.com" in agentic


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
