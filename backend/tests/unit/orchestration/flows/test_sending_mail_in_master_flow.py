import pytest
from unittest.mock import MagicMock, patch
import uuid
from orchestration.flows.master_flow import execute_automation_flow
from orchestration.tasks.gmail_tasks import GmailTasks

@pytest.mark.asyncio
async def test_master_flow_logic_only():
    """
    Tests that the flow calls the correct Gmail task WITHOUT sending a real email.
    """
    user_id = uuid.uuid4()
    workflow_payload = {
        "name": "Mock Test",
        "actions": [
            {
                "type": "send_email", 
                "config": {"to": "test@test.com", "subject": "Hi", "body": "Msg"}
            }
        ]
    }

    # We patch the 'send_message' method on your GmailTasks class
    # "autospec=True" ensures the mock has the same arguments as the real function
    with patch.object(GmailTasks, 'send_message', autospec=True) as mock_send:
        
        await execute_automation_flow(user_id, workflow_payload)

        # ASSERTION: Did the flow actually try to call send_message?
        mock_send.assert_called_once()
        
        # Check if it passed the right arguments
        args, _ = mock_send.call_args
        assert args[0] == user_id
        assert args[1] == "test@test.com"
        assert args[2] == "Hi"
