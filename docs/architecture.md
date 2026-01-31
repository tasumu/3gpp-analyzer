# アーキテクチャ設計

## 1. 設計思想

### 核心メッセージ

> 「寄書分析の価値」はRAGではなく、正規化・構造化・分析ロジックにある。
> RAGは取り換え可能な設計にするのが正解。

### 設計5原則

1. **docx正規化で世界が楽になる** - 下流処理の前に必ず正規化
2. **分析はEvidence入力に固定** - RAG実装を知らない
3. **RAGは裏方、差し替え前提** - ロックインしない
4. **危険なツールは外に出さない** - 内部ツールは非公開
5. **引用トレーサビリティ最優先** - 全結果に根拠を付与

---

## 2. システム構成

### 2.1 レイヤー図

```
[UI / API]  ← ユーザーが触る
     ↓
[分析エージェント]  ← LLMが判断・生成
     ↓
[Evidence取得IF]  ← ★RAG差し替え境界
     ↓
[既存RAG基盤]  ← Firestore / Dify / LangGraph / etc
     ↓
[正規化済み文書ストア]
     ↓
[FTP / ZIP / doc]
```

### 2.2 レイヤー責務

| レイヤー | 責務 | 公開範囲 |
|---------|------|---------|
| UI / API | ユーザーインタラクション、認証 | 公開 |
| 分析エージェント | LLMによる分析・生成 | 公開（API経由） |
| Evidence取得IF | RAG抽象化境界 | 内部 |
| RAG基盤 | ベクトル検索 | 内部 |
| 正規化済み文書ストア | 構造化データ保持 | 内部 |
| 取得・変換層 | FTP/ZIP/変換 | 内部 |

---

## 3. RAG抽象化設計

### 3.1 設計目的

- RAG基盤の差し替えを容易にする
- 分析ロジックをRAG非依存にする
- 将来的なMCP公開の余地を残す

### 3.2 Evidence取得インターフェース

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class Evidence(BaseModel):
    """RAGから返される根拠情報の共通形式"""
    text: str                    # テキスト抜粋
    document_id: str             # 文書番号
    contribution_number: str     # 寄書番号
    meeting: str                 # 会合情報
    clause_number: str | None    # 条項番号（見出しスタイルから抽出）
    page_number: int | None      # ページ番号
    score: float                 # 検索スコア
    source_file: str             # 元ファイル参照

class EvidenceProvider(ABC):
    """RAG抽象化インターフェース"""

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: dict | None = None,
        top_k: int = 10
    ) -> list[Evidence]:
        """クエリに対する根拠を検索"""
        pass
```

### 3.3 差し替え可能な実装

| 実装 | 特徴 |
|------|------|
| Firestore Vector Search | GCP統合、Firebase連携 |
| Dify標準RAG | 迅速な構築、UI付き |
| LangGraph + Vector DB | 高度なカスタマイズ |
| Elastic (Hybrid) | ハイブリッド検索 |

### 3.4 分析エージェントからの利用

```python
class AnalysisAgent:
    def __init__(self, evidence_provider: EvidenceProvider):
        self.evidence_provider = evidence_provider

    async def analyze(self, contribution_id: str) -> AnalysisResult:
        # Evidence取得（RAG実装を知らない）
        evidences = await self.evidence_provider.search(
            query="...",
            filters={"contribution_number": contribution_id}
        )
        # LLMによる分析
        ...
```

### 3.5 エージェントツール化

分析エージェントが直接RAG検索できるようツール化することも可能。
ただし、出力は必ずEvidence形式を維持する。

```python
@tool
async def search_evidence(
    query: str,
    contribution_number: str | None = None
) -> list[Evidence]:
    """寄書から関連する根拠を検索する"""
    filters = {}
    if contribution_number:
        filters["contribution_number"] = contribution_number
    return await evidence_provider.search(query, filters)
```

---

## 4. セキュリティ設計

### 4.1 ツール公開方針

**内部ツール（非公開）**

| ツール | 非公開理由 |
|--------|-----------|
| FTPアクセス | 外部サーバーへの直接アクセス |
| ZIP展開 | ファイルシステム操作 |
| doc→docx変換 | 外部プロセス実行（LibreOffice） |
| チャンク化・embedding | 内部処理 |
| ベクトルDB操作 | データベース直接操作 |
| クラウドストレージ操作 | ストレージ直接操作 |

**公開API / UI**

| 機能 | 説明 |
|------|------|
| 分析実行 | 寄書単体 / 比較分析 |
| 結果表示 | 分析結果の閲覧 |
| 成果物ダウンロード | 署名URL経由 |

### 4.2 認証・認可

- **認証**: Firebase Auth（メール/パスワード）
- **認可**: ユーザー別アクセス制御
- **通信**: HTTPS必須

### 4.3 MCP公開時の考慮

- 公開対象は分析系APIのみ
- Evidence取得IFは将来検討
- 内部ツールは非公開を維持

---

## 5. 技術選択

| コンポーネント | 選択 | 備考 |
|---------------|------|------|
| エージェント基盤 | Google ADK | Agent Development Kit |
| LLM | Gemini | gemini-3-flash-preview |
| ベクトル検索 | Firestore Vector Search | Firestoreに統合 |
| メタデータDB | Firestore | 構造化データ |
| ファイルストレージ | Cloud Storage (GCS) | 元ファイル、正規化済み、生成物 |
| プロジェクト構成 | モノレポ | frontend/ + backend/ |

### 5.1 ストレージ構成

```
Firestore (構造化データ + ベクトル)
├── documents/           # Document メタデータ
├── chunks/              # Chunk + embedding（ベクトル検索対象）
├── analysis_results/    # 分析結果
└── users/               # ユーザー情報

Cloud Storage (ファイル)
├── original/            # FTPからDLした元ファイル
├── normalized/          # 正規化済み docx
└── outputs/             # レビューシート等の生成物
```

### 5.2 Firestore Vector Search

メタデータとベクトルを同一DBで管理。

```python
# ベクトル検索 + フィルタの同時実行
results = db.collection("chunks").find_nearest(
    vector_field="embedding",
    query_vector=query_embedding,
    distance_measure="COSINE",
    limit=10,
    filters=FieldFilter("metadata.meeting", "==", "SA1#111")
)
```

**現行実装（Phase 1）:**
- Embeddingモデル: Vertex AI `text-embedding-004`（768次元）
- ベクトルインデックス: Firestore Vector Search
- 検索: コサイン類似度、メタデータフィルタ併用可能

**将来の拡張:**
- 性能問題が出た場合、EvidenceProvider実装を差し替え
- Pinecone / Vertex AI Vector Search 等に移行可能

---

## 6. 前処理設計

### 6.1 正規化で勝つ

> 正規化で揃えると既存RAGエコシステムがそのまま使える

**正規化前**
- .doc, .docx, .pdf, ZIP
- 様々なフォーマット
- 構造が不明確

**正規化後**
- docx / text / json のみ
- 統一フォーマット
- 構造が明確

### 6.2 FTP / ZIP の扱い

1. ディレクトリ構造とメタ情報のみ先行同期
2. ファイル本体は必要なときだけダウンロード
3. 処理開始時に自動ダウンロード（`gcs_original_path`未設定時）

**現行実装（Phase 1）:**
- FTP同期: 会合単位でメタデータ取得、遅延ダウンロード
- ZIP展開: `.docx`/`.doc`ファイルを自動抽出
  - `__MACOSX`フォルダ、隠しファイルを除外
  - `.docx`を優先、なければ`.doc`を選択
- 自動ダウンロード: ProcessorServiceが処理開始時に自動取得

### 6.3 ファイル変換

- `.doc` → `.docx`（LibreOffice headless）
- `.zip` → 内包する`.doc`/`.docx`を展開後、必要に応じて変換
- PDFは必要に応じてテキスト化（初期フェイズでは実装不要）

**現行実装（Phase 1）:**
- NormalizerService: LibreOffice headless によるdoc→docx変換
- ZIP対応: 自動展開、docx優先、doc→docx変換
- タイムアウト: 60秒

---

## 7. チャンク化戦略

### 7.1 設計方針

チャンク化戦略は**差し替え可能**な設計とする。
精度改善のために後から戦略を変更できることが重要。

### 7.2 抽象化インターフェース

```python
from abc import ABC, abstractmethod

class ChunkingStrategy(ABC):
    """チャンク化戦略の抽象インターフェース"""

    @abstractmethod
    def chunk(self, document: NormalizedDocument) -> list[Chunk]:
        """文書をチャンクに分割する"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """戦略のバージョン識別子"""
        pass
```

### 7.3 現行戦略（v1）: 見出しスタイルベース ✅ 実装済

```python
class HeadingBasedChunking(ChunkingStrategy):
    """Word見出しスタイルに基づくチャンク化"""

    version = "heading-based-v1"
```

**抽出ルール:**

| 要素 | 抽出方法 |
|------|---------|
| 条項番号 | Heading 1-6 スタイル、または `^\d+(\.\d+)*` パターン |
| 段落 | Normal スタイルのテキスト |
| 表 | Table要素、セル結合を考慮 |
| 図キャプション | Caption スタイル、"Figure X:" パターン |

**分割ルール:**
- 見出し（Heading）を境界として分割
- 1チャンクの最大サイズ: 1000トークン目安
- 最大サイズ超過時は段落境界で追加分割

**メタデータ付与:**
- 直近の見出しから条項番号を継承
- ページ番号は段落位置から推定

**Phase 1 実装:**
- `HeadingBasedChunking`: 見出しベースのチャンク化
- `DocxExtractor`: python-docx によるdocx構造解析
- チャンクメタデータ: `contribution_number`, `meeting_id`, `clause_number`
- Firestoreの`chunks`コレクションに保存
- `chunk_count`をDocumentに記録

### 7.4 将来の改善候補

| 戦略 | 説明 | ユースケース |
|------|------|-------------|
| セマンティック分割 | 意味的なまとまりで分割 | 精度向上 |
| オーバーラップ | チャンク間で重複を持たせる | 検索漏れ防止 |
| 階層preserving | 親子関係を保持 | 構造的な検索 |
| ハイブリッド | 複数戦略の組み合わせ | 最適化 |

### 7.5 戦略の切り替え

```python
# 依存性注入でチャンク化戦略を切り替え
class DocumentProcessor:
    def __init__(self, chunking_strategy: ChunkingStrategy):
        self.chunking_strategy = chunking_strategy

    def process(self, doc: NormalizedDocument) -> list[Chunk]:
        return self.chunking_strategy.chunk(doc)

# 使用例
processor = DocumentProcessor(
    chunking_strategy=HeadingBasedChunking()  # または別の戦略
)
```

### 7.6 バージョン管理

- チャンクには使用した戦略バージョンを記録
- 戦略変更時は再チャンク化が必要
- 既存チャンクとの互換性は保証しない（再インデックス前提）

---

## 8. プロジェクト構成

モノレポ構成を採用。

```
3gpp-analyzer/
├── frontend/                # Next.js アプリ
│   ├── src/
│   │   ├── app/            # App Router
│   │   ├── components/     # UIコンポーネント
│   │   └── lib/            # ユーティリティ
│   ├── package.json
│   └── ...
│
├── backend/                 # FastAPI アプリ
│   ├── src/
│   │   └── analyzer/       # メインパッケージ
│   │       ├── api/        # APIエンドポイント
│   │       ├── services/   # ビジネスロジック
│   │       ├── models/     # Pydanticモデル
│   │       ├── providers/  # EvidenceProvider等
│   │       └── main.py
│   ├── pyproject.toml
│   └── ...
│
├── docs/                    # ドキュメント
│   ├── requirements.md
│   ├── architecture.md
│   ├── data-model.md
│   ├── api.md
│   └── tech-stack.md
│
├── firebase.json            # Firebase設定
├── firestore.rules          # Firestoreセキュリティルール
├── storage.rules            # GCSセキュリティルール
└── README.md
```
