from auth.models.connected_account import ConnectedAccount
from user.models.user_settings import UserSettings


def test_notification_preferences_default_is_callable():
    """Regression: the JSONB default must be a callable so every insert gets a
    fresh dict — a shared literal dict is a mutable-default footgun (ruff B006)."""
    default = UserSettings.__table__.c.notification_preferences.default
    assert default is not None
    assert default.is_callable
    # SQLAlchemy wraps the zero-arg default to accept an execution context.
    assert default.arg(None) == {"email": True, "slack": False}


def test_metadata_account_default_is_callable():
    default = ConnectedAccount.__table__.c.metadata_account.default
    assert default is not None
    assert default.is_callable
