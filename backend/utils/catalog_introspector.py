import typing

from pydantic import BaseModel, EmailStr
from pydantic.fields import FieldInfo

from workflow.schemas.action import Action
from workflow.schemas.catalog import FieldDefinition, NodeDefinition, WorkflowCatalog
from workflow.schemas.condition_nodes import Condition
from workflow.schemas.trigger import Trigger


def _map_annotation_to_ui_type(annotation, field_info: FieldInfo) -> str:
    """Maps a Python/Pydantic annotation to a frontend widget string."""
    if annotation is EmailStr:
        return "email"
    if annotation is bool:
        return "toggle"
    if annotation is int:
        return "number"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return "object"  # TODO: flatten nested models in a future phase
    # check for manual override via json_schema_extra: {"widget": "password"}
    extra = field_info.json_schema_extra or {}
    return extra.get("widget", "text")


def _build_node_definitions(union_type) -> list[NodeDefinition]:
    nodes = []
    # If the union has only one member, typing.get_args returns an empty tuple
    clss = typing.get_args(union_type) or [union_type]
    for cls in clss:
        schema_extra = cls.model_config.get("json_schema_extra", {})
        config_cls = cls.model_fields["config"].annotation
        # Literal["email_received"] -> get_args returns ("email_received",)
        type_literal = typing.get_args(cls.model_fields["type"].annotation)[0]

        fields = []
        for field_name, field_info in config_cls.model_fields.items():
            key = field_info.alias or field_name
            fields.append(
                FieldDefinition(
                    key=key,
                    label=key.replace("_", " ").title(),
                    type=_map_annotation_to_ui_type(field_info.annotation, field_info),
                    required=field_info.is_required(),
                    default=field_info.default
                    if not field_info.is_required()
                    else None,
                    description=field_info.description or "",
                )
            )

        nodes.append(
            NodeDefinition(
                type=type_literal,
                category=schema_extra.get("category", "General"),
                icon=schema_extra.get("icon", "lucide-help-circle"),
                label=type_literal.replace("_", " ").title(),
                description="",
                fields=fields,
            )
        )
    return nodes


def build_catalog() -> WorkflowCatalog:
    """
    Introspects the Trigger and Action unions and returns a structured
    WorkflowCatalog manifest for the frontend to consume.
    """
    trigger_union = typing.get_args(Trigger)[0]  # unwrap Annotated[Union[...], ...]
    action_union = typing.get_args(Action)[0]
    condition_union = typing.get_args(Condition)[0]
 
    return WorkflowCatalog(
        triggers=_build_node_definitions(trigger_union),
        actions=_build_node_definitions(action_union),
        conditions=_build_node_definitions(condition_union),
    )
