# データモデル

## 1. データフロー

```
[3GPP FTP]
     ↓
[ZIP / doc / docx / pdf]
     ↓
[正規化] ← doc→docx変換
     ↓
[docx / text / json]
     ↓
[構造抽出] ← 見出し・段落・表・図
     ↓
[チャンク化] ← 条項単位
     ↓
[メタデータ付与]
     ↓
[正規化済み文書ストア]
     ↓
[RAG (embedding)]
     ↓
[Evidence検索]
```

---

## 2. Document（正規化済み文書）

### 2.1 スキーマ

```typescript
interface Document {
  id: string;                    // 文書ID
  contribution_number: string;   // 寄書番号（例: S1-234567）
  meeting: Meeting;              // 会合情報
  title: string;                 // 文書タイトル
  status: DocumentStatus;        // 処理ステータス
  source_files: SourceFile[];    // 元ファイル情報
  normalized_at: timestamp | null; // 正規化日時
  indexed_at: timestamp | null;  // ベクトル化日時
  chunks: Chunk[];               // チャンク一覧
}

type DocumentStatus =
  | "metadata_only"   // メタ情報のみ（FTP同期済）
  | "downloading"     // ダウンロード中
  | "extracting"      // ZIP展開中
  | "normalizing"     // 正規化中（doc→docx）
  | "normalized"      // 正規化済
  | "indexing"        // ベクトル化中
  | "indexed"         // ベクトル化済（分析可能）
  | "failed";         // 処理失敗

interface Meeting {
  name: string;                  // 例: "SA1#111", "RAN4#100"
  type: "working" | "plenary";   // WG会合 or プレナリ会合
}

interface SourceFile {
  filename: string;
  original_format: "doc" | "docx" | "pdf" | "zip";
  ftp_path: string;
  downloaded_at: timestamp;
}
```

### 2.2 Python定義

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

class Meeting(BaseModel):
    name: str
    type: Literal["working", "plenary"]

class SourceFile(BaseModel):
    filename: str
    original_format: Literal["doc", "docx", "pdf", "zip"]
    ftp_path: str
    downloaded_at: datetime

DocumentStatus = Literal[
    "metadata_only",  # メタ情報のみ
    "downloading",    # ダウンロード中
    "extracting",     # ZIP展開中
    "normalizing",    # 正規化中
    "normalized",     # 正規化済
    "indexing",       # ベクトル化中
    "indexed",        # ベクトル化済
    "failed",         # 処理失敗
]

class Document(BaseModel):
    id: str
    contribution_number: str
    meeting: Meeting
    title: str
    status: DocumentStatus
    source_files: list[SourceFile]
    normalized_at: datetime | None = None
    indexed_at: datetime | None = None
    chunks: list["Chunk"] = []
```

---

## 3. Chunk（条項単位チャンク）

### 3.1 スキーマ

```typescript
interface Chunk {
  id: string;                    // チャンクID
  document_id: string;           // 所属文書ID
  content: string;               // テキスト内容
  structure_type: StructureType; // 構造タイプ
  metadata: ChunkMetadata;       // メタデータ
  embedding?: number[];          // ベクトル（RAG用）
}

type StructureType =
  | "heading"         // 見出し（条項）
  | "paragraph"       // 段落
  | "table"           // 表
  | "figure_caption"; // 図キャプション

interface ChunkMetadata {
  contribution_number: string;   // 寄書番号
  meeting: string;               // 会合情報
  clause_number: string | null;  // 条項番号
  page_number: number | null;    // ページ番号
  source_file: string;           // 元ファイル参照
}
```

### 3.2 Python定義

```python
from pydantic import BaseModel
from typing import Literal

class ChunkMetadata(BaseModel):
    contribution_number: str
    meeting: str
    clause_number: str | None = None
    page_number: int | None = None
    source_file: str

class Chunk(BaseModel):
    id: str
    document_id: str
    content: str
    structure_type: Literal["heading", "paragraph", "table", "figure_caption"]
    metadata: ChunkMetadata
    embedding: list[float] | None = None
```

### 3.3 構造抽出ルール

| 構造タイプ | 抽出対象 |
|-----------|---------|
| heading | Heading 1-6 スタイル、番号付き条項（1., 1.1, 1.1.1 等） |
| paragraph | Normal スタイル、本文テキスト |
| table | Table要素、セル単位でテキスト抽出 |
| figure_caption | Caption スタイル、"Figure X:" パターン |

---

## 4. Evidence（RAG検索結果）

### 4.1 概要

Evidenceは、RAGから返される根拠情報の共通形式。
RAG基盤が変わっても、この形式は不変。

### 4.2 スキーマ

```python
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    """RAGから返される根拠情報の共通形式"""

    # 必須フィールド
    text: str = Field(
        description="テキスト抜粋（根拠となる文章）"
    )
    document_id: str = Field(
        description="文書番号"
    )
    contribution_number: str = Field(
        description="寄書番号"
    )
    meeting: str = Field(
        description="会合情報（例: SA1#111）"
    )
    score: float = Field(
        description="検索スコア（0.0-1.0）",
        ge=0.0,
        le=1.0
    )
    source_file: str = Field(
        description="元ファイル参照"
    )

    # オプションフィールド
    clause_number: str | None = Field(
        default=None,
        description="条項番号（見出しスタイルから抽出、例: 5.2.1）"
    )
    page_number: int | None = Field(
        default=None,
        description="ページ番号",
        ge=1
    )
    chunk_id: str | None = Field(
        default=None,
        description="チャンクID（内部参照用）"
    )
```

### 4.3 TypeScript定義

```typescript
interface Evidence {
  // 必須
  text: string;
  document_id: string;
  contribution_number: string;
  meeting: string;
  score: number;  // 0.0-1.0
  source_file: string;

  // オプション
  clause_number?: string;        // 条項番号（見出しスタイルから抽出）
  page_number?: number;
  chunk_id?: string;
}
```

### 4.4 使用例

**RAG検索結果**

```json
{
  "text": "The UE shall support the following...",
  "document_id": "doc-12345",
  "contribution_number": "S1-234567",
  "meeting": "SA1#111",
  "clause_number": "5.2.1",
  "page_number": 12,
  "score": 0.92,
  "source_file": "S1-234567.docx"
}
```

**分析結果での引用**

```markdown
## 分析結果

本寄書では、UEが以下をサポートすることが提案されています。

> "The UE shall support the following..."
> — S1-234567, Clause 5.2.1, Page 12
```

---

## 5. AnalysisResult（分析結果）

分析結果を永続化し、再利用・履歴管理を可能にする。

### 5.1 スキーマ

```typescript
interface AnalysisResult {
  id: string;                      // 分析結果ID
  document_id: string;             // 対象文書ID
  type: AnalysisType;              // 分析タイプ
  strategy_version: string;        // 分析戦略バージョン
  created_at: timestamp;           // 作成日時
  result: SingleAnalysis | CompareAnalysis;
}

type AnalysisType = "single" | "compare";

interface SingleAnalysis {
  summary: string;                 // 要点サマリ
  changes: Change[];               // 変更提案
  issues: Issue[];                 // 論点・懸念
  evidences: Evidence[];           // 根拠
}

interface CompareAnalysis {
  common_points: string[];         // 共通点
  differences: Difference[];       // 相違点
  recommendation: string;          // 推奨アクション
  evidences: Evidence[];           // 根拠
}

interface Change {
  type: "addition" | "modification" | "deletion";
  description: string;
  clause: string | null;
}

interface Issue {
  description: string;
  severity: "high" | "medium" | "low";
}

interface Difference {
  aspect: string;                  // 比較観点
  doc1_position: string;           // 文書1の立場
  doc2_position: string;           // 文書2の立場
}
```

### 5.2 Python定義

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

AnalysisType = Literal["single", "compare"]
ChangeType = Literal["addition", "modification", "deletion"]
Severity = Literal["high", "medium", "low"]

class Change(BaseModel):
    type: ChangeType
    description: str
    clause: str | None = None

class Issue(BaseModel):
    description: str
    severity: Severity

class Difference(BaseModel):
    aspect: str
    doc1_position: str
    doc2_position: str

class SingleAnalysis(BaseModel):
    summary: str
    changes: list[Change]
    issues: list[Issue]
    evidences: list[Evidence]

class CompareAnalysis(BaseModel):
    common_points: list[str]
    differences: list[Difference]
    recommendation: str
    evidences: list[Evidence]

class AnalysisResult(BaseModel):
    id: str
    document_id: str
    type: AnalysisType
    strategy_version: str
    created_at: datetime
    result: SingleAnalysis | CompareAnalysis
```

### 5.3 永続化の方針

| 項目 | 方針 |
|------|------|
| 保存先 | Firestore |
| キー | `document_id` + `type` + `strategy_version` |
| 再分析条件 | 戦略バージョン変更、明示的な再分析リクエスト |
| 保持期間 | 無期限（必要に応じてアーカイブ） |

### 5.4 使用例

```json
{
  "id": "ana-12345",
  "document_id": "doc-67890",
  "type": "single",
  "strategy_version": "v1",
  "created_at": "2025-01-29T10:00:00Z",
  "result": {
    "summary": "本寄書はTS 22.261への新要件追加を提案...",
    "changes": [
      {
        "type": "addition",
        "description": "低遅延要件の追加",
        "clause": "5.2.1"
      }
    ],
    "issues": [
      {
        "description": "RAN2との整合性確認が必要",
        "severity": "medium"
      }
    ],
    "evidences": [...]
  }
}
```

---

## 6. メタデータ仕様

### 6.1 寄書番号

**形式**: `{WG}-{番号}`

**例**: `S1-234567`, `R4-123456`, `C6-098765`

**WGコード対応表**

| WG | コード | WG | コード |
|----|-------|----|----|
| SA1 | S1 | RAN1 | R1 |
| SA2 | S2 | RAN2 | R2 |
| SA3 | S3 | RAN3 | R3 |
| SA4 | S4 | RAN4 | R4 |
| SA5 | S5 | RAN5 | R5 |
| SA6 | S6 | CT1 | C1 |
| | | CT3 | C3 |
| | | CT4 | C4 |
| | | CT6 | C6 |

### 6.2 会合情報

**WG会合（数字あり）**
- 形式: `{WG}#{番号}`
- 例: `SA1#111`, `RAN4#100`, `CT6#105`

**プレナリ会合（数字なし）**
- 形式: `{プレナリ}#{番号}`
- 例: `SA#101`, `RAN#102`, `CT#80`

**プレナリ種別**

| プレナリ | 配下WG |
|---------|-------|
| SA | SA1, SA2, SA3, SA4, SA5, SA6 |
| RAN | RAN1, RAN2, RAN3, RAN4, RAN5 |
| CT | CT1, CT3, CT4, CT6 |

### 6.3 条項番号

**形式**
- ドット区切り階層: `1`, `1.1`, `1.1.1`, etc.
- アルファベット付き: `A.1`, `B.2.3`
- Annex: `Annex A`, `Annex B.1`

### 6.4 ページ番号

- 整数（1始まり）
- 表紙は0またはnull

### 6.5 元ファイル参照

- 相対パス: `S1-234567.docx`
- FTPパス: `ftp://..../S1-234567.doc`
