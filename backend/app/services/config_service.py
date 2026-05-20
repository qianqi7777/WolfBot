"""
AI 配置持久化服务

将 AI 配置（base_url, api_key, model 等）保存到 JSON 文件，
服务器重启后自动加载，避免每次都重新填入。

文件位置：backend/config/ai_config.json
"""

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from app.services.game_service import AiRuntimeConfig

logger = logging.getLogger(__name__)

# 配置文件路径
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_CONFIG_FILE = _CONFIG_DIR / "ai_config.json"


def _ensure_config_dir() -> None:
    """确保配置目录存在"""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_saved_config() -> Optional[dict]:
    """从 JSON 文件加载已保存的 AI 配置。返回 None 表示无保存配置。"""
    if not _CONFIG_FILE.exists():
        return None
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("[Config] 已加载持久化 AI 配置: base_url=%s, model=%s",
                    data.get("base_url", ""), data.get("model", ""))
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("[Config] 读取 AI 配置文件失败: %s", exc)
        return None


def save_config(config: AiRuntimeConfig) -> None:
    """将 AI 配置保存到 JSON 文件"""
    _ensure_config_dir()
    try:
        data = {
            "base_url": config.base_url,
            "api_key": config.api_key,
            "model": config.model,
            "timeout_seconds": config.timeout_seconds,
            "temperature": config.temperature,
            "enable_mock": config.enable_mock,
        }
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("[Config] AI 配置已持久化: base_url=%s, model=%s, enable_mock=%s",
                    config.base_url, config.model, config.enable_mock)
    except OSError as exc:
        logger.error("[Config] 保存 AI 配置文件失败: %s", exc)


def apply_saved_config_to_defaults() -> dict:
    """加载持久化配置并返回，用于在创建新游戏时作为默认值。
    如果没有保存的配置，返回空 dict。
    """
    saved = load_saved_config()
    if saved is None:
        return {}
    return saved
