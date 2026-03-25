"""统一日志：在 ``main`` 中于创建应用前调用 ``configure_logging()``。"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import os
import sys
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any, Final, TypeVar, cast, overload

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_DEFAULT_DATEFMT: Final[str] = "%Y-%m-%d %H:%M:%S"
_DEFAULT_LOG_FILE: Final[str] = "log/app.log"


def configure_logging(
    *,
    level: str | None = None,
    log_file: str | None = None,
    format_string: str = _DEFAULT_FORMAT,
    datefmt: str = _DEFAULT_DATEFMT,
) -> None:
    """配置根 logger 与常见子 logger。

    ``level`` 缺省时依次尝试环境变量 ``LOG_LEVEL``，再缺省为 ``INFO``。
    """
    raw = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, raw, logging.INFO)
    target_file = (log_file or os.environ.get("LOG_FILE") or _DEFAULT_LOG_FILE).strip()
    if not target_file:
        target_file = _DEFAULT_LOG_FILE
    log_path = Path(target_file)
    if log_path.parent != Path("."):
        log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    stream_handler = logging.StreamHandler(sys.stderr)

    logging.basicConfig(
        level=log_level,
        format=format_string,
        datefmt=datefmt,
        handlers=[stream_handler, file_handler],
        force=True,
    )

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(log_level)


def _safe_repr(value: object, max_len: int) -> str:
    try:
        s = repr(value)
    except Exception as exc:  # noqa: BLE001
        return f"<repr 失败: {exc}>"
    if len(s) > max_len:
        return f"{s[: max_len - 3]}..."
    return s


def _format_bound_arguments(
    sig: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    max_value_len: int,
) -> str:
    try:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
    except TypeError:
        return f"*args={_safe_repr(args, max_value_len)} **kwargs={_safe_repr(kwargs, max_value_len)}"
    parts: list[str] = []
    for name, val in bound.arguments.items():
        parts.append(f"{name}={_safe_repr(val, max_value_len)}")
    return ", ".join(parts)


@overload
def log_io(func: F) -> F: ...


@overload
def log_io(
    func: None = None,
    *,
    logger: logging.Logger | None = None,
    level: int = logging.DEBUG,
    max_value_len: int = 400,
) -> Callable[[F], F]: ...


def log_io(
    func: F | None = None,
    *,
    logger: logging.Logger | None = None,
    level: int = logging.DEBUG,
    max_value_len: int = 400,
) -> F | Callable[[F], F]:
    """装饰函数或方法，在进入/退出时记录入参与返回值（异步函数会 ``await`` 后再记录）。

    用法：``@log_io`` 或 ``@log_io(level=logging.INFO, logger=...)``。
    异常会以 ``ERROR`` 记录并原样抛出。
    """

    def decorator(f: F) -> F:
        lg = logger or logging.getLogger(f.__module__)
        sig = inspect.signature(f)

        def _log_in(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            params = _format_bound_arguments(sig, args, kwargs, max_value_len=max_value_len)
            lg.log(level, "%s 入参: %s", f.__qualname__, params)

        def _log_out(result: object) -> None:
            lg.log(level, "%s 出参: %s", f.__qualname__, _safe_repr(result, max_value_len))

        if asyncio.iscoroutinefunction(f):

            @functools.wraps(f)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _log_in(args, kwargs)
                try:
                    out = await cast(Callable[..., Awaitable[Any]], f)(*args, **kwargs)
                except Exception:
                    lg.exception("%s 抛出异常", f.__qualname__)
                    raise
                _log_out(out)
                return out

            return cast(F, async_wrapper)

        @functools.wraps(f)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            _log_in(args, kwargs)
            try:
                out = f(*args, **kwargs)
            except Exception:
                lg.exception("%s 抛出异常", f.__qualname__)
                raise
            _log_out(out)
            return out

        return cast(F, sync_wrapper)

    if func is not None:
        return decorator(func)
    return decorator
