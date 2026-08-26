from __future__ import annotations

import contextlib
import json
import logging
import os
import typing
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

import config


LOGGER = logging.getLogger(__name__)
_LANGTRACE_STATE = {"initialized": False, "enabled": False, "error": None}
_LANGTRACE_UI_STRING_FIELDS = {
    "user_id",
    "prompt_id",
    "prompt_version",
    "model",
}


def _normalize_langtrace_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_langtrace_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_langtrace_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_langtrace_payload(item) for item in value]
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _normalize_span_attribute(key: str, value: Any) -> bool | int | float | str:
    if key in _LANGTRACE_UI_STRING_FIELDS or key.endswith("_id"):
        return str(value)
    return value if isinstance(value, (bool, int, float, str)) else str(value)


def _langtrace_api_url(path: str) -> str:
    parsed = urlparse(config.LANGTRACE_API_HOST or "http://localhost:3000/api/trace")
    base_path = parsed.path
    if base_path.endswith("/api/trace"):
        base_path = base_path[: -len("/api/trace")]
    path = "/" + path.lstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, f"{base_path}{path}", "", "", ""))


def _langtrace_dashboard_id(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("0x"):
        return text
    if len(text) in {16, 32} and all(char in "0123456789abcdefABCDEF" for char in text):
        return f"0x{text.lower()}"
    return text


def span_identity(span: Any, request_id: str | None = None) -> dict[str, str]:
    if span is None:
        return {}
    try:
        from opentelemetry.trace.span import format_span_id, format_trace_id  # type: ignore

        if request_id:
            span.set_attribute("request_id", str(request_id))
            span.set_attribute("meditech.request_id", str(request_id))
        context = span.get_span_context()
        return {
            "trace_id": _langtrace_dashboard_id(format_trace_id(context.trace_id)),
            "span_id": _langtrace_dashboard_id(format_span_id(context.span_id)),
        }
    except Exception as exc:
        LOGGER.warning("Langtrace span identity unavailable", extra={"reason": str(exc)})
        return {}


def submit_feedback_evaluation(
    request_entry: dict[str, Any] | None,
    *,
    user_id: int | str,
    helpful: bool,
    details: str = "",
) -> bool:
    if not config.ENABLE_LANGTRACE or config.LANGTRACE_MODE == "disabled" or not config.LANGTRACE_API_KEY:
        return False
    request_entry = request_entry or {}
    request_id = request_entry.get("request_id")
    span_id = _langtrace_dashboard_id(request_entry.get("langtrace_span_id") or request_id)
    trace_id = _langtrace_dashboard_id(request_entry.get("langtrace_trace_id") or request_id)
    if not span_id or not trace_id:
        return False
    payload = {
        "traceId": str(trace_id),
        "spanId": str(span_id),
        "userScore": 1 if helpful else -1,
        "userId": str(user_id),
        "reason": details.strip() or ("helpful" if helpful else "not helpful"),
    }
    url = _langtrace_api_url("/api/evaluation")
    if _send_langtrace_evaluation(url, payload, method="POST"):
        return True
    return _send_langtrace_evaluation(url, payload, method="PUT")


def _send_langtrace_evaluation(url: str, payload: dict[str, Any], *, method: str) -> bool:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "x-api-key": config.LANGTRACE_API_KEY,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            if 200 <= response.status < 300:
                return True
            LOGGER.warning("Langtrace evaluation rejected", extra={"status": response.status, "method": method})
            return False
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:1000]
        if method == "POST" and exc.code == 400 and "already exists" in body_text:
            return False
        LOGGER.warning("Langtrace evaluation failed", extra={"status": exc.code, "method": method, "body": body_text})
        return False
    except (URLError, TimeoutError) as exc:
        LOGGER.warning("Langtrace evaluation unavailable", extra={"method": method, "reason": str(exc)})
        return False


def _build_safe_langtrace_exporter(api_key: str | None, remote_url: str | None, write_to_remote_url: bool):
    from langtrace_python_sdk.extensions.langtrace_exporter import LangTraceExporter  # type: ignore
    from opentelemetry.trace.span import format_trace_id  # type: ignore
    from opentelemetry.sdk.trace.export import SpanExportResult  # type: ignore
    import requests

    class SafeLangTraceExporter(LangTraceExporter):
        def export(self, spans: typing.Sequence[Any]):
            data = []
            for span in spans:
                payload = _normalize_langtrace_payload(json.loads(span.to_json()))
                payload["traceId"] = format_trace_id(span.get_span_context().trace_id)
                data.append(payload)
            if not self.write_to_remote_url:
                return SpanExportResult.SUCCESS
            try:
                response = requests.post(
                    url=self.url,
                    data=json.dumps(data),
                    headers={"Content-Type": "application/json", "x-api-key": self.api_key},
                    timeout=10,
                )
                if response.status_code >= 400:
                    LOGGER.warning(
                        "Langtrace export rejected: status=%s body=%s",
                        response.status_code,
                        response.text[:1000],
                    )
                    return SpanExportResult.FAILURE
                return SpanExportResult.SUCCESS
            except Exception as exc:
                LOGGER.warning("Langtrace export failed: %s", exc)
                return SpanExportResult.FAILURE

    return SafeLangTraceExporter(api_key=api_key, url=remote_url, write_to_remote_url=write_to_remote_url)


def reset_langtrace() -> None:
    _LANGTRACE_STATE["initialized"] = False
    _LANGTRACE_STATE["enabled"] = False
    _LANGTRACE_STATE["error"] = None


def init_langtrace() -> bool:
    if _LANGTRACE_STATE["initialized"]:
        return bool(_LANGTRACE_STATE["enabled"])
    _LANGTRACE_STATE["initialized"] = True
    if not config.ENABLE_LANGTRACE or config.LANGTRACE_MODE == "disabled":
        _LANGTRACE_STATE["enabled"] = False
        return False
    try:
        from langtrace_python_sdk import langtrace  # type: ignore

        if config.LANGTRACE_API_HOST:
            os.environ.setdefault("LANGTRACE_API_HOST", config.LANGTRACE_API_HOST)
        if config.LANGTRACE_API_KEY:
            os.environ.setdefault("LANGTRACE_API_KEY", config.LANGTRACE_API_KEY)
        # The Langtrace SDK auto-instruments OpenAI on init and raises if no key
        # exists, even when the app uses only local backends like Ollama/LM Studio.
        os.environ.setdefault("OPENAI_API_KEY", "local-placeholder")

        kwargs: dict[str, Any] = {
            "batch": bool(config.LANGTRACE_BATCH),
            "log_spans_to_console": bool(config.LANGTRACE_WRITE_SPANS_TO_CONSOLE),
            "write_to_remote_url": bool(config.LANGTRACE_MODE != "console"),
            "custom_exporter": _build_safe_langtrace_exporter(
                api_key=config.LANGTRACE_API_KEY or None,
                remote_url=config.LANGTRACE_API_HOST or None,
                write_to_remote_url=bool(config.LANGTRACE_MODE != "console"),
            ),
        }
        if config.LANGTRACE_API_HOST:
            kwargs["remote_url"] = config.LANGTRACE_API_HOST
        if config.LANGTRACE_API_KEY:
            kwargs["api_key"] = config.LANGTRACE_API_KEY
        langtrace.init(**kwargs)
        _LANGTRACE_STATE["enabled"] = True
        LOGGER.info("Langtrace initialized", extra={"mode": config.LANGTRACE_MODE, "api_host": config.LANGTRACE_API_HOST or "console"})
        return True
    except Exception as exc:
        _LANGTRACE_STATE["enabled"] = False
        _LANGTRACE_STATE["error"] = str(exc)
        LOGGER.warning("Langtrace unavailable", extra={"reason": str(exc)})
        return False


@contextlib.contextmanager
def trace_workflow(operation_name: str, metadata: dict[str, Any] | None = None):
    if not init_langtrace():
        yield None
        return
    try:
        from opentelemetry import trace  # type: ignore

        tracer = trace.get_tracer("meditech-rag.workflow")
        with tracer.start_as_current_span(operation_name) as span:
            for key, value in (metadata or {}).items():
                if value is None:
                    continue
                span.set_attribute(key, _normalize_span_attribute(key, value))
            yield span
    except Exception as exc:
        LOGGER.warning("Langtrace workflow span failed", extra={"reason": str(exc)})
        yield None


def trace_llm_call(
    operation_name: str,
    metadata: dict[str, Any],
    call: Callable[[], str],
    *,
    prompt: str | None = None,
) -> str:
    if not init_langtrace():
        return call()
    try:
        from opentelemetry import trace  # type: ignore

        tracer = trace.get_tracer("meditech-rag.llm")
        with tracer.start_as_current_span(operation_name) as span:
            for key, value in metadata.items():
                if value is None:
                    continue
                span.set_attribute(f"meditech.{key}", _normalize_span_attribute(key, value))
            if config.LANGTRACE_CAPTURE_CONTENT and prompt is not None:
                span.set_attribute("meditech.prompt", prompt[:4000])
            response = call()
            span.set_attribute("meditech.response_length", len(response or ""))
            if config.LANGTRACE_CAPTURE_CONTENT:
                span.set_attribute("meditech.response", (response or "")[:4000])
            return response
    except Exception as exc:
        LOGGER.warning("Langtrace span failed", extra={"reason": str(exc)})
        return call()
