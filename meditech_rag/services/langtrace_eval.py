from __future__ import annotations

import json
import logging
from typing import Any

import config
from services.eval_metrics import enabled_metrics, metric_attribute_payload
from services.langtrace_service import init_langtrace, span_identity, submit_feedback_evaluation, trace_workflow as base_trace_workflow
from services.persistence import load_request_history


LOGGER = logging.getLogger(__name__)


def _safe_value(value: Any) -> bool | int | float | str:
    if value is None:
        return ""
    if isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def is_langtrace_enabled() -> bool:
    return bool(config.ENABLE_LANGTRACE and config.LANGTRACE_MODE != "disabled")


def get_langtrace_status() -> dict:
    sdk_import_ok = False
    sdk_error = ""
    try:
        from langtrace_python_sdk import langtrace as _langtrace  # type: ignore  # noqa: F401

        sdk_import_ok = True
    except Exception as exc:
        sdk_error = str(exc)
    recent = list(reversed(load_request_history()))[:10]
    recent_with_ids = [
        {
            "request_id": item.get("request_id"),
            "trace_id": item.get("trace_id") or item.get("langtrace_trace_id"),
            "span_id": item.get("span_id") or item.get("langtrace_span_id"),
            "workflow": item.get("workflow") or item.get("request_type"),
        }
        for item in recent
        if item.get("trace_id") or item.get("langtrace_trace_id") or item.get("span_id") or item.get("langtrace_span_id")
    ]
    return {
        "enabled": config.ENABLE_LANGTRACE,
        "mode": config.LANGTRACE_MODE,
        "api_host": config.LANGTRACE_API_HOST,
        "api_key_present": bool(config.LANGTRACE_API_KEY),
        "api_key_masked": _mask(config.LANGTRACE_API_KEY),
        "sdk_import_ok": sdk_import_ok,
        "sdk_error": sdk_error,
        "recent_with_trace_ids": recent_with_ids,
        "recent_trace_capture_ok": bool(recent_with_ids),
    }


def _mask(value: str) -> str:
    if not value:
        return "missing"
    if len(value) <= 10:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def attach_eval_attributes(attributes: dict[str, Any]) -> bool:
    try:
        from opentelemetry import trace  # type: ignore

        span = trace.get_current_span()
        if not span or not span.is_recording():
            return False
        for key, value in attributes.items():
            if value is None:
                continue
            span.set_attribute(key, _safe_value(value))
        return True
    except Exception as exc:
        LOGGER.warning("Could not attach Langtrace eval attributes", extra={"reason": str(exc)})
        return False


def trace_workflow(workflow_name: str, attributes: dict[str, Any] | None = None):
    return base_trace_workflow(workflow_name, attributes)


def record_langtrace_feedback(
    trace_id: str | None,
    span_id: str | None,
    score: int,
    feedback_text: str,
    user_id: int | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not trace_id or not span_id:
        return False
    request_entry = {
        "request_id": metadata.get("request_id") if metadata else None,
        "langtrace_trace_id": trace_id,
        "langtrace_span_id": span_id,
    }
    reason_parts = []
    if feedback_text:
        reason_parts.append(feedback_text.strip())
    if metadata:
        compact_metadata = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        reason_parts.append(compact_metadata[:1200])
    return submit_feedback_evaluation(
        request_entry,
        user_id=user_id or "local-user",
        helpful=score > 0,
        details="\n".join(reason_parts),
    )


def send_eval_setup_test_trace(metrics: list[dict] | None = None) -> dict:
    if not is_langtrace_enabled():
        return {"ok": False, "message": "Langtrace is disabled."}
    if not init_langtrace():
        return {"ok": False, "message": "Langtrace SDK could not initialize."}
    metrics = metrics or enabled_metrics()
    attributes = {
        "app.name": "meditech-rag",
        "app.workflow": "eval_setup_test",
        "eval.metrics_configured": True,
        "eval.metric_names": json.dumps([item["key"] for item in metrics], ensure_ascii=False),
        "eval.test_status": "ok",
        **metric_attribute_payload(),
    }
    for metric in metrics:
        if metric.get("type") == "human":
            attributes[f"eval.{metric['key']}.rubric"] = metric.get("rubric") or metric.get("description", "")
    with base_trace_workflow("eval_setup_test", attributes) as span:
        attach_eval_attributes(attributes)
        identity = span_identity(span)
    return {"ok": True, "message": "Test eval trace sent to Langtrace.", **identity}
