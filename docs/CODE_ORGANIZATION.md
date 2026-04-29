# Development & Code Organization

This document details the folder structures, the technologies utilized, and how exactly the pieces fit together under the hood.

## 1. Folder Structure

The project has a clear boundary between backend logic and frontend presentation, alongside automated Docker configurations.

```text
ai-workflow-automation/
├── backend/               # FastAPI & Prefect Orchestration logic
│   ├── actions/           # Reusable workflow nodes/blocks
│   ├── ai/                # LLM integration logic
│   ├── auth/              # JWT & OAuth handling
│   ├── core/              # DB setup, Configs, WebSocket Manager
│   ├── gmail/             # Google API integration specifics
│   ├── orchestration/     # Prefect Tasks & Flows
│   ├── processed_messages/# DB models for tracking handled triggers
│   ├── user/              # User models & API logic
│   ├── utils/             # Helper scripts
│   └── workflow/          # Core models/routers for Workflow schema
├── website/               # SvelteKit User Interface
│   ├── src/
│   │   ├── lib/           # Components & State management 
│   │   └── routes/        # App Pages (Dashboard, Editor, Auth)
├── docs/                  # Project Documentation
├── docker-compose.yml     # Service Orchestration Definitions
└── README.md              # Entrypoint Overview
```

---

## 2. Code Structure & Working Mechanism

### 2.1 Backend (Python / FastAPI)
The Backend follows a Domain-Driven-like layout containing encapsulated modules (`auth/`, `user/`, `workflow/`). Each domain folder generally encompasses:
- `models/`: SQLAlchemy ORM definitions for the Database.
- `schemas/`: Pydantic Models used for API Validation.
- `routes/`: FastAPI Routers mapping endpoints to services.
- `services/`: The core business logic decoupling DB queries from controllers.

**How it works (Backend Context):**
When an API request comes in via FastAPI, it is authenticated in the dependency layer (JWT/OAuth), processed by the relevant `services/` function, which performs queries against PostgreSQL using SQLAlchemy. 

When a workflow needs to run, it bridges out to **Prefect**. The logic in `orchestration/flows` or `orchestration/tasks` defines what needs processing asynchronously and ships that off to Prefect to be executed independently of the web API loop.

### 2.2 Frontend (SvelteKit / Bun)
The frontend uses SvelteKit, which structures its code in `src/routes/...`. 
- `routes/dashboard`: Contains pages showcasing available workflows, or triggering the editor `new` or `edit`.
- `lib/`: Encapsulates reusable UI elements like buttons, drag-and-drop handles, API fetch wrappers, and the node definitions that `@xyflow/svelte` expects.

**How it works (Frontend Context):**
The frontend utilizes Client-side routing. User interactions are managed as reactive states (Svelte Runes/stores). Dragging a node calls a state update ensuring the canvas renders precisely what the user requests.

### 2.3 The Connecting Layer (REST APIs & WebSockets)
The communication layer tying FastAPI and SvelteKit together consists of:
1. **REST APIs:** Used for CRUD Operations. When a user logs in, creates a workflow, or fetches their accounts, standard HTTP requests are fired.
2. **WebSockets:** To track the real-time execution of the long-running workflows orchestrated by Prefect, the backend (`core/websocket_manager.py`) streams execution states directly to the frontend. SvelteKit listens to this connection and mutates the visual DAG state (e.g., turning a node green, signaling "Completed") so the user gets real-time execution feedback.

---

## 3. Database & Entities

The primary datastore is **PostgreSQL**. The ORM utilized is **SQLAlchemy**. We manage database schema migrations employing **Alembic**.

### Main Entities (`core/models.py` Manifest)
1. **User:** Central identity tied to the system. Handles credentials and metadata.
2. **ConnectedAccount:** Handles 3rd-party OAuth connections (e.g., Google/Gmail tokens) linking back to a user.
3. **RefreshToken:** Securely handles JWT renewal logic.
4. **Workflow:** The stored JSON blob mimicking the layout of the graph (Nodes, Edges) combined with execution flags and cron schedules.
5. **ProcessedMessages:** Logging system that ensures duplication processing avoidance, beneficial for Inbox fetching or Webhook de-duplication.

---

## 4. Docker Services & Orchestration

We utilize `docker-compose.yml` to spin up consistent local environments quickly avoiding "works-on-my-machine" anomalies. 
The defined services orchestrate the entire platform natively:
- `postgres`: The primary database engine.
- `pgadmin`: Admin interface available on `port 8888` for direct DB inspection.
- `backend`: Runs the FastAPI server (`port 8000`) dealing with requests.
- `frontend`: The NodeJS/Bun container serving the SvelteKit application (`port 5173`).
- `prefect-server`: The localized Prefect orchestrator API and UI tracking workflow executions (`port 4200`).
- `prefect-worker`: The daemon pool connected to the project codebase running tasks defined inside our app context asynchronously.
