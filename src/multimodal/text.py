"""基于 OpenAI 客户端的文本对话封装。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Union

from ..config import get_settings
from .client import create_client, invoke_with_client

async def chat_completion(
    messages: Iterable[Dict[str, Any]],
    *,
    client: Optional[Any] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    response_format: Optional[Union[str, Dict[str, Any]]] = None,
    **params: Any,
) -> Dict[str, Any]:
    """
    Request a chat completion using the GLM text model.

    Parameters
    ----------
    messages:
        Iterable of OpenAI-style message dicts, each containing ``role`` and ``content``.
    client:
        可选的 OpenAI 客户端实例，用于复用连接。
    model:
        Override the default text model configured via environment variables.
    temperature:
        Sampling temperature for generation.
    response_format:
        控制模型的返回格式。
        - ``"text"`` 或 ``{"type": "text"}``：纯文本模式（默认）。
        - ``"json_object"`` 或 ``{"type": "json_object"}``：返回有效 JSON。
    params:
        Additional JSON-serialisable parameters forwarded to the API.
    """

    settings = get_settings()
    payload: Dict[str, Any] = {
        "model": model or settings.text_model,
        "messages": list(messages),
        "temperature": temperature,
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


__all__ = ["chat_completion"]


