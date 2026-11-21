#!/usr/bin/env bash
# Lab 6 demo: normal traffic, three failures, alerts, incident tickets (needs a running docker compose stack).
GW=${GW:-http://localhost:8080}
TOKEN=$("$(dirname "$0")/keycloak/get_token.sh")
step() { printf '\n\033[1m### %s\033[0m\n' "$1"; }
api() { curl -s -H "Authorization: Bearer $TOKEN" "$@"; }
load() {
  end=$((SECONDS + $1))
  while [ $SECONDS -lt $end ]; do
    api "$GW/catalog-service/catalog/albums/a3" -o /dev/null
    api "$GW/collection-service/collection/artem" -o /dev/null
    sleep 0.2
  done
}
alerts() {
  curl -s localhost:9093/api/v2/alerts | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    print('  %-20s %-9s %s' % (a['labels']['alertname'], a['labels']['severity'], a['annotations']['summary']))"
}
wait_alert() {
  for _ in $(seq "$2"); do
    curl -s localhost:9093/api/v2/alerts | grep -q "\"alertname\":\"$1\"" && { echo "  alert $1 is firing"; return; }
    sleep 1
  done
  echo "  alert $1 did not fire in $2 s"
}
tickets() {
  docker compose exec -T n8n cat /home/node/.n8n/incidents.json | python3 -c "
import sys, json
for t in json.load(sys.stdin)['incidents'].values():
    print('  %s %-9s %s' % (t['id'], t['status'], t['title']))"
}

step "0. Baseline traffic (30 s)"; load 30

step "1. Node down: stop catalog-service"
docker compose stop catalog-service >/dev/null 2>&1
wait_alert ServiceDown 60; sleep 12; tickets
docker compose start catalog-service >/dev/null 2>&1; sleep 15

step "2. High latency: catalog-service answers in 800 ms (fault injection)"
CATALOG_DELAY_MS=800 docker compose up -d catalog-service >/dev/null 2>&1; sleep 15
load 100 & wait_alert HighLatencyP99 100; wait; tickets
docker compose up -d catalog-service >/dev/null 2>&1; sleep 10

step "3. Replication lag: stop the consumer, complete albums"
docker compose stop analytics-consumer >/dev/null 2>&1
for i in 1 2 3; do
  U=lag$i-$RANDOM
  api -X POST "$GW/collection-service/collection/add" -H 'content-type: application/json' -d "{\"user_id\":\"$U\",\"album_id\":\"a1\"}" -o /dev/null
  api -X POST "$GW/collection-service/collection/$U/a1/progress" -H 'content-type: application/json' -d '{"tracks_played":5}' -o /dev/null
  api -X POST "$GW/collection-service/collection/$U/a1/complete" -o /dev/null
done
wait_alert EventLagHigh 90
docker compose start analytics-consumer >/dev/null 2>&1

step "Active alerts"; alerts
step "Incident tickets (n8n)"; tickets
