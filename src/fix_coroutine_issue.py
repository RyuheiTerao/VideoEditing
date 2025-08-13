#!/usr/bin/env python3
"""
緊急修正スクリプト - coroutine問題の完全解決
YouTube動画翻訳システムで発生しているcoroutineオブジェクト問題を修正します
"""

import os
import re
import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CoroutineFixer:
    """coroutineオブジェクト問題の修正を行うクラス"""

    def __init__(self):
        self.output_dir = Path("output")
        self.backup_dir = Path("backup")
        self.backup_dir.mkdir(exist_ok=True)

    def scan_and_fix_all_files(self) -> bool:
        """出力ディレクトリ内のすべてのファイルをスキャンして修正"""
        try:
            if not self.output_dir.exists():
                logger.error(f"出力ディレクトリが見つかりません: {self.output_dir}")
                return False

            logger.info(f"ファイルスキャン開始: {self.output_dir}")

            # SRTファイルをスキャン
            srt_files = list(self.output_dir.glob("*.srt"))
            fixed_count = 0

            for srt_file in srt_files:
                logger.info(f"SRTファイル検査中: {srt_file}")

                if self._contains_coroutine_issue(srt_file):
                    logger.warning(f"coroutine問題を発見: {srt_file}")
                    if self.fix_srt_file(srt_file):
                        fixed_count += 1
                        logger.info(f"修正完了: {srt_file}")
                    else:
                        logger.error(f"修正失敗: {srt_file}")
                else:
                    logger.info(f"問題なし: {srt_file}")

            logger.info(f"スキャン完了: {len(srt_files)} ファイル中 {fixed_count} ファイルを修正")
            return True

        except Exception as e:
            logger.error(f"ファイルスキャンエラー: {e}")
            return False

    def _contains_coroutine_issue(self, file_path: Path) -> bool:
        """ファイルにcoroutine問題が含まれているかチェック"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # coroutineオブジェクトの文字列表現をチェック
            patterns = [
                r'<coroutine object',
                r'coroutine object',
                r'<coroutine\s+object',
            ]

            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True

            return False

        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {e}")
            return False

    def fix_srt_file(self, srt_path: Path) -> bool:
        """SRTファイルのcoroutine問題を修正"""
        try:
            # バックアップを作成
            backup_path = self.backup_dir / f"{srt_path.stem}_backup_{int(time.time())}.srt"
            with open(srt_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            logger.info(f"バックアップ作成: {backup_path}")

            # 修正処理
            fixed_content = self._fix_content(original_content)

            # 修正されたファイルを保存
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)

            # 修正結果の検証
            if self._validate_fixed_srt(srt_path):
                logger.info(f"SRTファイル修正成功: {srt_path}")
                return True
            else:
                # 修正に失敗した場合は元に戻す
                logger.error(f"修正結果が無効、元のファイルに戻します: {srt_path}")
                with open(srt_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                return False

        except Exception as e:
            logger.error(f"SRTファイル修正エラー: {e}")
            return False

    def _fix_content(self, content: str) -> str:
        """コンテンツのcoroutine問題を修正"""
        try:
            # 修正パターンと置換文字列
            fix_patterns = [
                # 具体的なcoroutineオブジェクトパターン
                (r'<coroutine object Translator\.translate at 0x[a-fA-F0-9]+>', '[翻訳処理中]'),
                (r'<coroutine object [^>]+\.translate at 0x[a-fA-F0-9]+>', '[翻訳処理中]'),

                # より一般的なパターン
                (r'<coroutine object [^>]+>', '[翻訳エラー]'),
                (r'<coroutine\s+object\s+[^>]+>', '[翻訳エラー]'),

                # さらに広いパターン
                (r'<coroutine[^>]*>', '[翻訳エラー]'),

                # 文字列として残ったcoroutine参照
                (r'coroutine object [^\s\n]+', '[翻訳エラー]'),
            ]

            fixed_content = content
            total_replacements = 0

            for pattern, replacement in fix_patterns:
                matches = re.findall(pattern, fixed_content, re.IGNORECASE)
                if matches:
                    logger.info(f"パターン修正: '{pattern}' -> {len(matches)} 箇所")
                    fixed_content = re.sub(pattern, replacement, fixed_content, flags=re.IGNORECASE)
                    total_replacements += len(matches)

            # 追加の清理処理
            # 連続する空行を正規化
            fixed_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', fixed_content)

            # SRT時間フォーマットの正規化（.を,に）
            fixed_content = re.sub(r'(\d{2}:\d{2}:\d{2})\.(\d{3})', r'\1,\2', fixed_content)

            # 空のセグメントを削除
            fixed_content = self._remove_empty_segments(fixed_content)

            logger.info(f"修正完了: {total_replacements} 箇所を置換")
            return fixed_content

        except Exception as e:
            logger.error(f"コンテンツ修正エラー: {e}")
            return content

    def _remove_empty_segments(self, content: str) -> str:
        """空のセグメントを削除"""
        try:
            lines = content.split('\n')
            result_lines = []
            i = 0
            segment_number = 1

            while i < len(lines):
                line = lines[i].strip()

                # セグメント番号の行
                if line.isdigit():
                    # 次の行（時間）と次の次の行（テキスト）をチェック
                    if i + 2 < len(lines):
                        time_line = lines[i + 1].strip()
                        text_line = lines[i + 2].strip()

                        # 時間行が正しい形式で、テキストが空でない場合
                        if '-->' in time_line and text_line and text_line != '[翻訳エラー]':
                            result_lines.append(str(segment_number))
                            result_lines.append(time_line)
                            result_lines.append(text_line)
                            result_lines.append('')  # 空行
                            segment_number += 1
                            i += 3
                        else:
                            # 空のセグメントはスキップ
                            i += 3
                    else:
                        i += 1
                else:
                    i += 1

            return '\n'.join(result_lines)

        except Exception as e:
            logger.error(f"空セグメント削除エラー: {e}")
            return content

    def _validate_fixed_srt(self, srt_path: Path) -> bool:
        """修正されたSRTファイルの妥当性を検証"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # coroutineが残っていないかチェック
            if 'coroutine object' in content.lower():
                logger.error("修正後もcoroutineが残っています")
                return False

            # 空ファイルでないかチェック
            if not content.strip():
                logger.error("修正後のファイルが空です")
                return False

            # 基本的なSRT形式チェック
            if '-->' not in content:
                logger.error("タイムスタンプが見つかりません")
                return False

            # pysrtで読み込みテスト
            try:
                import pysrt
                subs = pysrt.open(str(srt_path), encoding='utf-8')
                if len(subs) == 0:
                    logger.error("有効な字幕エントリが見つかりません")
                    return False
                logger.info(f"検証成功: {len(subs)} 個の字幕エントリ")
            except ImportError:
                logger.warning("pysrtが利用できません。基本チェックのみ実行")

            return True

        except Exception as e:
            logger.error(f"SRTファイル検証エラー: {e}")
            return False

    def regenerate_srt_from_transcript(self, transcript_json_path: str, output_srt_path: str) -> bool:
        """元の転写データからSRTファイルを再生成"""
        try:
            logger.info(f"SRT再生成開始: {transcript_json_path} -> {output_srt_path}")

            # 転写データを読み込み
            with open(transcript_json_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)

            segments = transcript_data.get('segments', [])
            if not segments:
                logger.error("転写データにセグメントが見つかりません")
                return False

            # 緊急翻訳クライアントを初期化
            emergency_translator = self._create_emergency_translator()
            if not emergency_translator:
                logger.error("緊急翻訳クライアントの初期化に失敗")
                return False

            # SRTファイルを生成
            srt_content = []
            successful_segments = 0

            for i, segment in enumerate(segments):
                try:
                    start_time = float(segment.get('start', 0))
                    end_time = float(segment.get('end', 0))
                    original_text = str(segment.get('text', '')).strip()

                    if not original_text:
                        continue

                    # 翻訳実行
                    logger.info(f"セグメント {i+1}/{len(segments)} 翻訳中...")
                    translated_text = emergency_translator.translate_text(original_text, "ja")

                    # 翻訳結果の検証
                    if not isinstance(translated_text, str) or 'coroutine' in str(translated_text):
                        logger.warning(f"セグメント {i+1} 翻訳失敗、元のテキストを使用")
                        translated_text = original_text

                    # SRT形式で追加
                    start_srt = self._seconds_to_srt_time(start_time)
                    end_srt = self._seconds_to_srt_time(end_time)

                    successful_segments += 1
                    srt_content.append(f"{successful_segments}")
                    srt_content.append(f"{start_srt} --> {end_srt}")
                    srt_content.append(translated_text)
                    srt_content.append("")  # 空行

                    # 進捗表示とレート制限
                    if i % 5 == 0:
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"セグメント {i+1} 処理エラー: {e}")
                    continue

            # ファイルに保存
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))

            logger.info(f"SRT再生成完了: {successful_segments} セグメント")
            return self._validate_fixed_srt(Path(output_srt_path))

        except Exception as e:
            logger.error(f"SRT再生成エラー: {e}")
            return False

    def _create_emergency_translator(self):
        """緊急用の翻訳クライアントを作成"""
        try:
            from googletrans import Translator as GoogleTranslator

            class EmergencyTranslator:
                def __init__(self):
                    self.translator = GoogleTranslator(
                        service_urls=['translate.google.com'],
                        user_agent='Mozilla/5.0 (compatible; emergency-translator)'
                    )

                def translate_text(self, text: str, target_lang: str = "ja") -> str:
                    try:
                        if not text or not isinstance(text, str):
                            return str(text) if text else ""

                        result = self.translator.translate(text, dest=target_lang, src='auto')

                        if hasattr(result, 'text'):
                            translated = result.text
                        else:
                            translated = str(result)

                        # coroutineでないことを確認
                        if hasattr(translated, '__await__') or 'coroutine' in str(translated):
                            return text

                        return str(translated).strip()

                    except Exception as e:
                        logger.warning(f"緊急翻訳エラー: {e}")
                        return text

            return EmergencyTranslator()

        except ImportError:
            logger.error("googletransが必要です: pip install googletrans==4.0.0rc1")
            return None
        except Exception as e:
            logger.error(f"緊急翻訳クライアント作成エラー: {e}")
            return None

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """秒数をSRT時間フォーマットに変換"""
        try:
            seconds = max(0, float(seconds))
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)

            return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
        except Exception:
            return "00:00:00,000"

def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python fix_coroutine_issue.py scan        # 全ファイルをスキャンして修正")
        print("  python fix_coroutine_issue.py fix <file>  # 特定のファイルを修正")
        print("  python fix_coroutine_issue.py regen <json> <srt>  # 転写データからSRT再生成")
        sys.exit(1)

    command = sys.argv[1]
    fixer = CoroutineFixer()

    if command == "scan":
        success = fixer.scan_and_fix_all_files()
        print("=" * 50)
        if success:
            print("✅ スキャンと修正が完了しました")
        else:
            print("❌ スキャンと修正に失敗しました")
        print("=" * 50)
        sys.exit(0 if success else 1)

    elif command == "fix":
        if len(sys.argv) < 3:
            print("修正対象のファイルを指定してください")
            sys.exit(1)

        file_path = Path(sys.argv[2])
        if not file_path.exists():
            print(f"ファイルが見つかりません: {file_path}")
            sys.exit(1)

        success = fixer.fix_srt_file(file_path)
        print("=" * 50)
        if success:
            print(f"✅ ファイル修正完了: {file_path}")
        else:
            print(f"❌ ファイル修正失敗: {file_path}")
        print("=" * 50)
        sys.exit(0 if success else 1)

    elif command == "regen":
        if len(sys.argv) < 4:
            print("転写JSONファイルと出力SRTファイルを指定してください")
            sys.exit(1)

        json_path = sys.argv[2]
        srt_path = sys.argv[3]

        if not os.path.exists(json_path):
            print(f"転写ファイルが見つかりません: {json_path}")
            sys.exit(1)

        success = fixer.regenerate_srt_from_transcript(json_path, srt_path)
        print("=" * 50)
        if success:
            print(f"✅ SRT再生成完了: {srt_path}")
        else:
            print(f"❌ SRT再生成失敗: {srt_path}")
        print("=" * 50)
        sys.exit(0 if success else 1)

    else:
        print(f"不明なコマンド: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
