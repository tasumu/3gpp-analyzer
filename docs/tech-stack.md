# 技術スタック

このドキュメントは、プロジェクトで使用している技術スタックをまとめたものです。

## フロントエンド

| カテゴリ | 技術 | バージョン | 備考 |
|---------|------|-----------|------|
| フレームワーク | Next.js | 16.x | App Router使用、`output: "standalone"` |
| 言語 | TypeScript | 5.x | strict mode |
| UIライブラリ | React | 19.x | Server/Client Components |
| スタイリング | Tailwind CSS | 4.x | `@import "tailwindcss"` 形式 |
| ユーティリティ | use-debounce | 10.x | デバウンス処理 |
| 認証 | Firebase Auth SDK | 12.x | メール/パスワード認証 |

### 主要な設定

**TypeScript設定**
- `target`: ES2017
- `moduleResolution`: bundler
- パスエイリアス: `@/*` → `./src/*`

**Next.js設定**
- API Rewrite: `/api/*` → バックエンドURL
- Output: standalone（コンテナデプロイ向け）

## バックエンド

| カテゴリ | 技術 | バージョン | 備考 |
|---------|------|-----------|------|
| 言語 | Python | 3.12+ | |
| フレームワーク | FastAPI | 0.115+ | 非同期対応 |
| サーバー | Uvicorn | 0.30+ | ASGI、`--reload` 対応 |
| パッケージ管理 | uv | latest | 高速なパッケージマネージャ |
| バリデーション | Pydantic | 2.x | `pydantic-settings`含む |
| ストリーミング | sse-starlette | 2.x | Server-Sent Events |

### 開発ツール

| ツール | バージョン | 用途 |
|--------|-----------|------|
| Ruff | 0.5+ | Linter / Formatter |
| pytest | 8.x | テスト |
| pytest-asyncio | 0.23+ | 非同期テスト |

### Ruff設定

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

## AI/LLM

| カテゴリ | 技術 | バージョン | 備考 |
|---------|------|-----------|------|
| Agent Framework | Google ADK | 1.x | Agent Development Kit |
| LLM SDK | google-genai | 1.x | Gemini / Embedding API クライアント |
| LLMモデル | Gemini | - | `gemini-3-flash-preview` 等 |
| Embeddingモデル | text-embedding-004 | - | 768次元、Vertex AI 経由 |
| LLM接続 | Vertex AI | - | 本番環境で使用（サービスアカウント認証） |

### Vertex AI 初期化

Cloud Run 環境では Vertex AI モードで `genai.Client` を初期化:

```python
from google import genai

client = genai.Client(
    vertexai=True,
    project="your-project-id",
    location="asia-northeast1",
)

# Embedding生成
response = client.models.embed_content(
    model="text-embedding-004",
    contents=["テキスト"],
    config={"output_dimensionality": 768},
)
```

## Firebase / GCP

| カテゴリ | 技術 | 用途 |
|---------|------|------|
| 認証 | Firebase Auth | ユーザー認証（メール/パスワード） |
| データベース | Firestore | NoSQL ドキュメントDB + ベクトル検索 |
| ベクトル検索 | Firestore Vector Search | Firestoreに統合されたベクトル検索 |
| ファイルストレージ | Cloud Storage (GCS) | 元ファイル、正規化済みファイル、生成物 |
| Admin SDK | firebase-admin 6.5+ | サーバーサイドFirebase操作 |
| Firestore SDK | google-cloud-firestore 2.16+ | Firestoreクライアント |
| Storage SDK | google-cloud-storage 2.x | GCSクライアント |

### 署名URL生成（Cloud Run環境）

Cloud Run では秘密鍵がないため、IAM API を使用して署名URL を生成:

```python
import google.auth
from google.auth.transport import requests

credentials, project = google.auth.default()
credentials.refresh(requests.Request())

url = blob.generate_signed_url(
    version="v4",
    expiration=timedelta(minutes=60),
    method="GET",
    service_account_email=credentials.service_account_email,
    access_token=credentials.token,
)
```

> **必要な権限**: `roles/iam.serviceAccountTokenCreator`

### ストレージ構成

```
Firestore
├── documents/           # Document メタデータ
├── chunks/              # Chunk + embedding
├── analysis_results/    # 分析結果
└── users/               # ユーザー情報

Cloud Storage (GCS)
├── original/            # FTPからDLした元ファイル
├── normalized/          # 正規化済み docx
└── outputs/             # レビューシート等
```

### ローカル開発

| ツール | ポート | 用途 |
|--------|-------|------|
| Firebase Emulator (Auth) | 9099 | 認証エミュレーション |
| Firebase Emulator (Firestore) | 8080 | DBエミュレーション |
| Firebase Emulator (Storage) | 9199 | Storageエミュレーション |
| Firebase Emulator UI | 4000 | エミュレーター管理UI |

## インフラストラクチャ

### 本番環境

| サービス | 用途 | 備考 |
|---------|------|------|
| Firebase App Hosting | フロントエンド | Next.js standalone |
| Cloud Run | バックエンド | Docker コンテナ |
| Firestore | データベース | 本番環境 |
| Firebase Auth | 認証 | 本番環境 |

### コンテナ

**バックエンド Dockerfile**
- ベースイメージ: `python:3.12-slim`
- パッケージマネージャ: uv
- ポート: 8080
- サーバー: Uvicorn

### CI/CD

- GitHub push トリガーによる自動デプロイ

## バージョン一覧（まとめ）

### フロントエンド依存関係

```json
{
  "dependencies": {
    "firebase": "^12.8.0",
    "next": "16.1.4",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "use-debounce": "^10.1.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.1.4",
    "tailwindcss": "^4",
    "typescript": "^5"
  }
}
```

### バックエンド依存関係

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "google-cloud-firestore>=2.16.0",
    "google-cloud-storage>=2.14.0",
    "firebase-admin>=6.5.0",
    "google-adk>=1.0.0",
    "google-genai>=1.0.0",
    "python-docx>=1.1.0",
    "python-dotenv>=1.0.0",
    "sse-starlette>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.5.0",
]
```

## 開発コマンド

### バックエンド

```bash
# 起動
uv run uvicorn knowva.main:app --reload --port 8000

# Lint
uv run ruff check src/

# Format
uv run ruff format src/

# テスト
uv run pytest
```

### フロントエンド

```bash
# 起動
npm run dev

# ビルド
npm run build

# Lint
npm run lint
```

### Firebase Emulator

```bash
# データ永続化あり
firebase emulators:start --export-on-exit=./emulator-data --import=./emulator-data

# データ永続化なし
firebase emulators:start
```

## ブラウザAPI

| API | 用途 | ブラウザサポート |
|-----|------|-----------------|
| Web Speech API | 音声入力 | Chrome/Edge推奨 |
| EventSource | SSEストリーミング | 全モダンブラウザ |
