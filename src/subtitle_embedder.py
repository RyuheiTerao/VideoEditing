"""
字幕埋め込みモジュール (修正版)
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, List
import logging
import re

logger = logging.getLogger(__name__)

class SubtitleEmbedder:
    """動画に字幕を埋め込むクラス（修正版）"""

    def __init__(self, config):
        self.config = config
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        self.output_dir.mkdir(exist_ok=True)

        # フォント設定（型安全な取得）
        self.font_settings = {
            "font_name": str(config.get("subtitle_font", "Arial")),
            "font_size": self._safe_int(config.get("subtitle_font_size"), 20),
            "font_color": str(config.get("subtitle_font_color", "white")),
            "outline_color": str(config.get("subtitle_outline_color", "black")),
            "outline_width": self._safe_int(config.get("subtitle_outline_width"), 1),
        }

        logger.info(f"字幕フォント設定: {self.font_settings}")

    def _safe_int(self, value, default: int) -> int:
        """安全に整数値を取得"""
        try:
            if value is None:
                return default
            if isinstance(value, int):
                return value
            if isinstance(value, (str, float)):
                return int(float(value))
            return default
        except (ValueError, TypeError) as e:
            logger.warning(f"整数変換エラー: {value} -> デフォルト値 {default} を使用: {e}")
            return default

    def embed_subtitles(self, video_path: str, subtitle_path: str, method: str = "burn") -> Optional[str]:
        """
        動画に字幕を埋め込み（改善版）

        Args:
            video_path: 元動画のパス
            subtitle_path: 字幕ファイルのパス
            method: 埋め込み方法 ("burn" or "soft")

        Returns:
            字幕付き動画のパス
        """
        try:
            video_path = Path(video_path)
            subtitle_path = Path(subtitle_path)

            # ファイルの存在確認
            if not video_path.exists():
                logger.error(f"動画ファイルが見つかりません: {video_path}")
                return None
            if not subtitle_path.exists():
                logger.error(f"字幕ファイルが見つかりません: {subtitle_path}")
                return None

            # 出力ファイル名を生成（安全なファイル名に変換）
            safe_name = self._make_safe_filename(video_path.stem)
            output_filename = f"{safe_name}_with_subtitles.mp4"
            output_path = self.output_dir / output_filename

            logger.info(f"字幕埋め込み開始: {method}方式")
            logger.info(f"動画: {video_path}")
            logger.info(f"字幕: {subtitle_path}")
            logger.info(f"出力: {output_path}")

            if method == "burn":
                return self._burn_subtitles(video_path, subtitle_path, output_path)
            elif method == "soft":
                return self._add_soft_subtitles(video_path, subtitle_path, output_path)
            else:
                logger.error(f"サポートされていない埋め込み方法: {method}")
                return None

        except Exception as e:
            logger.error(f"字幕埋め込みエラー: {e}")
            return None

    def _make_safe_filename(self, filename: str) -> str:
        """ファイル名を安全な形式に変換"""
        # 特殊文字を除去・置換
        safe_name = re.sub(r'[<>:"/\\|?*⧸]', '_', filename)
        safe_name = re.sub(r'[^\w\s\-_\.\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', '_', safe_name)
        return safe_name.strip()

    def _burn_subtitles(self, video_path: Path, subtitle_path: Path, output_path: Path) -> Optional[str]:
        """
        字幕を動画に焼き込み（ハードコード）- 修正版
        """
        try:
            # FFmpegコマンドを構築
            subtitle_filter = self._build_subtitle_filter_corrected(subtitle_path)

            ffmpeg_cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", subtitle_filter,
                "-c:a", "copy",  # 音声はコピー
                "-c:v", "libx264",  # 動画エンコーダー
                "-preset", "medium",  # エンコード品質
                "-crf", "23",  # 品質設定
                "-avoid_negative_ts", "make_zero",  # タイムスタンプの問題を回避
                "-y",  # 出力ファイルを上書き
                str(output_path)
            ]

            logger.info("FFmpeg実行中...")
            logger.debug(f"コマンド: {' '.join(ffmpeg_cmd)}")

            # FFmpegを実行
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600  # 1時間でタイムアウト
            )

            if result.returncode == 0:
                logger.info("字幕の焼き込み完了")
                return str(output_path)
            else:
                logger.error(f"FFmpegエラー (戻り値: {result.returncode})")
                logger.error(f"stderr: {result.stderr}")

                # 代替方法を試行
                logger.info("代替方法で字幕埋め込みを試行...")
                return self._burn_subtitles_alternative(video_path, subtitle_path, output_path)

        except subprocess.TimeoutExpired:
            logger.error("FFmpegがタイムアウトしました")
            return None
        except Exception as e:
            logger.error(f"字幕焼き込みエラー: {e}")
            return None

    def _burn_subtitles_alternative(self, video_path: Path, subtitle_path: Path, output_path: Path) -> Optional[str]:
        """
        代替方法での字幕焼き込み（シンプルな方式）
        """
        try:
            # より単純なsubtitlesフィルターを使用
            escaped_path = self._escape_path_for_ffmpeg(subtitle_path)

            # シンプルなフィルター（フォント設定なし）
            subtitle_filter = f"subtitles={escaped_path}"

            ffmpeg_cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", subtitle_filter,
                "-c:a", "copy",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-y",
                str(output_path)
            ]

            logger.info("代替方法でFFmpeg実行中...")
            logger.debug(f"代替コマンド: {' '.join(ffmpeg_cmd)}")

            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600
            )

            if result.returncode == 0:
                logger.info("代替方法での字幕焼き込み完了")
                return str(output_path)
            else:
                logger.error(f"代替方法でもFFmpegエラー: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"代替字幕焼き込みエラー: {e}")
            return None

    def _build_subtitle_filter_corrected(self, subtitle_path: Path) -> str:
        """
        修正された字幕フィルターを構築
        """
        escaped_path = self._escape_path_for_ffmpeg(subtitle_path)

        # 正しいASS/SSAスタイルパラメータを使用
        font_config = (
            f"Fontname={self.font_settings['font_name']},"
            f"Fontsize={self.font_settings['font_size']},"
            f"PrimaryColour={self._color_to_ass_corrected(self.font_settings['font_color'])},"
            f"OutlineColour={self._color_to_ass_corrected(self.font_settings['outline_color'])},"
            f"Outline={self.font_settings['outline_width']}"
        )

        if subtitle_path.suffix.lower() == '.srt':
            return f"subtitles={escaped_path}:force_style='{font_config}'"
        elif subtitle_path.suffix.lower() in ['.ass', '.ssa']:
            return f"ass={escaped_path}"
        else:
            # デフォルトはsubtitlesフィルター
            return f"subtitles={escaped_path}:force_style='{font_config}'"

    def _escape_path_for_ffmpeg(self, path: Path) -> str:
        """
        FFmpeg用にパスを適切にエスケープ
        """
        path_str = str(path)

        # Windows と Unix の両方に対応
        if os.name == 'nt':  # Windows
            # Windowsの場合は二重エスケープ
            escaped = path_str.replace("\\", "\\\\\\\\").replace(":", "\\:")
        else:  # Unix系
            # Unix系の場合
            escaped = path_str.replace("\\", "\\\\").replace(":", "\\:")

        # 特殊文字のエスケープ
        special_chars = ['[', ']', ',', ';']
        for char in special_chars:
            escaped = escaped.replace(char, f"\\{char}")

        logger.debug(f"パスエスケープ: {path_str} -> {escaped}")
        return escaped

    def _color_to_ass_corrected(self, color_name: str) -> str:
        """
        色名を正しいASS形式のカラーコードに変換
        """
        # ASS形式は &HAABBGGRR (逆順のBGR + 透明度)
        color_map = {
            "white": "&HFFFFFF",
            "black": "&H000000",
            "red": "&H0000FF",    # BGR順序
            "green": "&H00FF00",
            "blue": "&HFF0000",   # BGR順序
            "yellow": "&H00FFFF",
            "cyan": "&HFFFF00",
            "magenta": "&HFF00FF",
        }
        return color_map.get(color_name.lower(), "&HFFFFFF")

    def _add_soft_subtitles(self, video_path: Path, subtitle_path: Path, output_path: Path) -> Optional[str]:
        """
        ソフト字幕として埋め込み（外部字幕ファイルとして追加）- 修正版
        """
        try:
            # 字幕形式の確認と変換
            if subtitle_path.suffix.lower() == '.vtt':
                # WebVTTの場合、SRTに変換してから埋め込み
                srt_path = self._convert_vtt_to_srt(subtitle_path)
                if not srt_path:
                    logger.error("VTTからSRTへの変換に失敗")
                    return None
                subtitle_path = Path(srt_path)

            ffmpeg_cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-i", str(subtitle_path),
                "-c:v", "copy",  # 動画をコピー
                "-c:a", "copy",  # 音声をコピー
                "-c:s", "mov_text",  # 字幕コーデック
                "-metadata:s:s:0", "language=ja",  # 日本語字幕として設定
                "-metadata:s:s:0", "title=Japanese",  # 字幕のタイトル
                "-disposition:s:0", "default",  # デフォルト字幕として設定
                "-y",
                str(output_path)
            ]

            logger.info("ソフト字幕埋め込み実行中...")
            logger.debug(f"コマンド: {' '.join(ffmpeg_cmd)}")

            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1800  # 30分でタイムアウト
            )

            if result.returncode == 0:
                logger.info("ソフト字幕埋め込み完了")
                return str(output_path)
            else:
                logger.error(f"ソフト字幕埋め込みFFmpegエラー: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"ソフト字幕埋め込みエラー: {e}")
            return None

    def _convert_vtt_to_srt(self, vtt_path: Path) -> Optional[str]:
        """
        VTTファイルをSRTに変換
        """
        try:
            srt_path = vtt_path.with_suffix('.srt')

            ffmpeg_cmd = [
                "ffmpeg",
                "-i", str(vtt_path),
                "-c:s", "srt",
                "-y",
                str(srt_path)
            ]

            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode == 0:
                logger.info(f"VTTからSRTへの変換完了: {srt_path}")
                return str(srt_path)
            else:
                logger.error(f"VTT変換エラー: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"VTT変換エラー: {e}")
            return None

    def extract_subtitles(self, video_path: str, output_dir: str = None) -> List[str]:
        """
        動画から既存の字幕を抽出（修正版）

        Args:
            video_path: 動画ファイルのパス
            output_dir: 字幕ファイルの出力ディレクトリ

        Returns:
            抽出された字幕ファイルのパスのリスト
        """
        try:
            video_path = Path(video_path)
            output_dir = Path(output_dir) if output_dir else self.output_dir

            # 動画の字幕ストリーム情報を取得
            probe_cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                str(video_path)
            ]

            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("字幕情報の取得に失敗")
                return []

            import json
            streams_info = json.loads(result.stdout)
            subtitle_streams = [
                stream for stream in streams_info.get("streams", [])
                if stream.get("codec_type") == "subtitle"
            ]

            if not subtitle_streams:
                logger.info("字幕ストリームが見つかりません")
                return []

            extracted_files = []
            safe_basename = self._make_safe_filename(video_path.stem)

            for i, stream in enumerate(subtitle_streams):
                # 字幕を抽出
                output_file = output_dir / f"{safe_basename}_subtitle_{i}.srt"

                extract_cmd = [
                    "ffmpeg",
                    "-i", str(video_path),
                    "-map", f"0:s:{i}",
                    "-c:s", "srt",
                    "-y",
                    str(output_file)
                ]

                result = subprocess.run(extract_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    extracted_files.append(str(output_file))
                    logger.info(f"字幕抽出完了: {output_file}")

            return extracted_files

        except Exception as e:
            logger.error(f"字幕抽出エラー: {e}")
            return []

    def get_video_info(self, video_path: str) -> Optional[dict]:
        """
        動画ファイルの情報を取得（改善版）
        """
        try:
            probe_cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(video_path)
            ]

            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"ffprobeエラー: {result.stderr}")
                return None

            import json
            info = json.loads(result.stdout)

            # 基本情報を整理
            video_info = {
                "duration": info.get("format", {}).get("duration"),
                "size": info.get("format", {}).get("size"),
                "bitrate": info.get("format", {}).get("bit_rate"),
                "streams": []
            }

            for stream in info.get("streams", []):
                stream_info = {
                    "index": stream.get("index"),
                    "codec_type": stream.get("codec_type"),
                    "codec_name": stream.get("codec_name")
                }

                if stream.get("codec_type") == "video":
                    stream_info.update({
                        "width": stream.get("width"),
                        "height": stream.get("height"),
                        "fps": stream.get("r_frame_rate")
                    })
                elif stream.get("codec_type") == "audio":
                    stream_info.update({
                        "sample_rate": stream.get("sample_rate"),
                        "channels": stream.get("channels")
                    })

                video_info["streams"].append(stream_info)

            return video_info

        except subprocess.TimeoutExpired:
            logger.error("ffprobe がタイムアウトしました")
            return None
        except Exception as e:
            logger.error(f"動画情報取得エラー: {e}")
            return None

    def validate_ffmpeg_installation(self) -> bool:
        """
        FFmpegのインストールと動作確認
        """
        try:
            # ffmpegのバージョン確認
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info("FFmpeg が正常にインストールされています")
                return True
            else:
                logger.error("FFmpeg が見つかりません")
                return False

        except FileNotFoundError:
            logger.error("FFmpeg が見つかりません。インストールしてください。")
            return False
        except Exception as e:
            logger.error(f"FFmpeg確認エラー: {e}")
            return False
