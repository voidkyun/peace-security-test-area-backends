# Peace Security Test Area Backends

Discordコミュニティ「平和保障試験区 - アマテラス」のバックエンド群です。  
三権分立を模した複数のサービス（Root / 立法 / 司法 / 行政）により、意思決定を相互承認で成立させ、監査ログを改ざん検出可能な形で保存します。

本リポジトリは **単一Gitリポジトリ内に複数Djangoプロジェクトを配置し、デプロイ単位は分離**する構成を採用します。

---

## 目的

- 意思決定の最小単位を Proposal とし、他2系統の承認を必須とする（承認の承認は行わない）
- 法（憲法・下位法）は実装から分離し、version管理可能なデータとして扱う
- Rootに監査ログを集中管理し、ハッシュチェーンで改ざん検出可能にする
- Rootは公開索引（Proposal Index）と閲覧APIを担い、各系統は実体（Proposal等）を保持する

---

## 構成

### サービス

- Root（公開窓口・監査ログ・Proposal索引）
- 規範生成系（立法）
- 法則審査系（司法）
- 秩序実行系（行政）

### 全体関係

```mermaid
flowchart TB
  ROOT[Root]
  L[規範生成系]
  J[法則審査系]
  E[秩序実行系]

  ROOT --> L
  ROOT --> J
  ROOT --> E

  L -->|Proposal| J
  L -->|Proposal| E

  E -->|Proposal| L
  E -->|Proposal| J

  J -->|Approval| L
  J -->|Approval| E
````

---

## ディレクトリ構成（想定）

```
services/
  root/
  legislative/
  judiciary/
  executive/
shared/
  audit/
  auth/
  ids/
  common_schemas/
infra/
  docker/
```

* `services/*` はそれぞれ独立したDjangoプロジェクト（分離デプロイ前提）
* 各サービスの設定は `settings/base.py`（共通）・`settings/dev.py`（開発）・`settings/prod.py`（本番）に分割。Docker では `root.settings.dev` / `root.settings.prod` のように指定。
* `shared/*` は共通の制度基盤（認証・監査・ID・共通スキーマ等）

---

## 意思決定モデル（要点）

* Proposalを発議した系統（origin）が Proposal を保持し、確定（finalize）もoriginが行う
* 確定には「他2系統からのAPPROVEが2件」必要
* Proposal作成時点の `law_context`（法体系スナップショット）は固定
* Rootは Proposal Index（参照URL等）を保持し、公開・検索の入口を提供する

---

## 監査ログ（要点）

* 監査ログはRootに集中
* append-only（追記専用）
* ハッシュチェーン（prev_hash -> hash）により改ざん検出可能

---

## セットアップ（開発環境）

### 前提

* Docker / Docker Compose
* Python（ローカル実行する場合）
* Poetry

### 1) 環境変数

`.env.example` を `.env` にコピーし、必要値を設定します。**Docker Compose 利用時は `.env` が必須です。**

```bash
cp .env.example .env
```

- `SECRET_KEY`: 各 Django サービス用（開発時はそのままで可）
- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`: PostgreSQL 用（Docker では 4 サービスが共通の postgres コンテナを利用し、DB は root_db / legislative_db / judiciary_db / executive_db に分離）
- `ALLOWED_HOSTS`: 本番（`docker-compose.prod.yml`）利用時は必須。カンマ区切りでホスト名を指定。

### 2) 起動（Docker Compose）

**dev（デフォルト）**: コンテナ起動時は runserver は動かさず、コンテナ内で bash してマイグレーション・runserver などを実行する想定です。

```bash
docker compose up --build
# 例: docker compose exec root bash のあと、以下で runserver を起動する
#      ※ Docker 内ではホストから接続できるよう、必ず 0.0.0.0 を指定すること（8080 だけだと 127.0.0.1 にしかバインドされずブラウザでつながらない）
# python services/root/manage.py runserver 0.0.0.0:8080
# 他サービスも同様（legislative / judiciary / executive はコンテナ内で runserver 0.0.0.0:8080 後、内部ネットワークで http://legislative:8080 等でアクセス可能）
```

- **postgres**: 1 コンテナで 4 データベース（root_db, legislative_db, judiciary_db, executive_db）を用意。初回起動時に `infra/docker/init-dbs.sql` で自動作成。
- **外部ポート公開は root のみ（8080）**。立法・司法・行政は内部ネットワーク限定で、他サービスや root コンテナからサービス名で HTTP アクセス可能。
- **healthcheck**: postgres および各 Django サービスに設定済み。アプリは `manage.py check --database default` で DB 接続を確認。
- 初回のみ、各サービスでマイグレーションを実行: `docker compose exec root python services/root/manage.py migrate` など。

**prod**: 本番用は `docker-compose.prod.yml` を併用し、**gunicorn**（WSGI）で起動します。開発サーバー（runserver）は本番では使いません。

```bash
# 本番では .env に ALLOWED_HOSTS を設定すること
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

* 設定は各サービスで `settings.prod`（`DEBUG=False`、`ALLOWED_HOSTS` は環境変数必須）。
* ポート: ホストからは **Root の 8080 のみ** 公開。立法・司法・行政はコンテナ内では 8080 で待ち受け、他コンテナからは `http://legislative:8080` 等でアクセス。

### 3) 依存解決（ローカル）

```bash
poetry install
```

### 4) 各サービスの起動（ローカル）

リポジトリルートで実行します。

```bash
# Root サービス（ポート 8080。8000 は他ライブラリ競合を避けるため使用しません）
poetry run python services/root/manage.py runserver 8080

# 他サービスも同様（別ポートで起動）
poetry run python services/legislative/manage.py runserver 8081
poetry run python services/judiciary/manage.py runserver 8082
poetry run python services/executive/manage.py runserver 8083
```

### 5) マイグレーション（例）

各サービスでモデルを追加した場合、リポジトリルートで実行します。

```bash
poetry run python services/root/manage.py migrate
# 同様に legislative / judiciary / executive でも実行
```

---

## 認証（方針）

* 外部（Discord）からの入口はRootのみ
* サービス間通信は **mTLS + Service JWT** を本番想定
* 開発初期は Service JWT のみで立ち上げ、後からmTLSを追加できる層構造とします

---

## 開発ルール（最低限）

* 破壊的なAPI変更はOpenAPI差分で検出する（予定）
* 監査イベントは必ず `request_id` と `law_context` を付与する
* finalize条件（承認2件等）は共通バリデーションで強制する

---

## ライセンス

TBD

```
```
