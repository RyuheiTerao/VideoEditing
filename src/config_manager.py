"""
設定管理モジュール
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """設定ファイルを管理するクラス"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.config_data = {}
        self.load()

    def load(self):
        """設定ファイルを読み込み"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
                logger.info(f"設定ファイルを読み込みました: {self.config_path}")
            else:
                logger.warning(f"設定ファイルが見つかりません: {self.config_path}")
                self._create_default_config()
        except Exception as e:
            logger.error(f"設定ファイルの読み込みに失敗: {e}")
            self._create_default_config()

    def _create_default_config(self):
        """デフォルト設定を作成"""
        self.config_data = {
            "whisper_model": "base",
            "translation_method": "googletrans_safe",
            "translation_retries": 3,
            "translation_retry_delay": 2.0,
            "batch_size": 3,
            "max_text_length": 4000,
            "subtitle_font": "Arial",
            "subtitle_font_size": 20,
            "download_quality": "best",
            "cleanup_temp_files": True,
            "log_level": "INFO"
        }

        # デフォルト設定を保存
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()
            logger.info(f"デフォルト設定ファイルを作成しました: {self.config_path}")
        except Exception as e:
            logger.error(f"デフォルト設定ファイルの作成に失敗: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """設定値を取得"""
        return self.config_data.get(key, default)

    def set(self, key: str, value: Any):
        """設定値を設定"""
        self.config_data[key] = value

    def save(self):
        """設定ファイルを保存"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, ensure_ascii=False)
            logger.info("設定ファイルを保存しました")
        except Exception as e:
            logger.error(f"設定ファイルの保存に失敗: {e}")
