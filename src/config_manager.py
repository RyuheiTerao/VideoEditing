"""
設定管理モジュール
"""

import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """設定ファイルの管理クラス"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._merge_env_variables()

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                logger.info(f"設定ファイルを読み込み: {self.config_path}")
                return config
            else:
                logger.warning(f"設定ファイルが見つかりません: {self.config_path}")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"設定ファイル読み込みエラー: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を返す"""
        return {
            # Whisper設定
            "whisper_model": "base",

            # 翻訳設定
            "translation_retries": 3,
            "translation_retry_delay": 1,
            "translation_batch_size": 5,

            # 字幕設定
            "subtitle_font": "Arial",
            "subtitle_font_size": 20,
            "subtitle_font_color": "white",
            "subtitle_outline_color": "black",
            "subtitle_outline_width": 1,
            "subtitle_method": "burn",  # burn or soft

            # ダウンロード設定
            "download_quality": "best",
            "proxy": None,

            # AI編集設定（将来用）
            "ai_editing": {
                "enabled": False,
                "api_provider": "openai",  # openai, anthropic
                "model": "gpt-4",
                "target_duration": 600,  # 10分
                "highlight_threshold": 0.7,
            },

            # ファイル設定
            "cleanup_temp_files": True,
            "keep_original_files": True,
        }

    def _merge_env_variables(self):
        """環境変数を設定にマージ"""
        env_mappings = {
            "WHISPER_MODEL": "whisper_model",
            "TRANSLATION_RETRIES": "translation_retries",
            "SUBTITLE_FONT_SIZE": "subtitle_font_size",
            "DOWNLOAD_QUALITY": "download_quality",
            "PROXY": "proxy",
            "OPENAI_API_KEY": "ai_editing.openai_api_key",
            "ANTHROPIC_API_KEY": "ai_editing.anthropic_api_key",
        }

        for env_var, config_key in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                self._set_nested_config(config_key, env_value)

    def _set_nested_config(self, key_path: str, value: Any):
        """ネストした設定キーに値を設定"""
        keys = key_path.split('.')
        config = self.config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        """設定値を取得"""
        keys = key.split('.')
        config = self.config

        try:
            for k in keys:
                config = config[k]
            return config
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """設定値を更新"""
        self._set_nested_config(key, value)

    def save(self):
        """設定をファイルに保存"""
        try:
            # 設定ディレクトリを作成
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"設定を保存: {self.config_path}")

        except Exception as e:
            logger.error(f"設定保存エラー: {e}")

    def validate_config(self) -> bool:
        """設定の妥当性をチェック"""
        errors = []

        # Whisperモデルのチェック
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if self.get("whisper_model") not in valid_models:
            errors.append(f"不正なWhisperモデル: {self.get('whisper_model')}")

        # 字幕フォントサイズのチェック
        font_size = self.get("subtitle_font_size")
        if not isinstance(font_size, int) or font_size < 8 or font_size > 72:
            errors.append(f"字幕フォントサイズが範囲外: {font_size}")

        # 翻訳リトライ回数のチェック
        retries = self.get("translation_retries")
        if not isinstance(retries, int) or retries < 1 or retries > 10:
            errors.append(f"翻訳リトライ回数が範囲外: {retries}")

        if errors:
            for error in errors:
                logger.error(f"設定エラー: {error}")
            return False

        logger.info("設定の妥当性チェック完了")
        return True

    def get_all(self) -> Dict[str, Any]:
        """全設定を取得"""
        return self.config.copy()

    def reset_to_defaults(self):
        """設定をデフォルトに戻す"""
        self.config = self._get_default_config()
        self._merge_env_variables()
        logger.info("設定をデフォルトにリセット")

    def update_from_dict(self, updates: Dict[str, Any]):
        """辞書から設定を更新"""
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value

        deep_update(self.config, updates)
        logger.info("設定を辞書から更新")

    def export_config(self, output_path: str):
        """設定を別のファイルにエクスポート"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"設定をエクスポート: {output_path}")

        except Exception as e:
            logger.error(f"設定エクスポートエラー: {e}")

    def import_config(self, input_path: str):
        """別のファイルから設定をインポート"""
        try:
            input_path = Path(input_path)
            if not input_path.exists():
                logger.error(f"設定ファイルが存在しません: {input_path}")
                return

            with open(input_path, 'r', encoding='utf-8') as f:
                imported_config = yaml.safe_load(f)

            if imported_config:
                self.config = imported_config
                self._merge_env_variables()
                logger.info(f"設定をインポート: {input_path}")

        except Exception as e:
            logger.error(f"設定インポートエラー: {e}")
