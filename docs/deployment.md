# デプロイ手順

## 概要

GitHub への push をトリガーとして自動デプロイを行います。

| コンポーネント | デプロイ先 | リージョン |
|---------------|-----------|-----------|
| Backend (FastAPI) | Cloud Run | asia-northeast1（東京） |
| Frontend (Next.js) | Firebase App Hosting | 自動選択 |
| Firestore | Firestore | asia-northeast1（東京） |
| Cloud Storage | GCS | asia-northeast1（東京） |

## 事前準備

### 1. GCPプロジェクト設定

```bash
# プロジェクトID設定
export PROJECT_ID=your-project-id
gcloud config set project $PROJECT_ID

# 必要なAPIを有効化
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com
```

### 2. GCS バケット作成

```bash
gsutil mb -l asia-northeast1 gs://${PROJECT_ID}-3gpp-documents
```

### 3. Firestore データベース作成

```bash
gcloud firestore databases create --location=asia-northeast1
```

### 4. Firebase Authentication 設定

1. [Firebase Console](https://console.firebase.google.com/) にアクセス
2. プロジェクトを選択 → Authentication → 「始める」
3. 「Sign-in method」タブで「Google」を有効化
4. プロジェクトのサポートメールを設定して「保存」
5. 「Settings」タブ → 「承認済みドメイン」に App Hosting の URL を追加
   - 例: `threegpp-bff--your-project.asia-east1.hosted.app`

### 5. IAM署名権限設定（署名URL用）

Cloud Run から GCS の署名URL を生成するために、サービスアカウントに署名権限が必要です。

```bash
# Cloud Run のサービスアカウントを取得
SERVICE_ACCOUNT=$(gcloud run services describe 3gpp-analyzer-api \
  --region asia-northeast1 \
  --format='value(spec.template.spec.serviceAccountName)')

# デフォルトの場合はCompute Engine default service account
if [ -z "$SERVICE_ACCOUNT" ]; then
  PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
  SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi

# 署名権限を付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountTokenCreator"

echo "Service Account: $SERVICE_ACCOUNT"
```

> **Note**: この権限は GCS 署名URL 生成に必要です。Cloud Run 環境では秘密鍵がないため、IAM API を使用して署名を行います。

## バックエンドデプロイ

Cloud Run の継続的デプロイ機能を使用します。`cloudbuild.yaml` は不要で、Dockerfile のみで自動デプロイが可能です。

### Cloud Run 継続的デプロイ設定

1. [Cloud Run Console](https://console.cloud.google.com/run) にアクセス
2. 「サービスを作成」→「リポジトリから継続的にデプロイする」を選択
3. 「Cloud Build の設定」をクリック
4. GitHub リポジトリを接続（初回のみ認証が必要）
5. 設定:
   - リポジトリ: `3gpp-analyzer`
   - ブランチ: `^main$`
   - ソースの場所: `/backend/Dockerfile`
   - ビルドタイプ: Dockerfile
6. サービス設定:
   - サービス名: `3gpp-analyzer-api`
   - リージョン: `asia-northeast1`
   - 認証: 「未認証の呼び出しを許可」
7. 「作成」をクリック

> **Note**: Artifact Registry リポジトリやサービスアカウント権限は自動的に設定されます。

### 環境変数設定（デプロイ後）

```bash
# フロントエンドURLを取得（App Hosting デプロイ後）
# Firebase Console → App Hosting → URL を確認

gcloud run services update 3gpp-analyzer-api \
  --region asia-northeast1 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID}" \
  --set-env-vars "GCS_BUCKET_NAME=${PROJECT_ID}-3gpp-documents" \
  --set-env-vars "USE_FIREBASE_EMULATOR=false" \
  --set-env-vars "FTP_MOCK_MODE=false" \
  --set-env-vars "VERTEX_AI_LOCATION=us-central1" \
  --set-env-vars "ANALYSIS_MODEL=gemini-3-flash-preview" \
  --update-env-vars='^|^CORS_ORIGINS_STR=http://localhost:3000,https://your-frontend-url.hosted.app'
```

> **Note**:
> - `CORS_ORIGINS_STR` はカンマ区切りで複数のオリジンを指定可能。ローカル開発用と本番用を両方含めることを推奨。gcloudでカンマを含む値を設定する場合は `--update-env-vars='^|^KEY=value'` 形式を使用。
> - `VERTEX_AI_LOCATION` は Vertex AI API のリージョン。preview モデル（gemini-3-*-preview）を使用するため `us-central1` を指定。
> - `ANALYSIS_MODEL` は分析に使用する Gemini モデル。デフォルトは `gemini-3-flash-preview`。

## フロントエンドデプロイ

### Firebase App Hosting 設定

1. [Firebase Console](https://console.firebase.google.com/) にアクセス
2. プロジェクトを選択 → App Hosting
3. 「始める」をクリック
4. GitHub リポジトリを接続
5. 設定:
   - ルートディレクトリ: `frontend`
   - ライブブランチ: `main`

### 環境変数設定

デプロイ後、Cloud Run の URL を取得して設定:

```bash
# Cloud Run URL 取得
BACKEND_URL=$(gcloud run services describe 3gpp-analyzer-api \
  --region asia-northeast1 \
  --format='value(status.url)')

echo "Backend URL: $BACKEND_URL"
```

Cloud Secret Manager に API URL を設定:

```bash
# Firebase CLI でシークレット作成
# 改行文字が入らないよう printf を使用
printf 'https://3gpp-analyzer-api-xxxxx-an.a.run.app/api' | firebase apphosting:secrets:set api-url --force

# バックエンドにシークレットへのアクセス権限を付与
firebase apphosting:secrets:grantaccess api-url --backend <バックエンド名>
```

## デプロイフロー

```
GitHub (main branch)
    │
    ├─── backend/** 変更
    │       ↓
    │    Cloud Run 継続的デプロイ
    │       ↓
    │    1. Docker Build（自動）
    │    2. Deploy to Cloud Run
    │
    └─── frontend/** 変更
            ↓
         Firebase App Hosting
            ↓
         1. npm install
         2. npm run build
         3. Deploy
```

## 手動デプロイ（緊急時）

### バックエンド

```bash
cd backend
gcloud run deploy 3gpp-analyzer-api \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated
```

### フロントエンド

```bash
cd frontend
firebase apphosting:rollouts:create --branch main
```

## トラブルシューティング

### Cloud Run ビルド・デプロイ失敗

```bash
# 最新のビルドログ確認
gcloud builds list --limit=5
gcloud builds log BUILD_ID

# サービスログ確認
gcloud run services logs read 3gpp-analyzer-api --region asia-northeast1 --limit=50
```

### FTP 接続エラー

Cloud Run からの FTP 接続は通常動作しますが、問題がある場合:
- VPC コネクタ経由での接続を検討
- `FTP_MOCK_MODE=true` で一時的にモックモードで動作確認

### Vertex AI Embedding エラー

```
ValueError: Missing key inputs argument! To use the Google AI API, provide (api_key) arguments.
To use the Google Cloud API, provide (vertexai, project & location) arguments.
```

このエラーは `genai.Client()` の初期化パラメータが不足している場合に発生します。

**解決方法:**
```python
# 正しい初期化（Cloud Run / Vertex AI 環境）
from google import genai

client = genai.Client(
    vertexai=True,
    project=project_id,
    location="asia-northeast1",  # VERTEX_AI_LOCATION
)
```

### 署名URL生成エラー

```
AttributeError: you need a private key to sign credentials
```

このエラーは Cloud Run 環境で秘密鍵なしで署名URLを生成しようとした場合に発生します。

**解決方法:**
1. IAM署名権限を付与（上記「5. IAM署名権限設定」参照）
2. コードで IAM 署名を使用:
```python
from google.auth.transport import requests
import google.auth

credentials, project = google.auth.default()
auth_request = requests.Request()
credentials.refresh(auth_request)

url = blob.generate_signed_url(
    version="v4",
    expiration=timedelta(minutes=60),
    method="GET",
    service_account_email=credentials.service_account_email,
    access_token=credentials.token,
)
```
