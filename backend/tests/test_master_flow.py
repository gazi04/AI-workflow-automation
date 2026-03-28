import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock

from orchestration.flows.master_flow import execute_automation_flow

# --- 1. Test Data Fixtures ---

@pytest.fixture
def mock_user_id():
    return uuid4()

@pytest.fixture
def base_workflow_json():
    """Generates a valid DAG workflow dict matching your Pydantic schemas."""
    return {
        "name": "Condition Test Workflow",
        "description": "Tests if routing works",
        "start_node_ids": ["node_trigger"],
        "nodes": {
            "node_trigger": {
                "id": "node_trigger",
                "type": "trigger",
                "config": {
                    "type": "email_received",
                    "config": {"subject_contains": "Alert"}
                }
            },
            "node_condition": {
                "id": "node_condition",
                "type": "condition",
                "config": {
                    "type": "if_condition",
                    "config": {
                        "match_type": "ALL",
                        "rules": [
                            {
                                "variable": "{{trigger.original_email.subject}}",
                                "operator": "contains",
                                "value": "Urgent"
                            }
                        ]
                    }
                }
            },
            "node_true_action": {
                "id": "node_true_action",
                "type": "action",
                "config": {
                    "type": "label_email",
                    "config": {
                        "label_info": {
                            "name": "URGENT",
                            "labelListVisibility": "labelShow",
                            "messageListVisibility": "show",
                            "type": "user"
                        }
                    }
                }
            },
            "node_false_action": {
                "id": "node_false_action",
                "type": "action",
                "config": {
                    "type": "send_email",
                    "config": {
                        "to": "boss@company.com",
                        "subject": "FYI: {{trigger.original_email.subject}}",
                        "body": "Just logging this."
                    }
                }
            }
        },
        "edges": [
            {"id": "e1", "source": "node_trigger", "target": "node_condition"},
            {"id": "e2", "source": "node_condition", "target": "node_true_action", "sourceHandle": "true_path"},
            {"id": "e3", "source": "node_condition", "target": "node_false_action", "sourceHandle": "false_path"}
        ]
    }


def generate_trigger_context(subject: str):
    """Helper to generate mock email payloads."""
    return {
        "trigger_context": {
            "matched_trigger_node_id": "node_trigger",
            "original_email": {
                "message_id": "msg_123",
                "thread_id": "thread_123",
                "subject": subject,
                "from": "sender@test.com",
                "snippet": "Hello world",
                "header_message_id": "hdr_123",
                "references": "",
                "body": "Hello world email body"
            }
        }
    }


# --- 2. The Tests ---

# UPDATE THESE PATHS TO POINT TO WHERE MASTER FLOW IMPORTS THE TASKS
@patch("orchestration.flows.master_flow.send_message")
@patch("orchestration.flows.master_flow.label_mail")
def test_condition_routes_to_true_path(mock_label_mail, mock_send_message, mock_user_id, base_workflow_json):
    """
    Test that an email with 'Urgent' in the subject successfully
    triggers the label_mail task and IGNORES the send_message task.
    """
    # Arrange: Setup mock task returns (chaining .submit().result())
    mock_label_mail.submit.return_value.result.return_value = {"status": "labeled"}
    mock_send_message.submit.return_value.result.return_value = {"status": "sent"}

    # Arrange: Provide a subject that MATCHES the condition
    trigger_context = generate_trigger_context(subject="Urgent: Server Down!")

    # Act
    execute_automation_flow(
        user_id=mock_user_id,
        workflow_data=base_workflow_json,
        trigger_context=trigger_context
    )

    # Assert: The true path (label) ran, the false path (send_email) did not.
    mock_label_mail.submit.assert_called_once()
    mock_send_message.submit.assert_not_called()

    # Assert: Verify Variable Resolution worked correctly on the Label schema
    args, kwargs = mock_label_mail.submit.call_args
    assert args[0] == mock_user_id
    assert args[1].name == "URGENT" # Checked that the Pydantic schema passed correctly


@patch("orchestration.flows.master_flow.send_message")
@patch("orchestration.flows.master_flow.label_mail")
def test_condition_routes_to_false_path(mock_label_mail, mock_send_message, mock_user_id, base_workflow_json):
    """
    Test that an email WITHOUT 'Urgent' in the subject successfully
    triggers the send_message task and IGNORES the label_mail task.
    """
    # Arrange: Setup mock task returns
    mock_label_mail.submit.return_value.result.return_value = {"status": "labeled"}
    mock_send_message.submit.return_value.result.return_value = {"status": "sent"}

    # Arrange: Provide a subject that FAILS the condition
    trigger_context = generate_trigger_context(subject="Weekly Newsletter")

    # Act
    execute_automation_flow(
        user_id=mock_user_id,
        workflow_data=base_workflow_json,
        trigger_context=trigger_context
    )

    # Assert: The false path (send_email) ran, the true path (label) did not.
    mock_send_message.submit.assert_called_once()
    mock_label_mail.submit.assert_not_called()

    # Assert: Verify Variable Resolution successfully swapped {{trigger.original_email.subject}}
    args, kwargs = mock_send_message.submit.call_args
    passed_subject = args[2]  # The 3rd positional argument in send_message is 'subject'
    assert passed_subject == "FYI: Weekly Newsletter"
