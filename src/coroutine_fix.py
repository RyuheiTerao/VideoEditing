#!/usr/bin/env python3
"""
緊急修正スクリプト - coroutineオブジェクト問題の修正
"""

import os
import re
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_coroutine_in_srt_files(directory_path: str = "output"):
    """
    出力ディレクトリ内のすべてのSRTファイルからcoroutineオブジェクトを修復

    Args:
        directory_path: 修復対象のディレクトリパス
    """
    try:
        output_dir = Path(directory_path)
        if not output_dir.exists():
            logger.error(f"ディレクトリが見つかりません: {output_dir}")
            return

        srt_files = list(output_dir.glob("*.srt"))
        if not srt_files:
            logger.info("修復対象のSRTファイルが見つかりません")
            return

        logger.info(f"{len(srt_files)} 個のSRTファイルを検査します")

        for srt_file in srt_files:
            try:
                # ファイル内容を読み込み
                with open(srt_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # coroutineオブジェクトが含まれているかチェック
                if 'coroutine object' in content:
                    logger.info(f"修復対象ファイル: {srt_file}")

                    # バックアップを作成
                    backup_file = srt_file.with_suffix('.backup.srt')
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"バックアップ作成: {backup_file}")

                    # 修復処理
                    fixed_content = fix_coroutine_content(content)

                    # 修復されたファイルを保存
                    with open(srt_file, 'w', encoding='utf-8') as f:
                        f.write(fixed_content)

                    logger.info(f"修復完了: {srt_file}")
                else:
                    logger.info(f"修復不要: {srt_file}")

            except Exception as e:
                logger.error(f"ファイル修復エラー: {srt_file} - {e}")

        logger.info("SRTファイルの修復が完了しました")

    except Exception as e:
        logger.error(f"修復処理エラー: {e}")

def fix_coroutine_content(content: str) -> str:
    """
    コンテンツ内のcoroutineオブジェクトを修復

    Args:
        content: 修復対象のコンテンツ

    Returns:
        修復されたコンテンツ
    """
    try:
        # coroutineオブジェクトのパターンを定義
        patterns = [
            # 具体的なパターン
            r'<coroutine object Translator\.translate at 0x[a-fA-F0-9]+>',
            r'<coroutine object [^>]+\.translate at 0x[a-fA-F0-9]+>',
            r'<coroutine object [^>]+>',
            # より一般的なパターン
            r'<coroutine.*?>',
        ]

        fixed_content = content
        for pattern in patterns:
            matches = re.findall(pattern, fixed_content)
            if matches:
                logger.info(f"パターン '{pattern}' で {len(matches)} 個の一致を発見")
                fixed_content = re.sub(pattern, '[翻訳エラー - 再処理が必要]', fixed_content)

        # 追加の清理処理
        # 空行の正規化
        fixed_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', fixed_content)

        # 時間フォーマットの修正（.を,に変換）
        fixed_content = re.sub(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})', r'\1:\2:\3,\4', fixed_content)

        return fixed_content

    except Exception as e:
        logger.error(f"コンテンツ修復エラー: {e}")
        return content

def validate_srt_content(content: str) -> bool:
    """
    SRTコンテンツの妥当性をチェック

    Args:
        content: チェック対象のコンテンツ

    Returns:
        妥当性チェックの結果
    """
    try:
        # 基本的なチェック
        if not content.strip():
            return False

        # coroutineオブジェクトが含まれていないかチェック
        if 'coroutine object' in content:
            return False

        # タイムスタンプが含まれているかチェック
        if '-->' not in content:
            return False

        return True

    except Exception as e:
        logger.error(f"妥当性チェックエラー: {e}")
        return False

def create_emergency_translation_function():
    """
    緊急用の翻訳関数を作成（coroutineを避ける）
    """
    def emergency_translate(text: str, target_lang: str = "ja") -> str:
        """
        緊急用翻訳関数（同期処理のみ）
        """
        try:
            from googletrans import Translator as GoogleTranslator

            if not text or not isinstance(text, str):
                return str(text) if text else ""

            text = text.strip()
            if not text:
                return ""

            # Google翻訳クライアントを作成
            translator = GoogleTranslator(
                service_urls=['translate.google.com'],
                user_agent='Mozilla/5.0 (compatible; emergency-translator)'
            )

            # 同期的に翻訳を実行
            result = translator.translate(text, dest=target_lang, src='auto')

            # 結果を検証
            if hasattr(result, 'text'):
                translated = result.text
            else:
                translated = str(result)

            # coroutineでないことを確認
            if hasattr(translated, '__await__') or 'coroutine object' in str(translated):
                logger.error(f"緊急翻訳でもcoroutineが発生: {type(translated)}")
                return text  # 元のテキストを返す

            return str(translated).strip()

        except Exception as e:
            logger.error(f"緊急翻訳エラー: {e}")
            return text  # エラー時は元のテキストを返す

    return emergency_translate

def regenerate_clean_srt(original_transcript_path: str, output_srt_path: str, target_lang: str = "ja"):
    """
    元の転写データから新しいSRTファイルを生成（coroutineを避ける）

    Args:
        original_transcript_path: 元の転写データ（JSON）のパス
        output_srt_path: 出力SRTファイルのパス
        target_lang: 翻訳先言語
    """
    try:
        import json
        import pysrt

        # 元の転写データを読み込み
        with open(original_transcript_path, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)

        segments = transcript_data.get('segments', [])
        if not segments:
            logger.error("転写データにセグメントが見つかりません")
            return False

        # 緊急翻訳関数を取得
        emergency_translate = create_emergency_translation_function()

        # 新しいSRTファイルを作成
        subs = pysrt.SubRipFile()

        logger.info(f"新しいSRTファイルを生成中: {len(segments)} セグメント")

        for i, segment in enumerate(segments):
            try:
                start_time = float(segment.get('start', 0))
                end_time = float(segment.get('end', 0))
                original_text = segment.get('text', '').strip()

                if not original_text:
                    continue

                # 緊急翻訳を実行
                logger.info(f"セグメント {i+1}/{len(segments)} 翻訳中...")
                translated_text = emergency_translate(original_text, target_lang)

                # SRT時間オブジェクトを作成
                start_srt = _seconds_to_srt_time(start_time)
                end_srt = _seconds_to_srt_time(end_time)

                # 字幕項目を作成
                sub = pysrt.SubRipItem(
                    index=i + 1,
                    start=start_srt,
                    end=end_srt,
                    text=translated_text
                )
                subs.append(sub)

                # 進捗表示
                if (i + 1) % 10 == 0:
                    logger.info(f"進捗: {i + 1}/{len(segments)}")

                # レート制限対策
                if i > 0 and i % 5 == 0:
                    import time
                    time.sleep(1)

            except Exception as e:
                logger.error(f"セグメント {i} の処理エラー: {e}")
                continue

        # SRTファイルを保存
        subs.save(output_srt_path, encoding='utf-8')
        logger.info(f"新しいSRTファイルを生成完了: {output_srt_path}")

        # 妥当性チェック
        with open(output_srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if validate_srt_content(content):
            logger.info("生成されたSRTファイルは正常です")
            return True
        else:
            logger.error("生成されたSRTファイルに問題があります")
            return False

    except Exception as e:
        logger.error(f"SRT再生成エラー: {e}")
        return False

def _seconds_to_srt_time(seconds: float):
    """秒数をSRT時間フォーマットに変換"""
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

def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python coroutine_fix.py fix [directory_path]  # SRTファイル修復")
        print("  python coroutine_fix.py regen transcript.json output.srt [lang]  # SRT再生成")
        sys.exit(1)

    command = sys.argv[1]

    if command == "fix":
        directory = sys.argv[2] if len(sys.argv) > 2 else "output"
        fix_coroutine_in_srt_files(directory)

    elif command == "regen":
        if len(sys.argv) < 4:
            logger.error("転写データファイルと出力パスを指定してください")
            sys.exit(1)

        transcript_path = sys.argv[2]
        output_path = sys.argv[3]
        target_lang = sys.argv[4] if len(sys.argv) > 4 else "ja"

        success = regenerate_clean_srt(transcript_path, output_path, target_lang)
        sys.exit(0 if success else 1)

    else:
        logger.error(f"不明なコマンド: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
