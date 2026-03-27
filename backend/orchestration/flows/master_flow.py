from uuid import UUID
from prefect import flow
from typing import Dict, Any, Optional
from core.setup_logging import setup_logger
from orchestration.tasks import send_message, reply_email, label_mail, smart_draft
from utils.build_adjacency_list import build_adjacency_list
from utils.resolve_variables import resolve_variables
from workflow.schemas import WorkflowDefinition

# Loading the models ensuring that the SQLAlchemy Base registry is fully populated before any database operation
import core.models  # noqa: F401


@flow(name="Master Automation Executor")
def execute_automation_flow(
    user_id: UUID,
    workflow_data: Dict[str, Any],
    trigger_context: Optional[Dict[str, Any]] = None,
):
    """
    Executes a DAG-based workflow using a Breadth-First Search (BFS) queue.
    """
    logger = setup_logger("Master flow")

    try:
        workflow = WorkflowDefinition.model_validate(workflow_data)
    except Exception as e:
        logger.error(f"Invalid workflow data for user {user_id}: {e}")
        raise Exception("Invalid workflow data.")

    print(f"🚀 Starting Workflow: {workflow.name}")

    # ♻️ todo: refactor the trigger context into a pydantic schema
    if trigger_context and "trigger_context" in trigger_context:
        ctx_data = trigger_context["trigger_context"]
    else:
        ctx_data = trigger_context or {}

    original_email = ctx_data.get("original_email")
    matched_trigger_node_id = ctx_data.get("matched_trigger_node_id")

    # Fallback for manual or scheduled triggers where the node ID might not be explicitly passed yet
    if not matched_trigger_node_id:
        matched_trigger_node_id = (
            workflow.start_node_ids[0] if workflow.start_node_ids else None
        )

    if not matched_trigger_node_id:
        logger.error("No valid starting node found for this workflow.")
        return

    queue = [matched_trigger_node_id]
    visited = (
        set()
    )  # To prevent infinite loops if the user accidentally created a cycle

    run_context = {
        "trigger": ctx_data,
        "node_outputs": {}
    }

    email_dependent_actions = {"reply_email", "label_email", "smart_draft"}
    adjacency_list = build_adjacency_list(workflow.edges)

    while queue:
        current_node_id = queue.pop(0)

        if current_node_id in visited:
            continue
        visited.add(current_node_id)

        node = workflow.nodes.get(current_node_id)
        if not node:
            continue

        if node.type == "action":
            # node.config is the Action model, node.config.config is the actual action data
            action_type = node.config.type
            raw_action_data = node.config.config

            resolved_dict = resolve_variables(raw_action_data.model_dump(), run_context)
            action_data = type(raw_action_data)(**resolved_dict)

            try:
                if action_type in email_dependent_actions and not original_email:
                    logger.error(
                        f"Action '{action_type}' on node '{current_node_id}' requires an email trigger context but none was provided."
                    )
                    raise ValueError("Action requires an email trigger context, but none was provided.")

                result = None

                if action_type == "send_email":
                    result = send_message.submit(user_id, action_data.to, action_data.subject, action_data.body).result()

                elif action_type == "reply_email":
                    result = reply_email.submit(user_id, action_data.body, original_email).result()

                elif action_type == "label_email":
                    result = label_mail.submit(user_id, action_data.label_info, original_email).result()

                elif action_type == "smart_draft":
                    result = smart_draft.submit(user_id, original_email, action_data.user_prompt).result()

                elif action_type == "send_slack_message":
                    result = {"status": "sent", "channel": action_data.channel}

                elif action_type == "create_document":
                    print(f"Create document '{action_data.title}'")
                    result = {"document_id": "doc_123", "title": action_data.title}

                run_context["node_outputs"][current_node_id] = result

            except Exception as e:
                # ✨ todo: send a notification to the user here
                print(
                    f"❌ Error executing action '{action_type}' on node '{current_node_id}': {e}"
                )
                logger.error(
                    f"Unexpected error occurred on action '{action_type}': {e}"
                )
                run_context["node_outputs"][current_node_id] = {"error": str(e)}

        outgoing_edges = adjacency_list.get(current_node_id, [])
        for edge in outgoing_edges:
            queue.append(edge.target)

    print(f"✅ Workflow '{workflow.name}' execution completed.")
