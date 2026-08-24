from typing import get_args

import pytest

from workflow.schemas.templates import (
    WORKFLOW_TEMPLATES,
    get_template,
    list_templates,
)
from workflow.schemas.workflow_nodes import NodeConfig

# Node types master_flow.py can actually run today. A seed built on anything
# else deploys and then silently never fires — the failure mode documented as
# whats_left.md #3 for NewSheetRowTrigger.
EXECUTABLE_TRIGGERS = {"email_received", "schedule", "manual", "webhook"}
EXECUTABLE_ACTIONS = {"send_email", "reply_email", "label_email", "smart_draft"}
EXECUTABLE_CONDITIONS = {"if_condition"}

# master_flow.py:96 — these hard-fail unless the run carries email trigger context.
EMAIL_DEPENDENT_ACTIONS = {"reply_email", "label_email", "smart_draft"}


def _node_classes_by_type():
    """Map each concrete `type` literal to its Pydantic class from the union."""
    union = get_args(NodeConfig)[0]
    return {
        get_args(cls.model_fields["type"].annotation)[0]: cls for cls in get_args(union)
    }


NODE_CLASSES = _node_classes_by_type()

ALL_TEMPLATES = list_templates()
TEMPLATE_IDS = [template.id for template in ALL_TEMPLATES]


def test_templates_are_registered():
    assert ALL_TEMPLATES, "No workflow templates registered."
    assert len(TEMPLATE_IDS) == len(set(TEMPLATE_IDS)), "Duplicate template ids."
    assert set(WORKFLOW_TEMPLATES) == set(TEMPLATE_IDS)


def test_get_template_unknown_id_returns_none():
    assert get_template("does_not_exist") is None


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_template_lands_paused(template):
    assert template.definition.is_active is False


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_template_start_nodes_exist_and_are_triggers(template):
    """`WorkflowExecutionConfig` validates neither of these."""
    config = template.definition.execution_config
    for start_id in config.start_node_ids:
        assert start_id in config.nodes, f"start node '{start_id}' is not in nodes"
        assert config.nodes[start_id].type == "trigger"


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_template_node_ids_match_their_keys(template):
    for node_id, node in template.definition.execution_config.nodes.items():
        assert node.id == node_id


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_template_edges_reference_known_nodes(template):
    config = template.definition.execution_config
    for edge in config.edges:
        assert edge.source in config.nodes, f"edge '{edge.id}' has unknown source"
        assert edge.target in config.nodes, f"edge '{edge.id}' has unknown target"


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_template_uses_no_coming_soon_nodes(template):
    """The catalog gates `coming_soon` types out of the editor palette
    (catalog_introspector.py), but WorkflowSchema still accepts them."""
    for node in template.definition.execution_config.nodes.values():
        node_class = NODE_CLASSES[node.config.type]
        extra = node_class.model_config.get("json_schema_extra") or {}
        assert extra.get("status") != "coming_soon", (
            f"template '{template.id}' uses coming_soon node '{node.config.type}'"
        )


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_template_nodes_are_executable(template):
    executable = {
        "trigger": EXECUTABLE_TRIGGERS,
        "action": EXECUTABLE_ACTIONS,
        "condition": EXECUTABLE_CONDITIONS,
    }
    for node in template.definition.execution_config.nodes.values():
        assert node.config.type in executable[node.type], (
            f"template '{template.id}' uses '{node.config.type}', "
            "which master_flow.py cannot execute"
        )


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_email_dependent_actions_start_from_an_email_trigger(template):
    config = template.definition.execution_config
    uses_email_action = any(
        node.config.type in EMAIL_DEPENDENT_ACTIONS for node in config.nodes.values()
    )
    if not uses_email_action:
        pytest.skip("no email-dependent actions")

    trigger_types = {
        config.nodes[node_id].config.type for node_id in config.start_node_ids
    }
    assert trigger_types == {"email_received"}, (
        f"template '{template.id}' uses an email-dependent action but does not "
        "start from an email_received trigger"
    )


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=TEMPLATE_IDS)
def test_template_has_gallery_metadata(template):
    assert template.name and template.description and template.category
    assert template.icon.startswith("lucide-")
    assert template.steps
    assert template.summary().id == template.id
