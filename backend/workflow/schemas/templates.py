"""Curated starter workflows offered to users with an empty dashboard.

Templates are hardcoded here rather than stored in a table: they are authored
with the codebase, must stay in step with the node schemas, and have no
per-user state. Keeping them as raw dicts that are validated into
``WorkflowSchema`` at import time means a malformed seed fails at boot (and in
every test run) instead of in a user's browser.

The raw-dict form is required, not stylistic: ``EmailReceivedConfig.from_email``
declares ``alias="from"`` without ``populate_by_name``, so the payload key has
to literally be ``"from"``.

Only node types that ``orchestration/flows/master_flow.py`` can actually execute
may appear here — a seed built on a ``coming_soon`` type would deploy and then
never run. ``tests/unit/test_workflow_templates.py`` enforces that.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from workflow.schemas.workflow_schema import WorkflowSchema


class WorkflowTemplateSummary(BaseModel):
    """The gallery card payload — everything the UI shows before a click."""

    id: str
    name: str
    description: str
    category: str
    icon: str
    steps: List[str]


class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    steps: List[str]
    # Not named `schema`: that shadows BaseModel's deprecated `schema` attribute.
    definition: WorkflowSchema

    def summary(self) -> WorkflowTemplateSummary:
        return WorkflowTemplateSummary(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            icon=self.icon,
            steps=self.steps,
        )


def _email_trigger(subject_contains: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": "trigger_1",
        "type": "trigger",
        "config": {
            "type": "email_received",
            "config": {"from": None, "subject_contains": subject_contains},
        },
    }


# Placeholder recipient for seeds that email the user; they land paused so the
# address is edited before the workflow can ever fire.
PLACEHOLDER_RECIPIENT = "you@example.com"


_RAW_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "auto_label_newsletters",
        "name": "Auto-label newsletters",
        "description": (
            "Tags every incoming email whose body contains an unsubscribe link "
            "with a 'Newsletters' label, so promotional mail sorts itself."
        ),
        "category": "Email",
        "icon": "lucide-tag",
        "steps": ["Email received", "Looks like a newsletter?", "Apply label"],
        "definition": {
            "name": "Auto-label newsletters",
            "description": "Label incoming newsletters so they sort themselves.",
            "is_active": False,
            "execution_config": {
                "start_node_ids": ["trigger_1"],
                "nodes": {
                    "trigger_1": _email_trigger(),
                    "condition_1": {
                        "id": "condition_1",
                        "name": "Looks like a newsletter?",
                        "type": "condition",
                        "config": {
                            "type": "if_condition",
                            "config": {
                                "rules": [
                                    {
                                        "variable": "{{trigger_1.body}}",
                                        "operator": "contains",
                                        "value": "unsubscribe",
                                    }
                                ],
                                "match_type": "ALL",
                            },
                        },
                    },
                    "action_1": {
                        "id": "action_1",
                        "name": "Label as Newsletters",
                        "type": "action",
                        "config": {
                            "type": "label_email",
                            "config": {
                                "label_name": "Newsletters",
                                "background_color": "#fb4c2f",
                                "text_color": "#ffffff",
                            },
                        },
                    },
                },
                "edges": [
                    {"id": "e1", "source": "trigger_1", "target": "condition_1"},
                    {
                        "id": "e2",
                        "source": "condition_1",
                        "target": "action_1",
                        "sourceHandle": "true_path",
                    },
                ],
            },
        },
    },
    {
        "id": "out_of_office_reply",
        "name": "Out-of-office auto-reply",
        "description": (
            "Replies to every incoming email with a short away message, in the "
            "original thread. Edit the message, then switch it on while you're away."
        ),
        "category": "Email",
        "icon": "lucide-reply",
        "steps": ["Email received", "Reply in thread"],
        "definition": {
            "name": "Out-of-office auto-reply",
            "description": "Answer incoming mail with an away message.",
            "is_active": False,
            "execution_config": {
                "start_node_ids": ["trigger_1"],
                "nodes": {
                    "trigger_1": _email_trigger(),
                    "action_1": {
                        "id": "action_1",
                        "name": "Send away message",
                        "type": "action",
                        "config": {
                            "type": "reply_email",
                            "config": {
                                "body": (
                                    "Thanks for your email — I'm currently out of "
                                    "office and will reply when I'm back.\n\n"
                                    "If it's urgent, please reach out again with "
                                    "URGENT in the subject line."
                                )
                            },
                        },
                    },
                },
                "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
            },
        },
    },
    {
        "id": "draft_follow_up",
        "name": "Draft a follow-up reply",
        "description": (
            "Reads each incoming email and leaves an AI-written reply waiting in "
            "your drafts. Nothing is sent — you review and hit send yourself."
        ),
        "category": "AI",
        "icon": "lucide-sparkles",
        "steps": ["Email received", "AI drafts a reply"],
        "definition": {
            "name": "Draft a follow-up reply",
            "description": "Leave an AI-written reply in drafts for every email.",
            "is_active": False,
            "execution_config": {
                "start_node_ids": ["trigger_1"],
                "nodes": {
                    "trigger_1": _email_trigger(),
                    "action_1": {
                        "id": "action_1",
                        "name": "Draft reply",
                        "type": "action",
                        "config": {
                            "type": "smart_draft",
                            "config": {
                                "user_prompt": (
                                    "Write a brief, friendly reply that acknowledges "
                                    "the sender's message and proposes a concrete "
                                    "next step. Keep it under 120 words."
                                )
                            },
                        },
                    },
                },
                "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
            },
        },
    },
    {
        "id": "urgent_email_triage",
        "name": "Urgent email triage",
        "description": (
            "Watches for 'urgent' in the subject line, labels those emails red "
            "and sends you a heads-up so they don't get buried."
        ),
        "category": "Email",
        "icon": "lucide-split",
        "steps": ["Email received", "Subject says urgent?", "Label", "Notify me"],
        "definition": {
            "name": "Urgent email triage",
            "description": "Flag urgent mail and send yourself a heads-up.",
            "is_active": False,
            "execution_config": {
                "start_node_ids": ["trigger_1"],
                "nodes": {
                    "trigger_1": _email_trigger(),
                    "condition_1": {
                        "id": "condition_1",
                        "name": "Subject says urgent?",
                        "type": "condition",
                        "config": {
                            "type": "if_condition",
                            "config": {
                                "rules": [
                                    {
                                        "variable": "{{trigger_1.subject}}",
                                        "operator": "contains",
                                        "value": "urgent",
                                    }
                                ],
                                "match_type": "ALL",
                            },
                        },
                    },
                    "action_1": {
                        "id": "action_1",
                        "name": "Label as Urgent",
                        "type": "action",
                        "config": {
                            "type": "label_email",
                            "config": {
                                "label_name": "Urgent",
                                "background_color": "#fb4c2f",
                                "text_color": "#ffffff",
                            },
                        },
                    },
                    "action_2": {
                        "id": "action_2",
                        "name": "Notify me",
                        "type": "action",
                        "config": {
                            "type": "send_email",
                            "config": {
                                "to": PLACEHOLDER_RECIPIENT,
                                "subject": "Urgent: {{trigger_1.subject}}",
                                "body": (
                                    "An urgent email arrived from "
                                    "{{trigger_1.from}}.\n\n{{trigger_1.body}}"
                                ),
                            },
                        },
                    },
                },
                "edges": [
                    {"id": "e1", "source": "trigger_1", "target": "condition_1"},
                    {
                        "id": "e2",
                        "source": "condition_1",
                        "target": "action_1",
                        "sourceHandle": "true_path",
                    },
                    {"id": "e3", "source": "action_1", "target": "action_2"},
                ],
            },
        },
    },
    {
        "id": "daily_digest",
        "name": "Daily morning reminder",
        "description": (
            "Emails you a short prompt every weekday at 09:00 — a starting point "
            "for any scheduled report or check-in."
        ),
        "category": "Scheduled",
        "icon": "lucide-calendar",
        "steps": ["Every weekday 09:00", "Send email"],
        "definition": {
            "name": "Daily morning reminder",
            "description": "A scheduled email that runs every weekday morning.",
            "is_active": False,
            "execution_config": {
                "start_node_ids": ["trigger_1"],
                "nodes": {
                    "trigger_1": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "config": {
                            "type": "schedule",
                            "config": {
                                "cron": "0 9 * * 1-5",
                                "description": "Every weekday at 09:00",
                            },
                        },
                    },
                    "action_1": {
                        "id": "action_1",
                        "name": "Send the reminder",
                        "type": "action",
                        "config": {
                            "type": "send_email",
                            "config": {
                                "to": PLACEHOLDER_RECIPIENT,
                                "subject": "Your morning check-in",
                                "body": (
                                    "Good morning! Here's your daily reminder.\n\n"
                                    "Edit this workflow to change what gets sent."
                                ),
                            },
                        },
                    },
                },
                "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}],
            },
        },
    },
]


# Validated at import: a broken seed breaks the app boot, not a user's browser.
WORKFLOW_TEMPLATES: Dict[str, WorkflowTemplate] = {
    template.id: template
    for template in (WorkflowTemplate.model_validate(raw) for raw in _RAW_TEMPLATES)
}


def list_templates() -> List[WorkflowTemplate]:
    """Every template, in authoring order."""
    return list(WORKFLOW_TEMPLATES.values())


def get_template(template_id: str) -> Optional[WorkflowTemplate]:
    return WORKFLOW_TEMPLATES.get(template_id)
