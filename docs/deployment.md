# デプロイ手順

## 概要

GitHub への push をトリガーとして自動デプロイを行います。

| コンポーネント | デプロイ先 | トリガー |
|---------------|-----------|---------|
| Backend (FastAPI) | Cloud Run | Cloud Build |
| Frontend (Next.js) | Firebase App Hosting | Firebase |

## 事前準備

### 1. GCPプロジェクト設定

```bash
# プロジェクトID設定
export PROJECT_ID=your-project-id
gcloud config set project $PROJECT_ID

# 必要なAPIを有効化
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com
```

### 2. Artifact Registry リポジトリ作成

```bash
gcloud artifacts repositories create 3gpp-analyzer \
  --repository-format=docker \
  --location=asia-northeast1 \
  --description="3GPP Analyzer container images"
```

### 3. GCS バケット作成

```bash
gsutil mb -l asia-northeast1 gs://${PROJECT_ID}-3gpp-documents
```

### 4. Firestore データベース作成

```bash
gcloud firestore databases create --location=asia-northeast1
```

## バックエンドデプロイ

### Cloud Build トリガー設定

1. [Cloud Build トリガー](https://console.cloud.google.com/cloud-build/triggers) にアクセス
2. 「リポジトリを接続」から GitHub リポジトリを接続
3. 「トリガーを作成」:
   - 名前: `deploy-backend`
   - イベント: ブランチに push する
   - ソース: `^main$`
   - 構成: Cloud Build 構成ファイル
   - 場所: `backend/cloudbuild.yaml`
   - 含まれるファイル: `backend/**`

または CLI で:

```bash
gcloud builds triggers create github \
  --name="deploy-backend" \
  --repo-owner="YOUR_GITHUB_USERNAME" \
  --repo-name="3gpp-analyzer" \
  --branch-pattern="^main$" \
  --build-config="backend/cloudbuild.yaml" \
  --included-files="backend/**"
```

### Cloud Build サービスアカウント権限

```bash
# プロジェクト番号取得
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Cloud Run Admin 権限付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"

# サービスアカウントユーザー権限付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### 環境変数設定（デプロイ後）

```bash
gcloud run services update 3gpp-analyzer-api \
  --region asia-northeast1 \
  --set-env-vars "GCS_BUCKET_NAME=${PROJECT_ID}-3gpp-documents" \
  --set-env-vars "CORS_ORIGINS=[\"https://your-frontend-url.web.app\"]"
```

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

Firebase Console → App Hosting → 環境変数で設定:
- `NEXT_PUBLIC_API_URL`: `https://3gpp-analyzer-api-xxxxx-an.a.run.app/api`

または Secret Manager を使用:

```bash
# シークレット作成
echo -n "https://3gpp-analyzer-api-xxxxx-an.a.run.app/api" | \
  gcloud secrets create BACKEND_API_URL --data-file=-

# App Hosting からアクセス許可
gcloud secrets add-iam-policy-binding BACKEND_API_URL \
  --member="serviceAccount:firebase-app-hosting-compute@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## デプロイフロー

```
GitHub (main branch)
    │
    ├─── backend/** 変更
    │       ↓
    │    Cloud Build Trigger
    │       ↓
    │    1. Docker Build
    │    2. Push to Artifact Registry
    │    3. Deploy to Cloud Run
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
gcloud builds submit --config=cloudbuild.yaml
```

### フロントエンド

```bash
cd frontend
firebase apphosting:rollouts:create --branch main
```

## トラブルシューティング

### Cloud Build 失敗

```bash
# ビルドログ確認
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

### Cloud Run 起動失敗

```bash
# ログ確認
gcloud run services logs read 3gpp-analyzer-api --region asia-northeast1 --limit=50
```

### FTP 接続エラー

Cloud Run からの FTP 接続は通常動作しますが、問題がある場合:
- VPC コネクタ経由での接続を検討
- `FTP_MOCK_MODE=true` で一時的にモックモードで動作確認
