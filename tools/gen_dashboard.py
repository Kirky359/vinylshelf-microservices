"""Generates observability/grafana/dashboards/vinylshelf.json (run: python tools/gen_dashboard.py)."""
import json

PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}
panels, pid = [], 0


def panel(kind, title, targets, x, y, w, h, ds=PROM, unit=None, extra=None, options=None):
    global pid
    pid += 1
    p = {"id": pid, "type": kind, "title": title, "datasource": ds, "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "targets": [{"refId": chr(65 + i), "datasource": ds, **t} for i, t in enumerate(targets)],
         "fieldConfig": {"defaults": {"unit": unit} if unit else {}, "overrides": []}, "options": options or {}}
    if extra:
        p["fieldConfig"]["defaults"].update(extra)
    panels.append(p)


def row(title, y):
    global pid
    pid += 1
    panels.append({"id": pid, "type": "row", "title": title, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "collapsed": False})


def q(expr, legend=""):
    return {"expr": expr, "legendFormat": legend}


S = '{service=~"$service"}'
red_green = {"thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}}
row("Cluster health", 0)
panel("stat", "Healthy instances (Consul)", [q("consul_healthy_instances", "{{target}}")], 0, 1, 10, 4, extra=red_green,
      options={"colorMode": "background", "graphMode": "none", "textMode": "value_and_name"})
panel("stat", "Firing alerts", [q('count(ALERTS{alertstate="firing"}) or vector(0)')], 10, 1, 4, 4,
      extra={"thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}]}},
      options={"colorMode": "background"})
panel("stat", "Scrape targets up", [q("sum(up)", "up"), q("count(up) - sum(up)", "down")], 14, 1, 5, 4,
      options={"colorMode": "value", "graphMode": "none"})
panel("stat", "Requests per second", [q("sum(rate(http_requests_total[1m]))")], 19, 1, 5, 4, unit="reqps")

row("Latency, throughput, errors (gateway = coordinator, per-service series below)", 5)
panel("timeseries", "Latency p50 / p95 / p99", [
    q(f"histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket{S}[1m])))", "p50"),
    q(f"histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{S}[1m])))", "p95"),
    q(f"histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{S}[1m])))", "p99")],
    0, 6, 8, 8, unit="s")
panel("timeseries", "Throughput by service", [q("sum by (service) (rate(http_requests_total[1m]))", "{{service}}")], 8, 6, 8, 8, unit="reqps")
panel("timeseries", "Error rate (5xx share)", [q(
    'sum by (service) (rate(http_requests_total{status=~"5.."}[1m])) / sum by (service) (rate(http_requests_total[1m]))',
    "{{service}}")], 16, 6, 8, 8, unit="percentunit")
panel("timeseries", "p99 latency by service", [q(
    "histogram_quantile(0.99, sum by (le, service) (rate(http_request_duration_seconds_bucket[1m])))", "{{service}}")],
    0, 14, 12, 7, unit="s")
panel("timeseries", "Gateway latency p95 by backend route", [q(
    'histogram_quantile(0.95, sum by (le, route) (rate(http_request_duration_seconds_bucket{service="api-gateway"}[1m])))',
    "{{route}}")], 12, 14, 12, 7, unit="s")

row("Replication lag (events stream: outbox -> RabbitMQ -> consumer)", 21)
panel("timeseries", "Events waiting in the queue (lag > 10 s fires EventLagHigh)", [q("rabbitmq_detailed_queue_messages_ready", "{{queue}}")], 0, 22, 12, 7)
panel("timeseries", "Events processed by the consumer", [q("sum by (result) (rate(analytics_events_total[1m]))", "{{result}}")], 12, 22, 12, 7, unit="ops")

row("Distribution (load balancing across instances)", 29)
panel("bargauge", "Calls per instance, last 5 min", [q("sum by (target, replica) (increase(upstream_requests_total[5m]))", "{{target}} / {{replica}}")],
      0, 30, 12, 8, options={"orientation": "horizontal", "displayMode": "gradient"})
panel("piechart", "Share of gateway traffic by backend", [q('sum by (target) (increase(upstream_requests_total{service="api-gateway"}[5m]))', "{{target}}")],
      12, 30, 12, 8)

row("Logs (Loki): paste a trace_id into the filter to follow one request through all services", 38)
panel("logs", "Logs of $service", [{"expr": '{service=~"$service"} | json | trace_id=~"$trace_id"', "queryType": "range"}], 0, 39, 24, 12,
      ds=LOKI, options={"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending"})

dash = {
    "uid": "vinylshelf", "title": "VinylShelf Observability", "schemaVersion": 39, "version": 1, "refresh": "5s",
    "time": {"from": "now-15m", "to": "now"}, "timezone": "browser", "panels": panels, "tags": ["vinylshelf"],
    "templating": {"list": [
        {"name": "service", "type": "query", "datasource": PROM, "query": "label_values(http_requests_total, service)",
         "includeAll": True, "allValue": ".+", "multi": True, "current": {"text": "All", "value": "$__all"}, "refresh": 2},
        {"name": "trace_id", "type": "textbox", "label": "trace_id", "query": ".*", "current": {"text": ".*", "value": ".*"}},
    ]},
}
json.dump(dash, open("observability/grafana/dashboards/vinylshelf.json", "w"), indent=1, ensure_ascii=False)
