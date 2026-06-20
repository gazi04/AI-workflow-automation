import pytest
from unittest.mock import MagicMock, patch, ANY
from uuid import uuid4
from googleapiclient.errors import HttpError

from core.processors import GmailHistoryProcessor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_credentials():
    return MagicMock()


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {}
    return service


@pytest.fixture
def processor(mock_credentials, user_id, mock_service):
    p = GmailHistoryProcessor(mock_credentials, user_id)
    p.service = mock_service
    p.logger = MagicMock()
    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_workflow_config(trigger_from=None, trigger_subject=None):
    """Build a valid WorkflowExecutionConfig dict for a trigger→send_email workflow."""
    return {
        "start_node_ids": ["trigger_1"],
        "nodes": {
            "trigger_1": {
                "id": "trigger_1",
                "type": "trigger",
                "config": {
                    "type": "email_received",
                    "config": {
                        "from": trigger_from or None,
                        "subject_contains": trigger_subject or None,
                    },
                },
            },
            "action_1": {
                "id": "action_1",
                "type": "action",
                "config": {
                    "type": "send_email",
                    "config": {
                        "to": "output@example.com",
                        "subject": "Auto reply",
                        "body": "Hello",
                    },
                },
            },
        },
        "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
    }


def create_mock_workflow(active=True, trigger_from=None, trigger_subject=None):
    workflow = MagicMock()
    workflow.id = uuid4()
    workflow.name = "Test Workflow"
    workflow.is_active = active
    workflow.config = make_workflow_config(trigger_from, trigger_subject)
    return workflow


def create_email_payload(message_id, labels=None, subject="Hello", sender="test@example.com"):
    if labels is None:
        labels = ["INBOX"]
    return {
        "id": message_id,
        "threadId": "thread-123",
        "labelIds": labels,
        "snippet": "This is a snippet",
        "historyId": "12345",
        "internalDate": "1700000000000",
        "sizeEstimate": 1024,
        "payload": {
            "partId": "",
            "mimeType": "text/plain",
            "filename": "",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "Message-ID", "value": f"<{message_id}@example.com>"},
                {"name": "References", "value": ""},
            ],
            "parts": [],
            "body": {"size": 0, "data": None},
        },
    }


# ---------------------------------------------------------------------------
# Correct patch targets — all are imported into gmail_history_processor module
# ---------------------------------------------------------------------------
_BASE = "core.processors.gmail_history_processor"
_WORKFLOW_SVC = f"{_BASE}.WorkflowService"
_PROCESSED_SVC = f"{_BASE}.ProcessedMessageService"
_DEPLOYMENT_SVC = f"{_BASE}.DeploymentService"
_DB_SESSION = f"{_BASE}.db_session"
_ANYIO = f"{_BASE}.anyio"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch(_ANYIO)
@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
def test_process_message_success_trigger(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    mock_anyio,
    processor,
    mock_service,
):
    """Matching email triggers deployment and creates processed record."""
    message_id = "msg-success-123"
    target_email = "target@example.com"
    target_subject = "Important Alert"

    email_payload = create_email_payload(
        message_id,
        labels=["INBOX", "IMPORTANT"],
        subject=target_subject,
        sender=f"Sender <{target_email}>",
    )
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    matching_workflow = create_mock_workflow(
        active=True, trigger_from=target_email, trigger_subject="Important"
    )

    mock_db = MagicMock()
    mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_db_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_workflow_service.get_by_user_id.return_value = [matching_workflow]
    mock_processed_service.get_by_message_id_and_workflow_id.return_value = None

    processor._process_single_message(message_id)

    mock_processed_service.create.assert_called_once_with(mock_db, message_id, matching_workflow.id)
    mock_anyio.from_thread.run.assert_called_once()
    call_args = mock_anyio.from_thread.run.call_args[0]
    assert call_args[0] == mock_deployment_service.run
    assert call_args[1] == matching_workflow.id


@patch(_DB_SESSION)
def test_process_message_skips_wrong_label(mock_db_session, processor, mock_service):
    """Email not in INBOX returns early — DB never queried."""
    message_id = "msg-skipped-label"
    email_payload = create_email_payload(message_id, labels=["SENT", "IMPORTANT"])
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    processor._process_single_message(message_id)

    mock_db_session.assert_not_called()


@patch(_ANYIO)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
def test_process_message_skips_mismatch_trigger(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_anyio,
    processor,
    mock_service,
):
    """Subject mismatch: no deployment triggered, no processed record created."""
    message_id = "msg-mismatch"
    email_payload = create_email_payload(message_id, subject="Random Newsletter", sender="news@example.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_subject="Urgent")

    mock_db = MagicMock()
    mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_db_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_workflow_service.get_by_user_id.return_value = [workflow]

    processor._process_single_message(message_id)

    mock_anyio.from_thread.run.assert_not_called()
    mock_processed_service.create.assert_not_called()


@patch(_ANYIO)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
def test_process_message_skips_already_processed(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_anyio,
    processor,
    mock_service,
):
    """Message already in ProcessedMessages: skip to avoid duplicate run."""
    message_id = "msg-duplicate"
    email_payload = create_email_payload(message_id, subject="Hello", sender="me@test.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_from="me@test.com")

    mock_db = MagicMock()
    mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_db_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_workflow_service.get_by_user_id.return_value = [workflow]
    mock_processed_service.get_by_message_id_and_workflow_id.return_value = MagicMock()

    processor._process_single_message(message_id)

    mock_anyio.from_thread.run.assert_not_called()
    mock_processed_service.create.assert_not_called()


@patch(_DB_SESSION)
def test_process_message_skips_spam_label(mock_db_session, processor, mock_service):
    """INBOX+SPAM combination returns early — DB never queried."""
    message_id = "msg-spam"
    email_payload = create_email_payload(message_id, labels=["INBOX", "SPAM"])
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    processor._process_single_message(message_id)

    mock_db_session.assert_not_called()


@patch(_ANYIO)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
def test_inactive_workflow_skipped(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_anyio,
    processor,
    mock_service,
):
    """Inactive workflow must not trigger deployment."""
    message_id = "msg-inactive"
    email_payload = create_email_payload(message_id, sender="me@test.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=False)

    mock_db = MagicMock()
    mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_db_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_workflow_service.get_by_user_id.return_value = [workflow]

    processor._process_single_message(message_id)

    mock_anyio.from_thread.run.assert_not_called()
