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
