"""
字幕埋め込みモジュール
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class SubtitleEmbedder:
    """字幕を動画に埋め込むクラス"""

    def __init__(self, config):
        self.config = config
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        self.output_dir.mkdir(exist_ok=True)

        self.subtitle_method = config.get("subtitle_method", "burn")
        self.font_size = config.get("subtitle_font_size", 20)

    def embed_subtitles(self, video_path: str, subtitle_path: str) -> Optional[str]:
        """
        動画に字幕を埋め込み

        Args:
            video_path: 動画ファイルのパス
            subtitle_path: 字幕ファイルのパス

        Returns:
            字幕付き動画のパス
        """
        try:
            video_path = Path(video_path)
            subtitle_path = Path(subtitle_path)

            if not video_path.exists():
                logger.error(f"動画ファイルが見つかりません: {video_path}")
                return None

            if not subtitle_path.exists():
                logger.error(f"字幕ファイルが見つかりません: {subtitle_path}")
                return None

            # 出力ファイル名を生成
            output_filename = f"{video_path.stem}_subtitled.mp4"
            output_path = self.output_dir / output_filename

            logger.info(f"字幕埋め込み開始: {video_path} + {subtitle_path}")

            if self.subtitle_method == "burn":
                result = self._burn_subtitles(video_path, subtitle_path, output_path)
            else:
                result = self._soft_subtitles(video_path, subtitle_path, output_path)

            if result:
                logger.info(f"字幕埋め込み完了: {output_path}")
                return str(output_path)
            else:
                return None

        except Exception as e:
            logger.error(f"字幕埋め込みエラー: {e}")
            return None

    def _burn_subtitles(self, video_path: Path, subtitle_path: Path, output_path: Path) -> bool:
        """字幕を動画に焼き込み"""
        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", f"subtitles='{subtitle_path}':force_style='FontSize={self.font_size}'",
                "-c:a", "copy",
                "-y",
                str(output_path)
            ]

            logger.info("FFmpegで字幕焼き込み実行中...")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("字幕焼き込み成功")
                return True
            else:
                logger.error(f"FFmpegエラー: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"字幕焼き込みエラー: {e}")
            return False

    def _soft_subtitles(self, video_path: Path, subtitle_path: Path, output_path: Path) -> bool:
        """外部字幕として埋め込み"""
        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-i", str(subtitle_path),
                "-c", "copy",
                "-c:s", "mov_text",
                "-y",
                str(output_path)
            ]

            logger.info("FFmpegで外部字幕埋め込み実行中...")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("外部字幕埋め込み成功")
                return True
            else:
                logger.error(f"FFmpegエラー: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"外部字幕埋め込みエラー: {e}")
            return False
