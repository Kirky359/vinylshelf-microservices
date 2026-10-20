# VinylShelf microservices (lab 2)

Stack: FastAPI, Consul (discovery), RabbitMQ (async events), Docker Compose.

    docker compose up -d --build          # start everything
    ./demo.sh                             # end-to-end scenario
    docker compose up -d --scale catalog-service=3 --no-recreate   # horizontal scaling
    docker compose down                   # stop

UIs: gateway http://localhost:8080/docs, Consul http://localhost:8500, RabbitMQ http://localhost:15672 (guest/guest).
Only stateless services (catalog-service) can be scaled safely: the others keep data in memory.

Each service is self-contained (its own copy of `app/discovery.py` / `app/events.py`), so images do not depend on shared code.


## Limitations (deliberate, lab scope)
- Data is kept in process memory (no database), so only the stateless catalog-service is scaled.
- No circuit breaker and no config service: config via env vars, resilience via Consul health checks + client-side failover.
- Auth tokens are issued but not validated by the gateway.
- One shared analytics queue: several consumer replicas would split events between them.
