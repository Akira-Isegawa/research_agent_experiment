"""研究エージェント スキーマのバリデーションテスト.

全スキーマについて、LLMがフィールドを省略した場合でも
バリデーションが通ることを確認する包括的テスト。

テスト方針:
  1. 完全なデータ（全フィールド指定）でバリデーション通過
  2. 最小データ（必須フィールドのみ / 空JSON）でバリデーション通過
  3. ネストされたスキーマでフィールド欠落してもバリデーション通過
  4. 実際のLLM出力パターンを再現してバリデーション通過
"""
import json
import pytest
from pydantic import TypeAdapter
from agents import Runner
from agents.exceptions import ModelBehaviorError

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


# ============================================================
# ヘルパー: TypeAdapterでJSONバリデーション
# ============================================================
def validate_json(model_class, data: dict):
    """Pydantic TypeAdapterでJSONバリデーションを実行する。"""
    ta = TypeAdapter(model_class)
    return ta.validate_json(json.dumps(data, ensure_ascii=False))


# ============================================================
# 1. Finding / Evidence (基本構成要素)
# ============================================================
class TestFinding:
    def test_full(self):
        result = validate_json(Finding, {"content": "テスト発見", "source": "テスト出所"})
        assert result.content == "テスト発見"
        assert result.source == "テスト出所"

    def test_empty(self):
        """LLMが空オブジェクトを返した場合"""
        result = validate_json(Finding, {})
        assert result.content == ""
        assert result.source == ""

    def test_partial(self):
        """contentのみ"""
        result = validate_json(Finding, {"content": "部分データ"})
        assert result.content == "部分データ"
        assert result.source == ""


class TestEvidence:
    def test_full(self):
        result = validate_json(Evidence, {
            "title": "タイトル", "url": "https://example.com", "summary": "概要"
        })
        assert result.url == "https://example.com"

    def test_empty(self):
        result = validate_json(Evidence, {})
        assert result.title == ""
        assert result.url == ""
        assert result.summary == ""

    def test_partial(self):
        result = validate_json(Evidence, {"title": "タイトルのみ"})
        assert result.title == "タイトルのみ"


# ============================================================
# 2. VerifiedEvidence / RemovedEvidence / VerifiedFinding / RemovedFinding
# ============================================================
class TestVerifiedEvidence:
    def test_full(self):
        result = validate_json(VerifiedEvidence, {
            "title": "T", "url": "http://x.com", "original_url": "http://y.com",
            "summary": "S", "status": "verified", "verification_note": "OK"
        })
        assert result.status == "verified"

    def test_empty(self):
        result = validate_json(VerifiedEvidence, {})
        assert result.status == "unverified"
        assert result.verification_note == ""


class TestRemovedEvidence:
    def test_empty(self):
        result = validate_json(RemovedEvidence, {})
        assert result.title == ""
        assert result.reason == ""


class TestVerifiedFinding:
    def test_empty(self):
        result = validate_json(VerifiedFinding, {})
        assert result.confidence == "low"
        assert result.source_url == ""


class TestRemovedFinding:
    def test_empty(self):
        result = validate_json(RemovedFinding, {})
        assert result.content == ""
        assert result.reason == ""


# ============================================================
# 3. FactCheckResultOutput
# ============================================================
class TestFactCheckResultOutput:
    def test_full(self):
        result = validate_json(FactCheckResultOutput, {
            "verified_evidences": [{"title": "T", "url": "http://x.com",
                                     "original_url": "http://y.com", "summary": "S",
                                     "status": "verified", "verification_note": "OK"}],
            "removed_evidences": [],
            "verified_findings": [{"content": "C", "source": "S",
                                    "source_url": "http://z.com", "confidence": "high"}],
            "removed_findings": [],
            "verification_summary": "全件検証済み",
            "total_verified": 1,
            "total_removed": 0,
            "reliability_score": 1.0,
        })
        assert result.total_verified == 1

    def test_empty(self):
        """全フィールド省略"""
        result = validate_json(FactCheckResultOutput, {})
        assert result.verified_evidences == []
        assert result.removed_evidences == []
        assert result.verified_findings == []
        assert result.removed_findings == []
        assert result.verification_summary == ""
        assert result.total_verified == 0
        assert result.total_removed == 0
        assert result.reliability_score == 0.0


# ============================================================
# 4. SearchPlanOutput
# ============================================================
class TestSearchPlanOutput:
    def test_full(self):
        result = validate_json(SearchPlanOutput, {
            "objective": "テスト目的",
            "research_areas": ["a", "b", "c", "d", "e"],
            "search_keywords": {"a": ["kw1", "kw2"]},
            "priority_order": ["a", "b", "c", "d", "e"],
            "research_strategy": "テスト戦略",
            "expected_outcomes": ["成果1", "成果2"],
        })
        assert result.objective == "テスト目的"
        assert len(result.research_areas) == 5

    def test_empty(self):
        """今回のエラーの根本原因: expected_outcomes等が欠落"""
        result = validate_json(SearchPlanOutput, {})
        assert result.objective == ""
        assert result.research_areas == []
        assert result.search_keywords == {}
        assert result.priority_order == []
        assert result.research_strategy == ""
        assert result.expected_outcomes == []

    def test_partial_no_expected_outcomes(self):
        """今回の実際のエラーパターン: expected_outcomesのみ欠落"""
        result = validate_json(SearchPlanOutput, {
            "objective": "2025年以降の最新AIエージェント調査",
            "research_areas": ["領域A", "領域B", "領域C", "領域D", "領域E"],
            "search_keywords": {"領域A": ["kw1"]},
            "priority_order": ["領域A"],
            "research_strategy": "段階的調査",
            # expected_outcomes が欠落
        })
        assert result.expected_outcomes == []
        assert result.objective == "2025年以降の最新AIエージェント調査"


# ============================================================
# 5. SimpleSearchOutput
# ============================================================
class TestSimpleSearchOutput:
    def test_full(self):
        result = validate_json(SimpleSearchOutput, {
            "theme": "テスト",
            "findings": [{"content": "f1", "source": "s1"}],
            "evidence": [{"title": "t1", "url": "http://x.com", "summary": "s"}],
            "summary": "総括テスト",
            "coverage_areas": ["領域1"],
        })
        assert result.theme == "テスト"

    def test_empty(self):
        result = validate_json(SimpleSearchOutput, {})
        assert result.theme == ""
        assert result.findings == []
        assert result.evidence == []
        assert result.coverage_areas == []

    def test_no_evidence(self):
        """前回のエラーパターン: evidence欠落"""
        result = validate_json(SimpleSearchOutput, {
            "theme": "テスト",
            "findings": [{"content": "f1", "source": "s1"}],
        })
        assert result.evidence == []

    def test_no_summary(self):
        """前々回のエラーパターン: summary欠落"""
        result = validate_json(SimpleSearchOutput, {
            "theme": "テスト",
            "findings": [{"content": "f1", "source": "s1"}],
            "evidence": [{"title": "t", "url": "http://x.com", "summary": "s"}],
        })
        assert "総括" in result.summary or "findings" in result.summary


# ============================================================
# 6. ResearchResultOutput
# ============================================================
class TestResearchResultOutput:
    def test_full(self):
        result = validate_json(ResearchResultOutput, {
            "theme": "テスト",
            "plan_used": {
                "objective": "目的",
                "research_areas": ["a", "b", "c", "d", "e"],
                "search_keywords": {"a": ["kw"]},
                "priority_order": ["a"],
                "research_strategy": "戦略",
                "expected_outcomes": ["成果"],
            },
            "findings": [{"content": "f1", "source": "s1"}],
            "evidence": [{"title": "t", "url": "http://x.com", "summary": "s"}],
            "summary": "テスト総括",
            "research_depth_analysis": "深さ分析",
            "interconnections": ["関連1"],
            "iteration_number": 2,
        })
        assert result.iteration_number == 2

    def test_empty(self):
        """全フィールド欠落"""
        result = validate_json(ResearchResultOutput, {})
        assert result.theme == ""
        assert result.plan_used is None
        assert result.findings == []
        assert result.evidence == []
        assert result.iteration_number == 1

    def test_no_evidence(self):
        """前回のエラーパターン: evidence欠落"""
        result = validate_json(ResearchResultOutput, {
            "theme": "テスト",
            "plan_used": {"objective": "目的"},
            "findings": [{"content": "f", "source": "s"}],
            "iteration_number": 3,
        })
        assert result.evidence == []
        assert len(result.findings) == 1

    def test_plan_used_missing_expected_outcomes(self):
        """今回のエラーパターン: plan_used.expected_outcomes欠落"""
        result = validate_json(ResearchResultOutput, {
            "theme": "AIエージェントを企画やアイデア出しに用いる研究",
            "plan_used": {
                "objective": "2025年以降の最新AIエージェント調査",
                "research_areas": ["領域1", "領域2", "領域3", "領域4", "領域5"],
                "search_keywords": {"領域1": ["kw1"]},
                "priority_order": ["領域1"],
                "research_strategy": "段階的調査",
                # expected_outcomes 欠落
            },
            "iteration_number": 1,
            "evidence": [{"title": "t", "url": "http://x.com", "summary": "s"}],
            "findings": [{"content": "f", "source": "s"}],
        })
        assert result.plan_used is not None
        assert result.plan_used.expected_outcomes == []

    def test_plan_used_completely_empty(self):
        """plan_usedが空オブジェクト"""
        result = validate_json(ResearchResultOutput, {
            "theme": "テスト",
            "plan_used": {},
            "findings": [{"content": "f", "source": "s"}],
        })
        assert result.plan_used is not None
        assert result.plan_used.objective == ""

    def test_no_plan_used(self):
        """plan_usedが完全に省略"""
        result = validate_json(ResearchResultOutput, {
            "theme": "テスト",
            "findings": [{"content": "f", "source": "s"}],
        })
        assert result.plan_used is None

    def test_real_world_llm_output(self):
        """実際のLLM出力を模倣した大規模テスト"""
        data = {
            "theme": "AIエージェント研究",
            "plan_used": {
                "objective": "調査目的",
                "research_areas": ["A", "B", "C", "D", "E", "F", "G"],
                "search_keywords": {
                    "A": ["kw1", "kw2"],
                    "B": ["kw3"],
                },
                "priority_order": ["A", "B", "C"],
                "research_strategy": "段階的に調査",
                # expected_outcomes 省略
            },
            "iteration_number": 3,
            "evidence": [
                {"title": f"Evidence {i}", "url": f"https://example.com/{i}", "summary": f"Summary {i}"}
                for i in range(10)
            ],
            "findings": [
                {"content": f"Finding content {i} with detailed description.", "source": f"Source {i}"}
                for i in range(10)
            ],
            "summary": "調査結果の総括",
            "research_depth_analysis": "深さ分析",
            "interconnections": ["関連1", "関連2"],
        }
        result = validate_json(ResearchResultOutput, data)
        assert len(result.findings) == 10
        assert len(result.evidence) == 10
        assert result.plan_used.expected_outcomes == []


# ============================================================
# 7. EvaluationOutput
# ============================================================
class TestEvaluationOutput:
    def test_full(self):
        result = validate_json(EvaluationOutput, {
            "iteration_number": 2,
            "objective_achievement_score": 8,
            "coverage_score": 7,
            "depth_insight_score": 7,
            "actionability_score": 6,
            "credibility_score": 8,
            "quantitative_score": 7,
            "coverage_gaps": ["倫理面の分析不足"],
            "overall_quality_score": 43,
            "should_refine": True,
            "refinement_strategy": "倫理面を追加調査",
            "refined_plan": None,
            "expert_observations": "全体的に良好",
        })
        assert result.overall_quality_score == 43
        assert result.should_refine is True

    def test_empty(self):
        """全フィールド省略"""
        result = validate_json(EvaluationOutput, {})
        assert result.iteration_number == 1
        assert result.objective_achievement_score == 0
        assert result.coverage_gaps == []
        assert result.overall_quality_score == 0
        assert result.should_refine is True  # デフォルトTrue（安全側）
        assert result.expert_observations == ""

    def test_partial_scores(self):
        """一部スコアのみ"""
        result = validate_json(EvaluationOutput, {
            "iteration_number": 1,
            "objective_achievement_score": 9,
            "coverage_score": 8,
        })
        assert result.objective_achievement_score == 9
        assert result.depth_insight_score == 0  # デフォルト

    def test_with_refined_plan_missing_fields(self):
        """refined_plan内のフィールドも欠落可能"""
        result = validate_json(EvaluationOutput, {
            "iteration_number": 1,
            "should_refine": True,
            "refined_plan": {
                "objective": "修正目的",
                # 他のフィールド省略
            },
        })
        assert result.refined_plan is not None
        assert result.refined_plan.expected_outcomes == []


# ============================================================
# 8. ComparisonReportOutput
# ============================================================
class TestComparisonReportOutput:
    def test_full(self):
        result = validate_json(ComparisonReportOutput, {
            "theme": "テスト",
            "simple_search_objective_score": 5,
            "simple_search_coverage_score": 4,
            "simple_search_depth_insight_score": 3,
            "simple_search_actionability_score": 4,
            "simple_search_credibility_score": 5,
            "simple_search_quantitative_score": 3,
            "agentic_search_objective_score": 8,
            "agentic_search_coverage_score": 8,
            "agentic_search_depth_insight_score": 7,
            "agentic_search_actionability_score": 7,
            "agentic_search_credibility_score": 8,
            "agentic_search_quantitative_score": 7,
            "objective_improvement_rate": 60.0,
            "coverage_improvement_rate": 100.0,
            "depth_insight_improvement_rate": 133.3,
            "actionability_improvement_rate": 75.0,
            "credibility_improvement_rate": 60.0,
            "quantitative_improvement_rate": 133.3,
            "simple_search_total_score": 24.0,
            "agentic_search_total_score": 45.0,
            "key_differences": ["差異1"],
            "simple_search_strengths": ["強み1"],
            "simple_search_weaknesses": ["弱み1"],
            "agentic_search_strengths": ["強み1"],
            "agentic_search_weaknesses": ["弱み1"],
            "recommendation": "推奨",
            "cost_effectiveness_analysis": "費用対効果",
        })
        assert result.agentic_search_total_score == 45.0

    def test_empty(self):
        """全フィールド省略"""
        result = validate_json(ComparisonReportOutput, {})
        assert result.theme == ""
        assert result.simple_search_objective_score == 0
        assert result.agentic_search_objective_score == 0
        assert result.objective_improvement_rate == 0.0
        assert result.simple_search_total_score == 0.0
        assert result.key_differences == []
        assert result.recommendation == ""

    def test_partial_scores_only(self):
        """スコアのみ、定性分析欠落"""
        result = validate_json(ComparisonReportOutput, {
            "theme": "テスト",
            "simple_search_objective_score": 5,
            "agentic_search_objective_score": 8,
        })
        assert result.simple_search_coverage_score == 0
        assert result.key_differences == []


# ============================================================
# 9. 実際に発生した全エラーパターンの再現テスト
# ============================================================
class TestRealWorldErrorPatterns:
    """過去に発生した全てのバリデーションエラーを再現し、修正を検証する。"""

    def test_error_1_summary_missing_in_simple_search(self):
        """エラー1: SimpleSearchOutput.summary欠落"""
        data = {
            "theme": "テスト",
            "findings": [{"content": f"f{i}", "source": f"s{i}"} for i in range(15)],
            "evidence": [{"title": f"t{i}", "url": f"http://x.com/{i}", "summary": f"s{i}"} for i in range(10)],
            # summary, coverage_areas 欠落
        }
        result = validate_json(SimpleSearchOutput, data)
        assert len(result.findings) == 15
        assert "findings" in result.summary

    def test_error_2_evidence_missing_in_research_result(self):
        """エラー2: ResearchResultOutput.evidence欠落"""
        data = {
            "theme": "テスト",
            "plan_used": {
                "objective": "目的",
                "research_areas": ["a", "b", "c", "d", "e"],
                "search_keywords": {"a": ["kw"]},
                "priority_order": ["a"],
                "research_strategy": "戦略",
                "expected_outcomes": ["成果"],
            },
            "findings": [{"content": f"f{i}", "source": f"s{i}"} for i in range(10)],
            "iteration_number": 3,
            # evidence 欠落
        }
        result = validate_json(ResearchResultOutput, data)
        assert result.evidence == []
        assert len(result.findings) == 10

    def test_error_3_expected_outcomes_missing_in_nested_plan(self):
        """エラー3 (今回): ResearchResultOutput.plan_used.expected_outcomes欠落"""
        data = {
            "theme": "AIエージェントを企画やアイデア出しに用いる研究（2025年以降）",
            "plan_used": {
                "objective": "2025年以降に発表された最新AIエージェント調査",
                "research_areas": [
                    "最新AIエージェントの概要とアーキテクチャ動向",
                    "AIエージェントによる企画・アイデア創出手法",
                    "ワンショットプロンプト・コンテキストエンジニアリングとの比較",
                    "評価指標・評価手法の最新動向",
                    "実践・応用事例",
                    "限界・課題・今後の展望",
                    "アカデミック/業界の論文・研究データベース情報",
                ],
                "search_keywords": {
                    "最新AIエージェントの概要とアーキテクチャ動向": ["GPT-5.2 architecture 2025"],
                },
                "priority_order": ["最新AIエージェントの概要とアーキテクチャ動向"],
                "research_strategy": "段階的調査",
                # expected_outcomes 欠落 ← 今回の実際のエラー
            },
            "iteration_number": 1,
            "evidence": [
                {"title": "CASCADE", "url": "https://arxiv.org/abs/2512.23880", "summary": "概要"},
            ],
            "findings": [
                {"content": "CASCADEフレームワーク", "source": "arXiv 2512.23880"},
            ],
            "summary": "調査結果の総括",
        }
        result = validate_json(ResearchResultOutput, data)
        assert result.plan_used is not None
        assert result.plan_used.expected_outcomes == []
        assert len(result.evidence) == 1
        assert len(result.findings) == 1

    def test_error_4_multiple_fields_missing(self):
        """将来のエラー防止: 複数フィールド同時欠落"""
        data = {
            "theme": "テスト",
            "plan_used": {
                "objective": "目的のみ",
                # 他全て欠落
            },
            # findings, evidence, summary, research_depth_analysis 等全て欠落
        }
        result = validate_json(ResearchResultOutput, data)
        assert result.findings == []
        assert result.evidence == []
        assert result.plan_used.research_areas == []
        assert result.plan_used.search_keywords == {}
        assert result.iteration_number == 1

    def test_error_5_completely_empty_json(self):
        """将来のエラー防止: 完全に空のJSONオブジェクト"""
        for model_class in [
            Finding, Evidence, VerifiedEvidence, RemovedEvidence,
            VerifiedFinding, RemovedFinding, FactCheckResultOutput,
            SearchPlanOutput, SimpleSearchOutput, ResearchResultOutput,
            EvaluationOutput, ComparisonReportOutput,
        ]:
            result = validate_json(model_class, {})
            assert result is not None, f"{model_class.__name__} failed with empty dict"


# ============================================================
# 10. トークン切り詰めエラーパターンの再現テスト
# ============================================================
class TestTruncatedJsonPatterns:
    """LLM出力がトークン制限で途中切りされた場合のエラーパターン。
    
    これらは Pydantic の TypeAdapter では修復できない構造的破損。
    _run_with_retry() で ModelBehaviorError としてキャッチし、
    リトライすることで対処する。
    """

    def test_finding_as_truncated_string(self):
        """実際のエラー: findings配列の要素が'{' という文字列になる"""
        data = {
            "theme": "テスト",
            "findings": [
                {"content": "正常な発見1", "source": "ソース1"},
                {"content": "正常な発見2", "source": "ソース2"},
                "{",  # ← トークン切り詰めで途切れた要素
            ],
        }
        with pytest.raises(Exception):
            # findingsの要素が文字列の場合、Findingオブジェクトとして解釈できない
            validate_json(ResearchResultOutput, data)

    def test_finding_as_partial_object(self):
        """findings要素が部分的なオブジェクト（contentのみ）"""
        data = {
            "theme": "テスト",
            "findings": [
                {"content": "正常な発見1", "source": "ソース1"},
                {"content": "途中で切れた発見"},  # sourceが欠落 → デフォルト値で通る
            ],
        }
        result = validate_json(ResearchResultOutput, data)
        assert len(result.findings) == 2
        assert result.findings[1].source == ""  # デフォルト値

    def test_evidence_as_truncated_string(self):
        """evidence配列の要素が文字列になった場合"""
        data = {
            "theme": "テスト",
            "evidence": [
                {"title": "正常", "url": "http://x.com", "summary": "OK"},
                '{"title": "切り詰められた',  # 文字列
            ],
        }
        with pytest.raises(Exception):
            validate_json(ResearchResultOutput, data)

    def test_malformed_json_string(self):
        """JSONそのものが壊れている（閉じ括弧なし）→ json.loadsで失敗"""
        malformed_json = '{"theme": "テスト", "findings": [{"content": "f1", "source": "s1"}, {"co'
        with pytest.raises(Exception):
            ta = TypeAdapter(ResearchResultOutput)
            ta.validate_json(malformed_json)

    def test_truncated_at_field_value(self):
        """フィールド値の途中でトークン切り詰め"""
        truncated_json = '{"theme": "AIエージェント研究", "summary": "この調査では'
        with pytest.raises(Exception):
            ta = TypeAdapter(ResearchResultOutput)
            ta.validate_json(truncated_json)

    def test_truncated_after_key(self):
        """キー名の後でトークン切り詰め"""
        truncated_json = '{"theme": "テスト", "findings":'
        with pytest.raises(Exception):
            ta = TypeAdapter(ResearchResultOutput)
            ta.validate_json(truncated_json)

    def test_empty_truncated_findings(self):
        """findings配列が途中で切れ、空配列で終わる（合法）"""
        data = {
            "theme": "テスト",
            "findings": [],  # 空配列は合法
            "evidence": [{"title": "t", "url": "http://x.com", "summary": "s"}],
        }
        result = validate_json(ResearchResultOutput, data)
        assert result.findings == []

    def test_number_as_finding(self):
        """findings配列要素が数値になった場合"""
        data = {
            "theme": "テスト",
            "findings": [42],
        }
        with pytest.raises(Exception):
            validate_json(ResearchResultOutput, data)

    def test_null_in_findings_array(self):
        """findings配列にnullが含まれる場合"""
        data = {
            "theme": "テスト",
            "findings": [
                {"content": "正常", "source": "s"},
                None,
            ],
        }
        with pytest.raises(Exception):
            validate_json(ResearchResultOutput, data)


# ============================================================
# 11. _run_with_retry() のユニットテスト
# ============================================================
class TestRunWithRetry:
    """_run_with_retry() のリトライロジックをモック付きでテスト。"""

    @pytest.fixture
    def mock_agent(self):
        """ダミーAgentオブジェクト"""
        class DummyAgent:
            name = "TestAgent"
        return DummyAgent()

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, mock_agent, monkeypatch):
        """1回目で成功する場合"""
        from workflows import research as research_mod

        class MockResult:
            def final_output_as(self, output_type):
                return SimpleSearchOutput(
                    theme="成功テスト",
                    findings=[Finding(content="f", source="s")],
                )

        async def mock_runner_run(agent, prompt):
            return MockResult()

        monkeypatch.setattr(research_mod.Runner, "run", staticmethod(mock_runner_run))

        result = await research_mod._run_with_retry(
            mock_agent, "テスト", SimpleSearchOutput,
            agent_name="Test", verbose=False,
        )
        assert result.theme == "成功テスト"
        assert len(result.findings) == 1

    @pytest.mark.asyncio
    async def test_success_on_retry(self, mock_agent, monkeypatch):
        """1回目失敗→2回目成功"""
        from workflows import research as research_mod

        call_count = 0

        class MockResult:
            def final_output_as(self, output_type):
                return SimpleSearchOutput(theme="リトライ成功")

        async def mock_runner_run(agent, prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ModelBehaviorError("Invalid JSON: truncated output")
            return MockResult()

        monkeypatch.setattr(research_mod.Runner, "run", staticmethod(mock_runner_run))

        result = await research_mod._run_with_retry(
            mock_agent, "テスト", SimpleSearchOutput,
            agent_name="Test", max_retries=2, verbose=False,
        )
        assert result.theme == "リトライ成功"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_prompt_includes_reduction_instructions(self, mock_agent, monkeypatch):
        """リトライ時のプロンプトに出力削減指示が含まれる"""
        from workflows import research as research_mod

        captured_prompts = []

        class MockResult:
            def final_output_as(self, output_type):
                return SimpleSearchOutput(theme="OK")

        async def mock_runner_run(agent, prompt):
            captured_prompts.append(prompt)
            if len(captured_prompts) == 1:
                raise ModelBehaviorError("Invalid JSON")
            return MockResult()

        monkeypatch.setattr(research_mod.Runner, "run", staticmethod(mock_runner_run))

        await research_mod._run_with_retry(
            mock_agent, "元のプロンプト", SimpleSearchOutput,
            agent_name="Test", max_retries=1, verbose=False,
        )

        assert len(captured_prompts) == 2
        # 1回目は元のプロンプト
        assert "リトライ" not in captured_prompts[0]
        # 2回目はリトライ指示付き
        assert "リトライ" in captured_prompts[1]
        assert "findings は最大 8 件" in captured_prompts[1]
        assert "evidence は最大 5 件" in captured_prompts[1]

    @pytest.mark.asyncio
    async def test_all_retries_fail_raises_error(self, mock_agent, monkeypatch):
        """全リトライ失敗→ModelBehaviorErrorが再送出"""
        from workflows import research as research_mod

        async def mock_runner_run(agent, prompt):
            raise ModelBehaviorError("Invalid JSON: always fail")

        monkeypatch.setattr(research_mod.Runner, "run", staticmethod(mock_runner_run))

        with pytest.raises(ModelBehaviorError, match="always fail"):
            await research_mod._run_with_retry(
                mock_agent, "テスト", SimpleSearchOutput,
                agent_name="Test", max_retries=2, verbose=False,
            )

    @pytest.mark.asyncio
    async def test_non_model_behavior_error_not_retried(self, mock_agent, monkeypatch):
        """ModelBehaviorError以外の例外はリトライしない"""
        from workflows import research as research_mod

        async def mock_runner_run(agent, prompt):
            raise ValueError("ネットワークエラー等")

        monkeypatch.setattr(research_mod.Runner, "run", staticmethod(mock_runner_run))

        with pytest.raises(ValueError, match="ネットワークエラー等"):
            await research_mod._run_with_retry(
                mock_agent, "テスト", SimpleSearchOutput,
                agent_name="Test", max_retries=2, verbose=False,
            )

    @pytest.mark.asyncio
    async def test_max_retries_zero(self, mock_agent, monkeypatch):
        """max_retries=0 の場合リトライしない"""
        from workflows import research as research_mod

        call_count = 0

        async def mock_runner_run(agent, prompt):
            nonlocal call_count
            call_count += 1
            raise ModelBehaviorError("fail")

        monkeypatch.setattr(research_mod.Runner, "run", staticmethod(mock_runner_run))

        with pytest.raises(ModelBehaviorError):
            await research_mod._run_with_retry(
                mock_agent, "テスト", SimpleSearchOutput,
                agent_name="Test", max_retries=0, verbose=False,
            )
        assert call_count == 1  # 初回の1回のみ


# ============================================================
# 12. エッジケース: 大量データでのバリデーション
# ============================================================
class TestLargeDataValidation:
    """出力量が多い場合のバリデーション安定性テスト。"""

    def test_max_findings_15(self):
        """findingsが上限の15件"""
        data = {
            "theme": "大量テスト",
            "findings": [
                {"content": f"発見事項{i}: " + "詳細な内容。" * 20, "source": f"ソース{i}"}
                for i in range(15)
            ],
            "evidence": [
                {"title": f"根拠{i}", "url": f"https://example.com/{i}", "summary": f"概要{i}"}
                for i in range(8)
            ],
            "summary": "総括" * 100,
            "research_depth_analysis": "分析" * 50,
            "interconnections": [f"関連{i}" for i in range(10)],
        }
        result = validate_json(ResearchResultOutput, data)
        assert len(result.findings) == 15
        assert len(result.evidence) == 8

    def test_max_evidence_8(self):
        """evidenceが上限の8件"""
        data = {
            "theme": "テスト",
            "evidence": [
                {"title": f"根拠{i}", "url": f"https://example{i}.com", "summary": "概要" * 30}
                for i in range(8)
            ],
        }
        result = validate_json(ResearchResultOutput, data)
        assert len(result.evidence) == 8

    def test_very_long_summary(self):
        """非常に長いsummaryでもバリデーション通過"""
        data = {
            "theme": "テスト",
            "summary": "A" * 5000,  # 5000文字のsummary
        }
        result = validate_json(ResearchResultOutput, data)
        assert len(result.summary) == 5000

    def test_deeply_nested_plan_in_evaluation(self):
        """EvaluationOutput.refined_plan.search_keywords が大量"""
        data = {
            "iteration_number": 2,
            "should_refine": True,
            "refined_plan": {
                "objective": "修正目的",
                "research_areas": [f"領域{i}" for i in range(8)],
                "search_keywords": {
                    f"領域{i}": [f"kw{j}" for j in range(5)]
                    for i in range(8)
                },
                "priority_order": [f"領域{i}" for i in range(8)],
                "research_strategy": "改善戦略",
                "expected_outcomes": [f"成果{i}" for i in range(5)],
            },
        }
        result = validate_json(EvaluationOutput, data)
        assert len(result.refined_plan.research_areas) == 8
        assert len(result.refined_plan.search_keywords) == 8

    def test_fact_check_large_output(self):
        """FactCheckResultOutput に大量のverified/removedが含まれる"""
        data = {
            "verified_evidences": [
                {"title": f"V{i}", "url": f"http://v{i}.com", "original_url": f"http://o{i}.com",
                 "summary": f"S{i}", "status": "verified", "verification_note": f"OK{i}"}
                for i in range(10)
            ],
            "removed_evidences": [
                {"title": f"R{i}", "url": f"http://r{i}.com", "reason": f"理由{i}"}
                for i in range(5)
            ],
            "verified_findings": [
                {"content": f"VF{i}", "source": f"S{i}", "source_url": f"http://sf{i}.com",
                 "confidence": "high"}
                for i in range(15)
            ],
            "removed_findings": [
                {"content": f"RF{i}", "reason": f"R{i}"}
                for i in range(3)
            ],
            "verification_summary": "検証完了",
            "total_verified": 15,
            "total_removed": 3,
            "reliability_score": 0.83,
        }
        result = validate_json(FactCheckResultOutput, data)
        assert result.total_verified == 15
        assert len(result.verified_findings) == 15
        assert len(result.removed_evidences) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
