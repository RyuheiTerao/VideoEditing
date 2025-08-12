"""
翻訳モジュール (修正版)
"""

import os
import pysrt
from pathlib import Path
from typing import Optional, Dict, List
import logging
import time
import json

logger = logging.getLogger(__name__)

class Translator:
    """テキスト翻訳と字幕生成を行うクラス（改善版）"""

    def __init__(self, config):
        self.config = config
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        self.output_dir.mkdir(exist_ok=True)

        # 翻訳方法を設定で選択
        self.translation_method = config.get("translation_method", "googletrans_safe")

        # 翻訳設定（型安全な取得）
        self.max_retries = self._safe_int(config.get("translation_retries"), 3)
        self.retry_delay = self._safe_float(config.get("translation_retry_delay"), 2.0)
        self.batch_size = self._safe_int(config.get("batch_size"), 3)
        self.max_text_length = self._safe_int(config.get("max_text_length"), 4000)

        # 設定値の検証とログ出力
        logger.info(f"翻訳設定 - max_retries: {self.max_retries} (型: {type(self.max_retries)})")
        logger.info(f"翻訳設定 - retry_delay: {self.retry_delay} (型: {type(self.retry_delay)})")
        logger.info(f"翻訳設定 - batch_size: {self.batch_size} (型: {type(self.batch_size)})")
        logger.info(f"翻訳設定 - max_text_length: {self.max_text_length} (型: {type(self.max_text_length)})")

        # 翻訳クライアントの初期化
        self.translator = None
        self._init_translator()

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

    def _safe_float(self, value, default: float) -> float:
        """安全に浮動小数点値を取得"""
        try:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value)
            return default
        except (ValueError, TypeError) as e:
            logger.warning(f"浮動小数点変換エラー: {value} -> デフォルト値 {default} を使用: {e}")
            return default

    def _init_translator(self):
        """翻訳クライアントを初期化"""
        try:
            if self.translation_method == "googletrans_safe":
                self._init_googletrans_safe()
            elif self.translation_method == "deepl":
                self._init_deepl()
            elif self.translation_method == "openai":
                self._init_openai()
            else:
                logger.warning(f"未知の翻訳方法: {self.translation_method}, googletrans_safeを使用")
                self._init_googletrans_safe()
        except Exception as e:
            logger.error(f"翻訳クライアント初期化エラー: {e}")
            self.translator = None

    def _init_googletrans_safe(self):
        """安全なGoogle翻訳初期化"""
        try:
            from googletrans import Translator as GoogleTranslator

            # User-Agentを設定してより安定させる
            self.translator = GoogleTranslator(
                service_urls=[
                    'translate.google.com',
                    'translate.google.co.kr',
                    'translate.google.co.jp'
                ],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            logger.info("Google翻訳を初期化しました")
        except ImportError:
            logger.error("googletransが必要です: pip install googletrans==4.0.0rc1")
            raise
        except Exception as e:
            logger.error(f"Google翻訳初期化エラー: {e}")
            raise

    def _init_deepl(self):
        """DeepL翻訳初期化"""
        try:
            import deepl
            api_key = self.config.get("deepl_api_key")
            if not api_key:
                raise ValueError("DeepL APIキーが設定されていません")
            self.translator = deepl.Translator(api_key)
            logger.info("DeepL翻訳を初期化しました")
        except ImportError:
            logger.error("deeplが必要です: pip install deepl")
            raise

    def _init_openai(self):
        """OpenAI翻訳初期化"""
        try:
            import openai
            api_key = self.config.get("openai_api_key")
            if not api_key:
                raise ValueError("OpenAI APIキーが設定されていません")
            self.translator = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI翻訳を初期化しました")
        except ImportError:
            logger.error("openaiが必要です: pip install openai")
            raise

    def translate_text(self, text: str, target_lang: str = "ja", source_lang: str = "auto") -> Optional[str]:
        """
        テキストを翻訳（改善版）

        Args:
            text: 翻訳するテキスト
            target_lang: 翻訳先言語コード
            source_lang: 翻訳元言語コード

        Returns:
            翻訳されたテキスト
        """
        if not text or not text.strip():
            return text

        # テキストの長さチェック
        if len(text) > self.max_text_length:
            logger.warning(f"テキストが長すぎます({len(text)}文字), 分割して処理")
            return self._translate_long_text(text, target_lang, source_lang)

        # 言語コードの正規化
        target_lang = self._normalize_language_code(target_lang)
        source_lang = self._normalize_language_code(source_lang) if source_lang != "auto" else source_lang

        # max_retriesの型を再確認（デバッグ用）
        if not isinstance(self.max_retries, int):
            logger.error(f"max_retries が整数ではありません: {self.max_retries} (型: {type(self.max_retries)})")
            self.max_retries = 3

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"翻訳試行 {attempt + 1}/{self.max_retries}: {text[:50]}...")

                if self.translation_method == "googletrans_safe":
                    result = self._translate_with_googletrans(text, target_lang, source_lang)
                elif self.translation_method == "deepl":
                    result = self._translate_with_deepl(text, target_lang, source_lang)
                elif self.translation_method == "openai":
                    result = self._translate_with_openai(text, target_lang, source_lang)
                else:
                    raise ValueError(f"サポートされていない翻訳方法: {self.translation_method}")

                if result and result.strip():
                    logger.debug(f"翻訳成功: {result[:50]}...")
                    return result

                logger.warning(f"翻訳結果が空です (試行 {attempt + 1}/{self.max_retries})")

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"翻訳試行 {attempt + 1}/{self.max_retries} 失敗: {error_msg}")

                # 特定のエラーに対する対処
                if "cannot be interpreted as an integer" in error_msg:
                    logger.error("言語コードエラーが検出されました。言語コードを確認してください。")
                elif "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.warning("レート制限に達しました。待機時間を増やします。")
                    time.sleep(self.retry_delay * (attempt + 2))
                elif "503" in error_msg or "service unavailable" in error_msg.lower():
                    logger.warning("翻訳サービスが一時的に利用できません。")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"翻訳に失敗しました: {text[:100]}...")
                    return text  # 翻訳失敗時は元のテキストを返す

        return text

    def _translate_with_googletrans(self, text: str, target_lang: str, source_lang: str) -> Optional[str]:
        """Google翻訳での翻訳"""
        if not self.translator:
            raise Exception("Google翻訳クライアントが初期化されていません")

        try:
            # 引数の型を明示的に確認
            if not isinstance(text, str):
                text = str(text)
            if not isinstance(target_lang, str):
                target_lang = str(target_lang)
            if not isinstance(source_lang, str):
                source_lang = str(source_lang)

            result = self.translator.translate(
                text,
                dest=target_lang,
                src=source_lang
            )

            return result.text if hasattr(result, 'text') else str(result)

        except Exception as e:
            logger.error(f"Google翻訳エラー: {e}")
            raise

    def _translate_with_deepl(self, text: str, target_lang: str, source_lang: str) -> Optional[str]:
        """DeepLでの翻訳"""
        if not self.translator:
            raise Exception("DeepL翻訳クライアントが初期化されていません")

        try:
            # DeepL用の言語コード変換
            target_lang_deepl = self._convert_to_deepl_code(target_lang)
            source_lang_deepl = None if source_lang == "auto" else self._convert_to_deepl_code(source_lang)

            result = self.translator.translate_text(
                text,
                target_lang=target_lang_deepl,
                source_lang=source_lang_deepl
            )

            return result.text

        except Exception as e:
            logger.error(f"DeepL翻訳エラー: {e}")
            raise

    def _translate_with_openai(self, text: str, target_lang: str, source_lang: str) -> Optional[str]:
        """OpenAIでの翻訳"""
        if not self.translator:
            raise Exception("OpenAI翻訳クライアントが初期化されていません")

        try:
            language_name = self._get_language_name(target_lang)

            response = self.translator.chat.completions.create(
                model=self.config.get("openai_model", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": f"Translate the following text to {language_name}. Return only the translation without any explanations."},
                    {"role": "user", "content": text}
                ],
                max_tokens=min(len(text) * 2, 4000),
                temperature=0.1
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI翻訳エラー: {e}")
            raise

    def _translate_long_text(self, text: str, target_lang: str, source_lang: str) -> str:
        """長いテキストを分割して翻訳"""
        try:
            chunks = self._split_text_safely(text, self.max_text_length)
            translated_chunks = []

            for i, chunk in enumerate(chunks):
                logger.info(f"長文分割翻訳: {i+1}/{len(chunks)}")
                translated_chunk = self.translate_text(chunk.strip(), target_lang, source_lang)
                translated_chunks.append(translated_chunk or chunk)
                time.sleep(1)  # レート制限対策

            return " ".join(translated_chunks)

        except Exception as e:
            logger.error(f"長文翻訳エラー: {e}")
            return text

    def _split_text_safely(self, text: str, max_length: int) -> List[str]:
        """テキストを安全に分割"""
        import re

        # 文単位で分割を試行
        sentences = re.split(r'([.!?。！？]\s*)', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk + sentence) <= max_length:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _normalize_language_code(self, lang_code: str) -> str:
        """言語コードの正規化"""
        if not isinstance(lang_code, str):
            lang_code = str(lang_code)

        # 小文字に変換し、最初の2文字のみ使用
        normalized = lang_code.lower().strip()[:2]

        # 一般的な言語コードのマッピング
        code_mapping = {
            "ja": "ja", "jp": "ja", "japanese": "ja",
            "en": "en", "english": "en",
            "ko": "ko", "kr": "ko", "korean": "ko",
            "zh": "zh", "cn": "zh", "chinese": "zh",
            "es": "es", "spanish": "es",
            "fr": "fr", "french": "fr",
            "de": "de", "german": "de"
        }

        return code_mapping.get(normalized, normalized)

    def _convert_to_deepl_code(self, lang_code: str) -> str:
        """DeepL用言語コードに変換"""
        deepl_mapping = {
            "ja": "JA", "en": "EN-US", "ko": "KO", "zh": "ZH",
            "es": "ES", "fr": "FR", "de": "DE", "it": "IT",
            "pt": "PT-BR", "ru": "RU"
        }
        return deepl_mapping.get(lang_code.lower(), lang_code.upper())

    def _get_language_name(self, lang_code: str) -> str:
        """言語コードから言語名を取得"""
        name_mapping = {
            "ja": "Japanese", "en": "English", "ko": "Korean", "zh": "Chinese",
            "es": "Spanish", "fr": "French", "de": "German", "it": "Italian",
            "pt": "Portuguese", "ru": "Russian"
        }
        return name_mapping.get(lang_code.lower(), lang_code)

    def translate_transcript(self, transcription: Dict, target_lang: str = "ja") -> Optional[Dict]:
        """
        転写結果を翻訳（改善版）

        Args:
            transcription: 転写結果
            target_lang: 翻訳先言語コード

        Returns:
            翻訳された転写結果
        """
        try:
            if not transcription or not isinstance(transcription, dict):
                logger.error("転写結果が不正です")
                return None

            logger.info(f"転写テキストの翻訳開始 - 対象言語: {target_lang}")

            # 転写結果をコピー
            translated_transcription = transcription.copy()
            translated_transcription["translated_language"] = target_lang
            translated_transcription["translated_segments"] = []

            segments = transcription.get("segments", [])
            if not segments:
                logger.error("セグメントが見つかりません")
                return None

            total_segments = len(segments)
            logger.info(f"翻訳対象セグメント数: {total_segments}")

            # 各セグメントを翻訳
            for i, segment in enumerate(segments):
                try:
                    # セグメントの型チェック
                    if not isinstance(segment, dict):
                        logger.warning(f"セグメント {i} の型が不正です: {type(segment)}")
                        continue

                    original_text = segment.get("text", "")
                    if not isinstance(original_text, str):
                        original_text = str(original_text)

                    if not original_text.strip():
                        logger.debug(f"セグメント {i} は空です、スキップ")
                        continue

                    # 翻訳実行
                    translated_text = self.translate_text(original_text, target_lang)

                    # 翻訳結果をセグメントに追加
                    translated_segment = {
                        "start": segment.get("start", 0),
                        "end": segment.get("end", 0),
                        "original_text": original_text,
                        "text": translated_text or original_text
                    }

                    translated_transcription["translated_segments"].append(translated_segment)

                    # 進捗表示
                    if (i + 1) % 10 == 0 or (i + 1) == total_segments:
                        logger.info(f"翻訳進捗: {i + 1}/{total_segments} セグメント完了")

                    # レート制限対策
                    if i > 0 and i % self.batch_size == 0:
                        time.sleep(1)

                except Exception as e:
                    logger.warning(f"セグメント {i} の翻訳でエラー: {e}")
                    # エラーが発生したセグメントは元のテキストを保持
                    translated_segment = {
                        "start": segment.get("start", 0),
                        "end": segment.get("end", 0),
                        "original_text": segment.get("text", ""),
                        "text": segment.get("text", "")
                    }
                    translated_transcription["translated_segments"].append(translated_segment)

            # 全体テキストも翻訳
            full_text = transcription.get("text", "")
            if full_text:
                translated_transcription["translated_text"] = self.translate_text(full_text, target_lang)
            else:
                translated_transcription["translated_text"] = ""

            logger.info("転写テキストの翻訳完了")
            return translated_transcription

        except Exception as e:
            logger.error(f"転写テキストの翻訳エラー: {e}")
            import traceback
            logger.error(f"詳細エラー: {traceback.format_exc()}")
            return None

    def create_subtitle_file(self, translated_transcription: Dict, video_path: str, format: str = "srt") -> Optional[str]:
        """
        翻訳結果から字幕ファイルを生成（改善版）

        Args:
            translated_transcription: 翻訳された転写結果
            video_path: 元動画のパス
            format: 字幕フォーマット ("srt", "vtt")

        Returns:
            生成された字幕ファイルのパス
        """
        try:
            if not translated_transcription or not isinstance(translated_transcription, dict):
                logger.error("翻訳結果が不正です")
                return None

            video_path = Path(video_path)
            subtitle_filename = f"{video_path.stem}_translated.{format}"
            subtitle_path = self.output_dir / subtitle_filename

            logger.info(f"字幕ファイル生成中: {subtitle_path}")

            if format.lower() == "srt":
                return self._create_srt_file(translated_transcription, subtitle_path)
            elif format.lower() == "vtt":
                return self._create_vtt_file(translated_transcription, subtitle_path)
            else:
                logger.error(f"サポートされていない字幕フォーマット: {format}")
                return None

        except Exception as e:
            logger.error(f"字幕ファイル生成エラー: {e}")
            return None

    def _create_srt_file(self, translated_transcription: Dict, output_path: Path) -> Optional[str]:
        """SRT形式の字幕ファイルを生成（改善版）"""
        try:
            subs = pysrt.SubRipFile()
            segments = translated_transcription.get("translated_segments", [])

            if not segments:
                logger.error("翻訳セグメントが見つかりません")
                return None

            for i, segment in enumerate(segments):
                try:
                    # 型チェックと値の検証
                    start_time_val = segment.get("start")
                    end_time_val = segment.get("end")
                    text_val = segment.get("text", "")

                    # 数値型チェック
                    if not isinstance(start_time_val, (int, float)):
                        logger.warning(f"セグメント {i} の開始時間が不正: {start_time_val}")
                        start_time_val = 0
                    if not isinstance(end_time_val, (int, float)):
                        logger.warning(f"セグメント {i} の終了時間が不正: {end_time_val}")
                        end_time_val = start_time_val + 1

                    # タイムスタンプを変換
                    start_time = self._seconds_to_srt_time(float(start_time_val))
                    end_time = self._seconds_to_srt_time(float(end_time_val))

                    # テキストの型チェック
                    if not isinstance(text_val, str):
                        text_val = str(text_val)

                    # 字幕項目を作成
                    sub = pysrt.SubRipItem(
                        index=i + 1,
                        start=start_time,
                        end=end_time,
                        text=text_val.strip()
                    )
                    subs.append(sub)

                except Exception as e:
                    logger.warning(f"セグメント {i} のSRT作成でエラー: {e}")
                    continue

            # SRTファイルに保存
            subs.save(str(output_path), encoding='utf-8')
            logger.info(f"SRT字幕ファイル生成完了: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"SRT字幕ファイル生成エラー: {e}")
            return None

    def _create_vtt_file(self, translated_transcription: Dict, output_path: Path) -> Optional[str]:
        """VTT形式の字幕ファイルを生成（改善版）"""
        try:
            segments = translated_transcription.get("translated_segments", [])

            if not segments:
                logger.error("翻訳セグメントが見つかりません")
                return None

            # 手動でVTTファイルを作成（webvttライブラリの依存性を避ける）
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")

                for i, segment in enumerate(segments):
                    try:
                        start_time_val = float(segment.get("start", 0))
                        end_time_val = float(segment.get("end", 0))
                        text_val = str(segment.get("text", "")).strip()

                        # タイムスタンプをVTT形式に変換
                        start_time = self._seconds_to_vtt_time(start_time_val)
                        end_time = self._seconds_to_vtt_time(end_time_val)

                        # VTT形式で書き込み
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{text_val}\n\n")

                    except Exception as e:
                        logger.warning(f"セグメント {i} のVTT作成でエラー: {e}")
                        continue

            logger.info(f"VTT字幕ファイル生成完了: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"VTT字幕ファイル生成エラー: {e}")
            return None

    def _seconds_to_srt_time(self, seconds: float):
        """秒数をSRT時間フォーマットに変換（エラーハンドリング強化）"""
        try:
            seconds = max(0, float(seconds))  # 負の値を防ぐ
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)

            return pysrt.SubRipTime(hours, minutes, secs, milliseconds)
        except Exception as e:
            logger.error(f"SRT時間変換エラー: {e}")
            return pysrt.SubRipTime(0, 0, 0, 0)

    def _seconds_to_vtt_time(self, seconds: float) -> str:
        """秒数をVTT時間フォーマットに変換（エラーハンドリング強化）"""
        try:
            seconds = max(0, float(seconds))  # 負の値を防ぐ
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)

            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
        except Exception as e:
            logger.error(f"VTT時間変換エラー: {e}")
            return "00:00:00.000"

    def detect_language(self, text: str) -> Optional[str]:
        """
        テキストの言語を検出（改善版）

        Args:
            text: 検出するテキスト

        Returns:
            検出された言語コード
        """
        try:
            if not self.translator or self.translation_method != "googletrans_safe":
                logger.warning("言語検出はGoogle翻訳でのみサポートされています")
                return None

            if not isinstance(text, str) or not text.strip():
                return None

            result = self.translator.detect(text)
            return result.lang if hasattr(result, 'lang') else None
        except Exception as e:
            logger.error(f"言語検出エラー: {e}")
            return None

    def get_supported_languages(self) -> Dict[str, str]:
        """サポートされている言語の一覧を取得"""
        return {
            'ja': '日本語',
            'en': '英語',
            'ko': '韓国語',
            'zh': '中国語',
            'es': 'スペイン語',
            'fr': 'フランス語',
            'de': 'ドイツ語',
            'it': 'イタリア語',
            'pt': 'ポルトガル語',
            'ru': 'ロシア語',
        }

    def cleanup_translator(self):
        """翻訳クライアントのクリーンアップ"""
        try:
            if hasattr(self.translator, 'close'):
                self.translator.close()
            self.translator = None
            logger.info("翻訳クライアントをクリーンアップしました")
        except Exception as e:
            logger.warning(f"翻訳クライアントクリーンアップエラー: {e}")
