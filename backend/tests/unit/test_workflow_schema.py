import pytest
from workflow.schemas.workflow_schema import WorkflowExecutionConfig
from workflow.schemas.workflow_nodes import WorkflowNode
from workflow.schemas.edges import Edge
from workflow.schemas.trigger import ManualTrigger, ManualConfig
from workflow.schemas.action import SendEmailAction, SendEmailConfig
from workflow.schemas.condition_nodes import (
    ConditionOperators,
    ConditionRule,
    IfCondition,
    IfConditionConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_trigger(node_id: str) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type="trigger",
        config=ManualTrigger(type="manual", config=ManualConfig()),
    )


def make_action(node_id: str) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type="action",
        config=SendEmailAction(
            type="send_email",
            config=SendEmailConfig(to="test@example.com", subject="Test", body="Test"),
        ),
    )


def make_condition(node_id: str) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type="condition",
        config=IfCondition(
            type="if_condition",
            config=IfConditionConfig(
                rules=[ConditionRule(variable="{{trigger_1.subject}}", operator=ConditionOperators.CONTAINS, value="invoice")],
                match_type="ALL",
            ),
        ),
    )


def make_edge(edge_id: str, source: str, target: str, source_handle: str = None) -> Edge:
    return Edge(id=edge_id, source=source, target=target, sourceHandle=source_handle)


# ---------------------------------------------------------------------------
# Valid workflows
# ---------------------------------------------------------------------------

def test_valid_minimal_workflow():
    config = WorkflowExecutionConfig(
        start_node_ids=["t1"],
        nodes={"t1": make_trigger("t1"), "a1": make_action("a1")},
        edges=[make_edge("e1", "t1", "a1")],
    )
    assert config is not None


def test_valid_workflow_with_condition():
    config = WorkflowExecutionConfig(
        start_node_ids=["t1"],
        nodes={
            "t1": make_trigger("t1"),
            "c1": make_condition("c1"),
            "a_true": make_action("a_true"),
            "a_false": make_action("a_false"),
        },
        edges=[
            make_edge("e1", "t1", "c1"),
            make_edge("e2", "c1", "a_true", source_handle="true_path"),
            make_edge("e3", "c1", "a_false", source_handle="false_path"),
        ],
    )
    assert config is not None


def test_valid_workflow_no_edges_is_rejected():
    # No edges means trigger is isolated → fails minimum requirements
    with pytest.raises(ValueError):
        WorkflowExecutionConfig(
            start_node_ids=["t1"],
            nodes={"t1": make_trigger("t1"), "a1": make_action("a1")},
            edges=[],
        )


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def test_self_loop_raises():
    with pytest.raises(ValueError, match="Circular dependency"):
        WorkflowExecutionConfig(
            start_node_ids=["t1"],
            nodes={"t1": make_trigger("t1"), "a1": make_action("a1")},
            edges=[
                make_edge("e1", "t1", "a1"),
                make_edge("e2", "a1", "a1"),  # self-loop
            ],
        )


def test_two_node_cycle_raises():
    with pytest.raises(ValueError, match="Circular dependency"):
        WorkflowExecutionConfig(
            start_node_ids=["t1"],
            nodes={"t1": make_trigger("t1"), "a1": make_action("a1"), "a2": make_action("a2")},
            edges=[
                make_edge("e1", "t1", "a1"),
                make_edge("e2", "a1", "a2"),
                make_edge("e3", "a2", "a1"),  # back-edge: cycle
            ],
        )


def test_three_node_cycle_raises():
    with pytest.raises(ValueError, match="Circular dependency"):
        WorkflowExecutionConfig(
            start_node_ids=["t1"],
            nodes={
                "t1": make_trigger("t1"),
                "a1": make_action("a1"),
                "a2": make_action("a2"),
                "a3": make_action("a3"),
            },
            edges=[
                make_edge("e1", "t1", "a1"),
                make_edge("e2", "a1", "a2"),
                make_edge("e3", "a2", "a3"),
                make_edge("e4", "a3", "a1"),  # cycle: a1→a2→a3→a1
            ],
        )


# ---------------------------------------------------------------------------
# Minimum requirements validation
# ---------------------------------------------------------------------------

def test_trigger_only_workflow_raises():
    with pytest.raises(ValueError, match="at least one action or condition"):
        WorkflowExecutionConfig(
            start_node_ids=["t1"],
            nodes={"t1": make_trigger("t1")},
            edges=[],
        )


def test_disconnected_trigger_raises():
    # Action exists but trigger has no edges → trigger not connected
    with pytest.raises(ValueError, match="trigger node must be connected"):
        WorkflowExecutionConfig(
            start_node_ids=["t1"],
            nodes={"t1": make_trigger("t1"), "a1": make_action("a1")},
            edges=[],
        )


def test_unreachable_node_raises():
    # a2 not connected to anything — unreachable from trigger
    with pytest.raises(ValueError, match="unreachable"):
        WorkflowExecutionConfig(
            start_node_ids=["t1"],
            nodes={
                "t1": make_trigger("t1"),
                "a1": make_action("a1"),
                "a2": make_action("a2"),  # floating island
            },
            edges=[make_edge("e1", "t1", "a1")],
        )


def test_multiple_start_nodes_valid():
    # Two triggers, both connected to the same action
    t2 = WorkflowNode(
        id="t2",
        type="trigger",
        config=ManualTrigger(type="manual", config=ManualConfig()),
    )
    config = WorkflowExecutionConfig(
        start_node_ids=["t1", "t2"],
        nodes={"t1": make_trigger("t1"), "t2": t2, "a1": make_action("a1")},
        edges=[
            make_edge("e1", "t1", "a1"),
            make_edge("e2", "t2", "a1"),
        ],
    )
    assert len(config.start_node_ids) == 2
