from uuid import UUID

from core.setup_logging import setup_logger
from prefect import flow
from typing import Dict, Any, List, Optional

from orchestration.tasks import GmailTasks

# Loading the models ensuring that the SQLAlchemy Base registry is fully populated before any database operation
import auth.models  # noqa: F401
import user.models  # noqa: F401
import workflow.models  # noqa: F401

import anyio

@flow(name="Master Automation Executor")
async def execute_automation_flow(
    user_id: UUID,
    workflow_data: Dict[str, Any],
    trigger_context: Optional[Dict[str, Any]] = None,
):
    """
    This flow is generic. It doesn't know what it does until it receives
    the 'workflow_data' JSON at runtime.
    """
    print(f"🚀 Starting Workflow: {workflow_data.get('name')}")

    logger = setup_logger("Master flow")

    original_email: Optional[Dict[str, Any]] = None
    if trigger_context:
        original_email = trigger_context.get("original_email")

    actions: List[Dict] = workflow_data.get("actions", [])

    for action in actions:
        action_type = action.get("type")
        action_config = action.get("config", {})

        try:
            if action_type == "send_email":
                await anyio.to_thread.run_sync(
                    GmailTasks.send_message,
                    user_id,
                    action_config.get("to"),
                    action_config.get("subject"),
                    action_config.get("body"),
                )

            elif action_type == "reply_email":
                if not original_email:
                    logger.error(
                        f"Action {action_type} requires an email trigger context. This is the original_email={original_email}"
                    )
                    continue

                logger.info(f"The orginal email: {original_email}")
                await anyio.to_thread.run_sync(
                    GmailTasks.reply_email,
                    user_id,
                    action_config.get("body"),
                    original_email,
                )

            elif action_type == "label_email":
                if not original_email:
                    logger.error(
                        f"Action {action_type} requires an email trigger context. This is the original_email={original_email}"
                    )
                    continue

                await anyio.to_thread.run_sync(
                    GmailTasks.label_mail,
                    user_id,
                    action_config.get("label"),
                    action_config.get("backgroundColor", ""),
                    action_config.get("textColor", ""),
                    original_email,
                )

            elif action_type == "send_slack_message":
                print(f"Send slack message to {action_config.get('channel')}")

        except Exception as e:
            # todo: ✨ send a notification to the user here
            print(f"❌ Error executing action {action_type}: {e}")
            logger.error(f"Unexpected error occurred on action {action_type}: {e}")
