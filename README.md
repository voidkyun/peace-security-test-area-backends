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

`.env.example` を `.env` にコピーし、必要値を設定します。

```bash
cp .env.example .env
```

（初期段階では最低限DB接続情報があれば起動可能な想定です）

### 2) 起動（Docker Compose）

```bash
docker compose up --build
```

* Rootのみ外部ポート公開
* 他サービスは内部ネットワークからのみ到達可能な想定です

### 3) 依存解決（ローカル）

```bash
poetry install
```

### 4) マイグレーション（例）

各サービス配下で実行します。

```bash
cd services/root
poetry run python manage.py migrate
```

同様に `services/legislative` / `services/judiciary` / `services/executive` でも実行します。

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
