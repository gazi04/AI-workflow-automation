from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

from gmail.schemas.label import GmailLabel
from orchestration.tasks.gmail_tasks import label_mail


def _build_service(modify_result, existing_labels):
    """A mock Gmail service whose chained calls resolve to the given results."""
    service = MagicMock()
    users = service.users.return_value

    users.labels.return_value.list.return_value.execute.return_value = {
        "labels": existing_labels
    }
    users.messages.return_value.modify.return_value.execute.return_value = modify_result
    return service


@contextmanager
def _fake_gmail_service(service):
    yield service, MagicMock()


def test_label_mail_returns_modify_result_not_label_list():
    modify_result = {"id": "m1", "threadId": "t1", "labelIds": ["L1", "INBOX"]}
    existing_labels = [{"id": "L1", "name": "Important"}]
    service = _build_service(modify_result, existing_labels)

    with patch(
        "orchestration.tasks.gmail_tasks._get_gmail_service",
        return_value=_fake_gmail_service(service),
    ):
        result = label_mail.fn(
            user_id=uuid4(),
            label_info=GmailLabel(name="Important"),
            original_email={"message_id": "m1"},
        )

    # The node output must be the modify result, never the full label list.
    assert result == modify_result
    assert result != existing_labels
    # Existing label was reused; no create call.
    service.users.return_value.labels.return_value.create.assert_not_called()
