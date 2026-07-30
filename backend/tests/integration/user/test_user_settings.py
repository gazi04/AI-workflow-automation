async def test_get_settings_requires_auth(client):
    response = await client.get("/api/user/settings")
    assert response.status_code == 401


async def test_get_settings_creates_defaults(client, auth_headers):
    """First read auto-creates a default settings row."""
    response = await client.get("/api/user/settings", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "UTC"
    assert body["default_llm_provider"] == "deepseek"
    assert body["notification_preferences"] == {"email": True, "slack": False}


async def test_patch_settings_partial_update_preserves_rest(client, auth_headers):
    """A partial PATCH updates only the provided fields."""
    # Seed defaults.
    await client.get("/api/user/settings", headers=auth_headers)

    response = await client.patch(
        "/api/user/settings",
        json={"timezone": "Europe/Berlin"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Europe/Berlin"
    # Untouched fields keep their defaults.
    assert body["default_llm_provider"] == "deepseek"
    assert body["notification_preferences"] == {"email": True, "slack": False}


async def test_patch_settings_updates_notification_prefs(client, auth_headers):
    response = await client.patch(
        "/api/user/settings",
        json={"notification_preferences": {"email": False, "slack": True}},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["notification_preferences"] == {
        "email": False,
        "slack": True,
    }


async def test_patch_settings_requires_auth(client, csrf_headers):
    response = await client.patch(
        "/api/user/settings", json={"timezone": "UTC"}, headers=csrf_headers
    )
    assert response.status_code == 401
