from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from workflow.services.workflow_service import WorkflowService


def _db_returning(workflow):
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = workflow
    db.execute = AsyncMock(return_value=mock_result)
    return db


async def test_update_config_none_ui_metadata_preserves_existing_and_updates_config():
    workflow = MagicMock()
    workflow.ui_metadata = {"existing": "kept"}
    db = _db_returning(workflow)

    schema = MagicMock()
    schema.ui_metadata = None
    schema.execution_config.model_dump.return_value = {"nodes": {}}

    # Must not raise AttributeError on None ui_metadata.
    result = await WorkflowService.update_config(db, uuid4(), schema)

    assert result is workflow
    # config still updated...
    assert workflow.config == {"nodes": {}}
    # ...but existing ui_metadata left untouched.
    assert workflow.ui_metadata == {"existing": "kept"}
    db.flush.assert_called_once()


async def test_update_config_with_ui_metadata_overwrites():
    workflow = MagicMock()
    workflow.ui_metadata = {"old": "value"}
    db = _db_returning(workflow)

    schema = MagicMock()
    schema.ui_metadata.model_dump.return_value = {"new": "value"}
    schema.execution_config.model_dump.return_value = {"nodes": {}}

    await WorkflowService.update_config(db, uuid4(), schema)

    assert workflow.ui_metadata == {"new": "value"}
    assert workflow.config == {"nodes": {}}


async def test_update_config_missing_workflow_returns_none():
    db = _db_returning(None)
    schema = MagicMock()

    assert await WorkflowService.update_config(db, uuid4(), schema) is None
    db.flush.assert_not_called()


async def test_update_config_increments_version():
    workflow = MagicMock()
    workflow.ui_metadata = {}
    workflow.version = 1
    db = _db_returning(workflow)

    schema = MagicMock()
    schema.ui_metadata = None
    schema.execution_config.model_dump.return_value = {"nodes": {}}

    await WorkflowService.update_config(db, uuid4(), schema)
    assert workflow.version == 2

    await WorkflowService.update_config(db, uuid4(), schema)
    assert workflow.version == 3
