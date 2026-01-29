# API仕様

## 1. 設計方針

### 1.1 基本方針

- **RESTful設計**: リソース指向、標準HTTPメソッド
- **認証**: Bearer Token（Firebase Auth）
- **レスポンス形式**: JSON
- **ストリーミング**: SSE（Server-Sent Events）

### 1.2 API分類

| 分類 | 説明 | 公開範囲 |
|------|------|---------|
| 公開API | ユーザー向け分析機能 | 公開 |
| 内部API | システム内部処理 | 非公開 |

---

## 2. 認証

全APIにBearer Tokenが必要（内部APIを除く）。

```
Authorization: Bearer {firebase_id_token}
```

---

## 3. 公開API

### GET /api/documents

文書一覧を取得する（処理ステータス付き）。

**クエリパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| meeting | string | No | 会合でフィルタ（例: SA1#111） |
| status | string | No | ステータスでフィルタ |
| limit | number | No | 取得件数（デフォルト: 50） |
| offset | number | No | オフセット |

**レスポンス**

```json
{
  "documents": [
    {
      "id": "doc-12345",
      "contribution_number": "S1-234567",
      "meeting": "SA1#111",
      "title": "New feature proposal",
      "status": "indexed",
      "normalized_at": "2025-01-29T10:00:00Z",
      "indexed_at": "2025-01-29T10:05:00Z"
    },
    {
      "id": "doc-12346",
      "contribution_number": "S1-234568",
      "meeting": "SA1#111",
      "title": "CR for TS 22.261",
      "status": "metadata_only",
      "normalized_at": null,
      "indexed_at": null
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

**ステータス一覧**

| status | 説明 |
|--------|------|
| metadata_only | メタ情報のみ（未ダウンロード） |
| downloading | ダウンロード中 |
| extracting | ZIP展開中 |
| normalizing | 正規化中 |
| normalized | 正規化済 |
| indexing | ベクトル化中 |
| indexed | ベクトル化済（分析可能） |
| failed | 処理失敗 |

---

### POST /api/documents/{id}/process

文書の処理をトリガーする（ダウンロード→正規化→ベクトル化）。

**リクエスト**

```json
{
  "target_status": "indexed"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|---|------|------|
| target_status | string | No | 目標ステータス（デフォルト: indexed） |

**レスポンス**

```json
{
  "document_id": "doc-12345",
  "current_status": "metadata_only",
  "target_status": "indexed",
  "message": "Processing started"
}
```

---

### GET /api/documents/{id}/status/stream

文書の処理ステータスをリアルタイムで取得する（SSE）。

**レスポンス（SSE）**

```
event: status
data: {"status": "downloading", "progress": 30}

event: status
data: {"status": "extracting", "progress": 50}

event: status
data: {"status": "normalizing", "progress": 70}

event: status
data: {"status": "indexing", "progress": 90}

event: complete
data: {"status": "indexed", "document_id": "doc-12345"}
```

---

### POST /api/analysis

分析を実行する。

**リクエスト**

```json
{
  "type": "single",
  "contribution_numbers": ["S1-234567"],
  "options": {
    "include_summary": true,
    "include_changes": true,
    "include_issues": true
  }
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|---|------|------|
| type | string | Yes | "single" または "compare" |
| contribution_numbers | string[] | Yes | single: 1件, compare: 2件 |
| options | object | No | 分析オプション |

**レスポンス**

```json
{
  "analysis_id": "ana-12345",
  "status": "processing",
  "created_at": "2025-01-29T12:00:00Z"
}
```

---

### GET /api/analysis/{id}

分析結果を取得する。

**レスポンス**

```json
{
  "analysis_id": "ana-12345",
  "status": "completed",
  "result": {
    "summary": "本寄書は...",
    "changes": [
      {
        "type": "addition",
        "description": "新しい要件の追加",
        "clause": "5.2.1"
      }
    ],
    "issues": [
      {
        "description": "既存仕様との整合性確認が必要",
        "severity": "medium"
      }
    ],
    "evidences": [
      {
        "text": "The UE shall support...",
        "contribution_number": "S1-234567",
        "clause_number": "5.2.1",
        "page_number": 12,
        "score": 0.92
      }
    ]
  },
  "review_sheet_url": "/api/downloads/rs-12345",
  "created_at": "2025-01-29T12:00:00Z",
  "completed_at": "2025-01-29T12:00:30Z"
}
```

**ステータス**

| status | 説明 |
|--------|------|
| processing | 処理中 |
| completed | 完了 |
| failed | 失敗 |

---

### GET /api/analysis/{id}/stream

分析結果をストリーミングで取得する（SSE）。

**レスポンス（SSE）**

```
event: progress
data: {"stage": "fetching", "progress": 10}

event: progress
data: {"stage": "analyzing", "progress": 50}

event: partial
data: {"summary": "要点: 本寄書は..."}

event: complete
data: {"analysis_id": "ana-12345", "status": "completed"}
```

**イベントタイプ**

| event | 説明 |
|-------|------|
| progress | 進捗情報 |
| partial | 部分結果 |
| complete | 完了通知 |
| error | エラー通知 |

---

### GET /api/downloads/{id}

成果物をダウンロードする。

**レスポンス**

- 302 Redirect to signed URL
- または直接ファイルストリーム

**ヘッダー**

```
Content-Type: text/markdown
Content-Disposition: attachment; filename="review-sheet-S1-234567.md"
```

---

## 4. 内部API

> **注意**: これらのAPIは内部使用専用であり、外部公開しない

### POST /internal/sync

FTPからメタデータを同期する。

**リクエスト**

```json
{
  "meeting": "SA1#111",
  "force": false
}
```

**レスポンス**

```json
{
  "synced_count": 150,
  "new_contributions": ["S1-234567", "S1-234568"],
  "updated_contributions": [],
  "errors": []
}
```

---

### POST /internal/normalize

ファイルを正規化する。

**リクエスト**

```json
{
  "contribution_number": "S1-234567"
}
```

**レスポンス**

```json
{
  "document_id": "doc-12345",
  "normalized_files": ["S1-234567.docx"],
  "chunk_count": 45,
  "processing_time_ms": 1234
}
```

---

### POST /internal/index

ベクトルインデックスを作成する。

**リクエスト**

```json
{
  "document_ids": ["doc-12345", "doc-12346"]
}
```

**レスポンス**

```json
{
  "indexed_count": 90,
  "total_chunks": 90,
  "processing_time_ms": 5678
}
```

---

## 5. エラーハンドリング

### 5.1 エラーレスポンス形式

```json
{
  "error": {
    "code": "ANALYSIS_FAILED",
    "message": "分析処理に失敗しました",
    "details": {
      "reason": "contribution not found",
      "contribution_number": "S1-999999"
    }
  }
}
```

### 5.2 エラーコード

| コード | 説明 |
|--------|------|
| INVALID_REQUEST | リクエスト形式エラー |
| UNAUTHORIZED | 認証エラー |
| FORBIDDEN | 認可エラー |
| NOT_FOUND | リソース不存在 |
| ANALYSIS_FAILED | 分析処理失敗 |
| INTERNAL_ERROR | サーバー内部エラー |

### 5.3 HTTPステータスコード

| コード | 用途 |
|--------|------|
| 200 | 成功 |
| 201 | 作成成功 |
| 302 | リダイレクト（ダウンロード） |
| 400 | リクエストエラー |
| 401 | 認証エラー |
| 403 | 認可エラー |
| 404 | リソース不存在 |
| 500 | サーバーエラー |

---

## 6. レート制限

| エンドポイント | 制限 |
|---------------|------|
| POST /api/analysis | 10 req/min/user |
| GET /api/analysis/* | 60 req/min/user |
| GET /api/downloads/* | 30 req/min/user |
