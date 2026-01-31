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
  secretmanager.googleapis.com
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
  --update-env-vars='^|^CORS_ORIGINS_STR=http://localhost:3000,https://your-frontend-url.hosted.app'
```

> **Note**: `CORS_ORIGINS_STR` はカンマ区切りで複数のオリジンを指定可能。ローカル開発用と本番用を両方含めることを推奨。gcloudでカンマを含む値を設定する場合は `--update-env-vars='^|^KEY=value'` 形式を使用。

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
