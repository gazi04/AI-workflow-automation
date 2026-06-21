# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (run from `backend/`)
```bash
uv run uvicorn main:app --reload          # dev server (port 8000)
uv run pytest                             # all tests
uv run pytest tests/unit/test_foo.py      # single test file
uv run pytest tests/unit/test_foo.py::test_name  # single test
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run alembic upgrade head               # apply migrations
uv run alembic revision --autogenerate -m "description"  # new migration
```

### Frontend (run from `website/`)
```bash
npm run dev       # dev server (port 5173)
npm run check     # type-check
npm run lint      # prettier + eslint
npm run format    # prettier write
```

### Infrastructure (run from repo root)
```bash
docker compose up -d                                      # start all services
docker compose exec backend uv run alembic upgrade head   # migrate in Docker
```

Docker services: PostgreSQL (5432), PgAdmin (8888), Prefect server (4200), Prefect worker, backend (8000), frontend (5173).

A running Prefect worker (`my-process-pool`) is required for workflow execution. Outside Docker, start it with:
```bash
cd backend && uv run prefect worker start --pool 'my-process-pool' --type process
```

## Architecture

### Overview
Monorepo with `backend/` (FastAPI + Prefect) and `website/` (SvelteKit 5). Workflows are stored as JSON in PostgreSQL, deployed to Prefect as named deployments, and executed by a Prefect worker process.

### Backend module structure
Each domain follows `routes/ → services/ → schemas/ → models/`. Domains: `auth`, `ai`, `gmail`, `workflow`, `orchestration`, `user`, `processed_messages`, `core`.

**`core/models.py`** is a SQLAlchemy manifest that imports every ORM model. It must be imported at the top level in `main.py` and `master_flow.py` before any DB operation to resolve circular dependencies and SQLAlchemy mapper relationships.

**`core/database.py`** provides two session patterns:
- `get_db()` — generator for FastAPI `Depends(get_db)` injection
- `db_session()` — context manager for use in orchestration tasks and scripts

### Workflow data model
A `WorkflowSchema` (Pydantic) contains an `execution_config: WorkflowExecutionConfig` with:
- `nodes: Dict[str, WorkflowNode]` — keyed by node ID for O(1) lookup
- `edges: List[Edge]` — flat list of connections
- `start_node_ids: List[str]` — trigger node IDs

`WorkflowExecutionConfig` validates DAG constraints (no cycles, reachability) via `@model_validator` at parse time.

### Execution flow
1. Gmail Pub/Sub push → `POST /api/webhooks/gmail`
2. `GmailHistoryProcessor` fetches new messages, matches against active workflow triggers
3. `DeploymentService.run(workflow_id, trigger_context)` calls `prefect.run_deployment`
4. Prefect worker picks up the job and runs `execute_automation_flow` (BFS over the DAG)
5. Each action node calls a `@task`-decorated function in `orchestration/tasks/gmail_tasks.py`
6. Node output stored in `run_context["node_outputs"][node_id]` for downstream variable resolution

### Variable resolution
Action node configs support `{{node_id.property}}` interpolation via `utils/resolve_variables.py`. The context object passed is `run_context` which has keys `trigger`, `node_outputs`, and each trigger node ID mapped to the trigger payload.

### Catalog-driven frontend
`utils/catalog_introspector.py` introspects the `Trigger`, `Action`, and `Condition` Pydantic unions to auto-generate `WorkflowCatalog`. **To add a new node type**: add the Pydantic model to the appropriate union in `workflow/schemas/{trigger,action,condition_nodes}.py`, then add execution logic in `orchestration/flows/master_flow.py`. The frontend catalog updates automatically.

Node types use `model_config = ConfigDict(json_schema_extra={...})` to declare UI metadata (`category`, `icon`, `outputs`). Field-level widgets override use `json_schema_extra={"widget": "color"|"password"|...}`.

### Condition routing
Condition nodes (`if_condition`) evaluate rules and route via `sourceHandle`. Edges from condition nodes must have `sourceHandle: "true_path"` or `"false_path"`. The master flow uses this to select which outgoing edge to follow.

### AI integration
`AiService` uses **Azure AI Inference** (not Anthropic). `generate_workflow()` sends the full `WorkflowSchema.model_json_schema()` as context to the LLM and validates the response back into a `WorkflowSchema`. `ask_ai()` is used for the smart draft feature.

### Authentication
JWT access tokens + rotating refresh tokens, delivered to the browser as **HttpOnly cookies** (`access_token`, `refresh_token`) plus a readable `csrf_token` cookie (`core/cookies.py`). A double-submit CSRF middleware (`main.py`) checks `X-CSRF-Token` against the cookie on mutating requests (webhooks, OAuth callback, and bearer-auth requests are exempt). `get_current_user` reads the access cookie, falling back to the `Authorization: Bearer` header for non-browser clients/tests. Refresh tokens are stored **hashed** (SHA-256, `auth.utils.hash_refresh_token`) — never plaintext.

Google OAuth tokens in `ConnectedAccount` are **Fernet-encrypted at rest** (`core/crypto.py`, key = `TOKEN_ENCRYPTION_KEY`); encrypt on write, decrypt on read. `AuthService.get_google_credentials()` auto-refreshes expired Google tokens and marks the account disconnected on `invalid_grant`.

### Frontend
SvelteKit 5 (Svelte 5 runes). Visual editor uses `@xyflow/svelte` for the DAG canvas. UI components are shadcn-svelte (bits-ui). API types live in `src/lib/types/schema.d.ts` (generated from backend OpenAPI schema). Stores use Svelte 5 `$state` rune pattern (class-based).

### Deduplication
`ProcessedMessages` table prevents the same Gmail message from triggering the same workflow twice.
