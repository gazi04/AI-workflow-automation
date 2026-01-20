import asyncio
import os
from uuid import UUID
from gmail.services import GmailService
from core.database import db_session
from orchestration.tasks.gmail_tasks import GmailTasks

REAL_USER_ID = UUID("d2b00790-dcdc-43c5-b2a0-2291aec393c0")

async def test_label_mail_real_data():
    print(f"--- Starting Real Integration Test for User: {REAL_USER_ID} ---")
    
    target_label = "Test2"

    try:
        latest_message_id = GmailService.get_latest_message_id(REAL_USER_ID)

        dummy_email = {"message_id": latest_message_id}

        labels = GmailTasks.label_mail(
            user_id=REAL_USER_ID,
            label=target_label,
            backgroundColor="",
            textColor="",
            original_email=dummy_email
        )

        print("\n✅ API Call Successful!")
        print(f"Total Labels found in Gmail: {len(labels)}")
        
        print("\nFirst 5 Labels found:")
        for l in labels[:5]:
            print(f" - {l['name']} (ID: {l['id']})")

    except Exception as e:
        print("\n❌ Test Failed!")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Detail: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(test_label_mail_real_data())
