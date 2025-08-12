#!/bin/bash
set -e

echo "YouTube動画翻訳システムを起動中..."

# ディレクトリの権限を確認・修正
echo "ディレクトリの権限を設定中..."
mkdir -p /app/downloads /app/output /app/temp /app/logs
chmod 755 /app/downloads /app/output /app/temp /app/logs

# 設定ファイルの存在確認
if [ ! -f "/app/config/config.yaml" ]; then
    echo "設定ファイルが見つからないため、デフォルト設定を作成します..."
    python3 -c "
from src.config_manager import ConfigManager
config = ConfigManager('/app/config/config.yaml')
config.save()
print('デフォルト設定ファイルを作成しました')
"
fi

# 引数によって実行方法を切り替え
if [ $# -eq 0 ]; then
    echo "対話モードで起動します..."
    echo "使用方法: python src/main.py <YouTube URL> [オプション]"
    echo ""
    echo "例:"
    echo "  python src/main.py https://www.youtube.com/watch?v=VIDEO_ID"
    echo "  python src/main.py https://www.youtube.com/watch?v=VIDEO_ID --lang ko"
    echo ""
    echo "オプション:"
    echo "  --lang LANG    翻訳先言語 (デフォルト: ja)"
    echo "  --config PATH  設定ファイルのパス"
    echo "  --cleanup      処理後に一時ファイルを削除"
    echo ""
    exec /bin/bash
elif [ "$1" = "web" ]; then
    echo "Web UIモードで起動します..."
    # 将来のWeb UI実装用
    exec python src/web_app.py
elif [ "$1" = "api" ]; then
    echo "APIサーバーモードで起動します..."
    exec uvicorn src.api:app --host 0.0.0.0 --port 8000
else
    echo "動画処理を開始します..."
    exec python src/main.py "$@"
fi
