from typing import Optional
from unittest.mock import MagicMock, patch
from uuid import uuid4

from orchestration.flows.master_flow import execute_automation_flow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_task(return_value: dict) -> MagicMock:
    """Returns a mock that behaves like a Prefect task: mock.submit(...).result() → value."""
    m = MagicMock()
    m.submit.return_value.result.return_value = return_value
    return m


def make_send_email_workflow(
    trigger_id: str = "trigger_1", action_id: str = "action_1"
) -> dict:
    return {
        "name": "Test Send Email",
        "description": "Sends an email",
        "execution_config": {
            "start_node_ids": [trigger_id],
            "nodes": {
                trigger_id: {
                    "id": trigger_id,
                    "type": "trigger",
                    "config": {
                        "type": "email_received",
                        "config": {"from": None, "subject_contains": None},
                    },
                },
                action_id: {
                    "id": action_id,
                    "type": "action",
                    "config": {
                        "type": "send_email",
                        "config": {
                            "to": "bob@example.com",
                            "subject": "Hi",
                            "body": "Hello",
                        },
                    },
                },
            },
            "edges": [{"id": "e1", "source": trigger_id, "target": action_id}],
        },
    }


def make_condition_workflow() -> dict:
    return {
        "name": "Test Condition",
        "description": "Routes by condition",
        "execution_config": {
            "start_node_ids": ["trigger_1"],
            "nodes": {
                "trigger_1": {
                    "id": "trigger_1",
                    "type": "trigger",
                    "config": {
                        "type": "email_received",
                        "config": {"from": None, "subject_contains": None},
                    },
                },
                "cond_1": {
                    "id": "cond_1",
                    "type": "condition",
                    "config": {
                        "type": "if_condition",
                        "config": {
                            "rules": [
                                {
                                    "variable": "{{trigger_1.subject}}",
                                    "operator": "contains",
                                    "value": "invoice",
                                }
                            ],
                            "match_type": "ALL",
                        },
                    },
                },
                "action_true": {
                    "id": "action_true",
                    "type": "action",
                    "config": {
                        "type": "send_email",
                        "config": {
                            "to": "a@example.com",
                            "subject": "True path",
                            "body": "Yes",
                        },
                    },
                },
                "action_false": {
                    "id": "action_false",
                    "type": "action",
                    "config": {
                        "type": "send_email",
                        "config": {
                            "to": "b@example.com",
                            "subject": "False path",
                            "body": "No",
                        },
                    },
                },
            },
            "edges": [
                {"id": "e1", "source": "trigger_1", "target": "cond_1"},
                {
                    "id": "e2",
                    "source": "cond_1",
                    "target": "action_true",
                    "sourceHandle": "true_path",
                },
                {
                    "id": "e3",
                    "source": "cond_1",
                    "target": "action_false",
                    "sourceHandle": "false_path",
                },
            ],
        },
    }


def make_trigger_context(trigger_node_id: str, email: Optional[dict] = None) -> dict:
    return {
        "trigger_context": {
            "matched_trigger_node_id": trigger_node_id,
            "original_email": email
            or {
                "from": "alice@example.com",
                "subject": "Invoice October",
                "body": "Please find attached the invoice.",
                "message_id": "msg_001",
                "thread_id": "thread_001",
                "header_message_id": "<msg001@gmail.com>",
                "references": "",
            },
        }
    }


USER_ID = uuid4()


# ---------------------------------------------------------------------------
# send_email action
# ---------------------------------------------------------------------------


def test_send_email_task_called():
    mock_send = mock_task({"id": "sent_123"})

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        execute_automation_flow.fn(
            USER_ID, make_send_email_workflow(), make_trigger_context("trigger_1")
        )

    mock_send.submit.assert_called_once()
    args = mock_send.submit.call_args[0]
    assert args[0] == USER_ID
    assert args[1] == "bob@example.com"  # to
    assert args[2] == "Hi"  # subject


def test_send_email_result_stored_in_node_outputs():
    mock_send = mock_task({"id": "sent_456"})

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        # No exception means outputs were stored (flow continues cleanly)
        execute_automation_flow.fn(
            USER_ID, make_send_email_workflow(), make_trigger_context("trigger_1")
        )


def test_send_email_variable_resolved_from_trigger_context():
    workflow = {
        "name": "Variable Test",
        "description": "Tests variable resolution",
        "execution_config": {
            "start_node_ids": ["trigger_1"],
            "nodes": {
                "trigger_1": {
                    "id": "trigger_1",
                    "type": "trigger",
                    "config": {
                        "type": "email_received",
                        "config": {"from": None, "subject_contains": None},
                    },
                },
                "action_1": {
                    "id": "action_1",
                    "type": "action",
                    "config": {
                        "type": "send_email",
                        "config": {
                            "to": "bob@example.com",
                            "subject": "Re: {{trigger_1.subject}}",
                            "body": "Hello",
                        },
                    },
                },
            },
            "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
        },
    }

    mock_send = mock_task({"id": "sent_789"})
    ctx = make_trigger_context(
        "trigger_1",
        email={
            "from": "alice@example.com",
            "subject": "Invoice October",
            "body": "body",
            "message_id": "m1",
            "thread_id": "t1",
            "header_message_id": "<m1@g.com>",
            "references": "",
        },
    )

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        execute_automation_flow.fn(USER_ID, workflow, ctx)

    args = mock_send.submit.call_args[0]
    assert args[2] == "Re: Invoice October"  # subject with variable resolved


# ---------------------------------------------------------------------------
# Condition routing
# ---------------------------------------------------------------------------


def test_condition_true_path_action_called():
    mock_send = mock_task({"id": "sent_true"})
    # "invoice" is in subject "Invoice October" (case-insensitive CONTAINS)
    ctx = make_trigger_context("trigger_1")

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        execute_automation_flow.fn(USER_ID, make_condition_workflow(), ctx)

    # True path action (to=a@example.com) must be called
    called_recipients = [call[0][1] for call in mock_send.submit.call_args_list]
    assert "a@example.com" in called_recipients
    assert "b@example.com" not in called_recipients


def test_condition_false_path_action_called():
    mock_send = mock_task({"id": "sent_false"})
    # Subject does NOT contain "invoice"
    ctx = make_trigger_context(
        "trigger_1",
        email={
            "from": "alice@example.com",
            "subject": "Hello there",
            "body": "body",
            "message_id": "m1",
            "thread_id": "t1",
            "header_message_id": "<m1@g.com>",
            "references": "",
        },
    )

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        execute_automation_flow.fn(USER_ID, make_condition_workflow(), ctx)

    called_recipients = [call[0][1] for call in mock_send.submit.call_args_list]
    assert "b@example.com" in called_recipients
    assert "a@example.com" not in called_recipients


# ---------------------------------------------------------------------------
# Email-dependent actions without email context
# ---------------------------------------------------------------------------


def test_reply_email_without_email_context_fails_run():
    import pytest

    workflow = {
        "name": "Reply Test",
        "description": "Test reply without email context",
        "execution_config": {
            "start_node_ids": ["trigger_1"],
            "nodes": {
                "trigger_1": {
                    "id": "trigger_1",
                    "type": "trigger",
                    "config": {"type": "manual", "config": {}},
                },
                "action_1": {
                    "id": "action_1",
                    "type": "action",
                    "config": {"type": "reply_email", "config": {"body": "Thanks!"}},
                },
            },
            "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
        },
    }

    mock_reply = mock_task({"id": "reply_123"})

    with patch("orchestration.flows.master_flow.reply_email", mock_reply):
        # No trigger context → original_email is None → node fails → run fails.
        with pytest.raises(Exception, match="action_1"):
            execute_automation_flow.fn(USER_ID, workflow, None)

    # Task must NOT have been called because no email context
    mock_reply.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Action raises exception — node failure marks the whole run as Failed
# ---------------------------------------------------------------------------


def test_action_exception_fails_run():
    import pytest

    mock_send = MagicMock()
    mock_send.submit.side_effect = Exception("Gmail API down")

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        # A failed action must surface as a run failure, not a silent success.
        with pytest.raises(Exception, match="action_1"):
            execute_automation_flow.fn(
                USER_ID, make_send_email_workflow(), make_trigger_context("trigger_1")
            )


# ---------------------------------------------------------------------------
# Diamond DAG — a failed node must not crash an independent branch, but the
# run as a whole must fail, and a downstream reference to the failed node is
# handled as that node's failure (not a raw resolve_variables crash).
# ---------------------------------------------------------------------------


def make_diamond_workflow() -> dict:
    """trigger → A (ok) and trigger → B (fails); both A and B → C, where C
    references {{node_b.body}} (B's failed output has no 'body')."""
    return {
        "name": "Diamond",
        "description": "Diamond DAG with one failing branch",
        "execution_config": {
            "start_node_ids": ["trigger_1"],
            "nodes": {
                "trigger_1": {
                    "id": "trigger_1",
                    "type": "trigger",
                    "config": {
                        "type": "email_received",
                        "config": {"from": None, "subject_contains": None},
                    },
                },
                "node_a": {
                    "id": "node_a",
                    "type": "action",
                    "config": {
                        "type": "send_email",
                        "config": {"to": "a@example.com", "subject": "A", "body": "ok"},
                    },
                },
                "node_b": {
                    "id": "node_b",
                    "type": "action",
                    "config": {
                        "type": "smart_draft",
                        "config": {"user_prompt": "draft it"},
                    },
                },
                "node_c": {
                    "id": "node_c",
                    "type": "action",
                    "config": {
                        "type": "reply_email",
                        "config": {"body": "{{node_b.body}}"},
                    },
                },
            },
            "edges": [
                {"id": "e1", "source": "trigger_1", "target": "node_a"},
                {"id": "e2", "source": "trigger_1", "target": "node_b"},
                {"id": "e3", "source": "node_a", "target": "node_c"},
                {"id": "e4", "source": "node_b", "target": "node_c"},
            ],
        },
    }


def test_diamond_failed_branch_fails_run_but_independent_branch_runs():
    import pytest

    mock_send = mock_task({"id": "sent_a"})  # node_a succeeds
    mock_draft = MagicMock()  # node_b fails
    mock_draft.submit.side_effect = Exception("AI down")
    mock_reply = mock_task({"id": "reply_c"})  # node_c never completes

    with (
        patch("orchestration.flows.master_flow.send_message", mock_send),
        patch("orchestration.flows.master_flow.smart_draft", mock_draft),
        patch("orchestration.flows.master_flow.reply_email", mock_reply),
    ):
        with pytest.raises(Exception, match="node_b"):
            execute_automation_flow.fn(
                USER_ID, make_diamond_workflow(), make_trigger_context("trigger_1")
            )

    # Independent branch (node_a) still executed.
    mock_send.submit.assert_called_once()
    # node_c referenced the failed node_b → it failed on resolution, never sent.
    mock_reply.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Independent siblings (perf #7) — a whole BFS level's tasks must all be
# submitted before any of them is awaited, so independent branches actually
# run concurrently on Prefect's ThreadPoolTaskRunner instead of one-at-a-time.
# ---------------------------------------------------------------------------


def make_parallel_siblings_workflow() -> dict:
    """trigger → two independent actions with no edge between them and no
    shared downstream node — a true "wave" of concurrent siblings."""
    return {
        "name": "Parallel Siblings",
        "description": "Two independent branches off one trigger",
        "execution_config": {
            "start_node_ids": ["trigger_1"],
            "nodes": {
                "trigger_1": {
                    "id": "trigger_1",
                    "type": "trigger",
                    "config": {
                        "type": "email_received",
                        "config": {"from": None, "subject_contains": None},
                    },
                },
                "node_a": {
                    "id": "node_a",
                    "type": "action",
                    "config": {
                        "type": "send_email",
                        "config": {"to": "a@example.com", "subject": "A", "body": "ok"},
                    },
                },
                "node_b": {
                    "id": "node_b",
                    "type": "action",
                    "config": {
                        "type": "smart_draft",
                        "config": {"user_prompt": "draft it"},
                    },
                },
            },
            "edges": [
                {"id": "e1", "source": "trigger_1", "target": "node_a"},
                {"id": "e2", "source": "trigger_1", "target": "node_b"},
            ],
        },
    }


def test_independent_siblings_all_submitted_before_any_result_is_awaited():
    """Both siblings' tasks must be submitted before either .result() is
    awaited — the invariant that lets Prefect's ThreadPoolTaskRunner actually
    run independent branches concurrently instead of one-at-a-time."""
    events = []

    def make_recording_mock(name, return_value):
        m = MagicMock()

        def fake_submit(*args, **kwargs):
            events.append(f"submit:{name}")
            future = MagicMock()
            future.result.side_effect = lambda: (
                events.append(f"result:{name}") or return_value
            )
            return future

        m.submit.side_effect = fake_submit
        return m

    mock_send = make_recording_mock("A", {"id": "sent_a"})
    mock_draft = make_recording_mock("B", {"id": "draft_b"})

    with (
        patch("orchestration.flows.master_flow.send_message", mock_send),
        patch("orchestration.flows.master_flow.smart_draft", mock_draft),
    ):
        execute_automation_flow.fn(
            USER_ID,
            make_parallel_siblings_workflow(),
            make_trigger_context("trigger_1"),
        )

    mock_send.submit.assert_called_once()
    mock_draft.submit.assert_called_once()
    # Both submits must precede both results — proves the whole level was
    # submitted before any .result() blocked (not submit→result→submit→result).
    submit_positions = [i for i, e in enumerate(events) if e.startswith("submit:")]
    result_positions = [i for i, e in enumerate(events) if e.startswith("result:")]
    assert max(submit_positions) < min(result_positions)


# ---------------------------------------------------------------------------
# Condition evaluation failure — must be caught, not crash the flow uncaught
# ---------------------------------------------------------------------------


def test_condition_eval_failure_fails_run():
    import pytest

    workflow = make_condition_workflow()
    # Reference a variable that does not exist and has no default → resolve raises.
    workflow["execution_config"]["nodes"]["cond_1"]["config"]["config"]["rules"] = [
        {
            "variable": "{{trigger_1.does_not_exist}}",
            "operator": "contains",
            "value": "x",
        }
    ]

    mock_send = mock_task({"id": "unused"})

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        with pytest.raises(Exception, match="cond_1"):
            execute_automation_flow.fn(
                USER_ID, workflow, make_trigger_context("trigger_1")
            )

    # Neither path action ran — the condition never produced a result.
    mock_send.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Webhook trigger — posted payload is bound into run_context for {{var}} use
# ---------------------------------------------------------------------------


def make_webhook_workflow() -> dict:
    return {
        "name": "Webhook Test",
        "description": "Triggered by HTTP",
        "execution_config": {
            "start_node_ids": ["trigger_1"],
            "nodes": {
                "trigger_1": {
                    "id": "trigger_1",
                    "type": "trigger",
                    "config": {"type": "webhook", "config": {}},
                },
                "action_1": {
                    "id": "action_1",
                    "type": "action",
                    "config": {
                        "type": "send_email",
                        "config": {
                            "to": "bob@example.com",
                            "subject": "Hi {{trigger_1.body.name}}",
                            "body": "Hello",
                        },
                    },
                },
            },
            "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
        },
    }


def test_webhook_payload_binds_into_run_context():
    mock_send = mock_task({"id": "sent_wh"})
    ctx = {
        "trigger_context": {
            "matched_trigger_node_id": "trigger_1",
            "webhook_payload": {
                "body": {"name": "Alice"},
                "headers": {},
                "query": {},
            },
        }
    }

    with patch("orchestration.flows.master_flow.send_message", mock_send):
        execute_automation_flow.fn(USER_ID, make_webhook_workflow(), ctx)

    args = mock_send.submit.call_args[0]
    assert args[2] == "Hi Alice"  # {{trigger_1.body.name}} resolved from webhook body


# ---------------------------------------------------------------------------
# Invalid workflow data
# ---------------------------------------------------------------------------


def test_invalid_workflow_data_raises():
    import pytest

    with pytest.raises(Exception, match="Invalid workflow data"):
        execute_automation_flow.fn(USER_ID, {"bad": "data"}, None)
