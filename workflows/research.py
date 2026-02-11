"""リサーチエージェントのメインワークフロー."""
from typing import Tuple, Optional
from agents import Runner
from agents.exceptions import ModelBehaviorError
import json


# LLM出力がトークン制限で切り詰められた場合のリトライ上限
MAX_PARSE_RETRIES = 2

from agent_definitions import (
    create_simple_searcher_agent,
    create_search_planner_agent,
    create_researcher_agent,
    create_evaluator_agent,
    create_comparison_analyzer_agent,
    create_fact_checker_agent,
)
from models.schemas import (
    SimpleSearchOutput,
    SearchPlanOutput,
    ResearchResultOutput,
    EvaluationOutput,
    ComparisonReportOutput,
    FactCheckResultOutput,
    Finding,
    Evidence,
)


async def _run_with_retry(
    agent,
    prompt: str,
    output_type,
    agent_name: str = "Agent",
    max_retries: int = MAX_PARSE_RETRIES,
    verbose: bool = True,
):
    """
    Runner.runを実行し、ModelBehaviorError発生時にリトライする。
    
    LLMがトークン制限で出力を切り詰めると、JSONが途中で途切れて
    ModelBehaviorError (Invalid JSON) が発生する。
    リトライ時は出力量を減らすよう追加指示を付加する。
    
    Args:
        agent: 実行するAgent
        prompt: 入力プロンプト
        output_type: 出力スキーマクラス
        agent_name: ログ表示用エージェント名
        max_retries: 最大リトライ回数
        verbose: ログ表示
    
    Returns:
        パース済みの出力オブジェクト
    
    Raises:
        ModelBehaviorError: リトライ回数を超えても失敗した場合
    """
    last_error = None
    
    for attempt in range(1 + max_retries):
        try:
            if attempt == 0:
                current_prompt = prompt
            else:
                # リトライ時: 出力量を削減する追加指示
                current_prompt = prompt + f"""

【⚠️ リトライ {attempt}/{max_retries} - 出力量削減指示】
前回の出力がトークン制限で切り詰められ、JSONが壊れました。
以下を厳守し、必ず完全なJSONを出力してください:
- findings は最大 8 件に制限する（重要なものだけ厳選）
- evidence は最大 5 件に制限する（最も信頼性の高いもの）
- summary は 200 字以内にする
- research_depth_analysis, interconnections は簡潔に（各 100 字以内）
- plan_used は objective のみ記載し他は省略可能
- 完全なJSON構造（すべての括弧が閉じている）を優先すること
"""
            
            result = await Runner.run(agent, current_prompt)
            output = result.final_output_as(output_type)
            
            if attempt > 0 and verbose:
                print(f"   ✅ リトライ{attempt}回目で{agent_name}の出力パースに成功")
            
            return output
            
        except ModelBehaviorError as e:
            last_error = e
            if verbose:
                if attempt < max_retries:
                    print(f"   ⚠️  {agent_name}の出力JSONが不正（トークン切り詰め）。リトライ {attempt + 1}/{max_retries}...")
                else:
                    print(f"   ❌ {agent_name}の出力JSONが{max_retries + 1}回連続で不正。")
    
    raise last_error


async def run_simple_research(
    theme: str,
    verbose: bool = True,
) -> SimpleSearchOutput:
    """
    ワンショット検索を実行する（フェーズA）.
    
    与えられたテーマについて、Web検索を用いて1回の包括的な検索を実行し、
    主要な発見事項と根拠情報を返す。
    
    Args:
        theme: 調査テーマ
        verbose: 進捗を表示するか
    
    Returns:
        SimpleSearchOutput: ワンショット検索結果
    """
    if verbose:
        print("=" * 80)
        print("🔍 ワンショット検索（フェーズA）を開始します")
        print("=" * 80)
        print(f"テーマ: {theme}")
        print()
    
    # 簡易検索エージェントを作成
    searcher = create_simple_searcher_agent()
    
    # プロンプトを構成
    search_prompt = f"""
以下のテーマについて、包括的で多面的なワンショット検索を実行してください。

テーマ:
{theme}

要件:
- 複数の異なる視点から検索を実行する
- 市場、技術、ビジネス、事例など、多角的な領域から情報を収集する
- 10-20個の主要な発見事項を抽出する
- すべての発見事項に根拠情報（URL、出所）を記録する
- 300-500字の総括を作成する
"""
    
    # ワンショット検索を実行
    if verbose:
        print("🔄 Web検索を実行中...")
    
    simple_output = await _run_with_retry(
        searcher, search_prompt, SimpleSearchOutput,
        agent_name="SimpleSearcher", verbose=verbose,
    )
    
    if verbose:
        print("✅ ワンショット検索が完了しました")
        print(f"   発見事項数: {len(simple_output.findings)}")
        print(f"   根拠情報数: {len(simple_output.evidence)}")
        print()
    
    return simple_output


async def run_agentic_research(
    theme: str,
    max_iterations: int = 5,
    verbose: bool = True,
) -> Tuple[SearchPlanOutput, ResearchResultOutput, list]:
    """
    エージェンティック検索を実行する（フェーズB）.
    
    与えられたテーマについて、以下のプロセスを実行：
    1. 初期調査計画立案
    2. ユーザーへの計画確認・修正受付
    3. 調査実行 → 評価 → 修正のサイクルを max_iterations 回実行
    
    Args:
        theme: 調査テーマ
        max_iterations: 最大反復回数（デフォルト: 5）
        verbose: 進捗を表示するか
    
    Returns:
        Tuple containing:
            - SearchPlanOutput: 最終的な調査計画
            - ResearchResultOutput: 最終的な調査結果（FC通過データのみ）
            - List of EvaluationOutput: 各反復での評価結果
            - List of dict: ファクトチェック履歴
            - List of dict: 各反復のresearcher生結果（URL未変更、検証用保存）
    """
    if verbose:
        print("=" * 80)
        print("🧠 エージェンティック検索（フェーズB）を開始します")
        print("=" * 80)
        print(f"テーマ: {theme}")
        print(f"最大反復回数: {max_iterations}")
        print()
    
    # エージェントを作成
    planner = create_search_planner_agent()
    researcher = create_researcher_agent()
    evaluator = create_evaluator_agent()
    
    # 反復1: 初期調査計画を立案
    if verbose:
        print("─" * 80)
        print("📋 反復1: 初期調査計画を立案")
        print("─" * 80)
    
    planner_prompt = f"""
以下のテーマについて、包括的で体系的な調査計画を立案してください。

テーマ:
{theme}

要件:
- テーマを5-8個の主要調査領域に分解する
- 各領域について3-5個の検索キーワードを定義する
- 調査領域の優先順位を明確にする
- 段階的な調査戦略を記述する
- 期待される成果を3-5個定義する
"""
    
    current_plan = await _run_with_retry(
        planner, planner_prompt, SearchPlanOutput,
        agent_name="Planner", verbose=verbose,
    )
    
    if verbose:
        print("✅ 調査計画が立案されました")
        print(f"   調査領域: {len(current_plan.research_areas)}")
        print(f"   優先領域: {', '.join(current_plan.priority_order[:3])}...")
        print()
        print("=" * 80)
        print("📋 調査計画の確認")
        print("=" * 80)
        print(f"\n【目的】")
        print(f"{current_plan.objective}\n")
        print(f"【調査領域】（{len(current_plan.research_areas)}個）")
        for i, area in enumerate(current_plan.research_areas, 1):
            keywords = current_plan.search_keywords.get(area, [])
            print(f"  {i}. {area}")
            print(f"     キーワード: {', '.join(keywords)}")
        print(f"\n【優先順位】")
        for i, area in enumerate(current_plan.priority_order, 1):
            print(f"  {i}. {area}")
        print(f"\n【調査戦略】")
        print(f"{current_plan.research_strategy}\n")
        print(f"【期待される成果】")
        for i, outcome in enumerate(current_plan.expected_outcomes, 1):
            print(f"  {i}. {outcome}")
        print("\n" + "=" * 80)
        print("この計画で調査を開始します。")
        print("調査計画を修正したい場合は、追加の指示を入力してください。")
        print("そのまま続行する場合は、Enterキーを押してください。")
        print("=" * 80)
    
    # ユーザーからの入力を受け付ける
    user_input = input("\n➤ ").strip()
    
    # ユーザーが追加指示を入力した場合、計画を修正
    if user_input:
        if verbose:
            print("\n" + "─" * 80)
            print("🔄 調査計画を修正中...")
            print("─" * 80)
        
        refinement_prompt = f"""
以下の調査計画について、ユーザーからの追加指示を反映して計画を修正してください。

現在の調査計画:
- 目的: {current_plan.objective}
- 調査領域: {', '.join(current_plan.research_areas)}
- 優先順位: {', '.join(current_plan.priority_order)}

ユーザーからの追加指示:
{user_input}

要件:
- ユーザーの指示を適切に反映する
- 調査の質と網羅性を維持または向上させる
- 実行可能で具体的な計画を立案する
"""
        
        current_plan = await _run_with_retry(
            planner, refinement_prompt, SearchPlanOutput,
            agent_name="Planner", verbose=verbose,
        )
        
        if verbose:
            print("✅ 調査計画が修正されました")
            print(f"   調査領域: {len(current_plan.research_areas)}")
            print(f"   優先領域: {', '.join(current_plan.priority_order[:3])}...")
            print()
    
    # 反復2以降: 調査実行 → 評価 → 修正のサイクル
    evaluations = []
    current_result = None
    # 各反復のresearcher生結果を保存（URLを変更せず後から検証可能にする）
    raw_results: list[dict] = []
    # FC通過した反復のfindingsとevidence（レポートに使用する）
    accepted_findings: list[Finding] = []
    accepted_evidence: list[Evidence] = []
    # ファクトチェック履歴（反復をまたいで引き継ぐ）
    fact_check_history: list[dict] = []
    
    for iteration in range(1, max_iterations + 1):
        if verbose:
            print("─" * 80)
            print(f"🔬 反復{iteration}: 調査実行")
            print("─" * 80)
        
        # ── 前回のFC通過結果と除外パターンをresearcherに渡す ──
        previous_context = ""
        if accepted_findings:
            previous_context += f"""
【前回までのFC通過発見事項（{len(accepted_findings)}件）】
以下は前回までにファクトチェックを通過した発見事項です。これらと重複しない新しい情報を探してください。
{chr(10).join(f'  - {f.content[:80]}...' for f in accepted_findings[:10])}
"""
        if accepted_evidence:
            previous_context += f"""
【前回までのFC通過根拠情報（{len(accepted_evidence)}件）】
以下のURLはファクトチェック通過済みです。新しいURLを探すこと。
{chr(10).join(f'  - {e.url} ({e.title})' for e in accepted_evidence[:8])}
"""
        if fact_check_history:
            latest_fc = fact_check_history[-1]
            previous_context += f"""
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
架空のURLを生成した場合、ファクトチェックで再び除外されます。
WebSearchToolで実際に取得したURLのみを使用してください。
"""
        
        # 評価者からの改善指示
        improvement_instruction = ""
        if evaluations:
            last_eval = evaluations[-1]
            if last_eval.coverage_gaps:
                improvement_instruction += f"""
【評価者からの改善要求】
- 前回の総合スコア: {last_eval.overall_quality_score}/60
- 信頼性スコア: {last_eval.credibility_score}/10
- 不足している観点: {', '.join(last_eval.coverage_gaps[:5])}
- 改善戦略: {last_eval.refinement_strategy or '特になし'}
上記のヌケモレを重点的に調査してください。
"""
        
        # 調査実行
        researcher_prompt = f"""
以下の調査計画に従って、詳細で体系的な調査を実行してください。

テーマ: {theme}

現在の反復番号: {iteration}

調査計画:
- 目的: {current_plan.objective}
- 調査領域: {', '.join(current_plan.research_areas)}
- 検索キーワード: {json.dumps(current_plan.search_keywords, ensure_ascii=False)}
- 調査戦略: {current_plan.research_strategy}
{previous_context}{improvement_instruction}
要件:
- 計画に従って、体系的に検索を実行する
- 10-15個の詳細な発見事項を抽出する（品質重視・数より質）
- 各発見事項に根拠情報（URL、出所）を記録する
- 領域間の相互関連性を特定する
- 調査の深さと具体性を最大化する
- 200-400字の総括を作成する
- 出力には必ずtheme、plan_used、iteration_numberを含めること

【最重要】出典URLに関する厳格なルール:
- evidenceのURLは、WebSearchToolで実際に取得した検索結果のURLのみを使用すること
- URLを自分で推測・生成・捏造してはならない
- Web検索で見つからなかった情報源のURLを作り出してはならない
- 「arxiv.org/abs/2501.12345」のような整った番号のURLを捏造しない
- URLが見つからない場合は、findingsのsourceに「Web検索で関連情報を確認」等と記載し、
  evidenceには実際にアクセスできたURLのみを含める
- 架空の組織名、学会名、ジャーナル名を作り出さない
"""
        
        current_result = await _run_with_retry(
            researcher, researcher_prompt, ResearchResultOutput,
            agent_name="Researcher", verbose=verbose,
        )
        
        # ── researcher の生結果を保存（URLを一切変更しない） ──
        raw_results.append({
            'iteration': iteration,
            'findings': [{'content': f.content, 'source': f.source} for f in current_result.findings],
            'evidence': [{'title': e.title, 'url': e.url, 'summary': e.summary} for e in current_result.evidence],
            'summary': current_result.summary,
        })
        
        if verbose:
            print(f"✅ 調査が完了しました（反復{iteration}）")
            print(f"   発見事項数: {len(current_result.findings)}")
            print(f"   根拠情報数: {len(current_result.evidence)}")
            print()
        
        # ファクトチェック: URLの実在性と内容の関連性を検証
        # evidence/findingsが両方空の場合はスキップ
        has_evidence = bool(current_result.evidence)
        has_findings = bool(current_result.findings)
        
        if not has_evidence and not has_findings:
            if verbose:
                print("⚠️  evidence・findingsが共に空のためファクトチェックをスキップ")
            fact_check = None
        else:
            if verbose:
                print("─" * 80)
                print(f"🔍 反復{iteration}: 出典URLのファクトチェック")
                print("─" * 80)
            
            fact_checker = create_fact_checker_agent()
            
            evidence_section = "（evidenceなし）" if not has_evidence else chr(10).join(
                f'- タイトル: {e.title}, URL: {e.url}, 概要: {e.summary}' for e in current_result.evidence
            )
            findings_section = "（findingsなし）" if not has_findings else chr(10).join(
                f'- 内容: {f.content[:100]}..., 出所: {f.source}' for f in current_result.findings
            )
            
            fact_check_prompt = f"""
以下の調査結果に含まれる出典URLを1件ずつ検証してください。

各URLについて:
1. Web検索ツールでURLに直接アクセスを試みる
2. タイトルや内容のキーワードでWeb検索して実在を確認
3. 無効なURLの場合、同じ内容の代替URLを探す

【検証対象: 根拠情報（evidence）】
{evidence_section}

【検証対象: 発見事項（findings）】
{findings_section}

検証の際の注意:
- 必ずWeb検索ツールを使って各URLの実在性を確認すること
- arxiv.org/abs/XXXX.XXXXX のような番号が整いすぎたURLは特に注意
- 実在しないドメインやパスを見逃さないこと
- URLが無効でも、内容自体がWeb検索で裏付けられる場合は代替URLを提示
- 完全に裏付けが取れない情報はfabricatedとして除外
"""
            
            fact_check = await _run_with_retry(
                fact_checker, fact_check_prompt, FactCheckResultOutput,
                agent_name="FactChecker", verbose=verbose,
            )
        
        if fact_check is not None:
            if verbose:
                print(f"✅ ファクトチェックが完了しました")
                print(f"   検証済み発見事項: {fact_check.total_verified}")
                print(f"   除外された発見事項: {fact_check.total_removed}")
                print(f"   信頼性スコア: {fact_check.reliability_score:.1%}")
                print()
            
            # ── ファクトチェック履歴を記録 ──
            removed_reasons = []
            for rf in (fact_check.removed_findings or []):
                removed_reasons.append(f"{rf.content[:50]}... → {rf.reason}")
            for re_ in (fact_check.removed_evidences or []):
                removed_reasons.append(f"URL: {re_.original_url} → {re_.reason}")
            
            fact_check_history.append({
                'iteration': iteration,
                'verified': fact_check.total_verified,
                'removed': fact_check.total_removed,
                'reliability': fact_check.reliability_score,
                'removed_reasons': removed_reasons,
                'summary': fact_check.verification_summary,
            })
            
            # ── FC結果に基づくデータの扱い ──
            # URLは変更しない。FC通過分のみresearcherのオリジナルデータから抽出して蓄積。
            # FC失敗データはレポートに使用しない（スコアゼロ扱い）。
            
            # verified_findingsの content を使って、元のresearcher findingsから該当分を特定
            verified_contents = {vf.content[:80] for vf in fact_check.verified_findings}
            verified_urls = set()
            for ve in fact_check.verified_evidences:
                # verified_evidences にはoriginal_urlがある場合はそちら、なければurlを使う
                original = ve.original_url if ve.original_url else ve.url
                if original:
                    verified_urls.add(original)
                if ve.url:
                    verified_urls.add(ve.url)
            
            # researcherのオリジナルfindingsからFC通過分を抽出（URLは変更しない）
            iteration_accepted_findings = []
            for f in current_result.findings:
                if f.content[:80] in verified_contents:
                    iteration_accepted_findings.append(f)
            
            # researcherのオリジナルevidenceからFC通過分を抽出（URLは変更しない）
            iteration_accepted_evidence = []
            for e in current_result.evidence:
                if e.url in verified_urls:
                    iteration_accepted_evidence.append(e)
            
            # accepted リストに蓄積（重複排除）
            existing_contents = {f.content[:80] for f in accepted_findings}
            for f in iteration_accepted_findings:
                if f.content[:80] not in existing_contents:
                    accepted_findings.append(f)
                    existing_contents.add(f.content[:80])
            
            existing_urls = {e.url for e in accepted_evidence}
            for e in iteration_accepted_evidence:
                if e.url and e.url not in existing_urls:
                    accepted_evidence.append(e)
                    existing_urls.add(e.url)
            
            if verbose:
                print(f"   → この反復でFC通過した発見事項: {len(iteration_accepted_findings)}")
                print(f"   → この反復でFC通過した根拠情報: {len(iteration_accepted_evidence)}")
                print(f"   → 蓄積されたFC通過発見事項数: {len(accepted_findings)}")
                print(f"   → 蓄積されたFC通過根拠情報数: {len(accepted_evidence)}")
                if fact_check.removed_findings:
                    print(f"   ⚠️  除外された発見事項:")
                    for rf in fact_check.removed_findings[:5]:
                        print(f"      - {rf.content[:60]}... ({rf.reason})")
                print()
        else:
            # ファクトチェックをスキップした場合も履歴に記録
            fact_check_history.append({
                'iteration': iteration,
                'verified': 0,
                'removed': 0,
                'reliability': 0.0,
                'removed_reasons': [],
                'summary': 'ファクトチェックをスキップ（evidence/findingsが空）',
            })
        
        # 評価
        if verbose:
            print("─" * 80)
            print(f"⭐ 反復{iteration}: 評価と修正判定")
            print("─" * 80)
        
        # 過去の評価結果を要約（反復改善の参考情報）
        past_eval_summary = ""
        if evaluations:
            past_eval_summary = "\n過去の評価履歴:\n"
            for past_eval in evaluations:
                past_eval_summary += f"  反復{past_eval.iteration_number}: 総合{past_eval.overall_quality_score}/60 "
                past_eval_summary += f"(目的:{past_eval.objective_achievement_score} 網羅:{past_eval.coverage_score} "
                past_eval_summary += f"深さ:{past_eval.depth_insight_score} 実用:{past_eval.actionability_score} "
                past_eval_summary += f"信頼:{past_eval.credibility_score} 定量:{past_eval.quantitative_score})\n"
                if past_eval.coverage_gaps:
                    past_eval_summary += f"  → 前回のヌケモレ: {', '.join(past_eval.coverage_gaps[:3])}\n"
        
        # ── ファクトチェック結果を評価者に渡す ──
        fact_check_section = ""
        if fact_check_history:
            latest_fc = fact_check_history[-1]
            fact_check_section = f"""

【⚠️ ファクトチェック結果 — 信頼性評価に必ず反映すること】
- 検証済み情報: {latest_fc['verified']}件
- 除外された情報（ハルシネーション）: {latest_fc['removed']}件
- ファクトチェッカーの信頼性スコア: {latest_fc['reliability']:.1%}
- 検証サマリー: {latest_fc['summary']}
"""
            if latest_fc['removed'] > 0:
                removal_rate = latest_fc['removed'] / max(latest_fc['verified'] + latest_fc['removed'], 1)
                fact_check_section += f"""
**ハルシネーション率: {removal_rate:.0%}**
ファクトチェックで{latest_fc['removed']}件が除外されています。
credibility_score はこの結果を厳格に反映してください:
- 除外率 > 30%: credibility_score は 5 以下にすること
- 除外率 > 20%: credibility_score は 6 以下にすること  
- 除外率 > 10%: credibility_score は 7 以下にすること
- 除外率 0%: credibility_score は 8 以上可能
"""
            # 累計のファクトチェック履歴
            if len(fact_check_history) > 1:
                fact_check_section += "\nファクトチェック履歴:\n"
                for fc in fact_check_history:
                    fact_check_section += f"  反復{fc['iteration']}: 検証{fc['verified']}件 / 除外{fc['removed']}件 (信頼性: {fc['reliability']:.1%})\n"
        
        evaluator_prompt = f"""
以下の調査結果を、当該分野の専門家の立場で**極めて厳格に**評価してください。

**重要**: 初回の調査は必ず改善余地があります。最初の2回は特に批判的に評価し、
具体的な改善案を出してください。表面的な情報収集では高得点を与えないでください。

テーマ: {theme}

調査計画の目的:
{current_plan.objective}

調査結果:
- 発見事項数: {len(current_result.findings)}
- 主要発見事項:
{chr(10).join(f'  - {f.content} (出所: {f.source})' for f in current_result.findings[:15])}
...（全{len(current_result.findings)}件）

根拠情報:
{chr(10).join(f'  - [{e.title}]({e.url}): {e.summary}' for e in current_result.evidence[:10])}
...（全{len(current_result.evidence)}件）

研究の深さ分析:
{current_result.research_depth_analysis}

領域間の相互関連性:
{chr(10).join(f'  - {i}' for i in current_result.interconnections[:5])}

総括:
{current_result.summary}
{fact_check_section}{past_eval_summary}

## 評価指示（6軸評価・厳格版）

以下の6軸で0-10のスコアをつけてください。各軸で厳格に採点すること。

1. **objective_achievement_score** (0-10): 目的達成度 - 調査目的が実質的に満たされているか
2. **coverage_score** (0-10): 網羅性 - 重要な観点がすべてカバーされているか
3. **depth_insight_score** (0-10): 深さ・洞察力 - 表面的でなく独自の洞察があるか
4. **actionability_score** (0-10): 実用性 - 意思決定に使える具体的示唆があるか
5. **credibility_score** (0-10): 信頼性 - 検証可能な根拠に基づいているか。**ファクトチェック結果を必ず反映すること**
6. **quantitative_score** (0-10): 定量性 - 数値データや具体例が十分か

**overall_quality_score** = 6軸の合計（最大60点）

## 改善判定基準（厳格版）

- **should_refine = True** にする条件（いずれか1つでも該当すれば）:
  - 反復回数が3回未満（最低3回は調査を改善する）
  - 総合スコア < 52点（87%未満）
  - いずれかの軸が7点未満
  - 2つ以上の軸が8点未満
  - objective_achievement_score < 8
  - depth_insight_score < 7
  - credibility_score < 7（ファクトチェックで除外が多い場合）

- **should_refine = False** にする条件（すべてを満たす場合のみ）:
  - 反復回数が3回以上
  - 総合スコア >= 52点
  - すべての軸が7点以上
  - objective_achievement_score >= 8
  - depth_insight_score >= 7
  - credibility_score >= 7

## 改善が必要な場合

coverage_gaps に具体的な不足観点を列挙し、
refinement_strategy に優先度付きの具体的改善計画を記述し、
refined_plan に修正された調査計画（SearchPlanOutput形式）を提供してください。

特に以下を意識した改善を求めてください：
- 前回の評価で指摘されたヌケモレの解消
- **ハルシネーション（架空URL）の削減** — 改善戦略に必ず含めること
- 数値データ・具体的事例の補強
- 因果関係の分析と独自の洞察の追加
- 実行可能な示唆・アクションの具体化

## 専門家の観察

expert_observations には、率直で批判的な評価を記述してください。
「十分」「高品質」などの抽象的な賛辞ではなく、
何が不足しているか、どう改善すべきかを具体的に指摘してください。
**ファクトチェックでの除外件数が多い場合は、その問題を必ず指摘すること。**

反復数: {iteration}/{max_iterations}
"""
        
        evaluation = await _run_with_retry(
            evaluator, evaluator_prompt, EvaluationOutput,
            agent_name="Evaluator", verbose=verbose,
        )
        evaluation.iteration_number = iteration
        evaluations.append(evaluation)
        
        if verbose:
            print(f"✅ 評価が完了しました（反復{iteration}）")
            print(f"   目的達成度: {evaluation.objective_achievement_score}/10")
            print(f"   網羅性: {evaluation.coverage_score}/10")
            print(f"   深さ・洞察力: {evaluation.depth_insight_score}/10")
            print(f"   実用性: {evaluation.actionability_score}/10")
            print(f"   信頼性: {evaluation.credibility_score}/10")
            print(f"   定量性: {evaluation.quantitative_score}/10")
            print(f"   総合スコア: {evaluation.overall_quality_score}/60")
            print(f"   さらなる調査が必要: {evaluation.should_refine}")
            print()
        
        # 修正判定
        if not evaluation.should_refine or iteration >= max_iterations:
            if verbose:
                if evaluation.should_refine and iteration >= max_iterations:
                    print(f"⚠️  最大反復回数に達しました")
                else:
                    print(f"✅ 調査品質が十分です。反復を終了します")
                print()
            break
        
        # 修正計画を適用
        if evaluation.refined_plan:
            current_plan = evaluation.refined_plan
            if verbose:
                print("─" * 80)
                print(f"🔄 反復{iteration+1}に向けて調査計画を修正")
                print("─" * 80)
                print(f"修正内容: {evaluation.refinement_strategy}")
                print()
    
    # ── 最終結果の構築: FC通過データのみ使用 ──
    # accepted_findings/evidence にはFC通過分のみが蓄積されている。
    # レポートにはこのFC通過データのみを使用する。
    if current_result and accepted_findings:
        current_result.findings = list(accepted_findings)
    elif current_result:
        # FC通過が0件の場合、findingsを空にする
        current_result.findings = []
    
    if current_result and accepted_evidence:
        current_result.evidence = list(accepted_evidence)
    elif current_result:
        current_result.evidence = []
    
    if verbose:
        print("=" * 80)
        print("✅ エージェンティック検索が完了しました")
        print(f"   総反復回数: {len(evaluations)}")
        print(f"   最終総合スコア: {evaluations[-1].overall_quality_score}/60")
        if fact_check_history:
            total_verified = sum(fc['verified'] for fc in fact_check_history)
            total_removed = sum(fc['removed'] for fc in fact_check_history)
            print(f"   ファクトチェック累計: 検証{total_verified}件 / 除外{total_removed}件")
        print(f"   最終発見事項数（FC通過のみ）: {len(current_result.findings) if current_result else 0}")
        print(f"   最終根拠情報数（FC通過のみ）: {len(current_result.evidence) if current_result else 0}")
        print("=" * 80)
        print()
    
    return current_plan, current_result, evaluations, fact_check_history, raw_results


async def run_comparison_analysis(
    theme: str,
    simple_result: SimpleSearchOutput,
    agentic_result: ResearchResultOutput,
    verbose: bool = True,
) -> ComparisonReportOutput:
    """
    簡易検索とエージェンティック検索を比較分析する（フェーズC）.
    
    Args:
        theme: 調査テーマ
        simple_result: ワンショット検索結果
        agentic_result: エージェンティック検索結果
        verbose: 進捗を表示するか
    
    Returns:
        ComparisonReportOutput: 比較分析レポート
    """
    if verbose:
        print("=" * 80)
        print("📊 比較分析（フェーズC）を実行")
        print("=" * 80)
        print(f"テーマ: {theme}")
        print()
    
    analyzer = create_comparison_analyzer_agent()
    
    comparison_prompt = f"""
以下の2つの調査結果を、多面的に比較分析してください。

テーマ: {theme}

【ワンショット検索結果】
発見事項数: {len(simple_result.findings)}
根拠情報数: {len(simple_result.evidence)}
カバー領域: {', '.join(simple_result.coverage_areas)}
総括:
{simple_result.summary}

【エージェンティック検索結果】
発見事項数: {len(agentic_result.findings)}
根拠情報数: {len(agentic_result.evidence)}
調査の深さ分析:
{agentic_result.research_depth_analysis}
総括:
{agentic_result.summary}

比較分析の要件:
1. 両結果を4つの観点（目的達成度、観点のヌケモレ、具体性・深さ、事実ベース）で定量的に評価
2. 各観点で改善率（%）を計算
3. 総合スコア（0-25）を算出
4. 両アプローチの強み・弱みを詳細に分析
5. 4観点での相違点を明確にする
6. 費用対効果を分析し、活用シーンごとの推奨を提示
"""
    
    comparison = await _run_with_retry(
        analyzer, comparison_prompt, ComparisonReportOutput,
        agent_name="ComparisonAnalyzer", verbose=verbose,
    )
    
    if verbose:
        print("✅ 比較分析が完了しました")
        print(f"   簡易検索スコア: {comparison.simple_search_total_score}/60")
        print(f"   エージェント検索スコア: {comparison.agentic_search_total_score}/60")
        print(f"   目的達成度改善率: {comparison.objective_improvement_rate:+.1f}%")
        print(f"   具体性・深さ改善率: {comparison.depth_insight_improvement_rate:+.1f}%")
        print("=" * 80)
        print()
    
    return comparison
