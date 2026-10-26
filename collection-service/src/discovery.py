import asyncio
import itertools
import socket

import httpx

from src.config import settings

CONSUL_URL = settings.consul_url
HOSTNAME = socket.gethostname()
counters = {}


async def register(name, port):
    ip = socket.gethostbyname(HOSTNAME)
    instance_id = f"{name}-{HOSTNAME}"
    payload = {
        "Name": name,
        "ID": instance_id,
        "Address": ip,
        "Port": port,
        "Check": {
            "HTTP": f"http://{ip}:{port}/health",
            "Interval": "5s",
            "Timeout": "2s",
            "DeregisterCriticalServiceAfter": "30s",
        },
    }
    async with httpx.AsyncClient() as client:
        # consul may not be ready yet, so retry
        for attempt in range(20):
            try:
                r = await client.put(f"{CONSUL_URL}/v1/agent/service/register", json=payload)
                if r.status_code == 200:
                    print(f"[consul] registered {instance_id} at {ip}:{port}", flush=True)
                    return instance_id
            except httpx.HTTPError as e:
                print(f"[consul] retry {attempt + 1}/20: {e}", flush=True)
            await asyncio.sleep(2)
    raise RuntimeError("cannot register in Consul")


async def deregister(instance_id):
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.put(f"{CONSUL_URL}/v1/agent/service/deregister/{instance_id}")
    except httpx.HTTPError:
        pass


async def instances(name):
    # only healthy instances
    async with httpx.AsyncClient(timeout=3) as client:
        r = await client.get(f"{CONSUL_URL}/v1/health/service/{name}", params={"passing": "true"})
        r.raise_for_status()
    return [
        {"id": e["Service"]["ID"], "url": f"http://{e['Service']['Address']}:{e['Service']['Port']}"}
        for e in r.json()
    ]


async def call(name, method, path, **kwargs):
    """Round-robin over instances from Consul, try the next one if connection fails."""
    found = await instances(name)
    if not found:
        raise LookupError(f"no healthy instances of {name}")
    counter = counters.setdefault(name, itertools.count())
    start = next(counter)
    error = None
    async with httpx.AsyncClient(timeout=5) as client:
        for i in range(len(found)):
            inst = found[(start + i) % len(found)]
            try:
                return await client.request(method, inst["url"] + path, **kwargs)
            except httpx.TransportError as e:
                error = e
    raise ConnectionError(f"all instances of {name} failed: {error}")


async def chain(name, text, route):
    # each service appends its name and passes the request to the next one
    text = f"{text} -> {name}@{HOSTNAME}"
    hops = [h for h in route.split(",") if h]
    if not hops:
        return {"result": text}
    r = await call(hops[0], "GET", "/chain", params={"text": text, "route": ",".join(hops[1:])})
    return r.json()
