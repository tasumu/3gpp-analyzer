# 会議分析機能

## 概要

本システムは4つの分析サービスを提供し、内部で3つのADK Agentを使い分けている。

## サービス一覧

| サービス | 呼び出し元 | Agent | 概要 |
|---------|-----------|-------|------|
| Summarize Meeting | 会議ページ「Summarize Meeting」ボタン | 不使用 | パイプライン方式で全doc要約→全体集約 |
| Generate Full Report | 会議ページ「Generate Full Report」ボタン | `agentic_search_agent` | Summarize + Agent深掘り調査 → Markdownレポート |
| Agentic QA | Q&Aチャット (Agentic Searchモード) | `agentic_search_agent` | 会議スコープのマルチステップ調査型Q&A |
| RAG QA | Q&Aチャット (RAG Searchモード) | `qa_agent` | `search_evidence`のみの軽量Q&A |

## Summarize Meeting vs Generate Full Report

2つのボタンは独立した機能ではなく、Generate Full Report が Summarize Meeting を内包する関係にある。

```
Summarize Meeting
├── 全寄書の個別LLM要約 (AnalysisService.generate_summary)
└── 全体サマリー生成 (_generate_overall_report)

Generate Full Report
├── Step 1: Summarize Meeting と同一処理 (MeetingService.summarize_meeting)
│   ├── 全寄書の個別LLM要約
│   └── 全体サマリー生成
└── Step 2: agentic_search_agent による深掘り調査
    ├── Step 1 の key_topics / sample contributions をプロンプトに注入
    ├── Agent が自律的に list_meeting_documents_enhanced, search_evidence,
    │   investigate_document 等を駆使して詳細分析
    └── 構造化 Markdown レポートとして GCS に保存 → 署名URL返却
```

Summarize Meeting を先に実行しておくと、Generate Full Report の Step 1 はキャッシュヒットしてほぼ即座に完了する。

## プロンプトの影響範囲

UIには2つのカスタムプロンプト入力欄がある。

|  | Summarize Meeting | Generate Full Report Step 1 | Generate Full Report Step 2 (Agent) |
|--|-------------------|---------------------------|-------------------------------------|
| **Analysis Prompt** | 各文書の個別要約 | 各文書の個別要約 | 影響なし |
| **Report Prompt** | 全体サマリー生成 | 全体サマリー生成 | Agent のプロンプトに注入 |

- **Analysis Prompt** は `AnalysisService.generate_summary(custom_prompt=...)` に渡され、個別文書のLLM要約時に使われる
- **Report Prompt** は `_generate_overall_report(report_prompt=...)` と `_build_agent_prompt(report_prompt=...)` の両方に渡される
- Agent の Sub-Agent (`investigate_document`) にはどちらのプロンプトも渡されない

## キャッシュアーキテクチャ

### 個別文書要約キャッシュ

- **保存先**: Firestore `document_summaries` コレクション
- **キー構成**: `{document_id}_{language}` (プロンプトなし) or `{document_id}_{language}_{md5(custom_prompt)[:8]}` (プロンプトあり)
- **生成**: `AnalysisService.generate_summary()` 内で cache miss 時に生成・保存
- **共有**: Summarize Meeting と Generate Full Report の Step 1 で同じキャッシュを使用

### キャッシュの影響

| 操作 | キャッシュ動作 |
|-----|-------------|
| Summarize → Full Report (同じプロンプト) | Step 1 は全キャッシュヒット。Step 2 (Agent) のみ実行 |
| Full Report 単独実行 (Summarize 未実施) | Step 1 で全寄書の個別分析が走る (高コスト・長時間) |
| プロンプト変更後に実行 | キーが変わるため全文書の再分析が必要 |
| Force re-analyze チェック | Summarize Meeting のみ影響。キャッシュを無視して再分析 |

### Force re-analyze

- `Summarize Meeting` ボタンにのみ影響する (`force=True` で API 呼出)
- `Generate Full Report` は内部で `summarize_meeting(force=False)` を呼ぶため影響しない
- 再分析が必要な場合は、先に Force 付きで Summarize を実行してから Full Report を生成する

## Agent 構成図

```
┌────────────────────────────────────────────────────────────┐
│                     adk_agents.py                           │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  1. qa_agent                                                │
│     Model: gemini-3-pro-preview                             │
│     用途: RAG QA (search_evidence のみ)                     │
│     呼出元: QAService (mode=RAG)                            │
│                                                             │
│  2. agentic_search_agent                                    │
│     Model: gemini-3-pro-preview                             │
│     用途: Agentic QA / Generate Full Report                 │
│     呼出元: QAService (mode=AGENTIC) /                      │
│            MeetingReportGenerator                           │
│     Tools:                                                  │
│       ├── list_meeting_documents_enhanced                   │
│       ├── search_evidence                                   │
│       ├── get_document_summary                              │
│       ├── list_meeting_attachments                          │
│       ├── read_attachment                                   │
│       └── AgentTool(investigate_document) ─┐                │
│                                             │                │
│     3. investigate_document (Sub-Agent)      │                │
│        Model: gemini-3-flash-preview        │                │
│        Input: InvestigationInput (Pydantic) │                │
│        Tools: get_document_content のみ      │                │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

## 関連ドキュメント

- [agentic-search.md](./agentic-search.md) - Agentic Search モードの設計詳細
- [requirements.md](./requirements.md) - 機能要件 (P3-02, P3-05, P3-06)
- [architecture.md](./architecture.md) - システム全体設計

## 主要ソースファイル

| ファイル | 役割 |
|---------|------|
| `backend/src/analyzer/agents/adk_agents.py` | Agent 定義 (qa_agent, agentic_search_agent, investigate_document) |
| `backend/src/analyzer/services/meeting_service.py` | Summarize Meeting の実装 |
| `backend/src/analyzer/services/meeting_report_generator.py` | Generate Full Report の実装 |
| `backend/src/analyzer/services/qa_service.py` | RAG QA / Agentic QA の実装 |
| `backend/src/analyzer/services/analysis_service.py` | 個別文書要約 + キャッシュ管理 |
| `backend/src/analyzer/agents/tools/` | Agent が使う各種 Tool の実装 |
