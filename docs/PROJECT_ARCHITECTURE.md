# AI Workflow Automation - Project Documentation

## 1. Introduction

The **AI Workflow Automation** project aims to democratize the creation and execution of automated workflows by leveraging natural language processing. It allows users to command powerful automation sequences using simple conversational prompts, removing the need for traditional coding or complex configuration interfaces. 

### Main Features
- **Natural Language Interface:** Translate conversational input (e.g., "When I receive an email with label 'Newsletter', forward it and archive it") into executable workflow templates using AI.
- **Visual Workflow Editor:** A node-based, drag-and-drop DAG (Directed Acyclic Graph) editor that visualizes workflow schemas and allows manual construction and refinement.
- **Automated Execution & Orchestration:** Background tracking and execution of connected steps, managed securely and robustly by an orchestration engine.
- **Real-time Monitoring:** WebSocket-based event streaming to track execution history and observe live status updates.
- **Gmail Integration:** Built-in actions to interact with Gmail (e.g., fetching, labeled email processing, forwarding, creating drafts).
- **External Triggers:** Webhook endpoints allow third-party services to trigger custom workflows.

---

## 2. System Architecture

The overarching architecture is designed around clear separation of responsibilities, adopting a modular, layered structure.

### 2.1 The AI Layer
The AI component is responsible for parsing user intent. It leverages Azure AI Inference (LLMs) to ingest natural language and map it against a catalog of known "Action Blocks". It outputs a structured workflow schema (nodes and edges) which acts as a machine-readable template.

### 2.2 The Orchestration Layer
The project relies heavily on **Prefect** for backend orchestration. Prefect handles the scheduling, state management, and execution of the workflow graphs. 
- **Prefect Server:** Acts as the central hub for workflow states and API communication.
- **Prefect Worker:** A background process pool that acts upon scheduled workflow runs, fetching the action code, and executing the actual integrations (e.g., calling the Gmail API).

### 2.3 The Web / API Layer
A **FastAPI** backend serves as the bridge between the frontend editor, the database, and the orchestration engine. It defines endpoints for authentication, AI schema generation, user connections (OAuth), and webhook triggers.

### 2.4 The Data Layer
The system uses **PostgreSQL** to persistently store:
- User accounts and authentication credentials safely.
- Oauth tokens for third-party services (like Gmail).
- Saved Workflow Definitions (the DAG structures).
- Execution History logs.

### 2.5 The Presentation Layer
A **SvelteKit** frontend gives users an interactive dashboard. Utilizing Svelte 5 and TailwindCSS, it provides a responsive interface. The heavy lifter here is `@xyflow/svelte`, which powers the canvas where nodes representing actions and edges representing control flow are modeled visually.

### Component Communication Flow:
1. **User Input:** The user types a prompt in the SvelteKit frontend or drags nodes in the editor.
2. **AI Processing:** Send prompt to FastAPI -> Azure AI generates schema -> Passed back to Frontend for visual confirmation.
3. **Execution:** User triggers workflow -> FastAPI stores it in PostgreSQL and signals Prefect. 
4. **Processing:** Prefect Worker picks up the job -> executes individual Python action blocks depending on schema logic.
5. **Feedback:** Execution state changes are pushed via standard polling or WebSockets from FastAPI back to the frontend for real-time visualization.
