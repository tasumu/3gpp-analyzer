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
  --set-env-vars "VERTEX_AI_LOCATION=global" \
  --set-env-vars "ANALYSIS_MODEL=gemini-2.5-flash" \
  --update-env-vars='^|^CORS_ORIGINS_STR=http://localhost:3000,https://your-frontend-url.hosted.app' \
  --update-env-vars='^|^INITIAL_ADMIN_EMAILS=admin@example.com'
```

> **Note**:
> - `CORS_ORIGINS_STR` はカンマ区切りで複数のオリジンを指定可能。ローカル開発用と本番用を両方含めることを推奨。gcloudでカンマを含む値を設定する場合は `--update-env-vars='^|^KEY=value'` 形式を使用。
> - `VERTEX_AI_LOCATION` は Vertex AI API のリージョン。デフォルトは `global`（全Geminiモデルが利用可能で、可用性が向上）。
> - `ANALYSIS_MODEL` は分析に使用する Gemini モデル。デフォルトは `gemini-2.5-flash`。
> - `INITIAL_ADMIN_EMAILS` は初期管理者のメールアドレス（カンマ区切りで複数指定可能）。このメールアドレスでログインすると自動的に管理者権限が付与されます。

#### ユーザー承認フロー（Admin Approval）

アプリケーションは初回ログイン時にユーザー承認フローを実装しています。

**初期管理者の設定（推奨：Secret Manager）**

機密性を考慮し、Secret Manager を使用することを推奨します：

```bash
# Secretを作成（複数の管理者を指定する場合はカンマ区切り）
echo -n "admin@example.com,admin2@example.com" | \
  gcloud secrets create initial-admin-emails --data-file=-

# Cloud Runサービスアカウントに権限を付与
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding initial-admin-emails \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Runサービスにシークレットをマウント
gcloud run services update 3gpp-analyzer-api \
  --region asia-northeast1 \
  --update-secrets="INITIAL_ADMIN_EMAILS=initial-admin-emails:latest"
```

**承認フローの動作**

1. **初期管理者**: `INITIAL_ADMIN_EMAILS` に含まれるメールアドレスでログインすると、自動的に `approved` 状態かつ `admin` ロールで登録されます
2. **一般ユーザー**: それ以外のメールアドレスでログインすると、`pending` 状態で登録され、「Approval Pending」画面が表示されます
3. **管理者による承認**: 管理者が `/admin/users` ページでユーザーを承認または拒否できます
4. **承認後**: 承認されたユーザーは通常通りアプリケーションにアクセスできます

**追加の管理者を設定する場合**

```bash
# 環境変数を直接更新
gcloud run services update 3gpp-analyzer-api \
  --region asia-northeast1 \
  --update-env-vars='^|^INITIAL_ADMIN_EMAILS=admin@example.com,admin2@example.com'

# またはSecret Managerを更新
echo -n "admin@example.com,admin2@example.com" | \
  gcloud secrets versions add initial-admin-emails --data-file=-
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
    location="global",  # VERTEX_AI_LOCATION
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

---

## セキュリティ設定（本番デプロイ前に必須）

本番環境への公開前に、以下のセキュリティ設定を必ず実施してください。

### 1. 環境変数の本番設定

```bash
# DEBUGを必ずfalseに設定（本番環境）
gcloud run services update 3gpp-analyzer-api \
  --region asia-northeast1 \
  --set-env-vars "DEBUG=false"

# CORS originsを本番URLのみに制限（localhostを除外）
gcloud run services update 3gpp-analyzer-api \
  --region asia-northeast1 \
  --update-env-vars='^|^CORS_ORIGINS_STR=https://your-production-frontend.hosted.app'
```

> **重要**: 本番環境では `CORS_ORIGINS_STR` に `localhost` を含めないでください。ローカル開発環境と本番環境で異なる設定を使用します。

### 2. Firestore/Storage ルールのデプロイ

承認ステータスチェックを含む最新のルールをデプロイ：

```bash
# ルールを本番環境にデプロイ
firebase deploy --only firestore:rules,storage

# デプロイ結果を確認
firebase firestore:rules:get
```

### 3. 依存パッケージのインストールとセキュリティスキャン

```bash
# バックエンドの依存パッケージをインストール
cd backend
uv sync

# セキュリティ脆弱性スキャン（オプション）
# pip install safety
# uv pip freeze | safety check --stdin
```

### 4. デプロイ前チェックリスト

以下の項目をすべて確認してからデプロイしてください：

- [ ] **DEBUG=false** が設定されている
- [ ] **CORS origins** が本番URLのみに制限されている（localhostを含まない）
- [ ] **Firestore/Storage ルール**が承認チェックを含む最新版
- [ ] **セキュリティヘッダー**が frontend/next.config.ts に設定されている
- [ ] **Rate limiting**が有効化されている（backend/src/analyzer/middleware/rate_limit.py）
- [ ] **機密情報のログマスク**が有効化されている（backend/src/analyzer/logging_config.py）
- [ ] **AdminUserDep**が internal API エンドポイントで使用されている
- [ ] **INITIAL_ADMIN_EMAILS**が Secret Manager に設定されている（推奨）

### 5. デプロイ後の検証

#### 5.1 セキュリティヘッダーの確認

```bash
# フロントエンドのセキュリティヘッダーを確認
curl -I https://your-frontend.hosted.app

# 必須ヘッダー:
# - Strict-Transport-Security
# - X-Content-Type-Options: nosniff
# - X-Frame-Options: DENY
# - Content-Security-Policy
# - Permissions-Policy
```

#### 5.2 CORS設定の確認

```bash
# CORSプリフライトリクエストをテスト
curl -X OPTIONS https://your-api.run.app/api/documents \
  -H "Origin: https://your-frontend.hosted.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" \
  -v

# 期待される結果:
# - Access-Control-Allow-Origin: https://your-frontend.hosted.app
# - Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
# - Access-Control-Allow-Headers に Authorization が含まれる
```

#### 5.3 認証・認可のテスト

```bash
# 1. 無効なトークンでアクセス → 401 Unauthorized
curl https://your-api.run.app/api/documents \
  -H "Authorization: Bearer invalid_token"

# 2. 認証なしでアクセス → 401 Unauthorized
curl https://your-api.run.app/api/documents

# 3. pending ユーザーでアクセス → 403 Forbidden
# (実際のユーザーでテスト)

# 4. approved ユーザーでアクセス → 200 OK
# (実際のユーザーでテスト)
```

#### 5.4 Storage Rulesのテスト

```bash
# Firebase Console → Firestore → Rules タブ
# Rules Playground でテスト:

# Test 1: pending ユーザーが /original/* を読む → Denied
# Test 2: approved ユーザーが /original/* を読む → Allowed
# Test 3: 認証なしで読む → Denied
```

#### 5.5 Rate Limitingのテスト

```bash
# 短時間に大量のリクエストを送信してテスト
for i in {1..20}; do
  curl https://your-api.run.app/api/documents \
    -H "Authorization: Bearer $TOKEN"
done

# 期待される結果:
# - 初期のリクエストは成功（200 OK）
# - 制限を超えると 429 Too Many Requests が返される
```

### 6. 監視とアラート

本番環境では以下の監視を設定することを推奨します：

#### Cloud Logging でのログ監視

```bash
# エラーログの確認
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=3gpp-analyzer-api \
  AND severity>=ERROR" \
  --limit=50 \
  --format=json

# 認証失敗のログ確認
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=3gpp-analyzer-api \
  AND textPayload=~'Unauthorized'" \
  --limit=50

# 機密情報がマスクされていることを確認
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=3gpp-analyzer-api" \
  --limit=100 | grep -i "password\|token\|api_key"
# 期待される結果: ***REDACTED*** のみ表示される
```

#### Cloud Monitoring アラート（オプション）

以下のアラートを設定することを推奨：

1. **高エラーレート**: エラーレート > 5%
2. **高レイテンシ**: P99 レイテンシ > 10秒
3. **認証失敗の急増**: 認証失敗が急激に増加
4. **Rate limit 超過**: 429エラーの急増

### 7. セキュリティベストプラクティス

#### 定期的なセキュリティレビュー

- **月次**: 依存パッケージの脆弱性スキャン
- **四半期**: アクセスログの監査
- **重要な変更前**: セキュリティレビューの実施

#### 依存パッケージの更新

```bash
# バックエンド
cd backend
uv lock --upgrade

# フロントエンド
cd frontend
npm update
npm audit fix
```

#### Secret Rotation

初期Admin メールアドレス等の機密情報は定期的にローテーションすることを推奨：

```bash
# Secret Manager の値を更新
echo -n "new-admin@example.com" | \
  gcloud secrets versions add initial-admin-emails --data-file=-

# Cloud Run を再起動して新しいシークレットを読み込み
gcloud run services update 3gpp-analyzer-api \
  --region asia-northeast1
```

---

## トラブルシューティング（セキュリティ関連）

### Rate Limiting で正常なユーザーがブロックされる

**症状**: 正常な使用でも 429 Too Many Requests が返される

**解決方法**:
```python
# backend/src/analyzer/middleware/rate_limit.py のレート制限を調整
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["600/minute"],  # 10 req/sec に緩和
    storage_uri="memory://",
)
```

### CSP エラーでフロントエンドが動作しない

**症状**: ブラウザコンソールに Content Security Policy エラー

**解決方法**:
```typescript
// frontend/next.config.ts の CSP を調整
// connect-src にAPIのドメインを追加
"connect-src 'self' https://*.run.app https://your-specific-api.run.app",
```

### Storage Rules でファイルアクセスができない

**症状**: approved ユーザーでもファイルダウンロードが失敗

**解決方法**:
```bash
# Firestore の users コレクションを確認
firebase firestore:get users/{uid}

# status が "approved" であることを確認
# 必要に応じて手動で更新
firebase firestore:update users/{uid} --data '{"status":"approved"}'
```
