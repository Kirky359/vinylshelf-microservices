#!/usr/bin/env bash
# End-to-end demo of VinylShelf microservices. Needs: docker compose up -d --build; curl; python3
GW=${GW:-http://localhost:8080}
j() { python3 -m json.tool; }
step() { printf '\n\033[1m### %s\033[0m\n' "$1"; }

echo "Waiting for all services to register in Consul..."
for i in $(seq 60); do
  ready=1
  for svc in auth-service catalog-service collection-service rating-service analytics-service; do
    n=$(curl -s "$GW/discovery/$svc" 2>/dev/null | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["instances"]))' 2>/dev/null || echo 0)
    [ "$n" -ge 1 ] || ready=0
  done
  [ "$ready" = 1 ] && break
  sleep 2
done
[ "$ready" = 1 ] || { echo "services are not ready, check: docker compose ps"; exit 1; }

step "1. Synchronous chain gateway -> auth -> collection -> catalog (each appends its name)"
curl -s "$GW/chain?text=hello" | j

step "2. Consul: registered instances of catalog-service"
curl -s "$GW/discovery/catalog-service" | j

step "3. Register + login (auth-service) -> event user.registered goes to RabbitMQ"
UID_=$(curl -s -X POST $GW/auth-service/auth/register -H 'content-type: application/json' -d '{"username":"artem'$RANDOM'","password":"secret"}' | tee /dev/stderr | python3 -c 'import sys,json;print(json.load(sys.stdin)["user_id"])')

step "4. Add album (collection -> catalog sync call, then album_added event)"
curl -s -X POST $GW/collection-service/collection/add -H 'content-type: application/json' -d '{"user_id":"'$UID_'","album_id":"a1"}' | j
curl -s -X POST $GW/collection-service/collection/add -H 'content-type: application/json' -d '{"user_id":"'$UID_'","album_id":"a2"}' >/dev/null

step "5. Invariant: cannot complete before all tracks are played (expect 409)"
curl -s -w '\nHTTP %{http_code}\n' -X POST $GW/collection-service/collection/$UID_/a1/complete

step "6. Progress -> complete -> events collection.progress_updated / album_completed"
curl -s -X POST $GW/collection-service/collection/$UID_/a1/progress -H 'content-type: application/json' -d '{"tracks_played":5}' >/dev/null
curl -s -X POST $GW/collection-service/collection/$UID_/a1/complete | j

step "7. Rate (rating -> collection sync check, then rating.created event)"
curl -s -X POST $GW/rating-service/rating/rate -H 'content-type: application/json' -d '{"user_id":"'$UID_'","album_id":"a1","rating":9}' | j

sleep 1
step "8. Dashboard built asynchronously by analytics consumer"
curl -s $GW/analytics-service/analytics/$UID_/dashboard | j

step "9. Load balancing: 9 requests to catalog-service, count per replica"
for i in $(seq 9); do curl -s "$GW/catalog-service/catalog/albums/a3" | python3 -c 'import sys,json;print(json.load(sys.stdin)["served_by"])'; done | sort | uniq -c
