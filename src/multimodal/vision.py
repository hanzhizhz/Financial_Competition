"""基于 OpenAI 客户端的视觉多模态封装。"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union

from ..config import get_settings
from .client import create_client, invoke_with_client


def encode_image_to_base64(image: Union[str, Path, bytes]) -> str:
    """
    Encode image content to a base64 string suitable for the Zhipu API.

    Parameters
    ----------
    image:
        Path to the image file or raw image bytes.
    """
    if isinstance(image, (str, Path)):
        data = Path(image).expanduser().read_bytes()
    else:
        data = image
    return base64.b64encode(data).decode("utf-8")


async def multimodal_completion(
    messages: Iterable[Dict[str, Any]],
    *,
    client: Optional[Any] = None,
    model: Optional[str] = None,
    response_format: Optional[Union[str, Dict[str, Any]]] = None,
    **params: Any,
) -> Dict[str, Any]:
    """
    Obtain a response from the GLM vision model.

    Messages follow the same structure as chat completions, but may include
    image content dictionaries such as::

        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe the receipt."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,<...>"}}
            ]
        }
    
    Parameters
    ----------
    response_format:
        控制模型的返回格式。
        - ``"text"`` 或 ``{"type": "text"}``：纯文本模式（默认）。
        - ``"json_object"`` 或 ``{"type": "json_object"}``：返回有效 JSON。
    """
    settings = get_settings()
    payload: Dict[str, Any] = {
        "model": model or settings.vision_model,
        "messages": list(messages),
        **params,
    }

    if response_format is not None:
        if isinstance(response_format, str):
            payload["response_format"] = {"type": response_format}
        elif isinstance(response_format, dict):
            payload["response_format"] = response_format
        else:
            raise TypeError("response_format 必须为字符串或字典。")

    active_client = client or create_client(settings=settings)
    response = await invoke_with_client(
        active_client.chat.completions.create,
        **payload,
    )
    return response.model_dump()


def _infer_mime_type(path: Path, default: str = "image/png") -> str:
    """根据文件扩展名推断 MIME 类型。"""
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type or default


async def analyze_image(
    image_path: Union[str, Path],
    prompt: str,
    *,
    client: Optional[Any] = None,
    model: Optional[str] = None,
    image_mime_type: Optional[str] = None,
    **params: Any,
) -> Dict[str, Any]:
    """
    使用视觉多模态模型对图像进行分析。

    Parameters
    ----------
    image_path:
        图像文件路径。
    prompt:
        引导模型分析的提示词。
    client:
        可选的客户端，用于复用 HTTP 连接。
    model:
        指定使用的模型，默认使用配置中的视觉模型。
    image_mime_type:
        显式指定图像的 MIME 类型；若未提供则根据路径推断。
    params:
        透传给接口的其他参数。
    """
    resolved_path = Path(image_path).expanduser()
    if not resolved_path.exists():
        raise FileNotFoundError(f"未找到图像文件: {resolved_path}")

    base64_content = encode_image_to_base64(resolved_path)
    mime_type = image_mime_type or _infer_mime_type(resolved_path)
    image_url = f"data:{mime_type};base64,{base64_content}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]

    return await multimodal_completion(
        messages,
        client=client,
        model=model,
        **params,
    )


__all__ = ["analyze_image", "multimodal_completion", "encode_image_to_base64"]


