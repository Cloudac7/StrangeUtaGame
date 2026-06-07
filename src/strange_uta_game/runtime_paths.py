"""跨平台运行时可写目录。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "StrangeUtaGame"


def program_dir() -> Path:
    """返回主程序可执行文件所在目录。"""
    return Path(sys.argv[0]).resolve().parent


def default_config_dir() -> Path:
    """返回平台默认配置目录。"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    return program_dir()


def config_redirect_path() -> Path:
    """返回配置目录重定向标记的位置。"""
    if sys.platform == "darwin":
        return default_config_dir() / ".config_redirect"
    return program_dir() / ".config_redirect"


def config_dir() -> Path:
    """返回实际配置目录，并应用用户设置的目录重定向。"""
    redirect_file = config_redirect_path()
    if redirect_file.exists():
        try:
            custom_dir = Path(redirect_file.read_text(encoding="utf-8").strip())
            if custom_dir.is_dir():
                return custom_dir
        except Exception:
            pass
    return default_config_dir()


def cache_dir() -> Path:
    """返回平台运行时缓存目录。"""
    env_dir = os.environ.get("SUG_CACHE_DIR")
    if env_dir:
        path = Path(env_dir)
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Caches" / APP_DIR_NAME
    else:
        path = program_dir() / ".cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
