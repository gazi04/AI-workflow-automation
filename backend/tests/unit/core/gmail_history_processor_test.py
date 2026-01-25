import pytest
from unittest.mock import MagicMock, patch, ANY
from uuid import uuid4
from googleapiclient.errors import HttpError

from core.processors import GmailHistoryProcessor

@pytest.fixture
def mock_credentials():
    return MagicMock()

@pytest.fixture
def user_id():
    return uuid4()

@pytest.fixture
def mock_service():
    """Mocks the Google API Service object chain."""
    service = MagicMock()
    # Chain: service.users().messages().get().execute()
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {}
    return service

@pytest.fixture
def processor(mock_credentials, user_id, mock_service):
    """Creates an instance of the processor with a mocked service attached."""
    processor = GmailHistoryProcessor(mock_credentials, user_id)
    processor.service = mock_service
    processor.logger = MagicMock() # Mock the logger to prevent console noise
    return processor

# --- Helper to create mock workflows ---
def create_mock_workflow(active=True, trigger_from=None, trigger_subject=None):
    workflow = MagicMock()
    workflow.id = uuid4()
    workflow.name = "Test Workflow"
    workflow.is_active = active
    workflow.config = {
        "trigger": {
            "type": "email_received",
            "config": {
                "from": trigger_from or "",
                "subject_contains": trigger_subject or ""
            }
        }
    }
    return workflow

# --- Helper to create mock email payloads ---
def create_email_payload(message_id, labels=["INBOX"], subject="Hello", sender="test@example.com"):
    return {
        "id": message_id,
        "threadId": "thread-123",
        "labelIds": labels,
        "snippet": "This is a snippet",
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "Message-ID", "value": f"<{message_id}@example.com>"},
                {"name": "References", "value": ""}
            ]
        }
    }

# ==========================================
# TEST CASES
# ==========================================

@patch("core.database.db_session")
@patch("workflow.services.workflow_service.WorkflowService")
@patch("processed_messages.services.ProcessedMessageService")
@patch("orchestration.services.deployment_service.DeploymentService")
@patch("anyio.from_thread.run")
def test_process_message_success_trigger(
    mock_anyio_run,
    mock_deployment_service,
    mock_processed_service,
    mock_workflow_service,
    mock_db_session,
    processor,
    mock_service
):
    """
    Scenario: 
    - Email is in INBOX.
    - Workflow is Active.
    - Email 'From' and 'Subject' match the workflow config.
    - Message has NOT been processed before.
    
    Expected Result: 
    - DeploymentService.run is called.
    - ProcessedMessageService.create is called.
    """
    # 1. Setup Data
    message_id = "msg-success-123"
    target_email = "target@example.com"
    target_subject = "Important Alert"
    
    # Mock Gmail API response
    email_payload = create_email_payload(
        message_id, 
        labels=["INBOX", "IMPORTANT"], 
        subject=target_subject, 
        sender=f"Sender <{target_email}>"
    )
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    # Mock DB Workflows
    matching_workflow = create_mock_workflow(active=True, trigger_from=target_email, trigger_subject="Important")
    mock_workflow_service.get_by_user_id.return_value = [matching_workflow]

    # Mock Processed Check (Returns None, meaning not processed yet)
    mock_processed_service.get_by_message_id_and_workflow_id.return_value = None

    # 2. Run
    processor._process_single_message(message_id)

    # 3. Assertions
    # Ensure processed record created
    mock_processed_service.create.assert_called_once_with(ANY, message_id, matching_workflow.id)
    
    # Ensure deployment triggered via anyio
    mock_anyio_run.assert_called_once()
    args, _ = mock_anyio_run.call_args
    assert args[0] == mock_deployment_service.run # First arg should be the function
    assert args[1] == matching_workflow.id # Second arg is workflow ID


@patch("core.database.db_session")
def test_process_message_skips_wrong_label(mock_db_session, processor, mock_service):
    """
    Scenario: Email is NOT in INBOX (e.g. Archived or Sent).
    Expected Result: Return early, DB is never queried.
    """
    message_id = "msg-skipped-label"
    email_payload = create_email_payload(message_id, labels=["SENT", "IMPORTANT"]) # No INBOX
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    processor._process_single_message(message_id)

    # Verify logger caught it
    processor.logger.debug.assert_any_call(f"Skipping message {message_id}. Labels ['SENT', 'IMPORTANT'] do not meet criteria (Must be INBOX, not SPAM/TRASH).")
    
    # Verify we never even opened the DB session
    mock_db_session.assert_not_called()


@patch("core.database.db_session")
@patch("workflow.services.workflow_service.WorkflowService")
@patch("processed_messages.services.ProcessedMessageService")
@patch("anyio.from_thread.run")
def test_process_message_skips_mismatch_trigger(
    mock_anyio_run,
    mock_processed_service,
    mock_workflow_service,
    mock_db_session,
    processor,
    mock_service
):
    """
    Scenario: Email exists, Workflow active, but Subject does NOT match.
    Expected Result: No deployment triggered.
    """
    message_id = "msg-mismatch"
    email_payload = create_email_payload(
        message_id, 
        subject="Random Newsletter", 
        sender="news@example.com"
    )
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    # Workflow expects "Urgent" in subject
    workflow = create_mock_workflow(active=True, trigger_subject="Urgent")
    mock_workflow_service.get_by_user_id.return_value = [workflow]

    processor._process_single_message(message_id)

    # Verify log
    processor.logger.debug.assert_any_call(ANY) # Check that we logged a mismatch
    
    # Verify NO deployment
    mock_anyio_run.assert_not_called()
    mock_processed_service.create.assert_not_called()


@patch("core.database.db_session")
@patch("workflow.services.workflow_service.WorkflowService")
@patch("processed_messages.services.ProcessedMessageService")
@patch("anyio.from_thread.run")
def test_process_message_skips_already_processed(
    mock_anyio_run,
    mock_processed_service,
    mock_workflow_service,
    mock_db_session,
    processor,
    mock_service
):
    """
    Scenario: Everything matches, BUT the message ID exists in ProcessedMessageService.
    Expected Result: Skip to avoid duplicate run.
    """
    message_id = "msg-duplicate"
    email_payload = create_email_payload(message_id, subject="Hello", sender="me@test.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_from="me@test.com")
    mock_workflow_service.get_by_user_id.return_value = [workflow]

    # Simulate that it WAS found in DB
    mock_processed_service.get_by_message_id_and_workflow_id.return_value = MagicMock()

    processor._process_single_message(message_id)

    # Assertions
    processor.logger.info.assert_any_call(f"Skipping duplicated: Workflow {workflow.id} already ran for message {message_id}")
    mock_anyio_run.assert_not_called()
