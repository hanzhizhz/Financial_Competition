"""Configuration utilities for environment-based settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv as _dotenv_loader
except ImportError:  # pragma: no cover - optional dependency
    _dotenv_loader = None


def _load_env_file(path: Path) -> None:
    """Fallback loader for .env files when python-dotenv is unavailable."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_env(dotenv_path: Optional[str] = None) -> None:
    """Load environment variables from a .env file without overriding existing values."""
    path = Path(dotenv_path or ".env")
    if _dotenv_loader:
        _dotenv_loader(dotenv_path=str(path), override=False)
    else:
        _load_env_file(path)


# 默认HTTP超时时间（秒）
DEFAULT_HTTP_TIMEOUT = 120.0


@dataclass(frozen=True)
class Settings:
    """Structured configuration values for Zhipu APIs."""

    api_key: str
    base_url: str
    text_model: str
    vision_model: str
    asr_model: str
    http_timeout: float = DEFAULT_HTTP_TIMEOUT
    # Deepseek 配置
    deepseek_api_key: str = ""
    deepseek_text_model: str = ""
    deepseek_base_url: str = ""

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key)
    
    @property
    def has_deepseek_credentials(self) -> bool:
        """检查是否配置了 deepseek 凭据"""
        return bool(self.deepseek_api_key)


@lru_cache(maxsize=1)
def get_settings(dotenv_path: Optional[str] = None) -> Settings:
    """Return cached settings, ensuring environment variables are loaded once."""
    load_env(dotenv_path)
    timeout_value = os.getenv("GLM_HTTP_TIMEOUT", "")
    http_timeout = DEFAULT_HTTP_TIMEOUT
    if timeout_value:
        try:
            parsed = float(timeout_value)
            if parsed > 0:
                http_timeout = parsed
        except ValueError:
            pass
    return Settings(
        api_key=os.getenv("ZHIPU_API_KEY", ""),
        base_url=os.getenv(
            "GLM_API_BASE_URL",
            "https://open.bigmodel.cn/api/paas/v4/",
        ),
        text_model=os.getenv("GLM_TEXT_MODEL", "GLM-4.5-Air"),
        vision_model=os.getenv("GLM_VISION_MODEL", "GLM-4V-Flash"),
        asr_model=os.getenv("GLM_ASR_MODEL", "GLM-ASR"),
        http_timeout=http_timeout,
        # Deepseek 配置（注意环境变量名：DEEKSEEP）
        deepseek_api_key=os.getenv("DEEKSEEP_API_KEY", ""),
        deepseek_text_model=os.getenv("DEEKSEEP_TEXT_MODEL", ""),
        deepseek_base_url=os.getenv("DEEKSEEP_BASE_URL", ""),
    )


