from prefect import flow
from typing import Dict, Any, List

# Import other tasks as you build them (e.g., slack_tasks)

@flow(name="Master Automation Executor")
def execute_automation_flow(user_id: str, workflow_data: Dict[str, Any]):
    """
    This flow is generic. It doesn't know what it does until it receives
    the 'workflow_data' JSON at runtime.
    """
    print(f"🚀 Starting Workflow: {workflow_data.get('name')}")
    
    actions: List[Dict] = workflow_data.get("actions", [])
    
    for action in actions:
        action_type = action.get("type")
        config = action.get("config", {})
        
        try:
            if action_type == "send_email":
                send_gmail_message_task(
                    user_id=user_id,
                    to=config.get("to"),
                    subject=config.get("subject"),
                    body=config.get("body")
                )
                
            elif action_type == "send_slack_message":
                print(f"Send slack message to {config.get('channel')}")
                
            
        except Exception as e:
            # todo: ✨ send a notification to the user here
            print(f"❌ Error executing action {action_type}: {e}")
