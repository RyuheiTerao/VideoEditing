#!/usr/bin/env python3
"""
YouTube動画翻訳システム - メインアプリケーション
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
from audio_processor import AudioProcessor
from translator import Translator
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
    """動画翻訳パイプライン"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = ConfigManager(config_path)
        self.downloader = YouTubeDownloader(self.config)
        self.audio_processor = AudioProcessor(self.config)
        self.translator = Translator(self.config)
        self.subtitle_embedder = SubtitleEmbedder(self.config)

    def process_video(self, youtube_url: str, target_lang: str = "ja") -> Optional[str]:
        """
        動画の処理パイプラインを実行

        Args:
            youtube_url: YouTube動画のURL
            target_lang: 翻訳先言語コード

        Returns:
            処理済み動画のパス
        """
        try:
            logger.info(f"動画処理を開始: {youtube_url}")

            # 1. 動画をダウンロード
            logger.info("動画をダウンロード中...")
            video_path = self.downloader.download(youtube_url)
            if not video_path:
                logger.error("動画のダウンロードに失敗しました")
                return None

            # 2. 音声を抽出して転写
            logger.info("音声を転写中...")
            transcript = self.audio_processor.extract_and_transcribe(video_path)
            if not transcript:
                logger.error("音声の転写に失敗しました")
                return None

            # 3. 転写テキストを翻訳
            logger.info(f"テキストを{target_lang}に翻訳中...")
            translated_text = self.translator.translate_transcript(transcript, target_lang)
            if not translated_text:
                logger.error("翻訳に失敗しました")
                return None

            # 4. 字幕を生成
            logger.info("字幕を生成中...")
            subtitle_path = self.translator.create_subtitle_file(translated_text, video_path)
            if not subtitle_path:
                logger.error("字幕の生成に失敗しました")
                return None

            # 5. 字幕を動画に埋め込み
            logger.info("字幕を動画に埋め込み中...")
            output_path = self.subtitle_embedder.embed_subtitles(video_path, subtitle_path)
            if not output_path:
                logger.error("字幕の埋め込みに失敗しました")
                return None

            logger.info(f"処理完了: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"処理中にエラーが発生しました: {e}")
            return None

    def cleanup_temp_files(self):
        """一時ファイルをクリーンアップ"""
        temp_dir = Path(os.getenv("TEMP_DIR", "temp"))
        if temp_dir.exists():
            for file_path in temp_dir.glob("*"):
                try:
                    file_path.unlink()
                    logger.info(f"一時ファイルを削除: {file_path}")
                except Exception as e:
                    logger.warning(f"ファイル削除に失敗: {file_path} - {e}")

def main():
    parser = argparse.ArgumentParser(description="YouTube動画翻訳システム")
    parser.add_argument("url", help="YouTube動画のURL")
    parser.add_argument("--lang", default="ja", help="翻訳先言語コード (デフォルト: ja)")
    parser.add_argument("--config", default="config/config.yaml", help="設定ファイルのパス")
    parser.add_argument("--cleanup", action="store_true", help="処理後に一時ファイルを削除")

    args = parser.parse_args()

    # パイプライン実行
    pipeline = VideoTranslationPipeline(args.config)

    try:
        output_path = pipeline.process_video(args.url, args.lang)

        if output_path:
            logger.info(f"✅ 処理が完了しました！")
            logger.info(f"📁 出力ファイル: {output_path}")
        else:
            logger.error("❌ 処理に失敗しました")
            sys.exit(1)

    finally:
        if args.cleanup:
            pipeline.cleanup_temp_files()

if __name__ == "__main__":
    main()
