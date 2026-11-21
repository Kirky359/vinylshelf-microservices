import io
import json
import logging

import httpx
from tests.conftest import make_token
from src.observability import JsonFormatter, current_trace_id

TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


def test_trace_id_is_generated_and_returned(client):
    r = client.get("/catalog-service/catalog/search")
    assert len(r.headers["x-trace-id"]) == 32


def test_incoming_traceparent_is_continued_and_forwarded(client, monkeypatch):
    seen = {}

    async def fake_call(name, method, path, **kwargs):
        seen["trace"] = current_trace_id()
        return httpx.Response(200, json={})

    monkeypatch.setattr("src.gateway.service.call", fake_call)
    r = client.get("/catalog-service/catalog/search", headers={"traceparent": TRACEPARENT, "authorization": f"Bearer {make_token()}"})
    assert r.headers["x-trace-id"] == "0af7651916cd43dd8448eb211c80319c"
    assert seen["trace"] == "0af7651916cd43dd8448eb211c80319c"


def test_metrics_endpoint_counts_requests_by_route(client):
    client.get("/catalog-service/catalog/search")
    body = client.get("/metrics").text
    assert 'http_requests_total{method="GET",route="/catalog-service/*",service="api-gateway",status="401"}' in body
    assert "http_request_duration_seconds_bucket" in body


def test_unknown_service_does_not_create_new_label_values(client):
    client.get("/made-up-name/x")
    assert 'route="/made-up-name/*"' not in client.get("/metrics").text


def test_access_log_is_json_with_trace_id(client):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter("api-gateway"))
    logging.getLogger("access").addHandler(handler)
    try:
        client.get("/catalog-service/x", headers={"traceparent": TRACEPARENT})
    finally:
        logging.getLogger("access").removeHandler(handler)
    line = json.loads(buf.getvalue().splitlines()[-1])
    assert line["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert line["service"] == "api-gateway" and line["status"] == 401 and "duration_ms" in line
