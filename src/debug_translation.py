#!/usr/bin/env python3
"""
翻訳問題デバッグスクリプト
coroutine誤検出問題を詳細に調査します
"""

import os
import sys
import logging
import inspect
from pathlib import Path

# パスを追加してプロジェクトモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent / "src"))

from translator import Translator
from config_manager import ConfigManager

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_googletrans_directly():
    """Google翻訳を直接テスト"""
    try:
        logger.info("=== Google翻訳直接テスト ===")

        from googletrans import Translator as GoogleTranslator

        translator = GoogleTranslator(
            service_urls=['translate.google.com'],
            user_agent='Mozilla/5.0 (compatible; debug-translator)'
        )

        test_text = "JPブローズに日本人の人生があるんですか?"
        logger.info(f"テストテキスト: '{test_text}'")

        result = translator.translate(test_text, dest="ja", src="auto")

        logger.info(f"結果オブジェクト型: {type(result)}")
        logger.info(f"結果オブジェクト内容: {dir(result)}")

        if hasattr(result, 'text'):
            text_result = result.text
            logger.info(f"text属性の型: {type(text_result)}")
            logger.info(f"text属性の内容: '{text_result}'")
            logger.info(f"text属性の長さ: {len(str(text_result))}")

            # 詳細なオブジェクト分析
            logger.info(f"inspect.iscoroutine(text_result): {inspect.iscoroutine(text_result)}")
            logger.info(f"hasattr(text_result, '__await__'): {hasattr(text_result, '__await__')}")
            logger.info(f"'coroutine' in str(text_result): {'coroutine' in str(text_result)}")
            logger.info(f"'coroutine' in str(type(text_result)): {'coroutine' in str(type(text_result))}")

            # 文字列変換テスト
            str_result = str(text_result)
            logger.info(f"str()変換後の型: {type(str_result)}")
            logger.info(f"str()変換後の内容: '{str_result}'")

            return True
        else:
            logger.error("結果にtext属性がありません")
            return False

    except Exception as e:
        logger.error(f"直接テストエラー: {e}")
        import traceback
        logger.error(f"詳細: {traceback.format_exc()}")
        return False

def test_translator_class():
    """Translatorクラスをテスト"""
    try:
        logger.info("=== Translatorクラステスト ===")

        # 設定を作成
        config = {
            "translation_method": "googletrans_safe",
            "translation_retries": 3,
            "translation_retry_delay": 1.0,
            "batch_size": 1
        }

        translator = Translator(config)

        # デバッグ翻訳を実行
        test_text = "JPブローズに日本人の人生があるんですか?"
        debug_info = translator.debug_translation(test_text)

        logger.info("デバッグ情報:")
        for key, value in debug_info.items():
            if key != "results":
                logger.info(f"  {key}: {value}")

        for i, result in enumerate(debug_info.get("results", [])):
            logger.info(f"試行 {i+1} 詳細:")
            for k, v in result.items():
                logger.info(f"    {k}: {v}")

        return True

    except Exception as e:
        logger.error(f"Translatorクラステストエラー: {e}")
        import traceback
        logger.error(f"詳細: {traceback.format_exc()}")
        return False

def analyze_coroutine_detection():
    """coroutine検出ロジックを分析"""
    try:
        logger.info("=== coroutine検出分析 ===")

        # 様々な値でテスト
        test_values = [
            "普通の文字列",
            "",
            "coroutine object という文字列",
            "<coroutine object test at 0x123>",
            123,
            None,
        ]

        for value in test_values:
            logger.info(f"テスト値: {value} (型: {type(value)})")

            # str型チェック
            is_str = isinstance(value, str)
            logger.info(f"  isinstance(value, str): {is_str}")

            if is_str:
                # coroutineチェック
                is_coroutine = inspect.iscoroutine(value)
                has_await = hasattr(value, '__await__')
                contains_coroutine_text = 'coroutine object' in value.lower()

                logger.info(f"  inspect.iscoroutine(): {is_coroutine}")
                logger.info(f"  hasattr(__await__): {has_await}")
                logger.info(f"  contains 'coroutine object': {contains_coroutine_text}")

                # 最終判定
                would_be_invalid = is_coroutine or has_await or contains_coroutine_text
                logger.info(f"  判定結果: {'無効' if would_be_invalid else '有効'}")

            logger.info("")

        return True

    except Exception as e:
        logger.error(f"coroutine検出分析エラー: {e}")
        return False

def test_simple_translation():
    """シンプルな翻訳テスト"""
    try:
        logger.info("=== シンプル翻訳テスト ===")

        from googletrans import Translator as GoogleTranslator

        translator = GoogleTranslator()

        simple_text = "Hello"
        logger.info(f"シンプルテスト: '{simple_text}'")

        result = translator.translate(simple_text, dest="ja")

        if hasattr(result, 'text'):
            translated = result.text
            logger.info(f"翻訳結果: '{translated}' (型: {type(translated)})")

            # 文字列化テスト
            str_translated = str(translated)
            logger.info(f"文字列化結果: '{str_translated}' (型: {type(str_translated)})")

            # 基本チェック
            logger.info(f"空文字列チェック: {not str_translated.strip()}")
            logger.info(f"coroutine文字列チェック: {'coroutine object' in str_translated.lower()}")
            logger.info(f"実際のcoroutineチェック: {inspect.iscoroutine(str_translated)}")

            return str_translated

        return None

    except Exception as e:
        logger.error(f"シンプル翻訳テストエラー: {e}")
        return None

def create_fixed_translator():
    """修正版の翻訳関数を作成"""
    logger.info("=== 修正版翻訳関数作成 ===")

    def safe_translate_text(text: str, target_lang: str = "ja") -> str:
        """安全な翻訳関数（デバッグ用）"""
        try:
            logger.info(f"安全翻訳開始: '{text[:50]}...' -> {target_lang}")

            if not text or not isinstance(text, str):
                return str(text) if text else ""

            text = text.strip()
            if not text:
                return ""

            from googletrans import Translator as GoogleTranslator

            translator = GoogleTranslator(
                service_urls=['translate.google.com'],
                user_agent='Mozilla/5.0 (compatible; safe-translator)'
            )

            # 翻訳実行
            result = translator.translate(text, dest=target_lang, src='auto')

            # 結果を取得
            if hasattr(result, 'text'):
                translated_text = result.text
            else:
                translated_text = str(result)

            # 確実に文字列に変換
            final_result = str(translated_text).strip()

            # デバッグ情報
            logger.info(f"翻訳完了: '{final_result[:50]}...'")
            logger.info(f"結果型: {type(final_result)}")
            logger.info(f"長さ: {len(final_result)}")

            # 簡単な妥当性チェック（coroutine文字列のみ）
            if 'coroutine object' in final_result:
                logger.warning("結果にcoroutineが含まれています。元のテキストを返します")
                return text

            # 空でなければ返す
            if final_result:
                return final_result
            else:
                logger.warning("翻訳結果が空です。元のテキストを返します")
                return text

        except Exception as e:
            logger.error(f"安全翻訳エラー: {e}")
            return text

    return safe_translate_text

def run_comprehensive_test():
    """包括的なテスト"""
    try:
        logger.info("=" * 60)
        logger.info("包括的翻訳テスト開始")
        logger.info("=" * 60)

        # 1. 直接テスト
        logger.info("\n1. Google翻訳直接テスト")
        direct_success = test_googletrans_directly()

        # 2. シンプルテスト
        logger.info("\n2. シンプル翻訳テスト")
        simple_result = test_simple_translation()

        # 3. coroutine検出分析
        logger.info("\n3. coroutine検出分析")
        analysis_success = analyze_coroutine_detection()

        # 4. Translatorクラステスト
        logger.info("\n4. Translatorクラステスト")
        class_success = test_translator_class()

        # 5. 修正版翻訳テスト
        logger.info("\n5. 修正版翻訳テスト")
        safe_translate = create_fixed_translator()

        test_texts = [
            "JPブローズに日本人の人生があるんですか?",
            "Hello, world!",
            "This is a test.",
            "こんにちは"
        ]

        for text in test_texts:
            result = safe_translate(text)
            logger.info(f"テスト: '{text}' -> '{result}'")

        # 結果サマリー
        logger.info("\n" + "=" * 60)
        logger.info("テスト結果サマリー")
        logger.info("=" * 60)
        logger.info(f"直接テスト: {'成功' if direct_success else '失敗'}")
        logger.info(f"シンプルテスト: {'成功' if simple_result else '失敗'}")
        logger.info(f"検出分析: {'成功' if analysis_success else '失敗'}")
        logger.info(f"クラステスト: {'成功' if class_success else '失敗'}")

        return True

    except Exception as e:
        logger.error(f"包括テストエラー: {e}")
        return False

def main():
    """メイン処理"""
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "direct":
            test_googletrans_directly()
        elif command == "simple":
            test_simple_translation()
        elif command == "class":
            test_translator_class()
        elif command == "analyze":
            analyze_coroutine_detection()
        elif command == "safe":
            safe_translate = create_fixed_translator()
            test_text = sys.argv[2] if len(sys.argv) > 2 else "Hello, world!"
            result = safe_translate(test_text)
            print(f"翻訳結果: {result}")
        else:
            print(f"不明なコマンド: {command}")
    else:
        # デフォルトは包括テスト
        run_comprehensive_test()

if __name__ == "__main__":
    main()
