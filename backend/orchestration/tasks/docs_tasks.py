import asyncio
from contextlib import contextmanager
from typing import Any, Dict
from uuid import UUID

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from prefect import task

from auth.scopes import DRIVE_FILE_SCOPE
from auth.services.auth_service import AuthService
from core.database import db_session
from core.setup_logging import setup_logger

logger = setup_logger("Prefect Docs Task")

PROVIDER = "google"

# Only what documents.create needs. drive.file covers files this app created,
# so we never gain read access to the user's other documents.
DEFAULT_SCOPES = [DRIVE_FILE_SCOPE]

RECONNECT_HINT = (
    "Google denied access to Docs. Reconnect your Google account from the "
    "Integrations page to grant document access, then run this workflow again."
)


@contextmanager
def _get_docs_service(user_id: UUID):
    """
    Private helper to handle DB session, credentials, and service building.
    Mirrors gmail_tasks._get_gmail_service — a sync Prefect task can't await, so
    the async credential fetch is bridged with asyncio.run.
    """

    async def _fetch():
        async with db_session() as db:
            return await AuthService.get_google_credentials(
                db, user_id, PROVIDER, DEFAULT_SCOPES
            )

    creds = asyncio.run(_fetch())
    with build("docs", "v1", credentials=creds) as service:
        yield service


def _is_insufficient_scope(error: HttpError) -> bool:
    """A 403 from a grant that predates the drive.file scope.

    Google reports this the same way as any other permission error, so the
    status code plus the reason string is all we have to go on.
    """
    if error.status_code != 403:
        return False

    return "insufficient" in str(error).lower() or "scope" in str(error).lower()


@task(name="Create Google Doc", retries=2, retry_delay_seconds=30, log_prints=True)
def create_document(user_id: UUID, title: str, content: str) -> Dict[str, Any]:
    """
    Create a Google Doc titled `title` containing `content`.

    The Docs API creates an empty document, so the body is inserted with a
    follow-up batchUpdate. Returns the id, title and URL so a downstream node
    can link to the document with {{node_id.document_url}}.
    """
    try:
        with _get_docs_service(user_id) as service:
            document = service.documents().create(body={"title": title}).execute()

            document_id = document.get("documentId")
            if not document_id:
                raise ValueError("Google Docs returned no documentId.")

            if content:
                service.documents().batchUpdate(
                    documentId=document_id,
                    body={
                        "requests": [
                            {
                                # Index 1 is the first position inside the body;
                                # index 0 is before the document start.
                                "insertText": {
                                    "location": {"index": 1},
                                    "text": content,
                                }
                            }
                        ]
                    },
                ).execute()

        logger.info(f"Created Google Doc {document_id}")

        return {
            "document_id": document_id,
            "title": document.get("title", title),
            "document_url": f"https://docs.google.com/document/d/{document_id}/edit",
        }
    except HttpError as error:
        if _is_insufficient_scope(error):
            logger.error(f"Docs access denied for user {user_id}: {error}")
            raise PermissionError(RECONNECT_HINT) from error

        logger.error(f"Http error occurred: \n {error}")
        raise error
    except Exception as error:
        logger.error(f"Unhandled error: {error}")
        raise error
