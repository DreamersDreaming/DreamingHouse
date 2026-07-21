"""AWS Lambda entry point. Database write orchestration is intentionally explicit."""

from __future__ import annotations

import json
import os
import hmac
from pathlib import Path

from agent import DreamInput, process_dream


def handler(event, _context):
    try:
        method = (
            event.get("requestContext", {}).get("http", {}).get("method", "POST")
        ).upper()
        if method == "GET":
            return html_response()
        if method != "POST":
            return response(
                405,
                {
                    "status": "method_not_allowed",
                    "message": "Only GET and POST are supported.",
                },
            )
        enforce_demo_api_key(event)
        body = event.get("body", event)
        if isinstance(body, str):
            body = json.loads(body)
        dream = DreamInput.from_payload(body)
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required")
        result = process_dream(dream, database_url)
        return response(200, result)
    except PermissionError:
        return response(401, {"status": "unauthorized", "message": "A valid demo key is required."})
    except (ValueError, json.JSONDecodeError) as exc:
        return response(400, {"status": "invalid_request", "message": str(exc)})
    except Exception:
        # Preserve details in CloudWatch without returning secrets or provider
        # errors to the caller.
        import logging

        logging.exception("Doream Recall agent execution failed")
        return response(
            500,
            {
                "status": "agent_error",
                "message": "The private memory agent could not complete this request.",
            },
        )


def html_response() -> dict:
    html = Path(__file__).with_name("static").joinpath("index.html").read_text(
        encoding="utf-8"
    )
    return {
        "statusCode": 200,
        "headers": {
            "content-type": "text/html; charset=utf-8",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
            "content-security-policy": (
                "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
            ),
        },
        "body": html,
    }


def enforce_demo_api_key(event: dict) -> None:
    """Require the private judge/demo key when configured."""
    expected = os.environ.get("DEMO_API_KEY", "")
    if not expected:
        return
    headers = {
        str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()
    }
    supplied = headers.get("x-doream-demo-key", "")
    if not hmac.compare_digest(supplied, expected):
        raise PermissionError("invalid demo API key")


def response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
        },
        "body": json.dumps(payload, ensure_ascii=False),
    }
