"""
音声処理・転写モジュール (修正版 - SRT空ファイル問題修正)
"""

import os
import whisper
from pathlib import Path
from moviepy.editor import VideoFileClip
from typing import Optional, List, Dict
import logging
import gc
import uuid
import tempfile
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class AudioProcessor:
    """音声処理と転写を行うクラス（修正版）"""

    def __init__(self, config):
        self.config = config
        self.temp_dir = Path(os.getenv("TEMP_DIR", "temp"))
        self.temp_dir.mkdir(exist_ok=True)

        # Whisperモデルをロード
        self.model_size = config.get("whisper_model", "base")
        self.chunk_length = config.get("chunk_length", 30)  # 音声分割長（秒）
        self.max_retries = config.get("max_retries", 3)

        logger.info(f"Whisperモデルをロード中: {self.model_size}")
        try:
            self.whisper_model = whisper.load_model(self.model_size)
            logger.info("Whisperモデルのロードが完了")
        except Exception as e:
            logger.error(f"Whisperモデルのロードに失敗: {e}")
            raise

    @contextmanager
    def _get_temp_file(self, suffix: str):
        """一時ファイルを安全に管理するコンテキストマネージャー"""
        temp_file = None
        try:
            # ユニークなファイル名を生成
            unique_id = str(uuid.uuid4())
            temp_file = self.temp_dir / f"{unique_id}{suffix}"
            yield temp_file
        finally:
            # 確実に一時ファイルを削除
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                    logger.debug(f"一時ファイルを削除: {temp_file}")
                except Exception as e:
                    logger.warning(f"一時ファイル削除に失敗: {e}")

    def extract_audio(self, video_path: str) -> Optional[str]:
        """
        動画から音声を抽出（改善版・バージョン互換性対応）

        Args:
            video_path: 動画ファイルのパス

        Returns:
            抽出された音声ファイルのパス
        """
        return self._extract_audio_safe(video_path) or self._extract_audio_simple(video_path)

    def _extract_audio_safe(self, video_path: str) -> Optional[str]:
        """安全な音声抽出（推奨方法）"""
        video_clip = None
        audio_clip = None

        try:
            video_path = Path(video_path)
            if not video_path.exists():
                logger.error(f"動画ファイルが見つかりません: {video_path}")
                return None

            # ユニークな出力パスを生成
            unique_id = str(uuid.uuid4())
            audio_path = self.temp_dir / f"{video_path.stem}_{unique_id}_audio.wav"

            logger.info(f"音声を抽出中: {video_path} -> {audio_path}")

            # MoviePyで音声を抽出
            video_clip = VideoFileClip(str(video_path))

            # 音声トラックが存在するかチェック
            if video_clip.audio is None:
                logger.error("動画に音声トラックがありません")
                return None

            audio_clip = video_clip.audio

            # 音声を書き出し（バージョン互換性を考慮）
            write_params = {
                'verbose': False,
                'logger': None
            }

            # MoviePyのバージョンに応じてパラメータを調整
            try:
                # より安全な書き出し設定
                audio_clip.write_audiofile(
                    str(audio_path),
                    **write_params
                )
            except Exception as write_error:
                # fallbackとしてシンプルな設定で再試行
                logger.warning(f"標準設定での書き出しに失敗、シンプル設定で再試行: {write_error}")
                audio_clip.write_audiofile(str(audio_path))

            logger.info("音声抽出完了")
            return str(audio_path)

        except Exception as e:
            error_msg = f"音声抽出エラー: {str(e)}"
            logger.error(error_msg)

            # エラーの詳細情報をログに出力
            if "temp_audiofile" in str(e):
                logger.error("MoviePyのバージョンが古い可能性があります。アップデートを検討してください: pip install --upgrade moviepy")
            elif "codec" in str(e).lower():
                logger.error("音声コーデックの問題です。FFmpegが正しくインストールされているか確認してください")
            elif "permission" in str(e).lower():
                logger.error("ファイルアクセス権限の問題です。出力先ディレクトリの権限を確認してください")

            return None

        finally:
            # リソースを確実に解放
            if audio_clip:
                try:
                    audio_clip.close()
                except:
                    pass
            if video_clip:
                try:
                    video_clip.close()
                except:
                    pass
            # メモリを解放
            gc.collect()

    def _extract_audio_simple(self, video_path: str) -> Optional[str]:
        """シンプルな音声抽出（フォールバック用）"""
        video_clip = None
        audio_clip = None

        try:
            video_path = Path(video_path)
            unique_id = str(uuid.uuid4())
            audio_path = self.temp_dir / f"{video_path.stem}_{unique_id}_simple.wav"

            logger.info(f"シンプル方式で音声を抽出中: {video_path}")

            video_clip = VideoFileClip(str(video_path))
            if video_clip.audio is None:
                logger.error("動画に音声トラックがありません")
                return None

            audio_clip = video_clip.audio

            # 最もシンプルな書き出し
            audio_clip.write_audiofile(str(audio_path))

            logger.info("シンプル方式での音声抽出完了")
            return str(audio_path)

        except Exception as e:
            logger.error(f"シンプル音声抽出もエラー: {e}")
            return None

        finally:
            if audio_clip:
                try:
                    audio_clip.close()
                except:
                    pass
            if video_clip:
                try:
                    video_clip.close()
                except:
                    pass
            gc.collect()

    def transcribe_audio(self, audio_path: str, language: str = None) -> Optional[Dict]:
        """
        音声を転写してテキスト化（修正版 - データ構造統一）

        Args:
            audio_path: 音声ファイルのパス
            language: 転写する言語 (None=自動検出)

        Returns:
            転写結果（テキストとタイムスタンプ付き）
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"音声転写開始: {audio_path} (試行 {attempt + 1}/{self.max_retries})")

                if not os.path.exists(audio_path):
                    logger.error(f"音声ファイルが見つかりません: {audio_path}")
                    return None

                # 音声ファイルのサイズをチェック
                file_size = os.path.getsize(audio_path) / (1024 * 1024)  # MB
                logger.info(f"音声ファイルサイズ: {file_size:.2f} MB")

                # Whisperで転写実行（オプションを調整）
                options = {
                    "language": language,
                    "task": "transcribe",
                    "verbose": False,  # 詳細ログを抑制
                    "word_timestamps": False,  # 単語レベルのタイムスタンプは無効化
                    "no_speech_threshold": 0.6,  # 無音部分の閾値を調整
                    "logprob_threshold": -1.0,
                }

                # 大きなファイルの場合は分割処理
                if file_size > 25:  # 25MB以上の場合
                    result = self._transcribe_in_chunks(audio_path, options)
                else:
                    result = self.whisper_model.transcribe(audio_path, **options)

                if result is None:
                    raise Exception("転写結果がNullです")

                # 結果を統一フォーマットに整理
                transcription = {
                    "text": result.get("text", ""),
                    "language": result.get("language", "unknown"),
                    "segments": []
                }

                # セグメント情報を追加（データ構造を統一）
                for segment in result.get("segments", []):
                    segment_text = segment.get("text", "").strip()
                    if segment_text:  # 空のセグメントを除外
                        # 統一された形式でセグメントを追加
                        transcription["segments"].append({
                            "start": float(segment.get("start", 0)),  # 明示的にfloatに変換
                            "end": float(segment.get("end", 0)),      # 明示的にfloatに変換
                            "text": segment_text,
                        })

                logger.info(f"転写完了 - 検出言語: {result.get('language', 'unknown')}")
                logger.info(f"総セグメント数: {len(transcription['segments'])}")

                # データの妥当性チェック
                if not transcription["segments"]:
                    logger.warning("セグメントが見つかりませんでした")
                    return None

                # デバッグ情報出力
                self._debug_transcription_result(transcription)

                return transcription

            except Exception as e:
                logger.warning(f"転写エラー (試行 {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    logger.error(f"転写に失敗しました: {e}")
                    return None

                # リトライ前にメモリをクリア
                gc.collect()

        return None

    def _transcribe_in_chunks(self, audio_path: str, options: dict) -> Optional[Dict]:
        """大きな音声ファイルを分割して転写"""
        try:
            from pydub import AudioSegment

            logger.info("音声を分割して転写します")

            # 音声を読み込み
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000  # 秒

            chunk_length_ms = self.chunk_length * 1000  # ミリ秒

            all_segments = []
            full_text = ""

            # 分割して処理
            for i in range(0, len(audio), chunk_length_ms):
                chunk = audio[i:i + chunk_length_ms]

                with self._get_temp_file("_chunk.wav") as chunk_path:
                    chunk.export(str(chunk_path), format="wav")

                    # チャンク単位で転写
                    chunk_result = self.whisper_model.transcribe(str(chunk_path), **options)

                    if chunk_result and "segments" in chunk_result:
                        # タイムスタンプを調整
                        time_offset = i / 1000  # 秒
                        for segment in chunk_result["segments"]:
                            segment["start"] = float(segment["start"] + time_offset)
                            segment["end"] = float(segment["end"] + time_offset)
                            all_segments.append(segment)

                        full_text += chunk_result.get("text", "")

            return {
                "text": full_text,
                "language": chunk_result.get("language", "unknown") if chunk_result else "unknown",
                "segments": all_segments
            }

        except ImportError:
            logger.error("pydubが必要です: pip install pydub")
            return None
        except Exception as e:
            logger.error(f"分割転写エラー: {e}")
            return None

    def extract_and_transcribe(self, video_path: str, language: str = None) -> Optional[Dict]:
        """
        動画から音声を抽出して転写（一括処理・修正版）

        Args:
            video_path: 動画ファイルのパス
            language: 転写する言語

        Returns:
            転写結果
        """
        audio_path = None
        try:
            # 音声を抽出
            audio_path = self.extract_audio(video_path)
            if not audio_path:
                logger.error("音声抽出に失敗しました")
                return None

            # 転写実行
            transcription = self.transcribe_audio(audio_path, language)

            return transcription

        except Exception as e:
            logger.error(f"処理中にエラーが発生: {e}")
            return None

        finally:
            # 一時音声ファイルを確実に削除
            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                    logger.info("一時音声ファイルを削除しました")
                except Exception as e:
                    logger.warning(f"一時ファイル削除に失敗: {e}")

            # メモリクリーンアップ
            gc.collect()

    def save_transcription(self, transcription: Dict, output_path: str) -> bool:
        """
        転写結果をファイルに保存（修正版）

        Args:
            transcription: 転写結果
            output_path: 出力ファイルパス

        Returns:
            保存成功の可否
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # テキストファイルとして保存
            if output_path.suffix == '.txt':
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(transcription.get("text", ""))

            # SRTファイルとして保存
            elif output_path.suffix == '.srt':
                return self._save_as_srt(transcription, output_path)

            # JSONファイルとして保存
            elif output_path.suffix == '.json':
                import json
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(transcription, f, ensure_ascii=False, indent=2)

            else:
                logger.error(f"サポートされていないファイル形式: {output_path.suffix}")
                return False

            logger.info(f"転写結果を保存: {output_path}")
            return True

        except Exception as e:
            logger.error(f"転写結果の保存に失敗: {e}")
            return False

    def _save_as_srt(self, transcription: Dict, output_path: Path) -> bool:
        """転写結果をSRTファイルとして保存"""
        try:
            import pysrt

            subs = pysrt.SubRipFile()
            segments = transcription.get("segments", [])

            if not segments:
                logger.error("セグメントが見つかりません")
                return False

            for i, segment in enumerate(segments):
                try:
                    start_time = self._seconds_to_timedelta(float(segment["start"]))
                    end_time = self._seconds_to_timedelta(float(segment["end"]))
                    text = str(segment["text"]).strip()

                    if text:
                        sub = pysrt.SubRipItem(
                            index=i+1,
                            start=start_time,
                            end=end_time,
                            text=text
                        )
                        subs.append(sub)

                except Exception as e:
                    logger.warning(f"セグメント {i} の処理でエラー: {e}")
                    continue

            subs.save(str(output_path), encoding='utf-8')
            logger.info(f"SRTファイルを保存: {output_path}")
            return True

        except ImportError:
            logger.error("pysrtが必要です: pip install pysrt")
            return False
        except Exception as e:
            logger.error(f"SRTファイル保存エラー: {e}")
            return False

    def _seconds_to_timedelta(self, seconds: float):
        """秒数をpysrtのTimeオブジェクトに変換（エラーハンドリング強化）"""
        try:
            import pysrt

            seconds = max(0, float(seconds))
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)

            return pysrt.SubRipTime(hours, minutes, secs, milliseconds)
        except Exception as e:
            logger.error(f"時間変換エラー: {e}")
            import pysrt
            return pysrt.SubRipTime(0, 0, 0, 0)

    def get_audio_info(self, audio_path: str) -> Optional[Dict]:
        """音声ファイルの情報を取得（改善版）"""
        try:
            from pydub import AudioSegment

            if not os.path.exists(audio_path):
                logger.error(f"音声ファイルが見つかりません: {audio_path}")
                return None

            audio = AudioSegment.from_file(audio_path)

            info = {
                "duration": len(audio) / 1000,  # 秒
                "frame_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "file_size_mb": os.path.getsize(audio_path) / (1024 * 1024)
            }

            logger.info(f"音声情報: {info}")
            return info

        except ImportError:
            logger.error("pydubが必要です: pip install pydub")
            return None
        except Exception as e:
            logger.error(f"音声情報の取得に失敗: {e}")
            return None

    def cleanup_temp_files(self):
        """一時ディレクトリのクリーンアップ"""
        try:
            if self.temp_dir.exists():
                for temp_file in self.temp_dir.glob("*"):
                    try:
                        temp_file.unlink()
                        logger.debug(f"一時ファイルを削除: {temp_file}")
                    except Exception as e:
                        logger.warning(f"一時ファイル削除に失敗: {temp_file} - {e}")

                logger.info("一時ファイルのクリーンアップが完了")
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")

    def _debug_transcription_result(self, transcription: Dict):
        """転写結果をデバッグ表示"""
        logger.debug("=== 転写結果デバッグ情報 ===")
        logger.debug(f"言語: {transcription.get('language', 'unknown')}")
        logger.debug(f"セグメント数: {len(transcription.get('segments', []))}")
        logger.debug(f"全体テキスト長: {len(transcription.get('text', ''))}")

        # 最初の3セグメントの詳細
        for i, segment in enumerate(transcription.get('segments', [])[:3]):
            logger.debug(f"セグメント {i+1}:")
            logger.debug(f"  時間: {segment['start']:.2f} - {segment['end']:.2f}")
            logger.debug(f"  テキスト: {segment['text'][:50]}...")
            logger.debug(f"  型チェック - start: {type(segment['start'])}, end: {type(segment['end'])}")

# トラブルシューティング用ユーティリティ関数

def validate_transcription_data(transcription: Dict) -> bool:
    """転写データの妥当性をチェック"""
    try:
        if not isinstance(transcription, dict):
            logger.error(f"転写データが辞書型ではありません: {type(transcription)}")
            return False

        required_keys = ["text", "language", "segments"]
        for key in required_keys:
            if key not in transcription:
                logger.error(f"必須キー '{key}' が見つかりません")
                return False

        segments = transcription.get("segments", [])
        if not isinstance(segments, list):
            logger.error(f"セグメントがリスト型ではありません: {type(segments)}")
            return False

        if not segments:
            logger.warning("セグメントが空です")
            return False

        # セグメントの妥当性チェック
        for i, segment in enumerate(segments[:5]):  # 最初の5セグメントのみチェック
            if not isinstance(segment, dict):
                logger.error(f"セグメント {i} が辞書型ではありません: {type(segment)}")
                return False

            required_segment_keys = ["start", "end", "text"]
            for key in required_segment_keys:
                if key not in segment:
                    logger.error(f"セグメント {i} に必須キー '{key}' が見つかりません")
                    return False

            # 数値型チェック
            try:
                float(segment["start"])
                float(segment["end"])
            except (ValueError, TypeError):
                logger.error(f"セグメント {i} の時間データが不正: start={segment['start']}, end={segment['end']}")
                return False

            # テキストチェック
            if not isinstance(segment["text"], str):
                logger.error(f"セグメント {i} のテキストが文字列ではありません: {type(segment['text'])}")
                return False

        logger.info("転写データの妥当性チェック: OK")
        return True

    except Exception as e:
        logger.error(f"転写データ検証エラー: {e}")
        return False

def create_test_transcription() -> Dict:
    """テスト用の転写データを作成"""
    return {
        "text": "これはテスト用の転写データです。正常に動作することを確認します。",
        "language": "ja",
        "segments": [
            {
                "start": 0.0,
                "end": 3.0,
                "text": "これはテスト用の転写データです。"
            },
            {
                "start": 3.0,
                "end": 6.0,
                "text": "正常に動作することを確認します。"
            }
        ]
    }
