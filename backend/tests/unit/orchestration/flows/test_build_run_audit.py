from orchestration.flows.master_flow import build_run_audit


def test_all_success():
    node_outputs = {"a": {"id": "1"}, "b": {"id": "2"}}
    failed_nodes = {}

    node_results, status = build_run_audit(node_outputs, failed_nodes)

    assert status == "success"
    assert node_results["a"] == {
        "output": {"id": "1"},
        "status": "success",
        "error": None,
    }
    assert node_results["b"]["status"] == "success"


def test_all_failed():
    node_outputs = {"a": {"error": "boom"}}
    failed_nodes = {"a": "boom"}

    node_results, status = build_run_audit(node_outputs, failed_nodes)

    assert status == "failed"
    assert node_results["a"] == {"output": None, "status": "failed", "error": "boom"}


def test_partial():
    node_outputs = {"a": {"id": "1"}, "b": {"error": "boom"}}
    failed_nodes = {"b": "boom"}

    node_results, status = build_run_audit(node_outputs, failed_nodes)

    assert status == "partial"
    assert node_results["a"]["status"] == "success"
    assert node_results["b"]["status"] == "failed"
    assert node_results["b"]["error"] == "boom"


def test_empty_run_is_success():
    node_results, status = build_run_audit({}, {})

    assert status == "success"
    assert node_results == {}


def test_non_serializable_output_is_coerced_to_str():
    class Weird:
        def __str__(self):
            return "weird-repr"

    node_outputs = {"a": Weird()}

    node_results, status = build_run_audit(node_outputs, {})

    assert status == "success"
    assert node_results["a"]["output"] == "weird-repr"


# ---------------------------------------------------------------------------
# Handled failures — a node caught by an error_path edge is neither a success
# nor a run-failing error.
# ---------------------------------------------------------------------------


def test_handled_node_gets_handled_status_and_keeps_its_error():
    node_outputs = {"a": {"id": "ok"}, "b": {"error": "Gmail down"}}

    node_results, status = build_run_audit(node_outputs, {}, {"b": "Gmail down"})

    assert node_results["a"]["status"] == "success"
    assert node_results["b"]["status"] == "handled"
    assert node_results["b"]["error"] == "Gmail down"
    assert node_results["b"]["output"] is None
    assert status == "partial"


def test_only_handled_failures_never_report_failed():
    """Every failure was modelled by the user, so the run is not an incident."""
    node_outputs = {"b": {"error": "Gmail down"}}

    _, status = build_run_audit(node_outputs, {}, {"b": "Gmail down"})

    assert status == "partial"


def test_unhandled_failure_still_fails_the_run():
    node_outputs = {"b": {"error": "Gmail down"}}

    node_results, status = build_run_audit(node_outputs, {"b": "Gmail down"}, {})

    assert node_results["b"]["status"] == "failed"
    assert status == "failed"


def test_unhandled_failure_alongside_a_success_is_partial():
    node_outputs = {"a": {"id": "ok"}, "b": {"error": "Gmail down"}}

    _, status = build_run_audit(node_outputs, {"b": "Gmail down"}, {})

    assert status == "partial"


def test_failed_takes_precedence_over_handled_for_the_same_node():
    """A node can only be in one bucket; failed is the conservative reading."""
    node_outputs = {"b": {"error": "Gmail down"}}

    node_results, _ = build_run_audit(
        node_outputs, {"b": "Gmail down"}, {"b": "Gmail down"}
    )

    assert node_results["b"]["status"] == "failed"


def test_handled_nodes_argument_is_optional():
    """Existing callers that pass two positional args keep working."""
    node_results, status = build_run_audit({"a": {"id": "ok"}}, {})

    assert status == "success"
    assert node_results["a"]["status"] == "success"
