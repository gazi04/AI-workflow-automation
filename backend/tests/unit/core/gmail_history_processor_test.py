import base64

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from core.processors import GmailHistoryProcessor
from core.processors.gmail_history_processor import DeploymentTriggerError


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


def _mock_db_session_ctx(mock_db_session):
    """Make a patched (MagicMock-replaced) `db_session` behave like the real
    async context manager: `async with db_session() as db: ...`."""
    mock_db = MagicMock()
    mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_process_message_success_trigger(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
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

    mock_db = _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[matching_workflow])
    mock_processed_service.get_by_message_id_and_workflow_id = AsyncMock(return_value=None)

    # The record must be created only AFTER the deployment is triggered.
    order = []

    async def fake_run(*a, **k):
        order.append("trigger")

    async def fake_create(*a, **k):
        order.append("create")

    mock_deployment_service.run = AsyncMock(side_effect=fake_run)
    mock_processed_service.create = AsyncMock(side_effect=fake_create)

    await processor._process_single_message(message_id)

    mock_processed_service.create.assert_called_once_with(mock_db, message_id, matching_workflow.id)
    mock_deployment_service.run.assert_called_once()
    call_args = mock_deployment_service.run.call_args[0]
    assert call_args[0] == matching_workflow.id
    assert order == ["trigger", "create"]


# ---------------------------------------------------------------------------
# fetch_and_process — pagination (2.4)
# ---------------------------------------------------------------------------

def _page(message_ids, next_token=None):
    page = {
        "history": [
            {"messagesAdded": [{"message": {"id": mid}}]} for mid in message_ids
        ]
    }
    if next_token:
        page["nextPageToken"] = next_token
    return page


def _set_history_pages(mock_service, pages):
    mock_service.users.return_value.history.return_value.list.return_value.execute.side_effect = pages


def _list_call_tokens(mock_service):
    list_mock = mock_service.users.return_value.history.return_value.list
    return [c.kwargs.get("pageToken") for c in list_mock.call_args_list]


@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_fetch_processes_all_pages(mock_db_session, mock_workflow_service, processor, mock_service):
    """Messages beyond the first page must still be processed."""
    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[])
    _set_history_pages(mock_service, [_page(["m1"], "t2"), _page(["m2"])])
    processor._process_single_message = AsyncMock()

    await processor.fetch_and_process("100")

    processed = {c.args[0] for c in processor._process_single_message.call_args_list}
    assert processed == {"m1", "m2"}
    # paged twice: first with no token, then with the nextPageToken
    assert _list_call_tokens(mock_service) == [None, "t2"]


@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_fetch_single_page_stops(mock_db_session, mock_workflow_service, processor, mock_service):
    """No nextPageToken → exactly one history.list call."""
    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[])
    _set_history_pages(mock_service, [_page(["m1"])])
    processor._process_single_message = AsyncMock()

    await processor.fetch_and_process("100")

    assert _list_call_tokens(mock_service) == [None]
    processor._process_single_message.assert_called_once_with("m1", [])


@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_fetch_dedups_message_ids_across_pages(mock_db_session, mock_workflow_service, processor, mock_service):
    """A message id repeated across pages is processed once."""
    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[])
    _set_history_pages(mock_service, [_page(["m1"], "t2"), _page(["m1", "m2"])])
    processor._process_single_message = AsyncMock()

    await processor.fetch_and_process("100")

    processed = [c.args[0] for c in processor._process_single_message.call_args_list]
    assert sorted(processed) == ["m1", "m2"]


async def test_fetch_empty_history_processes_nothing(processor, mock_service):
    _set_history_pages(mock_service, [_page([])])
    processor._process_single_message = AsyncMock()

    await processor.fetch_and_process("100")

    processor._process_single_message.assert_not_called()


@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_fetch_empty_history_never_queries_workflows(mock_db_session, mock_workflow_service, processor, mock_service):
    """No messages in the batch → the workflow cache query is skipped entirely."""
    _set_history_pages(mock_service, [_page([])])
    processor._process_single_message = AsyncMock()

    await processor.fetch_and_process("100")

    mock_db_session.assert_not_called()
    mock_workflow_service.get_by_user_id.assert_not_called()


@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_fetch_builds_workflow_cache_once_for_many_messages(mock_db_session, mock_workflow_service, processor, mock_service):
    """N messages in one batch must fetch+validate the workflow list only once,
    and every _process_single_message call must reuse the same cached list."""
    _mock_db_session_ctx(mock_db_session)
    workflow = create_mock_workflow(active=True, trigger_from="me@test.com")
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    _set_history_pages(mock_service, [_page(["m1", "m2", "m3"])])
    processor._process_single_message = AsyncMock()

    await processor.fetch_and_process("100")

    mock_workflow_service.get_by_user_id.assert_called_once()
    passed_caches = [c.args[1] for c in processor._process_single_message.call_args_list]
    assert len(passed_caches) == 3
    assert all(cache is passed_caches[0] for cache in passed_caches)
    assert passed_caches[0][0][0] is workflow


@patch(_DB_SESSION)
async def test_process_message_skips_wrong_label(mock_db_session, processor, mock_service):
    """Email not in INBOX returns early — DB never queried."""
    message_id = "msg-skipped-label"
    email_payload = create_email_payload(message_id, labels=["SENT", "IMPORTANT"])
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    await processor._process_single_message(message_id)

    mock_db_session.assert_not_called()


@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_process_message_skips_mismatch_trigger(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    processor,
    mock_service,
):
    """Subject mismatch: no deployment triggered, no processed record created."""
    message_id = "msg-mismatch"
    email_payload = create_email_payload(message_id, subject="Random Newsletter", sender="news@example.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_subject="Urgent")

    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    mock_deployment_service.run = AsyncMock()
    mock_processed_service.create = AsyncMock()

    await processor._process_single_message(message_id)

    mock_deployment_service.run.assert_not_called()
    mock_processed_service.create.assert_not_called()


@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_process_message_from_email_is_not_substring_matched(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    processor,
    mock_service,
):
    """A from_email that is a substring of the sender must NOT match:
    trigger 'o.com' should not fire on 'john@example.com'."""
    message_id = "msg-substring"
    email_payload = create_email_payload(
        message_id, subject="Hello", sender="John <john@example.com>"
    )
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_from="o.com")

    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    mock_deployment_service.run = AsyncMock()
    mock_processed_service.create = AsyncMock()

    await processor._process_single_message(message_id)

    mock_deployment_service.run.assert_not_called()
    mock_processed_service.create.assert_not_called()


@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_process_message_from_email_matches_address_inside_display_name(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    processor,
    mock_service,
):
    """Exact address match still works when the header is 'Name <addr>'."""
    message_id = "msg-display-name"
    email_payload = create_email_payload(
        message_id, subject="Hello", sender="Alice Example <alice@example.com>"
    )
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_from="alice@example.com")

    mock_db = _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    mock_processed_service.get_by_message_id_and_workflow_id = AsyncMock(return_value=None)
    mock_deployment_service.run = AsyncMock()
    mock_processed_service.create = AsyncMock()

    await processor._process_single_message(message_id)

    mock_deployment_service.run.assert_called_once()
    mock_processed_service.create.assert_called_once_with(
        mock_db, message_id, workflow.id
    )


@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_process_message_skips_already_processed(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    processor,
    mock_service,
):
    """Message already in ProcessedMessages: skip to avoid duplicate run."""
    message_id = "msg-duplicate"
    email_payload = create_email_payload(message_id, subject="Hello", sender="me@test.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_from="me@test.com")

    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    mock_processed_service.get_by_message_id_and_workflow_id = AsyncMock(return_value=MagicMock())
    mock_deployment_service.run = AsyncMock()
    mock_processed_service.create = AsyncMock()

    await processor._process_single_message(message_id)

    mock_deployment_service.run.assert_not_called()
    mock_processed_service.create.assert_not_called()


@patch(_DB_SESSION)
async def test_process_message_skips_spam_label(mock_db_session, processor, mock_service):
    """INBOX+SPAM combination returns early — DB never queried."""
    message_id = "msg-spam"
    email_payload = create_email_payload(message_id, labels=["INBOX", "SPAM"])
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    await processor._process_single_message(message_id)

    mock_db_session.assert_not_called()


@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_inactive_workflow_skipped(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    processor,
    mock_service,
):
    """Inactive workflow must not trigger deployment."""
    message_id = "msg-inactive"
    email_payload = create_email_payload(message_id, sender="me@test.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=False)

    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    mock_deployment_service.run = AsyncMock()

    await processor._process_single_message(message_id)

    mock_deployment_service.run.assert_not_called()


# ---------------------------------------------------------------------------
# 2.7 — processed-after-trigger ordering, retry on failure, dedup race
# ---------------------------------------------------------------------------

@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_trigger_failure_does_not_create_record_and_flags_batch(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    processor,
    mock_service,
):
    """A failed deployment trigger must NOT mark the message processed, and must
    flag the batch so the baseline is later withheld for retry."""
    message_id = "msg-trigger-fails"
    email_payload = create_email_payload(message_id, sender="me@test.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_from="me@test.com")

    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    mock_processed_service.get_by_message_id_and_workflow_id = AsyncMock(return_value=None)
    mock_processed_service.create = AsyncMock()

    mock_deployment_service.run = AsyncMock(side_effect=RuntimeError("prefect down"))

    await processor._process_single_message(message_id)

    mock_processed_service.create.assert_not_called()
    assert processor._trigger_failed is True


@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_fetch_raises_when_a_trigger_failed(mock_db_session, mock_workflow_service, processor, mock_service):
    """fetch_and_process surfaces a DeploymentTriggerError so the drain loop
    withholds the baseline advance and retries next pass."""
    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[])
    _set_history_pages(mock_service, [_page(["m1"])])

    async def fake_process(_mid, _active_workflows=None):
        processor._trigger_failed = True

    processor._process_single_message = fake_process

    with pytest.raises(DeploymentTriggerError):
        await processor.fetch_and_process("100")


@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_fetch_does_not_raise_when_all_triggers_succeed(mock_db_session, mock_workflow_service, processor, mock_service):
    """No failure flag → fetch_and_process returns cleanly (baseline advances)."""
    _mock_db_session_ctx(mock_db_session)
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[])
    _set_history_pages(mock_service, [_page(["m1", "m2"])])
    processor._process_single_message = AsyncMock()

    await processor.fetch_and_process("100")  # must not raise


@patch(_DEPLOYMENT_SVC)
@patch(_PROCESSED_SVC)
@patch(_WORKFLOW_SVC)
@patch(_DB_SESSION)
async def test_create_integrity_error_is_swallowed(
    mock_db_session,
    mock_workflow_service,
    mock_processed_service,
    mock_deployment_service,
    processor,
    mock_service,
):
    """A concurrent insert (IntegrityError on create) is treated as already
    handled — it must not propagate or flag the batch as failed."""
    message_id = "msg-dup-insert"
    email_payload = create_email_payload(message_id, sender="me@test.com")
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = email_payload

    workflow = create_mock_workflow(active=True, trigger_from="me@test.com")

    mock_db = _mock_db_session_ctx(mock_db_session)
    mock_db.rollback = AsyncMock()
    mock_workflow_service.get_by_user_id = AsyncMock(return_value=[workflow])
    mock_processed_service.get_by_message_id_and_workflow_id = AsyncMock(return_value=None)
    mock_processed_service.create = AsyncMock(
        side_effect=IntegrityError("stmt", {}, Exception("dup"))
    )
    mock_deployment_service.run = AsyncMock()

    processor._trigger_failed = False
    await processor._process_single_message(message_id)  # must not raise

    mock_deployment_service.run.assert_called_once()
    mock_db.rollback.assert_called_once()
    assert processor._trigger_failed is False


# ---------------------------------------------------------------------------
# _get_email_body decoding
# ---------------------------------------------------------------------------


def _text_part(raw_bytes: bytes):
    from gmail.schemas.message import GmailMessagePart, GmailMessagePartBody

    return GmailMessagePart(
        partId="0",
        mimeType="text/plain",
        body=GmailMessagePartBody(
            size=len(raw_bytes),
            data=base64.urlsafe_b64encode(raw_bytes).decode("ascii"),
        ),
    )


def test_get_email_body_non_utf8_does_not_crash(processor):
    # "café" in latin-1 is not valid UTF-8 — must not raise, lossy decode is fine.
    part = _text_part("café".encode("latin-1"))

    body = processor._get_email_body(part)

    assert isinstance(body, str)
    assert "caf" in body


def test_get_email_body_utf8_round_trips(processor):
    part = _text_part("héllo 🌍".encode("utf-8"))

    assert processor._get_email_body(part) == "héllo 🌍"
