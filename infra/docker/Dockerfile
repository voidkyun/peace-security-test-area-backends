# モノレポ用共通イメージ（4 Django サービス + shared）
# 各サービスは compose でコマンドを上書きして起動する
FROM python:3.12-slim

WORKDIR /app

# Poetry インストール
ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
ENV PATH="${POETRY_HOME}/bin:${PATH}"
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# プロジェクトコピー
COPY pyproject.toml poetry.lock* ./
COPY shared ./shared
COPY services ./services

# 依存関係 + shared パッケージをインストール（仮想環境を使わずシステムにインストール）
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction

# デフォルトは Root サービス（compose で上書き可能）
ENV DJANGO_SETTINGS_MODULE=root.settings
EXPOSE 8000
CMD ["python", "services/root/manage.py", "runserver", "0.0.0.0:8000"]
