"""基于 OpenAI 客户端的语音转写封装。"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ..config import get_settings
from .client import create_client, invoke_with_client

def encode_audio_to_base64(audio: Union[str, Path, bytes]) -> str:
    """
    Encode audio content to base64 for API submission.

    Parameters
    ----------
    audio:
        Path to the audio file or raw audio bytes.
    """
    if isinstance(audio, (str, Path)):
        data = Path(audio).expanduser().read_bytes()
    else:
        data = audio
    return base64.b64encode(data).decode("utf-8")


async def transcribe(
    audio: Union[str, Path, bytes],
    *,
    client: Optional[Any] = None,
    model: Optional[str] = None,
    mime_type: str = "audio/wav",
    filename: Optional[str] = None,
    **params: Any,
) -> Dict[str, Any]:
    """
    Submit audio content to GLM-ASR for transcription.

    Parameters
    ----------
    audio:
        File path or bytes of the audio content.
    client:
        可选的 OpenAI 客户端实例，可在多次调用中复用。
    model:
        Override the default ASR model.
    mime_type:
        MIME type describing the audio payload (e.g., ``audio/wav``).
    params:
        Extra parameters forwarded to the API, such as ``language``.
    """
    settings = get_settings()
    request_timeout = params.pop("timeout", None)
    resolved_model = model or settings.asr_model

    audio_bytes: bytes
    resolved_filename: str
    if isinstance(audio, (str, Path)):
        audio_path = Path(audio).expanduser()
        audio_bytes = audio_path.read_bytes()
        resolved_filename = filename or audio_path.name
    else:
        audio_bytes = audio
        resolved_filename = filename or "audio.wav"

    file_buffer = BytesIO(audio_bytes)
    file_buffer.name = resolved_filename  # type: ignore[attr-defined]

    request_kwargs: Dict[str, Any] = {
        "model": resolved_model,
        "file": file_buffer,
        **params,
    }
    if request_timeout is not None:
        request_kwargs["timeout"] = request_timeout

    active_client = client or create_client(settings=settings)
    response = await invoke_with_client(
        active_client.audio.transcriptions.create,
        **request_kwargs,
    )
    return response.model_dump()


transcribe_audio = transcribe


__all__ = ["transcribe", "transcribe_audio", "encode_audio_to_base64"]


