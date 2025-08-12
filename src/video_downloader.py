"""
YouTube動画ダウンローダーモジュール（429エラー対応版）
"""

import os
import time
import random
import yt_dlp
from pathlib import Path
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    """YouTube動画のダウンローダー（429エラー対応版）"""

    def __init__(self, config):
        self.config = config
        self.downloads_dir = Path(os.getenv("DOWNLOADS_DIR", "downloads"))
        self.downloads_dir.mkdir(exist_ok=True)

        # User-Agentのリスト
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
        ]

    def download(self, url: str, quality: str = "best", max_retries: int = 5) -> Optional[str]:
        """
        YouTube動画をダウンロード（429エラー対応版）

        Args:
            url: YouTube動画のURL
            quality: 動画品質 ("best", "worst", "720p", etc.)
            max_retries: リトライ最大回数

        Returns:
            ダウンロードされた動画ファイルのパス
        """
        wait_time = 20  # 初回待機時間（秒）

        for attempt in range(max_retries):
            try:
                logger.info(f"ダウンロード試行 {attempt + 1}/{max_retries}")

                # リトライ時は待機
                if attempt > 0:
                    jitter = random.uniform(0.8, 1.2)  # ジッター追加
                    actual_wait = wait_time * jitter
                    logger.info(f"{actual_wait:.1f}秒待機中...")
                    time.sleep(actual_wait)

                # yt-dlpオプションを動的に設定
                if attempt == 0:
                    # 初回は通常のオプションを試行
                    ydl_opts = self._get_ydl_options(quality, attempt, max_retries)
                else:
                    # リトライ時は安全なオプションを使用
                    logger.info("安全なオプションでリトライ中...")
                    ydl_opts = self._get_ydl_options_safe(quality, attempt, max_retries)

                # ダウンロード実行
                result = self._execute_download(url, ydl_opts)
                if result:
                    return result

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)

                if self._is_rate_limit_error(error_msg):
                    wait_time = min(wait_time * 1.5, 300)  # 最大5分
                    logger.warning(f"レート制限エラー発生 (試行 {attempt + 1}/{max_retries})")
                    logger.warning(f"次回は{wait_time:.1f}秒待機します")

                elif "Sign in to confirm" in error_msg:
                    logger.error("ボット検出エラー。60秒待機します")
                    time.sleep(60)

                else:
                    logger.error(f"ダウンロードエラー (リトライなし): {error_msg}")
                    break

            except Exception as e:
                import traceback
                error_type = type(e).__name__
                error_msg = str(e)

                logger.error(f"予期せぬエラー: {error_type}: {error_msg}")

                # AssertionErrorの場合の特別処理
                if error_type == "AssertionError" and "ImpersonateTarget" in traceback.format_exc():
                    logger.error("ブラウザ偽装機能の互換性エラーが発生しました")
                    logger.info("次回は安全なオプションでリトライします")
                elif error_type == "ImportError":
                    logger.error(f"モジュールの不足: {error_msg}")
                    if "curl_cffi" in error_msg:
                        logger.info("curl-cffiをインストールしてください: pip install curl-cffi")
                elif error_type in ["ConnectionError", "TimeoutError", "URLError"]:
                    logger.error("ネットワークエラーが発生しました")
                    if attempt < max_retries - 1:
                        logger.info("60秒待機してネットワーク接続を回復します")
                        time.sleep(60)
                        continue
                elif "unavailable" in error_msg.lower() or "private" in error_msg.lower():
                    logger.error("動画が利用できません（プライベート/削除済み/地域制限）")
                    break
                else:
                    logger.error(f"詳細スタックトレース:")
                    for line in traceback.format_exc().split('\n'):
                        if line.strip():
                            logger.error(f"  {line}")

                if attempt < max_retries - 1:
                    wait_time = 30 + (attempt * 15)
                    logger.info(f"{wait_time}秒待機してリトライします")
                    time.sleep(wait_time)
                else:
                    break

        logger.error("全てのリトライが失敗しました")
        return None

    def _get_ydl_options(self, quality: str, attempt: int, max_retries: int) -> dict:
        """yt-dlpのオプションを生成"""
        output_template = str(self.downloads_dir / "%(title)s.%(ext)s")

        # 基本オプション
        ydl_opts = {
            'format': self._get_format_selector(quality),
            'outtmpl': output_template,
            'writeinfojson': True,
            'ignoreerrors': False,
            'no_warnings': False,

            # レート制限対策
            'sleep_interval': random.uniform(2, 5),  # リクエスト間隔
            'max_sleep_interval': 15,
            'sleep_interval_subtitles': random.uniform(3, 6),

            # リトライ設定
            'retries': 3,
            'fragment_retries': 3,
            'file_access_retries': 3,

            # HTTPヘッダー
            'http_headers': {
                'User-Agent': random.choice(self.user_agents),
                'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
            },

            # Extractor設定
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'] if attempt > 0 else [],
                    'player_skip': ['configs'],
                }
            }
        }

        # 字幕設定（段階的に緩和）
        if attempt < max_retries - 2:
            # 通常時: 英語と日本語の字幕
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'ja'],
            })
        elif attempt == max_retries - 2:
            # 最後から2回目: 英語のみ
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
            })
            logger.info("字幕を英語のみに制限")
        else:
            # 最後の試行: 字幕なし
            ydl_opts.update({
                'writesubtitles': False,
                'writeautomaticsub': False,
            })
            logger.info("字幕ダウンロードを無効化")

        # プロキシ設定
        if self.config.get("proxy"):
            ydl_opts['proxy'] = self.config.get("proxy")

        # ブラウザ偽装（curl-cffiが利用可能な場合）
        try:
            import curl_cffi
            from yt_dlp.networking.impersonate import ImpersonateTarget

            # 利用可能なターゲットから選択
            available_targets = ['chrome', 'chrome-110', 'chrome-120', 'safari', 'safari-17']
            selected_target = random.choice(available_targets)

            try:
                # ImpersonateTargetオブジェクトを作成
                target = ImpersonateTarget.from_str(selected_target)
                ydl_opts['impersonate'] = target
                if attempt == 0:
                    logger.info(f"ブラウザ偽装機能を有効化: {selected_target}")
            except (AttributeError, ValueError) as e:
                # 古いバージョンの場合は文字列で試行
                ydl_opts['impersonate'] = selected_target
                if attempt == 0:
                    logger.info(f"ブラウザ偽装機能を有効化 (レガシー): {selected_target}")

        except ImportError:
            if attempt == 0:
                logger.warning("curl-cffiが未インストール (pip install curl-cffi)")
        except Exception as e:
            if attempt == 0:
                logger.warning(f"ブラウザ偽装の設定に失敗: {e}")
            # エラーが発生した場合はimpersonateオプションを削除
            ydl_opts.pop('impersonate', None)

    def _get_ydl_options_safe(self, quality: str, attempt: int, max_retries: int) -> dict:
        """yt-dlpのオプションを生成（安全版 - impersonateなし）"""
        output_template = str(self.downloads_dir / "%(title)s.%(ext)s")

        # 基本オプション
        ydl_opts = {
            'format': self._get_format_selector(quality),
            'outtmpl': output_template,
            'writeinfojson': True,
            'ignoreerrors': False,
            'no_warnings': False,

            # レート制限対策
            'sleep_interval': random.uniform(3, 7),  # より長い間隔
            'max_sleep_interval': 20,
            'sleep_interval_subtitles': random.uniform(5, 10),

            # リトライ設定
            'retries': 5,
            'fragment_retries': 5,
            'file_access_retries': 3,

            # HTTPヘッダー（シンプル版）
            'http_headers': {
                'User-Agent': random.choice(self.user_agents),
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
            },
        }

        # 字幕設定（段階的に緩和）
        if attempt < max_retries - 2:
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'ja'],
            })
        elif attempt == max_retries - 2:
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
            })
            logger.info("字幕を英語のみに制限")
        else:
            ydl_opts.update({
                'writesubtitles': False,
                'writeautomaticsub': False,
            })
            logger.info("字幕ダウンロードを無効化")

        # プロキシ設定
        if self.config.get("proxy"):
            ydl_opts['proxy'] = self.config.get("proxy")

        return ydl_opts

    def _execute_download(self, url: str, ydl_opts: dict) -> Optional[str]:
        """ダウンロードを実行"""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 動画情報取得
                logger.info("動画情報を取得中...")
                info = ydl.extract_info(url, download=False)
                video_title = self._sanitize_filename(info.get('title', 'video'))

                logger.info(f"タイトル: {video_title}")
                logger.info(f"再生時間: {info.get('duration', 0)}秒")
                logger.info(f"アップローダー: {info.get('uploader', 'Unknown')}")

                # 少し待機してからダウンロード
                time.sleep(random.uniform(1, 3))

                logger.info("ダウンロードを開始...")
                ydl.download([url])

                # ファイル検索
                video_file = self._find_downloaded_file(video_title)
                if video_file:
                    logger.info(f"✅ ダウンロード完了: {video_file}")
                    return str(video_file)
                else:
                    logger.error("❌ ダウンロードファイルが見つかりません")
                    return None

        except Exception as e:
            import traceback
            logger.error(f"_execute_download内でエラー: {type(e).__name__}: {str(e)}")
            logger.error(f"スタックトレース: {traceback.format_exc()}")
            raise  # 上位の例外ハンドラーに再送

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """レート制限エラーかどうかを判定"""
        rate_limit_keywords = [
            "HTTP Error 429",
            "Too Many Requests",
            "rate limit",
            "throttled",
        ]
        return any(keyword in error_msg for keyword in rate_limit_keywords)

    def _get_format_selector(self, quality: str) -> str:
        """品質設定に基づいてフォーマットセレクターを生成"""
        quality_map = {
            "best": "best[ext=mp4]/best",
            "worst": "worst[ext=mp4]/worst",
            "720p": "best[height<=720][ext=mp4]/best[height<=720]",
            "1080p": "best[height<=1080][ext=mp4]/best[height<=1080]",
            "480p": "best[height<=480][ext=mp4]/best[height<=480]",
            "audio": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
        }
        return quality_map.get(quality, "best[ext=mp4]/best")

    def _sanitize_filename(self, filename: str) -> str:
        """ファイル名から不正な文字を除去"""
        # 不正な文字を置換
        filename = re.sub(r'[<>:"/\\|?*\[\]]', '_', filename)
        # 制御文字を除去
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        # 連続するアンダースコアを1つに
        filename = re.sub(r'_+', '_', filename)
        # 前後の空白とピリオドを除去
        filename = filename.strip(' .')

        # 長すぎる場合は切り詰め
        if len(filename) > 100:
            filename = filename[:100].rstrip(' .')

        return filename or "video"  # 空の場合のフォールバック

    def _find_downloaded_file(self, title: str) -> Optional[Path]:
        """ダウンロードされたファイルを検索"""
        extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv']

        # 完全一致を優先して検索
        for ext in extensions:
            exact_match = self.downloads_dir / f"{title}{ext}"
            if exact_match.exists():
                return exact_match

        # 部分一致で検索
        for ext in extensions:
            for file_path in self.downloads_dir.glob(f"*{ext}"):
                if title in file_path.stem or file_path.stem in title:
                    return file_path

        # より緩い条件で再検索
        for file_path in self.downloads_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                # ファイル名の一部でも一致すれば候補とする
                title_words = set(re.findall(r'\w+', title.lower()))
                file_words = set(re.findall(r'\w+', file_path.stem.lower()))

                if title_words & file_words:  # 共通の単語があるか
                    return file_path

        return None

    def get_video_info(self, url: str, max_retries: int = 3) -> Optional[dict]:
        """動画の情報のみを取得（ダウンロードしない）"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 5 * (attempt + 1)
                    logger.info(f"情報取得リトライ ({attempt + 1}/{max_retries}) - {wait_time}秒待機")
                    time.sleep(wait_time)

                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'sleep_interval': 1,
                    'http_headers': {
                        'User-Agent': random.choice(self.user_agents),
                    }
                }

                # ブラウザ偽装
                try:
                    import curl_cffi
                    ydl_opts['impersonate'] = 'chrome120'
                except ImportError:
                    pass

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    return {
                        'title': info.get('title'),
                        'duration': info.get('duration'),
                        'uploader': info.get('uploader'),
                        'upload_date': info.get('upload_date'),
                        'view_count': info.get('view_count'),
                        'description': info.get('description'),
                        'thumbnail': info.get('thumbnail'),
                        'webpage_url': info.get('webpage_url'),
                    }

            except Exception as e:
                logger.error(f"動画情報取得エラー (試行 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None

        return None

    @staticmethod
    def check_dependencies() -> bool:
        """必要な依存関係をチェック"""
        missing_deps = []

        try:
            import curl_cffi
            logger.info("✅ curl-cffi: インストール済み")
        except ImportError:
            missing_deps.append("curl-cffi")
            logger.warning("❌ curl-cffi: 未インストール")

        if missing_deps:
            logger.warning("推奨依存関係をインストールしてください:")
            for dep in missing_deps:
                logger.warning(f"  pip install {dep}")

        return len(missing_deps) == 0

    def download_simple(self, url: str, quality: str = "best") -> Optional[str]:
        """
        シンプルなダウンロード（デバッグ用）
        エラーの詳細を確認するための最小限の実装
        """
        try:
            logger.info("=== シンプルダウンロード開始 ===")
            output_template = str(self.downloads_dir / "%(title)s.%(ext)s")

            # 最小限のオプション
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': output_template,
                'writeinfojson': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ignoreerrors': False,
                'no_warnings': False,
            }

            logger.info(f"URL: {url}")
            logger.info(f"出力先: {output_template}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("動画情報取得中...")
                info = ydl.extract_info(url, download=False)

                logger.info(f"タイトル: {info.get('title')}")
                logger.info(f"時間: {info.get('duration')}秒")

                logger.info("ダウンロード開始...")
                ydl.download([url])

                logger.info("ファイル検索中...")
                for file_path in self.downloads_dir.glob("*"):
                    if file_path.is_file():
                        logger.info(f"発見: {file_path}")
                        return str(file_path)

                logger.error("ファイルが見つかりません")
                return None

        except Exception as e:
            import traceback
            logger.error(f"シンプルダウンロードエラー: {type(e).__name__}")
            logger.error(f"エラーメッセージ: {str(e)}")
            logger.error(f"完全なスタックトレース:")
            for line in traceback.format_exc().split('\n'):
                logger.error(line)
            return None

    def test_connection(self, url: str) -> bool:
        """
        接続テスト用メソッド
        """
        try:
            logger.info("=== 接続テスト開始 ===")

            # 最小限のオプションで情報のみ取得
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,  # 高速化
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                logger.info(f"✅ 接続成功: {info.get('title', 'Unknown')}")
                return True

        except Exception as e:
            import traceback
            logger.error(f"❌ 接続テスト失敗: {type(e).__name__}: {str(e)}")
            logger.error(f"詳細: {traceback.format_exc()}")
            return False
