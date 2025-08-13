"""
翻訳モジュール - Coroutine問題完全解決版
既存のTranslatorクラスと互換性を保持
"""

import os
import pysrt
from pathlib import Path
from typing import Optional, Dict, List
import logging
import time
import json
import inspect
import requests
from urllib.parse import quote
import subprocess
import sys

logger = logging.getLogger(__name__)

class Translator:
    """テキスト翻訳と字幕生成を行うクラス（Coroutine問題解決版）"""

    def __init__(self, config):
        self.config = config
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        self.output_dir.mkdir(exist_ok=True)

        # 翻訳方法を設定で選択（デフォルトを変更）
        self.translation_method = config.get("translation_method", "direct_google")

        # 翻訳設定（型安全な取得）
        self.max_retries = self._safe_int(config.get("translation_retries"), 3)
        self.retry_delay = self._safe_float(config.get("translation_retry_delay"), 2.0)
        self.batch_size = self._safe_int(config.get("batch_size"), 3)
        self.max_text_length = self._safe_int(config.get("max_text_length"), 4000)

        logger.info(f"翻訳設定 - method: {self.translation_method}")

        # 翻訳クライアントの初期化
        self.translator = None
        self._init_translator()

    def _safe_int(self, value, default: int) -> int:
        """安全に整数値を取得"""
        try:
            if value is None:
                return default
            return int(float(str(value)))
        except (ValueError, TypeError):
            return default

    def _safe_float(self, value, default: float) -> float:
        """安全に浮動小数点値を取得"""
        try:
            if value is None:
                return default
            return float(str(value))
        except (ValueError, TypeError):
            return default

    def _init_translator(self):
        """翻訳クライアントを初期化"""
        try:
            if self.translation_method in ["googletrans_safe", "googletrans_fixed"]:
                self._init_googletrans_safe()
            elif self.translation_method == "direct_google":
                logger.info("直接Google翻訳APIを使用します")
                # 直接APIを使うのでtranslatorはNone
            else:
                logger.warning(f"未サポートの翻訳方法、direct_googleを使用: {self.translation_method}")
                self.translation_method = "direct_google"
        except Exception as e:
            logger.warning(f"翻訳クライアント初期化警告: {e}")
            logger.info("直接Google翻訳にフォールバック")
            self.translation_method = "direct_google"

    def _init_googletrans_safe(self):
        """安全なGoogle翻訳初期化"""
        try:
            from googletrans import Translator as GoogleTranslator

            self.translator = GoogleTranslator(
                service_urls=[
                    'translate.google.com',
                    'translate.google.co.jp',
                    'translate.google.co.kr'
                ],
                user_agent='Mozilla/5.0 (compatible; translator-bot)'
            )
            logger.info("Google翻訳クライアントを初期化しました")
        except ImportError:
            logger.warning("googletransが利用できません。直接APIを使用します。")
            self.translation_method = "direct_google"
            self.translator = None

    def translate_text(self, text: str, target_lang: str = "ja", source_lang: str = "auto") -> str:
        """
        テキストを翻訳（Coroutine問題完全解決版）
        """
        # 入力チェック
        if not text or not isinstance(text, str):
            return str(text) if text else ""

        text = text.strip()
        if not text:
            return ""

        # 言語コードの正規化
        target_lang = self._normalize_language_code(target_lang)

        # 翻訳実行
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"翻訳試行 {attempt + 1}: '{text[:50]}...'")

                # 翻訳方法に応じて実行
                if self.translation_method == "direct_google":
                    translated_text = self._translate_direct_google(text, target_lang, source_lang)
                elif self.translation_method == "subprocess":
                    translated_text = self._translate_subprocess(text, target_lang, source_lang)
                else:
                    translated_text = self._translate_googletrans_safe(text, target_lang, source_lang)

                # 結果の妥当性チェック
                if translated_text and self._is_valid_translation_result_v3(translated_text, text):
                    logger.debug(f"翻訳成功: '{translated_text[:30]}...'")
                    return translated_text
                else:
                    logger.warning(f"翻訳結果が無効 (試行 {attempt + 1}): '{translated_text[:30] if translated_text else 'None'}...'")

            except Exception as e:
                logger.warning(f"翻訳試行 {attempt + 1} 失敗: {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        # フォールバック処理
        fallback_result = self._try_fallback_translation(text, target_lang)
        if fallback_result:
            return fallback_result

        # すべて失敗した場合は元のテキストを返す
        logger.warning(f"翻訳失敗により元のテキストを返します: '{text[:50]}...'")
        return text

    def _translate_direct_google(self, text: str, target_lang: str, source_lang: str) -> Optional[str]:
        """
        Google翻訳APIに直接アクセス（最も安全）
        """
        try:
            # テキストをURLエンコード
            encoded_text = quote(text)

            # Google翻訳の公開API URL
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={encoded_text}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # JSONレスポンスを解析
            data = response.json()

            if data and len(data) > 0 and data[0] and len(data[0]) > 0:
                translated_parts = []
                for sentence in data[0]:
                    if sentence and len(sentence) > 0 and sentence[0]:
                        translated_parts.append(sentence[0])

                if translated_parts:
                    result = "".join(translated_parts).strip()
                    return result if result else None

            return None

        except Exception as e:
            logger.warning(f"直接Google翻訳エラー: {e}")
            return None

    def _translate_subprocess(self, text: str, target_lang: str, source_lang: str) -> Optional[str]:
        """
        サブプロセス経由で翻訳（完全分離）
        """
        try:
            # 翻訳スクリプトを作成
            escaped_text = text.replace('"""', '\\"\\"\\"')

            script_content = f'''
import sys
import json

def safe_translate():
    try:
        from googletrans import Translator
        translator = Translator()

        text = """{escaped_text}"""
        result = translator.translate(text, dest="{target_lang}", src="{source_lang}")

        if hasattr(result, 'text'):
            return str(result.text)
        else:
            return str(result)

    except Exception as e:
        return f"ERROR: {{str(e)}}"

if __name__ == "__main__":
    result = safe_translate()
    print(result)
'''

            # 一時ファイルに書き込み
            temp_script = self.output_dir / f"temp_translate_{int(time.time())}.py"
            with open(temp_script, 'w', encoding='utf-8') as f:
                f.write(script_content)

            try:
                # サブプロセスで実行
                result = subprocess.run([
                    sys.executable, str(temp_script)
                ], capture_output=True, text=True, timeout=30, encoding='utf-8')

                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output and not output.startswith("ERROR:"):
                        return output

            finally:
                # 一時ファイルを削除
                temp_script.unlink(missing_ok=True)

            return None

        except Exception as e:
            logger.warning(f"サブプロセス翻訳エラー: {e}")
            return None

    def _translate_googletrans_safe(self, text: str, target_lang: str, source_lang: str) -> Optional[str]:
        """
        googletransライブラリを使用した安全な翻訳
        """
        try:
            if not self.translator:
                return None

            # 翻訳実行
            result = self.translator.translate(
                text,
                dest=target_lang,
                src=source_lang if source_lang != "auto" else None
            )

            # 結果を安全に取得
            if hasattr(result, 'text'):
                translated_text = result.text
            else:
                translated_text = str(result)

            # coroutineが返された場合の対処
            if inspect.iscoroutine(translated_text):
                logger.warning("coroutineが検出されました。文字列変換を試行...")
                translated_text = str(translated_text)

                # coroutineの文字列表現が含まれている場合は失敗とする
                if 'coroutine object' in translated_text:
                    return None

            return str(translated_text).strip()

        except Exception as e:
            logger.warning(f"googletrans翻訳エラー: {e}")
            return None

    def _try_fallback_translation(self, text: str, target_lang: str) -> Optional[str]:
        """
        フォールバック翻訳（他の方法を試行）
        """
        fallback_methods = []

        # 現在の方法以外を試行
        if self.translation_method != "direct_google":
            fallback_methods.append(("direct_google", self._translate_direct_google))

        if self.translation_method != "subprocess":
            fallback_methods.append(("subprocess", self._translate_subprocess))

        if self.translation_method not in ["googletrans_safe", "googletrans_fixed"] and self.translator:
            fallback_methods.append(("googletrans_safe", self._translate_googletrans_safe))

        for method_name, method_func in fallback_methods:
            try:
                logger.info(f"フォールバック翻訳を試行: {method_name}")

                result = method_func(text, target_lang, "auto")

                if result and self._is_valid_translation_result_v3(result, text):
                    logger.info(f"フォールバック成功: {method_name}")
                    return result

            except Exception as e:
                logger.warning(f"フォールバック {method_name} 失敗: {e}")
                continue

        return None

    def _is_valid_translation_result_v3(self, result: str, original_text: str) -> bool:
        """
        翻訳結果の妥当性チェック（改良版）
        """
        try:
            # 1. 基本的な型チェック
            if not isinstance(result, str):
                logger.debug(f"結果が文字列ではありません: {type(result)}")
                return False

            # 2. 空文字列チェック
            if not result.strip():
                logger.debug("結果が空文字列です")
                return False

            # 3. 無効なパターンチェック
            result_lower = result.lower()
            invalid_patterns = [
                'coroutine object',
                '<coroutine',
                'coroutine at 0x',
                'generator object',
                '<generator',
                'error:',
                'exception:',
                'traceback',
                'failed',
                'timeout'
            ]

            for pattern in invalid_patterns:
                if pattern in result_lower:
                    logger.debug(f"無効パターン検出: {pattern}")
                    return False

            # 4. 長さの妥当性チェック
            if len(result) > len(original_text) * 15:
                logger.debug("結果が異常に長いです")
                return False

            # 5. 制御文字チェック
            if any(ord(char) < 32 for char in result if char not in '\n\r\t'):
                logger.debug("制御文字が含まれています")
                return False

            # 6. 実際のオブジェクトタイプチェック
            if inspect.iscoroutine(result) or inspect.isgenerator(result):
                logger.debug("coroutine/generatorオブジェクトです")
                return False

            return True

        except Exception as e:
            logger.error(f"翻訳結果検証中にエラー: {e}")
            return False

    def _normalize_language_code(self, lang_code: str) -> str:
        """言語コードの正規化"""
        code_mapping = {
            "ja": "ja", "jp": "ja", "japanese": "ja",
            "en": "en", "english": "en",
            "ko": "ko", "kr": "ko", "korean": "ko",
            "zh": "zh", "cn": "zh", "chinese": "zh",
        }
        normalized = str(lang_code).lower().strip()[:2]
        return code_mapping.get(normalized, normalized)

    def translate_transcript(self, transcription: Dict, target_lang: str = "ja") -> Optional[Dict]:
        """
        転写結果を翻訳（修正版）
        """
        try:
            if not transcription or not isinstance(transcription, dict):
                logger.error("転写結果が不正です")
                return None

            segments = transcription.get("segments", [])
            if not segments:
                logger.error("セグメントが見つかりません")
                return None

            logger.info(f"翻訳開始: {len(segments)} セグメント -> {target_lang}")

            # 結果格納用の辞書を作成
            translated_transcription = {
                "original_language": transcription.get("language", "unknown"),
                "translated_language": target_lang,
                "text": transcription.get("text", ""),
                "translated_text": "",
                "segments": transcription.get("segments", []),
                "translated_segments": []
            }

            successful_translations = 0
            failed_translations = 0
            full_translated_text = []

            # 各セグメントを翻訳
            for i, segment in enumerate(segments):
                try:
                    original_text = str(segment.get("text", "")).strip()
                    if not original_text:
                        logger.debug(f"セグメント {i+1} は空、スキップ")
                        continue

                    logger.info(f"セグメント {i+1}/{len(segments)} 翻訳中: '{original_text[:30]}...'")

                    # 翻訳を実行
                    translated_text = self.translate_text(original_text, target_lang)

                    # 翻訳結果を使用
                    translated_segment = {
                        "start": float(segment.get("start", 0)),
                        "end": float(segment.get("end", 0)),
                        "original_text": original_text,
                        "text": translated_text
                    }

                    translated_transcription["translated_segments"].append(translated_segment)
                    full_translated_text.append(translated_text)

                    if translated_text != original_text:
                        successful_translations += 1
                        logger.debug(f"翻訳成功: '{translated_text[:30]}...'")
                    else:
                        failed_translations += 1
                        logger.debug(f"翻訳未実行（元テキスト使用）: '{original_text[:30]}...'")

                    # 進捗表示
                    if (i + 1) % 5 == 0:
                        logger.info(f"進捗: {i+1}/{len(segments)} (成功: {successful_translations}, 失敗: {failed_translations})")

                    # レート制限対策
                    if i > 0 and i % self.batch_size == 0:
                        logger.debug("レート制限対策の待機中...")
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"セグメント {i+1} 翻訳エラー: {e}")
                    failed_translations += 1

                    # エラー時は元のテキストを保持
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
                            full_translated_text.append(original_text)
                    except Exception as nested_e:
                        logger.error(f"セグメント {i+1} エラー処理も失敗: {nested_e}")

            # 全体テキストを設定
            translated_transcription["translated_text"] = " ".join(full_translated_text)

            # 結果サマリー
            total_segments = len(translated_transcription["translated_segments"])
            logger.info(f"翻訳完了サマリー:")
            logger.info(f"  総セグメント数: {total_segments}")
            logger.info(f"  翻訳成功: {successful_translations}")
            logger.info(f"  翻訳失敗: {failed_translations}")

            if total_segments > 0:
                success_rate = (successful_translations / total_segments) * 100
                logger.info(f"  成功率: {success_rate:.1f}%")

            return translated_transcription

        except Exception as e:
            logger.error(f"転写翻訳エラー: {e}")
            import traceback
            logger.error(f"詳細: {traceback.format_exc()}")
            return None

    def create_subtitle_file(self, translated_transcription: Dict, video_path: str, format: str = "srt") -> Optional[str]:
        """
        翻訳結果から字幕ファイルを生成（修正版）
        """
        try:
            if not translated_transcription or not isinstance(translated_transcription, dict):
                logger.error("翻訳結果が不正です")
                return None

            segments = translated_transcription.get("translated_segments", [])
            if not segments:
                logger.error("翻訳セグメントが見つかりません")
                return None

            # 出力パスを生成
            video_path = Path(video_path)
            subtitle_filename = f"{video_path.stem}_translated.{format.lower()}"
            subtitle_path = self.output_dir / subtitle_filename

            logger.info(f"字幕ファイル生成: {subtitle_path} ({len(segments)} セグメント)")

            # SRT形式で生成
            if format.lower() == "srt":
                success = self._create_srt_file_safe(segments, subtitle_path)
            else:
                logger.error(f"未サポートの字幕形式: {format}")
                return None

            if success and subtitle_path.exists():
                # ファイル内容を検証
                if self._validate_srt_file(subtitle_path):
                    logger.info(f"字幕ファイル生成成功: {subtitle_path}")
                    return str(subtitle_path)
                else:
                    logger.error("生成された字幕ファイルが無効です")
                    return None
            else:
                logger.error("字幕ファイル生成に失敗しました")
                return None

        except Exception as e:
            logger.error(f"字幕ファイル生成エラー: {e}")
            return None

    def _create_srt_file_safe(self, segments: List[Dict], output_path: Path) -> bool:
        """安全にSRTファイルを生成"""
        try:
            subs = pysrt.SubRipFile()
            valid_count = 0

            for i, segment in enumerate(segments):
                try:
                    # データを取得
                    start_time = float(segment.get("start", 0))
                    end_time = float(segment.get("end", 0))
                    text = str(segment.get("text", "")).strip()

                    # 妥当性チェック
                    if not text:
                        logger.debug(f"セグメント {i+1} をスキップ: 空のテキスト")
                        continue

                    # 無効パターンチェック
                    if self._contains_invalid_patterns(text):
                        logger.warning(f"セグメント {i+1} をスキップ: 無効パターンが含まれています")
                        continue

                    if end_time <= start_time:
                        end_time = start_time + 1.0

                    if start_time < 0:
                        start_time = 0

                    # SRT時間オブジェクトを作成
                    start_srt = self._seconds_to_srt_time(start_time)
                    end_srt = self._seconds_to_srt_time(end_time)

                    # 字幕項目を作成
                    sub = pysrt.SubRipItem(
                        index=valid_count + 1,
                        start=start_srt,
                        end=end_srt,
                        text=text
                    )
                    subs.append(sub)
                    valid_count += 1

                    logger.debug(f"セグメント {valid_count} 追加: '{text[:30]}...'")

                except Exception as e:
                    logger.warning(f"セグメント {i+1} 処理エラー: {e}")
                    continue

            if valid_count == 0:
                logger.error("有効なセグメントが見つかりませんでした")
                return False

            # ファイルに保存
            subs.save(str(output_path), encoding='utf-8')
            logger.info(f"SRTファイル保存完了: {valid_count} セグメント")

            return True

        except Exception as e:
            logger.error(f"SRTファイル作成エラー: {e}")
            return False

    def _contains_invalid_patterns(self, text: str) -> bool:
        """テキストに無効なパターンが含まれているかチェック"""
        text_lower = text.lower()
        patterns = [
            'coroutine object',
            '<coroutine',
            'coroutine at 0x',
            'generator object',
            '<generator'
        ]
        return any(pattern in text_lower for pattern in patterns)

    def _seconds_to_srt_time(self, seconds: float):
        """秒数をSRT時間オブジェクトに変換"""
        try:
            seconds = max(0, float(seconds))
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)

            return pysrt.SubRipTime(hours, minutes, secs, milliseconds)
        except Exception as e:
            logger.error(f"時間変換エラー: {e}")
            return pysrt.SubRipTime(0, 0, 0, 0)

    def _validate_srt_file(self, file_path: Path) -> bool:
        """SRTファイルの妥当性をチェック"""
        try:
            if not file_path.exists() or file_path.stat().st_size == 0:
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 無効パターンチェック
            if self._contains_invalid_patterns(content):
                logger.error("SRTファイルに無効パターンが含まれています")
                return False

            # 基本的なSRT形式チェック
            if '-->' not in content:
                logger.error("SRTファイルにタイムスタンプが見つかりません")
                return False

            # pysrtで読み込みテスト
            pysrt.open(str(file_path), encoding='utf-8')

            logger.info("SRTファイル検証: OK")
            return True

        except Exception as e:
            logger.error(f"SRTファイル検証エラー: {e}")
            return False

    def debug_translation(self, test_text: str = "Hello, world!") -> Dict:
        """翻訳プロセスのデバッグ情報を出力"""
        debug_info = {
            "test_text": test_text,
            "translation_method": self.translation_method,
            "translator_type": type(self.translator).__name__ if self.translator else "None",
            "results": []
        }

        logger.info("=== 翻訳デバッグ開始 ===")

        try:
            # 現在の方法でテスト
            result = self.translate_text(test_text, "ja")

            debug_info["main_result"] = {
                "method": self.translation_method,
                "result": result,
                "valid": self._is_valid_translation_result_v3(result, test_text)
            }

            # 各方法を個別にテスト
            methods = [
                ("direct_google", self._translate_direct_google),
                ("subprocess", self._translate_subprocess),
                ("googletrans_safe", self._translate_googletrans_safe)
            ]

            for method_name, method_func in methods:
                try:
                    method_result = method_func(test_text, "ja", "auto")
                    debug_info["results"].append({
                        "method": method_name,
                        "result": method_result,
                        "valid": self._is_valid_translation_result_v3(method_result, test_text) if method_result else False
                    })
                except Exception as e:
                    debug_info["results"].append({
                        "method": method_name,
                        "error": str(e)
                    })

        except Exception as e:
            logger.error(f"デバッグ翻訳エラー: {e}")
            debug_info["error"] = str(e)

        logger.info("=== 翻訳デバッグ終了 ===")
        return debug_info


# ユーティリティ関数（既存のコードとの互換性のため）
def validate_srt_file(srt_path: str) -> bool:
    """SRTファイルの妥当性をチェック（外部関数）"""
    try:
        if not os.path.exists(srt_path):
            return False

        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 無効パターンチェック
        patterns = [
            'coroutine object',
            '<coroutine',
            'generator object',
            '<generator'
        ]

        for pattern in patterns:
            if pattern in content.lower():
                return False

        if not content.strip() or '-->' not in content:
            return False

        pysrt.open(srt_path, encoding='utf-8')
        return True

    except Exception:
        return False

def repair_srt_file(input_path: str, output_path: str) -> bool:
    """破損したSRTファイルを修復"""
    try:
        import re

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 無効パターンを修復
        patterns = [
            r'<coroutine object [^>]+>',
            r'<coroutine.*?>',
            r'<generator object [^>]+>',
            r'<generator.*?>',
        ]

        for pattern in patterns:
            content = re.sub(pattern, '[翻訳エラー]', content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return validate_srt_file(output_path)

    except Exception as e:
        logger.error(f"SRT修復エラー: {e}")
        return False
