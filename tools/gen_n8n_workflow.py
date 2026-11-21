"""Generates observability/n8n/incident-response.json (run: python tools/gen_n8n_workflow.py)."""
import json

SPLIT = r"""
const body = $input.first().json.body || {};
return (body.alerts || []).map(a => ({ json: {
  status: a.status,
  alertname: a.labels.alertname,
  severity: a.labels.severity || 'warning',
  service: a.annotations.service || a.labels.service || a.labels.target || 'unknown',
  summary: a.annotations.summary || a.labels.alertname,
  startsAt: a.startsAt,
  fingerprint: a.fingerprint,
}}));
"""

TICKET = r"""
const alert = $input.item.json;
const fs = require('fs');
const FILE = '/home/node/.n8n/incidents.json';
let store = { incidents: {}, counter: 0 };
try { store = JSON.parse(fs.readFileSync(FILE, 'utf8')); } catch (e) { /* first incident */ }
let ticket = store.incidents[alert.fingerprint];
if (alert.status === 'firing') {
  if (!ticket || ticket.status === 'resolved') {
    store.counter += 1;
    ticket = { id: 'INC-' + String(store.counter).padStart(4, '0'), opened: alert.startsAt };
  }
  Object.assign(ticket, {
    status: 'open', alertname: alert.alertname, severity: alert.severity, service: alert.service,
    title: `[${alert.severity.toUpperCase()}] ${alert.alertname} on ${alert.service}`, summary: alert.summary,
  });
} else if (ticket) {
  ticket.status = 'resolved'; ticket.resolved = new Date().toISOString();
}
if (ticket) store.incidents[alert.fingerprint] = ticket;
fs.writeFileSync(FILE, JSON.stringify(store));
return { json: { ...(ticket || {}), notify: alert.status === 'firing' && !!$env.SLACK_WEBHOOK_URL } };
"""


def code(name, js, pos):
    return {"parameters": {"jsCode": js.strip()}, "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


nodes = [
    {"parameters": {"httpMethod": "POST", "path": "alertmanager", "options": {}}, "name": "Alertmanager webhook",
     "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0], "webhookId": "alertmanager-webhook"},
    code("Split alerts", SPLIT, [220, 0]),
    {**code("Create incident ticket", TICKET, [440, 0]), "parameters": {"mode": "runOnceForEachItem", "jsCode": TICKET.strip()}},
    {"parameters": {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
                                   "conditions": [{"id": "n", "leftValue": "={{ $json.notify }}", "rightValue": True,
                                                   "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
                                   "combinator": "and"}},
     "name": "Slack configured?", "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [660, 0]},
    {"parameters": {"method": "POST", "url": "={{ $env.SLACK_WEBHOOK_URL }}", "sendBody": True, "specifyBody": "json",
                    "jsonBody": "={{ JSON.stringify({ text: `*${$json.id}* ${$json.title}\\n${$json.summary}\\nService: ${$json.service}` }) }}",
                    "options": {}},
     "name": "Post ticket to Slack", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [880, -80],
     "onError": "continueRegularOutput"},
]
conn = lambda a, b, i=0: {a: {"main": [[{"node": b, "type": "main", "index": 0}]]}}
connections = {}
for a, b in [("Alertmanager webhook", "Split alerts"), ("Split alerts", "Create incident ticket"),
             ("Create incident ticket", "Slack configured?")]:
    connections.update(conn(a, b))
connections["Slack configured?"] = {"main": [[{"node": "Post ticket to Slack", "type": "main", "index": 0}], []]}

wf = {"id": "vinylshelfIncident01", "name": "VinylShelf incident response", "active": True, "nodes": nodes,
      "connections": connections, "settings": {"executionOrder": "v1"}, "pinData": {}}
json.dump(wf, open("observability/n8n/incident-response.json", "w"), indent=1, ensure_ascii=False)
