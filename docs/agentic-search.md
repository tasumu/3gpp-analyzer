# Agentic Search 設計書

## 概要

Q&A画面の新しいモード「Agentic Search」の設計。従来の RAG Search がベクトル検索の結果のみを基に回答するのに対し、Agentic Search ではAgent が能動的にドキュメント一覧の調査、関連寄書の特定、個別文書の深掘りなどを行い、より精度の高い調査・回答を生成する。

### RAG Search vs Agentic Search

| 観点 | RAG Search | Agentic Search |
|------|-----------|----------------|
| 検索方式 | ベクトル類似度検索（1回〜数回） | Agent が計画を立てマルチステップで探索 |
| ツール | `search_evidence` のみ | ドキュメント一覧、メタデータ検索、RAG検索、個別文書調査 |
| 対応スコープ | document, meeting, global | meeting のみ |
| 適した質問 | 特定トピックの情報検索 | 会合全体の動向調査、議題横断の分析、合意結果の調査 |
| 応答速度 | 高速 | 調査深度に応じて時間がかかる |
| 透明性 | 最終回答のみ | 調査計画・ツール呼び出し・中間結果を逐次表示 |

## アーキテクチャ

### Agent構成: Single Agent + AgentTool

```
┌─────────────────────────────────────────────────┐
│  Agentic Search Agent (Main)                    │
│                                                 │
│  System Instruction:                            │
│  - クエリ分析 → 調査計画立案                       │
│  - ドキュメント一覧から関連寄書特定                   │
│  - ツール選択・実行判断                             │
│  - 最終サマライズ・回答生成                          │
│                                                 │
│  Tools:                                         │
│  ├── list_meeting_documents (拡張版)              │
│  │   └─ タイトル検索・ページネーション対応            │
│  ├── search_evidence (既存)                      │
│  │   └─ RAGベクトル検索                            │
│  ├── get_document_summary (既存)                  │
│  │   └─ 事前計算済みサマリー取得                     │
│  └── investigate_document (AgentTool)            │
│      └── Document Investigation Agent            │
│          ├── get_document_content                │
│          └── search_evidence                     │
└─────────────────────────────────────────────────┘
```

### なぜ Single Agent + AgentTool か

1. **既存パターンとの一貫性**: 現在のRAG Search、Meeting Report はいずれも Single Agent パターン
2. **コンテキスト管理**: メインAgent は計画・要約に集中し、個別文書の詳細（大量チャンク）はサブAgent に委任
3. **AgentTool の役割**: `investigate_document` は内部でサブAgent を生成・実行し、分析結果のテキストのみを返す。メインAgent のコンテキストウィンドウを保護

### ストリーミング設計

```
Frontend (SSE) ← Backend (EventSourceResponse)
    │
    ├── event: tool_call    {"tool": "list_meeting_documents", "args": {...}}
    ├── event: tool_result  {"tool": "list_meeting_documents", "summary": "Found 45 documents"}
    ├── event: tool_call    {"tool": "search_evidence", "args": {...}}
    ├── event: tool_result  {"tool": "search_evidence", "summary": "5 relevant results"}
    ├── event: tool_call    {"tool": "investigate_document", "args": {...}}
    ├── event: tool_result  {"tool": "investigate_document", "summary": "Analysis complete"}
    ├── event: chunk        {"content": "調査結果をまとめます..."}
    ├── event: chunk        {"content": "..."}
    ├── event: evidence     {"evidence": {...}}
    ├── event: evidence     {"evidence": {...}}
    └── event: done         {"result_id": "...", "answer": "..."}
```

## ツール詳細

### list_meeting_documents (拡張版)

既存の `adk_document_tools.py` 版はステータス `indexed` 固定だが、Agentic Search 用にフィルタリングを強化。

```python
async def list_meeting_documents(
    meeting_id: str,
    search_text: str | None = None,   # タイトル・ファイル名でキーワード検索
    page: int = 1,                    # ページ番号
    page_size: int = 50,              # 1ページあたりの件数
    tool_context: ToolContext = None,
) -> dict[str, Any]:
```

返却値:
```json
{
  "meeting_id": "SA2#162",
  "documents": [
    {
      "document_id": "abc123",
      "contribution_number": "S2-2401234",
      "title": "Discussion on UE power saving",
      "source": "Qualcomm",
      "filename": "S2-2401234.docx",
      "document_type": "contribution"
    }
  ],
  "total": 120,
  "page": 1,
  "page_size": 50
}
```

### investigate_document (AgentTool)

メインAgent のコンテキストを保護するため、個別文書の深掘りを別Agent に委任。

```python
async def investigate_document(
    document_id: str,
    investigation_query: str,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
```

内部動作:
1. `create_document_investigation_agent()` でサブAgent 生成
2. サブAgent は `get_document_content` と `search_evidence` を使って調査
3. サブAgent の応答テキスト（分析結果）のみを返却

返却値:
```json
{
  "document_id": "abc123",
  "contribution_number": "S2-2401234",
  "analysis": "This document proposes modifications to...",
  "evidence_count": 5
}
```

## Agentic Search Agent のプロンプト設計

### 調査ワークフロー（指示概要）

1. **クエリ分析**: ユーザーの質問を分析し、何を知りたいのか明確にする
2. **調査計画**: どのアプローチで調査するか計画を立てる
3. **ドキュメント探索**: `list_meeting_documents` で会合の寄書一覧を取得
4. **関連寄書特定**: タイトル・ソースから関連しそうな寄書を特定
5. **詳細調査**: `investigate_document` で重要な寄書を深掘り
6. **補強検索**: `search_evidence` で漏れがないか確認
7. **回答生成**: 調査結果をサマライズして回答

### Agent が活用する情報

- **ドキュメントタイトル**: 寄書の目的・内容の概要がわかる
- **ソース（source）**: 提案元の企業・団体
- **Contribution Number**: 寄書番号のパターン（revision は番号の末尾等で推測）
- **RAG 検索結果**: セマンティック検索で関連チャンクを取得
- **文書内容**: `investigate_document` で個別文書の詳細を取得

### 決定ステータス（Agreed/Approved/Revised等）の推測

現在のデータモデルに3GPP決定ステータスのフィールドは存在しない。Agent はタイトルやRAG検索結果から推測する:
- タイトルに "Agreed", "Approved" 等が含まれる場合
- 文書内容に議決結果が記載されている場合
- Revision の場合はタイトルや Contribution Number のパターンから推測

## フロントエンド設計

### モード切替

Settings Bar に切替ボタンを追加:
```
[Agentic Search] [RAG Search]
```

- Agentic Search 選択時は scope を自動的に `meeting` に制限
- RAG Search 選択時は全スコープ（document, meeting, global）選択可

### 中間ステップ表示

Agentic Search の応答中、ツール呼び出しと結果を逐次表示:

```
🔍 Searching meeting documents...
  → Found 45 documents in SA2#162

🔍 Searching for "UE power saving DRX"...
  → 5 relevant results found

📄 Investigating S2-2401234...
  → Analysis: Proposes modifications to DRX parameters...

📝 Generating summary...
  [最終回答がストリーミング表示]
```

## API 変更

### QARequest に mode 追加

```python
class QAMode(str, Enum):
    RAG = "rag"
    AGENTIC = "agentic"

class QARequest(BaseModel):
    mode: QAMode = QAMode.RAG
    # ... existing fields
```

### ストリーミングエンドポイント

`GET /qa/stream` に `mode` パラメータ追加:
```
GET /qa/stream?question=...&scope=meeting&scope_id=SA2%23162&mode=agentic
```

新ストリームイベント:
- `tool_call`: `{"tool": "tool_name", "args": {"key": "value"}}`
- `tool_result`: `{"tool": "tool_name", "summary": "result summary"}`
