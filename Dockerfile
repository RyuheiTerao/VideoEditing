# YouTube動画翻訳システム
FROM python:3.11-slim

# 必要なシステムパッケージをインストール
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    wget \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /app

# Pythonの依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY src/ ./src/
COPY config/ ./config/

# 必要なディレクトリを作成
RUN mkdir -p downloads output temp

# エントリーポイントスクリプトを実行可能にする
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# 環境変数を設定
ENV PYTHONPATH=/app/src
ENV DOWNLOADS_DIR=/app/downloads
ENV OUTPUT_DIR=/app/output
ENV TEMP_DIR=/app/temp

# ポートを公開（将来のWeb UI用）
EXPOSE 8000

# エントリーポイントを設定
ENTRYPOINT ["./entrypoint.sh"]
