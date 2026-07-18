from utils.catalog_introspector import build_catalog


def test_build_catalog_returns_triggers_and_actions():
    catalog = build_catalog()
    assert len(catalog.triggers) > 0
    assert len(catalog.actions) > 0


def test_build_catalog_is_cached():
    """build_catalog() is static per process — repeated calls must return the
    same cached instance instead of re-introspecting every time."""
    assert build_catalog() is build_catalog()


def test_email_trigger_has_correct_metadata():
    catalog = build_catalog()
    email_trigger = next(t for t in catalog.triggers if t.type == "email_received")
    assert email_trigger.category == "Communication"


def test_email_trigger_uses_field_alias():
    """from_email has alias='from' — the catalog key must use the alias."""
    catalog = build_catalog()
    email_trigger = next(t for t in catalog.triggers if t.type == "email_received")
    field_keys = [f.key for f in email_trigger.fields]
    assert "from" in field_keys


def test_manual_trigger_fields_are_not_required():
    catalog = build_catalog()
    manual_trigger = next(t for t in catalog.triggers if t.type == "manual")
    for field in manual_trigger.fields:
        assert not field.required


def test_schedule_trigger_has_cron_field():
    catalog = build_catalog()
    schedule_trigger = next(t for t in catalog.triggers if t.type == "schedule")
    field_keys = [f.key for f in schedule_trigger.fields]
    assert "cron" in field_keys


def test_schedule_cron_uses_cron_widget():
    """ScheduleConfig.cron declares widget='cron' — drives the dedicated UI."""
    catalog = build_catalog()
    schedule_trigger = next(t for t in catalog.triggers if t.type == "schedule")
    cron_field = next(f for f in schedule_trigger.fields if f.key == "cron")
    assert cron_field.type == "cron"
    assert cron_field.required


def test_schedule_description_is_optional():
    """description now has a default, so only cron is required on a schedule node."""
    catalog = build_catalog()
    schedule_trigger = next(t for t in catalog.triggers if t.type == "schedule")
    description_field = next(
        f for f in schedule_trigger.fields if f.key == "description"
    )
    assert not description_field.required


def test_send_email_action_maps_email_type():
    """The `to` field on SendEmailConfig is EmailStr — must map to 'email' widget."""
    catalog = build_catalog()
    send_email = next(a for a in catalog.actions if a.type == "send_email")
    to_field = next(f for f in send_email.fields if f.key == "to")
    assert to_field.type == "email"


def test_label_email_action_has_label_name_field():
    """LabelEmailConfig exposes label_name, background_color, text_color fields."""
    catalog = build_catalog()
    label_email = next(a for a in catalog.actions if a.type == "label_email")
    field_keys = [f.key for f in label_email.fields]
    assert "label_name" in field_keys


def test_label_email_color_fields_use_color_widget():
    """background_color and text_color declare widget='color' in json_schema_extra."""
    catalog = build_catalog()
    label_email = next(a for a in catalog.actions if a.type == "label_email")
    color_fields = [
        f for f in label_email.fields if f.key in ("background_color", "text_color")
    ]
    assert len(color_fields) == 2
    for field in color_fields:
        assert field.type == "color"


def test_all_nodes_have_category():
    catalog = build_catalog()
    for node in catalog.triggers + catalog.actions:
        assert node.category, f"Node '{node.type}' is missing a category"


# ---------------------------------------------------------------------------
# Trigger coverage
# ---------------------------------------------------------------------------


def test_all_trigger_types_present():
    catalog = build_catalog()
    types = {t.type for t in catalog.triggers}
    assert {
        "email_received",
        "manual",
        "schedule",
        "new_sheet_row",
        "webhook",
    } == types


def test_webhook_trigger_has_correct_metadata():
    """The generic webhook trigger exposes the posted payload as node outputs."""
    catalog = build_catalog()
    webhook = next(t for t in catalog.triggers if t.type == "webhook")
    assert webhook.category == "Developer"
    assert webhook.outputs == ["body", "headers", "query"]


# ---------------------------------------------------------------------------
# Action coverage
# ---------------------------------------------------------------------------


def test_all_action_types_present():
    catalog = build_catalog()
    types = {a.type for a in catalog.actions}
    assert "send_email" in types
    assert "reply_email" in types
    assert "label_email" in types
    assert "smart_draft" in types


def test_coming_soon_actions_gated():
    """Stub actions tagged status='coming_soon' must be excluded from the catalog."""
    catalog = build_catalog()
    types = {a.type for a in catalog.actions}
    assert "send_slack_message" not in types
    assert "create_document" not in types


def test_smart_draft_action_in_catalog():
    catalog = build_catalog()
    smart = next((a for a in catalog.actions if a.type == "smart_draft"), None)
    assert smart is not None
    assert smart.category == "AI"


def test_reply_email_action_has_body_field():
    catalog = build_catalog()
    reply = next(a for a in catalog.actions if a.type == "reply_email")
    field_keys = [f.key for f in reply.fields]
    assert "body" in field_keys


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


def test_conditions_catalog_has_if_condition():
    catalog = build_catalog()
    assert any(c.type == "if_condition" for c in catalog.conditions)
