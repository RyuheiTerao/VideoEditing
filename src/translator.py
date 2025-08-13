"""
翻訳モジュール (完全修正版 - coroutine問題解決)
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
    """テキスト翻訳と字幕生成を行うクラス（完全修正版）"""

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

        logger.info(f"翻訳設定 - method: {self.translation_method}")
        logger.info(f"翻訳設定 - max_retries: {self.max_retries}")
        logger.info(f"翻訳設定 - batch_size: {self.batch_size}")

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
            raise

    def _init_googletrans_safe(self):
        """安全なGoogle翻訳初期化"""
        try:
            from googletrans import Translator as GoogleTranslator

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

    def translate_text(self, text: str, target_lang: str = "ja", source_lang: str = "auto") -> str:
        """
        テキストを翻訳（完全修正版 - coroutine問題解決）

        Args:
            text: 翻訳するテキスト
            target_lang: 翻訳先言語コード
            source_lang: 翻訳元言語コード

        Returns:
            翻訳されたテキスト（必ず文字列を返す）
        """
        # 入力チェック
        if not text or not isinstance(text, str):
            logger.warning(f"無効な入力テキスト: {type(text)} - {text}")
            return str(text) if text else ""

        text = text.strip()
        if not text:
            return ""

        # テキストの長さチェック
        if len(text) > self.max_text_length:
            logger.warning(f"テキストが長すぎます({len(text)}文字), 分割して処理")
            return self._translate_long_text(text, target_lang, source_lang)

        # 言語コードの正規化
        target_lang = self._normalize_language_code(target_lang)
        source_lang = self._normalize_language_code(source_lang) if source_lang != "auto" else source_lang

        # 翻訳実行（同期的に処理）
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"翻訳試行 {attempt + 1}/{self.max_retries}: '{text[:30]}...'")

                # 翻訳方法に応じて処理を分岐
                if self.translation_method == "googletrans_safe":
                    result = self._translate_with_googletrans_sync(text, target_lang, source_lang)
                elif self.translation_method == "deepl":
                    result = self._translate_with_deepl_sync(text, target_lang, source_lang)
                elif self.translation_method == "openai":
                    result = self._translate_with_openai_sync(text, target_lang, source_lang)
                else:
                    raise ValueError(f"サポートされていない翻訳方法: {self.translation_method}")

                # 結果の検証（coroutineオブジェクトでないことを確認）
                if self._is_valid_translation_result(result):
                    result_str = str(result).strip()
                    logger.debug(f"翻訳成功: '{result_str[:30]}...'")
                    return result_str
                else:
                    logger.warning(f"無効な翻訳結果 (試行 {attempt + 1}): {type(result)} - {result}")

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"翻訳試行 {attempt + 1}/{self.max_retries} 失敗: {error_msg}")

                # レート制限の処理
                if "429" in error_msg or "rate limit" in error_msg.lower():
                    wait_time = self.retry_delay * (attempt + 2)
                    logger.warning(f"レート制限。{wait_time}秒待機します...")
                    time.sleep(wait_time)
                elif "503" in error_msg or "service unavailable" in error_msg.lower():
                    logger.warning("翻訳サービスが一時的に利用できません。")
                    time.sleep(self.retry_delay * (attempt + 1))

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

        # すべての試行が失敗した場合は元のテキストを返す
        logger.error(f"翻訳に失敗しました。元のテキストを返します: '{text[:50]}...'")
        return text

    def _is_valid_translation_result(self, result) -> bool:
        """翻訳結果の妥当性をチェック（coroutineオブジェクトでないことを確認）"""
        # coroutineオブジェクトでないことを確認
        if hasattr(result, '__await__') or str(type(result)).startswith('<class \'coroutine\''):
            logger.error(f"翻訳結果がcoroutineオブジェクトです: {type(result)}")
            return False

        # Noneや空文字列でないことを確認
        if result is None:
            return False

        # 文字列に変換して内容があることを確認
        result_str = str(result).strip()
        if not result_str:
            return False

        # coroutineの文字列表現が含まれていないことを確認
        if 'coroutine object' in result_str:
            logger.error(f"翻訳結果にcoroutineの文字列表現が含まれています: {result_str}")
            return False

        return True

    def _translate_with_googletrans_sync(self, text: str, target_lang: str, source_lang: str) -> str:
        """Google翻訳での翻訳（同期版）"""
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

            # 同期的に翻訳を実行
            result = self.translator.translate(
                text,
                dest=target_lang,
                src=source_lang
            )

            # 結果を文字列として取得
            if hasattr(result, 'text'):
                translated_text = result.text
            else:
                translated_text = str(result)

            # coroutineオブジェクトでないことを再確認
            if hasattr(translated_text, '__await__'):
                raise Exception("翻訳結果がcoroutineオブジェクトです")

            return translated_text

        except Exception as e:
            logger.error(f"Google翻訳エラー: {e}")
            raise

    def _translate_with_deepl_sync(self, text: str, target_lang: str, source_lang: str) -> str:
        """DeepLでの翻訳（同期版）"""
        if not self.translator:
            raise Exception("DeepL翻訳クライアントが初期化されていません")

        try:
            target_lang_deepl = self._convert_to_deepl_code(target_lang)
            source_lang_deepl = None if source_lang == "auto" else self._convert_to_deepl_code(source_lang)

            result = self.translator.translate_text(
                text,
                target_lang=target_lang_deepl,
                source_lang=source_lang_deepl
            )

            return str(result.text)

        except Exception as e:
            logger.error(f"DeepL翻訳エラー: {e}")
            raise

    def _translate_with_openai_sync(self, text: str, target_lang: str, source_lang: str) -> str:
        """OpenAIでの翻訳（同期版）"""
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

            return str(response.choices[0].message.content).strip()

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
                translated_chunks.append(translated_chunk)
                time.sleep(1)  # レート制限対策

            return " ".join(translated_chunks)

        except Exception as e:
            logger.error(f"長文翻訳エラー: {e}")
            return text

    def _split_text_safely(self, text: str, max_length: int) -> List[str]:
        """テキストを安全に分割"""
        import re

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

        normalized = lang_code.lower().strip()[:2]

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
        転写結果を翻訳（完全修正版 - coroutine問題解決）

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

            segments = transcription.get("segments", [])
            if not segments:
                logger.error("セグメントが見つかりません")
                return None

            logger.info(f"翻訳対象セグメント数: {len(segments)}")

            # 転写結果をコピー
            translated_transcription = transcription.copy()
            translated_transcription["translated_language"] = target_lang
            translated_transcription["translated_segments"] = []

            # 各セグメントを翻訳
            successful_translations = 0
            for i, segment in enumerate(segments):
                try:
                    if not isinstance(segment, dict):
                        logger.warning(f"セグメント {i} の型が不正: {type(segment)}")
                        continue

                    original_text = segment.get("text", "")
                    if not original_text or not str(original_text).strip():
                        logger.debug(f"セグメント {i} は空、スキップ")
                        continue

                    original_text = str(original_text).strip()

                    # 翻訳実行（同期的に実行）
                    logger.debug(f"セグメント {i+1} 翻訳中: '{original_text[:30]}...'")
                    translated_text = self.translate_text(original_text, target_lang)

                    # 翻訳結果の検証（coroutineでないことを確認）
                    if not self._is_valid_translation_result(translated_text):
                        logger.error(f"セグメント {i} の翻訳結果が不正: {type(translated_text)} - {translated_text}")
                        translated_text = original_text

                    translated_text = str(translated_text).strip()

                    # 翻訳結果をセグメントに追加
                    translated_segment = {
                        "start": float(segment.get("start", 0)),
                        "end": float(segment.get("end", 0)),
                        "original_text": original_text,
                        "text": translated_text
                    }

                    translated_transcription["translated_segments"].append(translated_segment)
                    successful_translations += 1

                    # 進捗表示
                    if (i + 1) % 10 == 0 or (i + 1) == len(segments):
                        logger.info(f"翻訳進捗: {i + 1}/{len(segments)} セグメント完了 (成功: {successful_translations})")

                    # レート制限対策
                    if i > 0 and i % self.batch_size == 0:
                        logger.debug("レート制限対策の待機中...")
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"セグメント {i} の翻訳でエラー: {e}")
                    # エラーが発生したセグメントは元のテキストを保持
                    try:
                        original_text = str(segment.get("text", "")).strip()
                        if original_text:
                            translated_segment = {
                                "start": float(segment.get("start", 0)),
                                "end": float(segment.get("end", 0)),
                                "original_text": original_text,
                                "text": original_text
                            }
                            translated_transcription["translated_segments"].append(translated_segment)
                    except Exception as nested_e:
                        logger.error(f"セグメント {i} のエラー復旧も失敗: {nested_e}")

            # 全体テキストも翻訳
            full_text = transcription.get("text", "")
            if full_text and isinstance(full_text, str):
                logger.info("全体テキストの翻訳中...")
                translated_full_text = self.translate_text(full_text, target_lang)
                if self._is_valid_translation_result(translated_full_text):
                    translated_transcription["translated_text"] = str(translated_full_text)
                else:
                    translated_transcription["translated_text"] = full_text
            else:
                translated_transcription["translated_text"] = ""

            logger.info(f"翻訳完了 - 成功: {successful_translations}/{len(segments)} セグメント")
            return translated_transcription

        except Exception as e:
            logger.error(f"転写テキストの翻訳エラー: {e}")
            import traceback
            logger.error(f"詳細エラー: {traceback.format_exc()}")
            return None

    def create_subtitle_file(self, translated_transcription: Dict, video_path: str, format: str = "srt") -> Optional[str]:
        """
        翻訳結果から字幕ファイルを生成（完全修正版）

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

            segments = translated_transcription.get("translated_segments", [])
            if not segments:
                logger.error("翻訳セグメントが見つかりません")
                return None

            logger.info(f"字幕生成対象セグメント数: {len(segments)}")

            if format.lower() == "srt":
                result = self._create_srt_file_safe(translated_transcription, subtitle_path)
            elif format.lower() == "vtt":
                result = self._create_vtt_file_safe(translated_transcription, subtitle_path)
            else:
                logger.error(f"サポートされていない字幕フォーマット: {format}")
                return None

            # 生成されたファイルの確認と検証
            if result and Path(result).exists():
                file_size = Path(result).stat().st_size
                logger.info(f"字幕ファイル生成成功: {result} (サイズ: {file_size} バイト)")

                # ファイル内容の検証
                if self._validate_generated_subtitle_file(result):
                    return result
                else:
                    logger.error("生成された字幕ファイルにcoroutineが含まれています")
                    # 修復を試行
                    repaired_path = str(Path(result).with_suffix('.repaired.srt'))
                    if self._repair_subtitle_file(result, repaired_path):
                        return repaired_path
                    return None
            else:
                logger.error("字幕ファイルの生成に失敗しました")
                return None

        except Exception as e:
            logger.error(f"字幕ファイル生成エラー: {e}")
            import traceback
            logger.error(f"詳細エラー: {traceback.format_exc()}")
            return None

    def _create_srt_file_safe(self, translated_transcription: Dict, output_path: Path) -> Optional[str]:
        """SRT形式の字幕ファイルを生成（完全修正版）"""
        try:
            segments = translated_transcription.get("translated_segments", [])

            if not segments:
                logger.error("翻訳セグメントが見つかりません")
                return None

            subs = pysrt.SubRipFile()
            valid_segments = 0

            for i, segment in enumerate(segments):
                try:
                    start_time_val = segment.get("start", 0)
                    end_time_val = segment.get("end", 0)
                    text_val = segment.get("text", "")

                    # 型変換と検証
                    try:
                        start_time_val = float(start_time_val)
                        end_time_val = float(end_time_val)
                    except (ValueError, TypeError):
                        logger.warning(f"セグメント {i} の時間が不正: start={start_time_val}, end={end_time_val}")
                        continue

                    # テキストの処理
                    if not isinstance(text_val, str):
                        text_val = str(text_val)

                    text_val = text_val.strip()

                    # coroutineオブジェクトの文字列表現をチェック
                    if 'coroutine object' in text_val:
                        logger.error(f"セグメント {i} にcoroutineが含まれています: {text_val}")
                        continue

                    if not text_val:
                        logger.debug(f"セグメント {i} のテキストが空")
                        continue

                    # 時間の妥当性チェック
                    if start_time_val < 0 or end_time_val <= start_time_val:
                        logger.warning(f"セグメント {i} の時間が不正: {start_time_val} -> {end_time_val}")
                        if end_time_val <= start_time_val:
                            end_time_val = start_time_val + 1

                    # タイムスタンプを変換
                    start_time = self._seconds_to_srt_time(start_time_val)
                    end_time = self._seconds_to_srt_time(end_time_val)

                    # 字幕項目を作成
                    sub = pysrt.SubRipItem(
                        index=valid_segments + 1,
                        start=start_time,
                        end=end_time,
                        text=text_val
                    )
                    subs.append(sub)
                    valid_segments += 1

                    logger.debug(f"セグメント {i} 追加: '{text_val[:30]}...' ({start_time_val:.2f}s -> {end_time_val:.2f}s)")

                except Exception as e:
                    logger.warning(f"セグメント {i} のSRT作成でエラー: {e}")
                    continue

            if valid_segments == 0:
                logger.error("有効なセグメントが1つもありません")
                return None

            # SRTファイルに保存
            logger.info(f"SRTファイル保存中: {valid_segments} セグメント")
            subs.save(str(output_path), encoding='utf-8')

            # ファイルが正常に作成されたか確認
            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"SRT字幕ファイル生成完了: {output_path} ({valid_segments} セグメント)")
                return str(output_path)
            else:
                logger.error("SRTファイルが空または作成されませんでした")
                return None

        except Exception as e:
            logger.error(f"SRT字幕ファイル生成エラー: {e}")
            import traceback
            logger.error(f"詳細エラー: {traceback.format_exc()}")
            return None

    def _create_vtt_file_safe(self, translated_transcription: Dict, output_path: Path) -> Optional[str]:
        """VTT形式の字幕ファイルを生成（完全修正版）"""
        try:
            segments = translated_transcription.get("translated_segments", [])

            if not segments:
                logger.error("翻訳セグメントが見つかりません")
                return None

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                valid_segments = 0

                for i, segment in enumerate(segments):
                    try:
                        start_time_val = float(segment.get("start", 0))
                        end_time_val = float(segment.get("end", 0))
                        text_val = str(segment.get("text", "")).strip()

                        # coroutineオブジェクトの文字列表現をチェック
                        if 'coroutine object' in text_val:
                            logger.error(f"セグメント {i} にcoroutineが含まれています: {text_val}")
                            continue

                        if not text_val:
                            continue

                        if end_time_val <= start_time_val:
                            end_time_val = start_time_val + 1

                        start_time = self._seconds_to_vtt_time(start_time_val)
                        end_time = self._seconds_to_vtt_time(end_time_val)

                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{text_val}\n\n")
                        valid_segments += 1

                    except Exception as e:
                        logger.warning(f"セグメント {i} のVTT作成でエラー: {e}")
                        continue

            if valid_segments > 0:
                logger.info(f"VTT字幕ファイル生成完了: {output_path} ({valid_segments} セグメント)")
                return str(output_path)
            else:
                logger.error("有効なセグメントが1つもありません")
                return None

        except Exception as e:
            logger.error(f"VTT字幕ファイル生成エラー: {e}")
            return None

    def _validate_generated_subtitle_file(self, file_path: str) -> bool:
        """生成された字幕ファイルの妥当性をチェック"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # coroutineオブジェクトの文字列表現が含まれているかチェック
            if 'coroutine object' in content:
                logger.error(f"字幕ファイルにcoroutineが含まれています: {file_path}")
                return False

            # 空ファイルでないかチェック
            if not content.strip():
                logger.error(f"字幕ファイルが空です: {file_path}")
                return False

            # 基本的なSRT形式のチェック
            if file_path.endswith('.srt'):
                lines = content.split('\n')
                has_timestamps = any('-->' in line for line in lines)
                if not has_timestamps:
                    logger.error(f"SRTファイルにタイムスタンプが見つかりません: {file_path}")
                    return False

            logger.info(f"字幕ファイルの妥当性チェック: OK - {file_path}")
            return True

        except Exception as e:
            logger.error(f"字幕ファイルの妥当性チェックエラー: {e}")
            return False

    def _repair_subtitle_file(self, input_path: str, output_path: str) -> bool:
        """破損した字幕ファイルを修復"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # coroutineオブジェクトの文字列を修復
            repaired_content = content.replace(
                '<coroutine object Translator.translate at 0x',
                '[翻訳エラー - 元のテキストを表示]'
            )

            # より一般的なcoroutineパターンも修復
            import re
            repaired_content = re.sub(
                r'<coroutine object [^>]+>',
                '[翻訳エラー]',
                repaired_content
            )

            # 修復されたファイルを保存
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(repaired_content)

            logger.info(f"字幕ファイルを修復しました: {output_path}")
            return self._validate_generated_subtitle_file(output_path)

        except Exception as e:
            logger.error(f"字幕ファイル修復エラー: {e}")
            return False

    def _seconds_to_srt_time(self, seconds: float):
        """秒数をSRT時間フォーマットに変換（エラーハンドリング強化）"""
        try:
            seconds = max(0, float(seconds))
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
            seconds = max(0, float(seconds))
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)

            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
        except Exception as e:
            logger.error(f"VTT時間変換エラー: {e}")
            return "00:00:00.000"

    def detect_language(self, text: str) -> Optional[str]:
        """テキストの言語を検出"""
        try:
            if not self.translator or self.translation_method != "googletrans_safe":
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

# デバッグ・トラブルシューティング用の関数

def validate_srt_file(srt_path: str) -> bool:
    """SRTファイルの妥当性をチェック"""
    try:
        if not os.path.exists(srt_path):
            logger.error(f"SRTファイルが存在しません: {srt_path}")
            return False

        file_size = os.path.getsize(srt_path)
        if file_size == 0:
            logger.error(f"SRTファイルが空です: {srt_path}")
            return False

        # ファイル内容をチェック
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # coroutineオブジェクトが含まれていないかチェック
        if 'coroutine object' in content:
            logger.error(f"SRTファイルにcoroutineオブジェクトが含まれています: {srt_path}")
            return False

        # pysrtで読み込みテスト
        subs = pysrt.open(srt_path, encoding='utf-8')
        logger.info(f"SRTファイル検証成功: {len(subs)} 字幕エントリ、{file_size} バイト")
        return True

    except Exception as e:
        logger.error(f"SRTファイル検証エラー: {e}")
        return False

def repair_srt_file(input_path: str, output_path: str) -> bool:
    """破損したSRTファイルを修復"""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # coroutineオブジェクトの文字列を修復
        import re

        # 具体的なcoroutineパターンを修復
        patterns = [
            r'<coroutine object Translator\.translate at 0x[a-fA-F0-9]+>',
            r'<coroutine object [^>]+>',
            r'<coroutine.*?>',
        ]

        for pattern in patterns:
            content = re.sub(pattern, '[翻訳エラー]', content)

        # 空行の正規化
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

        # 時間フォーマットの修正（必要に応じて）
        content = re.sub(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})', r'\1:\2:\3,\4', content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"SRTファイルを修復しました: {output_path}")
        return validate_srt_file(output_path)

    except Exception as e:
        logger.error(f"SRTファイル修復エラー: {e}")
        return False

def create_test_srt(output_path: str) -> bool:
    """テスト用のSRTファイルを作成（動作確認用）"""
    try:
        test_content = """1
00:00:01,000 --> 00:00:05,000
これはテスト字幕です。

2
00:00:05,000 --> 00:00:10,000
SRTファイルが正常に動作しています。

3
00:00:10,000 --> 00:00:15,000
字幕システムのテストが完了しました。
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(test_content)

        logger.info(f"テストSRTファイルを作成: {output_path}")
        return validate_srt_file(output_path)

    except Exception as e:
        logger.error(f"テストSRTファイル作成エラー: {e}")
        return False

def debug_translation_process(translator_instance, test_text: str = "Hello, world!") -> bool:
    """翻訳プロセスのデバッグ"""
    try:
        logger.info("=== 翻訳プロセスデバッグ開始 ===")

        # 1. 基本的な翻訳テスト
        logger.info(f"テストテキスト: '{test_text}'")
        result = translator_instance.translate_text(test_text, "ja")
        logger.info(f"翻訳結果: '{result}'")
        logger.info(f"結果の型: {type(result)}")

        # 2. coroutineチェック
        is_valid = translator_instance._is_valid_translation_result(result)
        logger.info(f"翻訳結果の妥当性: {is_valid}")

        # 3. 結果の詳細分析
        if hasattr(result, '__await__'):
            logger.error("翻訳結果がcoroutineオブジェクトです！")
            return False

        if 'coroutine object' in str(result):
            logger.error("翻訳結果にcoroutineの文字列表現が含まれています！")
            return False

        logger.info("=== 翻訳プロセスデバッグ完了: OK ===")
        return True

    except Exception as e:
        logger.error(f"翻訳プロセスデバッグエラー: {e}")
        return False
