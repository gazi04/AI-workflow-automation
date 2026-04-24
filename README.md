# AI Workflow Automation

Automate workflows through natural language prompts, similar to a ChatGPT-like interface or voice input (I'm still working on this voice input feature 😅).

## The Goal

The goal of this project is to democratize workflow automation by enabling users to create complex automations through simple natural language descriptions. Instead of requiring users to write code or understand programming concepts, the AI interprets their intent and constructs workflows from pre-built action blocks.

The architecture follows a layered approach:
- **AI Layer**: Converts user requests into machine-readable templates
- **Orchestration Layer**: Executes the automation based on the generated templates using available action code

## Technologies & Framework

### Backend
- **FastAPI** - REST API framework
- **Prefect** - Workflow orchestration and task scheduling
- **PostgreSQL** - Primary database
- **Azure AI Inference** - AI/LLM integration for natural language processing
- **Google API Python Client** - Gmail integration

### Frontend
- **SvelteKit** - Web framework
- **Svelte 5** - UI framework
- **TailwindCSS** - Styling
- **@xyflow/svelte** - Node-based workflow editor (DAG visualization)

### Infrastructure
- **Docker Compose** - Container orchestration
- **Alembic** - Database migrations

## Features

- **Visual Workflow Editor** - Drag-and-drop interface for building automation workflows using a node-based DAG editor
- **Natural Language Interface** - Describe workflows in plain English; AI converts them to executable templates
- **Gmail Integration** - Automate email workflows including:
  - Creating and sending emails
  - Managing labels
  - Creating drafts
  - Smart draft composition
- **Real-time Monitoring** - WebSocket-based execution history and live workflow status updates
- **Authentication** - Secure user authentication with JWT tokens and OAuth integration
- **Conditional Logic** - Support for branching and condition-based workflow paths
- **Webhook Support** - External trigger capabilities for workflows

## Setup Locally

### Prerequisites
- Docker & Docker Compose
- Python 3.13+
- Node.js 20+

### 1. Clone and Configure

```bash
git clone <repository-url>
cd ai-workflow-automation
```

### 2. Backend Setup

```bash
cd backend
cp .env.example .env
# Edit .env with your configuration (AI API keys, database URL, etc.)
uv sync
```

### 3. Frontend Setup

```bash
cd website
cp .env.example .env
# Edit .env if needed (API URL)
bun install
```

### 4. Start Services

```bash
# From project root
docker compose up -d
```

This starts:
- PostgreSQL database (port 5432)
- PgAdmin database UI (port 8888)
- Prefect server (port 4200)
- Prefect worker
- Backend API (port 8000)
- Frontend (port 5173)

### 5. Run Migrations

```bash
cd backend
uv run alembic upgrade head
```

## How to Use

### 1. Access the Application

Open `http://localhost:5173` in your browser.

### 2. Create a Workflow

- Click **"New Workflow"** in the dashboard
- Use the visual editor to drag nodes from the catalog
- Connect nodes to define the workflow flow
- Configure each node's parameters

### 3. AI-Assisted Creation

- Click the **AI Chat** button in the editor
- Describe your desired workflow in natural language
- Example: "When I receive an email with label 'Newsletter', forward it to my-team@example.com and archive it"
- The AI will construct the workflow template for you to review and refine

### 4. Run and Monitor

- Click **"Run"** to execute the workflow manually
- Enable **triggers** for automated execution
- Monitor real-time execution status via WebSocket
- View execution history in the **History** tab

### 5. External Triggers

Workflows can be triggered via webhook:
```
POST /api/webhook/{workflow_id}
```