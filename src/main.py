#!/usr/bin/env python3
"""
YouTube動画翻訳システム - メインアプリケーション (修正版)
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from colorlog import ColoredFormatter

from video_downloader import YouTubeDownloader
from audio_processor import AudioProcessor, validate_transcription_data
from translator import Translator, validate_srt_file
from subtitle_embedder import SubtitleEmbedder
from config_manager import ConfigManager

# 環境変数を読み込み
load_dotenv()

# ロガー設定
def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

logger = setup_logger()

class VideoTranslationPipeline:
    """動画翻訳パイプライン（修正版）"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = ConfigManager(config_path)
        self.downloader = YouTubeDownloader(self.config)
        self.audio_processor = AudioProcessor(self.config)
        self.translator = Translator(self.config)
        self.subtitle_embedder = SubtitleEmbedder(self.config)

    def process_video(self, youtube_url: str, target_lang: str = "ja") -> Optional[str]:
        """
        動画の処理パイプラインを実行（修正版）

        Args:
            youtube_url: YouTube動画のURL
            target_lang: 翻訳先言語コード

        Returns:
            処理済み動画のパス
        """
        video_path = None
        subtitle_path = None

        try:
            logger.info(f"動画処理を開始: {youtube_url}")
            logger.info(f"翻訳先言語: {target_lang}")

            # 1. 動画をダウンロード
            logger.info("=== Step 1: 動画ダウンロード ===")
            video_path = self.downloader.download(youtube_url)
            if not video_path:
                logger.error("動画のダウンロードに失敗しました")
                return None
            logger.info(f"ダウンロード完了: {video_path}")

            # 2. 音声を抽出して転写
            logger.info("=== Step 2: 音声転写 ===")
            transcript = self.audio_processor.extract_and_transcribe(video_path)
            if not transcript:
                logger.error("音声の転写に失敗しました")
                return None

            # 転写データの妥当性チェック
            if not validate_transcription_data(transcript):
                logger.error("転写データが不正です")
                return None

            logger.info(f"転写完了: {len(transcript.get('segments', []))} セグメント")

            # 3. 転写テキストを翻訳
            logger.info(f"=== Step 3: 翻訳 ({target_lang}) ===")
            translated_transcript = self.translator.translate_transcript(transcript, target_lang)
            if not translated_transcript:
                logger.error("翻訳に失敗しました")
                return None

            logger.info(f"翻訳完了: {len(translated_transcript.get('translated_segments', []))} セグメント")

            # 4. 字幕ファイルを生成
            logger.info("=== Step 4: 字幕ファイル生成 ===")
            subtitle_path = self.translator.create_subtitle_file(translated_transcript, video_path)
            if not subtitle_path:
                logger.error("字幕の生成に失敗しました")
                return None

            # 生成された字幕ファイルの妥当性チェック
            if not validate_srt_file(subtitle_path):
                logger.error("生成された字幕ファイルが不正です")

                # 修復を試行
                logger.info("字幕ファイルの修復を試行します...")
                from translator import repair_srt_file
                repaired_path = str(Path(subtitle_path).with_suffix('.repaired.srt'))
                if repair_srt_file(subtitle_path, repaired_path):
                    subtitle_path = repaired_path
                    logger.info(f"字幕ファイルを修復しました: {subtitle_path}")
                else:
                    logger.error("字幕ファイルの修復に失敗しました")
                    return None

            logger.info(f"字幕ファイル生成完了: {subtitle_path}")

            # 5. 字幕を動画に埋め込み
            logger.info("=== Step 5: 字幕埋め込み ===")
            output_path = self.subtitle_embedder.embed_subtitles(video_path, subtitle_path)
            if not output_path:
                logger.error("字幕の埋め込みに失敗しました")
                return None

            logger.info(f"✅ 処理完了: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"処理中にエラーが発生しました: {e}")
            import traceback
            logger.error(f"詳細エラー: {traceback.format_exc()}")
            return None

        finally:
            # クリーンアップ情報の表示
            logger.info("=== 処理結果 ===")
            if video_path and Path(video_path).exists():
                logger.info(f"動画ファイル: {video_path}")
            if subtitle_path and Path(subtitle_path).exists():
                logger.info(f"字幕ファイル: {subtitle_path}")

    def process_video_debug(self, youtube_url: str, target_lang: str = "ja") -> Optional[str]:
        """
        デバッグモードでの動画処理（詳細ログ付き）

        Args:
            youtube_url: YouTube動画のURL
            target_lang: 翻訳先言語コード

        Returns:
            処理済み動画のパス
        """
        try:
            logger.setLevel(logging.DEBUG)
            logger.info("=== デバッグモードで処理を開始 ===")

            result = self.process_video(youtube_url, target_lang)

            if result:
                logger.info("=== デバッグモード処理成功 ===")
            else:
                logger.error("=== デバッグモード処理失敗 ===")

            return result

        except Exception as e:
            logger.error(f"デバッグモード処理エラー: {e}")
            return None

    def test_components(self) -> bool:
        """各コンポーネントの動作テスト"""
        try:
            logger.info("=== コンポーネントテスト開始 ===")

            # 1. 設定テスト
            logger.info("設定テスト...")
            logger.info(f"翻訳方法: {self.config.get('translation_method', 'unknown')}")

            # 2. 翻訳機能テスト
            logger.info("翻訳テスト...")
            test_text = "This is a test."
            translated = self.translator.translate_text(test_text, "ja")
            logger.info(f"翻訳結果: '{test_text}' -> '{translated}'")

            # 3. 転写データテスト
            logger.info("転写データテスト...")
            from audio_processor import create_test_transcription
            test_transcript = create_test_transcription()
            is_valid = validate_transcription_data(test_transcript)
            logger.info(f"テスト転写データ妥当性: {is_valid}")

            # 4. 字幕ファイルテスト
            logger.info("字幕ファイルテスト...")
            from translator import create_test_srt
            test_srt_path = "/tmp/test.srt"
            if create_test_srt(test_srt_path):
                logger.info(f"テスト字幕ファイル作成成功: {test_srt_path}")

            logger.info("=== コンポーネントテスト完了 ===")
            return True

        except Exception as e:
            logger.error(f"コンポーネントテストエラー: {e}")
            return False

    def cleanup_temp_files(self):
        """一時ファイルをクリーンアップ"""
        try:
            logger.info("一時ファイルのクリーンアップを開始...")

            temp_dir = Path(os.getenv("TEMP_DIR", "temp"))
            downloads_dir = Path(os.getenv("DOWNLOADS_DIR", "downloads"))

            cleanup_dirs = [temp_dir]

            for directory in cleanup_dirs:
                if directory.exists():
                    temp_files = list(directory.glob("*"))
                    for file_path in temp_files:
                        try:
                            if file_path.is_file():
                                file_path.unlink()
                                logger.debug(f"削除: {file_path}")
                        except Exception as e:
                            logger.warning(f"ファイル削除失敗: {file_path} - {e}")

            # AudioProcessorのクリーンアップも呼び出し
            self.audio_processor.cleanup_temp_files()

            logger.info("一時ファイルのクリーンアップ完了")

        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")

def main():
    parser = argparse.ArgumentParser(description="YouTube動画翻訳システム (修正版)")
    parser.add_argument("url", nargs='?', help="YouTube動画のURL")
    parser.add_argument("--lang", default="ja", help="翻訳先言語コード (デフォルト: ja)")
    parser.add_argument("--config", default="config/config.yaml", help="設定ファイルのパス")
    parser.add_argument("--cleanup", action="store_true", help="処理後に一時ファイルを削除")
    parser.add_argument("--debug", action="store_true", help="デバッグモードで実行")
    parser.add_argument("--test", action="store_true", help="コンポーネントテストを実行")

    args = parser.parse_args()

    # テストモード
    if args.test:
        pipeline = VideoTranslationPipeline(args.config)
        success = pipeline.test_components()
        sys.exit(0 if success else 1)

    # URLが指定されていない場合
    if not args.url:
        logger.error("YouTube動画のURLを指定してください")
        logger.info("使用例: python main.py https://www.youtube.com/watch?v=VIDEO_ID")
        parser.print_help()
        sys.exit(1)

    # パイプライン実行
    pipeline = VideoTranslationPipeline(args.config)

    try:
        # デバッグモードの判定
        if args.debug:
            output_path = pipeline.process_video_debug(args.url, args.lang)
        else:
            output_path = pipeline.process_video(args.url, args.lang)

        if output_path:
            logger.info("=" * 50)
            logger.info("✅ 処理が完了しました！")
            logger.info(f"📁 出力ファイル: {output_path}")
            logger.info("=" * 50)
        else:
            logger.error("=" * 50)
            logger.error("❌ 処理に失敗しました")
            logger.error("=" * 50)
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("処理が中断されました")
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        sys.exit(1)
    finally:
        if args.cleanup:
            pipeline.cleanup_temp_files()

if __name__ == "__main__":
    main()
