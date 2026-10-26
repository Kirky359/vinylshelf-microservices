# VinylShelf microservices (lab 2 + lab 3)

Stack: FastAPI, Consul (discovery), RabbitMQ (async events), Docker Compose.

    docker compose up -d --build          # start everything
    ./demo.sh                             # end-to-end scenario
    docker compose up -d --scale catalog-service=3 --no-recreate   # horizontal scaling
    docker compose down                   # stop

Lab 3 (outbox / inbox / SAGA):

    docker compose down -v && docker compose up -d --build   # demo_saga.sh needs a fresh stack (the consumer fails every 3rd album_completed)
    ./demo_saga.sh                        # success, consumer error -> DLQ, timeout, broker down (takes ~1 min)

collection-service keeps data, `outbox` and `saga_log` in SQLite; the outbox dispatcher publishes to RabbitMQ with confirms.
`complete` starts a SAGA (status `CompletionPending`); analytics-consumer dedups via its `inbox`, fails every 3rd
`album_completed` (`FAIL_EVERY_N`), and the coordinator compensates on DLQ message, timeout (`SAGA_TIMEOUT_SECONDS`) or failed outbox row.

UIs: gateway http://localhost:8080/docs, Consul http://localhost:8500, RabbitMQ http://localhost:15672 (guest/guest).
Only the stateless catalog-service can be scaled safely: auth/rating keep data in memory, collection/analytics use per-service SQLite.

Each service is self-contained (its own copy of `app/discovery.py` / `app/events.py`), so images do not depend on shared code.


## Project structure

Every service follows [fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices): one package per domain
inside `src/`, global modules in the `src/` root.

    collection-service/
    ├── Dockerfile, requirements.txt
    └── src/
        ├── main.py            # app + lifespan, includes the routers
        ├── config.py          # global settings (pydantic-settings, env vars)
        ├── database.py        # SQLite connection, tx() = one local transaction
        ├── models.py          # global schema = schemas of all modules
        ├── discovery.py       # Consul registration / client-side load balancing
        ├── utils.py
        ├── messaging/         # RabbitMQ topology (constants.py, broker.py)
        ├── system/router.py   # /health, /chain
        ├── collection/        # router, schemas, service, models, dependencies, exceptions, constants
        ├── outbox/            # transactional outbox: dispatcher (service.py), /outbox
        └── saga/              # SAGA coordinator: timeouts, DLQ listener, compensation

Other services: `auth/`, `catalog/`, `rating/` (same file set), `analytics/` + `inbox/` (consumer with transactional inbox),
`gateway/` (proxy). Module settings live next to the module (`saga/config.py`, `analytics/config.py`).

## Limitations (deliberate, lab scope)
- auth-, rating-service keep data in memory; collection-service/analytics use per-service SQLite, so only the stateless catalog-service is scaled.
- Lab 3: one dispatcher/coordinator instance (SQLite); auth/rating still publish directly, not via outbox; the analytics dashboard is in memory (only the inbox is persisted).
- No circuit breaker and no config service: config via env vars, resilience via Consul health checks + client-side failover.
- Auth tokens are issued but not validated by the gateway.
- One shared analytics queue: several consumer replicas would split events between them.
