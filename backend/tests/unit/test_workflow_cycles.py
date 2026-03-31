import pytest
from pydantic import ValidationError
from workflow.schemas.workflow_definition import WorkflowDefinition
from workflow.schemas.workflow_nodes import WorkflowNode
from workflow.schemas.edges import Edge
from workflow.schemas.trigger import ManualTrigger, ManualConfig

def create_mock_node(node_id: str) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        name=f"Node {node_id}",
        type="trigger",
        config=ManualTrigger(type="manual", config=ManualConfig())
    )

def test_valid_dag():
    """Test a valid Directed Acyclic Graph (DAG) with no cycles."""
    nodes = {
        "start": create_mock_node("start"),
        "step1": create_mock_node("step1"),
        "step2": create_mock_node("step2"),
        "end": create_mock_node("end")
    }
    edges = [
        Edge(id="e1", source="start", target="step1"),
        Edge(id="e2", source="start", target="step2"),
        Edge(id="e3", source="step1", target="end"),
        Edge(id="e4", source="step2", target="end")
    ]
    
    WorkflowDefinition(
        name="Valid DAG",
        description="A simple valid DAG",
        start_node_ids=["start"],
        nodes=nodes,
        edges=edges
    )

def test_direct_self_loop():
    """Test a node that points to itself (A -> A)."""
    nodes = {"a": create_mock_node("a")}
    edges = [Edge(id="e1", source="a", target="a")]
    
    with pytest.raises(ValueError, match="Circular dependency detected"):
        WorkflowDefinition(
            name="Self Loop",
            description="A node pointing to itself",
            start_node_ids=["a"],
            nodes=nodes,
            edges=edges
        )

def test_simple_cycle():
    """Test a simple cycle (A -> B -> A)."""
    nodes = {
        "a": create_mock_node("a"),
        "b": create_mock_node("b")
    }
    edges = [
        Edge(id="e1", source="a", target="b"),
        Edge(id="e2", source="b", target="a")
    ]
    
    with pytest.raises(ValueError, match="Circular dependency detected"):
        WorkflowDefinition(
            name="Simple Cycle",
            description="Two nodes pointing to each other",
            start_node_ids=["a"],
            nodes=nodes,
            edges=edges
        )

def test_complex_cycle():
    """Test a cycle deeper in the graph (A -> B -> C -> B)."""
    nodes = {
        "a": create_mock_node("a"),
        "b": create_mock_node("b"),
        "c": create_mock_node("c"),
        "d": create_mock_node("d")
    }
    edges = [
        Edge(id="e1", source="a", target="b"),
        Edge(id="e2", source="b", target="c"),
        Edge(id="e3", source="c", target="b"),
        Edge(id="e4", source="c", target="d")
    ]
    
    with pytest.raises(ValueError, match="Circular dependency detected"):
        WorkflowDefinition(
            name="Complex Cycle",
            description="A cycle nested in the graph",
            start_node_ids=["a"],
            nodes=nodes,
            edges=edges
        )

def test_multiple_entry_points_with_cycle():
    """Test multiple entry points where one leads to a cycle."""
    nodes = {
        "start1": create_mock_node("start1"),
        "start2": create_mock_node("start2"),
        "a": create_mock_node("a"),
        "b": create_mock_node("b")
    }
    # Path 1: start1 -> a (valid)
    # Path 2: start2 -> b -> b (cycle)
    edges = [
        Edge(id="e1", source="start1", target="a"),
        Edge(id="e2", source="start2", target="b"),
        Edge(id="e3", source="b", target="b")
    ]
    
    with pytest.raises(ValueError, match="Circular dependency detected"):
        WorkflowDefinition(
            name="Multiple Entry Cycle",
            description="Cycle reachable from one of multiple starts",
            start_node_ids=["start1", "start2"],
            nodes=nodes,
            edges=edges
        )

def test_disconnected_cycle_not_reached():
    """
    Test a cycle that exists in the graph but is NOT reachable from any start_node_ids.
    Current implementation only starts DFS from start_node_ids, so it might NOT detect this.
    """
    nodes = {
        "start": create_mock_node("start"),
        "a": create_mock_node("a"),
        "b": create_mock_node("b"),
        "c": create_mock_node("c")
    }
    # Path: start -> a
    # Cycle: b -> c -> b (unreachable from 'start')
    edges = [
        Edge(id="e1", source="start", target="a"),
        Edge(id="e2", source="b", target="c"),
        Edge(id="e3", source="c", target="b")
    ]
    
    WorkflowDefinition(
        name="Unreachable Cycle",
        description="Cycle is not reachable from start nodes",
        start_node_ids=["start"],
        nodes=nodes,
        edges=edges
    )
