"""研究エージェントのスキーマ定義.

設計方針:
  LLMが大量のJSON出力を生成する際、トークン制限や出力不安定性により
  一部フィールドを省略することがある。そのため全フィールドにデフォルト値を
  設定し、バリデーションエラーを防止する。
  デフォルト値はあくまでフォールバックであり、LLMには全フィールド出力を促す。
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class Finding(BaseModel):
    """検索結果の個別発見事項。"""
    
    content: str = Field(default="", description="発見事項の内容")
    source: str = Field(default="", description="出所・根拠情報")


class Evidence(BaseModel):
    """根拠情報。"""
    
    title: str = Field(default="", description="ページタイトル/記事タイトル")
    url: str = Field(default="", description="URL")
    summary: str = Field(default="", description="内容概要")


class VerifiedEvidence(BaseModel):
    """検証済み根拠情報。"""
    
    title: str = Field(default="", description="ページタイトル/記事タイトル")
    url: str = Field(default="", description="検証済みURL（元URLまたは代替URL）")
    original_url: str = Field(default="", description="元のURL")
    summary: str = Field(default="", description="内容概要")
    status: str = Field(
        default="unverified",
        description="検証ステータス: verified（実在確認）, replaced（代替URL発見）, unverified（関連情報は存在するがURL未確認）"
    )
    verification_note: str = Field(
        default="",
        description="検証に関する補足メモ（どのように検証したか、何を代替URLとしたか等）"
    )


class RemovedEvidence(BaseModel):
    """除外された根拠情報。"""
    
    title: str = Field(default="", description="元のタイトル")
    original_url: str = Field(default="", description="元のURL（架空と判定）")
    reason: str = Field(default="", description="除外理由")


class VerifiedFinding(BaseModel):
    """検証済み発見事項。"""
    
    content: str = Field(default="", description="発見事項の内容")
    source: str = Field(default="", description="出所・根拠情報（検証済み）")
    source_url: str = Field(default="", description="検証済みの出典URL")
    confidence: str = Field(
        default="low",
        description="信頼度: high（URLと内容の一致を確認）, medium（関連URLを発見）, low（Web検索で関連情報のみ）"
    )


class RemovedFinding(BaseModel):
    """除外された発見事項。"""
    
    content: str = Field(default="", description="元の発見事項の内容")
    source: str = Field(default="", description="元の出所情報")
    reason: str = Field(default="", description="除外理由")


class FactCheckResultOutput(BaseModel):
    """ファクトチェック結果スキーマ。"""
    
    verified_evidences: List[VerifiedEvidence] = Field(
        default_factory=list,
        description="検証済みの根拠情報（URL実在確認済み or 代替URL発見）"
    )
    removed_evidences: List[RemovedEvidence] = Field(
        default_factory=list,
        description="除外された根拠情報（架空URL、裏付け不能）"
    )
    verified_findings: List[VerifiedFinding] = Field(
        default_factory=list,
        description="検証済みの発見事項（信頼できる出典付き）"
    )
    removed_findings: List[RemovedFinding] = Field(
        default_factory=list,
        description="除外された発見事項（根拠が裏付け不能）"
    )
    verification_summary: str = Field(
        default="",
        description="検証結果の要約（検証済み件数、除外件数、全体の信頼性評価）"
    )
    total_verified: int = Field(
        default=0,
        description="検証済み発見事項の総数"
    )
    total_removed: int = Field(
        default=0,
        description="除外された発見事項の総数"
    )
    reliability_score: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="全体の信頼性スコア（検証済み / 全件数）"
    )


class SearchPlanOutput(BaseModel):
    """調査計画スキーマ."""
    
    objective: str = Field(
        default="",
        description="調査の目的と期待される成果を明確に記述"
    )
    research_areas: List[str] = Field(
        default_factory=list,
        description="調査領域の一覧（5-8個）"
    )
    search_keywords: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="領域別の検索キーワード（領域ごとに3-5個のキーワード）"
    )
    priority_order: List[str] = Field(
        default_factory=list,
        description="調査領域の優先順位（search_areas と同じ順序で）"
    )
    research_strategy: str = Field(
        default="",
        description="調査戦略の詳細（段階的アプローチ、相互依存性、検証方法など）"
    )
    expected_outcomes: List[str] = Field(
        default_factory=list,
        description="期待される成果物（3-5個の具体的な成果）"
    )


class SimpleSearchOutput(BaseModel):
    """ワンショット検索結果スキーマ（フェーズA）."""
    
    theme: str = Field(default="", description="調査テーマ")
    findings: List[Finding] = Field(
        default_factory=list,
        description="主な発見事項（10-20個の事実・情報と出所）"
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="根拠情報（タイトル、URL、概要を含む）"
    )
    summary: str = Field(
        default="（総括はfindingsの内容を参照してください）",
        description="調査結果の総括（300-500字）"
    )
    coverage_areas: List[str] = Field(
        default_factory=list,
        description="カバーされた領域の一覧"
    )


class ResearchResultOutput(BaseModel):
    """詳細研究結果スキーマ（フェーズB）."""
    
    theme: str = Field(default="", description="調査テーマ")
    plan_used: Optional[SearchPlanOutput] = Field(
        default=None,
        description="この結果を生成した調査計画"
    )
    findings: List[Finding] = Field(
        default_factory=list,
        description="発見事項（体系的、詳細度の高い、20-40個）"
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="根拠情報（URL、引用、出所を含む）"
    )
    research_depth_analysis: str = Field(
        default="",
        description="調査の深さ分析（各領域での掘り下げ程度）"
    )
    interconnections: List[str] = Field(
        default_factory=list,
        description="異なる領域間での関連性・相互作用"
    )
    summary: str = Field(
        default="（総括はfindingsの内容を参照してください）",
        description="詳細調査結果の総括（500-1000字）"
    )
    iteration_number: int = Field(
        default=1,
        ge=1,
        description="このフェーズで何回目の反復か"
    )


class EvaluationOutput(BaseModel):
    """評価と修正計画スキーマ（6軸評価）."""
    
    iteration_number: int = Field(
        default=1,
        ge=1,
        description="評価対象の反復番号"
    )
    
    # 6つの評価軸
    objective_achievement_score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="1. 目的達成度：調査目的の達成度、重要な問いへの回答充実度（0-10）"
    )
    coverage_score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="2. 網羅性：重要な観点のカバレッジ、ヌケモレの少なさ、多角的視点（0-10）"
    )
    depth_insight_score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="3. 深さ・洞察力：分析の深さ、独自の洞察、因果関係の考察、批判的思考（0-10）"
    )
    actionability_score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="4. 実用性：意思決定への活用可能性、実行可能な示唆、ビジネス価値（0-10）"
    )
    credibility_score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="5. 信頼性：情報源の質、事実ベース、検証可能性、複数ソースでの裏付け（0-10）"
    )
    quantitative_score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="6. 定量性：数値データの充実度、統計情報、具体的事例、比較データ（0-10）"
    )
    
    # 観点のヌケモレ（詳細情報）
    coverage_gaps: List[str] = Field(
        default_factory=list,
        description="観点のヌケモレ（本質的に不足している重要領域・観点の詳細）"
    )
    
    # 総合評価
    overall_quality_score: int = Field(
        default=0,
        ge=0,
        le=60,
        description="総合スコア（6軸の合計、最大60点、合格ライン48点=80%）"
    )
    should_refine: bool = Field(
        default=True,
        description="さらなる調査が必要か（総合スコア < 48点 または いずれかの軸が6点未満の場合 True）"
    )
    refinement_strategy: Optional[str] = Field(
        default=None,
        description="改善戦略（refinement が必要な場合のみ記入）"
    )
    refined_plan: Optional[SearchPlanOutput] = Field(
        default=None,
        description="修正された調査計画（refinement が必要な場合のみ）"
    )
    expert_observations: str = Field(
        default="",
        description="当該分野の専門家としての観察・コメント"
    )


class ComparisonReportOutput(BaseModel):
    """簡易検索 vs 詳細検索の比較スキーマ."""
    
    theme: str = Field(default="", description="調査テーマ")
    
    # スコアリング
    # 6軸スコア（簡易検索）
    simple_search_objective_score: int = Field(
        default=0, ge=0, le=10,
        description="簡易検索：目的達成度（0-10）"
    )
    simple_search_coverage_score: int = Field(
        default=0, ge=0, le=10,
        description="簡易検索：網羅性（0-10）"
    )
    simple_search_depth_insight_score: int = Field(
        default=0, ge=0, le=10,
        description="簡易検索：深さ・洞察力（0-10）"
    )
    simple_search_actionability_score: int = Field(
        default=0, ge=0, le=10,
        description="簡易検索：実用性（0-10）"
    )
    simple_search_credibility_score: int = Field(
        default=0, ge=0, le=10,
        description="簡易検索：信頼性（0-10）"
    )
    simple_search_quantitative_score: int = Field(
        default=0, ge=0, le=10,
        description="簡易検索：定量性（0-10）"
    )
    
    # 6軸スコア（エージェント検索）
    agentic_search_objective_score: int = Field(
        default=0, ge=0, le=10,
        description="エージェント検索：目的達成度（0-10）"
    )
    agentic_search_coverage_score: int = Field(
        default=0, ge=0, le=10,
        description="エージェント検索：網羅性（0-10）"
    )
    agentic_search_depth_insight_score: int = Field(
        default=0, ge=0, le=10,
        description="エージェント検索：深さ・洞察力（0-10）"
    )
    agentic_search_actionability_score: int = Field(
        default=0, ge=0, le=10,
        description="エージェント検索：実用性（0-10）"
    )
    agentic_search_credibility_score: int = Field(
        default=0, ge=0, le=10,
        description="エージェント検索：信頼性（0-10）"
    )
    agentic_search_quantitative_score: int = Field(
        default=0, ge=0, le=10,
        description="エージェント検索：定量性（0-10）"
    )
    
    # 6軸の改善率
    objective_improvement_rate: float = Field(
        default=0.0, ge=-100.0, le=1000.0,
        description="目的達成度の改善率（%）"
    )
    coverage_improvement_rate: float = Field(
        default=0.0, ge=-100.0, le=1000.0,
        description="網羅性の改善率（%）"
    )
    depth_insight_improvement_rate: float = Field(
        default=0.0, ge=-100.0, le=1000.0,
        description="深さ・洞察力の改善率（%）"
    )
    actionability_improvement_rate: float = Field(
        default=0.0, ge=-100.0, le=1000.0,
        description="実用性の改善率（%）"
    )
    credibility_improvement_rate: float = Field(
        default=0.0, ge=-100.0, le=1000.0,
        description="信頼性の改善率（%）"
    )
    quantitative_improvement_rate: float = Field(
        default=0.0, ge=-100.0, le=1000.0,
        description="定量性の改善率（%）"
    )
    
    # 総合評価
    simple_search_total_score: float = Field(
        default=0.0,
        ge=0.0,
        le=60.0,
        description="簡易検索：総合スコア（6軸合計、0-60点、合格ライン48点=80%）"
    )
    agentic_search_total_score: float = Field(
        default=0.0,
        ge=0.0,
        le=60.0,
        description="エージェント検索：総合スコア（6軸合計、0-60点、合格ライン48点=80%）"
    )
    
    # 定性的分析
    key_differences: List[str] = Field(
        default_factory=list,
        description="簡易検索とエージェント検索の主な相違点"
    )
    
    simple_search_strengths: List[str] = Field(
        default_factory=list,
        description="簡易検索の強み"
    )
    simple_search_weaknesses: List[str] = Field(
        default_factory=list,
        description="簡易検索の弱み"
    )
    
    agentic_search_strengths: List[str] = Field(
        default_factory=list,
        description="エージェント検索の強み"
    )
    agentic_search_weaknesses: List[str] = Field(
        default_factory=list,
        description="エージェント検索の弱み"
    )
    
    recommendation: str = Field(
        default="",
        description="調査品質向上のための推奨結果・活用シーン"
    )
    
    cost_effectiveness_analysis: str = Field(
        default="",
        description="費用対効果分析（実行時間、API呼び出しコスト等を踏まえた評価）"
    )
