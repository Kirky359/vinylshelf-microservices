"""Prometheus metrics, JSON logs and W3C trace context (the same module in every service)."""
import asyncio
import contextvars
import json
import logging
import os
import re
import secrets
import sys
import time
from contextlib import contextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)
_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")


def new_span_id() -> str:
    return secrets.token_hex(8)


def current_trace_id() -> str | None:
    return trace_id_var.get()


def outgoing_headers() -> dict[str, str]:
    """traceparent header for a call to another service."""
    trace_id = trace_id_var.get()
    if not trace_id:
        return {}
    return {"traceparent": f"00-{trace_id}-{span_id_var.get() or new_span_id()}-01"}


@contextmanager
def bind_trace(trace_id: str | None):
    """Continue a trace outside of an HTTP request (e.g. in the RabbitMQ consumer)."""
    t1 = trace_id_var.set(trace_id or secrets.token_hex(16))
    t2 = span_id_var.set(new_span_id())
    try:
        yield trace_id_var.get()
    finally:
        trace_id_var.reset(t1)
        span_id_var.reset(t2)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname, "service": self.service, "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_var.get(), "span_id": span_id_var.get(),
        }
        doc.update(getattr(record, "fields", {}))
        if record.exc_info:
            doc["exception"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False)


def setup_logging(service: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, message: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, message, extra={"fields": fields})


REQUESTS = Counter("http_requests_total", "HTTP requests handled", ["service", "method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["service", "method", "route"],
                    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
UPSTREAM = Counter("upstream_requests_total", "Calls made to other services (load distribution across instances)",
                   ["service", "target", "replica"])
_SKIP = {"/metrics", "/health"}


def count_upstream(service: str, target: str, replica: str) -> None:
    UPSTREAM.labels(service, target, replica).inc()


def _route_label(request: Request, proxy_prefixes: set[str]) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path is None:
        return "unmatched"
    if path.startswith("/{service_name}"):
        name = request.path_params.get("service_name")
        return f"/{name}/*" if name in proxy_prefixes else "/unknown/*"
    return path


def setup_observability(app: FastAPI, service: str, proxy_prefixes: set[str] | None = None) -> None:
    setup_logging(service)
    logger = logging.getLogger("access")
    prefixes = proxy_prefixes or set()
    chaos_ms = int(os.getenv("CHAOS_DELAY_MS", "0"))  # delay for the alerting demo

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        if request.url.path in _SKIP:
            return await call_next(request)
        match = _TRACEPARENT.match(request.headers.get("traceparent", ""))
        trace_id = match.group(1) if match else secrets.token_hex(16)
        parent_span = match.group(2) if match else None
        t1 = trace_id_var.set(trace_id)
        t2 = span_id_var.set(new_span_id())
        started = time.perf_counter()
        status = 500
        try:
            if chaos_ms:
                await asyncio.sleep(chaos_ms / 1000)
            response = await call_next(request)
            status = response.status_code
            response.headers["x-trace-id"] = trace_id
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = _route_label(request, prefixes)
            REQUESTS.labels(service, request.method, route, str(status)).inc()
            LATENCY.labels(service, request.method, route).observe(elapsed)
            log_event(logger, f"{request.method} {request.url.path} -> {status}",
                      logging.ERROR if status >= 500 else logging.INFO,
                      method=request.method, path=request.url.path, route=route, status=status,
                      duration_ms=round(elapsed * 1000, 1), parent_span_id=parent_span)
            trace_id_var.reset(t1)
            span_id_var.reset(t2)
