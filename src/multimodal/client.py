"""OpenAI 客户端封装，适配智谱开放平台的多模态接口。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

try:  # pragma: no cover - 导入失败时提供友好提示
    from openai import OpenAI, OpenAIError
except ImportError as exc:  # pragma: no cover - 运行时缺少依赖
    OpenAI = None  # type: ignore[assignment]

    class OpenAIError(Exception):
        """缺少 openai 包时的占位异常。"""

    _OPENAI_IMPORT_ERROR: Optional[ImportError] = exc
else:
    _OPENAI_IMPORT_ERROR = None

from ..config import Settings, get_settings

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

T = TypeVar("T")


@dataclass
class OpenAIAPIError(Exception):
    """统一封装 OpenAI 客户端抛出的异常。"""

    status: Optional[int]
    message: str
    details: Optional[Any] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        code = self.status if self.status is not None else "-"
        return f"[{code}] {self.message}"


def _normalise_base_url(base_url: str) -> str:
    """确保 base_url 以 `/` 结尾，避免路径连接异常。"""
    return base_url if base_url.endswith("/") else f"{base_url}/"


def _wrap_openai_error(exc: OpenAIError) -> OpenAIAPIError:
    """将 OpenAI 异常转换为自定义异常，便于统一处理。"""
    status = getattr(exc, "status_code", None)
    message = getattr(exc, "message", None) or str(exc)
    details = getattr(exc, "response", None) or getattr(exc, "body", None)
    return OpenAIAPIError(status=status, message=message, details=details)


def create_client(
    settings: Optional[Settings] = None,
    *,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> OpenAI:
    """根据配置初始化同步 OpenAI 客户端。"""
    settings = settings or get_settings()
    if not settings.has_credentials:
        raise ValueError(
            "ZHIPU_API_KEY 未提供，请在环境变量或 .env 文件中进行配置。"
        )
    if OpenAI is None:
        raise RuntimeError(
            "未安装 openai 库，请先执行 `pip install openai`。"
        ) from _OPENAI_IMPORT_ERROR

    resolved_base_url = _normalise_base_url(base_url or settings.base_url)
    resolved_timeout = timeout if timeout is not None else settings.http_timeout

    # 构建客户端参数
    # 注意：某些版本的 OpenAI SDK 可能不支持某些参数
    # 如果出现 proxies 相关错误，可能是 httpx 版本不兼容导致的
    client_kwargs: dict[str, Any] = {
        "api_key": settings.api_key,
        "base_url": resolved_base_url,
    }
    
    # 尝试添加 timeout 参数
    if resolved_timeout is not None:
        client_kwargs["timeout"] = resolved_timeout
    
    try:
        return OpenAI(**client_kwargs)
    except TypeError as e:
        error_msg = str(e)
        # 如果出现 proxies 相关的错误，可能是 OpenAI SDK 内部使用了不兼容的参数
        # 尝试使用最基础的参数重试
        if "proxies" in error_msg or "unexpected keyword argument" in error_msg:
            # 尝试通过创建自定义 http_client 来绕过 proxies 问题
            try:
                import httpx
                # 创建一个不包含 proxies 的 httpx 客户端
                http_client = httpx.Client(timeout=resolved_timeout)
                return OpenAI(
                    api_key=settings.api_key,
                    base_url=resolved_base_url,
                    http_client=http_client
                )
            except (ImportError, TypeError):
                # 如果 httpx 不可用或还是失败，使用最基础的参数
                minimal_kwargs = {
                    "api_key": settings.api_key,
                    "base_url": resolved_base_url,
                }
                try:
                    return OpenAI(**minimal_kwargs)
                except TypeError:
                    # 如果还是失败，可能是 OpenAI SDK 版本问题
                    # 建议用户升级或降级 openai 和 httpx 库
                    raise RuntimeError(
                        f"创建 OpenAI 客户端失败: {error_msg}\n"
                        "这可能是因为 openai 或 httpx 库版本不兼容。\n"
                        "建议执行以下命令修复:\n"
                        "  pip install --upgrade openai httpx\n"
                        "或者:\n"
                        "  pip install httpx==0.27.2"
                    ) from e
        raise


async def invoke_with_client(
    func: Callable[..., T],
    /,
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    在线程池中执行同步 OpenAI 请求，并统一异常处理。

    Parameters
    ----------
    func:
        OpenAI 客户端的方法，如 ``client.chat.completions.create``。
    args, kwargs:
        透传给目标方法的参数。
    """

    def _runner() -> T:
        try:
            return func(*args, **kwargs)
        except OpenAIError as exc:  # pragma: no cover - 由业务测试覆盖
            raise _wrap_openai_error(exc) from exc

    loop = asyncio.get_running_loop()
    return await asyncio.to_thread(_runner) if loop.is_running() else _runner()


__all__ = ["OpenAI", "OpenAIAPIError", "create_client", "invoke_with_client"]


