from typing import get_args

from gmail.schemas.colors import GmailBackgroundHex, GmailTextHex
from core.config_loader import settings
from utils.catalog_introspector import build_catalog
from workflow.schemas.action import Action
from workflow.schemas.condition_nodes import Condition
from workflow.schemas.trigger import Trigger


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


def test_label_email_color_fields_offer_the_gmail_palette():
    """background_color and text_color are Literals, so the catalog must render them as
    a select with the palette as options — a free-text widget is how off-palette colors
    used to reach the executor and blow up the node at run time."""
    catalog = build_catalog()
    label_email = next(a for a in catalog.actions if a.type == "label_email")
    fields = {f.key: f for f in label_email.fields}

    assert fields["background_color"].type == "select"
    assert fields["background_color"].options == list(get_args(GmailBackgroundHex))
    assert fields["text_color"].type == "select"
    assert fields["text_color"].options == list(get_args(GmailTextHex))


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
        "webhook",
    } == types


def test_coming_soon_triggers_gated():
    """new_sheet_row has no executor — nothing polls Sheets — so a workflow built
    on it deploys and then silently never fires. Gated out of the catalog."""
    catalog = build_catalog()
    types = {t.type for t in catalog.triggers}
    assert "new_sheet_row" not in types


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
    assert "create_document" in types
    assert "send_slack_message" in types


def test_create_document_exposes_document_url_output():
    """Downstream nodes link to the doc with {{node_id.document_url}}."""
    catalog = build_catalog()
    create_doc = next(a for a in catalog.actions if a.type == "create_document")
    assert create_doc.category == "Google"
    assert create_doc.outputs == ["document_id", "title", "document_url"]
    assert {f.key for f in create_doc.fields} == {"title", "content"}


def test_send_slack_message_action_metadata():
    """Downstream nodes reference the posted message with {{node_id.ts}}."""
    catalog = build_catalog()
    slack = next(a for a in catalog.actions if a.type == "send_slack_message")
    assert slack.category == "Communication"
    assert slack.icon == "lucide-slack"
    assert slack.outputs == ["channel", "ts"]
    assert {f.key for f in slack.fields} == {"channel", "message"}


def test_no_coming_soon_action_leaks_into_catalog():
    """Any Action union member tagged status='coming_soon' must stay out of the
    catalog. Currently there are none — this guards the gate mechanism itself."""
    catalog = build_catalog()
    catalog_types = {a.type for a in catalog.actions}
    for cls in get_args(get_args(Action)[0]):
        extra = cls.model_config.get("json_schema_extra", {})
        if extra.get("status") == "coming_soon":
            node_type = get_args(cls.model_fields["type"].annotation)[0]
            assert node_type not in catalog_types


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


# ---------------------------------------------------------------------------
# The AI generator is a second, non-catalog way to create nodes
# ---------------------------------------------------------------------------


def _coming_soon_types() -> set[str]:
    """Every node type tagged status='coming_soon', straight from the unions."""
    gated = set()
    for union in (Trigger, Action, Condition):
        members = get_args(get_args(union)[0]) or [get_args(union)[0]]
        for cls in members:
            extra = cls.model_config.get("json_schema_extra", {})
            if extra.get("status") == "coming_soon":
                gated.add(get_args(cls.model_fields["type"].annotation)[0])
    return gated


def test_ai_prompt_does_not_advertise_gated_nodes():
    """The catalog gate only closes the editor palette. The AI planner has its own
    hardcoded allow-list, so a gated type left in the system prompt still reaches
    NodeConfig — which validates it — and produces a workflow that cannot run."""
    prompt = settings.system_prompt
    for node_type in _coming_soon_types():
        assert node_type not in prompt, (
            f"'{node_type}' is gated as coming_soon but the AI system prompt "
            "still advertises it"
        )


def test_ai_prompt_advertises_ungated_send_slack_message():
    """Ungating an action does not add it to the planner's allow-list — the
    system prompt is that list. Without this line the AI can never emit it."""
    assert "send_slack_message" in settings.system_prompt
