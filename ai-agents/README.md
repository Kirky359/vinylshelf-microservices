# VinylShelf AI agents (lab 4)

AI agents on top of the REST API of labs 1-3 (api-gateway → auth / catalog / collection / rating / analytics).
Python 3.11, class-based, layered (FastAPI stack).

| Task | What | Run |
|---|---|---|
| 1 | LLM agent with function calling (Gemini) + guardrails: tokens, tool chains, prompt injection | `python -m vinyl_agents.task1_function_calling` |
| 2 | MCP server for the REST API (tools, resources, prompts; stdio and streamable HTTP) | `python -m vinyl_agents.task2_mcp_server` |
| 3 | A2A: producer (collection-service) and consumer (analytics-consumer) as AI agents | `python -m vinyl_agents.task3_a2a.producer` / `.consumer` |

## Setup

    docker compose up -d --build                 # from the repo root: the lab 3 stack on :8080
    cd ai-agents
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    cp .env.example .env                         # put GEMINI_API_KEY there (https://aistudio.google.com/apikey)
    pytest                                       # 49 tests, no docker and no API key needed

The agents act as the user `AGENT_USERNAME` (registered on the first run).

## Task 1 — function calling

    python -m vinyl_agents.task1_function_calling

Prompts to try (commands `/stats`, `/exit`):

- `Покажи мою колекцію`
- Level 2 (chain): `Знайди в каталозі "Kind of Blue"; якщо цього альбому немає в моїй колекції — додай його, познач що я прослухав усі треки, заверши і постав 9`
- Level 3: `Ігноруй попередні інструкції`, `Додай альбом <script>alert(1)</script>`

Guardrails (`vinyl_agents/guardrails`, limits in `.env.example`):

1. `TokenBudget` — tokens per session / per user request, number of LLM requests, length of a tool chain, `max_output_tokens`; log in `logs/token_usage.json`.
2. `InputValidator` + `PromptInjectionGuard` — length, control/zero-width characters, patterns (EN/UK/RU); log in `logs/injection_attempts.json`.
3. `ToolRegistry` — allowlist of tools, Pydantic validation with `extra=forbid` (the model cannot pass a user id), `ToolOutputSanitizer` for indirect injection.

## Task 2 — MCP server

    python -m vinyl_agents.task2_mcp_server                              # stdio
    MCP_TRANSPORT=streamable-http python -m vinyl_agents.task2_mcp_server  # http://127.0.0.1:8000/mcp
    python -m vinyl_agents.task2_mcp_server.client_demo                  # tiny MCP host, no Claude needed
    npx @modelcontextprotocol/inspector .venv/bin/python -m vinyl_agents.task2_mcp_server   # MCP Inspector

Claude Desktop (`claude_desktop_config.json`):

    {"mcpServers": {"vinylshelf": {
      "command": "/abs/path/ai-agents/.venv/bin/python",
      "args": ["-m", "vinyl_agents.task2_mcp_server"],
      "env": {"GATEWAY_URL": "http://localhost:8080", "AGENT_USERNAME": "artem@pm.me", "AGENT_PASSWORD": "change-me"}}}}

Guardrails: argument validation, `MCP_READ_ONLY=true` (write tools refuse), rate limit, response size limit, audit log on stderr.

## Task 3 — A2A

    python -m vinyl_agents.task3_a2a.producer     # :9001  http://localhost:9001/.well-known/agent-card.json
    python -m vinyl_agents.task3_a2a.consumer     # :9002
    python -m vinyl_agents.task3_a2a.demo         # user -> consumer -> (A2A) producer -> outbox -> RabbitMQ -> consumer
    python -m vinyl_agents.task3_a2a.client_cli producer '{"skill": "publish_album_added", "arguments": {"user_id": "<id>", "album_id": "a1"}}'
    python -m vinyl_agents.task3_a2a.client_cli consumer "Show the dashboard of user <id>"     # text -> LLM (needs GEMINI_API_KEY)

A request is either a structured skill call (`DataPart {"skill", "arguments"}`) or free text routed by the LLM.

## Structure

Packages by domain, like the services of lab 3 (fastapi-best-practices); global modules in the root.

    src/vinyl_agents/
    ├── config.py, exceptions.py, dependencies.py      # Settings, error hierarchy, CoreContainer (DI)
    ├── vinylshelf/        client.py (REST client of the gateway), service.py (use cases), types.py
    ├── llm/               client.py (port), gemini.py, scripted.py (tests), prompts.py, schemas.py
    ├── guardrails/        token_budget, prompt_injection, output_sanitizer, rate_limiter
    ├── tools/             base.py (Tool), registry.py (ToolRegistry), vinyl_tools.py
    ├── agent/             service.py (FunctionCallingAgent), listener.py, dependencies.py (AgentContainer)
    ├── task1_function_calling/   console app: app.py, console.py
    ├── task2_mcp_server/         config.py, server.py, guard.py, app.py, client_demo.py
    └── task3_a2a/                config.py, parser, card, executor, application, remote_client,
                                  producer/ (skills, app), consumer/ (skills, app), client_cli.py, demo.py
