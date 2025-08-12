# YouTube動画翻訳システム - Makefile

.PHONY: help build up down restart logs clean setup test translate

# デフォルトターゲット
help:
	@echo "YouTube動画翻訳システム - 利用可能なコマンド:"
	@echo ""
	@echo "  make setup      - 初期セットアップを実行"
	@echo "  make build      - Dockerイメージをビルド"
	@echo "  make up         - コンテナを起動"
	@echo "  make down       - コンテナを停止・削除"
	@echo "  make restart    - コンテナを再起動"
	@echo "  make logs       - ログを表示"
	@echo "  make shell      - コンテナに接続"
	@echo "  make clean      - 一時ファイルをクリーンアップ"
	@echo "  make test       - テストを実行"
	@echo "  make translate URL=<YouTube URL> - 動画を翻訳"
	@echo ""
	@echo "例:"
	@echo "  make translate URL=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
	@echo "  make translate URL=https://www.youtube.com/watch?v=dQw4w9WgXcQ LANG=ko"

# 初期セットアップ
setup:
	@echo "初期セットアップを開始..."
	@mkdir -p downloads output temp logs config
	@touch downloads/.gitkeep output/.gitkeep temp/.gitkeep logs/.gitkeep
	@if [ ! -f .env ]; then \
		echo "# YouTube動画翻訳システム環境変数" > .env; \
		echo "WHISPER_MODEL=base" >> .env; \
		echo "DOWNLOAD_QUALITY=best" >> .env; \
		echo "SUBTITLE_FONT_SIZE=20" >> .env; \
		echo "# OPENAI_API_KEY=your_openai_api_key" >> .env; \
		echo "# ANTHROPIC_API_KEY=your_anthropic_api_key" >> .env; \
		echo ".env ファイルを作成しました。必要に応じて編集してください。"; \
	fi
	@echo "セットアップ完了！"

# Dockerイメージをビルド
build:
	@echo "Dockerイメージをビルド中..."
	@docker-compose build

# コンテナを起動
up:
	@echo "コンテナを起動中..."
	@docker-compose up -d

# コンテナを停止・削除
down:
	@echo "コンテナを停止中..."
	@docker-compose down

# コンテナを再起動
restart: down build up

# ログを表示
logs:
	@docker-compose logs -f youtube-translator

# コンテナに接続
shell:
	@docker-compose run --rm youtube-translator /bin/bash

# 動画を翻訳（メイン機能）
translate:
	@if [ -z "$(URL)" ]; then \
		echo "エラー: URLが指定されていません"; \
		echo "使用例: make translate URL=https://www.youtube.com/watch?v=VIDEO_ID"; \
		exit 1; \
	fi
	@echo "動画翻訳を開始: $(URL)"
	@if [ -n "$(LANG)" ]; then \
		docker-compose run --rm youtube-translator "$(URL)" --lang "$(LANG)" --cleanup; \
	else \
		docker-compose run --rm youtube-translator "$(URL)" --cleanup; \
	fi

# 複数の動画を処理（バッチ処理）
batch:
	@if [ -z "$(URLS_FILE)" ]; then \
		echo "エラー: URLS_FILEが指定されていません"; \
		echo "使用例: make batch URLS_FILE=urls.txt"; \
		exit 1; \
	fi
	@echo "バッチ処理を開始: $(URLS_FILE)"
	@while IFS= read -r url; do \
		if [ -n "$url" ] && [ "${url#\#}" = "$url" ]; then \
			echo "処理中: $url"; \
			docker-compose run --rm youtube-translator "$url" --cleanup || echo "エラー: $url の処理に失敗"; \
		fi; \
	done < "$(URLS_FILE)"

# テストを実行
test:
	@echo "テストを実行中..."
	@docker-compose run --rm youtube-translator python -m pytest tests/ -v

# 開発環境でのテスト実行
test-dev:
	@echo "開発環境でテストを実行中..."
	@python -m pytest tests/ -v

# コードフォーマット
format:
	@echo "コードをフォーマット中..."
	@docker-compose run --rm youtube-translator python -m black src/
	@docker-compose run --rm youtube-translator python -m isort src/

# コード品質チェック
lint:
	@echo "コード品質をチェック中..."
	@docker-compose run --rm youtube-translator python -m flake8 src/
	@docker-compose run --rm youtube-translator python -m mypy src/

# 一時ファイルをクリーンアップ
clean:
	@echo "一時ファイルをクリーンアップ中..."
	@rm -rf temp/*
	@rm -rf downloads/*.part
	@rm -rf downloads/*.tmp
	@docker system prune -f
	@echo "クリーンアップ完了！"

# すべての出力ファイルを削除
clean-all: clean
	@echo "すべての出力ファイルを削除中..."
	@rm -rf downloads/* output/* logs/*
	@touch downloads/.gitkeep output/.gitkeep logs/.gitkeep
	@echo "すべてのファイルを削除しました！"

# ログファイルをアーカイブ
archive-logs:
	@echo "ログファイルをアーカイブ中..."
	@mkdir -p archive
	@tar -czf archive/logs_$(shell date +%Y%m%d_%H%M%S).tar.gz logs/
	@echo "ログをアーカイブしました: archive/logs_$(shell date +%Y%m%d_%H%M%S).tar.gz"

# 設定ファイルのバックアップ
backup-config:
	@echo "設定ファイルをバックアップ中..."
	@mkdir -p backup
	@cp config/config.yaml backup/config_$(shell date +%Y%m%d_%H%M%S).yaml
	@if [ -f .env ]; then cp .env backup/env_$(shell date +%Y%m%d_%H%M%S).txt; fi
	@echo "設定ファイルをバックアップしました！"

# システム情報を表示
info:
	@echo "=== システム情報 ==="
	@echo "Docker version:"
	@docker --version
	@echo ""
	@echo "Docker Compose version:"
	@docker-compose --version
	@echo ""
	@echo "利用可能なディスク容量:"
	@df -h . | tail -1
	@echo ""
	@echo "コンテナ状態:"
	@docker-compose ps

# 依存関係を更新
update-deps:
	@echo "依存関係を更新中..."
	@docker-compose run --rm youtube-translator pip list --outdated
	@echo "手動でrequirements.txtを更新してください"

# Web UIを起動（将来機能）
web:
	@echo "Web UIを起動中..."
	@docker-compose --profile web up -d
	@echo "Web UI: http://localhost:3000"

# API サーバーを起動（将来機能）
api:
	@echo "APIサーバーを起動中..."
	@docker-compose run --rm -p 8000:8000 youtube-translator api
	@echo "API サーバー: http://localhost:8000"

# ヘルプテキストファイルを生成
help-file:
	@echo "使用方法ドキュメントを生成中..."
	@make help > USAGE.txt
	@echo "USAGE.txtを作成しました"

# インストール検証
verify:
	@echo "インストールを検証中..."
	@docker-compose run --rm youtube-translator python -c "import whisper; import moviepy; import googletrans; print('すべてのライブラリが正常にインストールされています')"
	@echo "検証完了！"
