from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from googleapiclient.errors import HttpError

from orchestration.tasks.docs_tasks import RECONNECT_HINT, create_document


def _build_service(document_id="doc-1", title="Meeting notes"):
    """A mock Docs service whose chained calls resolve to a created document."""
    service = MagicMock()
    documents = service.documents.return_value
    documents.create.return_value.execute.return_value = {
        "documentId": document_id,
        "title": title,
    }
    documents.batchUpdate.return_value.execute.return_value = {
        "documentId": document_id
    }
    return service


@contextmanager
def _fake_docs_service(service):
    yield service


def _http_error(status: int, reason: bytes) -> HttpError:
    response = MagicMock()
    response.status = status
    response.reason = reason.decode()
    return HttpError(resp=response, content=reason)


def _run(service, **kwargs):
    with patch(
        "orchestration.tasks.docs_tasks._get_docs_service",
        return_value=_fake_docs_service(service),
    ):
        return create_document.fn(user_id=uuid4(), **kwargs)


def test_create_document_returns_id_title_and_url():
    service = _build_service()

    result = _run(service, title="Meeting notes", content="Agenda")

    assert result == {
        "document_id": "doc-1",
        "title": "Meeting notes",
        "document_url": "https://docs.google.com/document/d/doc-1/edit",
    }
    service.documents.return_value.create.assert_called_once_with(
        body={"title": "Meeting notes"}
    )


def test_create_document_inserts_content_at_body_start():
    """Index 1 is the first position inside the body; index 0 is before it."""
    service = _build_service()

    _run(service, title="Notes", content="Hello world")

    _, kwargs = service.documents.return_value.batchUpdate.call_args
    assert kwargs["documentId"] == "doc-1"
    assert kwargs["body"]["requests"] == [
        {"insertText": {"location": {"index": 1}, "text": "Hello world"}}
    ]


def test_create_document_skips_batch_update_when_content_empty():
    service = _build_service()

    result = _run(service, title="Empty", content="")

    service.documents.return_value.batchUpdate.assert_not_called()
    assert result["document_id"] == "doc-1"


def test_create_document_raises_when_no_document_id_returned():
    service = _build_service()
    service.documents.return_value.create.return_value.execute.return_value = {}

    with pytest.raises(ValueError, match="documentId"):
        _run(service, title="Notes", content="Body")


def test_insufficient_scope_error_tells_the_user_to_reconnect():
    """A grant predating the drive.file scope fails with a 403 that the credential
    layer never sees — the node's error must name the fix."""
    service = _build_service()
    service.documents.return_value.create.return_value.execute.side_effect = (
        _http_error(403, b"Request had insufficient authentication scopes.")
    )

    with pytest.raises(PermissionError) as excinfo:
        _run(service, title="Notes", content="Body")

    assert str(excinfo.value) == RECONNECT_HINT


def test_other_http_errors_are_reraised_untouched():
    service = _build_service()
    error = _http_error(500, b"Backend error")
    service.documents.return_value.create.return_value.execute.side_effect = error

    with pytest.raises(HttpError):
        _run(service, title="Notes", content="Body")
