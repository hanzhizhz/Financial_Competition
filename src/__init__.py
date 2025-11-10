"""
智能票据/发票管理系统
基于多模态理解的AI Agent

Quickstart::

    import asyncio
    from src.multimodal import chat_completion

    async def main():
        response = await chat_completion(
            [{"role": "user", "content": "概述小票内容"}]
        )
        print(response["choices"][0]["message"]["content"])

    asyncio.run(main())
"""

from .config import Settings, get_settings, load_env
from .multimodal import (
    OpenAIAPIError,
    analyze_image,
    chat_completion,
    create_client,
    encode_audio_to_base64,
    encode_image_to_base64,
    invoke_with_client,
    multimodal_completion as vision_completion,
    transcribe,
)

load_env()

__version__ = "0.1.0"
__author__ = "Your Team"

__all__ = [
    "Settings",
    "OpenAIAPIError",
    "chat_completion",
    "create_client",
    "analyze_image",
    "encode_audio_to_base64",
    "encode_image_to_base64",
    "get_settings",
    "invoke_with_client",
    "load_env",
    "transcribe",
    "vision_completion",
    "__version__",
    "__author__",
]
