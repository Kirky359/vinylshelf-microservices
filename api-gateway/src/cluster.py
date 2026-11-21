"""Cluster health for Prometheus: how many healthy instances Consul knows for every backend service."""
import asyncio
import logging

from prometheus_client import Gauge

from src.discovery import instances
from src.gateway.constants import ROUTES
from src.observability import log_event

HEALTHY = Gauge("consul_healthy_instances", "Healthy instances registered in Consul", ["target"])
log = logging.getLogger("cluster")


async def poll_forever(period: float = 5.0) -> None:
    while True:
        for name in ROUTES:
            try:
                HEALTHY.labels(name).set(len(await instances(name)))
            except Exception as exc:  # keep the last value
                log_event(log, "cannot read instances from Consul", logging.WARNING, target=name, error=repr(exc))
        await asyncio.sleep(period)
