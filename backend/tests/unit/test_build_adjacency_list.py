from utils.build_adjacency_list import build_adjacency_list
from workflow.schemas.edges import Edge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_edge(id: str, source: str, target: str, source_handle: str = None) -> Edge:
    return Edge(id=id, source=source, target=target, sourceHandle=source_handle)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_edge_list_returns_empty_dict():
    assert build_adjacency_list([]) == {}


def test_single_edge_grouped_by_source():
    edge = make_edge("e1", "A", "B")
    result = build_adjacency_list([edge])
    assert list(result.keys()) == ["A"]
    assert result["A"] == [edge]


def test_multiple_edges_from_same_source():
    e1 = make_edge("e1", "A", "B")
    e2 = make_edge("e2", "A", "C")
    result = build_adjacency_list([e1, e2])
    assert set(result.keys()) == {"A"}
    assert result["A"] == [e1, e2]


def test_linear_chain_grouped_per_source():
    e1 = make_edge("e1", "A", "B")
    e2 = make_edge("e2", "B", "C")
    e3 = make_edge("e3", "C", "D")
    result = build_adjacency_list([e1, e2, e3])
    assert set(result.keys()) == {"A", "B", "C"}
    assert result["A"] == [e1]
    assert result["B"] == [e2]
    assert result["C"] == [e3]


def test_target_nodes_not_in_result_if_no_outgoing_edges():
    edge = make_edge("e1", "A", "B")
    result = build_adjacency_list([edge])
    assert "B" not in result


def test_condition_edges_with_source_handle_preserved():
    true_edge = make_edge("e1", "cond", "action_true", source_handle="true_path")
    false_edge = make_edge("e2", "cond", "action_false", source_handle="false_path")
    result = build_adjacency_list([true_edge, false_edge])
    assert len(result["cond"]) == 2
    handles = {e.sourceHandle for e in result["cond"]}
    assert handles == {"true_path", "false_path"}


def test_edge_order_preserved():
    e1 = make_edge("e1", "A", "B")
    e2 = make_edge("e2", "A", "C")
    e3 = make_edge("e3", "A", "D")
    result = build_adjacency_list([e1, e2, e3])
    assert result["A"] == [e1, e2, e3]
