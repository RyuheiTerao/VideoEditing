"""
AI動画編集モジュール（将来の機能）
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from moviepy.editor import VideoFileClip, concatenate_videoclips
import logging

logger = logging.getLogger(__name__)

class AIVideoEditor:
    """AI を使った動画編集クラス"""

    def __init__(self, config):
        self.config = config
        self.ai_config = config.get("ai_editing", {})
        self.api_provider = self.ai_config.get("api_provider", "openai")
        self.model = self.ai_config.get("model", "gpt-4")
        self.target_duration = self.ai_config.get("target_duration", 600)  # 10分

        # API設定
        if self.api_provider == "openai":
            self.api_key = self.ai_config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
            if self.api_key:
                import openai
                openai.api_key = self.api_key
                self.client = openai
        elif self.api_provider == "anthropic":
            self.api_key = self.ai_config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
            if self.api_key:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)

    def analyze_video_content(self, transcription: Dict, video_info: Dict) -> Optional[Dict]:
        """
        動画の内容を分析して見どころを特定

        Args:
            transcription: 転写結果
            video_info: 動画の基本情報

        Returns:
            分析結果（見どころ、重要セグメント等）
        """
        try:
            logger.info("AI による動画内容分析を開始...")

            # 転写テキストを準備
            full_text = transcription.get("text", "")
            segments = transcription.get("segments", [])

            # AIに送る分析プロンプトを構築
            analysis_prompt = self._build_analysis_prompt(full_text, video_info)

            # AI分析を実行
            if self.api_provider == "openai":
                analysis_result = self._analyze_with_openai(analysis_prompt, segments)
            elif self.api_provider == "anthropic":
                analysis_result = self._analyze_with_anthropic(analysis_prompt, segments)
            else:
                logger.error(f"サポートされていないAIプロバイダー: {self.api_provider}")
                return None

            if analysis_result:
                logger.info("AI分析完了")
                return self._process_analysis_result(analysis_result, segments)

            return None

        except Exception as e:
            logger.error(f"AI分析エラー: {e}")
            return None

    def create_highlight_video(self, video_path: str, analysis_result: Dict) -> Optional[str]:
        """
        分析結果を基にハイライト動画を作成

        Args:
            video_path: 元動画のパス
            analysis_result: AI分析結果

        Returns:
            作成されたハイライト動画のパス
        """
        try:
            logger.info("ハイライト動画作成を開始...")

            video_path = Path(video_path)
            output_path = Path(os.getenv("OUTPUT_DIR", "output")) / f"{video_path.stem}_highlights.mp4"

            # ハイライトセグメントを取得
            highlight_segments = analysis_result.get("highlight_segments", [])
            if not highlight_segments:
                logger.warning("ハイライトセグメントが見つかりません")
                return None

            # 動画をロード
            with VideoFileClip(str(video_path)) as video:
                clips = []
                total_duration = 0

                for segment in highlight_segments:
                    start_time = segment.get("start", 0)
                    end_time = segment.get("end", start_time + 30)  # デフォルト30秒

                    # 時間の妥当性チェック
                    if end_time > video.duration:
                        end_time = video.duration
                    if start_time >= end_time:
                        continue

                    # セグメントを抽出
                    clip = video.subclip(start_time, end_time)
                    clips.append(clip)
                    total_duration += (end_time - start_time)

                    # 目標時間に達したら終了
                    if total_duration >= self.target_duration:
                        break

                if not clips:
                    logger.warning("有効なハイライトクリップが作成できませんでした")
                    return None

                # クリップを結合
                logger.info(f"{len(clips)} のクリップを結合中...")
                final_video = concatenate_videoclips(clips, method="compose")

                # 出力
                final_video.write_videofile(
                    str(output_path),
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True
                )

                final_video.close()
                for clip in clips:
                    clip.close()

            logger.info(f"ハイライト動画作成完了: {output_path}")
            logger.info(f"総再生時間: {total_duration:.1f}秒")
            return str(output_path)

        except Exception as e:
            logger.error(f"ハイライト動画作成エラー: {e}")
            return None

    def _build_analysis_prompt(self, text: str, video_info: Dict) -> str:
        """分析用プロンプトを構築"""
        prompt = f"""
以下の動画内容を分析して、最も興味深く価値のある部分を特定してください。

動画情報:
- タイトル: {video_info.get('title', '不明')}
- 再生時間: {video_info.get('duration', 0)}秒
- アップロード者: {video_info.get('uploader', '不明')}

転写テキスト:
{text[:3000]}...  # 最初の3000文字のみ

以下の観点で分析してください:
1. 最も重要で価値のある情報が含まれている部分
2. 視聴者の注意を引く可能性が高い部分
3. 教育的価値や娯楽価値の高い部分
4. 話題の転換点や重要なポイント
5. 感情的なインパクトのある部分

分析結果をJSON形式で以下のように出力してください:
{{
    "summary": "動画全体の要約",
    "key_topics": ["主要なトピック1", "主要なトピック2", ...],
    "highlight_segments": [
        {{
            "start_time": 開始時間(秒),
            "end_time": 終了時間(秒),
            "importance_score": 重要度(0-1),
            "reason": "選択理由",
            "topic": "セグメントのトピック"
        }}
    ],
    "overall_engagement": 全体的な魅力度(0-1)
}}

目標: 約{self.target_duration}秒（{self.target_duration//60}分）のハイライト動画を作成
"""
        return prompt

    def _analyze_with_openai(self, prompt: str, segments: List[Dict]) -> Optional[Dict]:
        """OpenAI APIで分析"""
        try:
            response = self.client.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは動画コンテンツ分析の専門家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:
            logger.error(f"OpenAI分析エラー: {e}")
            return None

    def _analyze_with_anthropic(self, prompt: str, segments: List[Dict]) -> Optional[Dict]:
        """Anthropic APIで分析"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text
            return json.loads(content)

        except Exception as e:
            logger.error(f"Anthropic分析エラー: {e}")
            return None

    def _process_analysis_result(self, raw_result: Dict, segments: List[Dict]) -> Dict:
        """分析結果を処理して実際のタイムスタンプとマッピング"""
        try:
            processed_result = raw_result.copy()

            # ハイライトセグメントの時間を実際のセグメントタイムスタンプに合わせる
            if "highlight_segments" in processed_result:
                for highlight in processed_result["highlight_segments"]:
                    start_time = highlight.get("start_time", 0)
                    end_time = highlight.get("end_time", start_time + 30)

                    # 最も近いセグメントを見つける
                    matching_segments = [
                        seg for seg in segments
                        if seg["start"] <= start_time <= seg["end"] or
                           seg["start"] <= end_time <= seg["end"] or
                           start_time <= seg["start"] <= end_time
                    ]

                    if matching_segments:
                        # セグメント境界に合わせて調整
                        highlight["start"] = min(seg["start"] for seg in matching_segments)
                        highlight["end"] = max(seg["end"] for seg in matching_segments)
                        highlight["matched_text"] = " ".join(seg["text"] for seg in matching_segments)

            return processed_result

        except Exception as e:
            logger.error(f"分析結果処理エラー: {e}")
            return raw_result

    def save_analysis_result(self, analysis_result: Dict, output_path: str):
        """分析結果をファイルに保存"""
        try:
            output_path = Path(output_path)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)

            logger.info(f"分析結果を保存: {output_path}")

        except Exception as e:
            logger.error(f"分析結果保存エラー: {e}")

    def is_enabled(self) -> bool:
        """AI編集機能が有効かチェック"""
        return (
            self.ai_config.get("enabled", False) and
            self.api_key is not None and
            hasattr(self, 'client')
        )
