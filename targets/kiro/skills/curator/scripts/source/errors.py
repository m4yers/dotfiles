"""Uniform handler error envelope.

All fetch handlers (pdf, youtube, html, local) used to raise bespoke
exceptions that bubbled up through ``fetch.fetch`` and turned into
unstructured tracebacks in the source tool's output. The orchestrator
(main
Kiro session) had nothing to branch on beyond the message string.

This module defines:

- ``HandlerErrorCode`` — the finite set of categories the orchestrator
  can reason about (timeout vs. 4xx vs. missing subtitles, …).
- ``HandlerError`` — an exception that carries a code + details and is
  converted to the envelope by ``safe_handler``.
- ``safe_handler`` — a decorator wrapping each handler's top-level
  ``handle()`` function. It catches both the typed ``HandlerError`` and
  the common raw exceptions (``httpx`` network errors, subprocess
  timeouts, ``FileNotFoundError``, ``ValueError``) and emits the
  uniform envelope.

Success envelope  : ``{ok: True,  ...handler-fields}``
Failure envelope  : ``{ok: False, error: {code, handler, message,
                                           details?}}``

``details`` is optional and carries machine-readable extras — HTTP
status codes, subprocess exit codes, etc. — without mixing them into
``message`` (which stays human-readable).
"""
from __future__ import annotations

import functools
import subprocess
from typing import Any, Callable

import httpx


class HandlerErrorCode:
    """Finite set of error categories returned by handlers.

    Kept as a class of constants rather than an ``enum.Enum`` so the
    strings appear unchanged in JSON output and so adding a new code
    never breaks existing consumers that pattern-match on literals.
    """

    # Remote fetch: we got no answer or an error answer.
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_HTTP_ERROR = "NETWORK_HTTP_ERROR"
    NETWORK_CONNECT_ERROR = "NETWORK_CONNECT_ERROR"

    # Remote fetch: we got content, but it is unusable for our purpose
    # (no captions on a video, trafilatura extracted nothing, …).
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"

    # Malformed URL, JSON, or other input the handler cannot parse.
    PARSE_ERROR = "PARSE_ERROR"

    # A local file input has a suffix we do not handle.
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"

    # A local file input does not exist.
    FILE_NOT_FOUND = "FILE_NOT_FOUND"

    # Path escapes the vault, or target folder is not writable.
    VAULT_ERROR = "VAULT_ERROR"

    # A subprocess (yt-dlp, pdftotext, …) exited non-zero. Distinct
    # from NETWORK_* because the error originates locally.
    EXTERNAL_TOOL_ERROR = "EXTERNAL_TOOL_ERROR"

    # Catch-all for anything the decorator could not classify. Keep
    # small — every time this fires the right fix is usually to add a
    # more specific mapping above.
    INTERNAL_ERROR = "INTERNAL_ERROR"


class HandlerError(Exception):
    """Raised inside a handler when a failure cleanly maps to a code.

    Use this when the handler already knows which category applies; it
    is preferred over raising ``ValueError``/``FileNotFoundError`` and
    letting the decorator guess.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _error_envelope(handler: str, code: str, message: str,
                    details: dict[str, Any] | None = None) -> dict:
    env: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "handler": handler,
            "message": message,
        },
    }
    if details:
        env["error"]["details"] = details
    return env


def safe_handler(handler_name: str) -> Callable[[Callable[..., dict]], Callable[..., dict]]:
    """Wrap a handler's ``handle()`` function with uniform error mapping.

    The wrapped function always returns a dict:

    - Success: the handler's own dict plus ``ok: True`` (added if the
      handler did not set it).
    - Failure: the standard error envelope.

    The decorator catches:

    - ``HandlerError`` — passed through with its own code and details.
    - ``httpx.TimeoutException`` → ``NETWORK_TIMEOUT``
    - ``httpx.HTTPStatusError`` → ``NETWORK_HTTP_ERROR`` (includes the
      status code in ``details``).
    - ``httpx.ConnectError`` / ``httpx.RequestError`` (non-timeout) →
      ``NETWORK_CONNECT_ERROR``
    - ``subprocess.TimeoutExpired`` → ``EXTERNAL_TOOL_ERROR`` with
      ``details.kind = "timeout"``
    - ``subprocess.CalledProcessError`` → ``EXTERNAL_TOOL_ERROR`` with
      ``details.returncode``
    - ``FileNotFoundError`` → ``FILE_NOT_FOUND``
    - ``ValueError`` → ``PARSE_ERROR`` (handlers should prefer raising
      ``HandlerError`` with a more specific code; ``ValueError`` is the
      fallback).
    - Anything else → ``INTERNAL_ERROR``.
    """

    def _decorator(fn: Callable[..., dict]) -> Callable[..., dict]:
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs) -> dict:
            try:
                result = fn(*args, **kwargs)
            except HandlerError as e:
                return _error_envelope(
                    handler_name, e.code, e.message, e.details
                )
            except httpx.TimeoutException as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.NETWORK_TIMEOUT,
                    f"remote fetch timed out: {e}",
                )
            except httpx.HTTPStatusError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.NETWORK_HTTP_ERROR,
                    f"remote returned HTTP {e.response.status_code}",
                    {"status_code": e.response.status_code,
                     "url": str(e.request.url)},
                )
            except (httpx.ConnectError, httpx.RequestError) as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.NETWORK_CONNECT_ERROR,
                    f"connection error: {e}",
                )
            except subprocess.TimeoutExpired as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.EXTERNAL_TOOL_ERROR,
                    f"{e.cmd[0] if e.cmd else 'subprocess'} timed out after {e.timeout}s",
                    {"kind": "timeout",
                     "timeout_s": e.timeout,
                     "cmd": list(e.cmd) if e.cmd else None},
                )
            except subprocess.CalledProcessError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.EXTERNAL_TOOL_ERROR,
                    f"{e.cmd[0] if e.cmd else 'subprocess'} exited {e.returncode}",
                    {"kind": "nonzero",
                     "returncode": e.returncode,
                     "cmd": list(e.cmd) if e.cmd else None,
                     "stderr": (e.stderr or "")[:500] if isinstance(e.stderr, str) else None},
                )
            except FileNotFoundError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.FILE_NOT_FOUND,
                    f"file not found: {e}",
                )
            except PermissionError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.VAULT_ERROR,
                    f"permission denied: {e}",
                )
            except ValueError as e:
                # Handlers should prefer HandlerError(PARSE_ERROR, ...)
                # with details; plain ValueError is the fallback.
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.PARSE_ERROR,
                    str(e),
                )
            except Exception as e:  # noqa: BLE001 — last-resort safety net
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.INTERNAL_ERROR,
                    f"unhandled {type(e).__name__}: {e}",
                )

            # Success — ensure ok: True is present.
            if not isinstance(result, dict):
                raise TypeError(
                    f"handler {handler_name!r} returned non-dict: {type(result)}"
                )
            result.setdefault("ok", True)
            return result

        return _wrapped

    return _decorator
