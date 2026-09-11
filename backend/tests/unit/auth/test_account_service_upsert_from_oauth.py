"""Unit tests for AccountService.upsert_from_oauth.

New business logic introduced by the callback_google refactor (previously
inlined in the router). Covers the create-vs-update branch, the
falsy-refresh-token-preserved rule, and the two opt-in flags
(mark_connected, update_metadata_on_existing) that let Google and a future
Slack caller share this method without silently changing either's behavior.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from auth.models.connected_account import ConnectedAccount
from auth.services.account_service import AccountService


def _db():
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _patch_deps(existing_account):
    account_service_get = AsyncMock(return_value=existing_account)
    return (
        patch(
            "auth.services.account_service.AccountService.get_account_by_user_and_provider",
            account_service_get,
        ),
        patch(
            "auth.services.account_service.encrypt_token",
            side_effect=lambda t: f"encrypted:{t}" if t else None,
        ),
        account_service_get,
    )


async def test_creates_new_account_when_none_exists():
    db = _db()
    p_get, p_encrypt, get_mock = _patch_deps(None)
    user_id = uuid4()

    with p_get, p_encrypt:
        account = await AccountService.upsert_from_oauth(
            db,
            user_id=user_id,
            provider="google",
            provider_account_id="sub-1",
            access_token="tok",
            refresh_token="reftok",
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="openid email",
            metadata_account={"email": "a@example.com"},
        )

    db.add.assert_called_once()
    added = db.add.call_args.args[0]
    assert isinstance(added, ConnectedAccount)
    assert added.user_id == user_id
    assert added.provider == "google"
    assert added.provider_account_id == "sub-1"
    assert added.metadata_account == {"email": "a@example.com"}
    assert account.access_token == "encrypted:tok"
    assert account.refresh_token == "encrypted:reftok"
    assert account.scope == "openid email"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()
    get_mock.assert_awaited_once_with(db, user_id, "google")


async def test_updates_existing_account_without_touching_identity_fields():
    existing = MagicMock()
    existing.provider_account_id = "old-id"
    existing.metadata_account = {"x": 1}
    existing.refresh_token = "old-encrypted-refresh"
    existing.is_connected = False
    p_get, p_encrypt, _ = _patch_deps(existing)
    db = _db()

    with p_get, p_encrypt:
        await AccountService.upsert_from_oauth(
            db,
            user_id=uuid4(),
            provider="google",
            provider_account_id="new-id",
            access_token="new-tok",
            refresh_token="new-reftok",
            token_expires_at=None,
            scope="openid",
            metadata_account={"y": 2},
        )

    db.add.assert_not_called()
    assert existing.access_token == "encrypted:new-tok"
    assert existing.refresh_token == "encrypted:new-reftok"
    # update_metadata_on_existing defaults False — identity fields untouched.
    assert existing.provider_account_id == "old-id"
    assert existing.metadata_account == {"x": 1}


async def test_falsy_refresh_token_preserves_existing_one_on_update():
    existing = MagicMock()
    existing.refresh_token = "old-encrypted-refresh"
    p_get, p_encrypt, _ = _patch_deps(existing)
    db = _db()

    with p_get, p_encrypt:
        await AccountService.upsert_from_oauth(
            db,
            user_id=uuid4(),
            provider="google",
            provider_account_id="id",
            access_token="new-tok",
            refresh_token=None,
            token_expires_at=None,
            scope=None,
        )

    assert existing.refresh_token == "old-encrypted-refresh"


async def test_mark_connected_false_by_default_leaves_is_connected_untouched():
    existing = MagicMock()
    existing.is_connected = False
    p_get, p_encrypt, _ = _patch_deps(existing)
    db = _db()

    with p_get, p_encrypt:
        await AccountService.upsert_from_oauth(
            db,
            user_id=uuid4(),
            provider="google",
            provider_account_id="id",
            access_token="tok",
            refresh_token="reftok",
            token_expires_at=None,
            scope=None,
        )

    assert existing.is_connected is False


async def test_mark_connected_true_forces_is_connected_true():
    existing = MagicMock()
    existing.is_connected = False
    p_get, p_encrypt, _ = _patch_deps(existing)
    db = _db()

    with p_get, p_encrypt:
        await AccountService.upsert_from_oauth(
            db,
            user_id=uuid4(),
            provider="google",
            provider_account_id="id",
            access_token="tok",
            refresh_token="reftok",
            token_expires_at=None,
            scope=None,
            mark_connected=True,
        )

    assert existing.is_connected is True


async def test_update_metadata_on_existing_true_refreshes_identity_fields():
    existing = MagicMock()
    existing.provider_account_id = "old-id"
    existing.metadata_account = {"x": 1}
    p_get, p_encrypt, _ = _patch_deps(existing)
    db = _db()

    with p_get, p_encrypt:
        await AccountService.upsert_from_oauth(
            db,
            user_id=uuid4(),
            provider="slack",
            provider_account_id="new-id",
            access_token="tok",
            refresh_token=None,
            token_expires_at=None,
            scope=None,
            metadata_account={"y": 2},
            update_metadata_on_existing=True,
        )

    assert existing.provider_account_id == "new-id"
    assert existing.metadata_account == {"y": 2}
