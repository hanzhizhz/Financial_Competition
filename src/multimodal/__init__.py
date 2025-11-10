"""OpenAI 风格的智谱多模态客户端封装。"""

from __future__ import annotations

from ..config import Settings, get_settings
from .audio import encode_audio_to_base64, transcribe, transcribe_audio
from .client import OpenAIAPIError, create_client, invoke_with_client
from .text import chat_completion
from .vision import analyze_image, encode_image_to_base64, multimodal_completion

__all__ = [
    "Settings",
    "OpenAIAPIError",
    "chat_completion",
    "create_client",
    "analyze_image",
    "encode_audio_to_base64",
    "encode_image_to_base64",
    "get_settings",
    "multimodal_completion",
    "invoke_with_client",
    "transcribe_audio",
    "transcribe",
]
