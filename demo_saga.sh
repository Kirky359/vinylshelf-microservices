#!/usr/bin/env bash
# Lab 3: transactional outbox / inbox + SAGA with compensation. Needs: docker compose up -d --build; curl; python3
GW=${GW:-http://localhost:8080}
C=$GW/collection-service
j() { python3 -m json.tool; }
step() { printf '\n\033[1m### %s\033[0m\n' "$1"; }
field() { python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
post() { curl -s -X POST "$@" -H 'content-type: application/json'; }
state() { curl -s $C/collection/$1/$2 | field status; }
tbl() { python3 -c "
import sys,json
rows=json.load(sys.stdin)['$1']
cols='$2'.split()
print(*[c.ljust(40) for c in cols])
for r in reversed(rows): print(*[str(r.get(c) or '-')[:38].ljust(40) for c in cols])"; }
play() { post $C/collection/$1/$2/progress -d '{"tracks_played":'$3'}' >/dev/null; }

step "0. Register a user, add albums a1, a4 (5 tracks) and a2 (17 tracks), play all tracks"
U=$(post $GW/auth-service/auth/register -d '{"username":"saga'$RANDOM'","password":"secret"}' | field user_id)
for a in a1 a4 a2; do post $C/collection/add -d '{"user_id":"'$U'","album_id":"'$a'"}' >/dev/null; done
play $U a1 5; play $U a4 5; play $U a2 17
echo "user $U"

step "1. SAGA happy path: complete a1 -> CompletionPending -> (outbox, RabbitMQ, consumer, confirm) -> Completed"
post $C/collection/$U/a1/complete | j
echo "status right after the call: $(state $U a1)"; sleep 3; echo "status after consumer confirmation: $(state $U a1)"

step "2. Complete a4 (second event, also succeeds)"
post $C/collection/$U/a4/complete >/dev/null; sleep 3; echo "a4: $(state $U a4)"

step "3. Complete a2: consumer throws 'Simulated processing error' -> nack -> DLQ -> coordinator rolls back"
post $C/collection/$U/a2/complete | j
echo "status right after the call: $(state $U a2)"; sleep 4; echo "status after rollback: $(state $U a2)"

step "4. saga_log (collection DB)"
curl -s "$C/saga?user_id=$U" | tbl sagas "saga_id album_id state reason"
step "5. outbox (collection DB)"
curl -s "$C/outbox?user_id=$U" | tbl outbox "event_type status attempts"
step "6. inbox (analytics DB)"
curl -s "$GW/analytics-service/analytics/inbox?user_id=$U" | tbl inbox "event status deliveries"

step "7. Inbox idempotency: re-publish an already processed message (same message_id) via RabbitMQ HTTP API"
PAYLOAD=$(curl -s "$GW/analytics-service/analytics/inbox?user_id=$U" | python3 -c "
import sys,json
rows=[r for r in json.load(sys.stdin)['inbox'] if r['event']=='collection.album_added'][0:1]
print(json.dumps(rows[0]['message_id']))")
python3 - "$PAYLOAD" "$U" <<'PY'
import sys, json, base64, urllib.request
mid = json.loads(sys.argv[1]); uid = sys.argv[2]
body = json.dumps({"message_id": mid, "saga_id": None, "event": "collection.album_added", "user_id": uid, "album_id": "a1"})
req = urllib.request.Request("http://localhost:15672/api/exchanges/%2F/vinylshelf.events/publish",
    data=json.dumps({"properties": {"delivery_mode": 2}, "routing_key": "collection.album_added",
                     "payload": body, "payload_encoding": "string"}).encode(),
    headers={"content-type": "application/json", "Authorization": "Basic " + base64.b64encode(b"guest:guest").decode()})
print(urllib.request.urlopen(req).read().decode())
PY
sleep 2
docker compose logs --no-log-prefix --tail 4 analytics-consumer

step "8. Dashboard: only confirmed completions are counted (a1, a4 -> 2; a2 was rolled back)"
curl -s $GW/analytics-service/analytics/$U/dashboard | j

step "9. Timeout: stop the consumer, complete a2 again, wait for SAGA_TIMEOUT_SECONDS (20 s)"
docker compose stop analytics-consumer >/dev/null 2>&1
post $C/collection/$U/a2/complete >/dev/null
echo "status: $(state $U a2)"; sleep 24; echo "status after timeout: $(state $U a2)"
docker compose logs --no-log-prefix --tail 3 collection-service
docker compose start analytics-consumer >/dev/null 2>&1

step "10. Outbox failure: stop RabbitMQ, complete a2 -> 3 failed attempts -> outbox 'failed' -> rollback"
docker compose stop rabbitmq >/dev/null 2>&1
post $C/collection/$U/a2/complete >/dev/null
echo "status: $(state $U a2)"; sleep 14; echo "status after failed delivery: $(state $U a2)"
curl -s "$C/outbox?user_id=$U" | tbl outbox "event_type status attempts last_error" | tail -3
docker compose start rabbitmq >/dev/null 2>&1
sleep 5; echo "after RabbitMQ is back: $(state $U a2)"
