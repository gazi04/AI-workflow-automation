from uuid import UUID
from prefect import flow
from typing import Dict, Any, Optional
from core.setup_logging import setup_logger
from orchestration.tasks import GmailTasks
from workflow.schemas.workflow_definition import WorkflowDefinition
from workflow.schemas.action import (
    Action,
    SendEmailAction,
    ReplyEmailAction,
    LabelEmailAction,
    SmartDraftAction,
    SendSlackMessageAction,
    CreateDocumentAction,
)

# Loading the models ensuring that the SQLAlchemy Base registry is fully populated before any database operation
import core.models
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
    logger = setup_logger("Master flow")

    try:
        workflow = WorkflowDefinition.model_validate(workflow_data)
    except Exception as e:
        logger.error(f"Invalid workflow data for user {user_id}: {e}")
        raise

    print(f"🚀 Starting Workflow: {workflow.name}")

    original_email: Optional[Dict[str, Any]] = (
        trigger_context.get("original_email") if trigger_context else None
    )

    def requires_email_context(action: Action) -> bool:
        return isinstance(action, (ReplyEmailAction, LabelEmailAction, SmartDraftAction))

    for action in workflow.actions:
        try:
            if requires_email_context(action) and not original_email:
                logger.error(
                    f"Action '{action.type}' requires an email trigger context but none was provided."
                )
                continue

            if isinstance(action, SendEmailAction):
                await anyio.to_thread.run_sync(
                    GmailTasks.send_message,
                    user_id,
                    action.config.to,
                    action.config.subject,
                    action.config.body,
                )

            elif isinstance(action, ReplyEmailAction):
                await anyio.to_thread.run_sync(
                    GmailTasks.reply_email,
                    user_id,
                    action.config.body,
                    original_email,
                )

            elif isinstance(action, LabelEmailAction):
                await anyio.to_thread.run_sync(
                    GmailTasks.label_mail,
                    user_id,
                    action.config.label_info,
                    original_email,
                )

            elif isinstance(action, SmartDraftAction):
                await anyio.to_thread.run_sync(
                    GmailTasks.smart_draft,
                    user_id,
                    original_email,
                    action.config.user_prompt,
                )

            elif isinstance(action, SendSlackMessageAction):
                print(f"Send slack message to {action.config.channel}")

            elif isinstance(action, CreateDocumentAction):
                print(f"Create document '{action.config.title}'")

        except Exception as e:
            # todo: ✨ send a notification to the user here
            print(f"❌ Error executing action '{action.type}': {e}")
            logger.error(f"Unexpected error occurred on action '{action.type}': {e}")
