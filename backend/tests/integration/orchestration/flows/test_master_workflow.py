import pytest
import uuid
from orchestration.flows.master_flow import execute_automation_flow

REAL_USER_ID = uuid.UUID("d2b00790-dcdc-43c5-b2a0-2291aec393c0") 
TEST_RECIPIENT = "gazmend.halili.st@uni-gjilan.net"

@pytest.mark.asyncio
async def test_master_flow_send_email_real():
    """
    This test executes the actual master flow with real data.
    It WILL send a real email if credentials are correct.
    """
    print("\n🚀 Starting Master Flow Integration Test...")

    workflow_payload = {
        "name": "Pytest Integration Workflow",
        "actions": [
            {
                "type": "send_email",
                "config": {
                    "to": TEST_RECIPIENT,
                    "subject": "Test from Pytest Flow 🧪",
                    "body": "If you are reading this, the master flow orchestration is working correctly!"
                }
            }
        ]
    }

    try:
        await execute_automation_flow(
            user_id=REAL_USER_ID,
            workflow_data=workflow_payload,
            trigger_context=None
        )
        print("\n✅ Flow finished without errors.")
    except Exception as e:
        pytest.fail(f"Flow failed with error: {e}")
