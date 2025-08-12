# YouTube動画翻訳システム

YouTubeの動画を自動でダウンロードし、音声を転写・翻訳して日本語字幕を埋め込むDockerベースのシステムです。

## 🚀 主な機能

### 現在の機能
- ✅ YouTube動画の高品質ダウンロード
- ✅ Whisper AIを使った高精度音声転写
- ✅ Google Translateによる多言語翻訳
- ✅ 動画への字幕焼き込み・ソフト字幕埋め込み
- ✅ 設定可能な字幕スタイル（フォント、色、サイズ）
- ✅ Dockerによる簡単な環境構築

### 将来の機能（実装予定）
- 🔄 AI APIを使った動画のハイライト抽出
- 🔄 見どころを10分程度に自動編集
- 🔄 Web UIでの操作
- 🔄 バッチ処理機能

## 📋 必要な環境

- Docker & Docker Compose
- 4GB以上のRAM（Whisperモデル用）
- 十分なストレージ容量（動画ファイル保存用）

## 🛠️ セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd youtube-video-translator
```

### 2. 環境変数の設定

`.env` ファイルを作成し、必要に応じて設定：

```bash
# AI編集機能を使う場合（オプション）
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Whisperモデル設定
WHISPER_MODEL=base  # tiny, base, small, medium, large

# その他の設定
DOWNLOAD_QUALITY=best
SUBTITLE_FONT_SIZE=20
```

### 3. Docker環境の構築

```bash
docker-compose build
```

## 📖 使用方法

### 基本的な使用方法

```bash
# 基本的な翻訳（日本語）
docker-compose run --rm youtube-translator "https://www.youtube.com/watch?v=VIDEO_ID"

# 韓国語に翻訳
docker-compose run --rm youtube-translator "https://www.youtube.com/watch?v=VIDEO_ID" --lang ko

# 処理後に一時ファイルを削除
docker-compose run --rm youtube-translator "https://www.youtube.com/watch?v=VIDEO_ID" --cleanup
```

### 対話モードで起動

```bash
docker-compose run --rm youtube-translator
# コンテナ内で以下のようにコマンドを実行
python src/main.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### 利用可能なオプション

```bash
python src/main.py <YouTube URL> [オプション]

オプション:
  --lang LANG      翻訳先言語コード（デフォルト: ja）
  --config PATH    設定ファイルのパス
  --cleanup        処理後に一時ファイルを削除
```

## 🎛️ 設定

設定は `config/config.yaml` で管理されます。主な設定項目：

### 音声認識設定
```yaml
whisper_model: "base"  # tiny, base, small, medium, large
```

### 字幕設定
```yaml
subtitle_font: "Arial"
subtitle_font_size: 20
subtitle_font_color: "white"
subtitle_outline_color: "black"
subtitle_outline_width: 1
subtitle_method: "burn"  # burn（焼き込み）or soft（外部字幕）
```

### ダウンロード設定
```yaml
download_quality: "best"  # best, worst, 720p, 1080p
proxy: null  # プロキシが必要な場合
```

### AI編集設定（将来機能）
```yaml
ai_editing:
  enabled: true
  api_provider: "openai"  # openai, anthropic
  model: "gpt-4"
  target_duration: 600  # 目標動画長（秒）
```

## 📁 ディレクトリ構造

```
.
├── src/                    # ソースコード
│   ├── main.py            # メインアプリケーション
│   ├── video_downloader.py # 動画ダウンローダー
│   ├── audio_processor.py  # 音声処理・転写
│   ├── translator.py      # 翻訳
│   ├── subtitle_embedder.py # 字幕埋め込み
│   ├── config_manager.py  # 設定管理
│   └── ai_editor.py       # AI編集（将来機能）
├── config/                # 設定ファイル
├── downloads/             # ダウンロード動画
├── output/               # 処理済み動画
├── temp/                # 一時ファイル
└── logs/                # ログファイル
```

## 🎯 対応言語

翻訳先言語として以下をサポート：
- `ja` - 日本語
- `en` - 英語
- `ko` - 韓国語
- `zh` - 中国語
- `es` - スペイン語
- `fr` - フランス語
- `de` - ドイツ語
- その他Google Translateが対応する言語

## 🔧 トラブルシューティング

### よくある問題

**1. 動画のダウンロードに失敗する**
```bash
# 動画が地域制限されている場合、プロキシを設定
# config/config.yaml の proxy 設定を確認
```

**2. 転写精度が低い**
```bash
# より高精度なWhisperモデルを使用
WHISPER_MODEL=medium  # または large
```

**3. 翻訳が失敗する**
```bash
# インターネット接続を確認
# Google Translateのレート制限に注意
```

**4. 字幕が見づらい**
```bash
# config.yaml で字幕スタイルを調整
subtitle_font_size: 24
subtitle_outline_width: 2
```

### ログの確認

```bash
# コンテナのログを確認
docker-compose logs youtube-translator

# ログファイルを直接確認
cat logs/app.log
```

## 🚀 将来の機能

### AI編集機能
- OpenAI GPT-4またはAnthropic Claudeを使用
- 動画の転写テキストを分析して見どころを特定
- 感情的インパクト、教育的価値、娯楽価値を評価
- 10分程度のハイライト動画を自動生成

### Web UI
- ブラウザベースの操作インターフェース
- 進捗状況のリアルタイム表示
- 複数動画の並列処理

## 📝 ライセンス

このプロジェクトは MIT License の下で公開されています。

## 🤝 コントリビューション

プルリクエストやイシューの報告を歓迎します。

## ⚠️ 注意事項

- YouTube動画のダウンロードは利用規約を遵守してください
- 著作権のある動画の取り扱いには注意が必要です
- AI API の使用には料金が発生する場合があります
- プライベート使用または教育目的での利用を推奨します
