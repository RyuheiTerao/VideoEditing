"""
字幕埋め込みモジュール（日本語対応強化版）
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class SubtitleEmbedder:
    """字幕を動画に埋め込むクラス（日本語対応強化版）"""

    def __init__(self, config):
        self.config = config
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        self.output_dir.mkdir(exist_ok=True)

        self.subtitle_method = config.get("subtitle_method", "burn")
        self.font_size = config.get("subtitle_font_size", 24)

        # 日本語フォント設定
        self.font_name = config.get("font_name", "DejaVu Sans")  # フォールバック用
        self.subtitle_encoding = config.get("subtitle_encoding", "utf-8")

        # 日本語フォントの優先順位
        self.japanese_fonts = [
            "Noto Sans CJK JP",
            "NotoSansCJK-Regular",
            "Hiragino Sans",
            "Yu Gothic",
            "Meiryo",
            "DejaVu Sans",
            "Arial Unicode MS"
        ]

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

            # SRTファイルの事前検証と修復
            if not self._validate_and_fix_srt_file(subtitle_path):
                logger.error(f"SRTファイルが不正です: {subtitle_path}")
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

    def _validate_and_fix_srt_file(self, subtitle_path: Path) -> bool:
        """SRTファイルの検証と修復"""
        try:
            with open(subtitle_path, 'r', encoding=self.subtitle_encoding) as f:
                content = f.read()

            # coroutineオブジェクトの検出と修復
            if 'coroutine object' in content:
                logger.warning("SRTファイルにcoroutineオブジェクトが含まれています。修復します...")

                # バックアップを作成
                backup_path = subtitle_path.with_suffix('.backup')
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # 修復処理
                import re
                fixed_content = re.sub(r'<coroutine object [^>]+>', '[翻訳エラー]', content)
                fixed_content = re.sub(r'<coroutine.*?>', '[翻訳エラー]', fixed_content)

                # 修復されたファイルを保存
                with open(subtitle_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)

                logger.info(f"SRTファイルを修復しました: {subtitle_path}")

            # 基本的な妥当性チェック
            with open(subtitle_path, 'r', encoding=self.subtitle_encoding) as f:
                content = f.read()

            if not content.strip():
                logger.error("SRTファイルが空です")
                return False

            if '-->' not in content:
                logger.error("SRTファイルにタイムスタンプが見つかりません")
                return False

            lines = content.strip().split('\n')
            if len(lines) < 3:
                logger.error("SRTファイルの形式が不正です")
                return False

            logger.info("SRTファイルの検証完了")
            return True

        except Exception as e:
            logger.error(f"SRTファイルの検証エラー: {e}")
            return False

    def _burn_subtitles(self, video_path: Path, subtitle_path: Path, output_path: Path) -> bool:
        """字幕を動画に焼き込み（日本語対応強化版）"""
        try:
            # 使用可能なフォントを検出
            font_name = self._detect_available_font()
            logger.info(f"使用フォント: {font_name}")

            # 字幕フィルタの構築（エスケープ処理強化）
            subtitle_path_str = str(subtitle_path).replace('\\', '/')
            subtitle_path_str = subtitle_path_str.replace(':', '\\:')

            # より詳細なスタイル設定
            subtitle_filter = (
                f"subtitles='{subtitle_path_str}':"
                f"force_style='"
                f"FontName={font_name},"
                f"FontSize={self.font_size},"
                f"PrimaryColour=&Hffffff&,"
                f"SecondaryColour=&Hffffff&,"
                f"OutlineColour=&H000000&,"
                f"BackColour=&H80000000&,"
                f"Outline=2,"
                f"Shadow=1,"
                f"Alignment=2,"
                f"MarginV=20"
                f"'"
            )

            cmd = [
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

            logger.info("FFmpegで字幕焼き込み実行中...")
            logger.debug(f"実行コマンド: {' '.join(cmd)}")

            # エラー出力をキャプチャして詳細ログ
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600  # 1時間のタイムアウト
            )

            if result.returncode == 0:
                logger.info("字幕焼き込み成功")
                return True
            else:
                logger.error(f"FFmpegエラー (code: {result.returncode})")
                logger.error(f"STDERR: {result.stderr}")

                # よくあるエラーの対処法を提示
                if "font" in result.stderr.lower():
                    logger.error("フォント関連のエラーです。システムに日本語フォントがインストールされているか確認してください")
                elif "subtitle" in result.stderr.lower():
                    logger.error("字幕ファイル関連のエラーです。SRTファイルの形式を確認してください")

                return False

        except subprocess.TimeoutExpired:
            logger.error("字幕焼き込みがタイムアウトしました")
            return False
        except Exception as e:
            logger.error(f"字幕焼き込みエラー: {e}")
            return False

    def _soft_subtitles(self, video_path: Path, subtitle_path: Path, output_path: Path) -> bool:
        """外部字幕として埋め込み（改良版）"""
        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-i", str(subtitle_path),
                "-c:v", "copy",
                "-c:a", "copy",
                "-c:s", "mov_text",
                "-metadata:s:s:0", "language=jpn",
                "-metadata:s:s:0", "title=Japanese Subtitles",
                "-disposition:s:0", "default",
                "-y",
                str(output_path)
            ]

            logger.info("FFmpegで外部字幕埋め込み実行中...")
            logger.debug(f"実行コマンド: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600
            )

            if result.returncode == 0:
                logger.info("外部字幕埋め込み成功")
                return True
            else:
                logger.error(f"FFmpegエラー (code: {result.returncode})")
                logger.error(f"STDERR: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("外部字幕埋め込みがタイムアウトしました")
            return False
        except Exception as e:
            logger.error(f"外部字幕埋め込みエラー: {e}")
            return False

    def _detect_available_font(self) -> str:
        """使用可能なフォントを検出"""
        try:
            # システムフォントの確認
            for font in self.japanese_fonts:
                if self._check_font_availability(font):
                    logger.info(f"使用可能な日本語フォント: {font}")
                    return font

            # デフォルトフォントにフォールバック
            logger.warning("日本語フォントが見つかりません。デフォルトフォントを使用します")
            return self.font_name

        except Exception as e:
            logger.error(f"フォント検出エラー: {e}")
            return "DejaVu Sans"

    def _check_font_availability(self, font_name: str) -> bool:
        """指定されたフォントが使用可能かチェック"""
        try:
            # fc-listコマンドでフォントの存在を確認
            result = subprocess.run(
                ["fc-list", ":", "family"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                available_fonts = result.stdout.lower()
                return font_name.lower() in available_fonts
            else:
                # fc-listが使えない場合は、よく知られたフォントのみ許可
                common_fonts = ["dejavu sans", "arial", "liberation sans"]
                return font_name.lower() in common_fonts

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # コマンドが使えない場合はデフォルトのみ許可
            return font_name.lower() in ["dejavu sans", "arial"]
        except Exception as e:
            logger.warning(f"フォント確認エラー: {e}")
            return False

    def check_dependencies(self) -> bool:
        """FFmpegと必要な依存関係をチェック"""
        try:
            # FFmpegの確認
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info("FFmpegが正常に動作しています")

                # 字幕サポートの確認
                if "libass" in result.stdout:
                    logger.info("字幕サポート (libass) が利用可能です")
                else:
                    logger.warning("libassが見つかりません。字幕表示に問題が生じる可能性があります")

                return True
            else:
                logger.error("FFmpegが正常に動作していません")
                return False

        except subprocess.TimeoutExpired:
            logger.error("FFmpegの確認がタイムアウトしました")
            return False
        except FileNotFoundError:
            logger.error("FFmpegがインストールされていません")
            logger.error("以下のコマンドでインストールしてください:")
            logger.error("Ubuntu/Debian: sudo apt-get install ffmpeg")
            logger.error("CentOS/RHEL: sudo yum install ffmpeg")
            logger.error("macOS: brew install ffmpeg")
            return False
        except Exception as e:
            logger.error(f"FFmpeg確認エラー: {e}")
            return False

    def get_video_info(self, video_path: str) -> dict:
        """動画ファイルの情報を取得"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(video_path)
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)

                video_info = {
                    "duration": 0,
                    "width": 0,
                    "height": 0,
                    "fps": 0,
                    "codec": "unknown"
                }

                # フォーマット情報から動画の長さを取得
                if "format" in info:
                    video_info["duration"] = float(info["format"].get("duration", 0))

                # ストリーム情報から動画の詳細を取得
                for stream in info.get("streams", []):
                    if stream.get("codec_type") == "video":
                        video_info["width"] = stream.get("width", 0)
                        video_info["height"] = stream.get("height", 0)
                        video_info["codec"] = stream.get("codec_name", "unknown")

                        # フレームレートの計算
                        r_frame_rate = stream.get("r_frame_rate", "0/1")
                        if "/" in r_frame_rate:
                            num, den = map(int, r_frame_rate.split("/"))
                            if den != 0:
                                video_info["fps"] = round(num / den, 2)
                        break

                logger.info(f"動画情報: {video_info}")
                return video_info

            else:
                logger.error("動画情報の取得に失敗しました")
                return {}

        except Exception as e:
            logger.error(f"動画情報取得エラー: {e}")
            return {}

    def create_test_video_with_subtitles(self, output_path: str) -> bool:
        """テスト用の動画と字幕を作成（動作確認用）"""
        try:
            # テスト動画を作成（10秒間の単色動画）
            test_video_path = Path(output_path).parent / "test_video.mp4"
            test_srt_path = Path(output_path).parent / "test_subtitles.srt"

            # テスト動画作成
            cmd_video = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", "color=c=blue:size=1280x720:duration=10",
                "-c:v", "libx264",
                "-t", "10",
                "-pix_fmt", "yuv420p",
                "-y",
                str(test_video_path)
            ]

            result = subprocess.run(cmd_video, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("テスト動画の作成に失敗しました")
                return False

            # テスト字幕作成
            test_srt_content = """1
00:00:01,000 --> 00:00:03,000
これはテスト字幕です

2
00:00:04,000 --> 00:00:06,000
日本語フォントのテストです

3
00:00:07,000 --> 00:00:09,000
字幕システムが正常に動作しています
"""
            with open(test_srt_path, 'w', encoding='utf-8') as f:
                f.write(test_srt_content)

            # 字幕埋め込み
            result_path = self.embed_subtitles(str(test_video_path), str(test_srt_path))

            if result_path:
                logger.info(f"テスト動画作成成功: {result_path}")

                # 一時ファイルを削除
                try:
                    test_video_path.unlink()
                    test_srt_path.unlink()
                except:
                    pass

                return True
            else:
                logger.error("テスト動画の字幕埋め込みに失敗しました")
                return False

        except Exception as e:
            logger.error(f"テスト動画作成エラー: {e}")
            return False
