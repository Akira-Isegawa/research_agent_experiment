# Research Agent - ChatGPT DeepResearch型エージェントシステム

OpenAI Agent SDKを使用して、ChatGPTのDeepResearchのような、ワンショット検索とエージェンティック検索を比較分析するシステムです。

## 概要

本システムは、与えられたテーマについて以下の3つのフェーズで調査を実行し、それぞれのアプローチの特性を定量的・定性的に比較分析します。

### フェーズA: ワンショット検索
- **目的**: テーマに関する包括的なワンショット検索
- **方式**: Web検索を用いた1回の広範な検索セッション
- **出力**: 主要な発見事項と根拠情報

### フェーズB: エージェンティック検索
- **目的**: テーマについての深く、体系的な理解構築
- **方式**: 調査計画 → 実行 → 評価・修正のサイクルを最大5回反復
- **出力**: 詳細な発見事項、領域間の相互関連性、根拠情報

### フェーズC: 比較分析
- **目的**: 2つのアプローチの特性を明確化
- **観点**: 
  - 目的達成度
  - 観点のヌケモレ
  - 具体性と深さ
  - 事実ベース
- **出力**: 定量比較、改善率、推奨活用シーン

## ディレクトリ構造

```
research_agent_experiment/
├── __init__.py
├── main.py                          # メインエントリーポイント
├── agent_definitions/               # エージェント定義
│   ├── __init__.py
│   ├── simple_searcher.py           # ワンショット検索エージェント
│   ├── search_planner.py            # 調査計画立案エージェント
│   ├── researcher.py                # 調査実行エージェント（Web検索統合）
│   ├── evaluator.py                 # 調査評価・修正エージェント
│   └── comparison_analyzer.py       # 比較分析エージェント
├── models/                          # データスキーマ定義
│   ├── __init__.py
│   └── schemas.py                   # Pydanticスキーマ
├── workflows/                       # ワークフロー実装
│   ├── __init__.py
│   └── research.py                  # メインワークフロー
├── inputs/                          # 入力用テーマファイル（オプション）
├── outputs/                         # 出力ディレクトリ
├── README.md                        # このファイル
└── IMPLEMENTATION_GUIDE.md          # 実装ガイド

```

## インストール

### 依存パッケージ

```bash
pip install -r requirements.txt
```

**requirements.txt に含まれるパッケージ:**
- `openai-agents>=0.8.0` - OpenAI Agent SDK
- `pydantic>=2.0.0` - スキーマ定義
- `python-dotenv>=1.0.0` - 環境変数管理

## 使い方

### 基本的な実行
### 基本的な実行

```bash
# 簡単なテーマで実行
python main.py "調査したいテーマを入力"

# 実行フロー:
# 1. ワンショット検索を実行
# 2. 調査計画を立案・表示
# 3. ユーザー確認を待機（修正指示がある場合は入力、なければEnter）
# 4. エージェンティック検索を実行（計画→調査→評価のサイクル）
# 5. 比較分析を実行
# 6. outputs/ ディレクトリに3つのMarkdownファイルを生成
#    - simple_search_YYYYMMDD_HHMMSS.md      (ワンショット検索結果)
#    - agentic_search_YYYYMMDD_HHMMSS.md     (エージェンティック検索結果)
#    - comparison_YYYYMMDD_HHMMSS.md         (比較分析レポート)
```

### インタラクティブな調査計画の確認

エージェンティック検索の実行前に、システムが立案した調査計画が表示されます。
この時点で調査計画を確認し、必要に応じて修正指示を入力できます。

```
📋 調査計画の確認
================================================================================

【目的】
HackCampの事業内容を理解し、競合分析と継続率向上の施策を提案する

【調査領域】（8個）
  1. HackCampの事業内容とビジネスモデル
     キーワード: HackCamp 事業内容, HackCamp サービス, ...
  2. 競合企業の分析と市場ポジショニング
     ...

【優先順位】
  1. HackCampの事業内容とビジネスモデル
  2. 競合企業の分析と市場ポジショニング
  ...

【調査戦略】
まずHackCampの公式サイトから事業全体を把握し、...

【期待される成果】
  1. HackCampの提供サービスと価値提案の整理
  2. 主要競合と市場ポジショニングの概要
  ...

================================================================================
この計画で調査を開始します。
調査計画を修正したい場合は、追加の指示を入力してください。
そのまま続行する場合は、Enterキーを押してください。
================================================================================

➤ [ここで入力を待機]
```

**修正例:**
- `「競合分析では海外企業も含めてください」` と入力すると、計画が修正されます
- `「顧客事例を重点的に調査してください」` など、調査の重点を変更できます
- そのまま Enter を押すと、表示された計画で調査が開始されます

### コマンドラインオプション

```bash
python main.py <テーマ> [オプション]
```

**主要なオプション:**

| オプション | 説明 | デフォルト |
|-----------|------|---------|
| `--max-iterations` | エージェンティック検索の最大反復回数 | 5 |
| `--output-dir` | 出力ディレクトリパス | `outputs` |
| `--verbose` | 詳細な進捗出力 | 有効 |
| `--help` | ヘルプ表示 | - |

### 実行例

```bash
# 基本実行
python main.py "生成AIの企業での活用事例"

# 反復回数を3回に指定
python main.py "クラウドコンピューティングのセキュリティ" --max-iterations 3

# 出力ディレクトリを指定
python main.py "ブロックチェーンの応用事例" --output-dir my_results

# 詳細出力を有効（デフォルト）
python main.py "量子コンピュータの進展" --verbose
```

## エージェント仕様

### 1. SimpleSearcher（ワンショット検索エージェント）

**役割**: Web検索を使用して、テーマに関する包括的で多面的な情報を1回の検索セッションで収集

**出力スキーマ (`SimpleSearchOutput`)**:
```python
class SimpleSearchOutput(BaseModel):
    theme: str                          # 調査テーマ
    findings: List[str]                 # 発見事項（10-20個）
    evidence: List[Dict[str, str]]      # 根拠情報（URL、タイトル、概要）
    summary: str                        # 総括（300-500字）
    coverage_areas: List[str]           # カバーされた領域
```

### 2. SearchPlanner（調査計画立案エージェント）

**役割**: テーマについて、体系的で構造化された調査計画を立案

**出力スキーマ (`SearchPlanOutput`)**:
```python
class SearchPlanOutput(BaseModel):
    objective: str                      # 調査目的
    research_areas: List[str]           # 調査領域（5-8個）
    search_keywords: Dict[str, List[str]]  # 領域別検索キーワード
    priority_order: List[str]           # 優先順位
    research_strategy: str              # 調査戦略
    expected_outcomes: List[str]        # 期待される成果
```

### 3. Researcher（調査実行エージェント）

**役割**: 計画に基づいて、体系的かつ詳細な調査を実行（Web検索統合）

**特徴**:
- `WebSearchTool` を統合し、複数キーワード組み合わせで検索
- 初期情報に基づいて動的に追加検索を実行
- 領域間の相互関連性を特定
- すべての発見事項に根拠情報を記録

**出力スキーマ (`ResearchResultOutput`)**:
```python
class ResearchResultOutput(BaseModel):
    theme: str                          # 調査テーマ
    plan_used: SearchPlanOutput         # 使用した調査計画
    findings: List[str]                 # 詳細な発見事項（20-40個）
    evidence: List[Dict[str, str]]      # 根拠情報
    research_depth_analysis: str        # 調査の深さ分析
    interconnections: List[str]         # 領域間の相互関連性
    summary: str                        # 総括（500-1000字）
    iteration_number: int               # 反復番号
```

### 4. ResearchEvaluator（調査評価・修正エージェント）

**役割**: 極めて厳格な当該分野の専門家として、調査結果を**6つの観点**で評価し、改善が必要な場合は修正計画を提案

**6つの評価軸**:

1. **目的達成度** (0-10): 調査目的の実質的達成度、意思決定に使える洞察
2. **網羅性** (0-10): 重要な観点のカバレッジ、多角的視点、時間軸考慮
3. **深さ・洞察力** (0-10): 分析の深さ、独自の洞察、因果関係の考察、批判的思考
4. **実用性・アクション性** (0-10): 意思決定への活用可能性、実行可能な示唆
5. **信頼性・根拠性** (0-10): 情報源の質、事実ベース、複数ソース検証
6. **定量性・具体性** (0-10): 数値データ、統計情報、具体的事例、比較データ

**厳格な判定基準**: 
- **総合スコア計算**: 6軸の合計（最大60点）
- 総合スコア >= 48点 (80%) → `should_refine = False`（調査完了可能）
- 総合スコア >= 42点 (70%) → `should_refine = True`（改善余地あり）
- 総合スコア < 42点 → `should_refine = True`（改善が必要）
- **追加条件**: いずれかの軸が6点未満、または2つ以上の軸が7点未満で `should_refine = True`

**評価の心構え**:
- 安易に高得点を与えない（各軸で厳格な基準）
- 表面的な情報収集に満足しない
- ビジネスや研究での実用性を最優先
- 独自性と洞察の深さを重視
- 証拠に基づく主張を要求

**出力スキーマ (`EvaluationOutput`)**:
```python
class EvaluationOutput(BaseModel):
    iteration_number: int                  # 反復番号
    # 6軸評価
    objective_achievement_score: int       # 1. 目的達成度（0-10）
    coverage_score: int                    # 2. 網羅性（0-10）
    depth_insight_score: int               # 3. 深さ・洞察力（0-10）
    actionability_score: int               # 4. 実用性（0-10）
    credibility_score: int                 # 5. 信頼性（0-10）
    quantitative_score: int                # 6. 定量性（0-10）
    coverage_gaps: List[str]               # 観点のヌケモレ詳細
    overall_quality_score: int             # 総合スコア（0-60）
    should_refine: bool                    # さらなる調査が必要か
    refinement_strategy: Optional[str]     # 改善戦略
    refined_plan: Optional[SearchPlanOutput]  # 修正計画
    expert_observations: str               # 専門家の観察・コメント
```

### 5. ComparisonAnalyzer（比較分析エージェント）

**役割**: 簡易検索とエージェンティック検索の結果を、複数の観点で比較分析

**比較観点**:
- 6軸それぞれのスコア比較
  1. 目的達成度
  2. 網羅性
  3. 深さ・洞察力
  4. 実用性・アクション性
  5. 信頼性・根拠性
  6. 定量性・具体性
- 総合スコア（0-60、合格ライン48点=80%）
- 各軸の改善率（%）

**分析結果**:
- 定量比較（各観点での改善率）
- 定性分析（強み・弱み、相違点）
- 費用対効果分析
- 推奨活用シーン

**出力スキーマ (`ComparisonReportOutput`)**:
```python
class ComparisonReportOutput(BaseModel):
    theme: str                              # 調査テーマ
    # スコアリング（各アプローチごと）
    simple_search_objective_score: int      # 簡易検索：目的達成度
    agentic_search_objective_score: int     # エージェント検索：目的達成度
    # ... (他の観点のスコア)
    # 改善率
    objective_improvement_rate: float       # 目的達成度改善率（%）
    coverage_improvement_rate: float        # ヌケモレ削減率（%）
    depth_improvement_rate: float           # 具体性改善率（%）
    evidence_quality_improvement_rate: float  # 事実ベース改善率（%）
    # 総合評価
    simple_search_total_score: float        # 簡易検索：総合スコア（0-25）
    agentic_search_total_score: float       # エージェント検索：総合スコア（0-25）
    # 定性分析
    key_differences: List[str]              # 主な相違点
    simple_search_strengths: List[str]      # 簡易検索の強み
    simple_search_weaknesses: List[str]     # 簡易検索の弱み
    agentic_search_strengths: List[str]     # エージェント検索の強み
    agentic_search_weaknesses: List[str]    # エージェント検索の弱み
    # 推奨
    recommendation: str                     # 推奨結果・活用シーン
    cost_effectiveness_analysis: str        # 費用対効果分析
```

## ワークフロー実行フロー

### フェーズA: ワンショット検索

```
run_simple_research()
  ├─ SimpleSearcher エージェント作成
  ├─ Web検索実行
  ├─ 主要情報抽出（10-20個の発見事項）
  └─ SimpleSearchOutput を返却
```

### フェーズB: エージェンティック検索

```
run_agentic_research(max_iterations=5)
  ├─ ステップ1: 初期調査計画立案
  │   └─ SearchPlanner エージェント実行
  │       └─ SearchPlanOutput を生成
  │
  ├─ ステップ2: ユーザー確認・修正
  │   ├─ 調査計画を表示（目的、調査領域、キーワード、優先順位、戦略）
  │   ├─ ユーザー入力を待機
  │   └─ 追加指示がある場合は計画を修正
  │       └─ SearchPlanner エージェント再実行
  │
  ├─ ステップ3-N: 調査実行 → 評価 → 修正サイクル
  │   ├─ Researcher エージェント実行
  │   │   ├─ Web検索実行（複数キーワード組み合わせ）
  │   │   └─ ResearchResultOutput を生成
  │   │
  │   ├─ ResearchEvaluator エージェント実行
  │   │   ├─ 4観点で評価
  │   │   ├─ 総合スコア判定
  │   │   └─ should_refine 判定
  │   │
  │   └─ should_refine == True の場合
  │       └─ 修正計画を次の反復に適用
  │
  └─ 返却: (計画, 最終結果, [評価結果...])
```

### フェーズC: 比較分析

```
run_comparison_analysis(simple_result, agentic_result)
  ├─ ComparisonAnalyzer エージェント実行
  ├─ 定量比較（スコアリング、改善率）
  ├─ 定性分析（強み・弱み、相違点）
  ├─ 費用対効果分析
  └─ ComparisonReportOutput を返却
```

## 出力ファイル形式

各フェーズの結果は Markdown 形式で出力されます：

### 1. simple_search_YYYYMMDD_HHMMSS.md

ワンショット検索の結果：
- 調査概要
- 主要な発見事項（リスト形式）
- 根拠情報（URL、タイトル、概要）
- カバーされた領域
- 総括

### 2. agentic_search_YYYYMMDD_HHMMSS.md

エージェンティック検索の結果：
- 調査概要と総反復回数
- 調査計画（目的、領域、キーワード、戦略）
- 各反復でのスコアリングと評価
- 主要な発見事項
- 領域間の相互関連性
- 根拠情報
- 総括

### 3. comparison_YYYYMMDD_HHMMSS.md

比較分析レポート：
- スコアリング比較表（定量比較）
- スコア評価
- 定性分析（相違点、強み・弱み）
- 費用対効果分析
- 推奨事項（活用シーン、ガイドライン）

## 特徴

### 1. Web検索統合

`WebSearchTool` を Researcher エージェントに統合し、multi_persona_hearing と同様のアプローチで、複数の検索キーワード組み合わせとダイナミックな追加検索を実現します。

### 2. 反復的な改善

評価スコアに基づいた自動判定により、調査品質が目標水準（スコア 15/20）に達するまで反復を継続します。

### 3. 専門家視点の評価

ResearchEvaluator エージェントが当該分野の専門家として、観点のヌケモレを特定し、改善が必要な領域を具体的に提案します。

### 4. 多角的な比較分析

簡易検索とエージェンティック検索を、4つの定量的観点と定性的分析で比較し、改善率と推奨活用シーンを明確化します。

### 5. 費用対効果分析

実行時間と API コストを考慮し、それぞれのアプローチの活用シーンを提示します。

## 実装のポイント

### エージェント定義

各エージェントは `Agent` クラスを継承し、以下の要素を定義します：

```python
agent = Agent(
    name="エージェント名",
    instructions="詳細なシステムプロンプト",
    output_type=OutputSchema,  # Pydantic BaseModel
    tools=[WebSearchTool()]    # オプション
)
```

### ワークフロー実装

ワークフロー関数は `async` 定義し、`Runner.run()` でエージェントを実行します：

```python
result = await Runner.run(agent, prompt)
output = result.final_output_as(OutputSchema)
```

### スキーマ定義

Pydantic `BaseModel` を使用して型安全性を実現し、`Field` で制約を指定します：

```python
class OutputSchema(BaseModel):
    field_name: str = Field(description="フィールドの説明")
    score: int = Field(ge=1, le=10, description="1-10のスコア")
```

## 活用シーン

### ワンショット検索が適切なケース
- 時間的制約がある場合
- 高レベルの概要把握が目的
- 初期段階のリサーチ
- 予算が限定的

### エージェンティック検索が適切なケース
- 深い理解が必要
- 意思決定に重要な調査
- 包括的な分析が必須
- ヌケモレを最小化したい

### 併用アプローチ（推奨）
1. **初期段階**: ワンショット検索で概要把握
2. **精密段階**: エージェンティック検索で深掘り
3. **統合**: 両結果を組み合わせた包括的な理解

## トラブルシューティング

### インポートエラー

```
ModuleNotFoundError: No module named 'openai_agents'
```

**解決策**: 依存パッケージをインストール
```bash
pip install -r requirements.txt
```

### API 認証エラー

```
AuthenticationError: Incorrect API key
```

**解決策**: `.env` ファイルに OpenAI API キーを設定
```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

### Web検索がエラーになる

検索クエリに非ASCII文字が含まれている場合、エンコーディングエラーが発生することがあります。エージェントのシステムプロンプトで適切なエンコーディングを指示してください。

## パフォーマンスに関する考慮

- **実行時間**: エージェンティック検索は反復回数に応じて実行時間が増加します
- **API コスト**: Web検索の回数と LLM API のトークン使用量が主なコストファクタです
- **並列実行**: 現在のワークフローはシーケンシャル実行ですが、今後の拡張で並列化が可能です

## ライセンスと参考

- OpenAI Agent SDK: https://openai.com/index/agents/
- Pydantic: https://docs.pydantic.dev/

---

*このモジュールは multi_persona_hearing, idea_generator_evaluator, board_meeting と同じ設計パターンに基づいています。*
