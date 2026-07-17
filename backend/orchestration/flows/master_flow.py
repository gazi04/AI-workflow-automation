import asyncio
import time
from collections import deque
from uuid import UUID
from prefect import flow, get_run_logger
from prefect.runtime import (
    deployment as prefect_deployment,
    flow_run as prefect_flow_run,
)
from typing import Dict, Any, Optional
from core.setup_logging import setup_logger
from core.database import db_session
from core.events import publish_event
from orchestration.tasks import send_message, reply_email, label_mail, smart_draft
from utils.build_adjacency_list import build_adjacency_list
from utils.evaluate_condition import evaluate_condition
from utils.resolve_variables import resolve_variables
from workflow.schemas import WorkflowSchema
from workflow.services import WorkflowRunService

# Loading the models ensuring that the SQLAlchemy Base registry is fully populated before any database operation
import core.models  # noqa: F401


@flow(name="Master Automation Executor", log_prints=True)
def execute_automation_flow(
    user_id: UUID,
    workflow_data: Dict[str, Any],
    trigger_context: Optional[Dict[str, Any]] = None,
    workflow_id: Optional[str] = None,
):
    """
    Executes a DAG-based workflow using a Breadth-First Search (BFS) queue.
    """
    started_at = time.monotonic()
    logger = setup_logger("Master flow")
    # Prefect's run logger so node failures land in get_run_logs (History → View Logs),
    # unlike the local setup_logger which only writes to debug.log. Falls back to the
    # local logger when there is no Prefect run context (e.g. unit tests calling .fn).
    try:
        run_logger = get_run_logger()
    except Exception:
        run_logger = logger

    try:
        schema = WorkflowSchema.model_validate(workflow_data)
    except Exception as e:
        logger.error(f"Invalid workflow data for user {user_id}: {e}")
        raise Exception("Invalid workflow data.")

    workflow = schema.execution_config

    logger.info(f"🚀 Starting Workflow: {schema.name}")

    # ♻️ todo: refactor the trigger context into a pydantic schema
    if trigger_context and "trigger_context" in trigger_context:
        ctx_data = trigger_context["trigger_context"]
    else:
        ctx_data = trigger_context or {}

    original_email = ctx_data.get("original_email")
    # The trigger payload bound into run_context for {{node.x}} resolution.
    # Email triggers pass original_email; the generic webhook trigger passes
    # webhook_payload ({body, headers, query}). Both land at the start node.
    trigger_payload = original_email or ctx_data.get("webhook_payload")
    matched_trigger_node_id = ctx_data.get("matched_trigger_node_id")

    # Fallback for manual or scheduled triggers where the node ID might not be explicitly passed yet
    if not matched_trigger_node_id:
        matched_trigger_node_id = (
            workflow.start_node_ids[0] if workflow.start_node_ids else None
        )

    if not matched_trigger_node_id:
        logger.error("No valid starting node found for this workflow.")
        return

    queue = deque([matched_trigger_node_id])
    visited = (
        set()
    )  # To prevent infinite loops if the user accidentally created a cycle

    run_context = {"trigger": trigger_payload or {}, "node_outputs": {}}

    if matched_trigger_node_id:
        run_context[matched_trigger_node_id] = trigger_payload or {}

    email_dependent_actions = {"reply_email", "label_email", "smart_draft"}
    adjacency_list = build_adjacency_list(workflow.edges)

    # node_id → error string. Any entry here marks the whole run as Failed at the end.
    failed_nodes: Dict[str, str] = {}

    # Resolve ids once so the worker can NOTIFY per-node events that the API
    # process forwards to the user's WebSocket (core/events.py, event_listener.py).
    emit_workflow_id = _runtime_id(lambda: workflow_id or prefect_deployment.id)
    emit_run_id = _runtime_id(lambda: prefect_flow_run.id)

    # A single event loop for every async bridge call in this run (emit() fires
    # once per node event, and _persist_run() fires once at the end). asyncpg
    # connections are bound to the event loop that created them, so a fresh
    # asyncio.run() per call would hand the second call a pooled connection
    # tied to the first call's already-closed loop — reusing one loop for the
    # whole run keeps the shared `engine`'s connection pool valid throughout.
    bridge_loop = asyncio.new_event_loop()

    def emit(event_type, node_id, *, node_type=None, error=None, status=None):
        bridge_loop.run_until_complete(
            publish_event(
                {
                    "type": event_type,
                    "user_id": str(user_id),
                    "workflow_id": str(emit_workflow_id) if emit_workflow_id else None,
                    "run_id": str(emit_run_id) if emit_run_id else None,
                    "node_id": node_id,
                    "node_type": node_type,
                    "error": error,
                    "status": status,
                }
            )
        )

    while queue:
        # Process one BFS level (wave) at a time: submit every action node's
        # task in this wave before waiting on any of them, so independent
        # branches actually run concurrently on Prefect's default
        # ThreadPoolTaskRunner instead of one-at-a-time.
        level_size = len(queue)
        pending_actions: Dict[str, Dict[str, Any]] = {}

        for _ in range(level_size):
            current_node_id = queue.popleft()

            if current_node_id in visited:
                continue
            visited.add(current_node_id)

            node = workflow.nodes.get(current_node_id)
            if not node:
                continue

            if node.type == "condition":
                emit("node_started", current_node_id, node_type="condition")
                try:
                    condition_result = evaluate_condition(node.config, run_context)
                    run_context["node_outputs"][current_node_id] = {
                        "result": condition_result
                    }
                    emit("node_completed", current_node_id, node_type="condition")
                except Exception as e:
                    run_logger.error(
                        f"Condition node '{current_node_id}' failed to evaluate: {e}"
                    )
                    run_context["node_outputs"][current_node_id] = {"error": str(e)}
                    failed_nodes[current_node_id] = str(e)
                    emit(
                        "node_failed",
                        current_node_id,
                        node_type="condition",
                        error=str(e),
                    )
                    # Prune: route neither handle, don't queue downstream.
                    continue

                outgoing_edges = adjacency_list.get(current_node_id, [])
                expected_handle = "true_path" if condition_result else "false_path"
                path_continued = False

                for edge in outgoing_edges:
                    if edge.sourceHandle == expected_handle:
                        queue.append(edge.target)
                        path_continued = True

                if not path_continued:
                    logger.info(
                        f"🚦 Path stopped at condition node '{current_node_id}'. "
                        f"Evaluated to '{expected_handle}', but no edges are connected to this path."
                    )
                continue

            elif node.type == "action":
                # node.config is the Action model, node.config.config is the actual action data
                action_type = node.config.type
                raw_action_data = node.config.config

                emit("node_started", current_node_id, node_type="action")
                try:
                    # Resolution lives inside the try so that a reference to an
                    # already-failed node ({{failed.body}}) surfaces as this node's
                    # failure instead of crashing the whole run.
                    resolved_dict = resolve_variables(
                        raw_action_data.model_dump(), run_context
                    )
                    action_data = type(raw_action_data)(**resolved_dict)

                    if action_type in email_dependent_actions and not original_email:
                        logger.error(
                            f"Action '{action_type}' on node '{current_node_id}' requires an email trigger context but none was provided."
                        )
                        raise ValueError(
                            "Action requires an email trigger context, but none was provided."
                        )

                    if action_type == "send_email":
                        future = send_message.submit(
                            user_id,
                            action_data.to,
                            action_data.subject,
                            action_data.body,
                        )

                    elif action_type == "reply_email":
                        future = reply_email.submit(
                            user_id, action_data.body, original_email
                        )

                    elif action_type == "label_email":
                        future = label_mail.submit(
                            user_id, action_data.label_info, original_email
                        )

                    elif action_type == "smart_draft":
                        future = smart_draft.submit(
                            user_id, original_email, action_data.user_prompt
                        )

                    elif action_type == "send_slack_message":
                        raise NotImplementedError()

                    elif action_type == "create_document":
                        raise NotImplementedError()

                    # Don't wait here — stash the future and resolve it after the
                    # whole level has been submitted, so siblings run concurrently.
                    pending_actions[current_node_id] = {
                        "future": future,
                        "action_type": action_type,
                    }

                except Exception as e:
                    run_logger.error(
                        f"Action '{action_type}' on node '{current_node_id}' failed: {e}"
                    )
                    run_context["node_outputs"][current_node_id] = {"error": str(e)}
                    failed_nodes[current_node_id] = str(e)
                    emit(
                        "node_failed", current_node_id, node_type="action", error=str(e)
                    )
                    # Prune: don't queue this node's downstream children.
                continue

            else:
                # Trigger nodes (and any other non-condition/action type) pass
                # straight through to their outgoing edges.
                outgoing_edges = adjacency_list.get(current_node_id, [])
                if not outgoing_edges:
                    logger.info(
                        f"🏁 Path stopped at node '{current_node_id}'. No further outgoing edges found."
                    )
                for edge in outgoing_edges:
                    queue.append(edge.target)

        # Resolve this level's action tasks. Every one was already submitted
        # above, so Prefect's ThreadPoolTaskRunner (the flow's default) runs
        # them concurrently — these .result() calls just wait for completion.
        for current_node_id, pending in pending_actions.items():
            action_type = pending["action_type"]
            try:
                result = pending["future"].result()
                run_context["node_outputs"][current_node_id] = result
                emit("node_completed", current_node_id, node_type="action")

                outgoing_edges = adjacency_list.get(current_node_id, [])
                if not outgoing_edges:
                    logger.info(
                        f"🏁 Path stopped at node '{current_node_id}'. No further outgoing edges found."
                    )
                for edge in outgoing_edges:
                    queue.append(edge.target)

            except Exception as e:
                run_logger.error(
                    f"Action '{action_type}' on node '{current_node_id}' failed: {e}"
                )
                run_context["node_outputs"][current_node_id] = {"error": str(e)}
                failed_nodes[current_node_id] = str(e)
                emit("node_failed", current_node_id, node_type="action", error=str(e))
                # Prune: don't queue this node's downstream children.

    # Persist a per-node audit record so the failure is durable and the WS poll
    # loop can surface a node_failed event. Wrapped so an audit-write failure
    # never masks the real run outcome.
    _persist_run(
        run_logger,
        bridge_loop,
        user_id=user_id,
        workflow_id=workflow_id,
        trigger_data=trigger_payload or None,
        node_outputs=run_context["node_outputs"],
        failed_nodes=failed_nodes,
        duration_ms=int((time.monotonic() - started_at) * 1000),
    )

    _, overall_status = build_run_audit(run_context["node_outputs"], failed_nodes)
    emit("flow_finished", None, status=overall_status)
    bridge_loop.close()

    if failed_nodes:
        # Independent branches have finished; now fail the run so the frontend
        # (which polls Prefect run state) flags it and the user sees the reasons
        # in the run logs above.
        summary = "; ".join(f"{nid}: {err}" for nid, err in failed_nodes.items())
        run_logger.error(
            f"Workflow '{schema.name}' finished with {len(failed_nodes)} "
            f"failed node(s): {summary}"
        )
        raise RuntimeError(f"Workflow failed on node(s) — {summary}")

    logger.info(f"✅ Workflow '{schema.name}' execution completed.")


def _json_safe(value: Any) -> Any:
    """Best-effort coercion so a node output always lands in JSONB."""
    import json

    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def build_run_audit(
    node_outputs: Dict[str, Any], failed_nodes: Dict[str, str]
) -> tuple[Dict[str, Any], str]:
    """Build the per-node results map and the overall run status.

    Pure (no I/O) so it can be unit-tested in isolation.
    """
    node_results: Dict[str, Any] = {}
    for node_id, output in node_outputs.items():
        if node_id in failed_nodes:
            node_results[node_id] = {
                "output": None,
                "status": "failed",
                "error": failed_nodes[node_id],
            }
        else:
            node_results[node_id] = {
                "output": _json_safe(output),
                "status": "success",
                "error": None,
            }

    success_count = len(node_outputs) - len(failed_nodes)
    if not failed_nodes:
        status = "success"
    elif success_count <= 0:
        status = "failed"
    else:
        status = "partial"

    return node_results, status


def _runtime_id(accessor) -> Optional[UUID]:
    """Safely read a prefect.runtime id (returns None outside a run context)."""
    try:
        value = accessor()
        return UUID(str(value)) if value else None
    except Exception:
        return None


def _persist_run(
    run_logger,
    bridge_loop: asyncio.AbstractEventLoop,
    *,
    user_id: UUID,
    workflow_id: Optional[str],
    trigger_data: Optional[Dict[str, Any]],
    node_outputs: Dict[str, Any],
    failed_nodes: Dict[str, str],
    duration_ms: int,
) -> None:
    # The Workflow DB id equals the Prefect deployment id; fall back to it when
    # the flow runs inside a Prefect deployment (the common path).
    resolved_workflow_id = _runtime_id(lambda: workflow_id or prefect_deployment.id)
    if not resolved_workflow_id:
        # No way to attach the record (e.g. a bare .fn unit call with no runtime);
        # skip persistence rather than violate the NOT NULL workflow_id.
        return

    node_results, status = build_run_audit(node_outputs, failed_nodes)

    async def _persist():
        async with db_session() as db:
            await WorkflowRunService.create(
                db,
                workflow_id=UUID(str(resolved_workflow_id)),
                user_id=UUID(str(user_id)),
                node_results=node_results,
                status=status,
                prefect_run_id=(
                    UUID(str(prefect_flow_run.id)) if prefect_flow_run.id else None
                ),
                trigger_data=trigger_data,
                duration_ms=duration_ms,
            )

    try:
        bridge_loop.run_until_complete(_persist())
    except Exception as e:
        run_logger.error(f"Failed to persist workflow run audit record: {e}")
